"""Tests for the scheduler-triggered AOI poll endpoint — Phase 4B (2026-05-23).

Pins:
  - Secret gate: missing/wrong X-Scheduler-Secret = 403
  - Production deployment with unset SCHEDULER_SECRET = 503 (fail-closed)
  - Successful run returns `{status, task, summary}` envelope
  - poll_all_active failure is caught and returned as a logged error
    (NOT raised) so Cloud Scheduler doesn't retry-storm
  - Missing aoi_poll_service module = 503 ImportError path
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class TestSchedulerAOIPollGating:
    def test_no_secret_set_locally_accepts_no_header(self, monkeypatch):
        """When SCHEDULER_SECRET is empty AND ENVIRONMENT is dev/test,
        the endpoint accepts an unauthenticated call (matches existing
        scheduler routes' behaviour)."""
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "")
        monkeypatch.setenv("ENVIRONMENT", "test")

        with patch("api.aoi_poll_service.poll_all_active") as mock_poll:
            mock_summary = MagicMock()
            mock_summary.to_dict.return_value = {
                "total_subscriptions_checked": 0,
                "fire_count": 0,
            }
            mock_poll.return_value = mock_summary
            resp = client.post("/api/scheduler/aoi-poll")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["task"] == "aoi_poll"

    def test_wrong_secret_returns_403(self, monkeypatch):
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "expected-secret")
        resp = client.post(
            "/api/scheduler/aoi-poll",
            headers={"X-Scheduler-Secret": "wrong"},
        )
        assert resp.status_code == 403

    def test_missing_secret_with_secret_set_returns_403(self, monkeypatch):
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "expected-secret")
        resp = client.post("/api/scheduler/aoi-poll")
        assert resp.status_code == 403

    def test_correct_secret_runs_poll(self, monkeypatch):
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "right-key")

        with patch("api.aoi_poll_service.poll_all_active") as mock_poll:
            mock_summary = MagicMock()
            mock_summary.to_dict.return_value = {
                "total_subscriptions_checked": 5,
                "fire_count": 2,
            }
            mock_poll.return_value = mock_summary

            resp = client.post(
                "/api/scheduler/aoi-poll",
                headers={"X-Scheduler-Secret": "right-key"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["summary"]["fire_count"] == 2
        mock_poll.assert_called_once()

    def test_production_without_secret_returns_503(self, monkeypatch):
        """Critical fail-closed property: deploying to prod with
        SCHEDULER_SECRET unset MUST refuse to serve. Previously this
        was a silent no-op that left /api/scheduler/* publicly callable."""
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "")
        monkeypatch.setenv("ENVIRONMENT", "production")
        resp = client.post("/api/scheduler/aoi-poll")
        assert resp.status_code == 503
        assert "SCHEDULER_SECRET" in resp.json()["detail"]


class TestSchedulerAOIPollFailureModes:
    def test_poll_exception_returns_200_with_error_envelope_not_500(self, monkeypatch):
        """Cloud Scheduler retries 4xx/5xx aggressively — we'd rather log
        the failure inline and return 200 so the next tick tries fresh
        than enter a retry storm.

        Past incident: a scheduler returning 500 in a tight loop is what
        broke us before. Pin this with a test."""
        monkeypatch.setattr("api.scheduler_routes.SCHEDULER_SECRET", "")
        monkeypatch.setenv("ENVIRONMENT", "test")

        with patch(
            "api.aoi_poll_service.poll_all_active",
            side_effect=RuntimeError("postgres down"),
        ):
            resp = client.post("/api/scheduler/aoi-poll")
        # NOT 500 — error-envelope at 200
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["task"] == "aoi_poll"
        assert "postgres down" in body["error"]
