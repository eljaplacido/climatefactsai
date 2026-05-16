"""calibration_store tests (Phase 5 wave 5).

Pins the data → fit → apply loop:
- fetch_labelled_predictions normalises raw reliability_score (0–100) to [0,1]
- refit_and_persist writes a calibration_fits row when n >= min_labels,
  otherwise returns insufficient_data
- get_latest_platt returns the most-recent fit, None when missing/missing-table
- apply_latest_to_reliability returns a 0–100 calibrated value, None on no-fit
- record_calibration_label inserts a row; duplicate returns status='duplicate'
- All read paths degrade gracefully on missing tables / DB errors
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from app.domains.intelligence.calibration import PlattParams
from app.domains.intelligence.calibration_store import (
    LabelRecordResult,
    RefitResult,
    apply_latest_to_reliability,
    fetch_labelled_predictions,
    get_latest_platt,
    record_calibration_label,
    refit_and_persist,
)


# ---------------------------------------------------------------------------
# Fake DBs
# ---------------------------------------------------------------------------

class _RecordingDB:
    """Records queries; returns canned rows for SELECT and a synthetic
    id for INSERT ... RETURNING id."""
    def __init__(
        self,
        select_rows: Optional[List[Dict[str, Any]]] = None,
        *,
        raise_on_select: bool = False,
        raise_on_insert: bool = False,
        duplicate: bool = False,
    ):
        self.select_rows = select_rows or []
        self.raise_on_select = raise_on_select
        self.raise_on_insert = raise_on_insert
        self.duplicate = duplicate
        self.queries: List[Dict[str, Any]] = []
        self._next_id = 1
        self._next_labeled_at = "2026-05-16T12:00:00"

    def execute_query(self, query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()
        self.queries.append({"q": q, "params": params})
        if "insert into calibration_labels" in q:
            if self.raise_on_insert:
                raise RuntimeError("simulated db error")
            if self.duplicate:
                raise RuntimeError(
                    'duplicate key value violates unique constraint '
                    '"uq_calibration_labels_natural"'
                )
            row = {"id": self._next_id, "labeled_at": self._next_labeled_at}
            self._next_id += 1
            return [row]
        if "insert into calibration_fits" in q:
            if self.raise_on_insert:
                raise RuntimeError("simulated db error")
            row = {"id": self._next_id}
            self._next_id += 1
            return [row]
        if self.raise_on_select:
            raise RuntimeError("relation does not exist")
        return self.select_rows

    def execute_update(self, query, params=None):
        self.queries.append({"q": " ".join(query.split()).lower(), "params": params or {}})
        return None


# ---------------------------------------------------------------------------
# fetch_labelled_predictions
# ---------------------------------------------------------------------------

class TestFetchLabelledPredictions:
    def test_normalises_reliability_score_to_unit_interval(self):
        db = _RecordingDB(select_rows=[
            {"label_truth": 1.0, "reliability_score": 80},
            {"label_truth": 0.0, "reliability_score": 30},
        ])
        preds, labels = fetch_labelled_predictions(db, "reliability_score")
        assert preds == [0.8, 0.3]
        assert labels == [1.0, 0.0]

    def test_skips_rows_with_none_values(self):
        db = _RecordingDB(select_rows=[
            {"label_truth": 1.0, "reliability_score": None},
            {"label_truth": None, "reliability_score": 50},
            {"label_truth": 0.5, "reliability_score": 70},
        ])
        preds, labels = fetch_labelled_predictions(db, "reliability_score")
        assert preds == [0.7]
        assert labels == [0.5]

    def test_unknown_signal_returns_empty(self):
        db = _RecordingDB()
        preds, labels = fetch_labelled_predictions(db, "made_up_signal")
        assert preds == []
        assert labels == []
        # No SQL was attempted.
        assert db.queries == []

    def test_agreement_score_not_yet_supported(self):
        """agreement_score lives in JSONB; wave 5 doesn't query it."""
        db = _RecordingDB(select_rows=[{"label_truth": 1.0, "reliability_score": 80}])
        preds, labels = fetch_labelled_predictions(db, "agreement_score")
        assert preds == []
        # No SQL was attempted.
        assert db.queries == []

    def test_db_error_returns_empty(self):
        db = _RecordingDB(raise_on_select=True)
        preds, labels = fetch_labelled_predictions(db, "reliability_score")
        assert preds == []
        assert labels == []


# ---------------------------------------------------------------------------
# refit_and_persist
# ---------------------------------------------------------------------------

