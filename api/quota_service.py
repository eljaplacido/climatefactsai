"""Quota service — Phase 1A (2026-05-23).

Implements the user's 2026-05-23 freemium decision: 3 saved articles /
3 saved searches / 2 deep research / 1 URL analysis per Free (registered)
user per month, with progressive ladders into Basic / Professional /
Enterprise.

Sits ALONGSIDE the legacy `rate_limiter.UsageTracker`, not on top of it:
the legacy module gates per-day reads (articles_per_day, searches_per_day);
this service gates the four monetisable surfaces with their own quota
semantics (lifetime vs monthly).

The frontend reads `GET /api/quota` to render inline remaining counters
on every gated CTA; on over-limit, the gated endpoints return 429 with a
structured envelope so the client can show the upgrade modal with the
exact quota key and reset time.

See [[freemium_quota_decision_2026_05_23]] in memory for the ladder.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from shared.database import get_postgres
from shared.logger import setup_logging


logger = setup_logging("quota_service")


# =============================================================================
# Tier ladder — the durable source of truth for the 3/3/2 decision
# =============================================================================
# -1 means unlimited. Keys are quota slugs; the same slug appears on the
# frontend types and tests. Adding a new gated surface = add a key here
# AND in the LIFETIME_KEYS / MONTHLY_KEYS sets below AND in QUOTA_LABELS.
# Never silently extend the dict — every key must have an explicit count.

FREEMIUM_FREE_TIER_LIMITS: dict[str, int] = {
    "saved_articles": 3,    # lifetime cap
    "saved_searches": 3,    # lifetime cap
    "deep_research": 3,     # per calendar month (raised 2->3, 2026-05-31 owner decision)
    "url_analysis": 1,      # per calendar month
    "compare": 1,           # per calendar month
}

QUOTA_LIMITS_BY_TIER: dict[str, dict[str, int]] = {
    # Anonymous traffic — handled separately by the IP-based rate limiter;
    # the structured 0/0/0/0 here means "must sign in to use these".
    "anonymous": {
        "saved_articles": 0,
        "saved_searches": 0,
        "deep_research": 0,
        "url_analysis": 0,
        "compare": 0,
    },
    # Free (registered) — 3/3/2 per the 2026-05-23 decision.
    "freemium": FREEMIUM_FREE_TIER_LIMITS,
    "free": FREEMIUM_FREE_TIER_LIMITS,  # alias used by some legacy auth code
    "basic": {
        "saved_articles": 50,
        "saved_searches": 25,
        "deep_research": 15,
        "url_analysis": 5,
        "compare": 10,
    },
    "standard": {  # legacy alias for basic
        "saved_articles": 50,
        "saved_searches": 25,
        "deep_research": 15,
        "url_analysis": 5,
        "compare": 10,
    },
    "professional": {
        "saved_articles": -1,
        "saved_searches": -1,
        "deep_research": 100,
        "url_analysis": 30,
        "compare": 50,
    },
    "enterprise": {
        "saved_articles": -1,
        "saved_searches": -1,
        "deep_research": -1,
        "url_analysis": -1,
        "compare": -1,
    },
}

# Quotas measured as a lifetime cap on the underlying table size
# (delete a row → count drops → quota frees up).
LIFETIME_KEYS = frozenset({"saved_articles", "saved_searches"})

# Quotas measured per calendar month (counter resets at start of next month).
MONTHLY_KEYS = frozenset({"deep_research", "url_analysis", "compare"})

# Human-readable labels for client error messages and inline UI.
QUOTA_LABELS: dict[str, str] = {
    "saved_articles": "saved articles",
    "saved_searches": "saved searches",
    "deep_research": "deep research queries",
    "url_analysis": "URL analyses",
    "compare": "topic comparisons",
}

UPGRADE_URL = "/dashboard/subscription"


@dataclass
class QuotaCheck:
    """Result of a quota check — what the frontend renders inline."""
    quota_key: str
    allowed: bool
    used: int
    limit: int            # -1 = unlimited
    period: str           # "lifetime" or "monthly"
    reset_at: Optional[datetime]  # None for lifetime quotas
    upgrade_url: str
    tier: str
    label: str

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.reset_at is not None:
            d["reset_at"] = self.reset_at.isoformat()
        return d


def _month_start_utc() -> datetime:
    """First moment of the current UTC calendar month."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month_start_utc() -> datetime:
    """First moment of next UTC calendar month — when monthly quotas reset."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _normalize_tier(tier: Optional[str]) -> str:
    """Coerce arbitrary tier strings to one of the ladder keys.

    Unknown tiers fall through to 'anonymous' (the safest default) rather
    than 'freemium' — preventing accidental privilege grants from malformed
    JWT claims.
    """
    if not tier:
        return "anonymous"
    t = tier.lower().strip()
    if t in QUOTA_LIMITS_BY_TIER:
        return t
    return "anonymous"


class QuotaService:
    """Single entry point for all freemium quota checks."""

    @staticmethod
    def _count_used(user_id: Optional[str], quota_key: str) -> int:
        """Count current usage against the right underlying table.

        Returns 0 for anonymous users — they have limit=0 anyway, so the
        allowed=False decision happens on the limit side, not the count side.
        """
        if not user_id:
            return 0
        db = get_postgres()

        try:
            if quota_key == "saved_articles":
                rows = db.execute_query(
                    "SELECT COUNT(*) AS n FROM user_bookmarks WHERE user_id = :uid",
                    {"uid": user_id},
                )
                return int(rows[0]["n"]) if rows else 0
            if quota_key == "saved_searches":
                rows = db.execute_query(
                    "SELECT COUNT(*) AS n FROM user_saved_queries WHERE user_id = :uid",
                    {"uid": user_id},
                )
                return int(rows[0]["n"]) if rows else 0
            if quota_key == "url_analysis":
                rows = db.execute_query(
                    """
                    SELECT COUNT(*) AS n
                    FROM url_analyses
                    WHERE user_id = :uid
                      AND created_at >= DATE_TRUNC('month', NOW())
                    """,
                    {"uid": user_id},
                )
                return int(rows[0]["n"]) if rows else 0
            if quota_key in ("deep_research", "compare"):
                rows = db.execute_query(
                    """
                    SELECT COUNT(*) AS n
                    FROM user_usage
                    WHERE user_id = :uid
                      AND usage_type = :ut
                      AND created_at >= DATE_TRUNC('month', NOW())
                    """,
                    {"uid": user_id, "ut": quota_key},
                )
                return int(rows[0]["n"]) if rows else 0
        except Exception as exc:
            logger.warning(
                f"Quota count query failed for {quota_key}; defaulting to 0. "
                f"Either schema drift or table missing. detail={exc!r}"
            )
            return 0

        # Unknown quota key — fail open (return 0) but log loudly.
        logger.warning(f"Unknown quota_key requested: {quota_key!r}")
        return 0

    @classmethod
    def check(
        cls,
        user_id: Optional[str],
        tier: Optional[str],
        quota_key: str,
    ) -> QuotaCheck:
        """Read-only quota check. Does NOT increment usage.

        Returns a QuotaCheck describing where the user stands on this quota.
        Used by: `GET /api/quota` (display), every gated endpoint as the
        first step before doing the work, and the upgrade-modal copy.
        """
        normalized_tier = _normalize_tier(tier)
        tier_limits = QUOTA_LIMITS_BY_TIER[normalized_tier]
        limit = tier_limits.get(quota_key, 0)

        period = "lifetime" if quota_key in LIFETIME_KEYS else "monthly"
        reset_at = None if period == "lifetime" else _next_month_start_utc()

        used = cls._count_used(user_id, quota_key)
        allowed = (limit == -1) or (used < limit)

        return QuotaCheck(
            quota_key=quota_key,
            allowed=allowed,
            used=used,
            limit=limit,
            period=period,
            reset_at=reset_at,
            upgrade_url=UPGRADE_URL,
            tier=normalized_tier,
            label=QUOTA_LABELS.get(quota_key, quota_key),
        )

    @classmethod
    def check_and_raise(
        cls,
        user_id: Optional[str],
        tier: Optional[str],
        quota_key: str,
    ) -> QuotaCheck:
        """Same as check() but raises HTTP 429 when over limit.

        FastAPI handlers call this BEFORE doing the work. The 429 body is
        structured so the frontend can render the upgrade modal:

        {
          "error": "quota_exceeded",
          "quota": { ...QuotaCheck.to_dict()... },
          "message": "You've used 3 of 3 saved articles..."
        }
        """
        result = cls.check(user_id, tier, quota_key)
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "quota": result.to_dict(),
                    "message": (
                        f"You've used {result.used} of {result.limit} "
                        f"{result.label} on the {result.tier} tier "
                        f"({result.period}). Upgrade for higher limits."
                    ),
                },
            )
        return result

    @classmethod
    def consume(
        cls,
        user_id: Optional[str],
        quota_key: str,
        resource_id: Optional[str] = None,
        resource_url: Optional[str] = None,
    ) -> None:
        """Record a quota-consumption event.

        Lifetime quotas (saved_articles, saved_searches) don't need this —
        their count comes from the underlying table that already records
        the create. Monthly quotas (deep_research, url_analysis, compare)
        DO need it — for url_analysis the row in `url_analyses` itself is
        the record, but for deep_research and compare we log to user_usage
        so the count query at month-start can find them.
        """
        if not user_id:
            return  # anonymous events skip consumption (already blocked above)
        if quota_key in LIFETIME_KEYS:
            return  # source-of-truth table already records this
        if quota_key == "url_analysis":
            return  # url_analyses row insert IS the record

        # Defer to the legacy UsageTracker so we don't fork persistence
        # logic. The user_usage table is already the right shape.
        try:
            from api.rate_limiter import UsageTracker
            UsageTracker.log_usage(
                user_id=user_id,
                usage_type=quota_key,
                resource_id=resource_id,
                resource_url=resource_url,
            )
        except Exception as exc:
            # Logging is best-effort: never fail a user request because
            # quota tracking failed. We err on the side of letting them
            # have a free run rather than 500-erroring on bookkeeping.
            logger.warning(
                f"quota consume() failed for {quota_key} user={user_id}: {exc}"
            )

    @classmethod
    def summary(cls, user_id: Optional[str], tier: Optional[str]) -> list[dict]:
        """Return the full quota dashboard for a user — every key, every
        used/limit. Powers GET /api/quota."""
        keys = list(FREEMIUM_FREE_TIER_LIMITS.keys())
        return [cls.check(user_id, tier, k).to_dict() for k in keys]


__all__ = [
    "QuotaService",
    "QuotaCheck",
    "QUOTA_LIMITS_BY_TIER",
    "QUOTA_LABELS",
    "LIFETIME_KEYS",
    "MONTHLY_KEYS",
    "FREEMIUM_FREE_TIER_LIMITS",
    "UPGRADE_URL",
]
