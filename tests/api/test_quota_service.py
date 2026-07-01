"""Unit tests for the Phase 1A QuotaService (2026-05-23).

Pins:
- 3/3/2 Free-tier ladder (per the freemium decision saved in memory)
- Lifetime vs monthly semantics per quota key
- check() never raises; check_and_raise() emits structured 429 envelope
- Unknown tier strings fall through to 'anonymous' (privilege safety)
- Anonymous gets 0 limits across the board
- consume() is a no-op for lifetime keys and url_analysis (already tracked
  by source-of-truth table)

DB is mocked so the tests run in milliseconds and don't need Postgres.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.quota_service import (
    FREEMIUM_FREE_TIER_LIMITS,
    LIFETIME_KEYS,
    LIFETIME_USAGE_KEYS,
    MONTHLY_KEYS,
    QUOTA_LABELS,
    QUOTA_LIMITS_BY_TIER,
    QuotaService,
    _normalize_tier,
)


# ---------------------------------------------------------------------------
# Tier ladder pins — these are the user's explicit 2026-05-23 decision.
# Changing any of these requires updating
# `memory/freemium_quota_decision_2026_05_23.md` and the strategic memo.
# ---------------------------------------------------------------------------


class TestTierLadderPins:
    def test_free_tier_ladder(self):
        # 3 saved / 3 searches / 3 deep-research / 1 url / 1 compare.
        # deep_research raised 2->3 on 2026-05-31 (owner decision).
        free = QUOTA_LIMITS_BY_TIER["freemium"]
        assert free["saved_articles"] == 3
        assert free["saved_searches"] == 3
        assert free["deep_research"] == 3
        assert free["url_analysis"] == 1
        assert free["compare"] == 1

    def test_anonymous_is_zero_across_the_board(self):
        anon = QUOTA_LIMITS_BY_TIER["anonymous"]
        for v in anon.values():
            assert v == 0

    def test_enterprise_is_unlimited_across_the_board(self):
        ent = QUOTA_LIMITS_BY_TIER["enterprise"]
        for v in ent.values():
            assert v == -1  # -1 = unlimited

    def test_basic_is_strictly_higher_than_free(self):
        free = QUOTA_LIMITS_BY_TIER["freemium"]
        basic = QUOTA_LIMITS_BY_TIER["basic"]
        for k in free:
            assert basic[k] > free[k] or basic[k] == -1, (
                f"Basic regression on {k}: free={free[k]} basic={basic[k]}"
            )

    def test_free_and_freemium_alias_match(self):
        """The 'free' string used by some legacy auth code maps to 'freemium'."""
        assert QUOTA_LIMITS_BY_TIER["free"] == QUOTA_LIMITS_BY_TIER["freemium"]

    def test_lifetime_vs_monthly_partition_is_exhaustive(self):
        all_keys = set(FREEMIUM_FREE_TIER_LIMITS.keys())
        # Three disjoint buckets: lifetime-table-backed, monthly-usage, and
        # lifetime-usage-event (insights_extraction — 2026-06-02).
        partitioned = LIFETIME_KEYS | MONTHLY_KEYS | LIFETIME_USAGE_KEYS
        assert all_keys == partitioned, (
            "Every quota key must be exactly one of lifetime/monthly/lifetime-usage"
        )
        assert LIFETIME_KEYS.isdisjoint(MONTHLY_KEYS)
        assert LIFETIME_KEYS.isdisjoint(LIFETIME_USAGE_KEYS)
        assert MONTHLY_KEYS.isdisjoint(LIFETIME_USAGE_KEYS)

    def test_every_quota_has_a_human_label(self):
        for key in FREEMIUM_FREE_TIER_LIMITS:
            assert key in QUOTA_LABELS, f"{key!r} missing from QUOTA_LABELS"


# ---------------------------------------------------------------------------
# check() behaviour
# ---------------------------------------------------------------------------


class TestCheck:
    def setup_method(self):
        self.db = MagicMock()
        # Default: count query returns 0 (under quota)
        self.db.execute_query.return_value = [{"n": 0}]

    def _patch_db(self):
        return patch("api.quota_service.get_postgres", return_value=self.db)

    def test_anonymous_user_is_never_allowed(self):
        with self._patch_db():
            result = QuotaService.check(user_id=None, tier="anonymous", quota_key="saved_articles")
        assert result.allowed is False
        assert result.tier == "anonymous"
        assert result.limit == 0

    def test_unknown_tier_falls_through_to_anonymous(self):
        """Privilege-safety: malformed JWT claims must NOT grant Free access."""
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="enterprise-pro-platinum", quota_key="deep_research")
        assert result.tier == "anonymous"
        assert result.allowed is False

    def test_none_tier_falls_through_to_anonymous(self):
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier=None, quota_key="deep_research")
        assert result.tier == "anonymous"

    def test_free_user_under_quota_is_allowed(self):
        self.db.execute_query.return_value = [{"n": 1}]
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="freemium", quota_key="saved_articles")
        assert result.allowed is True
        assert result.used == 1
        assert result.limit == 3
        assert result.period == "lifetime"
        assert result.reset_at is None

    def test_free_user_at_quota_is_blocked(self):
        self.db.execute_query.return_value = [{"n": 3}]
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="freemium", quota_key="saved_articles")
        assert result.allowed is False
        assert result.used == 3
        assert result.limit == 3

    def test_free_user_over_quota_is_blocked(self):
        """Defensive: if a count somehow exceeds the limit, we still block."""
        self.db.execute_query.return_value = [{"n": 4}]
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="freemium", quota_key="saved_articles")
        assert result.allowed is False

    def test_unlimited_tier_always_allowed(self):
        self.db.execute_query.return_value = [{"n": 5000}]
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="enterprise", quota_key="deep_research")
        assert result.allowed is True
        assert result.limit == -1

    def test_monthly_quota_has_reset_at(self):
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="freemium", quota_key="deep_research")
        assert result.period == "monthly"
        assert result.reset_at is not None

    def test_check_returns_label_for_ui_copy(self):
        with self._patch_db():
            result = QuotaService.check(user_id="u-1", tier="freemium", quota_key="saved_articles")
        assert result.label == "saved articles"


# ---------------------------------------------------------------------------
# check_and_raise() behaviour
# ---------------------------------------------------------------------------


class TestCheckAndRaise:
    def setup_method(self):
        self.db = MagicMock()

    def _patch_db(self):
        return patch("api.quota_service.get_postgres", return_value=self.db)

    def test_returns_quota_check_when_allowed(self):
        self.db.execute_query.return_value = [{"n": 0}]
        with self._patch_db():
            result = QuotaService.check_and_raise(
                user_id="u-1", tier="freemium", quota_key="deep_research"
            )
        assert result.allowed is True

    def test_raises_429_when_blocked(self):
        self.db.execute_query.return_value = [{"n": 3}]  # freemium deep_research = 3
        with self._patch_db():
            with pytest.raises(HTTPException) as exc_info:
                QuotaService.check_and_raise(
                    user_id="u-1", tier="freemium", quota_key="deep_research"
                )
        assert exc_info.value.status_code == 429
        body = exc_info.value.detail
        assert body["error"] == "quota_exceeded"
        assert body["quota"]["quota_key"] == "deep_research"
        assert body["quota"]["used"] == 3
        assert body["quota"]["limit"] == 3
        assert "Upgrade" in body["message"]

    def test_429_payload_has_upgrade_url(self):
        self.db.execute_query.return_value = [{"n": 1}]
        with self._patch_db():
            with pytest.raises(HTTPException) as exc_info:
                QuotaService.check_and_raise(
                    user_id="u-1", tier="freemium", quota_key="url_analysis"
                )
        assert exc_info.value.detail["quota"]["upgrade_url"] == "/dashboard/subscription"


# ---------------------------------------------------------------------------
# consume() behaviour
# ---------------------------------------------------------------------------


class TestConsume:
    def test_lifetime_keys_skip_consume(self):
        """Lifetime quotas don't go through user_usage — the underlying
        table (user_bookmarks, user_saved_queries) is the source of truth."""
        with patch("api.rate_limiter.UsageTracker.log_usage") as mock_log:
            QuotaService.consume(user_id="u-1", quota_key="saved_articles")
            QuotaService.consume(user_id="u-1", quota_key="saved_searches")
        mock_log.assert_not_called()

    def test_url_analysis_skips_consume(self):
        """url_analyses row IS the consumption record — don't double-count."""
        with patch("api.rate_limiter.UsageTracker.log_usage") as mock_log:
            QuotaService.consume(user_id="u-1", quota_key="url_analysis")
        mock_log.assert_not_called()

    def test_deep_research_calls_log_usage(self):
        with patch("api.rate_limiter.UsageTracker.log_usage") as mock_log:
            QuotaService.consume(
                user_id="u-1",
                quota_key="deep_research",
                resource_url="deep_search:test",
            )
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] == "u-1"
        assert call_kwargs["usage_type"] == "deep_research"

    def test_compare_calls_log_usage(self):
        with patch("api.rate_limiter.UsageTracker.log_usage") as mock_log:
            QuotaService.consume(user_id="u-1", quota_key="compare")
        mock_log.assert_called_once()

    def test_anonymous_consume_is_noop(self):
        with patch("api.rate_limiter.UsageTracker.log_usage") as mock_log:
            QuotaService.consume(user_id=None, quota_key="deep_research")
        mock_log.assert_not_called()

    def test_consume_never_raises_on_log_failure(self):
        """Bookkeeping failure must not fail the user request."""
        with patch(
            "api.rate_limiter.UsageTracker.log_usage", side_effect=RuntimeError("boom")
        ):
            # Should not raise
            QuotaService.consume(user_id="u-1", quota_key="deep_research")


