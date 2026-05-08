"""Green Transition route tests.

Covers:
- GET /api/green-transition/dimensions    — 7 dimensions with associated tags
- GET /api/green-transition/leaderboard   — pagination + dimension filter
- GET /api/green-transition/country/{cc}  — full per-country profile
- GET /api/green-transition/compare       — ≥2 countries → dimension scores

(All endpoints in this router are GET; /compare takes a comma-separated
`countries` query param rather than a POST body.)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_green_db():
    """Return a fake DB whose responses cover the green-transition queries."""
    now = datetime.utcnow()
    db = MagicMock()

    def _execute(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()

        # Country lookup in /country/{cc}
        if "select country_name from countries where country_code" in q:
            return [{"country_name": "Finland"}]

        # /country/{cc} per-category counts
        if (
            "select content_category, count(*) as cnt" in q
            and "max(published_date) as latest" in q
        ):
            return [
                {"content_category": "renewable_energy", "cnt": 8, "latest": now},
                {"content_category": "cleantech", "cnt": 4, "latest": now},
                {"content_category": "circular_economy", "cnt": 2, "latest": now},
                {"content_category": "sustainability", "cnt": 6, "latest": now},
                {"content_category": "green_transition", "cnt": 5, "latest": now},
                {"content_category": "resource_efficiency", "cnt": 3, "latest": now},
                {"content_category": "regenerative_economy", "cnt": 1, "latest": now},
            ]

        # /country/{cc} top tags per dimension
        if "select unnest(tags) as tag, count(*) as cnt" in q:
            return [
                {"tag": "solar", "cnt": 4},
                {"tag": "wind", "cnt": 3},
            ]

        # /country/{cc} top sources
        if (
            "select source_name, count(*) as cnt" in q
            and "and content_category = any" in q
        ):
            return [
                {"source_name": "YLE", "cnt": 8},
                {"source_name": "Reuters", "cnt": 5},
            ]

        # /leaderboard country-category aggregates
        if (
            "select a.country_code" in q
            and "a.content_category" in q
            and "count(*) as cnt" in q
        ):
            return [
                {"country_code": "FI", "content_category": "renewable_energy", "cnt": 10},
                {"country_code": "FI", "content_category": "sustainability", "cnt": 6},
                {"country_code": "DE", "content_category": "renewable_energy", "cnt": 12},
                {"country_code": "DE", "content_category": "cleantech", "cnt": 8},
                {"country_code": "KE", "content_category": "circular_economy", "cnt": 4},
            ]

        # /compare per-country category counts
        if (
            "select content_category, count(*) as cnt from articles where country_code"
            in q
        ):
            return [
                {"content_category": "renewable_energy", "cnt": 6},
                {"content_category": "cleantech", "cnt": 3},
                {"content_category": "sustainability", "cnt": 4},
            ]

        return []

    db.execute_query.side_effect = _execute
    db.execute_update.return_value = None
    db.execute_scalar.return_value = 0
    return db


@pytest.fixture
def green_db():
    """Install the green-transition fake DB into the global postgres slot."""
    import shared.database as _shared_db
    db = _make_green_db()
    prior = _shared_db._postgres_client
    _shared_db._postgres_client = db
    yield db
    _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# GET /dimensions
# ---------------------------------------------------------------------------

class TestDimensions:
    def test_returns_seven_dimensions(self, client, green_db):
        resp = client.get("/api/green-transition/dimensions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        assert len(data["dimensions"]) == 7

        # Each entry exposes id and tags
        for entry in data["dimensions"]:
            assert "id" in entry
            assert "tags" in entry
            assert isinstance(entry["tags"], list)

        ids = {d["id"] for d in data["dimensions"]}
        # Pin the canonical 7 dimension ids
        expected = {
            "green_transition", "renewable_energy", "cleantech",
            "circular_economy", "resource_efficiency", "regenerative_economy",
            "sustainability",
        }
        assert ids == expected


# ---------------------------------------------------------------------------
# GET /country/{cc}
# ---------------------------------------------------------------------------

class TestCountryProfile:
    def test_full_profile_shape(self, client, green_db):
        resp = client.get("/api/green-transition/country/FI")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["country_code"] == "FI"
        assert data["country_name"] == "Finland"
        assert "overall_green_score" in data
        assert isinstance(data["overall_green_score"], (int, float))
        assert 0.0 <= data["overall_green_score"] <= 10.0
        assert "dimensions" in data
        assert len(data["dimensions"]) == 7  # always all 7 returned

        for dim in data["dimensions"]:
            assert "dimension" in dim
            assert "score" in dim
            assert 0.0 <= dim["score"] <= 10.0
            assert "article_count" in dim
            assert "top_tags" in dim

        # top_sources from our stub
        assert "YLE" in data["top_sources"]


# ---------------------------------------------------------------------------
# GET /leaderboard
# ---------------------------------------------------------------------------

class TestLeaderboard:
    def test_default_leaderboard(self, client, green_db):
        resp = client.get("/api/green-transition/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "leaders" in data
        assert "total_countries" in data
        assert data["total_countries"] >= 1
        assert len(data["leaders"]) >= 1

        # Leaders should be sorted by overall score desc
        scores = [l["overall_green_score"] for l in data["leaders"]]
        assert scores == sorted(scores, reverse=True)

    def test_leaderboard_limit_pagination(self, client, green_db):
        resp = client.get("/api/green-transition/leaderboard?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["leaders"]) <= 2

    def test_leaderboard_dimension_filter(self, client, green_db):
        resp = client.get(
            "/api/green-transition/leaderboard?dimension=renewable_energy"
        )
        assert resp.status_code == 200
        data = resp.json()
        # Echoes back the dimension we filtered by
        assert data["dimension"] == "renewable_energy"

    def test_leaderboard_limit_bounds_rejected(self, client, green_db):
        # ge=1, le=100
        resp_low = client.get("/api/green-transition/leaderboard?limit=0")
        assert resp_low.status_code == 422
        resp_high = client.get("/api/green-transition/leaderboard?limit=999")
        assert resp_high.status_code == 422


# ---------------------------------------------------------------------------
# GET /compare
# ---------------------------------------------------------------------------

class TestCompare:
    def test_compare_two_countries_returns_dimension_scores(
        self, client, green_db
    ):
        resp = client.get("/api/green-transition/compare?countries=FI,DE")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "countries" in data
        assert "summary" in data
        assert "dimensions_tracked" in data
        assert len(data["dimensions_tracked"]) == 7
        assert len(data["countries"]) == 2

        # Each compared country lists scores for all 7 dimensions
        for country in data["countries"]:
            assert "country_code" in country
            assert "country_name" in country
            assert "overall_green_score" in country
            assert "dimensions" in country
            assert isinstance(country["dimensions"], dict)
            assert set(country["dimensions"].keys()) == set(data["dimensions_tracked"])
            for dim_name, dim_payload in country["dimensions"].items():
                assert "score" in dim_payload
                assert "articles" in dim_payload

    def test_compare_empty_countries_returns_error(self, client, green_db):
        resp = client.get("/api/green-transition/compare?countries=")
        # Per implementation, returns {"error": "..."} (200 status)
        # The route returns dict, not HTTPException
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert "error" in resp.json()

    def test_compare_three_countries(self, client, green_db):
        resp = client.get("/api/green-transition/compare?countries=FI,DE,KE")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["countries"]) == 3
        # Summary mentions both leader and laggard
        assert "summary" in data
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0
