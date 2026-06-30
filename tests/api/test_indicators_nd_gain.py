"""ND-GAIN adapter tests (rev. 2026-06-30 — ZIP / wide-format source).

The ND-GAIN download moved from a single flat CSV (now HTTP 403) to a ZIP of
per-metric wide CSVs. These tests verify the reworked adapter:

- Composite index parsed from resources/gain/gain.csv (0-100, wide format)
- Vulnerability + readiness sub-scores parsed (0-1) and emitted as their own
  indicator_ids
- The `trends/` decoy CSVs are NOT picked (member resolution is parent-qualified)
- Out-of-range values clamped per metric scale (index >100, sub-score >1)
- Unknown ISO codes skipped; full ISO map now covers the long tail (AFG etc.)
- Variant ISO header resolved (iso_alpha3_code)
- min_year filter applied
- Missing headers / bad zip degrade gracefully (no crash, no records)
- 4xx fails fast
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


# --- wide-format fixtures (ISO3, Name, <year columns...>) -------------------

GAIN_CSV = (
    "ISO3,Name,2010,2020\n"
    "DEU,Germany,69.2,73.5\n"
    "USA,United States,70.0,71.0\n"
    "FIN,Finland,75.0,76.8\n"
    "AFG,Afghanistan,34.0,35.0\n"   # long-tail country — only covered with full ISO map
    "XYZ,Atlantis,40.0,50.0\n"       # unknown ISO — skipped
)

VULN_CSV = (
    "ISO3,Name,2010,2020\n"
    "DEU,Germany,0.30,0.28\n"
    "USA,United States,0.33,0.31\n"
    "AFG,Afghanistan,0.61,0.60\n"
)

READY_CSV = (
    "ISO3,Name,2010,2020\n"
    "DEU,Germany,0.60,0.62\n"
    "USA,United States,0.58,0.59\n"
    "AFG,Afghanistan,0.30,0.31\n"
)

# Decoy trends CSVs with obviously different values — must NOT be picked.
TRENDS_GAIN_CSV = "ISO3,Name,2010,2020\nDEU,Germany,1.1,2.2\n"


def _make_zip_bytes(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, text in members.items():
            zf.writestr(path, text)
    return buf.getvalue()


def _standard_zip(**overrides) -> bytes:
    members = {
        "resources/gain/gain.csv": GAIN_CSV,
        "resources/trends/gain.csv": TRENDS_GAIN_CSV,
        "resources/vulnerability/vulnerability.csv": VULN_CSV,
        "resources/readiness/readiness.csv": READY_CSV,
    }
    members.update(overrides)
    return _make_zip_bytes(members)


def _make_zip_client(zip_bytes: bytes, *, status_code: int = 200) -> httpx.AsyncClient:
    class _Resp:
        def __init__(self, content, code):
            self.content = content
            self.status_code = code
            self.request = httpx.Request("GET", "https://gain.nd.edu/zip")

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_Resp(zip_bytes, status_code))
    client.aclose = AsyncMock(return_value=None)
    return client


class TestNDGainAdapterParsing:
    @pytest.mark.asyncio
    async def test_emits_all_three_indicators(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2000)
        records = [r async for r in adapter.fetch_records()]

        ids = {r.indicator_id for r in records}
        assert ids == {"nd_gain_index", "nd_gain_vulnerability", "nd_gain_readiness"}

    @pytest.mark.asyncio
    async def test_composite_index_values_and_scale(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2000)
        records = [r async for r in adapter.fetch_records()]

        idx = {(r.country_code, r.year): r.value for r in records if r.indicator_id == "nd_gain_index"}
        assert idx[("DE", 2020)] == 73.5
        assert idx[("DE", 2010)] == 69.2
        assert idx[("US", 2020)] == 71.0
        assert idx[("FI", 2020)] == 76.8
        # Decoy trends values must never appear.
        assert ("DE", 2020) in idx and idx[("DE", 2020)] != 2.2

    @pytest.mark.asyncio
    async def test_full_iso_map_covers_long_tail(self):
        """Afghanistan (AFG) is absent from the shared climate_trace map but
        present in the ND-GAIN full map — it must now be covered."""
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2000)
        records = [r async for r in adapter.fetch_records()]
        countries = {r.country_code for r in records if r.indicator_id == "nd_gain_index"}
        assert "AF" in countries

    @pytest.mark.asyncio
    async def test_subscores_native_0_1_scale(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2000)
        records = [r async for r in adapter.fetch_records()]

        vuln = {(r.country_code, r.year): r.value for r in records if r.indicator_id == "nd_gain_vulnerability"}
        ready = {(r.country_code, r.year): r.value for r in records if r.indicator_id == "nd_gain_readiness"}
        assert vuln[("DE", 2020)] == 0.28
        assert ready[("DE", 2020)] == 0.62
        # All sub-scores are within the published 0-1 range.
        for v in list(vuln.values()) + list(ready.values()):
            assert 0.0 <= v <= 1.0

    @pytest.mark.asyncio
    async def test_unknown_iso_skipped(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()))
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert r.country_code != "XY"  # Atlantis filtered out

    @pytest.mark.asyncio
    async def test_index_out_of_range_rejected(self):
        from app.domains.content.indicators import NDGainAdapter
        bad_gain = (
            "ISO3,Name,2020\n"
            "DEU,Germany,150.0\n"   # > 100 rejected
            "USA,United States,-5.0\n"  # < 0 rejected
            "FIN,Finland,76.8\n"    # valid
        )
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip(**{"resources/gain/gain.csv": bad_gain})))
        records = [r async for r in adapter.fetch_records() if r.indicator_id == "nd_gain_index"]
        assert len(records) == 1
        assert records[0].country_code == "FI"
        assert records[0].value == 76.8

    @pytest.mark.asyncio
    async def test_subscore_out_of_range_rejected(self):
        from app.domains.content.indicators import NDGainAdapter
        bad_vuln = (
            "ISO3,Name,2020\n"
            "DEU,Germany,1.5\n"     # > 1 rejected for a sub-score
            "USA,United States,0.4\n"  # valid
        )
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip(**{"resources/vulnerability/vulnerability.csv": bad_vuln})))
        records = [r async for r in adapter.fetch_records() if r.indicator_id == "nd_gain_vulnerability"]
        keys = {r.country_code for r in records}
        assert keys == {"US"}
        assert records[0].value == 0.4

    @pytest.mark.asyncio
    async def test_variant_iso_header_resolved(self):
        from app.domains.content.indicators import NDGainAdapter
        variant_gain = (
            "iso_alpha3_code,country,2020\n"
            "DEU,Germany,73.5\n"
            "USA,United States,71.0\n"
        )
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip(**{"resources/gain/gain.csv": variant_gain})))
        records = [r async for r in adapter.fetch_records() if r.indicator_id == "nd_gain_index"]
        assert {r.country_code for r in records} == {"DE", "US"}

    @pytest.mark.asyncio
    async def test_min_year_filter(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2015)
        records = [r async for r in adapter.fetch_records()]
        for r in records:
            assert r.year >= 2015
        keys = {(r.country_code, r.year) for r in records if r.indicator_id == "nd_gain_index"}
        assert ("DE", 2010) not in keys

    @pytest.mark.asyncio
    async def test_missing_headers_no_crash(self):
        from app.domains.content.indicators import NDGainAdapter
        bad = "Region,Population\nGermany,80M\n"
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip(**{"resources/gain/gain.csv": bad})))
        records = [r async for r in adapter.fetch_records() if r.indicator_id == "nd_gain_index"]
        assert records == []

    @pytest.mark.asyncio
    async def test_missing_member_skipped_not_fatal(self):
        """If a metric CSV is absent, its indicator is simply not emitted —
        the others still flow."""
        from app.domains.content.indicators import NDGainAdapter
        members = {
            "resources/gain/gain.csv": GAIN_CSV,
            # vulnerability + readiness members omitted
        }
        adapter = NDGainAdapter(http_client=_make_zip_client(_make_zip_bytes(members)))
        records = [r async for r in adapter.fetch_records()]
        assert {r.indicator_id for r in records} == {"nd_gain_index"}

    @pytest.mark.asyncio
    async def test_bad_zip_no_crash(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(b"not a zip file"))
        records = [r async for r in adapter.fetch_records()]
        assert records == []

    @pytest.mark.asyncio
    async def test_4xx_fails_fast(self):
        from app.domains.content.indicators import NDGainAdapter
        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip(), status_code=403))
        with pytest.raises(httpx.HTTPStatusError):
            [r async for r in adapter.fetch_records()]


class TestNDGainAdapterSync:
    @pytest.mark.asyncio
    async def test_sync_writes_nd_gain_sources(self):
        from app.domains.content.indicators import NDGainAdapter
        captured = []

        class _DB:
            def execute_update(self, query, params=None):
                captured.append(params or {})

        adapter = NDGainAdapter(http_client=_make_zip_client(_standard_zip()), min_year=2018)
        result = await adapter.sync(_DB())
        assert result.source_name == "nd_gain"
        assert result.upserted_count > 0
        seen_ids = {p["indicator_id"] for p in captured}
        assert seen_ids == {"nd_gain_index", "nd_gain_vulnerability", "nd_gain_readiness"}
        for p in captured:
            assert p["source_name"] == "nd_gain"
            assert p["value"] is not None
