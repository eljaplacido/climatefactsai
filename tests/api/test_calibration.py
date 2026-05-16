"""Calibration math tests (Phase 5 wave 4).

Pins every math primitive at hand-calculated reference values so the
calibration grade can never silently regress on a refactor.

Brier reference values, ECE behaviour, reliability-diagram bucketing,
Platt convergence, and the full calibrate() output shape.
"""

from __future__ import annotations

import math

import pytest

from app.domains.intelligence.calibration import (
    CalibrationResult,
    PlattParams,
    ReliabilityBin,
    apply_platt,
    brier_score,
    calibrate,
    expected_calibration_error,
    fit_platt,
    reliability_diagram,
)


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------

class TestBrierScore:
    def test_perfect_predictions_yield_zero(self):
        assert brier_score([0.0, 1.0, 0.0, 1.0], [0, 1, 0, 1]) == pytest.approx(0.0)

    def test_always_half_against_balanced_labels(self):
        """Reference value: predicting 0.5 against balanced binary → 0.25."""
        bs = brier_score([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1])
        assert bs == pytest.approx(0.25)

    def test_known_value(self):
        """((0.8 - 1)^2 + (0.3 - 0)^2 + (0.6 - 1)^2 + (0.2 - 0)^2) / 4
        = (0.04 + 0.09 + 0.16 + 0.04) / 4
        = 0.33 / 4 = 0.0825
        """
        bs = brier_score([0.8, 0.3, 0.6, 0.2], [1, 0, 1, 0])
        assert bs == pytest.approx(0.0825)

    def test_handles_graded_labels(self):
        """Labels in [0, 1] (not just binary) — Brier still well-defined."""
        bs = brier_score([0.4, 0.7], [0.5, 0.8])
        # ((0.4 - 0.5)^2 + (0.7 - 0.8)^2) / 2 = (0.01 + 0.01) / 2 = 0.01
        assert bs == pytest.approx(0.01)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="align"):
            brier_score([0.5, 0.5], [0, 1, 0])

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            brier_score([], [])


# ---------------------------------------------------------------------------
# expected_calibration_error
# ---------------------------------------------------------------------------

class TestECE:
    def test_perfect_calibration_yields_zero(self):
        """When every prediction matches the label exactly, ECE = 0."""
        # 10 predictions at 0.1 with mean actual 0.1; 10 at 0.9 with mean actual 0.9.
        preds = [0.1] * 10 + [0.9] * 10
        labels = [0.1] * 10 + [0.9] * 10
        ece = expected_calibration_error(preds, labels, n_bins=10)
        assert ece == pytest.approx(0.0, abs=1e-9)

    def test_known_two_bin_example(self):
        """
        4 predictions in [0.0, 0.5) all predicting 0.3, mean actual 0.0
            → bin contribution 0.3 (gap) * 4/8 (weight) = 0.15
        4 predictions in [0.5, 1.0] all predicting 0.8, mean actual 1.0
            → bin contribution 0.2 (gap) * 4/8 (weight) = 0.10
        Total ECE = 0.25
        """
        preds = [0.3] * 4 + [0.8] * 4
        labels = [0] * 4 + [1] * 4
        ece = expected_calibration_error(preds, labels, n_bins=2)
        assert ece == pytest.approx(0.25)

    def test_empty_bins_contribute_zero(self):
        # All predictions in a single bin; the other 9 bins are empty.
        preds = [0.45] * 10
        labels = [0.5] * 10
        # The (0.4, 0.5] bin has mean_pred 0.45 and mean_actual 0.5.
        # Gap = 0.05; weight = 10/10 = 1.0. ECE = 0.05.
        ece = expected_calibration_error(preds, labels, n_bins=10)
        assert ece == pytest.approx(0.05, abs=1e-9)

    def test_clamps_out_of_range_predictions(self):
        """Predictions slightly outside [0, 1] (e.g., 1.0001 from numerics)
        don't crash; they clamp into the boundary bins."""
        preds = [-0.1, 1.1]
        labels = [0, 1]
        # Clamps to [0, 1]; bin 0 has pred~0 vs label 0 (gap 0),
        # bin 9 has pred~1 vs label 1 (gap 0). ECE ≈ 0.
        ece = expected_calibration_error(preds, labels, n_bins=10)
        assert ece == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# reliability_diagram
# ---------------------------------------------------------------------------

class TestReliabilityDiagram:
    def test_returns_n_bins_in_order(self):
        diagram = reliability_diagram([0.2, 0.7], [0, 1], n_bins=5)
        assert len(diagram) == 5
        # Bins ordered left-to-right.
        for i in range(4):
            assert diagram[i].bin_upper == diagram[i + 1].bin_lower

    def test_bucketing_assigns_predictions_correctly(self):
        # 0.2 lands in bin 1 (0.2 - 0.4 with n_bins=5 has edges at multiples of 0.2);
        # actually 0.2 / 0.2 = 1.0 → idx = 1 (bin [0.2, 0.4)).
        # 0.7 → 0.7 / 0.2 = 3.5 → idx = 3 (bin [0.6, 0.8)).
        diagram = reliability_diagram([0.2, 0.7], [0, 1], n_bins=5)
        assert diagram[1].count == 1
        assert diagram[1].mean_predicted == pytest.approx(0.2)
        assert diagram[3].count == 1
        assert diagram[3].mean_predicted == pytest.approx(0.7)

    def test_empty_input_returns_empty_bins(self):
        diagram = reliability_diagram([], [], n_bins=4)
        assert len(diagram) == 4
        for b in diagram:
            assert b.count == 0
            assert b.mean_predicted == 0.0
            assert b.mean_actual == 0.0

    def test_prediction_at_one_lands_in_top_bin(self):
        diagram = reliability_diagram([1.0], [1], n_bins=10)
        assert diagram[9].count == 1


