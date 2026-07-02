"""Tests for SourceProfileService._attach_credibility_tiers (Day 2 2026-05-23).

The Day 2 §3.7 rework deleted the hardcoded "Reference Scientific Sources"
list on the /sources page and now surfaces the real source_credibility_tiers
table (migration 027) via this LEFT-JOIN helper. These tests pin:

  - The helper enriches matching rows with tier + tier_prior_bonus
  - Non-matching rows get tier=None + tier_prior_bonus=None (UI knows to
    render "not assessed")
  - Migration-not-yet-applied clusters fail soft (helper returns rows
    unchanged rather than raising)
  - Domain normalisation handles 'www.' prefix and case
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.domains.content.source_profiles import SourceProfileService


def _service_with_db(db_mock):
    """Build a SourceProfileService with a stubbed DB."""
    svc = SourceProfileService(db_mock)
    return svc


class TestAttachCredibilityTiers:
    def test_empty_input_returns_empty(self):
        db = MagicMock()
        svc = _service_with_db(db)
        result = svc._attach_credibility_tiers([])
        assert result == []
        # No DB hit when input is empty
        db.execute_query.assert_not_called()

    def test_no_domain_no_name_returns_unchanged(self):
        """If profile rows have neither source_domain nor source_name, the join
        can't happen — return rows untouched, no DB hit."""
        db = MagicMock()
        svc = _service_with_db(db)
        rows = [{"source_name": None, "source_domain": None}]
        result = svc._attach_credibility_tiers(rows)
        assert result == rows
        db.execute_query.assert_not_called()

    def test_name_only_row_still_queries_by_name(self):
        """A profile with no usable domain but a source_name is now joined by
        name (the fabricated-domain recovery path). DB IS hit; a non-match
        yields explicit null tier fields."""
        db = MagicMock()
        db.execute_query.return_value = []  # no tier match for "X"
        svc = _service_with_db(db)
        rows = [{"source_name": "X", "source_domain": None}]
        result = svc._attach_credibility_tiers(rows)
        db.execute_query.assert_called_once()
        assert result[0]["tier"] is None
        assert result[0]["tier_prior_bonus"] is None

    def test_name_match_recovers_tier_when_domain_is_fabricated(self):
        """Core 2026-06-02 fix: a phantom profile carries a fabricated slug
        domain (`carbon-brief-c078`) that can't join, but its source_name is
        correct. A name match against the tier table recovers the real tier."""
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "carbonbrief.org", "source_name": "Carbon Brief", "tier": "T1", "prior_bonus": 30},
        ]
        svc = _service_with_db(db)
        rows = [{"source_name": "Carbon Brief", "source_domain": "carbon-brief-c078"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] == "T1"
        assert result[0]["tier_prior_bonus"] == 30

    def test_domain_match_preferred_over_name_match(self):
        """When a row matches one tier row by domain and a *different* tier row
        by name, the domain match (most specific) wins."""
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "example.com", "source_name": "Other", "tier": "T3", "prior_bonus": 5},
            {"domain": "elsewhere.org", "source_name": "Example", "tier": "T1", "prior_bonus": 30},
        ]
        svc = _service_with_db(db)
        rows = [{"source_name": "Example", "source_domain": "example.com"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] == "T3"  # domain match wins over name match

    def test_best_tier_wins_on_multiple_name_matches(self):
        """A source_name seeded under two tier rows (different migrations) must
        resolve to the best (T1 over T2)."""
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "reporterre.net", "source_name": "Reporterre (FR)", "tier": "T2", "prior_bonus": 15},
            {"domain": "reporterre.net", "source_name": "Reporterre (FR)", "tier": "T1", "prior_bonus": 30},
        ]
        svc = _service_with_db(db)
        rows = [{"source_name": "Reporterre (FR)", "source_domain": "reporterre-fr-80a4"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] == "T1"

    def test_matching_rows_get_tier_and_prior_bonus(self):
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "nature.com", "tier": "Q1", "prior_bonus": 30},
            {"domain": "ipcc.ch", "tier": "ipcc", "prior_bonus": 40},
        ]
        svc = _service_with_db(db)
        rows = [
            {"source_name": "Nature", "source_domain": "nature.com", "credibility_score": 90},
            {"source_name": "IPCC", "source_domain": "ipcc.ch", "credibility_score": 95},
        ]
        result = svc._attach_credibility_tiers(rows)
        assert len(result) == 2
        assert result[0]["tier"] == "Q1"
        assert result[0]["tier_prior_bonus"] == 30
        assert result[1]["tier"] == "ipcc"
        assert result[1]["tier_prior_bonus"] == 40

    def test_non_matching_rows_get_null_tier_fields(self):
        """Sources not yet tier-classified must surface explicit nulls so the
        frontend can render 'not assessed' rather than crash on missing keys."""
        db = MagicMock()
        db.execute_query.return_value = []  # no tier matches
        svc = _service_with_db(db)
        rows = [{"source_name": "BlogCo", "source_domain": "blogco.com"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] is None
        assert result[0]["tier_prior_bonus"] is None

    def test_mixed_match_and_no_match(self):
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "nature.com", "tier": "Q1", "prior_bonus": 30},
        ]
        svc = _service_with_db(db)
        rows = [
            {"source_name": "Nature", "source_domain": "nature.com"},
            {"source_name": "BlogCo", "source_domain": "blogco.com"},
        ]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] == "Q1"
        assert result[1]["tier"] is None

    def test_evidence_url_and_classification_exposed(self):
        """ML-12: the join must surface the public evidence_url + classification
        so the Sources UI can render a 'Why this tier?' auditor link."""
        db = MagicMock()
        db.execute_query.return_value = [
            {
                "domain": "reuters.com",
                "source_name": "Reuters",
                "tier": "T2",
                "prior_bonus": 15,
                "editorial_score": 92,
                "factcheck_score": 88,
                "transparency_score": 85,
                "evidence_url": "https://www.reuters.com/policies/corrections/",
                "classification": "wire_service_corrections",
            },
        ]
        svc = _service_with_db(db)
        rows = [{"source_name": "Reuters", "source_domain": "reuters.com"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["evidence_url"] == "https://www.reuters.com/policies/corrections/"
        assert result[0]["classification"] == "wire_service_corrections"
        # The SELECT must actually request the two new columns.
        select_sql = " ".join(db.execute_query.call_args.args[0].split()).lower()
        assert "evidence_url" in select_sql
        assert "classification" in select_sql

    def test_domain_normalisation_strips_www_and_lowercases(self):
        """Profile rows commonly have 'www.Example.com' while the tier
        table is normalised to 'example.com'. The helper MUST match these."""
        db = MagicMock()
        db.execute_query.return_value = [
            {"domain": "example.com", "tier": "blog", "prior_bonus": 0},
        ]
        svc = _service_with_db(db)
        rows = [{"source_name": "Example", "source_domain": "www.Example.com"}]
        result = svc._attach_credibility_tiers(rows)
        assert result[0]["tier"] == "blog"

    def test_migration_not_applied_fails_soft(self):
        """When source_credibility_tiers table doesn't exist (older clusters),
        the helper logs a debug message and returns rows unchanged — never
        raises. Critical: profile listings must keep working even pre-027."""
        db = MagicMock()
        db.execute_query.side_effect = RuntimeError(
            'relation "source_credibility_tiers" does not exist'
        )
        svc = _service_with_db(db)
        rows = [{"source_name": "Nature", "source_domain": "nature.com"}]
        # Must not raise
        result = svc._attach_credibility_tiers(rows)
        assert result == rows

    def test_domain_passed_to_join_query_is_lowercase_array(self):
        """Assert the SQL parameter shape — protects against a regression
        where the query would do per-row lookups (N+1) instead of one
        batched ANY query."""
        db = MagicMock()
        db.execute_query.return_value = []
        svc = _service_with_db(db)
        rows = [
            {"source_name": "Nature", "source_domain": "NATURE.com"},
            {"source_name": "IPCC", "source_domain": "ipcc.ch"},
        ]
        svc._attach_credibility_tiers(rows)
        # One call, with both domains in the params (batched, not N+1)
        assert db.execute_query.call_count == 1
        call_args = db.execute_query.call_args
        params = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("params") or call_args.args[0][1]
        # Find the domains param regardless of positional vs kwargs style
        if isinstance(params, dict):
            domains = params.get("domains", [])
        else:
            domains = []
        assert "nature.com" in domains
        assert "ipcc.ch" in domains
