"""Regression tests for verification-backed URL credibility scoring (audit seq-4).

The live URL-analysis path displayed a credibility label derived purely from text
length + claim count (an extraction-quality heuristic, self-commented as "NOT a
verified credibility score") while real per-claim verdicts from Step 7.5 were
discarded. Step 7.6 now feeds those verdicts + source credibility into the
canonical ReliabilityScorer. These tests pin the honest behavior.
"""

from __future__ import annotations

from api.url_analysis_routes import _verdicts_to_claim_counts
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
