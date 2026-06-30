"""URL Analysis route tests.

Covers:
- POST /api/analyze-url validation: HTTPS-only, blocks localhost / private IPs /
  DNS rebinding / .internal / .local TLDs.
- GET /api/analyze-url/{job_id} casts UUID -> str (regression for ace5787).
- 503 / 500 path when LLM keys are missing or extractor raises.

External services (httpx, ClaimExtractor, DNS lookups) are stubbed so each test
runs in milliseconds.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(autouse=True)
def _bypass_url_quota(monkeypatch):
    """These tests exercise URL-analysis submission/validation mechanics, not the
    freemium quota gate (covered in test_quota_endpoint_integration). Anonymous
    url_analysis quota is 0 (2026-05-23 freemium tightening), which would 429
    every submission here — bypass the gate so the pipeline assertions run."""
    from api.quota_service import QuotaService

    monkeypatch.setattr(QuotaService, "check_and_raise", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _smart_url_db(rows_for_get=None, raise_on_select=False):
    """Build a FakeDB-style stub that responds to URL analysis queries."""
    db = MagicMock()
    rows_for_get = rows_for_get or []

    def _execute_query(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()
        if raise_on_select and "from url_analyses" in q:
            raise RuntimeError("DB unavailable")
        if "from url_analyses" in q and "where analysis_id" in q:
            return rows_for_get
        if "from user_usage" in q:
            return [{"count": 0}]
        return []

    db.execute_query.side_effect = _execute_query
    db.execute_update.return_value = None
    db.execute_scalar.return_value = 0
    return db


# ---------------------------------------------------------------------------
# POST /api/analyze-url — validation
# ---------------------------------------------------------------------------

class TestAnalyzeUrlValidation:
    """Pydantic-level validation rejects unsafe URLs before any DB hit."""

    def test_rejects_http_url(self, client):
        resp = client.post("/api/analyze-url", json={"url": "http://example.com/article"})
        assert resp.status_code == 422
        body = resp.json()
        # Pydantic v1 returns a `detail` list; the message is in there
        assert "HTTPS" in str(body) or "https" in str(body).lower()

    def test_rejects_localhost(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://localhost/article"}
        )
        assert resp.status_code == 422
        assert "localhost" in str(resp.json()).lower() or "internal" in str(resp.json()).lower()

    def test_rejects_127_loopback(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://127.0.0.1/article"}
        )
        assert resp.status_code == 422

    def test_rejects_private_ip(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://192.168.1.10/article"}
        )
        assert resp.status_code == 422
        assert "private" in str(resp.json()).lower() or "internal" in str(resp.json()).lower()

    def test_rejects_link_local(self, client):
        # 169.254.169.254 is the AWS metadata endpoint
        resp = client.post(
            "/api/analyze-url", json={"url": "https://169.254.169.254/latest/meta-data/"}
        )
        assert resp.status_code == 422

    def test_rejects_metadata_google_internal(self, client):
        resp = client.post(
            "/api/analyze-url",
            json={"url": "https://metadata.google.internal/computeMetadata/v1/"},
        )
        assert resp.status_code == 422

    def test_rejects_internal_tld(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://server.internal/x"}
        )
        assert resp.status_code == 422
        assert ".internal" in str(resp.json()) or "internal" in str(resp.json()).lower()

    def test_rejects_local_tld(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://printer.local/x"}
        )
        assert resp.status_code == 422

    def test_rejects_localhost_tld(self, client):
        resp = client.post(
            "/api/analyze-url", json={"url": "https://app.localhost/x"}
        )
        assert resp.status_code == 422

    def test_rejects_dns_rebinding(self, client):
        """A hostname that resolves to a private IP must be rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            # Return AF_INET socktype with a private IP
            import socket
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))
            ]
            resp = client.post(
                "/api/analyze-url",
                json={"url": "https://attacker.example.com/article"},
            )
            assert resp.status_code == 422
            assert "rebinding" in str(resp.json()).lower() or "private" in str(resp.json()).lower()


# ---------------------------------------------------------------------------
# POST /api/analyze-url — happy submission path
# ---------------------------------------------------------------------------

