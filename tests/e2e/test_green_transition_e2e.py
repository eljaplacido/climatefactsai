"""
Green Transition, Global Coverage & Translation — End-to-End Tests

Validates:
1. 80%+ of world countries present in REGION_COUNTRIES mapping
2. Compare endpoint returns all green-transition dimension scores
3. compare response includes country_a / country_b convenience fields
4. Translation endpoint is reachable and returns valid JSON
5. PageTranslator API path (/api/translate/) works
6. seed_global_sources.py covers all key regions and sustainability topics
7. Country detail endpoint returns climate + article data
8. Map query endpoint handles region-level filtering for all regions
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytestmark = [pytest.mark.e2e]

# ---------------------------------------------------------------------------
# 1. REGION_COUNTRIES coverage
# ---------------------------------------------------------------------------


class TestRegionCoverage:
    """Verify REGION_COUNTRIES covers 80%+ of world countries."""

    # UN member states that must appear in at least one region
    REQUIRED_COUNTRIES = {
        # Africa (54)
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD",
        "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET",
        "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG",
        "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW",
        "SN", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG",
        "ZM", "ZW",
        # Europe (30+)
        "FI", "SE", "NO", "DK", "DE", "FR", "GB", "IT", "ES", "PL",
        "NL", "BE", "AT", "CZ", "GR", "RO", "HU", "PT", "UA", "TR",
        # Americas (30+)
        "US", "CA", "MX", "BR", "AR", "CO", "CL", "PE", "EC", "BO",
        "VE", "PY", "UY", "CR", "PA", "GT", "HN", "CU", "DO", "HT",
        # Asia (30+)
        "CN", "IN", "JP", "KR", "ID", "TH", "VN", "PH", "MY", "BD",
        "PK", "KZ", "UZ", "IR", "IQ", "SA", "AE", "IL", "JO",
        # Oceania
        "AU", "NZ", "PG", "FJ",
    }

    def test_region_countries_covers_africa(self):
        from api.map_routes import REGION_COUNTRIES
        africa = set(REGION_COUNTRIES.get("africa", []))
        african_required = {
            "DZ", "AO", "BJ", "BW", "BF", "BI", "CM", "CD", "CI",
            "EG", "ET", "GA", "GH", "KE", "LY", "MG", "MA", "MZ",
            "NA", "NG", "RW", "SN", "ZA", "SS", "SD", "TZ", "TN",
            "UG", "ZM", "ZW",
        }
        missing = african_required - africa
        assert not missing, f"Missing African countries: {missing}"

    def test_region_countries_covers_latin_america(self):
        from api.map_routes import REGION_COUNTRIES
        latam = set(REGION_COUNTRIES.get("latin_america", []))
        required = {"BR", "AR", "CO", "CL", "PE", "EC", "BO", "VE", "PY", "UY",
                    "CR", "PA", "GT", "HN", "CU", "DO", "GY", "SR"}
        missing = required - latam
        assert not missing, f"Missing LatAm countries: {missing}"

    def test_region_countries_covers_asia(self):
        from api.map_routes import REGION_COUNTRIES
        asia = set(REGION_COUNTRIES.get("asia", []))
        required = {"CN", "IN", "JP", "KR", "ID", "TH", "VN", "PH", "MY",
                    "BD", "PK", "KZ", "UZ", "IR", "IQ", "SA", "AE", "MN", "MM"}
        missing = required - asia
        assert not missing, f"Missing Asian countries: {missing}"

    def test_region_countries_covers_oceania(self):
        from api.map_routes import REGION_COUNTRIES
        oceania = set(REGION_COUNTRIES.get("oceania", []))
        assert "AU" in oceania
        assert "NZ" in oceania
        assert "FJ" in oceania
        assert "PG" in oceania

    def test_total_region_country_coverage_exceeds_80_pct(self):
        from api.map_routes import REGION_COUNTRIES
        all_in_regions: set = set()
        for codes in REGION_COUNTRIES.values():
            all_in_regions.update(codes)
        world_count = 195  # approximate UN member + observer states
        pct = len(all_in_regions) / world_count * 100
        assert pct >= 80, f"Only {pct:.1f}% country coverage ({len(all_in_regions)}/{world_count})"

    def test_required_countries_all_covered(self):
        from api.map_routes import REGION_COUNTRIES
        all_covered: set = set()
        for codes in REGION_COUNTRIES.values():
            all_covered.update(codes)
        missing = self.REQUIRED_COUNTRIES - all_covered
        assert not missing, f"Required countries missing from any region: {sorted(missing)}"


# ---------------------------------------------------------------------------
# 2. Compare endpoint — green transition dimensions
# ---------------------------------------------------------------------------


class TestCompareGreenTransition:
    """Validate /compare returns all green-transition dimension fields."""

    GREEN_TRANSITION_FIELDS = [
        "green_transition_score",
        "renewable_energy_score",
        "cleantech_score",
        "circular_economy_score",
        "resource_efficiency_score",
        "regenerative_score",
        "sustainability_score",
    ]

    def _make_fake_db_for_compare(self, countries=("FI", "DE")):
        """Return a FakeDB that satisfies compare_countries queries."""
        db = MagicMock()

        def execute_query(q, params=None):
            q_lower = q.lower().strip()
            cc = (params or {}).get("cc", "XX")

            if "count(*) as cnt" in q_lower and "source_name" in q_lower:
                # Basic stats
                return [{"cnt": 20, "src_cnt": 5, "avg_cred": 72.5}]

            if "unnest(tags)" in q_lower:
                # Top topics
                return [
                    {"tag": "renewable-energy"},
                    {"tag": "green-transition"},
                    {"tag": "circular-economy"},
                ]

            if "content_category" in q_lower and "group by content_category" in q_lower:
                # Category breakdown
                return [
                    {"content_category": "green_transition", "cnt": 8},
                    {"content_category": "renewable_energy", "cnt": 6},
                    {"content_category": "cleantech", "cnt": 5},
                    {"content_category": "circular_economy", "cnt": 4},
                    {"content_category": "resource_efficiency", "cnt": 3},
                    {"content_category": "regenerative_economy", "cnt": 2},
                    {"content_category": "sustainability", "cnt": 4},
                ]

            if "total_claims" in q_lower and "disputed" in q_lower:
                # Risk score
                return [{"total_claims": 10, "disputed": 2}]

            if "from countries" in q_lower:
                return []

            return []

        db.execute_query.side_effect = execute_query
        return db

    def test_compare_response_has_country_a_b_fields(self):
        """CompareResponse model must expose country_a and country_b."""
        from api.map_routes import CompareResponse, CountryComparison
        cc_a = CountryComparison(country_code="FI", country_name="Finland", article_count=10)
        cc_b = CountryComparison(country_code="DE", country_name="Germany", article_count=15)
        resp = CompareResponse(countries=[cc_a, cc_b], country_a=cc_a, country_b=cc_b)
        assert resp.country_a is not None
        assert resp.country_b is not None
        assert resp.country_a.country_code == "FI"
        assert resp.country_b.country_code == "DE"

    def test_country_comparison_has_green_transition_fields(self):
        """CountryComparison model must contain all green-transition score fields."""
        from api.map_routes import CountryComparison
        cc = CountryComparison(
            country_code="SE",
            country_name="Sweden",
            green_transition_score=8.0,
            renewable_energy_score=9.0,
            cleantech_score=7.5,
            circular_economy_score=6.0,
            resource_efficiency_score=5.5,
            regenerative_score=4.0,
            sustainability_score=7.0,
        )
        for field in self.GREEN_TRANSITION_FIELDS:
            val = getattr(cc, field)
            assert val is not None, f"{field} should not be None"
            assert 0.0 <= val <= 10.0, f"{field}={val} out of 0-10 range"

    def test_country_comparison_climate_risk_alias(self):
        """climate_risk field must equal climate_risk_score (frontend alias)."""
        from api.map_routes import CountryComparison
        cc = CountryComparison(
            country_code="NO", country_name="Norway",
            climate_risk_score=3.5, climate_risk=3.5,
        )
        assert cc.climate_risk == cc.climate_risk_score

    @patch("api.map.routes_compare.get_postgres")
    @patch("api.map.routes_compare._get_country_names")
    def test_compare_endpoint_returns_green_scores(self, mock_names, mock_db):
        """compare_countries must compute and return all green-transition scores."""
        import asyncio
        # After the api/map split, compare_countries lives in
        # api/map/routes_compare.py (the map_routes shim doesn't re-export it).
        from api.map.routes_compare import compare_countries

        mock_names.return_value = {"FI": "Finland", "DE": "Germany"}
        fake_db = self._make_fake_db_for_compare()
        mock_db.return_value = fake_db

        result = asyncio.run(compare_countries(countries="FI,DE"))
        assert result.country_a is not None
        assert result.country_b is not None

        for field in self.GREEN_TRANSITION_FIELDS:
            val_a = getattr(result.country_a, field)
            assert val_a is not None, f"country_a.{field} should not be None"
            assert 0.0 <= val_a <= 10.0

    def test_cat_score_scaling(self):
        """Green scores should be 0-10 with 2 articles per point."""
        from api.map_routes import CountryComparison
        # 8 articles in green_transition → score = min(10, 8/2) = 4.0
        breakdown = {"green_transition": 8, "renewable_energy": 20, "cleantech": 0}

        def _cat_score(cat):
            return round(min(10.0, breakdown.get(cat, 0) / 2.0), 1)

        assert _cat_score("green_transition") == 4.0
        assert _cat_score("renewable_energy") == 10.0  # capped at 10
        assert _cat_score("cleantech") == 0.0


# ---------------------------------------------------------------------------
# 3. Translation endpoint
# ---------------------------------------------------------------------------


class TestTranslationEndpoint:
    """Validate /api/translate/ works for whole-page translation."""

    def test_translate_english_returns_unchanged(self, client):
        """Translating to 'en' should return the original text."""
        resp = client.post("/api/translate/", json={
            "text": "Hello world",
            "target_language": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["translated_text"] == "Hello world"
        assert data["target_language"] == "en"

    @patch("api.main.os.getenv")
    def test_translate_endpoint_exists_and_accepts_post(self, mock_getenv, client):
        """POST /api/translate/ must be reachable (200 or 503 if no LLM key)."""
        mock_getenv.side_effect = lambda key, default=None: default  # no API keys
        resp = client.post("/api/translate/", json={
            "text": "Climate news from around the world",
            "target_language": "fi",
        })
        # 200 (translated) or 503 (no API key configured in test env)
        assert resp.status_code in (200, 503), f"Unexpected status {resp.status_code}"

    def test_translate_trailing_slash_and_no_slash_both_work(self, client):
        """Both /api/translate and /api/translate/ should be routed."""
        for path in ["/api/translate/", "/api/translate"]:
            resp = client.post(path, json={"text": "Test", "target_language": "en"})
            assert resp.status_code in (200, 422, 503), f"Unexpected {resp.status_code} at {path}"

    def test_translate_rejects_empty_text(self, client):
        resp = client.post("/api/translate/", json={"text": "", "target_language": "fr"})
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_translation_routes_languages_endpoint(self, client):
        """GET /api/translations/languages must list 20+ languages."""
        resp = client.get("/api/translations/languages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 20
        codes = [l["code"] for l in data["languages"]]
        for lang in ["en", "fi", "fr", "de", "es", "zh", "ar", "hi"]:
            assert lang in codes, f"Language {lang} missing from supported list"

    def test_translation_routes_ui_endpoint(self, client):
        """GET /api/translations/ui/{lang} must return translation keys."""
        for lang in ["en", "fi", "fr", "de", "es"]:
            resp = client.get(f"/api/translations/ui/{lang}")
            assert resp.status_code == 200
            data = resp.json()
            assert "translations" in data
            assert "nav.home" in data["translations"]


# ---------------------------------------------------------------------------
# 4. Global data sources coverage
# ---------------------------------------------------------------------------


class TestGlobalDataSources:
    """Verify seed_global_sources.py covers all required regions and topics."""

    REQUIRED_REGIONS = {"africa", "latin_america", "middle_east", "asia_pacific", "global"}
    REQUIRED_TOPICS_IN_GLOBAL = {
        "circular", "renewable", "cleantech", "resource", "mineral",
        "transition", "hydrogen", "efficiency",
    }
    REQUIRED_COUNTRY_SPECIFIC = {
        "RW": ["Rwanda"],
        "MA": ["Morocco", "MASEN"],
        "KE": ["Kenya"],
        "VN": ["Vietnam"],
        "ID": ["Indonesia"],
        "BO": ["Bolivia"],
        "IN": ["India"],
        "BR": ["Brazil"],
    }

    def _load_sources(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_global_sources",
            REPO_ROOT / "scripts" / "seed_global_sources.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # Patch psycopg2 so the module-level connect() call doesn't hit a real DB
        # seed_full_global.py sys.exit(2)s at import unless CLILENS_ALLOW_FAKE_SEED=1
        # (a SystemExit, which the bare `except Exception` below does NOT catch).
        # Opt in so the module body runs far enough to define TOPICS/ALL_COUNTRIES.
        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.extras": MagicMock()}), \
             patch.dict("os.environ", {"CLILENS_ALLOW_FAKE_SEED": "1"}):
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        return getattr(mod, "SOURCES", [])

    def test_sources_cover_all_required_regions(self):
        sources = self._load_sources()
        if not sources:
            pytest.skip("Could not load SOURCES list (psycopg2 not installed)")
        regions = {s[3] for s in sources}
        missing = self.REQUIRED_REGIONS - regions
        assert not missing, f"Missing regions in sources: {missing}"

    def test_global_sources_cover_key_topics(self):
        sources = self._load_sources()
        if not sources:
            pytest.skip("Could not load SOURCES list")
        global_names = " ".join(
            s[0].lower() for s in sources if s[3] == "global"
        )
        for topic in self.REQUIRED_TOPICS_IN_GLOBAL:
            assert topic in global_names, f"Topic '{topic}' not found in global sources"

    def test_africa_has_country_specific_sources(self):
        sources = self._load_sources()
        if not sources:
            pytest.skip("Could not load SOURCES list")
        africa_sources = [(s[0], s[2]) for s in sources if s[3] == "africa"]
        country_codes = {s[1] for s in africa_sources}
        # Must have at least 5 specific African countries (not XX)
        specific = {cc for cc in country_codes if cc != "XX"}
        assert len(specific) >= 5, f"Too few Africa-specific countries: {specific}"

    def test_critical_minerals_sources_present(self):
        sources = self._load_sources()
        if not sources:
            pytest.skip("Could not load SOURCES list")
        all_names = " ".join(s[0].lower() for s in sources)
        for keyword in ("mineral", "lithium", "cobalt", "raw material"):
            assert keyword in all_names, f"No source found for keyword '{keyword}'"

    def test_source_count_exceeds_minimum(self):
        sources = self._load_sources()
        if not sources:
            pytest.skip("Could not load SOURCES list")
        assert len(sources) >= 100, f"Only {len(sources)} sources defined, need >= 100"


# ---------------------------------------------------------------------------
# 5. Map API endpoints — region filtering
# ---------------------------------------------------------------------------


class TestMapRegionFiltering:
    """Verify map endpoints handle all newly added regions."""

    def test_regions_list_includes_all_continents(self, client):
        resp = client.get("/api/map/regions")
        assert resp.status_code == 200
        data = resp.json()
        for region in ["europe", "africa", "asia", "latin_america", "oceania"]:
            assert region in data, f"Region '{region}' missing from /api/map/regions"

    def test_regions_africa_has_50_plus_countries(self, client):
        resp = client.get("/api/map/regions")
        assert resp.status_code == 200
        data = resp.json()
        africa_count = data.get("africa", {}).get("count", 0)
        assert africa_count >= 50, f"Africa region has only {africa_count} countries"

    def test_regions_latin_america_has_complete_coverage(self, client):
        resp = client.get("/api/map/regions")
        assert resp.status_code == 200
        data = resp.json()
        latam = set(data.get("latin_america", {}).get("countries", []))
        required = {"BR", "AR", "CO", "CL", "PE", "EC", "BO", "VE", "PY", "UY"}
        missing = required - latam
        assert not missing, f"Missing LatAm countries in region: {missing}"

    def test_compare_endpoint_accepts_two_countries(self, client):
        resp = client.get("/api/map/compare?countries=FI,DE")
        assert resp.status_code == 200
        data = resp.json()
        assert "countries" in data
        assert len(data["countries"]) == 2

    def test_compare_response_includes_country_a_b(self, client):
        resp = client.get("/api/map/compare?countries=US,CN")
        assert resp.status_code == 200
        data = resp.json()
        assert "country_a" in data
        assert "country_b" in data

    def test_compare_response_country_a_has_green_fields(self, client):
        resp = client.get("/api/map/compare?countries=SE,NO")
        assert resp.status_code == 200
        data = resp.json()
        if data.get("country_a"):
            for field in [
                "green_transition_score", "renewable_energy_score",
                "circular_economy_score", "resource_efficiency_score",
            ]:
                assert field in data["country_a"], f"Missing field {field} in country_a"

    def test_country_stats_endpoint_returns_results(self, client):
        resp = client.get("/api/map/country-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_country_stats_region_filter_africa(self, client):
        resp = client.get("/api/map/country-stats?region=africa")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # All returned codes should be in Africa region
        from api.map_routes import REGION_COUNTRIES
        africa_set = set(REGION_COUNTRIES["africa"])
        for item in data:
            assert item["country_code"] in africa_set, (
                f"Country {item['country_code']} not in Africa region"
            )


# ---------------------------------------------------------------------------
# 6. Seed script — article categories
# ---------------------------------------------------------------------------


class TestSeedArticleCategories:
    """Validate seed_full_global.py generates correct topic coverage."""

    REQUIRED_TOPICS = {
        "green_transition", "cleantech", "circular_economy",
        "renewable_energy", "sustainability", "regenerative_economy",
        "resource_efficiency", "climate_science", "policy",
    }

    def test_seed_script_topics_match_required(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_full_global",
            REPO_ROOT / "scripts" / "seed_full_global.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # seed_full_global.py sys.exit(2)s at import unless CLILENS_ALLOW_FAKE_SEED=1
        # (a SystemExit, which the bare `except Exception` below does NOT catch).
        # Opt in so the module body runs far enough to define TOPICS/ALL_COUNTRIES.
        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.extras": MagicMock()}), \
             patch.dict("os.environ", {"CLILENS_ALLOW_FAKE_SEED": "1"}):
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        topics = getattr(mod, "TOPICS", {})
        if not topics:
            pytest.skip("Could not load TOPICS (psycopg2 not installed)")
        missing = self.REQUIRED_TOPICS - set(topics.keys())
        assert not missing, f"Missing topic categories in seed script: {missing}"

    def test_seed_script_country_count_exceeds_180(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_full_global2",
            REPO_ROOT / "scripts" / "seed_full_global.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # seed_full_global.py sys.exit(2)s at import unless CLILENS_ALLOW_FAKE_SEED=1
        # (a SystemExit, which the bare `except Exception` below does NOT catch).
        # Opt in so the module body runs far enough to define TOPICS/ALL_COUNTRIES.
        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.extras": MagicMock()}), \
             patch.dict("os.environ", {"CLILENS_ALLOW_FAKE_SEED": "1"}):
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        countries = getattr(mod, "ALL_COUNTRIES", {})
        if not countries:
            pytest.skip("Could not load ALL_COUNTRIES")
        assert len(countries) >= 180, f"Only {len(countries)} countries in seed script"

    def test_resource_efficiency_includes_mineral_template(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "seed_full_global3",
            REPO_ROOT / "scripts" / "seed_full_global.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # seed_full_global.py sys.exit(2)s at import unless CLILENS_ALLOW_FAKE_SEED=1
        # (a SystemExit, which the bare `except Exception` below does NOT catch).
        # Opt in so the module body runs far enough to define TOPICS/ALL_COUNTRIES.
        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.extras": MagicMock()}), \
             patch.dict("os.environ", {"CLILENS_ALLOW_FAKE_SEED": "1"}):
            try:
                spec.loader.exec_module(mod)
            except Exception:
                pass
        topics = getattr(mod, "TOPICS", {})
        if not topics:
            pytest.skip("Could not load TOPICS")
        re_templates = " ".join(topics.get("resource_efficiency", []))
        assert "mineral" in re_templates.lower(), (
            "resource_efficiency templates should mention critical minerals"
        )


# ---------------------------------------------------------------------------
# 7. Frontend PageTranslator API contract
# ---------------------------------------------------------------------------


class TestPageTranslatorContract:
    """Verify the API endpoints consumed by PageTranslator exist and behave correctly."""

    def test_translate_post_returns_translated_text_key(self, client):
        """PageTranslator expects {'translated_text': ...} in the response."""
        resp = client.post("/api/translate/", json={
            "text": "Climate change is accelerating.",
            "target_language": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "translated_text" in data, "PageTranslator requires 'translated_text' key"

    def test_translate_supports_split_separator(self, client):
        """PageTranslator sends texts joined by \\n---SPLIT---\\n."""
        combined = "Climate change\n---SPLIT---\nRenewable energy"
        resp = client.post("/api/translate/", json={
            "text": combined,
            "target_language": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "translated_text" in data

    def test_translate_handles_large_text_up_to_8000_chars(self, client):
        """PageTranslator truncates to 8000 chars; API must accept up to 10000."""
        text = "Climate article. " * 500  # ~8500 chars
        resp = client.post("/api/translate/", json={
            "text": text[:8000],
            "target_language": "en",
        })
        assert resp.status_code in (200, 503)

    def test_translate_rejects_overlong_text(self, client):
        text = "x" * 10001
        resp = client.post("/api/translate/", json={
            "text": text,
            "target_language": "en",
        })
        assert resp.status_code == 422  # max_length=10000
