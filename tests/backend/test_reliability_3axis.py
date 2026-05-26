"""Reliability scorer — 3-axis source scoring integration (Polish wave 2).

Strategy report Section I priority #2: "Integrate 3-Axis Source Scoring:
The schema for Editorial, Fact-check, and Transparency scores is
SHIPPED, but these axes are currently *not consumed* in the credibility
calculation. They must be wired into the compute_weighted_score() math."

These tests pin the blend formula so a future copy-edit can't quietly
disconnect the axes again.
"""

from __future__ import annotations

import pytest

from shared.reliability_scorer import ReliabilityScorer


class TestThreeAxisBlend:
    """3-axis scores blend into source_component at SOURCE_AXES_WEIGHT (0.4)."""

    def test_axes_unset_falls_back_to_legacy_only(self):
        """When all 3 axes are None, scoring matches the pre-Polish-2 path."""
        score_no_axes, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=80,
            total_claims=6,
            verified_claims=6,
            content_relevance_score=0.7,
        )
        # No axes provided → blended_source == legacy 80.
        # source=40, claims_component=30, relevance_component=14 → ~84.
        assert 80 <= score_no_axes <= 90

    def test_high_axes_lift_low_legacy_score(self):
        """Source with weak legacy score (50) but strong 3-axis (all 95)
        should land meaningfully higher than weak legacy alone."""
        low_legacy_no_axes, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
        )
        low_legacy_high_axes, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
            editorial_score=95,
            factcheck_score=95,
            transparency_score=95,
        )
        # blended = 0.6 * 50 + 0.4 * 95 = 68 (vs 50 without axes)
        # source_component goes from 25 to 34 — a real, defensible lift.
        assert low_legacy_high_axes > low_legacy_no_axes
        assert low_legacy_high_axes - low_legacy_no_axes >= 7

    def test_low_axes_drag_high_legacy_score(self):
        """Source with strong legacy (90) but weak 3-axis (all 30,
        the "unknown" tier from mig 041/045 defaults) should lose
        ground vs unfenced legacy."""
        high_legacy_no_axes, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
        )
        high_legacy_weak_axes, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
            editorial_score=30,
            factcheck_score=30,
            transparency_score=30,
        )
        # blended = 0.6 * 90 + 0.4 * 30 = 66 (vs 90)
        # Drag of ~12 source-component points → ~12 final.
        assert high_legacy_weak_axes < high_legacy_no_axes
        assert high_legacy_no_axes - high_legacy_weak_axes >= 10

    def test_partial_axes_only_count_provided_ones(self):
        """If only 2 of 3 axes are provided, mean is over the provided 2."""
        only_editorial_and_transparency, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
            editorial_score=90,
            transparency_score=90,
            # factcheck_score omitted
        )
        all_three_90, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
            editorial_score=90,
            factcheck_score=90,
            transparency_score=90,
        )
        # axes_mean is 90 in both cases (mean of [90, 90] == mean of [90, 90, 90]).
        # Should be identical.
        assert only_editorial_and_transparency == all_three_90

    def test_blend_weights_sum_to_one(self):
        """Defensive pin — if someone bumps SOURCE_LEGACY_WEIGHT without
        the AXES_WEIGHT counterpart, the source_component scale changes."""
        assert (
            ReliabilityScorer.SOURCE_LEGACY_WEIGHT
            + ReliabilityScorer.SOURCE_AXES_WEIGHT
        ) == pytest.approx(1.0)

    def test_axes_extreme_values_normalised(self):
        """Mig 041 enforces 0-100 bounds via CHECK constraints, but the
        calculator must also normalise defensively in case raw input
        bypasses the DB layer (e.g., LLM-suggested score)."""
        score, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
            editorial_score=150,  # >100, must be clamped
            factcheck_score=-20,  # <0, must be clamped
            transparency_score=50,
        )
        # editorial clamps to 100, factcheck to 0, transparency 50 → mean 50.
        # blended = 0.6 * 50 + 0.4 * 50 = 50. Same as legacy-only.
        score_legacy_only, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=6, verified_claims=6,
        )
        assert abs(score - score_legacy_only) <= 1
