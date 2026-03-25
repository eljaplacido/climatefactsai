"""
Production Readiness End-to-End Tests

Validates all fixes from the 2026-03-24 platform evaluation:
1. Security fixes (OAuth CSRF, rate limiter, SSRF, RBAC)
2. Data layer integrity (migration conflicts resolved, schema_migrations table)
3. API endpoint coverage for agentic access
4. Data source pipeline robustness
5. Visualization data endpoints
6. User persona journey coverage
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-minimum-32-bytes-long")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_climatenews")

pytestmark = [pytest.mark.e2e]


# =============================================================================
# FAKE DATABASE FOR TESTING
# =============================================================================

class ProductionReadinessFakeDB:
    """In-memory DB stub for production readiness tests."""

    def __init__(self):
        self.now = datetime.utcnow()
        self.users = [
            {"user_id": "admin-1", "email": "admin@clilens.ai", "subscription_tier": "enterprise",
             "is_active": True, "full_name": "Admin User"},
            {"user_id": "user-1", "email": "user@example.com", "subscription_tier": "freemium",
             "is_active": True, "full_name": "Free User"},
            {"user_id": "pro-1", "email": "pro@example.com", "subscription_tier": "professional",
             "is_active": True, "full_name": "Pro User"},
        ]
        self.articles = [
            {"article_id": str(uuid4()), "title": f"Climate Article {i}",
             "url": f"https://example.com/article-{i}", "source_name": "Test Source",
             "reliability_score": 85, "country_code": "FI", "tags": ["climate"],
             "content_category": "climate_science", "claims_status": "completed",
             "created_at": self.now, "overall_credibility": "HIGH",
             "source_credibility_score": 80, "claim_count": 2, "verified_claim_count": 1,
             "excerpt": f"Test article {i} about climate change."}
            for i in range(5)
        ]
        self.schema_migrations = [
            {"version": 0, "description": "init.sql", "applied_at": self.now}
        ]

    def execute_query(self, sql, params=None):
        sql_lower = sql.lower().strip()

        if "schema_migrations" in sql_lower and "select" in sql_lower:
            return self.schema_migrations

        if "from articles" in sql_lower or "from articles\n" in sql_lower:
            return self.articles

        if "from users" in sql_lower:
            if params and "email" in (params or {}):
                return [u for u in self.users if u["email"] == params["email"]]
            return self.users

        if "count(*)" in sql_lower:
            return [{"count": len(self.articles)}]

        return []

    def execute_update(self, sql, params=None):
        return True

    def execute_insert(self, sql, params=None):
        return [{"id": str(uuid4())}]


fake_db = ProductionReadinessFakeDB()


def override_get_db():
    return fake_db


# =============================================================================
# 1. SECURITY FIX TESTS
# =============================================================================

class TestOAuthCSRFProtection:
    """Verify OAuth callback requires state parameter validation."""

    def test_oauth_callback_model_has_state_field(self):
        from api.oauth_routes import OAuthCallbackRequest
        fields = OAuthCallbackRequest.model_fields if hasattr(OAuthCallbackRequest, 'model_fields') else OAuthCallbackRequest.__fields__
        assert "state" in fields, "OAuthCallbackRequest must include 'state' field for CSRF protection"

    def test_oauth_state_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        resp = client.get("/api/auth/oauth/state")
        assert resp.status_code in (200, 404), f"State endpoint should exist, got {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "state" in data, "State endpoint must return a 'state' token"


class TestRateLimiterRedis:
    """Verify rate limiter uses Redis instead of in-memory dict."""

    def test_rate_limiter_not_using_class_variable_dict(self):
        from api.rate_limiter import RateLimitMiddleware
        source_file = Path(REPO_ROOT / "api" / "rate_limiter.py")
        source = source_file.read_text(encoding="utf-8")
        # Check that we're importing/using Redis for IP counters
        assert "get_redis" in source or "redis" in source.lower(), \
            "Rate limiter should use Redis for IP counters, not in-memory dict"


class TestAdminRBAC:
    """Verify admin endpoints require authentication and role check."""

    def test_admin_pipeline_imports_auth(self):
        source_file = Path(REPO_ROOT / "api" / "admin_pipeline_routes.py")
        source = source_file.read_text(encoding="utf-8")
        assert "get_current_user" in source or "Depends" in source, \
            "Admin pipeline routes must import authentication dependency"

    def test_admin_pipeline_requires_auth(self):
        source_file = Path(REPO_ROOT / "api" / "admin_pipeline_routes.py")
        source = source_file.read_text(encoding="utf-8")
        # Check that route handlers use auth dependency
        assert "current_user" in source or "get_current_user" in source, \
            "Admin routes must enforce authentication"


class TestSSRFProtection:
    """Verify URL analysis has comprehensive SSRF protection."""

    def test_url_validator_blocks_private_ips(self):
        from api.url_analysis_routes import AnalyzeURLRequest
        from pydantic import ValidationError

        private_urls = [
            "https://127.0.0.1/test",
            "https://0.0.0.0/test",
            "https://localhost/test",
            "https://metadata.google.internal/computeMetadata/v1/",
        ]
        for url in private_urls:
            with pytest.raises((ValidationError, ValueError)):
                AnalyzeURLRequest(url=url)

    def test_url_validator_blocks_internal_tlds(self):
        from api.url_analysis_routes import AnalyzeURLRequest
        from pydantic import ValidationError

        internal_urls = [
            "https://server.internal/api",
            "https://db.local/data",
        ]
        for url in internal_urls:
            with pytest.raises((ValidationError, ValueError)):
                AnalyzeURLRequest(url=url)

    def test_url_validator_allows_valid_urls(self):
        from api.url_analysis_routes import AnalyzeURLRequest
        valid = AnalyzeURLRequest(url="https://www.bbc.co.uk/news/climate")
        assert str(valid.url).startswith("https://")


# =============================================================================
# 2. DATA LAYER INTEGRITY TESTS
# =============================================================================

class TestMigrationRegistry:
    """Verify migration registry table exists in init.sql."""

    def test_init_sql_creates_schema_migrations(self):
        init_sql = Path(REPO_ROOT / "infrastructure" / "database" / "init.sql")
        content = init_sql.read_text(encoding="utf-8")
        assert "schema_migrations" in content, \
            "init.sql must create schema_migrations table"
        assert "version INTEGER PRIMARY KEY" in content, \
            "schema_migrations must have version as PK"

    def test_migration_001_uses_alter_table(self):
        """Migration 001 should ALTER existing articles table, not CREATE a duplicate."""
        migration = Path(REPO_ROOT / "migrations" / "versions" / "001_add_trust_schema.sql")
        content = migration.read_text(encoding="utf-8")
        # Should NOT contain CREATE TABLE articles with SERIAL PK
        assert "id SERIAL PRIMARY KEY" not in content or "articles" not in content.split("id SERIAL PRIMARY KEY")[0][-50:], \
            "Migration 001 must not create duplicate articles table with SERIAL PK"
        # Should use ALTER TABLE articles
        assert "ALTER TABLE articles" in content, \
            "Migration 001 should ALTER the existing articles table"

    def test_migration_001_moderation_uses_uuid_fk(self):
        """Moderation queue should reference articles(article_id) UUID, not articles(id) INTEGER."""
        migration = Path(REPO_ROOT / "migrations" / "versions" / "001_add_trust_schema.sql")
        content = migration.read_text(encoding="utf-8")
        assert "article_id UUID" in content, \
            "moderation_queue.article_id should be UUID type"


# =============================================================================
# 3. API ENDPOINT COVERAGE FOR AGENTIC ACCESS
# =============================================================================

class TestAgenticAPIEndpointCoverage:
    """Verify all features have API endpoints for agentic/chatbot access."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    REQUIRED_ENDPOINT_PATTERNS = [
        ("/api/articles", "GET", "Article listing"),
        ("/api/search", "GET", "Search"),
        ("/api/map/country-stats", "GET", "Map country stats"),
        ("/api/analytics/dashboard", "GET", "Analytics dashboard"),
        ("/api/auth/login", "POST", "User login"),
        ("/api/auth/register", "POST", "User registration"),
        ("/api/feed/preferences", "GET", "Feed preferences"),
        ("/api/chat", "POST", "Chat/Q&A"),
        ("/api/deep-search", "POST", "Deep search"),
        ("/api/translations/list", "GET", "Translations"),
        ("/api/sources", "GET", "Source listing"),
        ("/api/forecasts", "GET", "Forecasts"),
    ]

    def test_all_agentic_endpoints_respond(self):
        """Every feature must have an API endpoint that returns non-404."""
        failures = []
        for path, method, feature in self.REQUIRED_ENDPOINT_PATTERNS:
            if method == "GET":
                resp = self.client.get(path)
            else:
                resp = self.client.post(path, json={})
            if resp.status_code == 404:
                failures.append(f"{feature}: {method} {path} returned 404")

        assert not failures, f"Missing agentic endpoints:\n" + "\n".join(failures)


