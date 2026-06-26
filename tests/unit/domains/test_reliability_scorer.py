"""Canonical ReliabilityScorer contract (audit TRUST-03).

The live verification pipeline (services.VerificationService.verify_article) now
delegates scoring to shared.reliability_scorer.ReliabilityScorer instead of a
homegrown claims-only ratio that ignored source credibility and the 3-axis
source scores. These tests pin the properties the verify path now relies on:
source weighting, the limited-evidence cap, the disputed->misleading mapping,
and the 3-axis blend.
"""

from __future__ import annotations

from shared.reliability_scorer import ReliabilityScorer as RS


class TestReliabilityScorerCanonical:
    def test_source_credibility_moves_the_score(self):
        # Identical claims, different source — source is weighted 50%, so the
        # score MUST differ (the homegrown formula ignored it entirely).
        low, _ = RS.calculate_reliability_score(
            source_credibility_score=30, total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
        )
        high, _ = RS.calculate_reliability_score(
            source_credibility_score=95, total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
        )
        assert high > low

    def test_thin_evidence_never_high(self):
        # A single verified claim from a perfect source must not be HIGH.
        _, level = RS.calculate_reliability_score(
            source_credibility_score=100, total_claims=1, verified_claims=1,
            content_relevance_score=1.0,
        )
        assert level != "HIGH"

    def test_deep_evidence_can_reach_high(self):
        _, level = RS.calculate_reliability_score(
            source_credibility_score=95, total_claims=8, verified_claims=8,
            content_relevance_score=0.9,
        )
        assert level == "HIGH"

    def test_disputed_mapped_to_misleading_caps_at_medium(self):
        # verify_article maps a 'disputed' verdict -> misleading_claims, which
        # caps the level at MEDIUM regardless of source quality.
        _, level = RS.calculate_reliability_score(
            source_credibility_score=95, total_claims=6, verified_claims=3,
            misleading_claims=3, content_relevance_score=0.9,
        )
        assert level in ("MEDIUM", "LOW")

    def test_three_axis_blend_lifts_a_weak_legacy_source(self):
        base, _ = RS.calculate_reliability_score(
            source_credibility_score=40, total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
        )
        blended, _ = RS.calculate_reliability_score(
            source_credibility_score=40, total_claims=6, verified_claims=6,
            content_relevance_score=0.7,
            editorial_score=95, factcheck_score=95, transparency_score=95,
        )
        assert blended > base