class TestAnalyzeUrlSubmission:
    """Successful submission creates an analysis row and queues bg processing."""

    def test_submit_valid_https_url(self, client, monkeypatch):
        # Make any background socket lookup deterministic (DNS rebinding check)
        import socket
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **kw: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ],
        )
        # Stub out the URL content fetcher so the bg task doesn't hit network
        from api import url_analysis_routes as url_mod

        async def _fake_fetch(url):
            return {
                "title": "Stub article",
                "text": "x" * 600,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }
        monkeypatch.setattr(url_mod, "fetch_url_content", _fake_fetch)

        # Stub out claim extraction so background task never touches an LLM
        from app.domains.intelligence import services as intel_services

        async def _no_llm(self, *args, **kwargs):
            return []

        monkeypatch.setattr(intel_services.ClaimExtractor, "decompose_claims", _no_llm)

        resp = client.post(
            "/api/analyze-url",
            json={"url": "https://example.com/article-1"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "processing"
        # job_id must be a real UUID string (regression — must not be UUID object)
        assert isinstance(data["job_id"], str)
        assert len(data["job_id"]) >= 32

    def test_submit_falls_back_when_priority_column_missing(self, client, monkeypatch):
        import socket
        import shared.database as _shared_db

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **kw: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ],
        )

        class _PriorityMissingDB:
            def __init__(self):
                self.queries = []

            def execute_update(self, query, params=None):
                self.queries.append(" ".join(query.split()).lower())
                normalized = " ".join(query.split()).lower()
                if "insert into url_analyses" in normalized and "priority" in normalized:
                    raise RuntimeError('column "priority" of relation "url_analyses" does not exist')
                return 1

            def execute_query(self, query, params=None):
                return []

            def execute_scalar(self, query, params=None):
                return 0

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _PriorityMissingDB()
        try:
            resp = client.post(
                "/api/analyze-url",
                json={"url": "https://example.com/article-priority-fallback"},
            )
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert payload["status"] == "processing"
            assert isinstance(payload["job_id"], str)
        finally:
            _shared_db._postgres_client = prior


class TestFetchUrlContentLimits:
    @pytest.mark.asyncio
    async def test_accepts_content_larger_than_legacy_500kb_guard(self, monkeypatch):
        """Regression: large pages should not fail at the old fixed 500KB threshold."""
        from api import url_analysis_routes

        class _FakeResponse:
            def __init__(self, content: bytes):
                self.status_code = 200
                self.content = content
                self.text = content.decode("utf-8", errors="ignore")
                self.headers = {"content-length": str(len(content))}

            def raise_for_status(self):
                return None

        class _FakeClient:
            def __init__(self, response):
                self._response = response

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, *args, **kwargs):
                return self._response

        html = (
            "<html><head><title>Big report</title></head><body>"
            + ("<p>" + ("A" * 1200) + "</p>") * 700
            + "</body></html>"
        ).encode("utf-8")
        assert len(html) > 500 * 1024

        monkeypatch.setenv("URL_ANALYSIS_MAX_RESPONSE_BYTES", str(8 * 1024 * 1024))
        monkeypatch.setenv("URL_ANALYSIS_MAX_TEXT_CHARS", "200000")
        monkeypatch.setattr(
            url_analysis_routes.httpx,
            "AsyncClient",
            lambda *a, **kw: _FakeClient(_FakeResponse(html)),
        )

        result = await url_analysis_routes.fetch_url_content("https://example.com/large-report")
        assert result["title"] == "Big report"
        assert len(result["text"]) > 50000

    @pytest.mark.asyncio
    async def test_declared_content_length_above_limit_raises_too_large(self, monkeypatch):
        from api import url_analysis_routes
        from api.url_analysis_routes import (
            URLFetchException,
            FAILURE_REASON_RESPONSE_TOO_LARGE,
        )

        class _FakeResponse:
            def __init__(self):
                self.status_code = 200
                self.content = b"<html><body><p>x</p></body></html>"
                self.text = self.content.decode("utf-8")
                self.headers = {"content-length": str(12 * 1024 * 1024)}

            def raise_for_status(self):
                return None

        class _FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, *args, **kwargs):
                return _FakeResponse()

        monkeypatch.setenv("URL_ANALYSIS_MAX_RESPONSE_BYTES", str(10 * 1024 * 1024))
        monkeypatch.setattr(url_analysis_routes.httpx, "AsyncClient", lambda *a, **kw: _FakeClient())

        # fetch_url_content now raises the structured URLFetchException
        # (response_too_large) instead of a bare HTTPException(400); the route
        # maps it to the structured failure envelope. See test_url_analysis_failures.
        with pytest.raises(URLFetchException) as exc:
            await url_analysis_routes.fetch_url_content("https://example.com/too-big")
        assert exc.value.reason == FAILURE_REASON_RESPONSE_TOO_LARGE

    @pytest.mark.asyncio
    async def test_text_is_capped_by_configured_char_limit(self, monkeypatch):
        from api import url_analysis_routes

        class _FakeResponse:
            def __init__(self, html: str):
                self.status_code = 200
                self.content = html.encode("utf-8")
                self.text = html
                self.headers = {"content-length": str(len(self.content))}

            def raise_for_status(self):
                return None

        class _FakeClient:
            def __init__(self, response):
                self._response = response

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, *args, **kwargs):
                return self._response

        html = (
            "<html><head><title>Huge text</title></head><body>"
            + ("<p>" + ("B" * 800) + "</p>") * 1000
            + "</body></html>"
        )
        monkeypatch.setenv("URL_ANALYSIS_MAX_TEXT_CHARS", "25000")
        monkeypatch.setenv("URL_ANALYSIS_MAX_RESPONSE_BYTES", str(30 * 1024 * 1024))
        monkeypatch.setattr(
            url_analysis_routes.httpx,
            "AsyncClient",
            lambda *a, **kw: _FakeClient(_FakeResponse(html)),
        )

        result = await url_analysis_routes.fetch_url_content("https://example.com/huge-text")
        assert len(result["text"]) <= 25000

    def test_submit_falls_back_when_anonymous_uuid_fk_fails(self, client, monkeypatch):
        import socket
        import shared.database as _shared_db

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **kw: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ],
        )

        class _AnonymousFkDB:
            def __init__(self):
                self.generated_user_id = "11111111-1111-1111-1111-111111111111"

            def execute_update(self, query, params=None):
                params = params or {}
                normalized = " ".join(query.split()).lower()
                if "insert into url_analyses" in normalized:
                    if params.get("user_id") == "00000000-0000-0000-0000-000000000000":
                        raise RuntimeError("insert or update on table \"url_analyses\" violates foreign key constraint")
                    return 1
                return 1

            def execute_query(self, query, params=None):
                normalized = " ".join(query.split()).lower()
                if "select user_id from users where email" in normalized:
                    return []
                if "insert into users" in normalized and "returning user_id" in normalized:
                    return [{"user_id": self.generated_user_id}]
                return []

            def execute_scalar(self, query, params=None):
                return 0

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _AnonymousFkDB()
        try:
            resp = client.post(
                "/api/analyze-url",
                json={"url": "https://example.com/article-anon-fk-fallback"},
            )
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert payload["status"] == "processing"
            assert isinstance(payload["job_id"], str)
        finally:
            _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# GET /api/analyze-url/{job_id}
