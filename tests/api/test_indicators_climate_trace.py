"""Climate TRACE adapter tests (Phase 3 wave 1).

Verifies:
- fetch_records aggregates per (country, year) and emits one total row
  plus one row per tracked sector.
- The HTTP layer is properly mocked through an injected AsyncClient.
- Unknown alpha-3 codes are skipped, not crashed on.
- Schema-variant fields (co2e_100yr vs co2e_100yr_tonnes) both work.
- The base class's sync() runs upsert with the right SQL shape.
- 4xx errors abort; 5xx errors are retried up to the configured limit.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(json_payload: Any, *, status_code: int = 200) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient stand-in that returns one canned response."""

    class _Resp:
        def __init__(self, payload, code):
            self._payload = payload
            self.status_code = code
            self.request = httpx.Request("GET", "https://api.climatetrace.org/v6/country/emissions")

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

        def json(self):
            return self._payload

    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_Resp(json_payload, status_code))
    client.aclose = AsyncMock(return_value=None)
    return client


class _CapturingDB:
    """Captures execute_update calls for assertion."""
    def __init__(self):
        self.updates: List[Dict[str, Any]] = []

    def execute_update(self, query, params=None):
        self.updates.append({"query": " ".join((query or "").split()), "params": params or {}})


# ---------------------------------------------------------------------------
# fetch_records — aggregation + alpha-3 → alpha-2 mapping
# ---------------------------------------------------------------------------

