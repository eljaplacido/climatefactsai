"""Unit tests for /api/feedback/topic/* — Stage 3 / M4 corpus feedback."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.auth_routes import get_optional_user


client = TestClient(app)


class _StubDB:
    def __init__(self, responses=None, update_returns=1):
        self.responses = responses or []
        self.updates: list[tuple[str, dict]] = []
        self.update_returns = update_returns

    def execute_query(self, sql, params=None):
        if not self.responses:
            return []
        return self.responses.pop(0)

    def execute_update(self, sql, params=None):
        self.updates.append((sql, params or {}))
        return self.update_returns


class TestSubmitTopicFeedback:
    def test_404_when_article_missing(self):
        stub = _StubDB([[]])  # article-exists check returns nothing
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.post(
                "/api/feedback/topic/00000000-0000-0000-0000-000000000000",
                json={"verdict": "off_topic"},
            )
        assert r.status_code == 404

    def test_valid_off_topic_recorded(self):
        stub = _StubDB([[{"1": 1}]])  # article exists
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.post(
                "/api/feedback/topic/11111111-1111-1111-1111-111111111111",
                json={
                    "verdict": "off_topic",
                    "reason": "Slovenian housing-loan article, not climate",
                    "off_topic_category": "finance",
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "recorded"
        assert body["verdict"] == "off_topic"
        # INSERT happened with the right params
        assert len(stub.updates) == 1
        params = stub.updates[0][1]
        assert params["v"] == "off_topic"
        assert params["cat"] == "finance"

    def test_invalid_verdict_rejected(self):
        # Pydantic pattern guard on verdict — must be one of the 3 valid values
        r = client.post(
            "/api/feedback/topic/11111111-1111-1111-1111-111111111111",
            json={"verdict": "garbage"},
        )
        assert r.status_code == 422


class TestListOffTopicIds:
    def test_empty_list(self):
        stub = _StubDB([[]])
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.get("/api/feedback/topic/off-topic-ids")
        assert r.status_code == 200
        body = r.json()
        assert body["off_topic_ids"] == []
        assert body["total"] == 0

    def test_populated_list(self):
        stub = _StubDB([
            [{"aid": "a1"}, {"aid": "a2"}, {"aid": "a3"}]
        ])
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.get("/api/feedback/topic/off-topic-ids")
        assert r.status_code == 200
        body = r.json()
        assert body["off_topic_ids"] == ["a1", "a2", "a3"]
        assert body["total"] == 3


class TestPerArticleFeedback:
    def test_shows_consensus_counts(self):
        stub = _StubDB([
            [
                {"feedback_id": "f1", "verdict": "off_topic",
                 "reason": "politics", "off_topic_category": "politics",
                 "reporter_id": None, "created_at": "2026-05-27"},
                {"feedback_id": "f2", "verdict": "off_topic",
                 "reason": None, "off_topic_category": "general_news",
                 "reporter_id": "user-1", "created_at": "2026-05-27"},
                {"feedback_id": "f3", "verdict": "on_topic",
                 "reason": "actually about emissions",
                 "off_topic_category": None,
                 "reporter_id": "user-2", "created_at": "2026-05-27"},
            ]
        ])
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.get("/api/feedback/topic/11111111-1111-1111-1111-111111111111")
        assert r.status_code == 200
        body = r.json()
        assert body["off_topic_count"] == 2
        assert body["on_topic_count"] == 1
        assert body["is_flagged"] is True


class TestDisplayFlagApplied:
    """F1: feedback now drives articles.is_off_topic (mig 056) so the report
    button actually hides/unhides from listing surfaces — but safely."""

    def test_on_topic_clears_flag_for_anyone(self):
        # on_topic is an un-hide; safe for anonymous reporters.
        stub = _StubDB([[{"1": 1}]])
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.post(
                "/api/feedback/topic/11111111-1111-1111-1111-111111111111",
                json={"verdict": "on_topic"},
            )
        assert r.status_code == 200
        assert r.json()["display_flag_applied"] is True
        # INSERT + UPDATE(is_off_topic = FALSE)
        assert len(stub.updates) == 2
        assert "is_off_topic = FALSE" in stub.updates[1][0]

    def test_anonymous_off_topic_does_not_hide(self):
        # Abuse guard: a single anon off_topic flag must NOT hide the article.
        stub = _StubDB([[{"1": 1}]])
        with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
            r = client.post(
                "/api/feedback/topic/11111111-1111-1111-1111-111111111111",
                json={"verdict": "off_topic"},
            )
        assert r.status_code == 200
        assert r.json()["display_flag_applied"] is False
        # only the INSERT — no display UPDATE
        assert len(stub.updates) == 1

    def test_authenticated_off_topic_hides(self):
        stub = _StubDB([[{"1": 1}]])
        app.dependency_overrides[get_optional_user] = lambda: {"user_id": "u-1"}
        try:
            with patch("api.topic_feedback_routes.get_postgres", return_value=stub):
                r = client.post(
                    "/api/feedback/topic/11111111-1111-1111-1111-111111111111",
                    json={"verdict": "off_topic", "off_topic_category": "crime"},
                )
        finally:
            app.dependency_overrides.pop(get_optional_user, None)
        assert r.status_code == 200
        assert r.json()["display_flag_applied"] is True
        assert len(stub.updates) == 2
        assert "is_off_topic = TRUE" in stub.updates[1][0]