# ---------------------------------------------------------------------------

class TestAnalyzeUrlGet:
    """Status endpoint returns analysis row, stringifies the UUID, and gates anonymous reads on the signed token (S7)."""

    def test_get_analysis_casts_uuid_to_str(self, client):
        """Regression for ace5787: UUID column must be returned as str."""
        from uuid import UUID
        import shared.database as _shared_db
        from api.url_analysis_routes import _generate_job_token

        analysis_uuid = UUID("12345678-1234-5678-1234-567812345678")
        now = datetime.utcnow()
        rows = [{
            "user_id": "00000000-0000-0000-0000-000000000000",  # anon submission
            "analysis_id": analysis_uuid,  # raw UUID type from psycopg
            "submitted_url": "https://example.com/x",
            "status": "completed",
            "title": "Test Article",
            "source_name": "example.com",
            "source_domain": "example.com",
            "extracted_text": "body",
            "language_code": "en",
            "published_date": None,
            "reliability_score": 70,
            "overall_credibility": "MEDIUM",
            "extracted_claims": [],
            "fact_checks": [],
            "created_at": now,
            "processing_started_at": now,
            "completed_at": now,
            "processing_time_ms": 1234,
            "error_message": None,
        }]

        # Replace the global postgres client with our stub
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _smart_url_db(rows_for_get=rows)
        try:
            token = _generate_job_token(str(analysis_uuid))
            resp = client.get(f"/api/analyze-url/{analysis_uuid}?token={token}")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 200, resp.text
        data = resp.json()
        # The CRITICAL assertion: the value must be a string, not a serialised
        # UUID object (which would have been "12345678-...").
        assert isinstance(data["analysis_id"], str)
        assert data["analysis_id"] == str(analysis_uuid)
        assert data["status"] == "completed"
        assert data["reliability_score"] == 70

    def test_get_completed_includes_nested_article(self, client):
        """Contract fix (2026-06-29): a completed GET must carry a nested
        `article` object so the UrlAnalysisForm success card renders. article_id
        is the analysis_id (success card links to /research/analysis/{id})."""
        from uuid import UUID
        import shared.database as _shared_db
        from api.url_analysis_routes import _generate_job_token

        analysis_uuid = UUID("99999999-8888-7777-6666-555544443333")
        now = datetime.utcnow()
        rows = [{
            "user_id": "00000000-0000-0000-0000-000000000000",
            "analysis_id": analysis_uuid,
            "submitted_url": "https://example.com/solar",
            "status": "completed",
            "title": "Solar capacity report",
            "source_name": "example.com",
            "source_domain": "example.com",
            "extracted_text": "Solar capacity grew sharply. " * 40,
            "language_code": "en",
            "published_date": None,
            "reliability_score": 72,
            "overall_credibility": "MEDIUM",
            "extracted_claims": [
                {"claim_text": "Solar grew 35%"},
                {"claim_text": "Wind doubled"},
            ],
            "fact_checks": [
                {"verification_status": "verified"},
                {"verification_status": "disputed"},
            ],
            "created_at": now,
            "processing_started_at": now,
            "completed_at": now,
            "processing_time_ms": 900,
            "error_message": None,
        }]

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _smart_url_db(rows_for_get=rows)
        try:
            token = _generate_job_token(str(analysis_uuid))
            resp = client.get(f"/api/analyze-url/{analysis_uuid}?token={token}")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 200, resp.text
        data = resp.json()
        article = data.get("article")
        assert article is not None, "completed analysis must include nested article"
        # article_id is the analysis_id so /research/analysis/{id} resolves.
        assert article["article_id"] == str(analysis_uuid)
        assert article["source_credibility_score"] == 72  # ← reliability_score
        assert article["claim_count"] == 2
        assert article["verified_claim_count"] == 1  # only the 'verified' one
        assert article["overall_credibility"] == "MEDIUM"
        assert article["source_name"] == "example.com"
        assert article["excerpt"]  # first ~300 chars of extracted_text
        assert isinstance(article["tags"], list)

    def test_get_analysis_404_when_missing(self, client):
        import shared.database as _shared_db
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _smart_url_db(rows_for_get=[])
        try:
            # 404 fires before the auth gate (no row to check ownership against),
            # so we do NOT need a valid token here.
            resp = client.get("/api/analyze-url/00000000-0000-0000-0000-000000000000")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_analysis_parses_jsonb_string_claims(self, client):
        """When extracted_claims is stored as a JSON string, route must parse it."""
        import shared.database as _shared_db
        from uuid import UUID
        from api.url_analysis_routes import _generate_job_token

        analysis_uuid = UUID("11111111-2222-3333-4444-555555555555")
        rows = [{
            "user_id": "00000000-0000-0000-0000-000000000000",
            "analysis_id": analysis_uuid,
            "submitted_url": "https://example.com/y",
            "status": "completed",
            "title": "X",
            "source_name": "example.com",
            "source_domain": "example.com",
            "extracted_text": "body",
            "language_code": "en",
            "published_date": None,
            "reliability_score": 60,
            "overall_credibility": "MEDIUM",
            "extracted_claims": '[{"claim_text": "Solar grew 35%"}]',
            "fact_checks": '[]',
            "created_at": datetime.utcnow(),
            "processing_started_at": None,
            "completed_at": None,
            "processing_time_ms": None,
            "error_message": None,
        }]

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _smart_url_db(rows_for_get=rows)
        try:
            token = _generate_job_token(str(analysis_uuid))
            resp = client.get(f"/api/analyze-url/{analysis_uuid}?token={token}")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["extracted_claims"], list)
        assert data["extracted_claims"][0]["claim_text"] == "Solar grew 35%"
        assert data["fact_checks"] == []

    def test_get_analysis_403_without_token_or_owner(self, client):
        """S7: anonymous GET without a valid token must be denied even when the row exists."""
        import shared.database as _shared_db
        from uuid import UUID

        analysis_uuid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        rows = [{
            "user_id": "00000000-0000-0000-0000-000000000000",
            "analysis_id": analysis_uuid,
            "submitted_url": "https://example.com/private",
            "status": "completed",
            "title": "Private result",
            "source_name": "example.com",
            "source_domain": "example.com",
            "extracted_text": "leaky content",
            "language_code": "en",
            "published_date": None,
            "reliability_score": 50,
            "overall_credibility": "MEDIUM",
            "extracted_claims": [],
            "fact_checks": [],
            "created_at": datetime.utcnow(),
            "processing_started_at": None,
            "completed_at": None,
            "processing_time_ms": None,
            "error_message": None,
        }]

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _smart_url_db(rows_for_get=rows)
        try:
            # No token, no auth -> 403 (NOT 200; the pre-fix bug returned 200).
            resp_no_token = client.get(f"/api/analyze-url/{analysis_uuid}")
            # Wrong token also -> 403.
            resp_wrong_token = client.get(
                f"/api/analyze-url/{analysis_uuid}?token=deadbeefdeadbeefdeadbeefdeadbeef"
            )
        finally:
            _shared_db._postgres_client = prior

        assert resp_no_token.status_code == 403
        assert "access denied" in resp_no_token.json()["detail"].lower()
        assert resp_wrong_token.status_code == 403

    def test_get_analysis_times_out_stale_processing_job(self, client):
        """Stale processing rows should be marked failed instead of spinning forever."""
        import shared.database as _shared_db
        from uuid import UUID
        from datetime import timedelta
        from api.url_analysis_routes import _generate_job_token

        analysis_uuid = UUID("aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb")
        now = datetime.utcnow()
        rows = [{
            "user_id": "00000000-0000-0000-0000-000000000000",
            "analysis_id": analysis_uuid,
            "submitted_url": "https://example.com/stale-job",
            "status": "processing",
            "title": "Stale processing result",
            "source_name": "example.com",
            "source_domain": "example.com",
            "extracted_text": "body",
            "language_code": "en",
            "published_date": None,
            "reliability_score": None,
            "overall_credibility": None,
            "extracted_claims": [],
            "fact_checks": [],
            "created_at": now - timedelta(minutes=45),
            "processing_started_at": now - timedelta(minutes=41),
            "completed_at": None,
            "processing_time_ms": None,
            "error_message": None,
        }]

        db = _smart_url_db(rows_for_get=rows)
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = db
        try:
            token = _generate_job_token(str(analysis_uuid))
            resp = client.get(f"/api/analyze-url/{analysis_uuid}?token={token}")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["status"] == "failed"
        assert "timed out" in (payload.get("error_message") or "").lower()

        updates = [
            call for call in db.execute_update.call_args_list
            if "update url_analyses" in " ".join(str(call.args[0]).split()).lower()
        ]
        assert updates, "Expected stale timeout update to be persisted"


