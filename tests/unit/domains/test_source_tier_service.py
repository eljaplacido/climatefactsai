"""Source-tier service — domain resolution, tier→score mapping, 3-axis lookup.

This module feeds the reliability scorer (source component + 3-axis blend) and
the /articles 3-axis exposure, but was only covered indirectly via DB-gated
route tests (2026-06-10 platform audit). These unit tests pin the pure
resolution + mapping logic by patching the LRU-cached DB lookups.
"""

from __future__ import annotations

import app.domains.trust.source_tier_service as sts


class TestExtractDomain:
    def test_url_strips_scheme_and_www(self):
        assert sts._extract_domain("https://www.reuters.com/world/x") == "reuters.com"

    def test_http_scheme(self):
        assert sts._extract_domain("http://example.org") == "example.org"

    def test_bare_name_lowercased_passthrough(self):
        assert sts._extract_domain("Reuters") == "reuters"

    def test_path_without_scheme_returns_none(self):
        assert sts._extract_domain("some/path/thing") is None


class TestSourceCredibilityScore:
    """tier band -> 0-100 base score. The historical case bug (every tier
    silently mapping to 50) must not regress."""

    def test_t1_maps_to_90(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: (30, "T1"))
        assert sts.get_source_credibility_score(object(), "reuters.com") == 90

    def test_t2_maps_to_75(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: (15, "T2"))
        assert sts.get_source_credibility_score(object(), "x.com") == 75

    def test_t3_maps_to_60(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: (5, "T3"))
        assert sts.get_source_credibility_score(object(), "x.com") == 60

    def test_db_miss_is_neutral_50(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: None)
        assert sts.get_source_credibility_score(object(), "unknown-source.com") == 50

    def test_retracted_maps_to_20(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: (-30, "retracted"))
        assert sts.get_source_credibility_score(object(), "bad.com") == 20


class TestThreeAxisScores:
    def test_returns_tuple_on_hit(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup_axes", lambda db, d, n: (88, 77, 66))
        assert sts.get_source_3axis_scores(object(), "reuters.com") == (88, 77, 66)

    def test_none_when_domain_unresolvable(self):
        # A path-shaped source_name yields no domain -> None without a DB call.
        assert sts.get_source_3axis_scores(object(), "some/path") is None

    def test_none_on_db_miss(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup_axes", lambda db, d, n: None)
        assert sts.get_source_3axis_scores(object(), "unknown.com") is None

    def test_explicit_domain_overrides_name(self, monkeypatch):
        seen = {}

        def _spy(db, domain, name):
            seen["domain"] = domain
            return (10, 20, 30)

        monkeypatch.setattr(sts, "_db_lookup_axes", _spy)
        sts.get_source_3axis_scores(object(), "Reuters", domain="reuters.com")
        assert seen["domain"] == "reuters.com"


class TestTierPrior:
    def test_db_hit_wins(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: (15, "T2"))
        assert sts.get_source_tier_prior(object(), "x.com") == (15, "T2")

    def test_legacy_known_venue_fallback(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: None)
        assert sts.get_source_tier_prior(object(), "Nature") == (sts.LEGACY_TIER_BONUS, "T1")

    def test_default_unknown(self, monkeypatch):
        monkeypatch.setattr(sts, "_db_lookup", lambda db, d, n: None)
        assert sts.get_source_tier_prior(object(), "Some Random Blog") == (0, "unknown")
