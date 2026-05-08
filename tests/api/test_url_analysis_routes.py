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


# ---------------------------------------------------------------------------
# GET /api/analyze-url/{job_id}
# ---------------------------------------------------------------------------

class TestAnalyzeUrlGet:
    """Status endpoint returns analysis row and stringifies the UUID."""

    def test_get_analysis_casts_uuid_to_str(self, client):
        """Regression for ace5787: UUID column must be returned as str."""
        from uuid import UUID
        import shared.database as _shared_db

        analysis_uuid = UUID("12345678-1234-5678-1234-567812345678")
        now = datetime.utcnow()
        rows = [{
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
            resp = client.get(f"/api/analyze-url/{analysis_uuid}")
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
            resp = client.get("/api/analyze-url/00000000-0000-0000-0000-000000000000")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_analysis_parses_jsonb_string_claims(self, client):
        """When extracted_claims is stored as a JSON string, route must parse it."""
        import shared.database as _shared_db
        from uuid import UUID

        analysis_uuid = UUID("11111111-2222-3333-4444-555555555555")
        rows = [{
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
            resp = client.get(f"/api/analyze-url/{analysis_uuid}")
        finally:
            _shared_db._postgres_client = prior

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["extracted_claims"], list)
        assert data["extracted_claims"][0]["claim_text"] == "Solar grew 35%"
        assert data["fact_checks"] == []


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
