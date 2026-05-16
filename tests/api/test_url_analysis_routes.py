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
    async def test_declared_content_length_above_limit_returns_400(self, monkeypatch):
        from api import url_analysis_routes
        from fastapi import HTTPException

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

        with pytest.raises(HTTPException) as exc:
            await url_analysis_routes.fetch_url_content("https://example.com/too-big")
        assert exc.value.status_code == 400
        assert "Response too large" in str(exc.value.detail)

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
