"""Endpoint-level integration tests for the Phase 1A quota gate (2026-05-23).

Pins:
- POST /api/analyze-url returns HTTP 429 with structured envelope when the
  quota service blocks (anonymous traffic, freemium over-limit, etc.)
- The 429 response body contains the upgrade_url, used, limit, and a
  human-readable message — the frontend reads this verbatim to render the
  upgrade modal.
- The quota check fires BEFORE any background work; failing the check
  must not create url_analyses rows or kick off processing.
- GET /api/quota responds without authentication and returns the
  anonymous-zero envelope when no token is present.

These complement the pure-unit tests in test_quota_service.py — they
exercise the FastAPI request/response cycle so we catch wiring bugs
(missing middleware, wrong exception serialisation, etc.).
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/quota — anonymous access
# ---------------------------------------------------------------------------


class TestQuotaSummaryEndpoint:
    def test_anonymous_get_returns_zero_envelope(self):
        resp = client.get("/api/quota")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == "anonymous"
        assert isinstance(body["quotas"], list)
        # Anonymous users are 0/0 on every quota
        for q in body["quotas"]:
            assert q["limit"] == 0
            assert q["allowed"] is False
            assert q["upgrade_url"] == "/dashboard/subscription"

    def test_anonymous_covers_all_five_quota_keys(self):
        resp = client.get("/api/quota")
        body = resp.json()
        keys = {q["quota_key"] for q in body["quotas"]}
        # The 3/3/2 decision + url_analysis + compare = 5 keys
        assert keys == {
            "saved_articles",
            "saved_searches",
            "deep_research",
            "url_analysis",
            "compare",
        }

    def test_single_quota_endpoint_returns_one_key(self):
        resp = client.get("/api/quota/saved_articles")
        assert resp.status_code == 200
        body = resp.json()
        assert body["quota_key"] == "saved_articles"
        assert body["period"] == "lifetime"

    def test_single_quota_endpoint_404s_on_unknown_key(self):
        resp = client.get("/api/quota/email_quota")
        assert resp.status_code == 404
        assert "Unknown" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/analyze-url — quota gate fires BEFORE work
# ---------------------------------------------------------------------------


class TestUrlAnalysisQuotaGate:
    def test_anonymous_submission_returns_429_with_structured_envelope(self):
        """Anonymous traffic gets url_analysis: 0 on the ladder, so the
        first request MUST 429. Body is the structured envelope the
        upgrade modal reads."""
        # _validate_safe_url runs first (raises 422 if URL invalid). Use a
        # safe-looking URL so we get past validation into the quota gate.
        import socket

        with patch.object(
            socket,
            "getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
        ):
            resp = client.post(
                "/api/analyze-url",
                json={"url": "https://example.com/climate-article"},
            )

        assert resp.status_code == 429, resp.text
        body = resp.json()
        assert "detail" in body
        detail = body["detail"]
        assert detail["error"] == "quota_exceeded"
        assert detail["quota"]["quota_key"] == "url_analysis"
        assert detail["quota"]["limit"] == 0
        assert detail["quota"]["upgrade_url"] == "/dashboard/subscription"
        assert "Upgrade" in detail["message"]

    def test_quota_429_skips_background_work(self):
        """A blocked quota MUST short-circuit the request — no DB writes
        to url_analyses, no background task queued. Pin this by asserting
        the row-insert function is never called."""
        import socket
        from api import url_analysis_routes as url_mod

        with patch.object(
            socket,
            "getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
        ), patch.object(url_mod, "_insert_url_analysis_record") as mock_insert:
            resp = client.post(
                "/api/analyze-url",
                json={"url": "https://example.com/article-1"},
            )

        assert resp.status_code == 429
        # The structured-failure unit tests cover what _insert does on the
        # happy path; here we just pin that it's NEVER called when blocked.
        mock_insert.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/deep-search/compare — quota gate fires BEFORE work
# ---------------------------------------------------------------------------


class TestCompareQuotaGate:
    def test_compare_at_quota_returns_429(self):
        """When the quota service blocks a compare request, the endpoint
        MUST surface the structured 429 envelope. Pin by forcing the
        service to raise — equivalent to a freemium user who has already
        used their 1 compare/month.

        Note: anonymous users currently get freemium DEFAULTS on this
        route (existing routing pattern across the codebase), so the
        first compare is allowed (0 used of 1 limit). This test pins
        the over-limit behavior instead, which is what the quota gate
        is actually for."""
        from fastapi import HTTPException, status
        from api import quota_service

        def _fake_check_and_raise(*args, **kwargs):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "quota": {
                        "quota_key": "compare",
                        "allowed": False,
                        "used": 1,
                        "limit": 1,
                        "period": "monthly",
                        "reset_at": None,
                        "upgrade_url": "/dashboard/subscription",
                        "tier": "freemium",
                        "label": "topic comparisons",
                    },
                    "message": "You've used 1 of 1 topic comparisons on the freemium tier (monthly). Upgrade for higher limits.",
                },
            )

        with patch.object(
            quota_service.QuotaService,
            "check_and_raise",
            side_effect=_fake_check_and_raise,
        ):
            resp = client.post(
                "/api/deep-search/compare",
                json={
                    "query_a": "Arctic ice melt acceleration",
                    "query_b": "Antarctic ice shelf loss",
                },
            )

        assert resp.status_code == 429, resp.text
        body = resp.json()
        detail = body["detail"]
        assert detail["error"] == "quota_exceeded"
        assert detail["quota"]["quota_key"] == "compare"
        assert detail["quota"]["limit"] == 1
        assert "Upgrade" in detail["message"]
