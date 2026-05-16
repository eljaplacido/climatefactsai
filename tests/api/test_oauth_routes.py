"""OAuth route tests.

Covers provider readiness behavior for `/api/auth/oauth/providers`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class TestOAuthProviderReadiness:
    def test_providers_report_disabled_when_env_missing(self, monkeypatch):
        for key in (
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "google-client-id",
            "google-client-secret",
            "MICROSOFT_CLIENT_ID",
            "MICROSOFT_CLIENT_SECRET",
            "microsoft-client-id",
            "microsoft-client-secret",
        ):
            monkeypatch.delenv(key, raising=False)

        resp = client.get("/api/auth/oauth/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["google"] is False
        assert body["microsoft"] is False

    def test_google_provider_uses_uppercase_env_names(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id-value")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret-value")
        for key in ("google-client-id", "google-client-secret"):
            monkeypatch.delenv(key, raising=False)

        resp = client.get("/api/auth/oauth/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["google"] is True

    def test_google_provider_uses_gcp_style_secret_env_names(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("google-client-id", "google-client-id-value")
        monkeypatch.setenv("google-client-secret", "google-client-secret-value")

        resp = client.get("/api/auth/oauth/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["google"] is True


class TestOAuthStateGeneration:
    """`/api/auth/oauth/state` must return a CSRF token that the callback will accept."""

    def test_state_endpoint_returns_url_safe_token(self):
        import re

        resp = client.get("/api/auth/oauth/state")
        assert resp.status_code == 200
        body = resp.json()
        assert "state" in body
        state = body["state"]
        # Must be >= 16 chars (callback rejects shorter) and URL-safe base64
        # (no padding, no slashes). secrets.token_urlsafe(32) gives ~43 chars.
        assert isinstance(state, str)
        assert len(state) >= 16
        assert re.fullmatch(r"[A-Za-z0-9_\-]+", state) is not None


class TestOAuthCallbackValidation:
    """The callback rejects garbage state and unsupported providers before any token exchange."""

    def test_callback_rejects_short_state(self):
        # 8 chars — below the 16-char minimum enforced in oauth_routes.py.
        resp = client.post(
            "/api/auth/oauth/callback",
            json={
                "code": "any-code",
                "redirect_uri": "https://example.com/auth/callback",
                "provider": "google",
                "state": "tooshort",
            },
        )
        assert resp.status_code == 400
        assert "state" in resp.json()["detail"].lower()

    def test_callback_rejects_malformed_state(self):
        # Long enough but contains a disallowed character (space). Backend
        # validates URL-safe base64 charset.
        resp = client.post(
            "/api/auth/oauth/callback",
            json={
                "code": "any-code",
                "redirect_uri": "https://example.com/auth/callback",
                "provider": "google",
                # 32 chars but contains a space halfway
                "state": "abcdefghij klmnopqrstuvwxyz012345",
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "malformed" in detail or "state" in detail

    def test_callback_rejects_unsupported_provider(self, monkeypatch):
        # Configure google so the unsupported-provider check happens *before*
        # any provider-config 501.
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
        resp = client.post(
            "/api/auth/oauth/callback",
            json={
                "code": "any-code",
                "redirect_uri": "https://example.com/auth/callback",
                "provider": "twitter",
                "state": "x" * 32,
            },
        )
        assert resp.status_code == 400
        assert "unsupported provider" in resp.json()["detail"].lower()
