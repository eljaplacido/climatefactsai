"""
End-to-end tests for Translation API, i18n, Benchmark/Audit, and Source Evaluation.

Covers:
- Translation languages listing
- UI translations for 10+ languages
- Article translation retrieval
- Translation coverage stats
- Scientific reference standards listing
- Article audit trail generation
- Source evaluation reports
- Platform KPI benchmarking
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
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


class BenchmarkFakeDB:
    """FakeDB with article, claims, fact_checks, and source_profiles data."""

    def __init__(self):
        self.now = datetime.utcnow()

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        params = params or {}
        nq = " ".join(query.split()).lower()

        # Article detail for audit trail
        if "from articles a" in nq and "article_id" in nq and "left join source_profiles" in nq:
            return [{
                "article_id": params.get("aid", "test-1"),
                "title": "Test Climate Article",
                "source_name": "IPCC",
                "reliability_score": 92,
                "overall_credibility": "HIGH",
                "claims_status": "completed",
                "claims_count": 3,
                "verified_claims_count": 2,
                "created_at": self.now,
                "content_relevance_score": 0.91,
                "source_credibility_score": 95,
                "claims_error_message": None,
                "source_profile_score": 97,
                "editorial_standards": "rigorous",
                "fact_check_record": "excellent",
                "transparency_level": "high",
                "false_claim_rate": 0.017,
                "tags": ["climate", "temperature"],
            }]

        # Fact checks for audit trail
        if "from claims c" in nq and "join fact_checks" in nq:
            return [
                {"verification_status": "VERIFIED", "confidence_score": 0.94,
                 "justification": "Confirmed by NASA satellite data", "claim_text": "Arctic warming at 2x global rate",
                 "claim_category": "scientific_causal"},
                {"verification_status": "PARTIALLY_VERIFIED", "confidence_score": 0.72,
                 "justification": "Figure within range but high-end estimate", "claim_text": "Sea level rise 1m by 2100",
                 "claim_category": "predictive"},
            ]

        # Source profile lookup
        if "from source_profiles" in nq:
            return [{
                "source_name": params.get("name", "IPCC"),
                "credibility_score": 97,
                "editorial_standards": "rigorous",
                "fact_check_record": "excellent",
                "transparency_level": "high",
                "false_claim_rate": 0.017,
            }]

        # Article stats for source eval
        if "count(*) as total_articles" in nq and "avg(reliability_score)" in nq:
            return [{"total_articles": 15, "avg_reliability": 93.5, "high_count": 12, "low_count": 0}]

        # Platform KPIs - article stats
        if "count(*) as total" in nq and "count(distinct country_code)" in nq:
            return [{"total": 666, "scored": 120, "avg_reliability": 83.5, "countries": 56, "sources": 45}]

        # Platform KPIs - claim stats
        if "total_claims" in nq and "avg(fc.confidence_score)" in nq:
            return [{"total_claims": 314, "verified": 200, "unverified": 30, "avg_confidence": 0.87}]

        # Translation queries
        if "from article_translations" in nq and "to_language" in nq and "count" in nq:
            return [
                {"to_language": "en", "translated_count": 50, "avg_confidence": 0.95},
                {"to_language": "fi", "translated_count": 30, "avg_confidence": 0.92},
            ]

        if "count(*) as cnt from articles" in nq:
            return [{"cnt": 666}]

        if "from article_translations t" in nq:
            if params.get("lang"):
                return [{"article_id": "test-1", "from_language": "en", "to_language": "fi",
                         "translated_title": "Testi ilmastoartikkeli", "translated_summary": "Yhteenveto",
                         "translation_confidence": 0.93, "translation_service": "deepl",
                         "translated_at": self.now}]
            return []

        return []


@pytest.fixture
def bench_client():
    db = BenchmarkFakeDB()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with patch("api.benchmark_routes.get_postgres", return_value=db), \
         patch("api.translation_routes.get_postgres", return_value=db):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


# ============================================================================
# Translation API Tests
# ============================================================================

class TestTranslationAPI:
    def test_list_supported_languages(self, bench_client):
        r = bench_client.get("/api/translations/languages")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 10
        codes = [l["code"] for l in data["languages"]]
        # Must include top 10 languages
        for required in ["en", "zh", "es", "hi", "ar", "fr", "pt", "ru", "ja", "de"]:
            assert required in codes, f"Missing required language: {required}"

    def test_get_english_ui_translations(self, bench_client):
        r = bench_client.get("/api/translations/ui/en")
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "en"
        assert "nav.home" in data["translations"]
        assert "nav.map" in data["translations"]
        assert data["rtl"] is False

    def test_get_finnish_ui_translations(self, bench_client):
        r = bench_client.get("/api/translations/ui/fi")
        assert r.status_code == 200
        data = r.json()
        assert data["translations"]["nav.home"] == "Uutiset"

    def test_get_arabic_rtl(self, bench_client):
        r = bench_client.get("/api/translations/ui/ar")
        assert r.status_code == 200
        assert r.json()["rtl"] is True

    def test_get_chinese_translations(self, bench_client):
        r = bench_client.get("/api/translations/ui/zh")
        assert r.status_code == 200
        data = r.json()
        assert "nav.home" in data["translations"]

    def test_fallback_for_unknown_language(self, bench_client):
        r = bench_client.get("/api/translations/ui/xx")
        assert r.status_code == 200
        data = r.json()
        assert data["is_fallback"] is True

    def test_article_translation_with_language(self, bench_client):
        r = bench_client.get("/api/translations/article/test-1", params={"language": "fi"})
        assert r.status_code == 200
        data = r.json()
        assert data["article_id"] == "test-1"

    def test_translation_coverage(self, bench_client):
        r = bench_client.get("/api/translations/coverage")
        assert r.status_code == 200
        data = r.json()
        assert "coverage" in data
        assert data["supported_languages"] >= 10


# ============================================================================
# Benchmark & Audit Tests
# ============================================================================

class TestBenchmarkAPI:
    def test_list_reference_standards(self, bench_client):
        r = bench_client.get("/api/benchmarks/standards")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 10
        names = [s["name"] for s in data["standards"]]
        assert any("IPCC" in n for n in names)
        assert any("WMO" in n for n in names)
        assert any("NASA" in n for n in names)

    def test_article_audit_trail(self, bench_client):
        r = bench_client.get("/api/benchmarks/article/test-1/audit-trail")
        assert r.status_code == 200
        data = r.json()
        assert data["article_id"] == "test-1"
        assert len(data["audit_trail"]) >= 3
        # Should have ingestion, source assessment, claims, fact-checks, scoring
        actions = [step["action"] for step in data["audit_trail"]]
        assert any("ingested" in a.lower() for a in actions)
        assert any("credibility" in a.lower() for a in actions)
        assert any("reliability" in a.lower() for a in actions)

    def test_audit_trail_has_benchmarks(self, bench_client):
        r = bench_client.get("/api/benchmarks/article/test-1/audit-trail")
        data = r.json()
        assert "benchmarks_applicable" in data
        assert len(data["benchmarks_applicable"]) > 0

    def test_source_evaluation(self, bench_client):
        r = bench_client.get("/api/benchmarks/source/IPCC/evaluation")
        assert r.status_code == 200
        data = r.json()
        assert data["source_name"] == "IPCC"
        assert data["overall_score"] > 0
        assert len(data["strengths"]) > 0
        assert "confidence_explanation" in data
        assert "recommendation" in data

    def test_source_evaluation_explains_scoring(self, bench_client):
        r = bench_client.get("/api/benchmarks/source/IPCC/evaluation")
        data = r.json()
        # Must explain WHY the score was given
        assert "editorial" in data["confidence_explanation"].lower() or "articles" in data["confidence_explanation"].lower()
        assert data["benchmarks_used"] and len(data["benchmarks_used"]) > 0

    def test_platform_kpis(self, bench_client):
        r = bench_client.get("/api/benchmarks/platform-kpis")
        assert r.status_code == 200
        data = r.json()
        assert len(data["kpis"]) >= 6
        # Each KPI must have a benchmark reference
        for kpi in data["kpis"]:
            assert "benchmark" in kpi, f"KPI '{kpi['metric']}' missing benchmark"
        assert len(data["reference_standards"]) == 10

    def test_platform_kpis_values(self, bench_client):
        r = bench_client.get("/api/benchmarks/platform-kpis")
        data = r.json()
        metrics = {k["metric"]: k for k in data["kpis"]}
        assert metrics["Total Articles Ingested"]["value"] > 0
        assert metrics["Country Coverage"]["value"] > 0