class TestRefitAndPersist:
    def test_writes_fit_row_when_enough_labels(self):
        db = _RecordingDB(select_rows=[
            {"label_truth": 1.0, "reliability_score": 90},
            {"label_truth": 0.0, "reliability_score": 30},
            {"label_truth": 1.0, "reliability_score": 80},
            {"label_truth": 0.0, "reliability_score": 40},
            {"label_truth": 1.0, "reliability_score": 75},
        ])
        result = refit_and_persist(db, signal_name="reliability_score")
        assert result.status == "ok"
        assert result.n_labels == 5
        assert result.brier_score is not None
        assert result.ece is not None
        assert result.platt_a is not None
        assert result.platt_b is not None
        assert result.fit_id == 1
        # An INSERT happened.
        inserts = [q for q in db.queries if "insert into calibration_fits" in q["q"]]
        assert len(inserts) == 1
        # The reliability_diagram JSONB was serialised before binding.
        diagram_str = inserts[0]["params"]["diagram"]
        assert isinstance(diagram_str, str)
        json.loads(diagram_str)  # parses

    def test_returns_insufficient_data_when_below_min(self):
        db = _RecordingDB(select_rows=[
            {"label_truth": 1.0, "reliability_score": 80},
            {"label_truth": 0.0, "reliability_score": 30},
        ])
        result = refit_and_persist(db, signal_name="reliability_score", min_labels=5)
        assert result.status == "insufficient_data"
        assert result.n_labels == 2
        # No INSERT ran.
        inserts = [q for q in db.queries if "insert into calibration_fits" in q["q"]]
        assert inserts == []

    def test_insert_failure_returns_error(self):
        """A DB write failure leaves the function returning status='error'."""
        # Need >=5 rows so we attempt the insert.
        db = _RecordingDB(
            select_rows=[
                {"label_truth": 1.0, "reliability_score": 90},
                {"label_truth": 0.0, "reliability_score": 30},
                {"label_truth": 1.0, "reliability_score": 80},
                {"label_truth": 0.0, "reliability_score": 40},
                {"label_truth": 1.0, "reliability_score": 75},
            ],
            raise_on_insert=True,
        )
        result = refit_and_persist(db, signal_name="reliability_score")
        assert result.status == "error"
        assert result.n_labels == 5
        assert "simulated db error" in result.error


# ---------------------------------------------------------------------------
# get_latest_platt + apply_latest_to_reliability
# ---------------------------------------------------------------------------

class TestGetLatestPlatt:
    def test_returns_platt_params_from_db(self):
        db = _RecordingDB(select_rows=[{"platt_a": -2.5, "platt_b": 1.0}])
        params = get_latest_platt(db, "reliability_score")
        assert params is not None
        assert params.A == -2.5
        assert params.B == 1.0

    def test_returns_none_on_empty_result(self):
        db = _RecordingDB(select_rows=[])
        params = get_latest_platt(db, "reliability_score")
        assert params is None

    def test_returns_none_on_db_error(self):
        db = _RecordingDB(raise_on_select=True)
        params = get_latest_platt(db, "reliability_score")
        assert params is None


class TestApplyLatestToReliability:
    def test_returns_calibrated_value_when_fit_exists(self):
        db = _RecordingDB(select_rows=[{"platt_a": -2.0, "platt_b": 0.5}])
        calibrated = apply_latest_to_reliability(db, 80.0)
        assert calibrated is not None
        # apply_platt(0.8, A=-2, B=0.5) = 1 - sigmoid(-2*0.8 + 0.5) = 1 - sigmoid(-1.1)
        # = 1 - 0.2497 ≈ 0.7503; * 100 = 75.03 ≈ 75.0
        assert 70.0 <= calibrated <= 80.0

    def test_returns_none_when_no_fit(self):
        db = _RecordingDB(select_rows=[])
        calibrated = apply_latest_to_reliability(db, 80.0)
        assert calibrated is None

    def test_returns_none_when_raw_is_none(self):
        db = _RecordingDB(select_rows=[{"platt_a": -2.0, "platt_b": 0.5}])
        assert apply_latest_to_reliability(db, None) is None

    def test_handles_db_error_gracefully(self):
        db = _RecordingDB(raise_on_select=True)
        assert apply_latest_to_reliability(db, 80.0) is None


# ---------------------------------------------------------------------------
# record_calibration_label
# ---------------------------------------------------------------------------

class TestRecordCalibrationLabel:
    def test_records_label_returns_id(self):
        db = _RecordingDB()
        result = record_calibration_label(
            db,
            url_analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            label_truth=0.85,
            labeled_by="reviewer-1",
            label_method="human_review",
            label_notes="Mostly correct, one overstatement.",
        )
        assert result.status == "recorded"
        assert result.id == 1
        assert result.labeled_at is not None

    def test_invalid_label_truth_returns_error_no_db_call(self):
        db = _RecordingDB()
        result = record_calibration_label(
            db,
            url_analysis_id="x",
            label_truth=1.5,
            labeled_by="r",
        )
        assert result.status == "error"
        assert "0.0" in result.error or "1.0" in result.error
        # No SQL ran.
        assert db.queries == []

    def test_duplicate_returns_duplicate_status(self):
        db = _RecordingDB(duplicate=True)
        result = record_calibration_label(
            db,
            url_analysis_id="x",
            label_truth=0.5,
            labeled_by="r",
        )
        assert result.status == "duplicate"

    def test_generic_failure_returns_error(self):
        db = _RecordingDB(raise_on_insert=True)
        result = record_calibration_label(
            db,
            url_analysis_id="x",
            label_truth=0.5,
            labeled_by="r",
        )
        assert result.status == "error"
        assert "simulated db error" in result.error
