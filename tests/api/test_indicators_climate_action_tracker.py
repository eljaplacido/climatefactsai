"""ClimateActionTrackerAdapter tests (Phase 3 wave 4).

Pins:
- rating_to_score covers all five CAT bands + tolerates encoding/spacing variants
- extract_rating_from_html finds the rating via class selectors and via
  structural fallback
- fetch_records yields one record per country with the right score + provenance
- per-country fetch failures skip that one country without aborting the run
- sync() writes country_indicators rows with source_name='cat'
- HTTP retry behaviour matches the other adapters (4xx aborts, 5xx retries)
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_html_client(
    *,
    html_by_url: Dict[str, str] = None,
    status_by_url: Dict[str, int] = None,
    default_html: str = "",
    default_status: int = 200,
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient stand-in that returns canned HTML per URL."""
    html_by_url = html_by_url or {}
    status_by_url = status_by_url or {}

    class _Resp:
        def __init__(self, text: str, status_code: int):
            self.text = text
            self.status_code = status_code
            self.request = httpx.Request("GET", "https://example.com")

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

    client = MagicMock(spec=httpx.AsyncClient)

    async def _get(url, *args, **kwargs):
        text = html_by_url.get(url, default_html)
        sc = status_by_url.get(url, default_status)
        return _Resp(text, sc)

    client.get = AsyncMock(side_effect=_get)
    client.aclose = AsyncMock(return_value=None)
    return client


class _CapturingDB:
    def __init__(self):
        self.updates: List[Dict[str, Any]] = []

    def execute_update(self, query, params=None):
        self.updates.append({"query": " ".join((query or "").split()), "params": params or {}})


# ---------------------------------------------------------------------------
# rating_to_score
# ---------------------------------------------------------------------------

class TestRatingToScore:
    @pytest.mark.parametrize("rating,expected", [
        ("Critically insufficient", 10.0),
        ("Highly insufficient",     30.0),
        ("Insufficient",            50.0),
        ("Almost sufficient",       70.0),
        ("1.5°C compatible",        90.0),
    ])
    def test_canonical_bands(self, rating, expected):
        from app.domains.content.indicators.climate_action_tracker import rating_to_score
        assert rating_to_score(rating) == expected

    @pytest.mark.parametrize("rating,expected", [
        ("1.5C compatible",                 90.0),
        ("1.5 C compatible",                90.0),
        ("1.5°C paris agreement compatible", 90.0),
    ])
    def test_encoding_and_spacing_variants(self, rating, expected):
        from app.domains.content.indicators.climate_action_tracker import rating_to_score
        assert rating_to_score(rating) == expected

    def test_substring_match(self):
        """CAT sometimes embellishes the label."""
        from app.domains.content.indicators.climate_action_tracker import rating_to_score
        assert rating_to_score("Insufficient (Fair share)") == 50.0

    def test_unknown_returns_none(self):
        from app.domains.content.indicators.climate_action_tracker import rating_to_score
        assert rating_to_score("mostly fine") is None
        assert rating_to_score("") is None
        assert rating_to_score(None) is None


# ---------------------------------------------------------------------------
# extract_rating_from_html
# ---------------------------------------------------------------------------

class TestExtractRatingFromHtml:
    def test_finds_rating_via_class_selector(self):
        from app.domains.content.indicators.climate_action_tracker import extract_rating_from_html
        html = """
        <html><body>
            <div class="rating-headline rating-headline--insufficient">Insufficient</div>
        </body></html>
        """
        assert extract_rating_from_html(html) == "Insufficient"

    def test_finds_rating_via_overall_rating_class(self):
        from app.domains.content.indicators.climate_action_tracker import extract_rating_from_html
        html = """
        <html><body>
            <h2>Country page</h2>
            <span class="overall-rating">Almost sufficient</span>
        </body></html>
        """
        assert extract_rating_from_html(html) == "Almost sufficient"

    def test_structural_fallback_via_body_scan(self):
        """Even when the CSS hints all miss, scanning the body text for a
        known band still surfaces it."""
        from app.domains.content.indicators.climate_action_tracker import extract_rating_from_html
        html = """
        <html><body>
            <p>The country's policy is rated as Critically insufficient.</p>
        </body></html>
        """
        # Lowercased match.
        result = extract_rating_from_html(html)
        assert result is not None
        from app.domains.content.indicators.climate_action_tracker import rating_to_score
        assert rating_to_score(result) == 10.0

    def test_returns_none_when_no_band_present(self):
        from app.domains.content.indicators.climate_action_tracker import extract_rating_from_html
        html = "<html><body>No rating here</body></html>"
        assert extract_rating_from_html(html) is None

    def test_handles_empty_html(self):
        from app.domains.content.indicators.climate_action_tracker import extract_rating_from_html
        assert extract_rating_from_html("") is None


