"""Tests for the source assessment derivation (data-completeness Fix A).

source_profiles.editorial_standards / fact_check_record / transparency_level
default to 'unknown' and were written by no code path, so the Sources UI showed
"Not assessed" for every source. derive_source_assessment() maps the row's
numeric/tier signals to those three labels (a restatement of the platform's own
reliability tiering — not an independent audit). These tests pin the mapping and
the upsert apply path.
"""

from __future__ import annotations

from app.domains.content.source_profiles import (
    SourceProfileService,
    derive_source_assessment,
)


class TestDeriveSourceAssessment:
    def test_no_signal_returns_none(self):
        # Schema-default row: credibility 50, no articles, neutral tier, no FCR.
        assert derive_source_assessment(
            credibility_score=50,
            average_reliability_score=None,
            reliability_tier="public",
            false_claim_rate=0.0,
            total_articles_analyzed=0,
        ) is None

    def test_high_band(self):
        out = derive_source_assessment(
            credibility_score=82, total_articles_analyzed=20, false_claim_rate=0.0
        )
        assert out == {
            "editorial_standards": "rigorous",
            "fact_check_record": "good",
            "transparency_level": "high",
        }

    def test_high_band_excellent_factcheck(self):
        out = derive_source_assessment(
            credibility_score=92, total_articles_analyzed=30, false_claim_rate=0.0
        )
        assert out["fact_check_record"] == "excellent"
        assert out["editorial_standards"] == "rigorous"

    def test_moderate_band(self):
        out = derive_source_assessment(
            credibility_score=60, total_articles_analyzed=10, false_claim_rate=0.0
        )
        assert out == {
            "editorial_standards": "moderate",
            "fact_check_record": "mixed",
            "transparency_level": "moderate",
        }

    def test_low_band(self):
        out = derive_source_assessment(
            credibility_score=40, total_articles_analyzed=8, false_claim_rate=0.0
        )
        assert out == {
            "editorial_standards": "limited",
            "fact_check_record": "mixed",   # not 'poor' — low credibility alone never asserts poor fact-checking
            "transparency_level": "low",
        }

    def test_elevated_false_claim_rate_forces_poor(self):
        out = derive_source_assessment(
            credibility_score=82, total_articles_analyzed=20, false_claim_rate=0.20
        )
        assert out["fact_check_record"] == "poor"
        # ...but the credibility-driven editorial/transparency stay high.
        assert out["editorial_standards"] == "rigorous"
        assert out["transparency_level"] == "high"

    def test_mid_false_claim_rate_forces_mixed(self):
        out = derive_source_assessment(
            credibility_score=82, total_articles_analyzed=20, false_claim_rate=0.08
        )
        assert out["fact_check_record"] == "mixed"

    def test_scientific_tier_overrides_default_score(self):
        # Curated institutional source, no articles yet, default credibility.
        out = derive_source_assessment(
            credibility_score=50,
            reliability_tier="scientific",
            total_articles_analyzed=0,
            false_claim_rate=0.0,
        )
        assert out == {
            "editorial_standards": "rigorous",
            "fact_check_record": "good",
            "transparency_level": "high",
        }

    def test_average_reliability_fallback_when_no_credibility(self):
        out = derive_source_assessment(
            credibility_score=None,
            average_reliability_score=78,
            total_articles_analyzed=5,
        )
        assert out["editorial_standards"] == "rigorous"  # 78 >= 75 -> high band

    def test_avg_only_low_band(self):
        out = derive_source_assessment(
            credibility_score=None,
            average_reliability_score=45,
            total_articles_analyzed=3,
        )
        assert out["editorial_standards"] == "limited"
        assert out["transparency_level"] == "low"


