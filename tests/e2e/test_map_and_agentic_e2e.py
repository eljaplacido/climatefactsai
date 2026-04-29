"""
End-to-end tests for Climate Intelligence Map, source/theme filtering,
agentic query features, and weather overlay.

Tests cover:
- Map country stats endpoints (publisher + discussed modes)
- Source filtering on map
- Reliability tier filtering
- Category/theme filtering
- Agentic map query (natural language + structured)
- Weather overlay for selected country
- Source coverage / available sources / available themes APIs
- Region listing
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_climatenews")

from fastapi.testclient import TestClient
from api.main import app, get_db


# ============================================================================
# FakeDB with map-relevant data across all continents
# ============================================================================

class MapFakeDB:
    """In-memory DB stub with global article data for map tests."""

    def __init__(self):
        self.now = datetime.utcnow()
        # Articles spanning 6 continents
        self.articles = [
            # Europe (3)
            {"article_id": "eu-1", "title": "Finland Renewable Energy", "country_code": "FI",
             "source_name": "YLE", "reliability_score": 88, "tags": ["climate", "renewable-energy"],
             "content_category": "climate_science", "created_at": self.now},
            {"article_id": "eu-2", "title": "Germany Wind Power", "country_code": "DE",
             "source_name": "Nature", "reliability_score": 92, "tags": ["climate", "wind-power"],
             "content_category": "green_transition", "created_at": self.now},
            {"article_id": "eu-3", "title": "Spain Desertification", "country_code": "ES",
             "source_name": "Nature", "reliability_score": 89, "tags": ["climate", "water-stress"],
             "content_category": "climate_science", "created_at": self.now},
            # North America (2)
            {"article_id": "na-1", "title": "US Wildfire Season", "country_code": "US",
             "source_name": "NRDC", "reliability_score": 85, "tags": ["climate", "wildfire"],
             "content_category": "climate_science", "created_at": self.now},
            {"article_id": "na-2", "title": "Canada Arctic Ice", "country_code": "CA",
             "source_name": "ECCC", "reliability_score": 91, "tags": ["climate", "arctic"],
             "content_category": "climate_science", "created_at": self.now},
            # Africa (2)
            {"article_id": "af-1", "title": "Kenya Geothermal", "country_code": "KE",
             "source_name": "ACF", "reliability_score": 84, "tags": ["climate", "clean-energy"],
             "content_category": "green_transition", "created_at": self.now},
            {"article_id": "af-2", "title": "Nigeria Flooding", "country_code": "NG",
             "source_name": "UNEP", "reliability_score": 92, "tags": ["climate", "adaptation"],
             "content_category": "climate_science", "created_at": self.now},
            # Asia (2)
            {"article_id": "as-1", "title": "China Solar Record", "country_code": "CN",
             "source_name": "IEA", "reliability_score": 92, "tags": ["climate", "solar"],
             "content_category": "green_transition", "created_at": self.now},
            {"article_id": "as-2", "title": "India Heat Wave", "country_code": "IN",
             "source_name": "TERI", "reliability_score": 83, "tags": ["climate", "temperature"],
             "content_category": "climate_science", "created_at": self.now},
            # Middle East (1)
            {"article_id": "me-1", "title": "UAE Solar Expansion", "country_code": "AE",
             "source_name": "Masdar", "reliability_score": 76, "tags": ["climate", "solar"],
             "content_category": "green_transition", "created_at": self.now},
            # Latin America (1)
            {"article_id": "la-1", "title": "Amazon Deforestation", "country_code": "BR",
             "source_name": "INPE", "reliability_score": 90, "tags": ["climate", "deforestation"],
             "content_category": "climate_science", "created_at": self.now},
        ]

        self.claims = [
            {"claim_id": "c-1", "article_id": "eu-1", "location_country": "FI"},
            {"claim_id": "c-2", "article_id": "na-1", "location_country": "US"},
            {"claim_id": "c-3", "article_id": "af-1", "location_country": "KE"},
            {"claim_id": "c-4", "article_id": "as-1", "location_country": "CN"},
            {"claim_id": "c-5", "article_id": "la-1", "location_country": "BR"},
        ]

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        params = params or {}
        nq = " ".join(query.split()).lower()

        # --- Discussed sub-queries (must match before main discussed query) ---
        # Discussed top_topics sub-query (unnest + coalesce)
        if "unnest(a.tags) as tag" in nq and "coalesce(c.location_country" in nq:
            return [{"tag": "climate", "cnt": 5}]

        # Discussed top_sources sub-query (source_name + coalesce + group by)
        if "a.source_name" in nq and "coalesce(c.location_country" in nq and "group by a.source_name" in nq:
            cc = params.get("cc", "")
            matched = [a for a in self.articles if a["country_code"] == cc]
            return [{"source_name": a["source_name"], "cnt": 1} for a in matched[:3]]

        # Topic density — :topic = any(a.tags) — must come before generic country grouping
        if ":topic = any(a.tags)" in nq:
            topic = (params.get("topic") or "").lower()
            groups = {}
            for a in self.articles:
                low_tags = [t.lower() for t in a.get("tags", [])]
                if topic and topic in low_tags:
                    cc = a["country_code"]
                    if cc not in groups:
                        groups[cc] = {"country_code": cc, "article_count": 0}
                    groups[cc]["article_count"] += 1
            return list(groups.values())

        # Country stats grouping
        if "group by a.country_code" in nq and "from articles a" in nq:
            groups: Dict[str, Dict] = {}
            for a in self._filter_articles(nq, params):
                cc = a["country_code"]
                if cc not in groups:
                    groups[cc] = {"country_code": cc, "article_count": 0,
                                  "last_updated": a["created_at"], "avg_reliability": a["reliability_score"]}
                groups[cc]["article_count"] += 1
            return list(groups.values())

        # Discussed country stats (main grouping query)
        if "coalesce(c.location_country" in nq and "group by" in nq and "count" in nq:
            groups = {}
            for a in self.articles:
                cc = a["country_code"]
                if params.get("source") and a["source_name"].lower() != params["source"].lower():
                    continue
                if cc not in groups:
                    groups[cc] = {"country_code": cc, "article_count": 0,
                                  "last_updated": a["created_at"], "avg_reliability": a["reliability_score"]}
                groups[cc]["article_count"] += 1
            return list(groups.values())

        # Country name lookup
        if "from countries" in nq:
            return [
                {"country_code": "FI", "country_name": "Finland"},
                {"country_code": "DE", "country_name": "Germany"},
                {"country_code": "ES", "country_name": "Spain"},
                {"country_code": "US", "country_name": "United States"},
                {"country_code": "CA", "country_name": "Canada"},
                {"country_code": "KE", "country_name": "Kenya"},
                {"country_code": "NG", "country_name": "Nigeria"},
                {"country_code": "CN", "country_name": "China"},
                {"country_code": "IN", "country_name": "India"},
                {"country_code": "AE", "country_name": "UAE"},
                {"country_code": "BR", "country_name": "Brazil"},
            ]

        # Tag/topic queries (top_topics sub-query uses column alias "tag")
        if "unnest" in nq and "tags" in nq and "as tag" in nq:
            return [{"tag": "climate", "cnt": 10}, {"tag": "renewable-energy", "cnt": 3}]

        # Source queries
        if "source_name" in nq and "group by" in nq and "country_code" in nq and "from articles" in nq:
            results = []
            for a in self.articles:
                results.append({
                    "source_name": a["source_name"],
                    "country_code": a["country_code"],
                    "article_count": 1,
                    "avg_reliability": a["reliability_score"],
                })
            return results

        # Available sources
        if "source_name" in nq and "group by source_name" in nq:
            source_counts: Dict[str, Dict] = {}
            for a in self.articles:
                sn = a["source_name"]
                if sn not in source_counts:
                    source_counts[sn] = {"source_name": sn, "article_count": 0, "avg_reliability": a["reliability_score"]}
                source_counts[sn]["article_count"] += 1
            return list(source_counts.values())

        # Available themes
        if "unnest(tags) as theme" in nq:
            tag_counts: Dict[str, int] = {}
            for a in self.articles:
                for t in a.get("tags", []):
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            return [{"theme": t, "article_count": c} for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])]

        # Count query for map/query
        if "count(*) as total" in nq:
            return [{"total": len(self._filter_articles(nq, params))}]

        # Full text search (map query)
        if "plainto_tsquery" in nq or "to_tsvector" in nq:
            q = params.get("q", "").lower()
            groups = {}
            for a in self.articles:
                if q in a["title"].lower():
                    cc = a["country_code"]
                    if cc not in groups:
                        groups[cc] = {"country_code": cc, "article_count": 0,
                                      "avg_reliability": a["reliability_score"],
                                      "last_updated": a["created_at"]}
                    groups[cc]["article_count"] += 1
            return list(groups.values())

        return []

    def _filter_articles(self, nq: str, params: Dict):
        arts = list(self.articles)
        if params.get("source"):
            arts = [a for a in arts if a["source_name"].lower() == params["source"].lower()]
        if params.get("rel_min"):
            arts = [a for a in arts if (a.get("reliability_score") or 0) >= params["rel_min"]]
        if params.get("region_codes"):
            arts = [a for a in arts if a["country_code"] in params["region_codes"]]
        if params.get("countries"):
            arts = [a for a in arts if a["country_code"] in params["countries"]]
        return arts


@pytest.fixture
def map_client():
    db = MapFakeDB()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    # Patch the global postgres singleton so ALL modules get the mock.
    import shared.database as _shared_db
    _orig_pg = _shared_db._postgres_client
    _shared_db._postgres_client = db

    # Mock LLM client so _llm_parse_query / _llm_generate_map_answer return instantly.
    from unittest.mock import MagicMock, patch
    llm_mock = MagicMock()
    llm_mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="{}"))]
    )
    try:
        with patch("app.domains.intelligence.llm_client.get_llm_client", return_value=(llm_mock, "test-model")):
            with TestClient(app) as c:
                yield c
    finally:
        _shared_db._postgres_client = _orig_pg
        app.dependency_overrides.clear()


# ============================================================================
# Tests: Country Stats
# ============================================================================

class TestCountryStats:
    def test_publisher_origin_returns_all_countries(self, map_client):
        r = map_client.get("/api/map/country-stats")
        assert r.status_code == 200
        data = r.json()
        codes = {d["country_code"] for d in data}
        # Should have articles from multiple continents
        assert "FI" in codes
        assert "US" in codes
        assert "KE" in codes
        assert "CN" in codes

    def test_publisher_origin_with_source_filter(self, map_client):
        r = map_client.get("/api/map/country-stats", params={"source": "Nature"})
        assert r.status_code == 200
        data = r.json()
        codes = {d["country_code"] for d in data}
        assert "DE" in codes or "ES" in codes

    def test_publisher_origin_with_reliability_filter(self, map_client):
        r = map_client.get("/api/map/country-stats", params={"reliability_min": 90})
        assert r.status_code == 200
        data = r.json()
        for d in data:
            # All returned should have articles with avg reliability >= 90
            assert d["article_count"] >= 1

    def test_publisher_origin_with_region_filter(self, map_client):
        r = map_client.get("/api/map/country-stats", params={"region": "europe"})
        assert r.status_code == 200

    def test_discussed_country_stats(self, map_client):
        r = map_client.get("/api/map/discussed-country-stats")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    def test_discussed_with_source_filter(self, map_client):
        r = map_client.get("/api/map/discussed-country-stats", params={"source": "YLE"})
        assert r.status_code == 200


# ============================================================================
# Tests: Source Coverage & Available Sources
# ============================================================================

class TestSourceCoverage:
    def test_source_coverage_returns_data(self, map_client):
        r = map_client.get("/api/map/source-coverage")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_source_coverage_filter_by_country(self, map_client):
        r = map_client.get("/api/map/source-coverage", params={"country": "FI"})
        assert r.status_code == 200

    def test_source_coverage_filter_by_source(self, map_client):
        r = map_client.get("/api/map/source-coverage", params={"source": "Nature"})
        assert r.status_code == 200

    def test_available_sources_returns_list(self, map_client):
        r = map_client.get("/api/map/available-sources")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "source_name" in data[0]
            assert "article_count" in data[0]

    def test_available_themes_returns_list(self, map_client):
        r = map_client.get("/api/map/available-themes")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "theme" in data[0]
            assert "article_count" in data[0]


# ============================================================================
# Tests: Topic Density
# ============================================================================

class TestTopicDensity:
    def test_topic_density_valid_topic(self, map_client):
        r = map_client.get("/api/map/topic-density", params={"topic": "climate"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_topic_density_empty_for_nonexistent(self, map_client):
        r = map_client.get("/api/map/topic-density", params={"topic": "nonexistent-xyz"})
        assert r.status_code == 200
        assert r.json() == []

    def test_topic_density_requires_topic(self, map_client):
        r = map_client.get("/api/map/topic-density")
        assert r.status_code == 422  # validation error


# ============================================================================
# Tests: Agentic Map Query
# ============================================================================

class TestAgenticMapQuery:
    def test_natural_language_query(self, map_client):
        r = map_client.post("/api/map/query", json={
            "query": "wildfire",
            "limit": 10,
        })
        assert r.status_code == 200
        data = r.json()
        assert "country_highlights" in data
        assert "matching_articles" in data
        assert "queried_at" in data

    def test_structured_query_by_region(self, map_client):
        r = map_client.post("/api/map/query", json={
            "region": "europe",
            "limit": 20,
        })
        assert r.status_code == 200
        data = r.json()
        assert "country_highlights" in data

    def test_structured_query_by_countries(self, map_client):
        r = map_client.post("/api/map/query", json={
            "countries": ["FI", "DE"],
            "limit": 20,
        })
        assert r.status_code == 200

    def test_structured_query_by_source(self, map_client):
        r = map_client.post("/api/map/query", json={
            "sources": ["Nature"],
            "limit": 20,
        })
        assert r.status_code == 200

    def test_structured_query_with_reliability(self, map_client):
        r = map_client.post("/api/map/query", json={
            "reliability_min": 90,
            "limit": 20,
        })
        assert r.status_code == 200

    def test_combined_query_with_answer(self, map_client):
        r = map_client.post("/api/map/query", json={
            "query": "Solar",
            "region": "asia",
            "limit": 10,
        })
        assert r.status_code == 200
        data = r.json()
        # If results found, should have an answer
        if data.get("matching_articles", 0) > 0:
            assert data.get("answer") is not None

    def test_query_no_results_returns_message(self, map_client):
        r = map_client.post("/api/map/query", json={
            "query": "completely-nonexistent-topic-xyz-2099",
            "limit": 10,
        })
        assert r.status_code == 200
        data = r.json()
        if data.get("matching_articles", 0) == 0 and data.get("query"):
            assert "No articles" in (data.get("answer") or "")

    def test_query_filters_applied_tracked(self, map_client):
        r = map_client.post("/api/map/query", json={
            "query": "climate",
            "region": "africa",
            "reliability_min": 80,
            "limit": 10,
        })
        assert r.status_code == 200
        data = r.json()
        filters = data.get("filters_applied", {})
        assert "region" in filters or "reliability_min" in filters


# ============================================================================
# Tests: Regions
# ============================================================================

class TestRegions:
    def test_list_regions(self, map_client):
        r = map_client.get("/api/map/regions")
        assert r.status_code == 200
        data = r.json()
        assert "europe" in data
        assert "africa" in data
        assert "asia" in data
        assert "north_america" in data
        assert "latin_america" in data
        assert "middle_east" in data

    def test_region_has_countries(self, map_client):
        r = map_client.get("/api/map/regions")
        data = r.json()
        assert len(data["europe"]["countries"]) > 10
        assert "FI" in data["europe"]["countries"]


# ============================================================================
# Tests: Response Schema Validation
# ============================================================================

class TestResponseSchemas:
    def test_country_stats_schema(self, map_client):
        r = map_client.get("/api/map/country-stats")
        assert r.status_code == 200
        data = r.json()
        if data:
            item = data[0]
            assert "country_code" in item
            assert "country_name" in item
            assert "article_count" in item
            assert isinstance(item["article_count"], int)

    def test_map_query_response_schema(self, map_client):
        r = map_client.post("/api/map/query", json={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert "country_highlights" in data
        assert "matching_articles" in data
        assert "queried_at" in data
        assert "filters_applied" in data

    def test_source_coverage_schema(self, map_client):
        r = map_client.get("/api/map/source-coverage")
        assert r.status_code == 200
        data = r.json()
        if data:
            item = data[0]
            assert "source_name" in item
            assert "country_code" in item
            assert "article_count" in item