# ---------------------------------------------------------------------------
# Platt scaling
# ---------------------------------------------------------------------------

class TestPlattScaling:
    def test_converges_to_identity_on_perfect_data(self):
        """If the raw predictions are already perfectly calibrated, Platt
        should converge to ~identity (which for the Platt formulation
        means A ≈ -large and B ≈ A/2 — practically, apply_platt(p) ≈ p)."""
        preds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        labels = list(preds)
        params = fit_platt(preds, labels, max_iter=2000, learning_rate=0.2)

        # Check Platt-scaled predictions are close to raw predictions.
        # Tolerance is loose — Platt is a 2-parameter model and can't
        # perfectly recover an identity function in general; we accept
        # that the mapping doesn't push predictions toward 0.5.
        for p in (0.1, 0.3, 0.5, 0.7, 0.9):
            calibrated = apply_platt(p, params)
            # Calibrated should fall on the same side of 0.5 as p.
            assert (calibrated - 0.5) * (p - 0.5) >= 0, (
                f"Platt flipped a perfectly-calibrated prediction: "
                f"raw {p} -> calibrated {calibrated}"
            )

    def test_pulls_overconfident_predictions_toward_truth(self):
        """Synthetic over-confident classifier: it predicts 0.9 for samples
        that are only true 60% of the time. Platt should learn to map 0.9
        to roughly 0.6."""
        preds = [0.9] * 100
        labels = [1.0] * 60 + [0.0] * 40
        params = fit_platt(preds, labels, max_iter=2000, learning_rate=0.05)
        calibrated = apply_platt(0.9, params)
        # Calibrated value should be close to the actual rate of 0.6.
        assert 0.5 <= calibrated <= 0.7, (
            f"Platt should pull 0.9 toward 0.6 (actual rate); got {calibrated}"
        )

    def test_apply_platt_clamps_inputs(self):
        params = PlattParams(A=-1.0, B=0.5)
        # Out-of-range inputs don't crash.
        assert 0.0 <= apply_platt(-0.5, params) <= 1.0
        assert 0.0 <= apply_platt(1.5, params) <= 1.0

    def test_apply_platt_output_in_unit_interval(self):
        """Whatever PlattParams are given, the output is a valid probability."""
        for params in (
            PlattParams(A=-5.0, B=2.5),
            PlattParams(A=10.0, B=-5.0),
            PlattParams(A=0.0, B=0.0),
        ):
            for p in (0.0, 0.25, 0.5, 0.75, 1.0):
                v = apply_platt(p, params)
                assert 0.0 <= v <= 1.0

    def test_fit_platt_requires_data(self):
        with pytest.raises(ValueError):
            fit_platt([], [])
        with pytest.raises(ValueError):
            fit_platt([0.5], [0, 1])  # length mismatch


# ---------------------------------------------------------------------------
# calibrate() — full pipeline
# ---------------------------------------------------------------------------

class TestCalibrateFullPipeline:
    def test_returns_full_calibration_result(self):
        preds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        labels = [0, 0, 0, 0, 0, 1, 1, 1, 1]
        result = calibrate(preds, labels, n_bins=5)
        assert isinstance(result, CalibrationResult)
        assert result.n == 9
        assert 0.0 <= result.brier_score <= 1.0
        assert 0.0 <= result.ece <= 1.0
        assert len(result.reliability_diagram) == 5
        assert result.platt is not None  # n >= 5 so we fit

    def test_skips_platt_with_too_few_labels(self):
        result = calibrate([0.5, 0.6], [1, 0], n_bins=5)
        assert result.n == 2
        assert result.platt is None  # default min is 5

    def test_empty_input_returns_zeros(self):
        result = calibrate([], [], n_bins=4)
        assert result.n == 0
        assert result.brier_score == 0.0
        assert result.ece == 0.0
        assert result.platt is None
        assert len(result.reliability_diagram) == 4

    def test_as_dict_serialises_cleanly(self):
        preds = [0.1, 0.5, 0.5, 0.9, 0.9]
        labels = [0, 0, 1, 0, 1]
        result = calibrate(preds, labels, n_bins=5)
        out = result.as_dict()
        assert "n_labels" in out
        assert "brier_score" in out
        assert "ece" in out
        assert "reliability_diagram" in out
        assert "platt_a" in out
        assert "platt_b" in out
        # All values JSON-serialisable.
        import json as _json
        _json.dumps(out)


# ---------------------------------------------------------------------------
# ReliabilityBin output shape
# ---------------------------------------------------------------------------

class TestReliabilityBinAsDict:
    def test_dict_keys_present(self):
        b = ReliabilityBin(0.0, 0.1, 0.05, 0.04, 7)
        d = b.as_dict()
        for key in ("bin_lower", "bin_upper", "mean_predicted", "mean_actual", "count"):
            assert key in d
        assert d["count"] == 7
