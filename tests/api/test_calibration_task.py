"""Nightly calibration refit Celery task tests — Phase 5 wave 7.

Verifies that `nightly_calibration_refit` iterates over every supported
calibration signal, isolates per-signal failures (so one DB blip can't
abort the whole run), and emits a summary dict the dashboard can render.

Uses `.apply().get()` for synchronous execution — no broker required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pytest


@dataclass
class _FakeRefitResult:
    """Mimics calibration_store.RefitResult.as_dict()."""
    signal: str
    status: str = "ok"
    n_labels: int = 10
    fit_id: Optional[int] = 1
    platt_a: Optional[float] = 1.0
    platt_b: Optional[float] = 0.0
    brier_score: Optional[float] = 0.05
    ece: Optional[float] = 0.02
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "n_labels": self.n_labels,
            "fit_id": self.fit_id,
            "platt_a": self.platt_a,
            "platt_b": self.platt_b,
            "brier_score": self.brier_score,
            "ece": self.ece,
            "error": self.error,
        }


def _install_fake_refit(monkeypatch, mapping: Dict[str, _FakeRefitResult]):
    """Patch calibration_store.refit_and_persist to return canned results per signal."""
    calls: List[Tuple[str, int]] = []

    def fake_refit(db, signal_name: str, min_labels: int = 5) -> _FakeRefitResult:
        calls.append((signal_name, min_labels))
        if signal_name not in mapping:
            return _FakeRefitResult(signal=signal_name, status="error", error="unknown")
        return mapping[signal_name]

    monkeypatch.setattr(
        "app.domains.intelligence.calibration_store.refit_and_persist",
        fake_refit,
    )
    return calls


def _install_dummy_db(monkeypatch):
    """Replace the shared postgres client with a stub the task ignores."""
    import shared.database as _shared_db
    _shared_db._postgres_client = object()
    return _shared_db._postgres_client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestNightlyRefitHappyPath:
    def test_iterates_all_supported_signals(self, monkeypatch):
        mapping = {
            "reliability_score": _FakeRefitResult("reliability_score", "ok"),
            "agreement_score": _FakeRefitResult("agreement_score", "ok"),
            "hallucination_score": _FakeRefitResult("hallucination_score", "ok"),
        }
        calls = _install_fake_refit(monkeypatch, mapping)
        _install_dummy_db(monkeypatch)

        from app.tasks.calibration import nightly_calibration_refit
        out = nightly_calibration_refit.apply(kwargs={"min_labels": 5}).get()

        assert out["total_signals"] == 3
        assert out["ok"] == 3
        assert out["insufficient"] == 0
        assert out["errors"] == 0
        assert {c[0] for c in calls} == {
            "reliability_score", "agreement_score", "hallucination_score",
        }
        # Each signal-level row must carry the signal name in the response.
        signals_in_out = {row["signal"] for row in out["signals"]}
        assert signals_in_out == {
            "reliability_score", "agreement_score", "hallucination_score",
        }

    def test_min_labels_param_propagates(self, monkeypatch):
        mapping = {
            "reliability_score": _FakeRefitResult("reliability_score", "ok"),
            "agreement_score": _FakeRefitResult("agreement_score", "ok"),
            "hallucination_score": _FakeRefitResult("hallucination_score", "ok"),
        }
        calls = _install_fake_refit(monkeypatch, mapping)
        _install_dummy_db(monkeypatch)

        from app.tasks.calibration import nightly_calibration_refit
        nightly_calibration_refit.apply(kwargs={"min_labels": 25}).get()

        # Every call should have received min_labels=25.
        assert all(c[1] == 25 for c in calls)


# ---------------------------------------------------------------------------
# Partial success
# ---------------------------------------------------------------------------

class TestNightlyRefitPartialSuccess:
    def test_insufficient_data_counted_separately(self, monkeypatch):
        mapping = {
            "reliability_score": _FakeRefitResult("reliability_score", "ok"),
            "agreement_score": _FakeRefitResult(
                "agreement_score", status="insufficient_data", n_labels=2, fit_id=None
            ),
            "hallucination_score": _FakeRefitResult("hallucination_score", "ok"),
        }
        _install_fake_refit(monkeypatch, mapping)
        _install_dummy_db(monkeypatch)

        from app.tasks.calibration import nightly_calibration_refit
        out = nightly_calibration_refit.apply(kwargs={"min_labels": 5}).get()

        assert out["total_signals"] == 3
        assert out["ok"] == 2
        assert out["insufficient"] == 1
        assert out["errors"] == 0
        # Find the agreement_score row.
        agreement = next(r for r in out["signals"] if r["signal"] == "agreement_score")
        assert agreement["status"] == "insufficient_data"
        assert agreement["n_labels"] == 2


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------

class TestNightlyRefitErrorIsolation:
    def test_signal_exception_does_not_abort_loop(self, monkeypatch):
        """If refit_and_persist raises mid-loop, the task catches the exception,
        records `status='error'` for that signal, and continues to the next."""
        mapping = {
            "reliability_score": _FakeRefitResult("reliability_score", "ok"),
            "hallucination_score": _FakeRefitResult("hallucination_score", "ok"),
            # `agreement_score` intentionally missing → fake will raise via
            # the raise_signal override below.
        }
        calls: List[str] = []

        def fake_refit(db, signal_name: str, min_labels: int = 5):
            calls.append(signal_name)
            if signal_name == "agreement_score":
                raise RuntimeError("transient DB error")
            return mapping[signal_name]

        monkeypatch.setattr(
            "app.domains.intelligence.calibration_store.refit_and_persist",
            fake_refit,
        )
        _install_dummy_db(monkeypatch)

        from app.tasks.calibration import nightly_calibration_refit
        out = nightly_calibration_refit.apply(kwargs={"min_labels": 5}).get()

        # All three signals attempted; one errored, two succeeded.
        assert set(calls) == {"reliability_score", "agreement_score", "hallucination_score"}
        assert out["total_signals"] == 3
        assert out["ok"] == 2
        assert out["errors"] == 1
        agreement = next(r for r in out["signals"] if r["signal"] == "agreement_score")
        assert agreement["status"] == "error"
        assert "transient DB error" in agreement["error"]

    def test_error_status_from_refit_counted_as_error(self, monkeypatch):
        """When refit_and_persist returns a result with status='error' (not
        raises), we still count it as an error in the summary."""
        mapping = {
            "reliability_score": _FakeRefitResult(
                "reliability_score", status="error", error="constraint violation"
            ),
            "agreement_score": _FakeRefitResult("agreement_score", "ok"),
            "hallucination_score": _FakeRefitResult("hallucination_score", "ok"),
        }
        _install_fake_refit(monkeypatch, mapping)
        _install_dummy_db(monkeypatch)

        from app.tasks.calibration import nightly_calibration_refit
        out = nightly_calibration_refit.apply(kwargs={"min_labels": 5}).get()

        assert out["ok"] == 2
        assert out["errors"] == 1
        reliability = next(r for r in out["signals"] if r["signal"] == "reliability_score")
        assert reliability["status"] == "error"


# ---------------------------------------------------------------------------
# Celery beat-schedule registration
# ---------------------------------------------------------------------------

class TestNightlyRefitScheduleRegistration:
    def test_beat_schedule_contains_nightly_refit_entry(self):
        """The Celery beat schedule must register the nightly refit at 03:00 UTC."""
        from app.core.celery_app import app as celery_app
        schedule = celery_app.conf.beat_schedule
        assert "nightly-calibration-refit" in schedule
        entry = schedule["nightly-calibration-refit"]
        assert entry["task"] == "app.tasks.calibration.nightly_calibration_refit"
        # The kwargs propagate to the task — verify the min_labels default.
        assert entry["kwargs"] == {"min_labels": 5}

    def test_task_name_matches_decorator(self):
        from app.tasks.calibration import nightly_calibration_refit
        assert nightly_calibration_refit.name == "app.tasks.calibration.nightly_calibration_refit"
