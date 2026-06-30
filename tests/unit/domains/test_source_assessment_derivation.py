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


class _FakeDB:
    """Captures the derived-assessment UPDATE for the apply-path test."""

    def __init__(self, profile_row, columns=("reliability_tier",)):
        self.profile_row = profile_row
        self.columns = columns
        self.updates = []

    def execute_query(self, query, params=None):
        n = " ".join(query.split()).lower()
        if "information_schema.columns" in n:
            return [{"column_name": c} for c in self.columns]
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
