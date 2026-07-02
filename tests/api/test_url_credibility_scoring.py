"""Regression tests for verification-backed URL credibility scoring (audit seq-4).

The live URL-analysis path displayed a credibility label derived purely from text
length + claim count (an extraction-quality heuristic, self-commented as "NOT a
verified credibility score") while real per-claim verdicts from Step 7.5 were
discarded. Step 7.6 now feeds those verdicts + source credibility into the
canonical ReliabilityScorer. These tests pin the honest behavior.
"""

from __future__ import annotations

from api.url_analysis_routes import _finalize_credibility, _verdicts_to_claim_counts
from shared.reliability_scorer import ReliabilityScorer


class TestVerdictMapping:
    def test_maps_each_verdict_bucket(self):
        fc = [
            {"verdict": "verified"},
            {"verdict": "verified"},
            {"verdict": "disputed"},
            {"verdict": "partially_true"},
            {"verdict": "partially_verified"},
            {"verdict": "unverified"},
        ]
        verified, false, misleading = _verdicts_to_claim_counts(fc)
        assert verified == 2
        assert false == 1          # disputed
        assert misleading == 2     # partially_true + partially_verified
        # unverified counts toward neither

    def test_empty(self):
        assert _verdicts_to_claim_counts([]) == (0, 0, 0)


class TestHonestScoring:
    def test_disputed_claims_are_not_high_even_with_good_source(self):
        """A reputable source whose claims get DISPUTED must not read HIGH —
        the old heuristic would have called a long, claim-dense article HIGH."""
        verified, false, misleading = _verdicts_to_claim_counts(
            [{"verdict": "disputed"}, {"verdict": "disputed"}, {"verdict": "disputed"}]
        )
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=3,
            verified_claims=verified,
            false_claims=false,
            misleading_claims=misleading,
        )
        assert level != "HIGH"

    def test_few_verified_claims_capped_below_high(self):
        """Limited evidence (1-2 claims) must not yield HIGH regardless of source —
        the density/limited-evidence honesty cap applies."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=95,
            total_claims=1,
            verified_claims=1,
            false_claims=0,
            misleading_claims=0,
        )
        assert level != "HIGH"

    def test_well_verified_reputable_article_can_reach_high(self):
        """Enough verified claims + a strong source SHOULD be able to read HIGH —
        the honest path still rewards genuinely well-supported analysis."""
        score, level = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=95,
            total_claims=6,
            verified_claims=6,
            false_claims=0,
            misleading_claims=0,
        )
        assert score >= 70


class TestCredibilityFloorAndScoreBasis:
    """ML-09: a HIGH/MEDIUM badge must be verification-backed. When no claim
    reaches a supporting/verified verdict (all-unverified, or zero fact-checks),
    the text-length heuristic must be FLOORED to UNVERIFIED, and score_basis must
    label whether verdicts or the heuristic drove the score."""

    def test_all_unverified_factchecks_do_not_return_high(self):
        # ReliabilityScorer ran on real (all-unverified) verdicts + a strong
        # source, so verification_backed=True — but nothing was actually
        # supported, so the badge must NOT read HIGH/MEDIUM.
        fc = [{"verdict": "unverified"}, {"verdict": "unverified"}, {"verdict": "unverified"}]
        score, level, basis = _finalize_credibility(
            fact_checks=fc,
            reliability_score=70,
            overall_credibility="MEDIUM",
            verification_backed=True,
        )
        assert level == "UNVERIFIED"
        assert level != "HIGH"
        assert score <= 25
        assert basis == "verification_backed"

    def test_zero_factchecks_heuristic_high_is_floored(self):
        # No verification ran (empty fact_checks) but the text-length heuristic
        # emitted HIGH/70 — this is the exact ML-09 bug. Floor + honest basis.
        score, level, basis = _finalize_credibility(
            fact_checks=[],
            reliability_score=70,
            overall_credibility="HIGH",
            verification_backed=False,
        )
        assert level == "UNVERIFIED"
        assert score <= 25
        assert basis == "extraction_heuristic"

    def test_verified_claim_keeps_high_and_is_verification_backed(self):
        # At least one supporting verdict → the honest path still allows HIGH.
        fc = [{"verdict": "verified"}, {"verdict": "verified"}]
        score, level, basis = _finalize_credibility(
            fact_checks=fc,
            reliability_score=85,
            overall_credibility="HIGH",
            verification_backed=True,
        )
        assert level == "HIGH"
        assert score == 85
        assert basis == "verification_backed"

    def test_disputed_low_is_not_refloored_to_unverified(self):
        # Disputed claims are verification-backed and already read LOW — we must
        # NOT overwrite that honest LOW with UNVERIFIED (the floor only touches
        # inflated HIGH/MEDIUM labels).
        fc = [{"verdict": "disputed"}, {"verdict": "disputed"}]
        score, level, basis = _finalize_credibility(
            fact_checks=fc,
            reliability_score=30,
            overall_credibility="LOW",
            verification_backed=True,
        )
        assert level == "LOW"
        assert score == 30
        assert basis == "verification_backed"
