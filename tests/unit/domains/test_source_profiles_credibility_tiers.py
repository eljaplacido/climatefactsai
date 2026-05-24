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

    def test_no_domains_in_rows_returns_unchanged(self):
        """If profile rows have no source_domain, the join can't happen —
        return rows untouched, no DB hit."""
        db = MagicMock()
        svc = _service_with_db(db)
        rows = [{"source_name": "X", "source_domain": None}]
        result = svc._attach_credibility_tiers(rows)
        assert result == rows
        db.execute_query.assert_not_called()

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
