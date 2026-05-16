"""claim_provenance + audit-trail endpoint tests (Phase 4 wave 3).

Pins:
- record_provenance writes the expected INSERT shape and serialises JSONB.
- record_provenance is best-effort: missing-table / DB errors don't raise.
- record_provenance rejects rows without any identifying link.
- get_provenance_for_* return parsed JSONB and stringified UUIDs.
- /api/methodology/audit-trail/* endpoints surface records through the
  same shape.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.domains.intelligence.provenance import (
    EXTRACTION_DEEP_SEARCH,
    EXTRACTION_URL_ANALYSIS,
    ProvenanceRecord,
    get_provenance_for_article,
    get_provenance_for_claim,
    get_provenance_for_url_analysis,
    record_provenance,
)


client = TestClient(app)


# ---------------------------------------------------------------------------
# Fake DB
# ---------------------------------------------------------------------------

class _CaptureDB:
    """Records execute_query/execute_update calls and serves canned rows."""
    def __init__(self, rows_for_select: Optional[List[Dict[str, Any]]] = None,
                 fail_on_insert: bool = False):
        self.queries: List[Dict[str, Any]] = []
        self.rows_for_select = rows_for_select or []
        self.fail_on_insert = fail_on_insert
        self._next_id = 1

    def execute_query(self, query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()
        self.queries.append({"q": q, "params": params})
        if "insert into claim_provenance" in q:
            if self.fail_on_insert:
                raise RuntimeError("simulated insert failure")
            row = {"id": self._next_id}
            self._next_id += 1
            return [row]
        if "from claim_provenance" in q:
            return self.rows_for_select
        return []

    def execute_update(self, query, params=None):
        self.queries.append({"q": " ".join(query.split()).lower(), "params": params or {}})
        return None


# ---------------------------------------------------------------------------
# record_provenance write path
# ---------------------------------------------------------------------------

class TestRecordProvenance:
    def test_writes_insert_with_serialised_jsonb(self):
        db = _CaptureDB()
        rec = ProvenanceRecord(
            extraction_method=EXTRACTION_URL_ANALYSIS,
            url_analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            model_name="deepseek-chat",
            prompt_name="cynefin_classifier",
            prompt_version="v1.0",
            prompt_fingerprint="abcdef0123456789",
            retrieval_strategy="user_submitted_url",
            source_article_ids=["uuid-1", "uuid-2"],
            hallucination_score=0.2,
            confidence=0.7,
            raw_metadata={"claim_count": 5, "text_length": 1234},
        )
        new_id = record_provenance(db, rec)
        assert new_id == 1
        # The INSERT was the only call.
        assert len(db.queries) == 1
        call = db.queries[0]
        assert "insert into claim_provenance" in call["q"]
        # JSONB columns are serialised to string before binding.
        assert isinstance(call["params"]["source_article_ids"], str)
        assert json.loads(call["params"]["source_article_ids"]) == ["uuid-1", "uuid-2"]
        assert isinstance(call["params"]["raw_metadata"], str)
        assert json.loads(call["params"]["raw_metadata"]) == {
            "claim_count": 5, "text_length": 1234,
        }
        # Pass-throughs preserved.
        assert call["params"]["extraction_method"] == EXTRACTION_URL_ANALYSIS
        assert call["params"]["url_analysis_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert call["params"]["prompt_fingerprint"] == "abcdef0123456789"

    def test_returns_none_when_no_link_provided(self):
        db = _CaptureDB()
        rec = ProvenanceRecord(extraction_method="anything")
        result = record_provenance(db, rec)
        assert result is None
        # No SQL was attempted.
        assert db.queries == []

    def test_returns_none_on_db_failure(self):
        """A failing insert (e.g. migration not applied) must not raise."""
        db = _CaptureDB(fail_on_insert=True)
        rec = ProvenanceRecord(
            extraction_method=EXTRACTION_DEEP_SEARCH,
            article_id="11111111-1111-1111-1111-111111111111",
            model_name="claude-sonnet-4-5",
        )
        result = record_provenance(db, rec)
        assert result is None

    def test_none_jsonb_fields_pass_as_none(self):
        db = _CaptureDB()
        rec = ProvenanceRecord(
            extraction_method=EXTRACTION_URL_ANALYSIS,
            url_analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            source_article_ids=None,
            raw_metadata=None,
        )
        new_id = record_provenance(db, rec)
        assert new_id == 1
        params = db.queries[0]["params"]
        assert params["source_article_ids"] is None
        assert params["raw_metadata"] is None


# ---------------------------------------------------------------------------
# Read paths
# ---------------------------------------------------------------------------

class TestGetProvenance:
    def _sample_row(self, link_field: str, link_value: str) -> Dict[str, Any]:
        from uuid import UUID
        row = {
            "id": 7,
            "claim_id": None,
            "url_analysis_id": None,
            "article_id": None,
            "extraction_method": EXTRACTION_URL_ANALYSIS,
            "model_name": "deepseek-chat",
            "prompt_name": "cynefin_classifier",
            "prompt_version": "v1.0",
            "prompt_fingerprint": "abcdef0123456789",
            "retrieval_strategy": "user_submitted_url",
            # JSONB stored as JSON string (psycopg sometimes returns string).
            "source_article_ids": '["uuid-1", "uuid-2"]',
            "hallucination_score": 0.2,
            "confidence": 0.7,
            "created_at": datetime(2026, 5, 16, 12, 0, 0),
            "raw_metadata": '{"claim_count": 5}',
        }
        # Set the link as a UUID so the stringify path is exercised.
        row[link_field] = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee") if link_value == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" else link_value
        return row

    def test_url_analysis_parses_jsonb_and_stringifies_uuids(self):
        db = _CaptureDB(rows_for_select=[
            self._sample_row("url_analysis_id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        ])
        out = get_provenance_for_url_analysis(db, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert len(out) == 1
        # JSONB strings parsed to native lists/dicts.
        assert out[0]["source_article_ids"] == ["uuid-1", "uuid-2"]
        assert out[0]["raw_metadata"] == {"claim_count": 5}
        # UUID -> str.
        assert out[0]["url_analysis_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        # created_at -> str.
        assert isinstance(out[0]["created_at"], str)

    def test_returns_empty_list_on_db_error(self):
        class _BrokenDB:
            def execute_query(self, q, p=None):
                raise RuntimeError("relation claim_provenance does not exist")

        db = _BrokenDB()
        assert get_provenance_for_url_analysis(db, "x") == []
        assert get_provenance_for_article(db, "x") == []
        assert get_provenance_for_claim(db, "x") == []


# ---------------------------------------------------------------------------
# /api/methodology/audit-trail/* endpoints
# ---------------------------------------------------------------------------

class TestProvenanceWithSessionIds:
    """Phase 4 wave 4: deep_search_session_id + cynefin_classification_id
    can serve as the identity link instead of the article/url/claim columns."""

    def test_deep_search_session_id_satisfies_check(self):
        db = _CaptureDB()
        rec = ProvenanceRecord(
            extraction_method=EXTRACTION_DEEP_SEARCH,
            deep_search_session_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            model_name="anthropic:claude-sonnet-4-5",
            prompt_name="deep_search_synthesis",
            prompt_version="v1.0",
            prompt_fingerprint="abcdef0123456789",
        )
        new_id = record_provenance(db, rec)
        assert new_id == 1
        params = db.queries[0]["params"]
        assert params["deep_search_session_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert params["claim_id"] is None
        assert params["url_analysis_id"] is None
        assert params["article_id"] is None

    def test_cynefin_classification_id_satisfies_check(self):
        from app.domains.intelligence.provenance import EXTRACTION_CYNEFIN
        db = _CaptureDB()
        rec = ProvenanceRecord(
            extraction_method=EXTRACTION_CYNEFIN,
            cynefin_classification_id="11111111-2222-3333-4444-555555555555",
        )
        new_id = record_provenance(db, rec)
        assert new_id == 1
        params = db.queries[0]["params"]
        assert params["cynefin_classification_id"] == "11111111-2222-3333-4444-555555555555"

    def test_no_link_at_all_still_refuses(self):
        """Regression: removing the original three links AND not setting the
        new ones still bounces the record."""
        db = _CaptureDB()
        rec = ProvenanceRecord(extraction_method=EXTRACTION_URL_ANALYSIS)
        assert record_provenance(db, rec) is None
        assert db.queries == []  # no SQL attempted


class TestGetProvenanceForDeepSearchSession:
    def test_returns_rows_for_session(self):
        from app.domains.intelligence.provenance import (
            get_provenance_for_deep_search_session,
        )
        rows = [
            {
                "id": 1,
                "claim_id": None,
                "url_analysis_id": None,
                "article_id": None,
                "deep_search_session_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "cynefin_classification_id": None,
                "extraction_method": EXTRACTION_DEEP_SEARCH,
                "model_name": "anthropic",
                "prompt_name": "deep_search_synthesis",
                "prompt_version": "v1.0",
                "prompt_fingerprint": "abcdef0123456789",
                "retrieval_strategy": "internal_corpus+perplexity",
                "source_article_ids": None,
                "hallucination_score": 0.15,
                "confidence": None,
                "created_at": datetime(2026, 5, 16, 14, 0, 0),
                "raw_metadata": None,
            }
        ]
        db = _CaptureDB(rows_for_select=rows)
        out = get_provenance_for_deep_search_session(
            db, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        assert len(out) == 1
        assert out[0]["deep_search_session_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert out[0]["extraction_method"] == EXTRACTION_DEEP_SEARCH


class TestCynefinRouterRecordsProvenance:
    """When the LLM path fires AND a db is passed, CynefinRouter writes one
    provenance row."""

    def test_llm_path_records_when_db_provided(self, monkeypatch):
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return '{"domain": "complex", "confidence": 0.7, "reasoning": "test"}'
        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        captured = []
        class _DB:
            def execute_query(self, q, p=None):
                if "insert into claim_provenance" in " ".join(q.split()).lower():
                    captured.append(p or {})
                    return [{"id": 1}]
                return []

        router = CynefinRouter()
        result = router.classify(
            "Intersection of monsoonal variability with grid resilience.",
            db=_DB(),
            deep_search_session_id="session-123",
        )
        assert result["domain"] == "complex"
        assert len(captured) == 1
        params = captured[0]
        assert params["extraction_method"] == "cynefin_classification"
        assert params["deep_search_session_id"] == "session-123"
        # cynefin_classification_id was minted (UUID).
        assert params["cynefin_classification_id"] is not None
        assert params["confidence"] == 0.7

    def test_llm_path_no_db_no_record(self, monkeypatch):
        """No db → don't try to record, but still return the classification."""
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return '{"domain": "complex", "confidence": 0.7, "reasoning": "test"}'
        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        result = router.classify(
            "Intersection of monsoonal variability with grid resilience.",
        )
        # Result still produced normally.
        assert result["domain"] == "complex"

    def test_keyword_path_does_not_record(self, monkeypatch):
        """The keyword path matches before LLM, so no provenance is written
        (we only audit LLM calls in this wave; keyword scoring is local
        deterministic logic)."""
        from app.domains.intelligence.cynefin_router import CynefinRouter

        captured = []
        class _DB:
            def execute_query(self, q, p=None):
                if "insert into claim_provenance" in " ".join(q.split()).lower():
                    captured.append(p or {})
                    return [{"id": 1}]
                return []

        router = CynefinRouter()
        result = router.classify("What is the current temperature?", db=_DB())
        assert result["domain"] == "clear"  # keyword match
        assert captured == []