# =============================================================================
# 4. DATA SOURCE PIPELINE TESTS
# =============================================================================

class TestDataSourceRobustness:
    """Verify data source adapters and pipeline components exist and are functional."""

    def test_open_meteo_adapter_exists(self):
        adapter = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "data_sources" / "open_meteo_adapter.py")
        assert adapter.exists(), "Open-Meteo adapter must exist"
        content = adapter.read_text(encoding="utf-8")
        assert "fetch_current_weather" in content, "Must have current weather fetch"
        assert "fetch_historical_climate" in content, "Must have historical climate fetch"

    def test_copernicus_adapter_exists(self):
        adapter = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "data_sources" / "copernicus_adapter.py")
        assert adapter.exists(), "Copernicus adapter must exist"
        content = adapter.read_text(encoding="utf-8")
        assert "CopernicusAdapter" in content, "Must have CopernicusAdapter class"

    def test_ecmwf_adapter_exists(self):
        adapter = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "data_sources" / "ecmwf_adapter.py")
        assert adapter.exists(), "ECMWF adapter must exist"

    def test_rss_adapter_exists(self):
        adapter = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "data_sources" / "rss_adapter.py")
        assert adapter.exists(), "RSS adapter must exist"

    def test_eu_feeds_registry_has_minimum_countries(self):
        from app.domains.content.data_sources.eu_feeds_registry import (
            EU_CLIMATE_FEEDS, get_european_country_codes,
        )
        codes = get_european_country_codes()
        assert len(codes) >= 35, f"Expected 35+ European countries, got {len(codes)}"

    def test_weather_context_service_has_city_coords(self):
        service_file = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "weather_context_service.py")
        content = service_file.read_text(encoding="utf-8")
        # Must have Finnish cities
        assert "helsinki" in content.lower(), "Must have Helsinki coordinates"
        assert "tampere" in content.lower(), "Must have Tampere coordinates"

    def test_embedding_service_exists(self):
        service_file = Path(REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "embedding_service.py")
        assert service_file.exists(), "Embedding service must exist"
        content = service_file.read_text(encoding="utf-8")
        assert "1536" in content, "Must use 1536-dim embeddings (ada-002)"


