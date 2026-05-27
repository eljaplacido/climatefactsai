"""Unit tests for /api/status/* — public platform-status endpoints.

Covers the contract a frontend (or a curl session) relies on:
  * GET /api/status/gx10 returns a deterministic shape
  * lane_a_health classification: healthy / degraded / stalled
  * GET /api/status/summary aggregates without surfacing PII
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class _StubDB:
    """Returns canned rows in FIFO order; records every (sql, params)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def execute_query(self, sql, params=None):
        self.calls.append((sql, params or {}))
        if not self.responses:
            return []
        return self.responses.pop(0)

    def execute_update(self, sql, params=None):
        return 1


class TestGx10Status:
    def test_healthy_when_gx10_produces_enrichments(self):
        # Order in status_routes.get_gx10_status:
        #   1. enrichments-by-provider GROUP BY
        #   2. latest enriched
        #   3. entities last 24h
        #   4. article_entities last 24h
        #   5. latest entity
        #   6. off_topic count
        stub = _StubDB(
            [
                [{"provider": "local-gx10", "n": 42}, {"provider": "deepseek", "n": 3}],
                [
                    {
                        "article_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "title": "Sample climate article",
                        "enriched_at": datetime.now(timezone.utc),
                        "provider": "local-gx10",
                        "model": "qwen2.5:7b-instruct",
                    }
                ],
                [{"n": 17}],
                [{"n": 35}],
                [
                    {
                        "entity_name": "European Union",
                        "entity_type": "ORGANIZATION",
                        "first_seen_at": datetime.now(timezone.utc),
                    }
                ],
                [{"n": 962}],
            ]
        )
        with patch("api.status_routes.get_postgres", return_value=stub):
            r = client.get("/api/status/gx10")
        assert r.status_code == 200
        body = r.json()
        assert body["enrichments_24h"] == 45
        assert body["enrichments_24h_local_gx10"] == 42
        assert body["entities_24h"] == 17
        assert body["article_entities_24h"] == 35
        assert body["topic_feedback_off_topic"] == 962
        assert body["lane_a_health"] == "healthy"
        assert body["latest_enriched"]["provider"] == "local-gx10"
        assert body["latest_entity"]["type"] == "ORGANIZATION"

    def test_degraded_when_only_cloud_fallbacks_run(self):
        stub = _StubDB(
            [
                [{"provider": "deepseek", "n": 12}],
                [],
                [{"n": 0}],
                [{"n": 0}],
                [],
                [{"n": 100}],
            ]
        )
        with patch("api.status_routes.get_postgres", return_value=stub):
            r = client.get("/api/status/gx10")
        body = r.json()
        assert body["enrichments_24h"] == 12
        assert body["enrichments_24h_local_gx10"] == 0
        assert body["lane_a_health"] == "degraded"

    def test_stalled_when_no_activity(self):
        stub = _StubDB([[], [], [{"n": 0}], [{"n": 0}], [], [{"n": 0}]])
        with patch("api.status_routes.get_postgres", return_value=stub):
            r = client.get("/api/status/gx10")
        body = r.json()
        assert body["enrichments_24h"] == 0
        assert body["lane_a_health"] == "stalled"
        assert body["latest_enriched"] is None
        assert body["latest_entity"] is None

    def test_chained_provider_string_counts_as_gx10(self):
        # When Lane A falls through GX10 -> deepseek, llm_provider stamps
        # the comma-joined chain. Anything STARTING with local-gx10 should
        # count toward the gx10 number.
        stub = _StubDB(
            [
                [
                    {"provider": "local-gx10,deepseek", "n": 8},
                    {"provider": "local-gx10", "n": 30},
                ],
                [],
                [{"n": 5}],
                [{"n": 10}],
                [],
                [{"n": 50}],
            ]
        )
        with patch("api.status_routes.get_postgres", return_value=stub):
            r = client.get("/api/status/gx10")
        body = r.json()
        assert body["enrichments_24h_local_gx10"] == 38

    def test_db_error_degrades_to_zero_not_500(self):
        class BoomDB:
            def execute_query(self, *a, **kw):
                raise RuntimeError("DB connection lost")

        with patch("api.status_routes.get_postgres", return_value=BoomDB()):
            r = client.get("/api/status/gx10")
        assert r.status_code == 200
        body = r.json()
        assert body["enrichments_24h"] == 0
        assert body["lane_a_health"] == "stalled"


class TestPlatformSummary:
    def test_summary_aggregates_counts(self):
        stub = _StubDB(
            [
                [{"n": 14797}],     # articles_total
                [{"n": 12500}],     # articles_enriched
                [{"n": 220}],       # companies_total
                [{"n": 8400}],      # entities_total
                [{"n": 70}],        # url_analyses_total
                [{"n": 962}],       # off_topic_flagged
                [{"n": 168}],       # rss_feeds_active
            ]
        )
        with patch("api.status_routes.get_postgres", return_value=stub):
            r = client.get("/api/status/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["articles_total"] == 14797
        assert body["articles_enriched"] == 12500
        assert body["companies_total"] == 220
        assert body["entities_total"] == 8400
        assert body["url_analyses_total"] == 70
        assert body["off_topic_flagged"] == 962
        assert body["rss_feeds_active"] == 168
        assert "server_time" in body

    def test_summary_db_error_returns_zeros_not_500(self):
        class BoomDB:
            def execute_query(self, *a, **kw):
                raise RuntimeError("DB connection lost")

        with patch("api.status_routes.get_postgres", return_value=BoomDB()):
            r = client.get("/api/status/summary")
        assert r.status_code == 200
        body = r.json()
        # All counts default to 0 on failure rather than hard-failing
        for key in (
            "articles_total",
            "articles_enriched",
            "companies_total",
            "entities_total",
            "url_analyses_total",
            "off_topic_flagged",
            "rss_feeds_active",
        ):
            assert body[key] == 0
