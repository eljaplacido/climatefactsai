"""Calibration label/fit storage — Phase 5 wave 5.

Closes the data → fit → apply loop on calibration:

  1. Operators POST a label → row in `calibration_labels`.
  2. Operators (or a cron job) trigger a refit → row in `calibration_fits`.
  3. The application reads the most-recent fit per signal at inference
     and surfaces `calibrated_reliability_score` alongside the raw value.

All functions are best-effort against the database — failures degrade
to "no calibration available" rather than crashing user-facing paths.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .calibration import (
    CalibrationResult,
    PlattParams,
    apply_platt,
    calibrate,
)

_logger = logging.getLogger("calibration_store")


# ---------------------------------------------------------------------------
# Data → predictions/labels
# ---------------------------------------------------------------------------

SUPPORTED_SIGNALS = {
    "reliability_score",
    "agreement_score",
    "hallucination_score",
}


def fetch_labelled_predictions(
    db,
    signal_name: str = "reliability_score",
) -> Tuple[List[float], List[float]]:
    """Pull (raw_prediction, ground_truth) pairs from the labelled dataset.

    Predictions are normalised to [0, 1] so Brier / ECE / Platt math
    works uniformly across signals stored on different scales:

      * reliability_score (0–100, on url_analyses) → divided by 100.
      * agreement_score (0–1, in claim_provenance.raw_metadata JSONB) → as-is.
      * hallucination_score (0–1, dedicated claim_provenance column) → as-is.
        Note: hallucination_score is INVERTED for calibration — a low
        hallucination_risk means a TRUSTWORTHY answer, so the "prediction"
        we fit against label_truth is (1 - hallucination_score). This way
        a well-calibrated platform shows agreement between
        (1 - hallucination_risk) and the ground-truth verdict.

    Returns:
        (predictions, labels). Empty when no labels exist or the
        migration hasn't been applied — caller handles the empty case
        gracefully.
    """
    if signal_name not in SUPPORTED_SIGNALS:
        _logger.debug(f"Unknown signal_name={signal_name}; returning empty")
        return [], []

    if signal_name == "reliability_score":
        return _fetch_reliability_score(db)
    if signal_name == "agreement_score":
        return _fetch_agreement_score(db)
    if signal_name == "hallucination_score":
        return _fetch_hallucination_score(db)
    return [], []


def _fetch_reliability_score(db) -> Tuple[List[float], List[float]]:
    """Normalise 0–100 reliability_score to [0, 1] for the calibration math."""
    try:
        rows = db.execute_query(
            """
            SELECT
                cl.label_truth,
                ua.reliability_score AS raw
            FROM calibration_labels cl
            JOIN url_analyses ua ON cl.url_analysis_id = ua.analysis_id
            WHERE ua.reliability_score IS NOT NULL
            """,
            {},
        )
    except Exception as exc:
        _logger.warning(f"_fetch_reliability_score failed: {exc}")
        return [], []
    return _rows_to_pairs(rows, divisor=100.0)


def _fetch_agreement_score(db) -> Tuple[List[float], List[float]]:
    """Read agreement_score from claim_provenance.raw_metadata JSONB.

    The multi-LLM verifier writes it at
    raw_metadata.multi_llm_verification.agreement_score in [0, 1].
    Picks the most-recent provenance row per analysis (in case
    multiple syncs / replays exist).
    """
    try:
        rows = db.execute_query(
            """
            SELECT
                cl.label_truth,
                (cp.raw_metadata #>> '{multi_llm_verification,agreement_score}')::float
                    AS raw
            FROM calibration_labels cl
            JOIN LATERAL (
                SELECT raw_metadata
                FROM claim_provenance
                WHERE url_analysis_id = cl.url_analysis_id
                  AND raw_metadata #>> '{multi_llm_verification,agreement_score}' IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
            ) cp ON TRUE
            """,
            {},
        )
    except Exception as exc:
        _logger.warning(f"_fetch_agreement_score failed: {exc}")
        return [], []
    return _rows_to_pairs(rows, divisor=1.0)


def _fetch_hallucination_score(db) -> Tuple[List[float], List[float]]:
    """Read hallucination_score from claim_provenance.hallucination_score
    (dedicated column from migration 021).

    INVERTS the value before returning — a low hallucination_risk means
    a trustworthy output, so the "prediction" the math sees is
    (1 - hallucination_score). With that flip, a perfectly calibrated
    detector matches label_truth directly.
    """
    try:
        rows = db.execute_query(
            """
            SELECT
                cl.label_truth,
                (1.0 - cp.hallucination_score) AS raw
            FROM calibration_labels cl
            JOIN LATERAL (
                SELECT hallucination_score
                FROM claim_provenance
                WHERE url_analysis_id = cl.url_analysis_id
                  AND hallucination_score IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
            ) cp ON TRUE
            """,
            {},
        )
    except Exception as exc:
        _logger.warning(f"_fetch_hallucination_score failed: {exc}")
        return [], []
    return _rows_to_pairs(rows, divisor=1.0)


def _rows_to_pairs(
    rows,
    *,
    divisor: float,
) -> Tuple[List[float], List[float]]:
    """Common (label_truth, raw) → (predictions, labels) shaping logic.

    Accepts either the new aliased `raw` column (current production SQL)
    or the legacy column name (`reliability_score`) for backward compat
    with tests + earlier SQL shapes.
    """
    predictions: List[float] = []
    labels: List[float] = []
    for r in rows or []:
        raw = r.get("raw")
        if raw is None:
            # Legacy column name used by older tests / earlier SQL.
            raw = r.get("reliability_score")
        lt = r.get("label_truth")
        if raw is None or lt is None:
            continue
        try:
            p = float(raw) / float(divisor)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        # Clamp into [0, 1] in case of arithmetic edge cases.
        p = max(0.0, min(1.0, p))
        predictions.append(p)
        try:
            labels.append(float(lt))
        except (TypeError, ValueError):
            predictions.pop()  # roll back the prediction we just added
            continue
    return predictions, labels


# ---------------------------------------------------------------------------
# Refit + persist
# ---------------------------------------------------------------------------

# Calibration honesty: 5 labels is far below the N≈50 needed for a stable Platt
# fit. Below STABLE_FIT_MIN the fit is marked is_preview=True so the UI can warn
# users that this signal is calibrated on too-few labels. Above it the fit is
# considered production-grade.
PREVIEW_FIT_MIN = 5
STABLE_FIT_MIN = 50


@dataclass
class RefitResult:
    """Outcome of a single refit run."""
    signal_name: str
    status: str            # 'ok' | 'insufficient_data' | 'error'
    n_labels: int
    brier_score: Optional[float] = None
    ece: Optional[float] = None
    platt_a: Optional[float] = None
    platt_b: Optional[float] = None
    fit_id: Optional[int] = None
    error: Optional[str] = None
    is_preview: bool = False  # True when n_labels < STABLE_FIT_MIN

    def as_dict(self) -> Dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "status": self.status,
            "n_labels": self.n_labels,
            "brier_score": round(self.brier_score, 4) if self.brier_score is not None else None,
            "ece": round(self.ece, 4) if self.ece is not None else None,
            "platt_a": round(self.platt_a, 4) if self.platt_a is not None else None,
            "platt_b": round(self.platt_b, 4) if self.platt_b is not None else None,
            "fit_id": self.fit_id,
            "error": self.error,
            "is_preview": self.is_preview,
        }


def refit_and_persist(
    db,
    signal_name: str = "reliability_score",
    *,
    min_labels: int = PREVIEW_FIT_MIN,
) -> RefitResult:
    """Refit Platt scaling on the latest labels and write to `calibration_fits`.

    Below `min_labels` the function returns `status='insufficient_data'`
    without writing anything — Platt scaling on too-few points produces
    unstable parameters that would degrade inference rather than improve it.

    The fit row is stamped with `fitted_at = NOW()` so the application's
    `get_latest_platt(db, signal_name)` picks up the new fit on the next
    call.
    """
    predictions, labels = fetch_labelled_predictions(db, signal_name)

    if len(predictions) < min_labels:
        return RefitResult(
            signal_name=signal_name,
            status="insufficient_data",
            n_labels=len(predictions),
        )

    result: CalibrationResult = calibrate(predictions, labels)
    if result.platt is None:
        # Should be unreachable when n >= 5, but guard anyway.
        return RefitResult(
            signal_name=signal_name,
            status="insufficient_data",
            n_labels=result.n,
        )

    try:
        rows = db.execute_query(
            """
            INSERT INTO calibration_fits (
                signal_name, platt_a, platt_b, brier_score, ece, n_labels,
                reliability_diagram
            ) VALUES (
                :signal, :a, :b, :bs, :ece, :n,
                CAST(:diagram AS jsonb)
            )
            RETURNING id
            """,
            {
                "signal": signal_name,
                "a": result.platt.A,
                "b": result.platt.B,
                "bs": result.brier_score,
                "ece": result.ece,
                "n": result.n,
                "diagram": json.dumps([b.as_dict() for b in result.reliability_diagram]),
            },
        )
        fit_id = int(rows[0]["id"]) if rows else None
    except Exception as exc:
        _logger.error(f"refit_and_persist write failed: {exc}")
        return RefitResult(
            signal_name=signal_name,
            status="error",
            n_labels=result.n,
            error=f"{type(exc).__name__}: {exc}",
        )

    return RefitResult(
        signal_name=signal_name,
        status="ok",
        n_labels=result.n,
        brier_score=result.brier_score,
        ece=result.ece,
        platt_a=result.platt.A,
        platt_b=result.platt.B,
        fit_id=fit_id,
        is_preview=result.n < STABLE_FIT_MIN,
    )


# ---------------------------------------------------------------------------
# Read most-recent fit (used at inference)
# ---------------------------------------------------------------------------

def get_latest_platt(
    db,
    signal_name: str = "reliability_score",
) -> Optional[PlattParams]:
    """Most-recent fitted Platt parameters for `signal_name`, or None.

    Returns None when:
      * `calibration_fits` table doesn't exist (migration not applied).
      * No row exists for this signal yet.
      * The stored values can't be coerced to float.

    Callers MUST treat None as "no calibration available" and fall back
    to the raw value rather than crashing.
    """
    try:
        rows = db.execute_query(
            """
            SELECT platt_a, platt_b
            FROM calibration_fits
            WHERE signal_name = :signal
            ORDER BY fitted_at DESC
            LIMIT 1
            """,
            {"signal": signal_name},
        )
    except Exception as exc:
        _logger.debug(f"get_latest_platt failed: {exc}")
        return None
    if not rows:
        return None
    try:
        return PlattParams(
            A=float(rows[0]["platt_a"]),
            B=float(rows[0]["platt_b"]),
        )
    except (TypeError, ValueError, KeyError) as exc:
        _logger.debug(f"get_latest_platt could not coerce row: {exc}")
        return None


def get_latest_fit_meta(
    db,
    signal_name: str = "reliability_score",
) -> Optional[dict]:
    """Return {platt_a, platt_b, n_labels, is_preview} for the latest fit, or None."""
    try:
        rows = db.execute_query(
            """
            SELECT platt_a, platt_b, n_labels,
                   CASE WHEN n_labels < :stable_min THEN true ELSE false END AS is_preview
            FROM calibration_fits
            WHERE signal_name = :signal
            ORDER BY fitted_at DESC
            LIMIT 1
            """,
            {"signal": signal_name, "stable_min": STABLE_FIT_MIN},
        )
    except Exception as exc:
        _logger.debug(f"get_latest_fit_meta failed: {exc}")
        return None
    if not rows:
        return None
    try:
        return {
            "platt_a": float(rows[0]["platt_a"]),
            "platt_b": float(rows[0]["platt_b"]),
            "n_labels": int(rows[0].get("n_labels") or 0),
            "is_preview": bool(rows[0].get("is_preview", True)),
        }
    except (TypeError, ValueError, KeyError) as exc:
        _logger.debug(f"get_latest_fit_meta could not coerce row: {exc}")
        return None


def apply_latest_to_reliability(
    db,
    raw_reliability_score: Optional[float],
) -> Optional[float]:
    """Convenience: take a 0–100 reliability_score, apply the latest Platt,
    return the calibrated 0–100 score. Returns None when raw is None,
    no fit exists, or the fit is still a preview (n_labels < STABLE_FIT_MIN).
    """
    if raw_reliability_score is None:
        return None
    meta = get_latest_fit_meta(db, signal_name="reliability_score")
    if meta is None or meta.get("is_preview", True):
        return None
    try:
        a = float(meta["platt_a"])
        b = float(meta["platt_b"])
        raw_unit = max(0.0, min(1.0, float(raw_reliability_score) / 100.0))
        calibrated_unit = apply_platt(PlattParams(A=a, B=b), raw_unit)
        return round(calibrated_unit * 100.0, 1)
    except Exception as exc:
        _logger.debug(f"apply_latest_to_reliability failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Recording a label (used by the POST endpoint)
# ---------------------------------------------------------------------------

@dataclass
class LabelRecordResult:
    status: str          # 'recorded' | 'duplicate' | 'error'
    id: Optional[int] = None
    labeled_at: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "id": self.id,
            "labeled_at": self.labeled_at,
            "error": self.error,
        }


def record_calibration_label(
    db,
    *,
    url_analysis_id: str,
    label_truth: float,
    labeled_by: str,
    label_method: str = "human_review",
    label_notes: Optional[str] = None,
    confidence_at_label: Optional[float] = None,
) -> LabelRecordResult:
    """Insert one calibration label. Idempotent on the natural key —
    re-submitting the same (analysis, labeler, method) tuple returns
    `duplicate`."""
    if not (0.0 <= float(label_truth) <= 1.0):
        return LabelRecordResult(
            status="error",
            error="label_truth must be in [0.0, 1.0]",
        )
    try:
        rows = db.execute_query(
            """
            INSERT INTO calibration_labels (
                url_analysis_id, label_truth, labeled_by, label_method,
                label_notes, confidence_at_label
            ) VALUES (
                :uaid, :truth, :by, :method, :notes, :confidence
            )
            RETURNING id, labeled_at
            """,
            {
                "uaid": url_analysis_id,
                "truth": float(label_truth),
                "by": labeled_by,
                "method": label_method,
                "notes": label_notes,
                "confidence": confidence_at_label,
            },
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate key" in msg or "uq_calibration_labels_natural" in msg or "unique" in msg:
            return LabelRecordResult(status="duplicate", error=str(exc))
        _logger.error(f"record_calibration_label failed: {exc}")
        return LabelRecordResult(status="error", error=f"{type(exc).__name__}: {exc}")

    if not rows:
        return LabelRecordResult(status="error", error="INSERT returned no rows")

    return LabelRecordResult(
        status="recorded",
        id=int(rows[0]["id"]),
        labeled_at=str(rows[0]["labeled_at"]) if rows[0].get("labeled_at") else None,
    )
