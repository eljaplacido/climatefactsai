"""Unit tests for /api/semantic/* — Stage 4 / M5 semantic layer.

Mocks the DB at module-level so the route handlers exercise the
shape transformation + bridge-finding logic without needing a real
knowledge_graph schema. The actual LLM call (in /explain) is also
mocked — the test verifies the bridge-construction + fallback paths,
not the LLM quality.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class _StubDB:
    """Minimal DB stub — returns whatever rows we hand it."""
    def __init__(self, query_responses=None):
        # query_responses: list of (predicate_fn, rows) or list of rows
        self.responses = query_responses or []
        self.call_log: list[tuple[str, dict]] = []

    def execute_query(self, sql, params=None):
        self.call_log.append((sql, params or {}))
        # Use a simple FIFO if list of rows; or pick by predicate
        if not self.responses:
            return []
        nxt = self.responses.pop(0)
        if callable(nxt):
            return nxt(sql, params or {})
        return nxt


class TestEntityProfile:
    def test_entity_404_when_missing(self):
        stub = _StubDB([[]])  # entities query returns nothing
        with patch("api.semantic_routes.get_postgres", return_value=stub):
            r = client.get("/api/semantic/entity/nonexistent-uuid")
        assert r.status_code == 404

    def test_entity_returns_full_profile(self):
        # Three queries in order: profile, relationships, articles
        stub = _StubDB([
            [{"entity_id": "e1", "entity_name": "COP30", "entity_type": "EVENT",
              "description": "Conference of the Parties", "article_count": 25,
              "created_at": "2026-01-01"}],
            [{"relationship_id": "r1",
              "src_id": "e1", "src_name": "COP30", "src_type": "EVENT",
              "tgt_id": "e2", "tgt_name": "Amazon", "tgt_type": "LOCATION",
              "relationship_type": "DISCUSSES",
              "strength": 0.6, "confidence": 0.85,
              "evidence_text": "COP30 discusses Amazon protection"}],
            [{"article_id": "a1", "title": "After Belém: COP30 legacy",
              "source_name": "InfoAmazonia", "country_code": "BR",
              "published_date": "2026-05-15", "overall_credibility": "HIGH",
              "mention_count": 3, "salience": 0.7}],
        ])
        with patch("api.semantic_routes.get_postgres", return_value=stub):
            r = client.get("/api/semantic/entity/e1")
        assert r.status_code == 200
        body = r.json()
        assert body["entity"]["name"] == "COP30"
        assert body["entity"]["article_count"] == 25
        assert len(body["relationships"]) == 1
        assert body["relationships"][0]["source"]["name"] == "COP30"
        assert body["relationships"][0]["target"]["name"] == "Amazon"
        assert len(body["articles"]) == 1
        # Neighbors derived from relationships — should include Amazon, not COP30
        neighbor_names = {n["name"] for n in body["neighbors"]}
        assert "Amazon" in neighbor_names
        assert "COP30" not in neighbor_names


class TestEntitySearch:
    def test_search_returns_results(self):
        stub = _StubDB([
            [{"entity_id": "e1", "entity_name": "COP30",
              "entity_type": "EVENT", "description": "", "article_count": 25}],
        ])
        with patch("api.semantic_routes.get_postgres", return_value=stub):
            r = client.get("/api/semantic/entities/search?q=COP")
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "COP"
        assert len(body["results"]) == 1
        assert body["results"][0]["name"] == "COP30"

    def test_search_validates_min_length(self):
        # q must be >= 2 chars per Query validation
        r = client.get("/api/semantic/entities/search?q=a")
        assert r.status_code == 422


class TestExplain:
    def test_explain_requires_input(self):
        r = client.post("/api/semantic/explain", json={})
        assert r.status_code == 400

    def test_explain_articles_need_at_least_2(self):
        r = client.post("/api/semantic/explain", json={"article_ids": ["one"]})
        assert r.status_code == 400

    def test_explain_with_no_bridges_returns_explainer(self):
        stub = _StubDB([
            # titles
            [{"article_id": "a1", "title": "Article 1"},
             {"article_id": "a2", "title": "Article 2"}],
            # shared entities — empty
            [],
        ])
        with patch("api.semantic_routes.get_postgres", return_value=stub):
            r = client.post("/api/semantic/explain",
                            json={"article_ids": ["a1", "a2"]})
        assert r.status_code == 200
        body = r.json()
        assert body["bridges"] == []
        assert body["llm_provider"] == "none"
        assert "no shared" in body["explanation"].lower()

    def test_explain_with_bridges_calls_llm(self):
        # 2 articles share entity "COP30" — LLM mocked to return text
        stub = _StubDB([
            [{"article_id": "a1", "title": "COP30 Amazon"},
             {"article_id": "a2", "title": "COP30 Indigenous"}],
            [{"entity_id": "e1", "entity_name": "COP30", "entity_type": "EVENT",
              "description": "Conference", "shared_count": 2}],
        ])
        # Mock the LLM call
        async def _fake_llm(self, sys_p, usr_p, max_tokens=400):
            return ("These two articles both discuss COP30 outcomes in the Amazon.",
                    "local-gx10", "qwen2.5:7b-instruct")
        with patch("api.semantic_routes.get_postgres", return_value=stub), \
             patch("app.domains.content.article_enrichment_service.ArticleEnrichmentService._call_llm",
                   new=_fake_llm):
            r = client.post("/api/semantic/explain",
                            json={"article_ids": ["a1", "a2"]})
        assert r.status_code == 200
        body = r.json()
        assert body["llm_provider"] == "local-gx10"
        assert "COP30" in body["explanation"]
        assert len(body["bridges"]) == 1
        assert body["bridges"][0]["name"] == "COP30"