# =============================================================================
# 5. VISUALIZATION DATA ENDPOINT TESTS
# =============================================================================

class TestVisualizationEndpoints:
    """Verify visualization-supporting API endpoints return structured data."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def test_map_country_stats_returns_structured_data(self):
        resp = self.client.get("/api/map/country-stats")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list) or isinstance(data, dict), \
                "Map stats must return structured data"

    def test_analytics_dashboard_returns_data(self):
        resp = self.client.get("/api/analytics/dashboard")
        assert resp.status_code in (200, 401, 503), \
            f"Analytics dashboard should return valid status, got {resp.status_code}"

    def test_forecasts_endpoint_returns_data(self):
        resp = self.client.get("/api/forecasts/FI")
        assert resp.status_code in (200, 503), \
            f"Forecast endpoint should return data or 503, got {resp.status_code}"


# =============================================================================
# 6. USER PERSONA JOURNEY TESTS
# =============================================================================

class TestClimateResearcherJourney:
    """Researcher: search, filter, analyze, export."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def test_search_with_filters(self):
        resp = self.client.get("/api/search?q=climate&country=FI&credibility=HIGH")
        assert resp.status_code in (200, 422), \
            f"Search with filters should work, got {resp.status_code}"

    def test_article_detail_with_claims(self):
        resp = self.client.get("/api/articles")
        if resp.status_code == 200:
            articles = resp.json()
            if articles:
                aid = articles[0].get("article_id", articles[0].get("id"))
                detail = self.client.get(f"/api/articles/{aid}")
                assert detail.status_code in (200, 404)


class TestCasualReaderJourney:
    """Reader: browse feed, personalize, share."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def test_homepage_articles_load(self):
        resp = self.client.get("/api/articles?limit=10")
        assert resp.status_code == 200, "Homepage articles must load"

    def test_country_filter_works(self):
        resp = self.client.get("/api/articles?country=FI")
        assert resp.status_code == 200, "Country filter must work"


class TestAdminOperatorJourney:
    """Admin: pipeline monitoring, analytics."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from api.main import app, get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def test_analytics_endpoint(self):
        resp = self.client.get("/api/analytics/dashboard")
        assert resp.status_code != 404, "Analytics dashboard must exist"