# ---------------------------------------------------------------------------
# summary() behaviour
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_returns_all_quota_keys(self):
        db = MagicMock()
        db.execute_query.return_value = [{"n": 0}]
        with patch("api.quota_service.get_postgres", return_value=db):
            rows = QuotaService.summary(user_id="u-1", tier="freemium")
        keys = {r["quota_key"] for r in rows}
        assert keys == set(FREEMIUM_FREE_TIER_LIMITS.keys())

    def test_summary_for_anonymous_shows_zero_limits(self):
        db = MagicMock()
        db.execute_query.return_value = [{"n": 0}]
        with patch("api.quota_service.get_postgres", return_value=db):
            rows = QuotaService.summary(user_id=None, tier="anonymous")
        for r in rows:
            assert r["limit"] == 0
            assert r["allowed"] is False


# ---------------------------------------------------------------------------
# ML-16 — tier-alias normalization
# ---------------------------------------------------------------------------
# The Stripe webhook writes tier='pro' (its price reverse-map's first match),
# which is NOT a QUOTA_LIMITS_BY_TIER key. Without the alias, _normalize_tier
# fell through to 'anonymous' (all-zero quotas) and every gated action 429'd
# for a paying Professional customer.


class TestTierAliasNormalization:
    def test_pro_alias_maps_to_professional(self):
        assert _normalize_tier("pro") == "professional"

    def test_pro_alias_is_case_and_whitespace_insensitive(self):
        assert _normalize_tier("  PRO ") == "professional"

    def test_prof_alias_maps_to_professional(self):
        assert _normalize_tier("prof") == "professional"

    def test_free_alias_maps_to_freemium(self):
        assert _normalize_tier("free") == "freemium"

    def test_canonical_tiers_pass_through_unchanged(self):
        for t in ("anonymous", "freemium", "basic", "professional", "enterprise"):
            assert _normalize_tier(t) == t

    def test_unknown_tier_still_falls_through_to_anonymous(self):
        # Privilege safety must survive the alias table.
        assert _normalize_tier("enterprise-pro-platinum") == "anonymous"

    def test_professional_paying_customer_gets_nonzero_quota(self):
        """A tier='pro' JWT/webkook claim must resolve to professional quotas,
        NOT anonymous-zero — otherwise a paying customer is 429'd everywhere."""
        db = MagicMock()
        db.execute_query.return_value = [{"n": 0}]
        with patch("api.quota_service.get_postgres", return_value=db):
            result = QuotaService.check(
                user_id="u-pro", tier="pro", quota_key="url_analysis"
            )
        assert result.tier == "professional"
        assert result.limit == QUOTA_LIMITS_BY_TIER["professional"]["url_analysis"]
        assert result.limit > 0
        assert result.allowed is True