# ---------------------------------------------------------------------------
# Background task — 503 when LLM key missing
# ---------------------------------------------------------------------------

class TestBackgroundProcessing:
    """The background task should record `failed` status when extractor raises."""

    @pytest.mark.asyncio
    async def test_503_when_extractor_unavailable(self, monkeypatch):
        """When ClaimExtractor.decompose_claims raises 503, background task
        should mark the analysis as failed (not crash the worker)."""
        from api import url_analysis_routes
        from app.domains.intelligence import services as intel_services
        from fastapi import HTTPException

        # Stub fetch_url_content to return enough text for processing
        async def _fake_fetch(url):
            return {
                "title": "Example",
                "text": "x" * 600,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }

        async def _raise_503(self, *args, **kwargs):
            raise HTTPException(
                status_code=503,
                detail="Claim extraction unavailable: DEEPSEEK_API_KEY not configured.",
            )

        monkeypatch.setattr(url_analysis_routes, "fetch_url_content", _fake_fetch)
        monkeypatch.setattr(intel_services.ClaimExtractor, "decompose_claims", _raise_503)

        # Track update calls
        update_calls: list[dict] = []

        class _RecorderDB:
            def execute_update(self, query, params=None):
                update_calls.append({"query": " ".join(query.split()), "params": params or {}})
                return None

            def execute_query(self, query, params=None):
                return []

        # Patch get_postgres in the route module to return our recorder
        monkeypatch.setattr(
            url_analysis_routes, "get_postgres", lambda: _RecorderDB()
        )

        # Run the background job directly
        await url_analysis_routes.process_url_analysis_sync(
            analysis_id="aid-1",
            url="https://example.com/x",
            user_id="00000000-0000-0000-0000-000000000000",
        )

        # Should have set status to 'failed' with the error message
        failed_updates = [
            c for c in update_calls
            if "status = 'failed'" in c["query"].lower() or "set status = 'failed'" in c["query"].lower()
        ]
        assert failed_updates, f"Expected a 'failed' status update; got: {[c['query'] for c in update_calls]}"
        assert any(
            "DEEPSEEK_API_KEY" in (c["params"].get("error", "") or "")
            for c in failed_updates
        )

    @pytest.mark.asyncio
    async def test_hallucination_grounding_records_score(self, monkeypatch):
        """Phase 6 wave 2: HallucinationDetector runs on extracted claims and
        the score lands in claim_provenance.hallucination_score (dedicated column)."""
        from api import url_analysis_routes
        from app.domains.intelligence import services as intel_services
        from app.domains.intelligence import hallucination_detector as hd_mod

        async def _fake_fetch(url):
            return {
                "title": "Example",
                "text": "Solar capacity grew by 35% in 2022. " * 100,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }
        monkeypatch.setattr(url_analysis_routes, "fetch_url_content", _fake_fetch)

        class _Claim:
            def __init__(self, txt="Solar capacity grew by 35% in 2022"):
                self.claim_text = txt
                self.claim_type = "factual"
                self.importance_score = 0.85
                self.claim_context = "ctx"

        async def _fake_claims(self_arg, *args, **kwargs):
            return [_Claim()]
        monkeypatch.setattr(intel_services.ClaimExtractor, "decompose_claims", _fake_claims)

        # Mock HallucinationDetector.check so we don't need an LLM.
        async def _fake_check(self_arg, generated_text, source_texts, source_metadata=None):
            return {
                "hallucination_risk": 0.18,
                "is_grounded": True,
                "flagged_segments": [
                    {"text": "minor unsupported phrase", "reason": "no source", "severity": "low"},
                ],
                "entity_overlap_score": 0.9,
                "statistic_accuracy": 0.95,
                "overall_confidence": 0.82,
                "checks_performed": ["entity_overlap", "statistic_verification", "llm_grounding"],
            }
        monkeypatch.setattr(hd_mod.HallucinationDetector, "check", _fake_check)

        recorded = []
        class _RecorderDB:
            def execute_update(self, query, params=None):
                recorded.append(("update", " ".join((query or "").split()), params or {}))
                return None
            def execute_query(self, query, params=None):
                recorded.append(("query", " ".join((query or "").split()), params or {}))
                normalized = " ".join((query or "").split()).lower()
                if "insert into claim_provenance" in normalized:
                    return [{"id": 99}]
                return []
            def execute_scalar(self, query, params=None):
                return 0
        monkeypatch.setattr(url_analysis_routes, "get_postgres", lambda: _RecorderDB())

        await url_analysis_routes.process_url_analysis_sync(
            analysis_id="aid-hallucination",
            url="https://example.com/grounding-test",
            user_id="00000000-0000-0000-0000-000000000000",
        )

        prov_calls = [
            c for c in recorded
            if c[0] == "query" and "insert into claim_provenance" in c[1].lower()
        ]
        assert prov_calls, "Expected provenance insert with hallucination score"
        params = prov_calls[0][2]
        # Dedicated column populated, not None.
        assert params["hallucination_score"] == 0.18

        import json as _json
        raw_meta = _json.loads(params["raw_metadata"])
        # Flagged segments mirrored into raw_metadata so audit trail surfaces them.
        assert "hallucination_flagged_segments" in raw_meta
        assert len(raw_meta["hallucination_flagged_segments"]) == 1
        assert raw_meta["hallucination_flagged_segments"][0]["severity"] == "low"

    @pytest.mark.asyncio
    async def test_multi_llm_verification_records_agreement_in_provenance(self, monkeypatch):
        """Phase 5 wave 3: when CLILENS_MULTI_LLM_VERIFY=1 + ANTHROPIC_API_KEY is set,
        process_url_analysis_sync runs Anthropic as a secondary extractor and records
        agreement_score in claim_provenance.raw_metadata.multi_llm_verification.
        """
        import os as _os
        from api import url_analysis_routes
        from app.domains.intelligence import services as intel_services
        from app.domains.intelligence import anthropic_claim_extractor as ace_mod

        monkeypatch.setenv("CLILENS_MULTI_LLM_VERIFY", "1")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat-test")

        # 1) Fake fetch returns enough text for claim extraction to proceed.
        async def _fake_fetch(url):
            return {
                "title": "Example",
                "text": "Solar capacity grew 35% in 2022 according to the IEA. " * 50,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }
        monkeypatch.setattr(url_analysis_routes, "fetch_url_content", _fake_fetch)

        # 2) Primary (DeepSeek path) returns two claims.
        class _Claim:
            def __init__(self, claim_text, importance_score=0.8):
                self.claim_text = claim_text
                self.claim_type = "factual"
                self.importance_score = importance_score
                self.claim_context = "ctx"

        async def _fake_primary(self_arg, *args, **kwargs):
            return [
                _Claim("Solar capacity grew 35% in 2022"),
                _Claim("Wind doubled deployment in 2022"),
            ]
        monkeypatch.setattr(
            intel_services.ClaimExtractor, "decompose_claims", _fake_primary,
        )

        # 3) Secondary (Anthropic) returns one matching claim (50% agreement).
        #    Accepts prompt_name — the verifier now drives the secondary with a
        #    distinct auditor-persona prompt (audit item 5).
        async def _fake_secondary(self_arg, text, max_claims=20, prompt_name="claim_extraction"):
            from app.domains.intelligence.schemas import AtomicClaim, ClaimCategory
            return [
                AtomicClaim(
                    claim_text="Solar capacity grew 35% in 2022",
                    claim_type="factual",
                    claim_category=ClaimCategory.STATISTICAL,
                    importance_score=0.7,
                    claim_context="ctx",
                    extraction_model="anthropic:test-model",
                    extraction_confidence=0.9,
                ),
            ]
        monkeypatch.setattr(
            ace_mod.AnthropicClaimExtractor, "decompose_claims", _fake_secondary,
        )

        # 4) Record DB calls so we can assert what was written.
        recorded = []

        class _RecorderDB:
            def execute_update(self, query, params=None):
                recorded.append(("update", " ".join((query or "").split()), params or {}))
                return None

            def execute_query(self, query, params=None):
                recorded.append(("query", " ".join((query or "").split()), params or {}))
                # The provenance INSERT uses RETURNING id; return a row.
                normalized = " ".join((query or "").split()).lower()
                if "insert into claim_provenance" in normalized:
                    return [{"id": 42}]
                return []

            def execute_scalar(self, query, params=None):
                return 0

        monkeypatch.setattr(url_analysis_routes, "get_postgres", lambda: _RecorderDB())

        await url_analysis_routes.process_url_analysis_sync(
            analysis_id="aid-multi-llm",
            url="https://example.com/multi-llm-test",
            user_id="00000000-0000-0000-0000-000000000000",
        )

        # Find the claim_provenance INSERT and verify multi_llm_verification metadata.
        prov_calls = [
            c for c in recorded
            if c[0] == "query" and "insert into claim_provenance" in c[1].lower()
        ]
        assert prov_calls, "Expected a claim_provenance INSERT to have run"
        params = prov_calls[0][2]
        # raw_metadata is JSON-serialised before binding.
        import json as _json
        raw_meta = _json.loads(params["raw_metadata"])
        assert "multi_llm_verification" in raw_meta, (
            f"Expected multi_llm_verification key in raw_metadata, got: {raw_meta}"
        )
        mv = raw_meta["multi_llm_verification"]
        assert mv["enabled"] is True
        assert mv["primary_model"] == "deepseek-chat-test"
        # 1 corroborated / 2 primary = 0.5 agreement
        assert mv["agreement_score"] == 0.5
        assert mv["corroborated_count"] == 1
        assert mv["primary_count"] == 2
        # Audit item 5: the secondary ran a DISTINCT auditor-persona prompt, and
        # provenance records both prompt names so independence is auditable.
        assert mv["primary_prompt_name"] == "claim_extraction"
        assert mv["secondary_prompt_name"] == "claim_extraction_auditor_persona"

    @pytest.mark.asyncio
    async def test_multi_llm_off_by_default(self, monkeypatch):
        """Phase 5 wave 3: when CLILENS_MULTI_LLM_VERIFY is unset, no verification
        runs and raw_metadata has no `multi_llm_verification` key."""
        import os as _os
        from api import url_analysis_routes
        from app.domains.intelligence import services as intel_services

        monkeypatch.delenv("CLILENS_MULTI_LLM_VERIFY", raising=False)

        async def _fake_fetch(url):
            return {
                "title": "Example",
                "text": "x" * 2000,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }
        monkeypatch.setattr(url_analysis_routes, "fetch_url_content", _fake_fetch)

        class _Claim:
            def __init__(self):
                self.claim_text = "Solar capacity grew 35% in 2022"
                self.claim_type = "factual"
                self.importance_score = 0.8
                self.claim_context = "ctx"

        async def _fake_claims(self_arg, *args, **kwargs):
            return [_Claim()]
        monkeypatch.setattr(intel_services.ClaimExtractor, "decompose_claims", _fake_claims)

        recorded = []

        class _RecorderDB:
            def execute_update(self, query, params=None):
                recorded.append(("update", " ".join((query or "").split()), params or {}))
                return None

            def execute_query(self, query, params=None):
                recorded.append(("query", " ".join((query or "").split()), params or {}))
                normalized = " ".join((query or "").split()).lower()
                if "insert into claim_provenance" in normalized:
                    return [{"id": 1}]
                return []

            def execute_scalar(self, query, params=None):
                return 0

        monkeypatch.setattr(url_analysis_routes, "get_postgres", lambda: _RecorderDB())

        await url_analysis_routes.process_url_analysis_sync(
            analysis_id="aid-default",
            url="https://example.com/default",
            user_id="00000000-0000-0000-0000-000000000000",
        )

        prov_calls = [
            c for c in recorded
            if c[0] == "query" and "insert into claim_provenance" in c[1].lower()
        ]
        assert prov_calls, "Expected provenance insert even when multi-LLM disabled"
        import json as _json
        raw_meta = _json.loads(prov_calls[0][2]["raw_metadata"])
        assert "multi_llm_verification" not in raw_meta

    @pytest.mark.asyncio
    async def test_completed_update_uses_cast_jsonb_not_pg_style(self, monkeypatch):
        """Regression: SQLAlchemy text queries must avoid ':param::jsonb' syntax."""
        from api import url_analysis_routes
        from app.domains.intelligence import services as intel_services

        async def _fake_fetch(url):
            return {
                "title": "Example",
                "text": "x" * 2000,
                "source_name": "example.com",
                "source_domain": "example.com",
                "language_code": "en",
                "published_date": None,
            }

        class _Claim:
            def __init__(self):
                self.claim_text = "Climate policy changed"
                self.claim_type = "factual"
                self.importance_score = 0.8
                self.claim_context = "context"

        async def _fake_claims(self, *args, **kwargs):
            return [_Claim()]

        monkeypatch.setattr(url_analysis_routes, "fetch_url_content", _fake_fetch)
        monkeypatch.setattr(intel_services.ClaimExtractor, "decompose_claims", _fake_claims)

        update_calls: list[str] = []

        class _RecorderDB:
            def execute_update(self, query, params=None):
                update_calls.append(" ".join(query.split()))
                return None

            def execute_query(self, query, params=None):
                if "insert into articles" in " ".join(query.split()).lower():
                    return [{"article_id": "article-1"}]
                return []

        monkeypatch.setattr(url_analysis_routes, "get_postgres", lambda: _RecorderDB())

        await url_analysis_routes.process_url_analysis_sync(
            analysis_id="aid-cast-jsonb",
            url="https://example.com/x",
            user_id="00000000-0000-0000-0000-000000000000",
        )

        completed_updates = [q for q in update_calls if "SET status = 'completed'" in q]
        assert completed_updates, "Expected completed status update query"
        assert all(":claims::jsonb" not in q for q in completed_updates)
        assert any("CAST(:claims AS jsonb)" in q for q in completed_updates)


