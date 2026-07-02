"""ML-15 regression: map "Ask" must not return 0 when the structured topic
filter matches nothing.

Root cause: the topic clause ANDed ``a.tags && :variants`` against a tags column
that is empty platform-wide, so the golden query "Drought in East Africa"
returned matching_articles=0 while /country-stats?keyword=drought returned 96.

Fix: the topic clause is now ADDITIVE (OR into content_category + an English FTS
match) and, when the structured filters still match nothing, the endpoint falls
back to a broadened OR-of-terms corpus search and says so honestly rather than
returning 0.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def fallback_db():
    """DB where the strict/structured primary pass returns 0 rows but the
    relaxed OR-of-terms fallback (``to_tsquery(:q_or)``) returns matches."""
    now = datetime.utcnow()

    def _execute(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()

        # Relaxed fallback pass — identified by the :q_or bind used ONLY there.
        if ":q_or" in q:
            if "count(*) as total" in q:
                return [{"total": 96}]
            if "group by a.country_code" in q:
                return [
                    {"country_code": "KE", "article_count": 40,
                     "avg_reliability": 71.0, "last_updated": now},
                    {"country_code": "ET", "article_count": 31,
                     "avg_reliability": 68.0, "last_updated": now},
                    {"country_code": "SO", "article_count": 25,
                     "avg_reliability": 60.0, "last_updated": now},
                ]
            return []

        # Country-name lookup (_get_country_names).
        if "from countries" in q and "country_name" in q:
            return [
                {"country_code": "KE", "country_name": "Kenya"},
                {"country_code": "ET", "country_name": "Ethiopia"},
                {"country_code": "SO", "country_name": "Somalia"},
            ]

        # Primary pass (strict topic clause / websearch AND) — matches nothing.
        return []

    db = MagicMock()
    db.execute_query.side_effect = _execute
    db.execute_update.return_value = None
    db.execute_scalar.return_value = 0

    import shared.database as _shared_db
    prior = _shared_db._postgres_client
    _shared_db._postgres_client = db
    yield db
    _shared_db._postgres_client = prior


class TestMapQueryTopicFallback:
    def test_topic_query_falls_back_instead_of_returning_zero(
        self, client, fallback_db, monkeypatch
    ):
        from api.map import routes_query

        # LLM parse yields a topic + region (the golden "Drought in East Africa").
        monkeypatch.setattr(
            routes_query, "_llm_parse_query",
            AsyncMock(return_value={"topic": "drought", "region": "africa"}),
        )
        # Force the deterministic (non-LLM) answer path.
        monkeypatch.setattr(
            routes_query, "_llm_generate_map_answer",
            AsyncMock(return_value=(None, None, [])),
        )

        resp = client.post("/api/map/query", json={"query": "Drought in East Africa"})
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # The bug returned 0; the fallback must surface the real corpus matches.
        assert data["matching_articles"] == 96
        assert len(data["country_highlights"]) == 3
        assert data["filters_applied"].get("fallback") == "broadened_corpus_search"
        # Honest framing about the broadened search.
        assert "broader keyword search" in (data["answer"] or "").lower()

    def test_or_tsquery_terms_builds_safe_or_string(self):
        from api.map.routes_query import _or_tsquery_terms

        out = _or_tsquery_terms("Drought in East Africa", "drought")
        # OR semantics; stopword/short token dropped; de-duplicated.
        assert " | " in out
        parts = out.split(" | ")
        assert "drought" in parts and "east" in parts and "africa" in parts
        assert "in" not in parts
        assert parts.count("drought") == 1  # topic duplicate collapsed
        # Only alphanumeric tokens + separators — no tsquery metachars leak.
        assert all(c.isalnum() or c in " |" for c in out)

    def test_empty_or_all_stopword_query_yields_no_terms(self):
        from api.map.routes_query import _or_tsquery_terms

        assert _or_tsquery_terms("", None) == ""
        assert _or_tsquery_terms("of the a", None) == ""
