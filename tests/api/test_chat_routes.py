"""Chat route tests — POST /api/chat with view_context hydration.

The system prompt that the LLM receives must include hydrated content
from the view_context the frontend sends. We patch
`get_llm_client` so we can capture the messages without making a network
call, and assert on the system prompt the chat route built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeChatChain:
    """Captures the prompts passed to llm_chat_with_fallback (the chain the chat
    route uses since the 2026-05-28 fallback refactor) and returns a canned
    (answer, provider, model) tuple.

    Exposes ``.calls[i]["messages"]`` as ``[{system}, {user}]`` so the existing
    system-prompt assertions keep working without change."""

    def __init__(self, content: str = "Hydrated answer."):
        self.calls: List[Dict[str, Any]] = []
        self.content = content

    def __call__(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        })
        return (self.content, "fake-provider", "fake-model")


def _stub_llm(monkeypatch, fake_client: Optional["_FakeChatChain"] = None):
    """Patch llm_chat_with_fallback so chat tests capture the prompts without a
    network call. (Was get_llm_client until the route moved to the fallback
    chain in the 2026-05-28 refactor — patching get_llm_client no longer
    intercepts the answer path, which silently broke these tests.)"""
    fake_client = fake_client or _FakeChatChain()

    import app.domains.intelligence.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "llm_chat_with_fallback", fake_client)
    return fake_client


def _make_chat_db(article_row=None, country_stats=None, url_analysis_row=None):
    """Build a fake DB stub keyed by query substring."""
    db = MagicMock()
    now = datetime.utcnow()

    article_row = article_row or {
        "article_id": "art-42",
        "title": "Greenland Ice Sheet Loss Accelerates",
        "source_name": "Nature",
        "country_code": "GL",
        "overall_credibility": "HIGH",
        "content_category": "climate_impacts",
        "claims_status": "completed",
        "insight_summary": "Mass loss has tripled since 2000.",
        "body_preview": "New satellite measurements show ice loss outpacing models.",
    }
    country_stats = country_stats or {
        "country_code": "FI",
        "article_count": 42,
        "source_count": 7,
        "high_cred_articles": 19,
        "latest_published": now,
    }
    url_analysis_row = url_analysis_row or {
        "analysis_id": "ua-1",
        "submitted_url": "https://example.com/x",
        "source_name": "Example",
        "source_domain": "example.com",
        "title": "X article",
        "status": "completed",
        "reliability_score": 72,
        "overall_credibility": "MEDIUM",
        "extracted_claims": [{"claim_text": "Solar grew 35%"}],
    }

    def _execute(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()

        # _hydrate_view_context article lookup
        if "from articles where article_id" in q:
            return [article_row] if params.get("id") else []

        # _hydrate_view_context country aggregate lookup
        if "count(*) as article_count" in q and "where country_code" in q:
            return [country_stats]

        # _hydrate_view_context URL analysis lookup
        if "from url_analyses where analysis_id" in q:
            return [url_analysis_row] if params.get("id") else []

        # _build_multi_article_context (most specific match — has text_preview)
        if "text_preview" in q and "claims_status" in q:
            return [{
                "article_id": "art-1",
                "title": "Climate research update",
                "source_name": "Reuters",
                "excerpt": "Details about the climate.",
                "text_preview": "Climate research is advancing.",
                "overall_credibility": "HIGH",
                "insight_summary": "Trend insight.",
                "claims_status": "completed",
                "claims_error_message": None,
            }]

        # _search_relevant_articles FTS / fallback queries
        if (
            ("ts_rank" in q or "to_tsvector" in q)
            and "from articles a" in q
        ) or (
            "select a.article_id, a.title, a.source_name, a.overall_credibility" in q
        ):
            return [{
                "article_id": "art-1",
                "title": "Climate research update",
                "source_name": "Reuters",
                "overall_credibility": "HIGH",
                "relevance": 0.7,
            }]

        # claims for context
        if "from claims c" in q and "fact_checks" in q:
            return []

        # _get_session_history
        if "from chat_messages where session_id" in q:
            return []

        # _get_platform_metrics
        if "count(distinct country_code)" in q:
            return [{"c": 198}]
        if "count(distinct source_name)" in q:
            return [{"c": 75}]

        # _extract_countries_from_sources
        if "select distinct country_code" in q and "from articles" in q:
            return [{"country_code": "GL"}]

        return []

    db.execute_query.side_effect = _execute
    db.execute_update.return_value = None
    db.execute_scalar.return_value = 0
    return db


@pytest.fixture
def chat_db():
    """Install the chat fake DB into the global postgres slot."""
    import shared.database as _shared_db
    db = _make_chat_db()
    prior = _shared_db._postgres_client
    _shared_db._postgres_client = db
    yield db
    _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatViewContext:
    def test_article_id_in_view_context_hydrates_system_prompt(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)

        resp = client.post(
            "/api/chat",
            json={
                "question": "What does this article say?",
                "view_context": {"article_id": "art-42"},
            },
        )
        assert resp.status_code == 200, resp.text

        # Inspect the prompt sent to the LLM. INT-05 CacheAligner moved the
        # volatile view-context out of the static system prefix and into the
        # user message (so the prefix stays cache-eligible), so assert against
        # the full prompt rather than the system message alone.
        assert fake_llm.calls, "LLM should have been invoked"
        messages = fake_llm.calls[0]["messages"]
        full_prompt = "\n".join(m["content"] for m in messages if m.get("content"))

        # The article title from the hydrated view must appear
        assert "Greenland Ice Sheet Loss Accelerates" in full_prompt
        # And its credibility tag
        assert "HIGH" in full_prompt

    def test_country_in_view_context_promoted_for_retrieval(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)

        resp = client.post(
            "/api/chat",
            json={
                "question": "what about it?",
                "view_context": {"country": "FI"},
            },
        )
        assert resp.status_code == 200
        # INT-05 CacheAligner moved the volatile view-context out of the static
        # system prefix into the user message, so assert against the full prompt.
        messages = fake_llm.calls[0]["messages"]
        full_prompt = "\n".join(m["content"] for m in messages if m.get("content"))
        assert "FI" in full_prompt
        assert "Country focus" in full_prompt or "42 articles" in full_prompt

    def test_analysis_id_triggers_url_analysis_lookup(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)

        resp = client.post(
            "/api/chat",
            json={
                "question": "What does the analysis say?",
                "view_context": {"analysis_id": "ua-1"},
            },
        )
        assert resp.status_code == 200, resp.text

        # INT-05 CacheAligner moved the view-context into the user message, so
        # assert against the full prompt rather than the system message alone.
        messages = fake_llm.calls[0]["messages"]
        full_prompt = "\n".join(m["content"] for m in messages if m.get("content"))
        assert "URL analysis open" in full_prompt or "X article" in full_prompt

    def test_no_llm_providers_returns_error_payload(
        self, client, chat_db, monkeypatch
    ):
        """When the whole fallback chain fails (llm_chat_with_fallback returns
        None — no provider usable), the chat route returns a structured error
        payload instead of crashing."""
        import app.domains.intelligence.llm_client as llm_mod
        monkeypatch.setattr(llm_mod, "llm_chat_with_fallback", lambda **kw: None)

        resp = client.post(
            "/api/chat",
            json={"question": "Anything?"},
        )
        # Route still returns 200 (the error is encoded in the body)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("error") == "all_providers_failed"
        assert "unavailable" in data["answer"].lower()

    def test_session_id_is_reused_for_multi_turn(
        self, client, chat_db, monkeypatch
    ):
        _stub_llm(monkeypatch)
        existing_session = "11111111-2222-3333-4444-555555555555"

        resp = client.post(
            "/api/chat",
            json={
                "question": "Follow-up question?",
                "session_id": existing_session,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # The same session_id must be returned (no new one created)
        assert data["session_id"] == existing_session

    def test_too_short_question_rejected(self, client, chat_db, monkeypatch):
        _stub_llm(monkeypatch)
        resp = client.post("/api/chat", json={"question": "x"})
        # min_length=3 on the field
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Cynefin routing tests — research_analysis mode steers the system prompt
# based on the classified domain (clear / complicated / complex / chaotic).
# ---------------------------------------------------------------------------

class TestCynefinRouting:
    """When mode=research_analysis, the Cynefin classification result must
    actually shape the system prompt the LLM receives — not just be returned
    in the response. Each domain injects a distinct guidance block."""

    def test_chaotic_question_injects_rapid_assessment_guidance(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)
        resp = client.post(
            "/api/chat",
            json={
                "question": "Breaking emergency: what is the immediate flood evacuation status?",
                "mode": "research_analysis",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # The classification must be returned to the client unchanged
        assert data.get("cynefin_classification", {}).get("recommended_strategy") == "rapid_assessment"

        # And — the new behaviour — the guidance text must be in the prompt.
        # INT-05 CacheAligner builds cynefin guidance into the user message, so
        # assert against the full prompt rather than the system message alone.
        full_prompt = "\n".join(
            m["content"] for m in fake_llm.calls[0]["messages"] if m.get("content")
        )
        assert "rapid assessment" in full_prompt.lower()
        assert "uncertainty" in full_prompt.lower()

    def test_clear_factual_question_injects_direct_lookup_guidance(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)
        resp = client.post(
            "/api/chat",
            json={
                "question": "What is the current temperature in Helsinki?",
                "mode": "research_analysis",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cynefin_classification", {}).get("recommended_strategy") == "direct_lookup"

        full_prompt = "\n".join(
            m["content"] for m in fake_llm.calls[0]["messages"] if m.get("content")
        )
        assert "direct lookup" in full_prompt.lower()
        # Direct-lookup guidance forbids speculation
        assert "do not speculate" in full_prompt.lower() or "do not pad" in full_prompt.lower()

    def test_complex_predictive_question_injects_causal_guidance(
        self, client, chat_db, monkeypatch
    ):
        fake_llm = _stub_llm(monkeypatch)
        resp = client.post(
            "/api/chat",
            json={
                "question": "Predict the tipping point and feedback loop scenarios for Greenland ice loss.",
                "mode": "research_analysis",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cynefin_classification", {}).get("recommended_strategy") == "causal_analysis"

        full_prompt = "\n".join(
            m["content"] for m in fake_llm.calls[0]["messages"] if m.get("content")
        )
        assert "causal" in full_prompt.lower()
        assert "counterfactual" in full_prompt.lower()

    def test_general_mode_skips_cynefin_guidance(
        self, client, chat_db, monkeypatch
    ):
        """In modes other than research_analysis the cynefin block must not
        appear — the steering only activates for research_analysis."""
        fake_llm = _stub_llm(monkeypatch)
        resp = client.post(
            "/api/chat",
            json={
                "question": "Predict the tipping point for Greenland ice loss.",
                "mode": "general",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # In general mode the classification should NOT be set
        assert data.get("cynefin_classification") is None

        system_prompt = next(
            m["content"] for m in fake_llm.calls[0]["messages"] if m["role"] == "system"
        )
        # None of the four guidance headers should appear
        assert "ANALYSIS DEPTH (Cynefin:" not in system_prompt
