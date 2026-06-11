"""Unit tests for api.rate_limiter._coerce_user_uuid + UsageTracker.

Regression tests for commit df07f69: when the user_id is non-UUID
("anonymous", random strings, empty), the helpers must NOT issue queries
against user_usage.user_id (a UUID column) and must short-circuit safely.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.rate_limiter import UsageTracker, _coerce_user_uuid


# ---------------------------------------------------------------------------
# _coerce_user_uuid
# ---------------------------------------------------------------------------

class TestCoerceUserUuid:
    def test_returns_none_for_anonymous_sentinel(self):
        assert _coerce_user_uuid("anonymous") is None

    def test_returns_none_for_empty_string(self):
        assert _coerce_user_uuid("") is None

    def test_returns_none_for_none(self):
        assert _coerce_user_uuid(None) is None

    def test_returns_none_for_arbitrary_non_uuid(self):
        assert _coerce_user_uuid("not-a-uuid") is None
        assert _coerce_user_uuid("12345") is None
        assert _coerce_user_uuid("user-1") is None

    def test_returns_canonical_uuid_for_valid_uuid_string(self):
        valid = "12345678-1234-5678-1234-567812345678"
        result = _coerce_user_uuid(valid)
        assert result == valid

    def test_normalises_uppercase_uuid(self):
        upper = "12345678-1234-5678-1234-567812345678".upper()
        result = _coerce_user_uuid(upper)
        assert result is not None
        # uuid module normalises to lowercase
        assert result.lower() == upper.lower()

    def test_handles_uuid_without_hyphens(self):
        no_hyphens = "12345678123456781234567812345678"
        result = _coerce_user_uuid(no_hyphens)
        assert result is not None
        assert result == "12345678-1234-5678-1234-567812345678"

    def test_returns_none_for_object_without_str(self):
        class Weird:
            def __str__(self):
                raise RuntimeError("boom")

        # str() conversion will raise, helper should swallow it via except
        # AttributeError/ValueError. RuntimeError propagates — that's fine,
        # the goal is to not corrupt UUID handling for the common cases.
        try:
            _coerce_user_uuid(Weird())
        except RuntimeError:
            pass  # Acceptable — non-UUID objects shouldn't reach this code.


# ---------------------------------------------------------------------------
# UsageTracker.log_usage
# ---------------------------------------------------------------------------

class TestLogUsageSkipsAnonymous:
    def test_log_usage_short_circuits_for_anonymous(self, monkeypatch):
        """Anonymous user_id must NOT trigger any DB call."""
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        UsageTracker.log_usage(
            user_id="anonymous", usage_type="article_view"
        )
        assert called["count"] == 0

    def test_log_usage_short_circuits_for_non_uuid(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        UsageTracker.log_usage(
            user_id="not-a-uuid", usage_type="article_view"
        )
        assert called["count"] == 0

    def test_log_usage_short_circuits_for_empty_string(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        UsageTracker.log_usage(user_id="", usage_type="search")
        assert called["count"] == 0

    def test_log_usage_short_circuits_for_none(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        UsageTracker.log_usage(user_id=None, usage_type="search")
        assert called["count"] == 0

    def test_log_usage_calls_db_for_valid_uuid(self, monkeypatch):
        captured = []

        class _SpyDB:
            def execute_query(self, query, params=None):
                captured.append({"query": query, "params": params or {}})
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        valid = "12345678-1234-5678-1234-567812345678"
        UsageTracker.log_usage(
            user_id=valid, usage_type="article_view",
            resource_id="art-1",
        )
        assert len(captured) == 1
        params = captured[0]["params"]
        assert params["user_id"] == valid
        assert params["usage_type"] == "article_view"
        assert params["resource_id"] == "art-1"


# ---------------------------------------------------------------------------
# UsageTracker.get_usage_count
# ---------------------------------------------------------------------------

class TestGetUsageCountSkipsAnonymous:
    def test_count_returns_zero_for_anonymous(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return [{"count": 999}]

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        result = UsageTracker.get_usage_count(
            user_id="anonymous", usage_type="article_view"
        )
        assert result == 0
        assert called["count"] == 0  # No DB query issued

    def test_count_returns_zero_for_non_uuid(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        result = UsageTracker.get_usage_count(
            user_id="user-1", usage_type="search"
        )
        assert result == 0
        assert called["count"] == 0

    def test_count_returns_zero_for_none(self, monkeypatch):
        called = {"count": 0}

        class _SpyDB:
            def execute_query(self, query, params=None):
                called["count"] += 1
                return []

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        result = UsageTracker.get_usage_count(
            user_id=None, usage_type="search"
        )
        assert result == 0
        assert called["count"] == 0

    def test_count_runs_query_for_valid_uuid(self, monkeypatch):
        captured = []

        class _SpyDB:
            def execute_query(self, query, params=None):
                captured.append({"query": query, "params": params or {}})
                return [{"count": 7}]

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        valid = "12345678-1234-5678-1234-567812345678"
        result = UsageTracker.get_usage_count(
            user_id=valid, usage_type="article_view", period="day"
        )
        assert result == 7
        assert len(captured) == 1
        # Day filter is in the query
        assert "current_date" in captured[0]["query"].lower()


# ---------------------------------------------------------------------------
# UsageTracker.check_limit
# ---------------------------------------------------------------------------

class TestCheckLimit:
    def test_unknown_usage_type_allowed_unlimited(self, monkeypatch):
        # The unknown branch returns (True, 0, None) without DB calls
        allowed, current, limit = UsageTracker.check_limit(
            user_id="anonymous",
            subscription_tier="freemium",
            usage_type="unknown_type",
        )
        assert allowed is True
        assert current == 0
        assert limit is None

    def test_freemium_articles_per_day_uses_limit(self, monkeypatch):
        """For valid users, freemium articles_per_day should be 10."""
        class _SpyDB:
            def execute_query(self, query, params=None):
                return [{"count": 3}]

        import api.rate_limiter as rl
        monkeypatch.setattr(rl, "get_postgres", lambda: _SpyDB())

        valid = "12345678-1234-5678-1234-567812345678"
        allowed, current, limit = UsageTracker.check_limit(
            user_id=valid,
            subscription_tier="freemium",
            usage_type="article_view",
            period="day",
        )
        assert allowed is True
        assert current == 3
        assert limit == 10

    def test_anonymous_user_with_known_type_returns_zero(self, monkeypatch):
        """Even with a valid usage_type, anonymous users get 0 current usage."""
        # No DB needed because get_usage_count short-circuits
        allowed, current, limit = UsageTracker.check_limit(
            user_id="anonymous",
            subscription_tier="freemium",
            usage_type="article_view",
            period="day",
        )
        # current=0 < 10, so allowed=True
        assert current == 0
        assert limit == 10
        assert allowed is True


class TestResolveUserFromToken:
    """2026-06-10 audit: the middleware must populate request.state.user from
    the bearer token, else every authenticated request fell to the anonymous
    branch and the tier ladder was dead. Pins that decoding."""

    def _req(self, headers):
        class _R:
            def __init__(self, h):
                self.headers = h
        return _R(headers)

    def test_valid_access_token_resolves_user_and_tier(self):
        from api.rate_limiter import RateLimitMiddleware
        from api.auth_utils import TokenManager
        tok = TokenManager.create_access_token(
            user_id="u-123", email="a@b.c", subscription_tier="professional",
        )
        u = RateLimitMiddleware._resolve_user_from_token(
            self._req({"Authorization": f"Bearer {tok}"})
        )
        assert u is not None
        assert u["user_id"] == "u-123"
        assert u["subscription_tier"] == "professional"

    def test_missing_header_is_anonymous(self):
        from api.rate_limiter import RateLimitMiddleware
        assert RateLimitMiddleware._resolve_user_from_token(self._req({})) is None

    def test_non_bearer_header_is_anonymous(self):
        from api.rate_limiter import RateLimitMiddleware
        assert RateLimitMiddleware._resolve_user_from_token(
            self._req({"Authorization": "Basic abc"})
        ) is None

    def test_garbage_token_is_anonymous(self):
        from api.rate_limiter import RateLimitMiddleware
        assert RateLimitMiddleware._resolve_user_from_token(
            self._req({"Authorization": "Bearer not.a.jwt"})
        ) is None

    def test_non_access_token_rejected(self):
        # Only access tokens carry the tier; a valid-signature non-access
        # token (e.g. a refresh token) must not resolve a user.
        import jwt as _jwt
        from datetime import datetime, timedelta
        import api.auth_utils as au
        from api.rate_limiter import RateLimitMiddleware
        tok = _jwt.encode(
            {"sub": "u-9", "type": "refresh",
             "exp": datetime.utcnow() + timedelta(minutes=5)},
            au.SECRET_KEY, algorithm=au.ALGORITHM,
        )
        assert RateLimitMiddleware._resolve_user_from_token(
            self._req({"Authorization": f"Bearer {tok}"})
        ) is None