# ---------------------------------------------------------------------------
# fetch_records — happy path + skipping
# ---------------------------------------------------------------------------

class TestFetchRecordsHappyPath:
    @pytest.mark.asyncio
    async def test_yields_one_record_per_country_with_provenance(self):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        html = {
            "https://climateactiontracker.org/countries/germany/":
                '<div class="rating-headline">Almost sufficient</div>',
            "https://climateactiontracker.org/countries/the-usa/":
                '<div class="rating-headline">Insufficient</div>',
        }
        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(html_by_url=html),
            countries={"DE": "germany", "US": "the-usa"},
            inter_country_delay_seconds=0.0,
        )

        records = [r async for r in adapter.fetch_records()]
        assert len(records) == 2

        by_country = {r.country_code: r for r in records}
        assert by_country["DE"].value == 70.0
        assert by_country["DE"].indicator_id == "cat_overall_rating"
        assert by_country["DE"].methodology_version == "cat_2026"
        assert by_country["DE"].source_url.endswith("/germany/")
        # Provenance keeps the raw rating text + slug.
        assert by_country["DE"].raw_record["raw_rating"] == "Almost sufficient"
        assert by_country["DE"].raw_record["slug"] == "germany"

        assert by_country["US"].value == 50.0


class TestFetchRecordsSkipping:
    @pytest.mark.asyncio
    async def test_per_country_404_skipped_without_abort(self):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        html = {
            "https://climateactiontracker.org/countries/germany/":
                '<div class="rating-headline">Almost sufficient</div>',
        }
        status = {
            "https://climateactiontracker.org/countries/the-usa/": 404,
        }
        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(html_by_url=html, status_by_url=status),
            countries={"DE": "germany", "US": "the-usa"},
            inter_country_delay_seconds=0.0,
        )

        records = [r async for r in adapter.fetch_records()]
        # US 404'd, only DE survives.
        assert len(records) == 1
        assert records[0].country_code == "DE"

    @pytest.mark.asyncio
    async def test_page_without_rating_skipped(self):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(
                default_html="<html><body>No rating data here</body></html>",
            ),
            countries={"DE": "germany"},
            inter_country_delay_seconds=0.0,
        )

        records = [r async for r in adapter.fetch_records()]
        assert records == []


# ---------------------------------------------------------------------------
# sync() integration
# ---------------------------------------------------------------------------

class TestSyncIntegration:
    @pytest.mark.asyncio
    async def test_sync_writes_rows_with_cat_source_name(self):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        html = {
            "https://climateactiontracker.org/countries/germany/":
                '<div class="rating-headline">1.5°C compatible</div>',
            "https://climateactiontracker.org/countries/the-usa/":
                '<div class="rating-headline">Insufficient</div>',
        }
        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(html_by_url=html),
            countries={"DE": "germany", "US": "the-usa"},
            inter_country_delay_seconds=0.0,
        )
        db = _CapturingDB()
        result = await adapter.sync(db)

        assert result.source_name == "cat"
        assert result.fetched_count == 2
        assert result.upserted_count == 2
        for call in db.updates:
            assert "insert into country_indicators" in call["query"].lower()
            assert call["params"]["source_name"] == "cat"
            assert call["params"]["indicator_id"] == "cat_overall_rating"


# ---------------------------------------------------------------------------
# HTTP retry behaviour
# ---------------------------------------------------------------------------

class TestHttpRetries:
    @pytest.mark.asyncio
    async def test_4xx_other_than_404_aborts_country(self):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        # 403 → should abort that country (not retry); 4xx aborts.
        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(default_status=403),
            countries={"DE": "germany"},
            inter_country_delay_seconds=0.0,
        )
        records = [r async for r in adapter.fetch_records()]
        assert records == []
        # Single attempt — 4xx aborts retry.
        assert adapter._http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_5xx_retries_up_to_limit(self, monkeypatch):
        from app.domains.content.indicators import ClimateActionTrackerAdapter

        # Make backoff instant.
        import asyncio as _aio
        async def _no_sleep(_):
            return None
        monkeypatch.setattr(_aio, "sleep", _no_sleep)

        adapter = ClimateActionTrackerAdapter(
            http_client=_make_html_client(default_status=503),
            countries={"DE": "germany"},
            max_retries=3,
            inter_country_delay_seconds=0.0,
        )
        records = [r async for r in adapter.fetch_records()]
        # All 3 attempts failed; country skipped.
        assert records == []
        assert adapter._http_client.get.call_count == 3
