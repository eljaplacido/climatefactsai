"""Regression tests for ArticleRepository.list_articles (2026-06-02).

Pins the fix for the dead /api/v2/articles endpoint (flagged by the e2e audit):
  - the canonical content API returned [] because list_articles gated on a
    hardcoded climate-tag whitelist; it must gate on the off-topic classifier
    (is_off_topic / is_synthetic) like the working legacy /api/articles.
  - ?q= 500'd because the search to_tsvector referenced headline/summary_text
    columns that do not exist in prod.
  - all user-controlled filters must be bound params, not f-string interpolated.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.domains.content.repository import ArticleRepository


def _repo():
    db = MagicMock()
    db.execute_query.return_value = []  # empty -> no row parsing
    return ArticleRepository(db), db


def _captured_sql_and_params(db):
    call = db.execute_query.call_args
    sql = call.args[0] if call.args else call.kwargs.get("query", "")
    params = call.args[1] if len(call.args) > 1 else call.kwargs.get("params", {})
    return sql, params


class TestListArticlesRelevanceGate:
    def test_default_uses_offtopic_gate_not_tag_whitelist(self):
        repo, db = _repo()
        repo.list_articles()
        sql, _ = _captured_sql_and_params(db)
        assert "is_off_topic IS NOT TRUE" in sql
        assert "is_synthetic IS NOT TRUE" in sql
        # The brittle hardcoded whitelist must be gone.
        assert "renewable-energy" not in sql
        assert "climate_tags" not in sql

    def test_include_non_climate_drops_offtopic_gate(self):
        repo, db = _repo()
        repo.list_articles(include_non_climate=True)
        sql, _ = _captured_sql_and_params(db)
        assert "is_synthetic IS NOT TRUE" in sql  # synthetic always excluded
        assert "is_off_topic" not in sql  # off-topic gate lifted


class TestListArticlesSearch:
    def test_search_parameterized_and_no_missing_columns(self):
        repo, db = _repo()
        repo.list_articles(query="climate")
        sql, params = _captured_sql_and_params(db)
        assert ":q_text" in sql
        # SEM-01: multilingual FTS uses the precomputed language-aware search_tsv
        # column + websearch_to_tsquery('simple', …), not hardcoded English.
        assert "search_tsv" in sql
        assert "websearch_to_tsquery('simple'" in sql
        assert "to_tsvector('english'" not in sql
        # The non-existent columns that 500'd prod must not appear.
        assert "headline" not in sql
        assert "summary_text" not in sql
        # Value is bound, never interpolated as a literal.
        assert "websearch_to_tsquery('simple', 'climate')" not in sql
        assert params.get("q_text") == "climate"

    def test_legacy_path_also_has_no_missing_columns(self):
        """Prod always falls back to the legacy query (publishers table absent),
        so the legacy SQL must also be free of headline/summary_text."""
        repo, db = _repo()
        repo._trust_queries_supported = False  # force legacy path
        repo.list_articles(query="climate")
        sql, params = _captured_sql_and_params(db)
        assert "headline" not in sql
        assert "summary_text" not in sql
        assert ":q_text" in sql
        assert params.get("q_text") == "climate"


class TestListArticlesFilterBinding:
    def test_country_credibility_tags_are_bound_params(self):
        repo, db = _repo()
        repo.list_articles(country="US", credibility="HIGH", tags=["solar", "wind"])
        sql, params = _captured_sql_and_params(db)
        assert ":country" in sql and params.get("country") == "US"
        assert ":credibility" in sql and params.get("credibility") == "HIGH"
        assert ":tag0" in sql and ":tag1" in sql
        assert params.get("tag0") == "solar" and params.get("tag1") == "wind"
        # No raw literals interpolated.
        assert "'US'" not in sql
        assert "'HIGH'" not in sql

    def test_injection_attempt_is_not_interpolated(self):
        repo, db = _repo()
        evil = "x'; DROP TABLE articles; --"
        repo.list_articles(country=evil, query=evil)
        sql, params = _captured_sql_and_params(db)
        assert "DROP TABLE" not in sql  # value never reaches the SQL string
        assert params.get("country") == evil
        assert params.get("q_text") == evil

    def test_limit_offset_are_bound(self):
        repo, db = _repo()
        repo.list_articles(limit=7, offset=14)
        sql, params = _captured_sql_and_params(db)
        assert ":limit" in sql and ":offset" in sql
        assert params.get("limit") == 7 and params.get("offset") == 14
