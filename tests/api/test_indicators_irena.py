"""IRENA renewable-capacity adapter tests (Phase 3 wave 6).

Verifies:
- Multi-CSV aggregation (solar + wind + hydro → single MW value per country-year)
- Per-tech raw_record breakdown preserved
- Per-source CSV failure doesn't abort the run
- Unknown ISO codes skipped
- Missing capacity column degrades silently
- min_year filter applied
"""

from __future__ import annotations

from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


def _make_multi_csv_client(csvs_by_url: dict) -> httpx.AsyncClient:
    """Returns a fake AsyncClient that maps url → csv text (or raises)."""
    class _Resp:
        def __init__(self, text, code, url):
            self.text = text
            self.status_code = code
            self.request = httpx.Request("GET", url)

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    async def fake_get(url, **kwargs):
        entry = csvs_by_url.get(url)
        if entry is None:
            raise httpx.RequestError(f"No fixture for {url}", request=httpx.Request("GET", url))
        if isinstance(entry, Exception):
            raise entry
        text, code = entry
        return _Resp(text, code, url)

    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=fake_get)
    client.aclose = AsyncMock(return_value=None)
    return client


SOLAR_CSV = """\
Entity,Code,Year,Solar Capacity
Germany,DEU,2022,67000
United States,USA,2022,142000
Atlantis,XYZ,2022,99
Germany,DEU,2005,2000
"""

WIND_CSV = """\
Entity,Code,Year,Wind Capacity
Germany,DEU,2022,64000
United States,USA,2022,141000
"""

HYDRO_CSV = """\
Entity,Code,Year,Hydropower Capacity
Germany,DEU,2022,12000
United States,USA,2022,103000
"""


URLS: List[Tuple[str, str]] = [
    ("solar",  "https://example.com/solar.csv"),
    ("wind",   "https://example.com/wind.csv"),
    ("hydro",  "https://example.com/hydro.csv"),
]


class TestIRENAAdapterAggregation:
    @pytest.mark.asyncio
    async def test_sums_capacity_across_3_sources(self):
        from app.domains.content.indicators import IRENAAdapter
        client = _make_multi_csv_client({
            URLS[0][1]: (SOLAR_CSV, 200),
            URLS[1][1]: (WIND_CSV, 200),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        adapter = IRENAAdapter(
            http_client=client,
            capacity_csv_urls=URLS,
            min_year=2020,
        )
        records = [r async for r in adapter.fetch_records()]

        by_key = {(r.country_code, r.year): r for r in records}

        # DE 2022: 67000 + 64000 + 12000 = 143000
        assert by_key[("DE", 2022)].value == 143000.0
        # US 2022: 142000 + 141000 + 103000 = 386000
        assert by_key[("US", 2022)].value == 386000.0

        # raw_record carries per-tech breakdown.
        de = by_key[("DE", 2022)]
        assert de.raw_record["by_technology"] == {
            "solar": 67000.0, "wind": 64000.0, "hydro": 12000.0,
        }
        assert set(de.raw_record["covered_techs"]) == {"solar", "wind", "hydro"}

    @pytest.mark.asyncio
    async def test_partial_coverage_records_only_available_techs(self):
        """If wind CSV fails, DE still records solar + hydro only."""
        from app.domains.content.indicators import IRENAAdapter
        client = _make_multi_csv_client({
            URLS[0][1]: (SOLAR_CSV, 200),
            URLS[1][1]: httpx.RequestError("wind CSV unreachable", request=httpx.Request("GET", URLS[1][1])),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        adapter = IRENAAdapter(
            http_client=client, capacity_csv_urls=URLS, min_year=2020,
        )
        records = [r async for r in adapter.fetch_records()]
        de = next(r for r in records if r.country_code == "DE" and r.year == 2022)
        assert de.value == 67000.0 + 12000.0  # only solar + hydro
        assert "wind" not in de.raw_record["covered_techs"]

    @pytest.mark.asyncio
    async def test_unknown_alpha3_skipped(self):
        from app.domains.content.indicators import IRENAAdapter
        client = _make_multi_csv_client({
            URLS[0][1]: (SOLAR_CSV, 200),
            URLS[1][1]: (WIND_CSV, 200),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        adapter = IRENAAdapter(
            http_client=client, capacity_csv_urls=URLS, min_year=2020,
        )
        records = [r async for r in adapter.fetch_records()]
        countries = {r.country_code for r in records}
        # Atlantis (XYZ) must not appear.
        assert countries <= {"DE", "US"}

    @pytest.mark.asyncio
    async def test_min_year_filter(self):
        from app.domains.content.indicators import IRENAAdapter
        client = _make_multi_csv_client({
            URLS[0][1]: (SOLAR_CSV, 200),
            URLS[1][1]: (WIND_CSV, 200),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        # min_year=2020 excludes the DE 2005 solar row.
        adapter = IRENAAdapter(
            http_client=client, capacity_csv_urls=URLS, min_year=2020,
        )
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert r.year >= 2020

    @pytest.mark.asyncio
    async def test_missing_capacity_column_skips_csv(self):
        """A CSV without a recognisable capacity column degrades gracefully."""
        from app.domains.content.indicators import IRENAAdapter
        bad_csv = "Entity,Code,Year\nGermany,DEU,2022\n"
        client = _make_multi_csv_client({
            URLS[0][1]: (bad_csv, 200),
            URLS[1][1]: (WIND_CSV, 200),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        adapter = IRENAAdapter(
            http_client=client, capacity_csv_urls=URLS, min_year=2020,
        )
        records = [r async for r in adapter.fetch_records()]
        # DE still has wind + hydro records.
        de = next((r for r in records if r.country_code == "DE"), None)
        assert de is not None
        assert "solar" not in de.raw_record["covered_techs"]


class TestIRENAAdapterSync:
    @pytest.mark.asyncio
    async def test_sync_writes_irena_source(self):
        from app.domains.content.indicators import IRENAAdapter
        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append(params or {})

        client = _make_multi_csv_client({
            URLS[0][1]: (SOLAR_CSV, 200),
            URLS[1][1]: (WIND_CSV, 200),
            URLS[2][1]: (HYDRO_CSV, 200),
        })
        adapter = IRENAAdapter(
            http_client=client, capacity_csv_urls=URLS, min_year=2020,
        )
        result = await adapter.sync(_DB())
        assert result.source_name == "irena"
        assert result.upserted_count >= 2
        for p in captured:
            assert p["source_name"] == "irena"
            assert p["indicator_id"] == "renewable_capacity_mw"
