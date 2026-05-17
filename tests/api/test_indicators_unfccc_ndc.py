"""UNFCCC NDC adapter tests (Phase 3 wave 6).

Verifies:
- parse_target extracts (pct, year) from real-world NDC commitment text
- Net-zero pledges map to 100% reduction
- Qualitative pledges yield (None, None) and are skipped
- fetch_records yields one record per (country, indicator) when both
  pct and year are present
- Country with alpha-3 not in ALPHA3_TO_ALPHA2 is skipped
- Malformed JSON payloads degrade gracefully (no records)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


def _make_json_client(payload, *, status_code: int = 200) -> httpx.AsyncClient:
    class _Resp:
        def __init__(self, body, code):
            self._body = body
            self.status_code = code
            self.request = httpx.Request("GET", "https://example.com/ndc")

        def json(self):
            return self._body

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_Resp(payload, status_code))
    client.aclose = AsyncMock(return_value=None)
    return client


# ---------------------------------------------------------------------------
# parse_target — pure string parsing
# ---------------------------------------------------------------------------

class TestParseTarget:
    def test_simple_pct_by_year(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        assert parse_target("Reduce emissions by 30% by 2030") == (30.0, 2030)

    def test_pct_below_base_year(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        pct, year = parse_target("55% below 1990 levels by 2030")
        assert pct == 55.0
        assert year == 2030

    def test_net_zero_pledge_is_100_pct(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        pct, year = parse_target("Achieve net-zero by 2050")
        assert pct == 100.0
        assert year == 2050

    def test_net_zero_alt_spelling(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        assert parse_target("net zero 2045") == (100.0, 2045)

    def test_qualitative_only_returns_nones(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        pct, year = parse_target("Strengthen adaptation measures")
        assert pct is None
        assert year is None

    def test_year_below_2020_rejected(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        pct, year = parse_target("Reduce by 20% by 2010")
        assert year is None

    def test_empty_string(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        assert parse_target("") == (None, None)
        assert parse_target(None) == (None, None)  # type: ignore[arg-type]

    def test_pct_clipped_to_100(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        # 150% reduction is nonsense — must not be returned as a valid pct.
        pct, year = parse_target("Reduce by 150% by 2030")
        assert pct is None  # rejected as > 100


# ---------------------------------------------------------------------------
# Adapter — fetch_records integration
# ---------------------------------------------------------------------------

SAMPLE_PAYLOAD = {
    "data": [
        {
            "iso_code3": "DEU",
            "value": "55% below 1990 levels by 2030; net-zero by 2045",
        },
        {
            "iso_code3": "USA",
            "value": "50% reduction by 2030",
        },
        {
            "iso_code3": "FIN",
            "value": "Achieve net-zero by 2035",
        },
        {
            "iso_code3": "ATL",   # Atlantis — not in alpha3 map
            "value": "100% by 2030",
        },
        {
            "iso_code3": "BRA",
            "value": "Strengthen forest protection",  # qualitative
        },
        {
            "iso_code3": "",      # missing iso → skip
            "value": "30% by 2030",
        },
    ],
    "meta": {"total": 6},
}


class TestUNFCCCNdcAdapterFetch:
    @pytest.mark.asyncio
    async def test_yields_year_and_pct_records_per_country(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE_PAYLOAD))
        records = [r async for r in adapter.fetch_records()]

        # DE: net-zero pledge → 100% + year 2045 (net-zero takes precedence)
        # US: 50% by 2030 → 2 records (year + pct)
        # FI: net-zero 2035 → 2 records
        # Total: 6 records
        assert len(records) == 6

        # Group by (country, indicator_id) to verify shape.
        by_key = {(r.country_code, r.indicator_id): r for r in records}

        assert by_key[("US", "ndc_target_year")].value == 2030.0
        assert by_key[("US", "ndc_target_reduction_percent")].value == 50.0
        assert by_key[("FI", "ndc_target_year")].value == 2035.0
        assert by_key[("FI", "ndc_target_reduction_percent")].value == 100.0
        # DE first match is net-zero (Germany NDC pledges net-zero by 2045)
        assert by_key[("DE", "ndc_target_year")].value == 2045.0
        assert by_key[("DE", "ndc_target_reduction_percent")].value == 100.0

    @pytest.mark.asyncio
    async def test_unknown_iso3_skipped(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE_PAYLOAD))
        records = [r async for r in adapter.fetch_records()]
        # The "ATL" row in the fixture must not appear.
        for r in records:
            assert r.country_code != "AT" or r.raw_record.get("iso_code3") != "ATL"
        # And no record should reference a known-bad alpha2.
        codes = {r.country_code for r in records}
        assert codes <= {"DE", "US", "FI"}

    @pytest.mark.asyncio
    async def test_qualitative_only_no_records(self):
        """Brazil's qualitative pledge in the fixture yields no records."""
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE_PAYLOAD))
        records = [r async for r in adapter.fetch_records()]
        assert all(r.country_code != "BR" for r in records)

    @pytest.mark.asyncio
    async def test_unexpected_payload_shape_no_crash(self):
        """If the API returns a list instead of {'data': [...]} we don't crash."""
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(["not a dict"]))
        records = [r async for r in adapter.fetch_records()]
        assert records == []

    @pytest.mark.asyncio
    async def test_source_url_per_country(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE_PAYLOAD))
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert "/ndcs/country/" in r.source_url
            assert r.methodology_version == "cw_ndc_v1"


class TestUNFCCCNdcAdapterSync:
    @pytest.mark.asyncio
    async def test_sync_upserts_with_unfccc_ndc_source(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append(params or {})

        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE_PAYLOAD))
        result = await adapter.sync(_DB())
        assert result.source_name == "unfccc_ndc"
        assert result.upserted_count == len(captured) > 0
        for p in captured:
            assert p["source_name"] == "unfccc_ndc"
