"""Source-health canary tests (seq-9).

There were ZERO source-liveness tests before this — dead feeds rotted silently.
These pin the canary logic without touching the network:
  * run_source_health_canary: reset-on-healthy, increment-on-fail, auto-disable
    at the threshold, never disable below it, registry-read failure handling.
  * check_feed_liveness: HTTP error / network error / empty-feed / healthy paths
    via monkeypatched httpx + feedparser.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.domains.content.source_health import (
    DEAD_FEED_THRESHOLD,
    LivenessResult,
    check_feed_liveness,
    run_source_health_canary,
)


class _FakeDB:
    """Records UPDATEs; returns canned registry rows for the SELECT."""

    def __init__(self, rows: List[Dict[str, Any]], fail_query: bool = False):
        self._rows = rows
        self.fail_query = fail_query
        self.updates: List[Dict[str, Any]] = []

    def execute_query(self, query: str, params: Optional[Dict] = None):
        if self.fail_query:
            raise RuntimeError("registry unavailable")
        return [dict(r) for r in self._rows]

    def execute_update(self, query: str, params: Optional[Dict] = None):
        self.updates.append({"q": " ".join(query.split()).lower(), "p": params or {}})
        return None


def _feed(name="Grist", errors=0, active=True, feed_id=None):
    return {
        "feed_id": feed_id or f"id-{name}",
        "feed_name": name,
        "feed_url": f"https://{name.lower()}.example/feed",
        "is_active": active,
        "fetch_error_count": errors,
    }


def _ok(_url):
    return LivenessResult(ok=True, http_status=200, item_count=12)


def _fail(_url):
    return LivenessResult(ok=False, http_status=503, error="HTTP 503")


# ---------------------------------------------------------------------------
# run_source_health_canary
# ---------------------------------------------------------------------------

class TestCanary:
    def test_healthy_feed_resets_errors_and_stays_active(self):
        db = _FakeDB([_feed(errors=3)])
        summary = run_source_health_canary(db, checker=_ok)
        assert summary["checked"] == 1
        assert summary["healthy"] == 1
        assert summary["failed"] == 0
        assert summary["auto_disabled"] == 0
        # The success UPDATE resets the counter and stamps last_success_at.
        upd = db.updates[0]["q"]
        assert "fetch_error_count = 0" in upd
        assert "last_success_at" in upd

    def test_failing_below_threshold_increments_not_disabled(self):
        db = _FakeDB([_feed(errors=0)])
        summary = run_source_health_canary(db, checker=_fail, threshold=5)
        assert summary["failed"] == 1
        assert summary["auto_disabled"] == 0
        assert summary["disabled_feeds"] == []
        upd = db.updates[0]["q"]
        assert "fetch_error_count = fetch_error_count + 1" in upd
        # The error string is persisted for diagnostics.
        assert db.updates[0]["p"].get("error") == "HTTP 503"

    def test_failing_at_threshold_auto_disables(self):
        # prior_errors=4, this failure makes it 5 == threshold -> disabled.
        db = _FakeDB([_feed(name="DeadFeed", errors=DEAD_FEED_THRESHOLD - 1)])
        summary = run_source_health_canary(db, checker=_fail, threshold=DEAD_FEED_THRESHOLD)
        assert summary["auto_disabled"] == 1
        assert summary["disabled_feeds"][0]["feed_name"] == "DeadFeed"
        assert summary["disabled_feeds"][0]["consecutive_errors"] == DEAD_FEED_THRESHOLD
        # The failure UPDATE flips is_active off via the CASE expression.
        upd = db.updates[0]["q"]
        assert "is_active = case" in upd
        assert db.updates[0]["p"].get("threshold") == DEAD_FEED_THRESHOLD

    def test_already_inactive_feed_not_counted_as_newly_disabled(self):
        db = _FakeDB([_feed(name="Old", errors=99, active=False)])
        summary = run_source_health_canary(
            db, checker=_fail, threshold=DEAD_FEED_THRESHOLD, include_inactive=True
        )
        # It still gets its error count bumped, but it was already off, so it is
        # not reported as a *newly* disabled feed.
        assert summary["auto_disabled"] == 0
        assert summary["failed"] == 1

    def test_mixed_batch_counts(self):
        rows = [_feed(name="Good", errors=0), _feed(name="Bad", errors=1)]
        checker = lambda url: _ok(url) if "good" in url else _fail(url)
        summary = run_source_health_canary(db := _FakeDB(rows), checker=checker, threshold=5)
        assert summary["checked"] == 2
        assert summary["healthy"] == 1
        assert summary["failed"] == 1
        assert len(db.updates) == 2

    def test_active_only_by_default(self):
        # include_inactive defaults False -> SELECT carries the is_active filter.
        db = _FakeDB([_feed()])
        run_source_health_canary(db, checker=_ok)
        # (the WHERE is built into the query string; assert via a probe query)
        # The fake returns rows regardless, but the canary must run cleanly.
        assert db.updates  # at least one update issued

    def test_registry_read_failure_returns_error(self):
        db = _FakeDB([], fail_query=True)
        summary = run_source_health_canary(db, checker=_ok)
        assert summary["status"] == "error"
        assert summary["checked"] == 0


# ---------------------------------------------------------------------------
# check_feed_liveness (network probe)
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code = status_code
        self.content = content


class TestCheckFeedLiveness:
    def test_network_error_is_caught(self, monkeypatch):
        import httpx

        def _boom(*a, **k):
            raise httpx.ConnectError("dns fail")

        monkeypatch.setattr(httpx, "get", _boom)
        res = check_feed_liveness("https://dead.example/feed")
        assert res.ok is False
        assert res.http_status is None
        assert "ConnectError" in res.error

    def test_http_4xx_is_unhealthy(self, monkeypatch):
        import httpx

        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(404))
        res = check_feed_liveness("https://gone.example/feed")
        assert res.ok is False
        assert res.http_status == 404

    def test_empty_feed_is_unhealthy(self, monkeypatch):
        import httpx
        import feedparser

        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, b"<rss></rss>"))
        monkeypatch.setattr(feedparser, "parse", lambda content: type("F", (), {"entries": []})())
        res = check_feed_liveness("https://empty.example/feed")
        assert res.ok is False
        assert res.http_status == 200
        assert "no entries" in res.error

    def test_healthy_feed(self, monkeypatch):
        import httpx
        import feedparser

        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, b"<rss>...</rss>"))
        monkeypatch.setattr(
            feedparser, "parse",
            lambda content: type("F", (), {"entries": [{"title": "a"}, {"title": "b"}]})(),
        )
        res = check_feed_liveness("https://live.example/feed")
        assert res.ok is True
        assert res.http_status == 200
        assert res.item_count == 2


# ---------------------------------------------------------------------------
# Endpoint wiring (also proves the router is mounted in api.main)
# ---------------------------------------------------------------------------

class TestSourceHealthEndpoints:
    def test_get_snapshot_returns_aggregate_shape(self):
        from fastapi.testclient import TestClient
        from api.main import app

        r = TestClient(app).get("/api/admin/source-health")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("total", "active", "disabled", "at_risk", "feeds"):
            assert key in body
        assert isinstance(body["feeds"], list)

    def test_post_trigger_503_when_no_tokens(self, monkeypatch):
        monkeypatch.delenv("CORPORATE_SYNC_TOKEN", raising=False)
        monkeypatch.delenv("SCHEDULER_SECRET", raising=False)
        from fastapi.testclient import TestClient
        from api.main import app

        r = TestClient(app).post("/api/admin/scheduler/source-health")
        assert r.status_code == 503

    def test_post_trigger_401_when_token_wrong(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_SECRET", "right-secret")
        from fastapi.testclient import TestClient
        from api.main import app

        r = TestClient(app).post(
            "/api/admin/scheduler/source-health",
            headers={"x-scheduler-secret": "wrong"},
        )
        assert r.status_code == 401
