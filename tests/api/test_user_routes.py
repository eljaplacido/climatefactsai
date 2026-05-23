"""User routes regressions.

Covers bookmark status endpoint used by frontend bookmark sync.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


@pytest.fixture
def auth_headers(request):
    """Create an authenticated user and return Authorization header."""
    unique_email = f"bookmark_{request.node.name}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePass123!",
            "full_name": "Bookmark Tester",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestBookmarkStatus:
    def test_status_returns_false_when_not_bookmarked(self, auth_headers):
        resp = client.get("/api/user/bookmarks/article-0001/status", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["article_id"] == "article-0001"
        assert body["bookmarked"] is False

    def test_status_returns_true_after_creating_bookmark(self, auth_headers):
        create = client.post(
            "/api/user/bookmarks/article-0001",
            headers=auth_headers,
            json={"folder": "default", "notes": "interesting"},
        )
        assert create.status_code == 200

        resp = client.get("/api/user/bookmarks/article-0001/status", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["article_id"] == "article-0001"
        assert body["bookmarked"] is True
        assert body["folder"] == "default"
        assert body["notes"] == "interesting"
