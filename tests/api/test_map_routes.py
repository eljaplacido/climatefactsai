"""Map route tests.

Covers:
- GET /api/map/regions, /country-stats, /country/{cc}/detail
- GET /api/map/country/{cc}/climate-data — degraded path returns no fake data
- GET /api/map/compare — full 7 green-transition dimensions
- POST /api/map/query — view_context.country promoted into filter
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_country_db(*, countries: Optional[List[Dict[str, Any]]] = None):
    """Build a MagicMock DB whose execute_query handles map queries."""
    countries = countries or [{
        "country_code": "FI", "country_name": "Finland", "continent": "Europe",
        "flag_emoji": "FI", "latitude": 60.0, "longitude": 24.0,
    }]
    now = datetime.utcnow()

    def _execute(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()
        cc = (params.get("cc") or "").upper()

        if "from countries where country_code" in q:
            for c in countries:
                if c["country_code"] == cc:
                    return [c]
            return []
        if (
            "select a.country_code" in q
            and "count(*) as article_count" in q
            and "group by a.country_code" in q
            and "coalesce(c.location_country" not in q
        ):
            return [{
                "country_code": "FI", "article_count": 12, "source_count": 4,
                "last_updated": now, "avg_reliability": 78.5,
            }]
        if (
            "count(distinct a.article_id) as article_count" in q
            and "count(c.claim_id) as total_claims" in q
            and "group by a.country_code" in q
        ):
            return [{
                "country_code": "FI",
                "article_count": 12,
                "avg_reliability": 78.5,
                "total_claims": 10,
                "disputed": 1,
                "unverified": 1,
            }]
        if "unnest(tags)" in q and "count(*)" in q:
            return [{"tag": "climate", "cnt": 6}, {"tag": "energy", "cnt": 3}]
        if "select source_name, count(*) as cnt" in q and "avg(reliability_score)" in q:
            return [{"source_name": "YLE", "cnt": 4, "avg_rel": 80.0}]
        if "select source_name, count(*) as cnt" in q:
            return [{"source_name": "YLE", "cnt": 6}]
        if (
            "from companies c" in q
            and "where c.country_code = :cc" in q
            and "group by c.company_id" in q
        ):
            if cc != "FI":
                return []
            rows = [
                {
                    "company_id": "11111111-1111-1111-1111-111111111111",
                    "name": "Wartsila",
                    "ticker": "WRT1V",
                    "country_code": "FI",
                    "sector_nace": "C28",
                    "disclosure_count": 2,
                    "latest_disclosure_year": 2024,
                    "sbti_validated": True,
                    "net_zero_target_year": 2040,
                },
                {
                    "company_id": "22222222-2222-2222-2222-222222222222",
                    "name": "Neste",
                    "ticker": "NESTE",
                    "country_code": "FI",
                    "sector_nace": "C19",
                    "disclosure_count": 1,
                    "latest_disclosure_year": 2023,
                    "sbti_validated": False,
                    "net_zero_target_year": None,
                },
            ]
            if params.get("sbti_only"):
                rows = [r for r in rows if r.get("sbti_validated")]
            return rows
        if (
            "from companies c" in q
            and "group by c.country_code" in q
            and "company_count" in q
        ):
            return [
                {
                    "country_code": "FI",
                    "company_count": 2,
                    "sbti_validated_count": 1,
                    "net_zero_target_count": 1,
                },
                {
                    "country_code": "SE",
                    "company_count": 1,
                    "sbti_validated_count": 1,
                    "net_zero_target_count": 1,
                },
            ]
        if (
            "count(distinct a.article_id) as event_count" in q
            and "a.created_at >= now() - make_interval(days => :days)" in q
            and "group by a.country_code" in q
        ):
            return [
                {
                    "country_code": "FI",
                    "event_count": 9,
                    "disputed_count": 2,
                    "latest_event_at": now,
                },
                {
                    "country_code": "SE",
                    "event_count": 3,
                    "disputed_count": 0,
                    "latest_event_at": now,
                },
            ]
        if "select count(*) as total" in q and "avg(reliability_score) as avg_cred" in q:
            return [{"total": 8, "avg_cred": 78.5}]
        if "coalesce(content_category" in q:
            return [{"cat": "renewable_energy", "cnt": 4}]
        if "select article_id, title, source_name" in q:
            return [{
                "article_id": "art-001", "title": "Solar boom",
                "source_name": "YLE", "published_date": now,
                "overall_credibility": "HIGH",
                "excerpt": "Solar capacity grew rapidly.",
            }]
        if "count(c.claim_id) as total_claims" in q:
            return [{"total_claims": 10, "disputed": 1, "high_severity": 3}]
        if (
            "select count(*) as cnt" in q
            and "count(distinct source_name) as src_cnt" in q
        ):
            return [{"cnt": 5, "src_cnt": 2, "avg_cred": 75.0}]
        if "select content_category, count(*) as cnt" in q and "where country_code" in q:
            return [
                {"content_category": "renewable_energy", "cnt": 6},
                {"content_category": "cleantech", "cnt": 4},
                {"content_category": "circular_economy", "cnt": 2},
                {"content_category": "sustainability", "cnt": 3},
            ]
        if "select count(*) as total from articles" in q:
            return [{"total": 12}]
        if (
            "select a.country_code" in q
            and "avg(a.reliability_score) as avg_reliability" in q
            and "group by a.country_code" in q
        ):
            return [{
                "country_code": (params.get("countries") or ["FI"])[0]
                if isinstance(params.get("countries"), list) else "FI",
                "article_count": 12, "avg_reliability": 78.5, "last_updated": now,
            }]
        if "join claims c on c.article_id = a.article_id" in q and "claim_cnt" in q:
            return [{"country_code": "FI", "claim_cnt": 4, "risky_cnt": 1}]
        if "select distinct country_code from articles" in q:
            return [{"country_code": "FI"}, {"country_code": "SE"}]
        if (
            "ssp126" in q and "ssp245" in q and "ssp370" in q
            and "from countries cc" in q and "left join country_projections cp" in q
        ):
            return [{"country_code": "FI", "ssp126": 1.5, "ssp245": 2.8, "ssp370": 4.2}]
        if (
            "ndc_target_year" in q and "ndc_target_reduction" in q
            and "from countries cc" in q and "left join country_indicators ci" in q
        ):
            return [{
                "country_code": "FI",
                "ndc_target_year": 2035,
                "ndc_target_reduction_pct": 60.0,
                "cat_overall_rating": 55.0,
            }]
        if (
            "nd_gain_index" in q and "nd_gain_vulnerability" in q and "nd_gain_readiness" in q
            and "from country_indicators ci" in q
        ):
            return [{
                "country_code": "FI",
                "nd_gain": 65.0,
                "vulnerability": 40.0,
                "readiness": 55.0,
            }]
        if "select count(*) as cnt" in q and "from countries" in q and "enabled = true" in q:
            return [{"cnt": 2}]
        if "from country_projections" in q and "where country_code = :cc" in q:
            if cc != "FI":
                return []
            return [
                {
                    "scenario": "SSP1-2.6", "horizon_year": 2030, "temp_anomaly_c": 1.2,
                    "methodology_version": "AR6-v1", "citation_url": "https://ipcc.ch/ar6",
                },
                {
                    "scenario": "SSP1-2.6", "horizon_year": 2050, "temp_anomaly_c": 1.8,
                    "methodology_version": "AR6-v1", "citation_url": "https://ipcc.ch/ar6",
                },
                {
                    "scenario": "SSP2-4.5", "horizon_year": 2030, "temp_anomaly_c": 1.8,
                    "methodology_version": "AR6-v1", "citation_url": "https://ipcc.ch/ar6",
                },
                {
                    "scenario": "SSP2-4.5", "horizon_year": 2050, "temp_anomaly_c": 2.8,
                    "methodology_version": "AR6-v1", "citation_url": "https://ipcc.ch/ar6",
                },
                {
                    "scenario": "SSP3-7.0", "horizon_year": 2050, "temp_anomaly_c": 4.2,
                    "methodology_version": "AR6-v1", "citation_url": "https://ipcc.ch/ar6",
                },
            ]
        return []

    db = MagicMock()
    db.execute_query.side_effect = _execute
    db.execute_update.return_value = None
    db.execute_scalar.return_value = 0
    return db


@pytest.fixture
def map_db(monkeypatch):
    """Install a country/article fake DB and stub Open-Meteo."""
    import shared.database as _shared_db
    db = _make_country_db()
    prior = _shared_db._postgres_client
    _shared_db._postgres_client = db

    # After the api/map split, the country-detail handler lives in
    # api/map/routes_country.py and calls its module-local _fetch_*_weather
    # names, so patch there (the map_routes shim re-export no longer
    # intercepts the route's call site).
    from api.map import routes_country
    monkeypatch.setattr(
        routes_country, "_fetch_current_weather",
        AsyncMock(return_value={
            "temperature_c": 5.0, "humidity_pct": 70.0,
            "precipitation_mm": 0.0, "wind_speed_kmh": 12.0,
            "weather_code": 1,
        }),
    )
    monkeypatch.setattr(
        routes_country, "_fetch_historical_weather",
        AsyncMock(return_value={"temperature_avg": 4.0, "precipitation_avg": 30.0}),
    )

    yield db
    _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# GET /api/map/regions
# ---------------------------------------------------------------------------

class TestRegions:
    def test_regions_returns_full_catalogue(self, client):
        resp = client.get("/api/map/regions")
        assert resp.status_code == 200
        data = resp.json()
        for region in ("europe", "africa", "asia", "north_america", "oceania"):
            assert region in data
            assert "countries" in data[region]
            assert "count" in data[region]
            assert data[region]["count"] == len(data[region]["countries"])
        assert data["europe"]["count"] >= 30


# ---------------------------------------------------------------------------
# GET /api/map/country-stats
# ---------------------------------------------------------------------------

class TestCountryStats:
    def test_country_stats_basic(self, client, map_db):
        resp = client.get("/api/map/country-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        first = data[0]
        assert first["country_code"] == "FI"
        assert first["article_count"] == 12
        assert first["country_name"] == "Finland"

    def test_country_stats_with_filters(self, client, map_db):
        for url in (
            "/api/map/country-stats?source=YLE",
            "/api/map/country-stats?credibility=HIGH",
            "/api/map/country-stats?keyword=solar",
            "/api/map/country-stats?reliability_min=50",
        ):
            assert client.get(url).status_code == 200

    def test_reliability_min_bounds(self, client, map_db):
        assert client.get("/api/map/country-stats?reliability_min=999").status_code == 422
        assert client.get("/api/map/country-stats?reliability_min=-1").status_code == 422

    def test_source_count_falls_back_to_one_when_articles_exist(self, client, map_db):
        original = map_db.execute_query.side_effect

        def _side_effect(query, params=None):
            q = " ".join(query.split()).lower()
            if (
                "select a.country_code" in q
                and "count(*) as article_count" in q
                and "group by a.country_code" in q
                and "coalesce(c.location_country" not in q
            ):
                return [{
                    "country_code": "FI",
                    "article_count": 5,
                    "source_count": 0,
                    "last_updated": datetime.utcnow(),
                    "avg_reliability": 72.0,
                }]
            return original(query, params)

        map_db.execute_query.side_effect = _side_effect

        resp = client.get("/api/map/country-stats")
        assert resp.status_code == 200
        first = resp.json()[0]
        assert first["article_count"] == 5
        assert first["source_count"] == 1


class TestClimateRiskLayer:
    def test_layer_returns_dense_scores_even_without_claims(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        original = map_db.execute_query.side_effect

        def _side_effect(query, params=None):
            q = " ".join(query.split()).lower()
            if (
                "count(distinct a.article_id) as article_count" in q
                and "count(c.claim_id) as total_claims" in q
                and "group by a.country_code" in q
            ):
                return [{
                    "country_code": "FI",
                    "article_count": 9,
                    "avg_reliability": 82.0,
                    "total_claims": 0,
                    "disputed": 0,
                    "unverified": 0,
                }]
            return original(query, params)

        map_db.execute_query.side_effect = _side_effect

        resp = client.get("/api/map/layers/climate-risk")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["country_code"] == "FI"
        assert data[0]["claim_count"] == 0
        assert data[0]["disputed_ratio"] == 0.0
        assert data[0]["risk_score"] > 0


# ---------------------------------------------------------------------------
# GET /api/map/country/{cc}/detail
# ---------------------------------------------------------------------------

class TestCountryDetail:
    def test_returns_country_detail_shape(self, client, map_db):
        resp = client.get("/api/map/country/FI/detail")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for key in (
            "country_code", "country_name", "continent", "region",
            "flag_emoji", "latitude", "longitude", "weather",
            "article_count", "articles_by_category", "avg_credibility",
            "recent_articles", "source_coverage",
            "high_severity_claims", "disputed_claims_ratio",
        ):
            assert key in data, f"missing key: {key}"
        assert data["country_code"] == "FI"
        assert data["country_name"] == "Finland"
        assert data["weather"]["temperature_c"] == 5.0
        # current(5.0) - hist(4.0) = 1.0
        assert data["weather"]["temperature_anomaly_c"] == 1.0

    def test_unknown_country_returns_empty_shape_not_500(self, client, map_db):
        resp = client.get("/api/map/country/XX/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["country_code"] == "XX"


# ---------------------------------------------------------------------------
# GET /api/map/country/{cc}/companies
# ---------------------------------------------------------------------------

class TestCountryCompanies:
    def test_country_companies_returns_list(self, client, map_db):
        resp = client.get("/api/map/country/FI/companies")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] == "FI"
        assert "disclosure_count" in first
        assert "sbti_validated" in first

    def test_country_companies_invalid_code_rejected(self, client, map_db):
        resp = client.get("/api/map/country/FIN/companies")
        assert resp.status_code == 400

    def test_country_companies_sbti_only_filter(self, client, map_db):
        resp = client.get("/api/map/country/FI/companies?sbti_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sbti_validated"] is True


# ---------------------------------------------------------------------------
# GET /api/map/layers/corporate-density
# ---------------------------------------------------------------------------

class TestCorporateDensityLayer:
    def test_corporate_density_layer_returns_country_counts(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/corporate-density")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] in {"FI", "SE"}
        assert "company_count" in first
        assert "sbti_validated_count" in first
        assert "net_zero_target_count" in first


class TestNewsEventsLayer:
    def test_news_events_layer_returns_intensity_scores(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/news-events?window_days=21")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] in {"FI", "SE"}
        assert "event_count" in first
        assert "disputed_count" in first
        assert "controversy_score" in first


# ---------------------------------------------------------------------------
# GET /api/map/country/{cc}/climate-data
# ---------------------------------------------------------------------------

class TestClimateData:
    def test_degraded_when_open_meteo_unavailable(self, client, monkeypatch, map_db):
        """When Open-Meteo is unreachable: return 200 with empty period slots —
        never fabricate climate numbers."""
        from api.map import routes_country
        monkeypatch.setattr(
            routes_country, "_fetch_historical_weather",
            AsyncMock(return_value=None),
        )

        resp = client.get("/api/map/country/FI/climate-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["country_code"] == "FI"
        assert data["current_month"] is None
        assert data["last_year_same_month"] is None
        assert data["five_years_ago_same_month"] is None
        assert data["temperature_trend"] is None
        assert data["precipitation_comparison"] is None

    def test_no_coords_returns_empty_payload(self, client, map_db):
        # 'XX' is not in COUNTRY_COORDS — endpoint returns the empty payload.
        resp = client.get("/api/map/country/XX/climate-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["country_code"] == "XX"
        assert data["current_month"] is None


# ---------------------------------------------------------------------------
# GET /api/map/compare
# ---------------------------------------------------------------------------

class TestCompare:
    def test_compare_two_countries_returns_seven_dims(self, client, map_db):
        resp = client.get("/api/map/compare?countries=US,DE")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "countries" in data
        assert "country_a" in data
        assert "country_b" in data
        assert len(data["countries"]) == 2
        for c in data["countries"]:
            for dim in (
                "green_transition_score", "renewable_energy_score",
                "cleantech_score", "circular_economy_score",
                "resource_efficiency_score", "regenerative_score",
                "sustainability_score",
            ):
                assert dim in c, f"missing dimension {dim}"
            assert c["climate_risk"] == c["climate_risk_score"]

    def test_compare_zero_countries_rejected(self, client, map_db):
        assert client.get("/api/map/compare?countries=").status_code == 400

    def test_compare_too_many_countries_rejected(self, client, map_db):
        codes = ",".join(f"C{i}" for i in range(15))
        assert client.get(f"/api/map/compare?countries={codes}").status_code == 400


# ---------------------------------------------------------------------------
# POST /api/map/query — view_context.country promotion
# ---------------------------------------------------------------------------

class TestMapQueryViewContext:
    def test_country_in_view_context_promoted_into_filter(
        self, client, map_db, monkeypatch
    ):
        from api.map import routes_query
        monkeypatch.setattr(
            routes_query, "_llm_parse_query", AsyncMock(return_value={})
        )
        monkeypatch.setattr(
            routes_query, "_llm_generate_map_answer", AsyncMock(return_value=(None, None, []))
        )

        resp = client.post(
            "/api/map/query",
            json={
                "query": "what about it?",
                "view_context": {"country": "fi"},
            },
        )
        assert resp.status_code == 200, resp.text
        applied = resp.json()["filters_applied"]
        assert applied.get("countries") == ["FI"]

    def test_explicit_countries_override_view_context(
        self, client, map_db, monkeypatch
    ):
        from api.map import routes_query
        monkeypatch.setattr(
            routes_query, "_llm_parse_query", AsyncMock(return_value={})
        )
        monkeypatch.setattr(
            routes_query, "_llm_generate_map_answer", AsyncMock(return_value=(None, None, []))
        )

        resp = client.post(
            "/api/map/query",
            json={
                "query": "comparison?",
                "countries": ["DE"],
                "view_context": {"country": "FI"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["filters_applied"].get("countries") == ["DE"]

    def test_compare_countries_in_view_context_promoted(
        self, client, map_db, monkeypatch
    ):
        from api.map import routes_query
        monkeypatch.setattr(
            routes_query, "_llm_parse_query", AsyncMock(return_value={})
        )
        monkeypatch.setattr(
            routes_query, "_llm_generate_map_answer", AsyncMock(return_value=(None, None, []))
        )

        resp = client.post(
            "/api/map/query",
            json={
                "query": "compare them",
                "view_context": {"compare_countries": ["fi", "se", "no"]},
            },
        )
        assert resp.status_code == 200
        applied = resp.json()["filters_applied"]
        assert set(applied.get("countries") or []) == {"FI", "SE", "NO"}


# ---------------------------------------------------------------------------
# GET /api/map/layers/temperature-anomaly
# ---------------------------------------------------------------------------

class TestTemperatureAnomalyLayer:
    def test_layer_returns_data_shape(self, client, map_db, monkeypatch):
        from api import map_routes
        from api.map import routes_layers as map_layers

        map_routes._cache.clear()
        monkeypatch.setattr(
            map_layers, "_fetch_current_weather",
            AsyncMock(return_value={
                "temperature_c": 5.0, "precipitation_mm": 0.0,
            }),
        )
        monkeypatch.setattr(
            map_layers, "_fetch_historical_weather",
            AsyncMock(return_value={"temperature_avg": 4.0, "precipitation_avg": 30.0}),
        )

        resp = client.get("/api/map/layers/temperature-anomaly")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] == "FI"
        assert "anomaly_celsius" in first
        assert "trend" in first
        assert "current_temp" in first
        assert "historical_avg" in first


# ---------------------------------------------------------------------------
# GET /api/map/layers/ndc-status
# ---------------------------------------------------------------------------

class TestNdcStatusLayer:
    def test_layer_returns_status_categories(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/ndc-status")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] == "FI"
        assert "status_category" in first
        assert first["status_category"] in ("net_zero", "strong", "moderate", "weak", "no_data")
        assert "ndc_target_year" in first
        assert "ndc_target_reduction_pct" in first
        assert "cat_overall_rating" in first


# ---------------------------------------------------------------------------
# GET /api/map/layers/warming-outlook
# ---------------------------------------------------------------------------

class TestWarmingOutlookLayer:
    def test_layer_returns_scenario_anomalies(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/warming-outlook")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] == "FI"
        assert "ssp126_anomaly_c" in first
        assert "ssp245_anomaly_c" in first
        assert "ssp370_anomaly_c" in first
        assert "best_estimate_c" in first
        assert "covered" in first

    def test_layer_with_custom_horizon(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/warming-outlook?horizon_year=2030")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["country_code"] == "FI"


# ---------------------------------------------------------------------------
# GET /api/map/layers/adaptation-finance-gap
# ---------------------------------------------------------------------------

class TestAdaptationGapLayer:
    def test_layer_returns_gap_scores(self, client, map_db):
        from api import map_routes

        map_routes._cache.clear()
        resp = client.get("/api/map/layers/adaptation-finance-gap")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        first = data[0]
        assert first["country_code"] == "FI"
        assert "adaptation_gap_score" in first
        assert "nd_gain_index" in first
        assert "vulnerability_score" in first
        assert "readiness_score" in first
        assert "covered" in first


# ---------------------------------------------------------------------------
# GET /api/map/biome-overview
# ---------------------------------------------------------------------------

class TestBiomeOverview:
    def test_overview_returns_biomes_with_taxonomy(self, client):
        resp = client.get("/api/map/biome-overview")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "countries" in data
        assert "biome_taxonomy" in data
        assert "koppen_taxonomy" in data
        assert "total_countries" in data
        assert isinstance(data["countries"], list)
        assert len(data["countries"]) >= 1
        first = data["countries"][0]
        assert "country_code" in first
        assert "biome_id" in first
        assert "biome_label" in first
        assert "koppen_id" in first
        assert "koppen_color" in first


# ---------------------------------------------------------------------------
# GET /api/map/country/{cc}/biome
# ---------------------------------------------------------------------------

class TestCountryBiome:
    def test_returns_biome_for_finland(self, client):
        resp = client.get("/api/map/country/FI/biome")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["country_code"] == "FI"
        assert "biome_summary" in data
        assert "climate_effects" in data
        assert "biome_symbol" in data
        symbol = data["biome_symbol"]
        assert "biome_id" in symbol
        assert "biome_label" in symbol
        assert "koppen_id" in symbol
        assert "koppen_color" in symbol

    def test_invalid_country_code_rejected(self, client):
        resp = client.get("/api/map/country/FIN/biome")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/map/country/{cc}/projections
# ---------------------------------------------------------------------------

class TestCountryProjections:
    def test_returns_scenario_projections(self, client, map_db):
        resp = client.get("/api/map/country/FI/projections")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["country_code"] == "FI"
        assert "scenarios" in data
        assert "available" in data
        assert data["available"] is True
        scenarios = data["scenarios"]
        assert isinstance(scenarios, dict)
        assert len(scenarios) >= 1
        # each scenario key maps to a list of {horizon_year, temp_anomaly_c}
        ssp126 = scenarios.get("SSP1-2.6")
        assert ssp126 is not None
        assert isinstance(ssp126, list)
        assert len(ssp126) >= 1
        assert "horizon_year" in ssp126[0]
        assert "temp_anomaly_c" in ssp126[0]

    def test_unknown_country_returns_empty_scenarios(self, client, map_db):
        resp = client.get("/api/map/country/XX/projections")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["country_code"] == "XX"
        assert data["available"] is False
        assert data["scenarios"] == {}

    def test_invalid_code_rejected(self, client):
        resp = client.get("/api/map/country/FIN/projections")
        assert resp.status_code == 400