class TestLongTextClaimExtraction:
    @pytest.mark.asyncio
    async def test_chunk_sampling_spans_document_when_chunk_count_is_capped(self, monkeypatch):
        from api import url_analysis_routes

        monkeypatch.setenv("URL_ANALYSIS_CLAIM_CHUNK_CHARS", "4000")
        monkeypatch.setenv("URL_ANALYSIS_CLAIM_CHUNK_OVERLAP_CHARS", "1000")
        monkeypatch.setenv("URL_ANALYSIS_MAX_CLAIM_CHUNKS", "4")
        monkeypatch.setenv("URL_ANALYSIS_MAX_CLAIMS_PER_CHUNK", "2")

        def _segment(idx: int) -> str:
            marker = f"SEG{idx:02d}|"
            return marker + ("x" * (3000 - len(marker)))

        text = "".join(_segment(i) for i in range(15))

        class _Claim:
            def __init__(self, claim_text: str, importance_score: float):
                self.claim_text = claim_text
                self.claim_type = "factual"
                self.importance_score = importance_score
                self.claim_context = "ctx"

        class _Extractor:
            def __init__(self):
                self.chunk_markers = []

            async def decompose_claims(self, chunk, max_claims):
                assert max_claims >= 1
                assert chunk.startswith("SEG")
                marker = int(chunk[3:5])
                self.chunk_markers.append(marker)
                return [_Claim(claim_text=f"claim-{marker}", importance_score=float(marker))]

        extractor = _Extractor()
        claims = await url_analysis_routes._extract_claims_for_long_text(
            extractor=extractor,
            text=text,
            max_total_claims=12,
        )

        # Regression check: sampling should spread across the full document,
        # not only earliest chunks.
        assert extractor.chunk_markers == [0, 4, 9, 13]
        assert len(claims) == 4

    def test_normalize_claim_text_compacts_whitespace_and_truncates(self):
        from api import url_analysis_routes

        normalized = url_analysis_routes._normalize_claim_text_for_dedupe(
            "  Climate   POLICY\n grew   35% !!!  "
        )
        assert normalized == "climatepolicygrew35%"

        long_key = url_analysis_routes._normalize_claim_text_for_dedupe(("A " * 1000).strip())
        assert len(long_key) == 600
        assert long_key == ("a" * 600)

    def test_dedupe_uses_truncated_key_and_keeps_highest_importance(self):
        from api import url_analysis_routes

        class _Claim:
            def __init__(self, claim_text: str, importance_score: float):
                self.claim_text = claim_text
                self.importance_score = importance_score

        shared_prefix = ("A " * 700).strip()
        lower_importance = _Claim(f"{shared_prefix} first", 0.2)
        higher_importance = _Claim(f"{shared_prefix} second", 0.9)

        deduped = url_analysis_routes._dedupe_claim_objects([lower_importance, higher_importance])

        assert len(deduped) == 1
        assert deduped[0].importance_score == 0.9