class TestFetchRecordsAggregation:
    @pytest.mark.asyncio
    async def test_emits_total_plus_sector_rows(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            # USA 2022 power emissions
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 1_500_000_000},
            # USA 2022 transportation emissions
            {"country": "USA", "year": 2022, "sector": "transportation", "co2e_100yr_tonnes": 1_800_000_000},
            # USA 2022 agriculture (not tracked → contributes to total only)
            {"country": "USA", "year": 2022, "sector": "agriculture", "co2e_100yr_tonnes": 300_000_000},
            # DEU 2022 power
            {"country": "DEU", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 250_000_000},
        ]

        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        records = [r async for r in adapter.fetch_records()]

        # Expect: USA total + USA power + USA transportation + DEU total + DEU power = 5
        assert len(records) == 5

        # Group records for assertions.
        by_key = {
            (r.country_code, r.indicator_id, r.year): r for r in records
        }

        usa_total = by_key[("US", "emissions_tco2e_total", 2022)]
        assert usa_total.value == 3_600_000_000  # 1.5B + 1.8B + 0.3B

        usa_power = by_key[("US", "emissions_tco2_power", 2022)]
        assert usa_power.value == 1_500_000_000

        usa_trans = by_key[("US", "emissions_tco2_transportation", 2022)]
        assert usa_trans.value == 1_800_000_000

        deu_total = by_key[("DE", "emissions_tco2e_total", 2022)]
        assert deu_total.value == 250_000_000

        # Methodology version pinned on every record.
        for r in records:
            assert r.methodology_version == "climate_trace_v6"
            assert r.source_url == "https://api.climatetrace.org/v6/country/emissions"

    @pytest.mark.asyncio
    async def test_unknown_alpha3_is_skipped(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            {"country": "XYZ", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 1},
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 100},
        ]
        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        records = [r async for r in adapter.fetch_records()]

        # Only the USA rows survive.
        assert all(r.country_code == "US" for r in records)
        assert len(records) == 2  # total + power

    @pytest.mark.asyncio
    async def test_legacy_co2e_field_name_is_accepted(self):
        """Older API versions used `co2e_100yr` (no _tonnes suffix). Both should parse."""
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            # Old field name
            {"country": "FRA", "year": 2021, "sector": "power", "co2e_100yr": 50_000_000},
        ]
        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        records = [r async for r in adapter.fetch_records()]
        assert len(records) == 2
        fra_total = next(r for r in records if r.indicator_id == "emissions_tco2e_total")
        assert fra_total.value == 50_000_000

    @pytest.mark.asyncio
    async def test_invalid_year_or_missing_value_is_skipped(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            {"country": "USA", "year": "not-a-year", "sector": "power", "co2e_100yr_tonnes": 1},
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": None},
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 500},
        ]
        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        records = [r async for r in adapter.fetch_records()]
        # Only the third record contributes.
        assert len(records) == 2  # USA total + USA power
        for r in records:
            assert r.value == 500

    @pytest.mark.asyncio
    async def test_non_list_payload_raises(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        adapter = ClimateTRACEAdapter(http_client=_make_mock_client({"error": "oops"}))
        with pytest.raises(RuntimeError, match="Unexpected Climate TRACE payload shape"):
            _ = [r async for r in adapter.fetch_records()]


# ---------------------------------------------------------------------------
# sync() integration — upsert SQL shape + SyncResult
# ---------------------------------------------------------------------------

class TestSyncIntegration:
    @pytest.mark.asyncio
    async def test_sync_upserts_all_records_and_returns_counts(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 100},
            {"country": "USA", "year": 2022, "sector": "transportation", "co2e_100yr_tonnes": 50},
        ]
        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        db = _CapturingDB()

        result = await adapter.sync(db)

        # 3 rows: total + power + transportation.
        assert result.source_name == "climate_trace"
        assert result.fetched_count == 3
        assert result.upserted_count == 3
        assert result.skipped_count == 0
        assert result.errors == []
        assert result.duration_seconds is not None and result.duration_seconds >= 0

        # Every UPDATE call hits country_indicators with ON CONFLICT logic.
        for call in db.updates:
            assert "insert into country_indicators" in call["query"].lower()
            assert "on conflict" in call["query"].lower()
            assert call["params"]["source_name"] == "climate_trace"
            # raw_record is JSON-serialised before the SQL bind.
            assert isinstance(call["params"]["raw_record"], str)
            json.loads(call["params"]["raw_record"])  # parses cleanly

    @pytest.mark.asyncio
    async def test_sync_isolates_individual_upsert_failures(self):
        """An upsert failing on one record must not abort the whole sync."""
        from app.domains.content.indicators import ClimateTRACEAdapter

        payload = [
            {"country": "USA", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 100},
            {"country": "DEU", "year": 2022, "sector": "power", "co2e_100yr_tonnes": 50},
        ]

        class _PickyDB:
            def __init__(self):
                self.updates = []
                self.fail_next = False

            def execute_update(self, query, params=None):
                self.updates.append(params)
                # Fail on every DEU row.
                if params and params.get("country_code") == "DE":
                    raise RuntimeError("DE upsert constraint violation (test)")

        db = _PickyDB()
        adapter = ClimateTRACEAdapter(http_client=_make_mock_client(payload))
        result = await adapter.sync(db)

        # 4 records fetched: USA total + USA power + DEU total + DEU power.
        assert result.fetched_count == 4
        # Two USA records upserted, two DEU records failed.
        assert result.upserted_count == 2
        assert result.skipped_count == 2
        assert len(result.errors) == 2
        assert all("DE" in err or "DEU" in err for err in result.errors)


# ---------------------------------------------------------------------------
# HTTP retry behaviour
# ---------------------------------------------------------------------------

class TestHttpRetries:
    @pytest.mark.asyncio
    async def test_4xx_aborts_without_retry(self):
        from app.domains.content.indicators import ClimateTRACEAdapter

        adapter = ClimateTRACEAdapter(http_client=_make_mock_client([], status_code=404))
        with pytest.raises(httpx.HTTPStatusError):
            _ = [r async for r in adapter.fetch_records()]
        # 1 call only — 4xx aborts.
        assert adapter._http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_5xx_retries_up_to_limit(self, monkeypatch):
        from app.domains.content.indicators import ClimateTRACEAdapter

        # Make asyncio.sleep instant so the test doesn't take seconds.
        import asyncio as _aio
        async def _no_sleep(_):
            return None
        monkeypatch.setattr(_aio, "sleep", _no_sleep)

        adapter = ClimateTRACEAdapter(
            http_client=_make_mock_client([], status_code=503),
            max_retries=3,
        )
        with pytest.raises(httpx.HTTPStatusError):
            _ = [r async for r in adapter.fetch_records()]
        # 3 attempts.
        assert adapter._http_client.get.call_count == 3