# ---------------------------------------------------------------------------
# ML-08 — url_analysis is gated ONLY by QuotaService, not the legacy middleware
# ---------------------------------------------------------------------------
# The freemium TIER_LIMITS in rate_limiter still carries
# url_analyses_per_month=0. The middleware used to gate url_analysis on that,
# double-gating free users to 0 while GET /api/quota advertised url_analysis as
# available (limit 1). The middleware branch was removed so QuotaService is the
# single source of truth for the url_analysis entitlement.


def _make_request(path: str, method: str, user):
    """Minimal stand-in exposing only what RateLimitMiddleware._dispatch reads."""

    class _URL:
        def __init__(self, p):
            self.path = p

    class _Client:
        host = "203.0.113.7"

    class _State:
        pass

    class _Req:
        def __init__(self):
            self.url = _URL(path)
            self.method = method
            self.headers = {}
            self.client = _Client()
            self.state = _State()
            self.state.user = user

    return _Req()


class TestUrlAnalysisMiddlewareGate:
    @pytest.mark.asyncio
    async def test_freemium_url_analysis_passes_through_middleware(self):
        """A freemium user hitting /api/analyze-url must NOT be 429'd by the
        rate-limit middleware — no branch may gate url_analysis to 0."""
        from api.rate_limiter import RateLimitMiddleware

        mw = RateLimitMiddleware(app=None)

        sentinel = object()
        calls = {"n": 0}

        async def call_next(_request):
            calls["n"] += 1
            return sentinel

        request = _make_request(
            "/api/analyze-url",
            "POST",
            user={
                "user_id": "11111111-1111-1111-1111-111111111111",
                "subscription_tier": "freemium",
            },
        )
        result = await mw._dispatch(request, call_next)

        assert result is sentinel  # request reached the route, not short-circuited
        assert calls["n"] == 1     # middleware did not block with a 429

    def test_quota_service_governs_freemium_url_analysis(self):
        """Corroborates ML-08: freemium url_analysis is a positive QuotaService
        allowance (1/mo), not the zeroed middleware limit."""
        db = MagicMock()
        db.execute_query.return_value = [{"n": 0}]
        with patch("api.quota_service.get_postgres", return_value=db):
            result = QuotaService.check(
                user_id="u-1", tier="freemium", quota_key="url_analysis"
            )
        assert result.limit == 1
        assert result.allowed is True
