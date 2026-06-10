"""Reliability scorer — claim-density factor + limited-evidence cap (Slice 4).

Honest-Gap-Audit v2 item 4 documented the pre-Slice-4 behaviour as:

  Source 80 + 1/1 verified claim + neutral relevance
    -> source_component=40, claims_component=30, relevance=12
    -> total=82 -> HIGH

That's the bug — an article with one trivial verified claim showed a 90%
credibility chip when it had barely been examined. Slice 4 fixes this two
ways: a density_factor scaling the claims contribution, and a HIGH-cap
when total_claims < LIMITED_EVIDENCE_THRESHOLD. These tests pin the new
math so a future formula tweak can't quietly reopen the gap.
"""

from __future__ import annotations

import pytest

from shared.reliability_scorer import ReliabilityScorer, CredibilityLevel


class TestClaimDensityFactor:
    """Density factor is min(1, total_claims/6). 1 claim ~> 17% of claims
    weight; 6+ claims => full weight. Pins the math so a constant rename
    or a formula refactor fails loudly."""

    def test_one_claim_gets_reduced_weight_not_full(self):
        """Pre-Slice-4: source=80 + 1/1 verified -> 82 HIGH. Now should
        be substantially lower and capped MEDIUM."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=80,
            total_claims=1,
            verified_claims=1,
            false_claims=0,
            misleading_claims=0,
            content_relevance_score=0.6,
        )
        # claims_component now ~= 100 * 0.30 * (1/6) = 5 (was 30)
        # total ~= 40 + 5 + 12 = 57 (was 82)
        assert score < 70, (
            f"Single-claim article scored {score}; expected substantial "
            f"drop from pre-Slice-4 value of 82"
        )
        # Even if score sneaks past 80 in some scenario, the level cap
        # prevents HIGH for limited-evidence articles.
        assert level == CredibilityLevel.MEDIUM, (
            f"Single-claim article got level {level}; expected MEDIUM "
            f"(LIMITED_EVIDENCE_THRESHOLD={ReliabilityScorer.LIMITED_EVIDENCE_THRESHOLD})"
        )

    def test_six_claims_gets_full_weight(self):
        """At CLAIMS_FOR_FULL_CREDIT, density_factor=1.0 — score should
        match the pre-Slice-4 formula (no penalty)."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=80,
            total_claims=6,
            verified_claims=6,
            false_claims=0,
            misleading_claims=0,
            content_relevance_score=0.6,
        )
        # claims_component = 100 * 0.30 * 1.0 = 30
        # total = 40 + 30 + 12 = 82 -> HIGH
        assert score >= 80
        assert level == CredibilityLevel.HIGH

    def test_three_claims_is_threshold_boundary(self):
        """At LIMITED_EVIDENCE_THRESHOLD (3), the HIGH-cap should NOT
        apply (>= threshold = passes). Density factor still reduces the
        score because we're below CLAIMS_FOR_FULL_CREDIT (6)."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=3,
            verified_claims=3,
            false_claims=0,
            misleading_claims=0,
            content_relevance_score=0.9,
        )
        # density = 3/6 = 0.5 -> claims_component = 100 * 0.30 * 0.5 = 15
        # source_component = 90 * 0.50 = 45; relevance_component = 90*.20 = 18
        # total = 78 -> MEDIUM (not HIGH because score < 80, NOT because of cap)
        assert score < 80
        # Threshold is "< 3", so 3 claims should NOT hit the cap.
        assert level == CredibilityLevel.MEDIUM

    @pytest.mark.parametrize("total_claims,expected_factor", [
        (1, 1 / 6),
        (2, 2 / 6),
        (3, 3 / 6),
        (4, 4 / 6),
        (5, 5 / 6),
        (6, 1.0),
        (10, 1.0),  # capped
    ])
    def test_density_factor_curve(self, total_claims, expected_factor):
        """Spot-check the curve at every claim count from 1-6 + capped at 10.
        All other inputs held constant so the delta is entirely the density
        factor."""
        score, _ = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=0,  # zero out source so we isolate claims
            total_claims=total_claims,
            verified_claims=total_claims,
            false_claims=0,
            misleading_claims=0,
            content_relevance_score=0.0,  # zero out relevance too
        )
        # All weight is in claims_component now.
        expected = 100 * 0.30 * expected_factor
        assert abs(score - round(expected)) <= 1, (
            f"{total_claims} claims: expected score~{round(expected)}, got {score}"
        )


class TestLimitedEvidenceLabel:
    """The HIGH cap kicks in when total_claims < 3 (now including zero).
    Zero-claims articles get NO verification credit (2026-06-09 audit) so
    empty-evidence can score LOW and can never reach HIGH."""

    def test_zero_claims_strong_source_caps_at_medium(self):
        """2026-06-09 audit — an unverified article (0 claims) from a strong
        source used to score 81/HIGH on the neutral-60 path. With no
        verification credit it now maxes at source(45)+relevance(18)=63 and
        is held at MEDIUM: you cannot be HIGH credibility with zero evidence."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=0,
            verified_claims=0,
            content_relevance_score=0.9,
        )
        assert score < ReliabilityScorer.THRESHOLD_HIGH, (
            f"zero-claims article scored {score}; must stay below HIGH"
        )
        assert level == CredibilityLevel.MEDIUM

    def test_zero_claims_average_source_can_score_low(self):
        """The core audit fix: empty-evidence must be ABLE to rate LOW. With
        an average source (50) and neutral relevance (0.5) the OLD neutral-60
        floor scored 25 + 18 + 10 = 53 -> MEDIUM. The NEW math forfeits the
        claims credit: 25 + 0 + 10 = 35 -> LOW. This is the exact verdict that
        used to be unreachable."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=50,
            total_claims=0,
            verified_claims=0,
            content_relevance_score=0.5,
        )
        assert score < ReliabilityScorer.THRESHOLD_MEDIUM, (
            f"zero-claims average-source article scored {score}; expected LOW "
            f"(was floored at MEDIUM=53 by the old neutral-60 default)"
        )
        assert level == CredibilityLevel.LOW

    def test_zero_claims_top_source_max_is_medium(self):
        """Even a perfect source + perfect relevance cannot reach HIGH with
        zero claims: the claims weight (30 pts) is forfeited, capping the
        ceiling at 70."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=100,
            total_claims=0,
            verified_claims=0,
            content_relevance_score=1.0,
        )
        assert score <= 70
        assert level == CredibilityLevel.MEDIUM

    def test_two_claims_caps_high_to_medium(self):
        """Below threshold (3) — cap fires."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=95,
            total_claims=2,
            verified_claims=2,
            content_relevance_score=1.0,
        )
        # Whatever the raw score, level must be capped at MEDIUM.
        assert level == CredibilityLevel.MEDIUM, (
            f"2-claim article got level {level}; HIGH cap should have fired"
        )

    def test_false_claims_still_yield_mixed_even_with_low_density(self):
        """False-claims override is independent of density — MIXED/LOW
        beats the limited-evidence cap because false content is the
        bigger trust failure."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=1,
            verified_claims=0,
            false_claims=1,
            content_relevance_score=0.5,
        )
        assert level in {CredibilityLevel.MIXED, CredibilityLevel.LOW}


class TestIsLimitedEvidenceHelper:
    """Helper used by /articles/{id} page to show the badge."""

    @pytest.mark.parametrize("n,expected", [
        (0, True),
        (1, True),
        (2, True),
        (3, False),
        (4, False),
        (10, False),
    ])
    def test_is_limited_evidence(self, n, expected):
        assert ReliabilityScorer.is_limited_evidence(n) is expected