class TestTierBridge:
    """ML-12: bridge evidence-backed source_credibility_tiers (tier + 3-axis
    scores) to the three labels when the profile has no per-article signal."""

    def test_t2_tier_bridges_when_no_other_signal(self):
        # Reuters/Guardian pattern: default profile (no articles) but a T2 tier.
        out = derive_source_assessment(
            credibility_score=50,
            reliability_tier="public",
            total_articles_analyzed=0,
            false_claim_rate=0.0,
            tier="T2",
            tier_editorial_score=70,
            tier_factcheck_score=75,
            tier_transparency_score=65,
        )
        assert out == {
            "editorial_standards": "moderate",
            "fact_check_record": "good",
            "transparency_level": "moderate",
        }

    def test_t1_tier_bridges_to_top_labels(self):
        out = derive_source_assessment(
            credibility_score=50,
            total_articles_analyzed=0,
            tier="T1",
            tier_editorial_score=90,
            tier_factcheck_score=90,
            tier_transparency_score=90,
        )
        assert out == {
            "editorial_standards": "rigorous",
            "fact_check_record": "excellent",
            "transparency_level": "high",
        }

    def test_t3_tier_bridges_to_mid_labels(self):
        out = derive_source_assessment(
            total_articles_analyzed=0,
            tier="T3",
            tier_editorial_score=55,
            tier_factcheck_score=50,
            tier_transparency_score=60,
        )
        assert out == {
            "editorial_standards": "moderate",
            "fact_check_record": "mixed",
            "transparency_level": "moderate",
        }

    def test_article_signal_takes_precedence_over_tier(self):
        # A profile WITH its own analysed articles derives from that signal;
        # the tier is a fallback only (finding: "when no other signal").
        out = derive_source_assessment(
            credibility_score=92,
            total_articles_analyzed=30,
            false_claim_rate=0.0,
            tier="T3",
            tier_editorial_score=55,
            tier_factcheck_score=50,
            tier_transparency_score=60,
        )
        assert out["editorial_standards"] == "rigorous"   # from the 92 score, not T3
        assert out["fact_check_record"] == "excellent"

    def test_non_evidence_tier_does_not_bridge(self):
        # 'unknown'/'retracted' tiers are not evidence-backed -> no invented rating.
        assert derive_source_assessment(
            credibility_score=50,
            total_articles_analyzed=0,
            tier="unknown",
            tier_editorial_score=30,
            tier_factcheck_score=25,
            tier_transparency_score=30,
        ) is None

    def test_tier_without_scores_bridges_via_tier_defaults(self):
        # Feed-added tier rows carry no explicit axis scores, but the T2 LEVEL is
        # evidence-backed -> bridge from the tier-level default (70/75/65).
        out = derive_source_assessment(
            credibility_score=50,
            total_articles_analyzed=0,
            tier="T2",
            tier_editorial_score=None,
            tier_factcheck_score=None,
            tier_transparency_score=None,
        )
        assert out == {
            "editorial_standards": "moderate",
            "fact_check_record": "good",
            "transparency_level": "moderate",
        }

    def test_t1_without_scores_bridges_via_tier_defaults(self):
        out = derive_source_assessment(
            total_articles_analyzed=0,
            tier="T1",
        )
        assert out == {
            "editorial_standards": "rigorous",
            "fact_check_record": "excellent",
            "transparency_level": "high",
        }

    def test_partial_scores_coalesce_with_tier_default(self):
        # explicit editorial 40 (limited) but NULL factcheck/transparency -> T2
        # defaults (good / moderate) fill the gaps.
        out = derive_source_assessment(
            total_articles_analyzed=0,
            tier="T2",
            tier_editorial_score=40,
            tier_factcheck_score=None,
            tier_transparency_score=None,
        )
        assert out["editorial_standards"] == "limited"
        assert out["fact_check_record"] == "good"
        assert out["transparency_level"] == "moderate"


class _FakeDB:
    """Captures the derived-assessment UPDATE for the apply-path test.

    Optionally serves a source_credibility_tiers row for the tier-bridge path.
    """

    def __init__(self, profile_row, columns=("reliability_tier",), tier_row=None):
        self.profile_row = profile_row
        self.columns = columns
        self.tier_row = tier_row
        self.updates = []

    def execute_query(self, query, params=None):
        n = " ".join(query.split()).lower()
        if "information_schema.columns" in n:
            return [{"column_name": c} for c in self.columns]
        if "from source_credibility_tiers" in n:
            return [self.tier_row] if self.tier_row else []
        if "from source_profiles" in n:
            return [self.profile_row]
        return []

    def execute_update(self, query, params=None):
        self.updates.append((query, params or {}))
        return 1


class TestApplyDerivedAssessment:
    def test_writes_derived_labels(self):
        db = _FakeDB({
            "credibility_score": 82,
            "average_reliability_score": 80.0,
            "reliability_tier": "public",
            "false_claim_rate": 0.0,
            "total_articles_analyzed": 20,
        })
        svc = SourceProfileService(db)
        svc._apply_derived_assessment("example.com")

        assert len(db.updates) == 1
        _, params = db.updates[0]
        assert params["editorial_standards"] == "rigorous"
        assert params["fact_check_record"] == "good"
        assert params["transparency_level"] == "high"
        assert params["domain"] == "example.com"

    def test_no_write_when_no_signal(self):
        db = _FakeDB({
            "credibility_score": 50,
            "average_reliability_score": None,
            "reliability_tier": "public",
            "false_claim_rate": 0.0,
            "total_articles_analyzed": 0,
        })
        svc = SourceProfileService(db)
        svc._apply_derived_assessment("example.com")
        assert db.updates == []

    def test_fails_soft_when_tier_column_absent(self):
        # No reliability_tier column -> service selects NULL AS reliability_tier;
        # derivation still works off credibility + articles.
        db = _FakeDB(
            {
                "credibility_score": 60,
                "average_reliability_score": 60.0,
                "reliability_tier": None,
                "false_claim_rate": 0.0,
                "total_articles_analyzed": 10,
            },
            columns=(),  # information_schema returns no reliability_tier
        )
        svc = SourceProfileService(db)
        svc._apply_derived_assessment("example.com")
        assert len(db.updates) == 1
        _, params = db.updates[0]
        assert params["editorial_standards"] == "moderate"

    def test_apply_bridges_from_tier_when_no_article_signal(self):
        # No-signal profile (Reuters-style) + a matching T2 tier row -> the
        # apply path bridges the tier's 3-axis scores to the labels.
        db = _FakeDB(
            {
                "credibility_score": 50,
                "average_reliability_score": None,
                "reliability_tier": "public",
                "false_claim_rate": 0.0,
                "total_articles_analyzed": 0,
            },
            tier_row={
                "tier": "T2",
                "editorial_score": 70,
                "factcheck_score": 75,
                "transparency_score": 65,
            },
        )
        svc = SourceProfileService(db)
        svc._apply_derived_assessment("reuters.com", "Reuters")
        assert len(db.updates) == 1
        _, params = db.updates[0]
        assert params["editorial_standards"] == "moderate"
        assert params["fact_check_record"] == "good"
        assert params["transparency_level"] == "moderate"
