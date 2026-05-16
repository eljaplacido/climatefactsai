"""Confidence calibration — Phase 5 wave 4.

Turns the raw confidence signals the platform records
(reliability_score, agreement_score, hallucination_score) into MEASURED
calibration metrics + a Platt-scaled corrected-confidence function.

Why this matters: the audit's Calibration axis is the lowest grade
because self-reported model confidence is uncalibrated. A model saying
"0.7 confident" doesn't mean "this kind of claim is true 70% of the
time" — we have no measurement. With ground-truth labels (table
`calibration_labels`, migration 022) we can compute:

  * **Brier score** — mean squared error between predicted and actual.
    0 = perfect; 0.25 = always-predict-0.5; higher = worse than coin-flip.

  * **Expected Calibration Error (ECE)** — the standard reliability
    metric. Buckets predictions into bins, measures the gap between
    mean predicted confidence and actual accuracy per bin, weighted by
    bin size. ECE < 0.05 is considered well-calibrated.

  * **Reliability diagram** — per-bin {mean_predicted, mean_actual,
    count} so the calibration is human-inspectable as a plot.

  * **Platt scaling** — fits two parameters (A, B) such that
    P_calibrated(y=1 | p) = sigmoid(-(A*p + B)). Used to MAP raw
    confidences back to calibrated probabilities at inference time.

# Why hand-rolled (no scipy)

scipy isn't in the platform's requirements.txt. Platt scaling is two
parameters of logistic regression — a tight gradient-descent loop on
cross-entropy converges in 200 iterations. The math is short enough
that an auditor can verify the gradient by hand; an opaque scipy
optimizer would be harder to certify.

Reference values for the tests are hand-calculated.

# Wiring into the app (wave 5, future)

When `calibration_fits` has a row for `signal_name='reliability_score'`,
the application reads the most-recent {A, B} and surfaces a
`calibrated_reliability` alongside the raw value:

    calibrated = apply_platt(raw_reliability / 100.0, params) * 100.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlattParams:
    """Fitted parameters of the Platt scaling function.

    The calibrated probability is::

        P_calibrated(y = 1 | raw_p) = 1 / (1 + exp(A * raw_p + B))

    A typical well-calibrated fit on an overconfident classifier has
    A < 0 and B somewhere around 0 (so high raw_p → high calibrated).
    """
    A: float
    B: float


@dataclass(frozen=True)
class ReliabilityBin:
    """One bin of the reliability diagram."""
    bin_lower: float
    bin_upper: float
    mean_predicted: float    # average raw confidence of predictions in this bin
    mean_actual: float        # average ground-truth label of predictions in this bin
    count: int

    def as_dict(self) -> dict:
        return {
            "bin_lower": round(self.bin_lower, 4),
            "bin_upper": round(self.bin_upper, 4),
            "mean_predicted": round(self.mean_predicted, 4),
            "mean_actual": round(self.mean_actual, 4),
            "count": self.count,
        }


@dataclass
class CalibrationResult:
    """Full output of calibrate() — both diagnostic metrics and a fitted Platt."""
    n: int
    brier_score: float
    ece: float
    reliability_diagram: List[ReliabilityBin]
    platt: Optional[PlattParams]

    def as_dict(self) -> dict:
        return {
            "n_labels": self.n,
            "brier_score": round(self.brier_score, 4),
            "ece": round(self.ece, 4),
            "reliability_diagram": [b.as_dict() for b in self.reliability_diagram],
            "platt_a": round(self.platt.A, 4) if self.platt is not None else None,
            "platt_b": round(self.platt.B, 4) if self.platt is not None else None,
        }


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------

def brier_score(predictions: Sequence[float], labels: Sequence[float]) -> float:
    """Mean squared error between predicted probabilities and ground-truth labels.

    Both inputs are sequences over [0, 1]. Returns a scalar in [0, 1]:
      * 0.0 = perfect predictions
      * 0.25 = always predicting 0.5 against balanced binary labels
      * 1.0 = always predicting the opposite of the truth

    Raises ValueError on mismatched lengths or empty input.
    """
    if len(predictions) != len(labels):
        raise ValueError(
            f"predictions ({len(predictions)}) and labels ({len(labels)}) must align"
        )
    if not predictions:
        raise ValueError("brier_score requires at least one (prediction, label) pair")
    total = 0.0
    for p, y in zip(predictions, labels):
        total += (float(p) - float(y)) ** 2
    return total / len(predictions)


# ---------------------------------------------------------------------------
# Expected Calibration Error (ECE) + reliability diagram
# ---------------------------------------------------------------------------

def _build_bins(
    predictions: Sequence[float],
    labels: Sequence[float],
    n_bins: int,
) -> List[ReliabilityBin]:
    """Bucket (prediction, label) pairs into n_bins equal-width bins.

    Bins span [0, 1]. A prediction at exactly 1.0 lands in the top bin
    (closed upper edge for the final bin only).
    """
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")

    bin_width = 1.0 / n_bins
    bucket_preds: List[List[float]] = [[] for _ in range(n_bins)]
    bucket_labels: List[List[float]] = [[] for _ in range(n_bins)]

    for p, y in zip(predictions, labels):
        # Clamp inputs to [0, 1] before bucketing — defensive.
        p_clamped = max(0.0, min(1.0, float(p)))
        idx = int(p_clamped / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        bucket_preds[idx].append(p_clamped)
        bucket_labels[idx].append(float(y))

    out: List[ReliabilityBin] = []
    for i in range(n_bins):
        lower = i * bin_width
        upper = (i + 1) * bin_width
        n = len(bucket_preds[i])
        if n == 0:
            mean_pred = 0.0
            mean_actual = 0.0
        else:
            mean_pred = sum(bucket_preds[i]) / n
            mean_actual = sum(bucket_labels[i]) / n
        out.append(ReliabilityBin(
            bin_lower=lower,
            bin_upper=upper,
            mean_predicted=mean_pred,
            mean_actual=mean_actual,
            count=n,
        ))
    return out


def expected_calibration_error(
    predictions: Sequence[float],
    labels: Sequence[float],
    n_bins: int = 10,
) -> float:
    """ECE over n_bins equal-width bins.

    Returns:
        ECE in [0, 1]. 0 = perfectly calibrated; 1 = maximally miscalibrated.
        Empty bins contribute zero (per standard ECE definition).
    """
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must align")
    if not predictions:
        raise ValueError("ECE requires at least one (prediction, label) pair")

    bins = _build_bins(predictions, labels, n_bins)
    n_total = len(predictions)
    ece = 0.0
    for b in bins:
        if b.count == 0:
            continue
        ece += (b.count / n_total) * abs(b.mean_predicted - b.mean_actual)
    return ece


def reliability_diagram(
    predictions: Sequence[float],
    labels: Sequence[float],
    n_bins: int = 10,
) -> List[ReliabilityBin]:
    """Return the reliability-diagram bins (sized for plotting + audit)."""
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must align")
    if not predictions:
        return [ReliabilityBin(i * (1.0 / n_bins), (i + 1) * (1.0 / n_bins),
                               0.0, 0.0, 0) for i in range(n_bins)]
    return _build_bins(predictions, labels, n_bins)


# ---------------------------------------------------------------------------
# Platt scaling
# ---------------------------------------------------------------------------

def _sigmoid(z: float) -> float:
    """Numerically stable logistic sigmoid."""
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fit_platt(
    predictions: Sequence[float],
    labels: Sequence[float],
    *,
    max_iter: int = 500,
    learning_rate: float = 0.1,
    tolerance: float = 1e-6,
) -> PlattParams:
    """Fit Platt scaling parameters (A, B) via gradient descent on cross-entropy.

    The Platt model is:
        P_calibrated(y = 1 | p) = sigma(-(A*p + B))
    where sigma is the logistic sigmoid. We minimise mean cross-entropy:
        L = -[ y * log(sigma(-(A*p + B))) + (1-y) * log(1 - sigma(-(A*p + B))) ]
    The closed-form gradients are
        dL/dA =  (sigma(-(A*p + B)) - y) * (-p)
        dL/dB =  (sigma(-(A*p + B)) - y) * (-1)
    written equivalently below using `g = sigma_at_p - y` and the
    sigmoid identity sigma(-z) = 1 - sigma(z).

    Args:
        predictions: raw model outputs in [0, 1].
        labels: ground-truth labels in [0, 1].
        max_iter: hard cap on gradient steps (default 500).
        learning_rate: gradient step size (default 0.1).
        tolerance: stop when both |grad_A|, |grad_B| < tolerance.

    Returns:
        PlattParams with the fitted A, B.

    Raises:
        ValueError on length mismatch or empty inputs.
    """
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must align")
    if not predictions:
        raise ValueError("Platt scaling requires at least one (prediction, label) pair")

    # Standard Platt initialisation: A=-1.0, B=0.5 — pulls extremes toward 0.5.
    A = -1.0
    B = 0.5
    n = len(predictions)

    for _ in range(max_iter):
        grad_A = 0.0
        grad_B = 0.0
        for p, y in zip(predictions, labels):
            z = A * float(p) + B
            # P_calibrated = sigma(-z); equivalently 1 - sigma(z).
            cal = 1.0 - _sigmoid(z)
            # dL/dA, dL/dB derived from cross-entropy on the calibrated prob.
            err = cal - float(y)         # >0 when over-calibrated, <0 when under
            grad_A += -err * float(p)
            grad_B += -err

        grad_A /= n
        grad_B /= n

        A -= learning_rate * grad_A
        B -= learning_rate * grad_B

        if abs(grad_A) < tolerance and abs(grad_B) < tolerance:
            break

    return PlattParams(A=A, B=B)


def apply_platt(raw_p: float, params: PlattParams) -> float:
    """Map a raw confidence in [0, 1] through Platt scaling to a calibrated probability."""
    if not isinstance(params, PlattParams):
        raise TypeError("params must be a PlattParams instance")
    p_clamped = max(0.0, min(1.0, float(raw_p)))
    z = params.A * p_clamped + params.B
    return 1.0 - _sigmoid(z)


# ---------------------------------------------------------------------------
# Full calibrate() — runs all four
# ---------------------------------------------------------------------------

def calibrate(
    predictions: Sequence[float],
    labels: Sequence[float],
    *,
    n_bins: int = 10,
    fit: bool = True,
) -> CalibrationResult:
    """Compute Brier + ECE + reliability diagram + (optionally) fit Platt.

    Returns a CalibrationResult ready to serialise to a /api/methodology/calibration
    response or persist into the `calibration_fits` table.

    `fit=False` skips Platt fitting (useful when N is too small for a stable fit).
    """
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must align")
    if not predictions:
        return CalibrationResult(
            n=0,
            brier_score=0.0,
            ece=0.0,
            reliability_diagram=reliability_diagram([], [], n_bins=n_bins),
            platt=None,
        )

    bs = brier_score(predictions, labels)
    ece = expected_calibration_error(predictions, labels, n_bins=n_bins)
    diagram = reliability_diagram(predictions, labels, n_bins=n_bins)
    platt = fit_platt(predictions, labels) if (fit and len(predictions) >= 5) else None

    return CalibrationResult(
        n=len(predictions),
        brier_score=bs,
        ece=ece,
        reliability_diagram=diagram,
        platt=platt,
    )
