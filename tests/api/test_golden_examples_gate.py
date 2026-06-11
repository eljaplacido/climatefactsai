"""Golden-examples promotion is admin/curator-gated (2026-06-10 audit).

Promoting an artifact seeds LoRA training data for the GX10 specialists, so
it must not be open to any logged-in user — enterprise tier or an
ADMIN_EMAILS address only.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.auth_routes import get_current_user

client = TestClient(app)

_PROMOTE_BODY = {
    "artifact_kind": "article_enrichment",
    "artifact_ref": "art-1",
    "why_golden": "An exemplary enrichment with full provenance.",
    "quality_score": 5,
}


def _override_user(user: dict):
    app.dependency_overrides[get_current_user] = lambda: user


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def test_non_admin_user_is_forbidden():
    _override_user({"user_id": "u1", "email": "x@y.z", "subscription_tier": "freemium"})
    try:
        r = client.post("/api/golden-examples", json=_PROMOTE_BODY)
        assert r.status_code == 403
    finally:
        _clear()


def test_enterprise_tier_is_allowed():
    _override_user({"user_id": "u2", "email": "boss@corp.com", "subscription_tier": "enterprise"})

    class _DB:
        def execute_update(self, q, p=None):
            return 1

    try:
        with patch("api.golden_examples_routes.get_postgres", return_value=_DB()):
            r = client.post("/api/golden-examples", json=_PROMOTE_BODY)
        assert r.status_code == 200
    finally:
        _clear()


def test_admin_email_is_allowed(monkeypatch):
    monkeypatch.setattr("api.admin_pipeline_routes.ADMIN_EMAILS", {"admin@climatefacts.ai"})
    _override_user({"user_id": "u3", "email": "admin@climatefacts.ai", "subscription_tier": "freemium"})

    class _DB:
        def execute_update(self, q, p=None):
            return 1

    try:
        with patch("api.golden_examples_routes.get_postgres", return_value=_DB()):
            r = client.post("/api/golden-examples", json=_PROMOTE_BODY)
        assert r.status_code == 200
    finally:
        _clear()