class TestAuditTrailEndpoints:
    """End-to-end via FastAPI TestClient. Swap the shared postgres client
    to a deterministic fake."""

    def _swap_db(self, fake):
        import shared.database as _shared_db
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = fake
        return prior

    def _restore(self, prior):
        import shared.database as _shared_db
        _shared_db._postgres_client = prior

    def test_url_analysis_endpoint_returns_records(self):
        fake = _CaptureDB(rows_for_select=[
            {
                "id": 1,
                "claim_id": None,
                "url_analysis_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "article_id": None,
                "extraction_method": EXTRACTION_URL_ANALYSIS,
                "model_name": "deepseek-chat",
                "prompt_name": None,
                "prompt_version": None,
                "prompt_fingerprint": None,
                "retrieval_strategy": "user_submitted_url",
                "source_article_ids": None,
                "hallucination_score": None,
                "confidence": 0.7,
                "created_at": datetime(2026, 5, 16, 12, 0, 0),
                "raw_metadata": None,
            }
        ])
        prior = self._swap_db(fake)
        try:
            r = client.get(
                "/api/methodology/audit-trail/url-analysis/"
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["url_analysis_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            assert body["total"] == 1
            rec = body["records"][0]
            assert rec["extraction_method"] == EXTRACTION_URL_ANALYSIS
            assert rec["confidence"] == 0.7
        finally:
            self._restore(prior)

    def test_article_endpoint_returns_records(self):
        fake = _CaptureDB(rows_for_select=[
            {
                "id": 2,
                "claim_id": None,
                "url_analysis_id": None,
                "article_id": "11111111-1111-1111-1111-111111111111",
                "extraction_method": EXTRACTION_DEEP_SEARCH,
                "model_name": "claude-sonnet-4-5",
                "prompt_name": "deep_search_synthesis",
                "prompt_version": "v1.0",
                "prompt_fingerprint": "abcdef0123456789",
                "retrieval_strategy": "internal_corpus(fts+semantic)",
                "source_article_ids": '["a","b"]',
                "hallucination_score": 0.1,
                "confidence": 0.85,
                "created_at": datetime(2026, 5, 16, 13, 0, 0),
                "raw_metadata": None,
            }
        ])
        prior = self._swap_db(fake)
        try:
            r = client.get(
                "/api/methodology/audit-trail/article/"
                "11111111-1111-1111-1111-111111111111"
            )
            assert r.status_code == 200
            body = r.json()
            assert body["article_id"] == "11111111-1111-1111-1111-111111111111"
            assert body["total"] == 1
            rec = body["records"][0]
            assert rec["prompt_fingerprint"] == "abcdef0123456789"
            assert rec["source_article_ids"] == ["a", "b"]
        finally:
            self._restore(prior)

    def test_claim_endpoint_handles_no_rows(self):
        fake = _CaptureDB(rows_for_select=[])
        prior = self._swap_db(fake)
        try:
            r = client.get(
                "/api/methodology/audit-trail/claim/"
                "22222222-2222-2222-2222-222222222222"
            )
            assert r.status_code == 200
            body = r.json()
            assert body["claim_id"] == "22222222-2222-2222-2222-222222222222"
            assert body["total"] == 0
            assert body["records"] == []
        finally:
            self._restore(prior)

    def test_audit_trail_graceful_when_table_missing(self):
        """If the migration hasn't been applied, return empty list (200)."""
        class _BrokenDB:
            def execute_query(self, q, p=None):
                raise RuntimeError("relation claim_provenance does not exist")

        prior = self._swap_db(_BrokenDB())
        try:
            r = client.get(
                "/api/methodology/audit-trail/url-analysis/"
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            )
            assert r.status_code == 200
            assert r.json()["total"] == 0
        finally:
            self._restore(prior)
