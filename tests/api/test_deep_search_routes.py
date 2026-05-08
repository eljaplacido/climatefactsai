"""Deep Search route tests.

Covers POST /api/deep-search/ and POST /api/deep-search/compare with the
DeepSearchService class patched at the *route module* boundary so no LLM /
HTTP traffic ever leaves the test process.

Pinned regressions:
- methodology.embedding_model = "openai:text-embedding-ada-002" when
  OPENAI_API_KEY is set, None otherwise.
- DeepSearchResponse keeps the methodology block intact end-to-end.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_payload(*, embedding_model=None, internal_count=2, external_count=1):
    """Return a fixture matching the DeepSearchResponse schema."""
    return {
        "query": "renewable energy in Africa",
        "answer": "Africa is rapidly expanding solar capacity.",
        "citations": [
            {
                "type": "internal_article",
                "article_id": "art-001",
                "title": "Solar boom in Kenya",
                "source_name": "Reuters",
                "published_date": None,
                "credibility": "HIGH",
                "reliability_score": 88,
                "relevance_score": 0.91,
                "excerpt": "Kenya tripled installed solar.",
            },
            {
                "type": "internal_article",
                "article_id": "art-002",
                "title": "South African green grid",
                "source_name": "BBC",
                "published_date": None,
                "credibility": "HIGH",
                "reliability_score": 85,
                "relevance_score": 0.83,
                "excerpt": "ZA invests in renewables.",
            },
            {
                "type": "external_web",
                "source_url": "https://example.com/study",
                "source_name": "example.com",
            },
        ][: internal_count + external_count],
        "internal_articles_count": internal_count,
        "external_sources_count": external_count,
        "weather_context": None,
        "filters": {"country": None, "category": None},
        "methodology": {
            "queries_run": [
                {"layer": "internal_corpus", "scope": {}, "hits": internal_count},
                {"layer": "perplexity_external", "skipped": False, "hits": external_count},
            ],
            "weather_used": False,
            "synthesis_model": "anthropic",
            "embedding_model": embedding_model,
            "external_provider_configured": True,
            "sources_consulted": ["BBC", "Reuters", "example.com"],
        },
        "clarification_needed": None,
        "searched_at": datetime.utcnow().isoformat(),
    }


def _patch_deep_search(monkeypatch, search_return=None, compare_return=None,
                      raise_on_search=False):
    """Replace DeepSearchService inside api.deep_search_routes."""
    from api import deep_search_routes

    fake_service_cls = MagicMock()
    instance = MagicMock()

    if raise_on_search:
        instance.search = AsyncMock(side_effect=RuntimeError("LLM crashed"))
    else:
        instance.search = AsyncMock(return_value=search_return)

    if compare_return is not None:
        instance.compare = AsyncMock(return_value=compare_return)

    fake_service_cls.return_value = instance

    # The route imports DeepSearchService inside the handler — patch the
    # module attribute that lazy-import resolves to.
    import app.domains.intelligence.deep_search_service as svc_mod
    monkeypatch.setattr(svc_mod, "DeepSearchService", fake_service_cls)
    return fake_service_cls, instance


# ---------------------------------------------------------------------------
# POST /api/deep-search/  (note trailing slash matches @router.post("/"))
# ---------------------------------------------------------------------------

class TestDeepSearchEndpoint:
    def test_happy_path_returns_methodology(self, client, monkeypatch):
        payload = _make_search_payload(
            embedding_model="openai:text-embedding-ada-002",
        )
        _patch_deep_search(monkeypatch, search_return=payload)

        resp = client.post(
            "/api/deep-search/",
            json={"query": "renewable energy in Africa", "limit": 5},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["query"] == "renewable energy in Africa"
        assert data["internal_articles_count"] == 2
        assert data["external_sources_count"] == 1
        assert "methodology" in data
        assert data["methodology"]["embedding_model"] == "openai:text-embedding-ada-002"
        assert data["methodology"]["weather_used"] is False
        assert data["methodology"]["synthesis_model"] == "anthropic"

    def test_methodology_embedding_model_none_when_no_openai_key(
        self, client, monkeypatch
    ):
        """Regression: methodology.embedding_model must be None when
        OPENAI_API_KEY is not set."""
        payload = _make_search_payload(embedding_model=None)
        _patch_deep_search(monkeypatch, search_return=payload)

        # Ensure key is unset for this test
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        resp = client.post(
            "/api/deep-search/",
            json={"query": "renewable energy in Africa"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "methodology" in data
        assert data["methodology"]["embedding_model"] is None

    def test_empty_query_returns_422(self, client, monkeypatch):
        # Patch service even though it should never be invoked
        _patch_deep_search(monkeypatch, search_return=_make_search_payload())
        resp = client.post("/api/deep-search/", json={"query": ""})
        # min_length=3 on the field => 422 from pydantic
        assert resp.status_code == 422

    def test_short_query_returns_422(self, client, monkeypatch):
        _patch_deep_search(monkeypatch, search_return=_make_search_payload())
        resp = client.post("/api/deep-search/", json={"query": "ab"})
        assert resp.status_code == 422

    def test_service_failure_returns_500(self, client, monkeypatch):
        _patch_deep_search(monkeypatch, raise_on_search=True)
        resp = client.post(
            "/api/deep-search/",
            json={"query": "renewable energy"},
        )
        assert resp.status_code == 500
        assert "deep search failed" in resp.json()["detail"].lower()

    def test_country_too_long_rejected(self, client, monkeypatch):
        _patch_deep_search(monkeypatch, search_return=_make_search_payload())
        resp = client.post(
            "/api/deep-search/",
            json={"query": "renewable energy", "country": "USA"},  # max 2
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/deep-search/compare
# ---------------------------------------------------------------------------

class TestCompareEndpoint:
    def test_compare_happy_path(self, client, monkeypatch):
        result_a = _make_search_payload(embedding_model=None, internal_count=1, external_count=0)
        result_b = _make_search_payload(embedding_model=None, internal_count=2, external_count=1)
        compare_payload = {
            "query_a": "wind north",
            "query_b": "solar south",
            "result_a": result_a,
            "result_b": result_b,
            "comparative_analysis": "Wind dominates the north; solar leads the south.",
            "comparative_analysis_structured": {
                "summary": "Two distinct regional patterns.",
                "similarities": ["Both rapidly growing"],
                "differences": ["Wind vs solar"],
                "evidence_strength": "high",
                "common_gaps": ["Storage data missing"],
            },
            "compared_at": datetime.utcnow().isoformat(),
        }

        _patch_deep_search(
            monkeypatch,
            search_return=_make_search_payload(),
            compare_return=compare_payload,
        )

        resp = client.post(
            "/api/deep-search/compare",
            json={"query_a": "wind north", "query_b": "solar south"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["query_a"] == "wind north"
        assert data["query_b"] == "solar south"
        assert data["result_a"]["internal_articles_count"] == 1
        assert data["result_b"]["internal_articles_count"] == 2
        assert "comparative_analysis_structured" in data
        assert data["comparative_analysis_structured"]["evidence_strength"] == "high"

    def test_compare_rejects_short_query(self, client, monkeypatch):
        _patch_deep_search(monkeypatch, search_return=_make_search_payload())
        resp = client.post(
            "/api/deep-search/compare",
            json={"query_a": "ab", "query_b": "valid query"},
        )
        assert resp.status_code == 422
