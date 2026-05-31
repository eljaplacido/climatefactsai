"""Pin test for F12a — analytics endpoints must be admin-gated.

The /api/analytics/* surface exposes platform-wide aggregates (country
distribution, verdict distribution, pipeline health) that reveal ingestion
bias and verification-yield internals. Before this fix every endpoint took
only `Depends(get_db)` and was publicly reachable. This test pins the
contract: anonymous → 401, non-admin → 403, admin → 200, on EVERY route.

Run locally with:  python -m pytest tests/api/test_analytics_admin_gate.py -o addopts=""
(the repo pytest.ini addopts require pytest-cov / pytest-xdist which are a
CI-only dependency).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import analytics_routes
from api.auth_routes import get_optional_user


# Every GET route on the analytics router and a representative path for it.
ANALYTICS_PATHS = [
    "/api/analytics/dashboard",
    "/api/analytics/pipeline",
    "/api/analytics/trends",
    "/api/analytics/sources",
    "/api/analytics/claims",
    "/api/analytics/verdicts",
    "/api/analytics/countries",
]


class _StubDB:
    """Returns empty result sets so admin requests reach 200 (not 500)."""

    def execute_query(self, query, params=None):
        return []

    def fetch_all(self, query, params=None):
        return []

    def fetch_one(self, query, params=None):
        return None


def _make_app(user):
    app = FastAPI()
    app.include_router(analytics_routes.router)
    app.dependency_overrides[analytics_routes.get_db] = lambda: _StubDB()
    app.dependency_overrides[get_optional_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ANALYTICS_PATHS)
def test_anonymous_is_rejected_401(path):
    client = _make_app(user=None)
    resp = client.get(path)
    assert resp.status_code == 401, f"{path} should 401 for anonymous, got {resp.status_code}"


@pytest.mark.parametrize("path", ANALYTICS_PATHS)
def test_non_admin_is_rejected_403(path):
    client = _make_app(user={"user_id": "u-1", "subscription_tier": "free", "email": "joe@public.com"})
    resp = client.get(path)
    assert resp.status_code == 403, f"{path} should 403 for non-admin, got {resp.status_code}"


@pytest.mark.parametrize("path", ANALYTICS_PATHS)
def test_enterprise_admin_is_allowed(path):
    client = _make_app(user={"user_id": "u-1", "subscription_tier": "enterprise", "email": "boss@corp.com"})
    resp = client.get(path)
    # Should pass the gate (not 401/403). Data layer is stubbed empty → 200.
    assert resp.status_code == 200, f"{path} should 200 for enterprise admin, got {resp.status_code}"


def test_admin_email_allowlist_is_honoured(monkeypatch):
    """A user whose email is in ADMIN_EMAILS passes even on a non-enterprise tier."""
    monkeypatch.setattr(analytics_routes, "ADMIN_EMAILS", {"admin@cisu.org"})
    client = _make_app(user={"user_id": "u-2", "subscription_tier": "free", "email": "admin@cisu.org"})
    resp = client.get("/api/analytics/dashboard")
    assert resp.status_code == 200


def test_every_router_route_depends_on_the_guard():
    """Structural pin: no analytics GET route may exist without the admin guard.

    Guards against a future route being added that forgets the dependency.
    """
    guarded = 0
    for route in analytics_routes.router.routes:
        deps = getattr(getattr(route, "dependant", None), "dependencies", [])
        names = {getattr(d.call, "__name__", "") for d in deps}
        # also include sub-dependencies' call names
        flat = set(names)
        for d in deps:
            for sub in getattr(d, "dependencies", []):
                flat.add(getattr(sub.call, "__name__", ""))
        assert "require_analytics_admin" in flat, (
            f"Route {getattr(route, 'path', route)} is missing require_analytics_admin"
        )
        guarded += 1
    assert guarded == len(ANALYTICS_PATHS), f"expected {len(ANALYTICS_PATHS)} guarded routes, found {guarded}"