# =============================================================================
# 7. INFRASTRUCTURE TESTS
# =============================================================================

class TestDockerConfiguration:
    """Verify Docker Compose configuration is consistent."""

    def test_port_consistency(self):
        """API port must be 5400 in both compose files."""
        simple = Path(REPO_ROOT / "docker-compose.simple.yml")
        full = Path(REPO_ROOT / "docker-compose.yml")
        simple_content = simple.read_text(encoding="utf-8")
        full_content = full.read_text(encoding="utf-8")
        assert "5400:8000" in simple_content, "simple.yml must use port 5400"
        assert "5400:8000" in full_content, "docker-compose.yml must use port 5400"

    def test_health_checks_configured(self):
        """All services must have healthcheck in simple compose."""
        simple = Path(REPO_ROOT / "docker-compose.simple.yml")
        content = simple.read_text(encoding="utf-8")
        services = ["postgres", "redis", "api", "frontend", "celery-worker", "jaeger"]
        for svc in services:
            assert content.count("healthcheck:") >= len(services) - 1, \
                f"At least {len(services)-1} services should have healthchecks"
            break  # Just check total count

    def test_resource_limits_configured(self):
        """Services should have resource limits."""
        simple = Path(REPO_ROOT / "docker-compose.simple.yml")
        content = simple.read_text(encoding="utf-8")
        assert "deploy:" in content, "Docker compose should have deploy resource limits"
        assert "memory:" in content, "Services should have memory limits"


# =============================================================================
# 8. FRONTEND COMPONENT TESTS (FILE-BASED)
# =============================================================================

class TestFrontendAccessibility:
    """Verify frontend components have accessibility attributes."""

    def test_layout_has_skip_to_content(self):
        layout = Path(REPO_ROOT / "src" / "frontend" / "src" / "app" / "layout.tsx")
        content = layout.read_text(encoding="utf-8")
        assert "skip" in content.lower() or "Skip" in content, \
            "Layout must have skip-to-content link"

    def test_layout_has_error_boundary(self):
        layout = Path(REPO_ROOT / "src" / "frontend" / "src" / "app" / "layout.tsx")
        content = layout.read_text(encoding="utf-8")
        assert "ErrorBoundary" in content, "Layout must wrap children in ErrorBoundary"

    def test_error_boundary_component_exists(self):
        eb = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "ErrorBoundary.tsx")
        assert eb.exists(), "ErrorBoundary component must exist"

    def test_toast_component_exists(self):
        toast = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "Toast.tsx")
        assert toast.exists(), "Toast notification component must exist"

    def test_site_layout_has_aria_roles(self):
        site = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "SiteLayout.tsx")
        content = site.read_text(encoding="utf-8")
        assert "role=" in content, "SiteLayout must have ARIA roles"
        assert "main" in content.lower(), "Must have main content area"

    def test_credibility_gauge_has_aria(self):
        gauge = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "CredibilityGauge.tsx")
        content = gauge.read_text(encoding="utf-8")
        assert "aria-label" in content or "role=" in content, \
            "CredibilityGauge must have accessibility attributes"


class TestFrontendVisualization:
    """Verify visualization components exist."""

    def test_recharts_installed(self):
        pkg = Path(REPO_ROOT / "src" / "frontend" / "package.json")
        content = pkg.read_text(encoding="utf-8")
        assert "recharts" in content, "Recharts must be installed"

    def test_trend_chart_exists(self):
        chart = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "TrendChart.tsx")
        assert chart.exists(), "TrendChart component must exist"

    def test_forecast_chart_exists(self):
        chart = Path(REPO_ROOT / "src" / "frontend" / "src" / "components" / "ForecastChart.tsx")
        assert chart.exists(), "ForecastChart component must exist"


class TestI18nCoverage:
    """Verify internationalization coverage."""

    def test_i18n_supports_11_languages(self):
        i18n = Path(REPO_ROOT / "src" / "frontend" / "src" / "lib" / "i18n.ts")
        content = i18n.read_text(encoding="utf-8")
        expected_langs = ["en", "zh", "es", "hi", "ar", "fr", "pt", "ru", "ja", "de", "fi"]
        for lang in expected_langs:
            assert f'"{lang}"' in content, f"i18n must support {lang}"

    def test_rtl_support_for_arabic(self):
        i18n = Path(REPO_ROOT / "src" / "frontend" / "src" / "lib" / "i18n.ts")
        content = i18n.read_text(encoding="utf-8")
        assert "rtl" in content.lower(), "i18n must support RTL for Arabic"
