"""UNFCCC NDC adapter tests (Phase 3 wave 6; rewritten 2026-07-02 for ML-14).

Verifies:
- parse_target still extracts (pct, year) from single NDC strings (pure helper)
- parse_target_year takes the latest in-range year (ranges collapse to the end
  year) and falls back to a "by YYYY" clause in the ghg text
- parse_reduction_pct: net-zero precedence + first parseable percent
- fetch_records groups the indicator-keyed rows (ghg_target / time_target_year)
  by country and emits year + pct records
- ISO3 mapping now uses the FULL map — AFG maps to AF (regression: it was
  dropped by the old 80-entry map, giving the layer ZERO data)
- Pagination follows &page=N until a short page
- Unknown ISO3 / missing ISO / qualitative rows are skipped
- Malformed JSON payloads degrade gracefully (no records)
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


class _Resp:
    def __init__(self, body, code=200):
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


def _make_json_client(payload, *, status_code: int = 200) -> httpx.AsyncClient:
    """Single-page client: returns `payload` for page 1, empty data thereafter."""
    client = MagicMock(spec=httpx.AsyncClient)

    async def _get(url, *args, **kwargs):
        m = re.search(r"[?&]page=(\d+)", url)
        page = int(m.group(1)) if m else 1
        if page == 1:
            return _Resp(payload, status_code)
        return _Resp({"data": [], "meta": {}}, status_code)

    client.get = AsyncMock(side_effect=_get)
    client.aclose = AsyncMock(return_value=None)
    return client


def _make_paged_client(pages: dict) -> httpx.AsyncClient:
    """Client that serves `pages[N]` (a list of rows) per &page=N; empty otherwise."""
    client = MagicMock(spec=httpx.AsyncClient)

    async def _get(url, *args, **kwargs):
        m = re.search(r"[?&]page=(\d+)", url)
        page = int(m.group(1)) if m else 1
        return _Resp({"data": pages.get(page, []), "meta": {}})

    client.get = AsyncMock(side_effect=_get)
    client.aclose = AsyncMock(return_value=None)
    return client


def _row(iso, indicator, value):
    return {"iso_code3": iso, "indicator_id": indicator, "value": value}


# ---------------------------------------------------------------------------
# Pure parsing helpers
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
        assert parse_target("Achieve net-zero by 2050") == (100.0, 2050)

    def test_qualitative_only_returns_nones(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        assert parse_target("Strengthen adaptation measures") == (None, None)

    def test_year_below_2020_rejected(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        _, year = parse_target("Reduce by 20% by 2010")
        assert year is None

    def test_empty_string(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        assert parse_target("") == (None, None)
        assert parse_target(None) == (None, None)  # type: ignore[arg-type]

    def test_pct_over_100_rejected(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target
        pct, _ = parse_target("Reduce by 150% by 2030")
        assert pct is None


class TestParseTargetYear:
    def test_latest_year_wins_over_period_start(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target_year
        # A commitment period collapses to its end/target year, and the most
        # recent NDC horizon wins.
        assert parse_target_year(["2021 to 2030", "2035"]) == 2035

    def test_bare_year(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target_year
        assert parse_target_year(["2030"]) == 2030

    def test_prose_period_range(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target_year
        assert parse_target_year(["1 January 2021- 31 December 2030"]) == 2030

    def test_fallback_to_ghg_by_year(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target_year
        # No clean timing field -> pull the "by YYYY" clause from the ghg text
        # (and NOT a base year like "below 2005 levels").
        assert parse_target_year([], ["40% reduction below 2005 levels by 2030"]) == 2030

    def test_none_when_no_year(self):
        from app.domains.content.indicators.unfccc_ndc import parse_target_year
        assert parse_target_year(["no year here"], ["qualitative pledge"]) is None


class TestParseReductionPct:
    def test_first_percent(self):
        from app.domains.content.indicators.unfccc_ndc import parse_reduction_pct
        assert parse_reduction_pct(["26% to 28% reduction by 2030 vs 2005"]) == 26.0

    def test_net_zero_precedence(self):
        from app.domains.content.indicators.unfccc_ndc import parse_reduction_pct
        assert parse_reduction_pct(["some prose", "net-zero by 2050"]) == 100.0

    def test_none_when_qualitative(self):
        from app.domains.content.indicators.unfccc_ndc import parse_reduction_pct
        assert parse_reduction_pct(["Strengthen forest protection"]) is None


# ---------------------------------------------------------------------------
# fetch_records — indicator-keyed rows grouped per country
# ---------------------------------------------------------------------------

SAMPLE = {
    "data": [
        _row("AFG", "time_target_year", "2030"),
        _row("AFG", "ghg_target", "13.6% reduction in GHG emissions by 2030 compared to BAU"),
        _row("DEU", "time_target_year", "2021 to 2030"),
        _row("DEU", "ghg_target", "at least 55% reduction by 2030 vs 1990"),
        _row("AUS", "time_target_year", "2021 to 2030"),
        _row("AUS", "time_target_year", "2035"),
        _row("AUS", "ghg_target", "26% to 28% reduction by 2030 compared to 2005"),
        _row("FIN", "ghg_target", "Achieve net-zero by 2035"),
        _row("ATL", "ghg_target", "100% by 2030"),   # unknown iso3 -> skip
        _row("BRA", "ghg_target", "Strengthen forest protection"),  # qualitative -> skip
        _row("", "ghg_target", "30% by 2030"),        # missing iso -> skip
    ],
    "meta": {},
}


class TestFetchRecords:
    @pytest.mark.asyncio
    async def test_groups_and_emits_year_and_pct(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        records = [r async for r in adapter.fetch_records()]
        by = {(r.country_code, r.indicator_id): r.value for r in records}

        # AFG regression: the old 80-entry map dropped AFG -> ZERO data. Now AF.
        assert by[("AF", "ndc_target_year")] == 2030.0
        assert by[("AF", "ndc_target_reduction_percent")] == 13.6

        assert by[("DE", "ndc_target_year")] == 2030.0
        assert by[("DE", "ndc_target_reduction_percent")] == 55.0

        # AUS: two timing rows -> latest (2035); pct 26 from the ghg lower bound.
        assert by[("AU", "ndc_target_year")] == 2035.0
        assert by[("AU", "ndc_target_reduction_percent")] == 26.0

        # FIN: no timing field, net-zero pledge -> year via "by 2035", pct 100.
        assert by[("FI", "ndc_target_year")] == 2035.0
        assert by[("FI", "ndc_target_reduction_percent")] == 100.0

    @pytest.mark.asyncio
    async def test_afg_maps_to_af(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        codes = {r.country_code async for r in adapter.fetch_records()}
        assert "AF" in codes  # the exact regression ML-14 fixes

    @pytest.mark.asyncio
    async def test_unknown_iso3_and_missing_iso_skipped(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        codes = {r.country_code async for r in adapter.fetch_records()}
        assert codes <= {"AF", "DE", "AU", "FI"}  # ATL / "" excluded

    @pytest.mark.asyncio
    async def test_qualitative_only_no_records(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        records = [r async for r in adapter.fetch_records()]
        assert all(r.country_code != "BR" for r in records)  # Brazil qualitative

    @pytest.mark.asyncio
    async def test_source_url_and_methodology(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert "/ndcs/country/" in r.source_url
            assert r.methodology_version == "cw_ndc_v1"

    @pytest.mark.asyncio
    async def test_unexpected_payload_shape_no_crash(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(["not a dict"]))
        records = [r async for r in adapter.fetch_records()]
        assert records == []


class TestPagination:
    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        pages = {
            1: [_row("AFG", "time_target_year", "2030"), _row("AFG", "ghg_target", "20% by 2030")],
            2: [_row("BRA", "time_target_year", "2030"), _row("BRA", "ghg_target", "37% by 2030")],
            3: [_row("CHN", "time_target_year", "2030")],  # short page -> stop
        }
        adapter = UNFCCCNdcAdapter(
            http_client=_make_paged_client(pages),
            api_url="https://example.com/api/ndc_content?indicator_ids[]=627369&per_page=2",
        )
        codes = {r.country_code async for r in adapter.fetch_records()}
        # All three pages consumed (AF from p1, BR from p2, CN from p3).
        assert codes == {"AF", "BR", "CN"}
        assert adapter._http_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_max_pages_cap_respected(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        # Every page returns exactly per_page rows -> only the cap stops it.
        full_page = [_row("AFG", "ghg_target", "10% by 2030"), _row("AGO", "ghg_target", "20% by 2030")]
        adapter = UNFCCCNdcAdapter(
            http_client=_make_paged_client({n: full_page for n in range(1, 50)}),
            api_url="https://example.com/api/ndc_content?per_page=2",
            max_pages=3,
        )
        _ = [r async for r in adapter.fetch_records()]
        assert adapter._http_client.get.call_count == 3


class TestSync:
    @pytest.mark.asyncio
    async def test_sync_upserts_with_unfccc_ndc_source(self):
        from app.domains.content.indicators import UNFCCCNdcAdapter
        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append(params or {})

        adapter = UNFCCCNdcAdapter(http_client=_make_json_client(SAMPLE))
        result = await adapter.sync(_DB())
        assert result.source_name == "unfccc_ndc"
        assert result.upserted_count == len(captured) > 0
        for p in captured:
            assert p["source_name"] == "unfccc_ndc"
