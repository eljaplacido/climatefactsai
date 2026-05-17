"""ND-GAIN adapter tests (Phase 3 wave 6).

Verifies:
- Standard schema (ISO3 / Year / Index) parsed correctly
- Header variants resolved (ISO_alpha3, iso_alpha3_code, etc.)
- Scores outside [0, 100] clamped (rejected)
- Unknown ISO codes skipped
- Missing required headers degrades gracefully (no crash, no records)
- min_year filter applied
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


def _make_csv_client(csv_text: str, *, status_code: int = 200) -> httpx.AsyncClient:
    class _Resp:
        def __init__(self, text, code):
            self.text = text
            self.status_code = code
            self.request = httpx.Request("GET", "https://gain.nd.edu/csv")

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_Resp(csv_text, status_code))
    client.aclose = AsyncMock(return_value=None)
    return client


# Standard header schema.
SAMPLE_CSV_STANDARD = """\
Country,ISO3,Year,Index
Germany,DEU,2020,73.5
Germany,DEU,2010,69.2
United States,USA,2020,71.0
Atlantis,XYZ,2020,50.0
Finland,FIN,2020,76.8
"""

# Variant schema (older publication years).
SAMPLE_CSV_VARIANT = """\
country,iso_alpha3_code,year,country_index
Germany,DEU,2020,73.5
United States,USA,2020,71.0
"""

# Out-of-range scores.
SAMPLE_CSV_BAD = """\
Country,ISO3,Year,Index
Germany,DEU,2020,150.0
United States,USA,2020,-5.0
Finland,FIN,2020,76.8
"""


class TestNDGainAdapterParsing:
    @pytest.mark.asyncio
    async def test_standard_schema_yields_records(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_STANDARD), min_year=2000)
        records = [r async for r in adapter.fetch_records()]

        # 5 rows in fixture, XYZ skipped (unknown alpha-3) = 4 records.
        assert len(records) == 4
        by_key = {(r.country_code, r.year): r.value for r in records}
        assert by_key[("DE", 2020)] == 73.5
        assert by_key[("DE", 2010)] == 69.2
        assert by_key[("US", 2020)] == 71.0
        assert by_key[("FI", 2020)] == 76.8

    @pytest.mark.asyncio
    async def test_variant_headers_resolved(self):
        """Older ND-GAIN CSVs use iso_alpha3_code / country_index column names."""
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_VARIANT))
        records = [r async for r in adapter.fetch_records()]
        assert len(records) == 2
        countries = {r.country_code for r in records}
        assert countries == {"DE", "US"}

    @pytest.mark.asyncio
    async def test_out_of_range_scores_rejected(self):
        """Scores < 0 or > 100 are clamped (rejected) — preserves data integrity."""
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_BAD))
        records = [r async for r in adapter.fetch_records()]
        # Only Finland's 76.8 should survive.
        assert len(records) == 1
        assert records[0].country_code == "FI"
        assert records[0].value == 76.8

    @pytest.mark.asyncio
    async def test_unknown_iso_skipped(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_STANDARD))
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert r.country_code != "XY"  # Atlantis filtered out

    @pytest.mark.asyncio
    async def test_min_year_filter(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_STANDARD), min_year=2015)
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert r.year >= 2015
        # The DE 2010 row should be filtered.
        keys = {(r.country_code, r.year) for r in records}
        assert ("DE", 2010) not in keys

    @pytest.mark.asyncio
    async def test_missing_required_headers_no_crash(self):
        """If CSV is missing recognisable headers, no records emitted (and no exception)."""
        from app.domains.content.indicators import NDGainAdapter
        bad_csv = "Region,Population,GDP\nGermany,80M,4T\n"
        adapter = NDGainAdapter(http_client=_make_csv_client(bad_csv))
        records = [r async for r in adapter.fetch_records()]
        assert records == []


class TestNDGainAdapterSync:
    @pytest.mark.asyncio
    async def test_sync_writes_nd_gain_source(self):
        from app.domains.content.indicators import NDGainAdapter
        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append(params or {})

        adapter = NDGainAdapter(http_client=_make_csv_client(SAMPLE_CSV_STANDARD), min_year=2018)
        result = await adapter.sync(_DB())
        assert result.source_name == "nd_gain"
        assert result.upserted_count > 0
        for p in captured:
            assert p["source_name"] == "nd_gain"
            assert p["indicator_id"] == "nd_gain_index"
            assert 0 <= p["value"] <= 100
