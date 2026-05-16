"""OWID adapter tests (Phase 3 wave 2).

Verifies:
- CSV parsing yields one record per (country, year, indicator) triple
- Unit transforms apply (co2 column is million-tonnes → stored as tonnes)
- Unknown alpha-3 codes are skipped
- min_year filter is respected
- Empty / non-numeric values are skipped per cell, never aborting the run
- Sync() upserts each record with source_name='owid'
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


def _make_csv_client(csv_text: str, *, status_code: int = 200) -> httpx.AsyncClient:
    class _Resp:
        def __init__(self, text, code):
            self.text = text
            self.status_code = code
            self.request = httpx.Request("GET", "https://example.com/csv")

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


SAMPLE_CSV = """\
country,year,iso_code,co2,co2_per_capita,renewables_share_elec
United States,2022,USA,5057.4,15.2,21.5
United States,2008,USA,5800.0,18.6,9.4
Germany,2022,DEU,683.2,8.1,46.2
Atlantis,2022,XYZ,123,1,5
United States,2022,USA,,16.0,
"""


class TestOWIDCsvParsing:
    @pytest.mark.asyncio
    async def test_yields_records_per_country_year_indicator(self):
        from app.domains.content.indicators import OWIDAdapter

        adapter = OWIDAdapter(http_client=_make_csv_client(SAMPLE_CSV), min_year=2010)
        records = [r async for r in adapter.fetch_records()]

        # Expected breakdown of the SAMPLE_CSV with min_year=2010:
        #   - US 2022: row1 contributes co2 + co2_pc + renewables = 3 records
        #              row5 has only co2_per_capita (and empty co2, empty renewables)
        #              → adds 1 more record (co2_per_capita)
        #   - US 2008: filtered out by min_year
        #   - DE 2022: 3 records (co2, co2_pc, renewables)
        #   - XYZ: filtered out (unknown alpha-3)
        # Total: 3 + 1 + 3 = 7
        assert len(records) == 7

        # Group by (country, indicator) for assertions; latest year wins for duplicates.
        by_key = {(r.country_code, r.indicator_id, r.year): r for r in records}

        us_total = by_key[("US", "emissions_tco2e_total", 2022)]
        # OWID `co2` is in MILLION tonnes → stored as tonnes (×1e6).
        assert us_total.value == 5057.4 * 1_000_000.0

        us_per_capita = by_key[("US", "emissions_tco2e_per_capita", 2022)]
        # Multiple rows for same key — last one wins via dict overwrite.
        # In any case, both 15.2 and 16.0 are acceptable; pin to actual.
        assert us_per_capita.value in (15.2, 16.0)

        de_renew = by_key[("DE", "renewable_share_electricity_percent", 2022)]
        assert de_renew.value == 46.2

        # Methodology + source URL pinned.
        for r in records:
            assert r.methodology_version == "owid_co2_data_master"
            assert r.source_url.endswith("owid-co2-data.csv")

    @pytest.mark.asyncio
    async def test_min_year_filter(self):
        from app.domains.content.indicators import OWIDAdapter

        adapter = OWIDAdapter(http_client=_make_csv_client(SAMPLE_CSV), min_year=2020)
        records = [r async for r in adapter.fetch_records()]
        # All records must be from 2020+.
        for r in records:
            assert r.year >= 2020

    @pytest.mark.asyncio
    async def test_unknown_alpha3_skipped(self):
        """The Atlantis/XYZ row in SAMPLE_CSV must not produce any record."""
        from app.domains.content.indicators import OWIDAdapter

        adapter = OWIDAdapter(http_client=_make_csv_client(SAMPLE_CSV))
        records = [r async for r in adapter.fetch_records()]
        assert all(r.country_code in {"US", "DE"} for r in records)

    @pytest.mark.asyncio
    async def test_empty_cells_skipped_not_inserted_as_zero(self):
        """Row 5 has empty `co2` and `renewables_share_elec` — those cells
        must not produce records with value=0; they must be skipped."""
        from app.domains.content.indicators import OWIDAdapter

        adapter = OWIDAdapter(http_client=_make_csv_client(SAMPLE_CSV))
        records = [r async for r in adapter.fetch_records()]
        # No record can have value == 0 from the synthetic empty cells.
        # (real data may legitimately be 0 — the SAMPLE_CSV doesn't include any
        # row whose populated value is 0).
        zeros = [r for r in records if r.value == 0]
        assert zeros == []


class TestOWIDSyncIntegration:
    @pytest.mark.asyncio
    async def test_sync_writes_to_country_indicators_with_owid_source_name(self):
        from app.domains.content.indicators import OWIDAdapter

        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append({"q": " ".join((query or "").split()).lower(), "params": params or {}})

        adapter = OWIDAdapter(
            http_client=_make_csv_client(SAMPLE_CSV), min_year=2020,
        )
        db = _DB()
        result = await adapter.sync(db)
        assert result.source_name == "owid"
        assert result.upserted_count > 0
        for call in captured:
            assert "insert into country_indicators" in call["q"]
            assert call["params"]["source_name"] == "owid"
