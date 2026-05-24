"""AOI (Area of Interest) alert service — Phase 3 (2026-05-23).

Implements MH5 from the competitive UX audit (Global Forest Watch
pattern). Authenticated users on Basic+ tier can subscribe to threshold
alerts for any (country, climate variable, comparison, value) combination.
Hourly Celery beat pulls indicator values and dispatches an email when a
threshold is crossed.

Tier gating:
  - freemium / anonymous: 0 subscriptions
  - basic: 5 active
  - professional: 50 active
  - enterprise: unlimited

The threshold-check semantics are pure (no DB / network), so they're
exhaustively unit-testable. The Celery integration is a thin wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status

from shared.database import get_postgres
from shared.logger import setup_logging


logger = setup_logging("aoi_service")


# ---------------------------------------------------------------------------
# Tier gating — separate from the freemium quota service because AOI is a
# Basic+ paid feature, not a free-tier limit.
# ---------------------------------------------------------------------------

AOI_TIER_LIMITS: dict[str, int] = {
    "anonymous": 0,
    "freemium": 0,
    "free": 0,
    "basic": 5,
    "standard": 5,  # legacy alias
    "professional": 50,
    "enterprise": -1,  # unlimited
}


# ---------------------------------------------------------------------------
# Threshold-check primitive — pure, no I/O, exhaustively testable
# ---------------------------------------------------------------------------

VALID_COMPARISONS = frozenset({"gt", "gte", "lt", "lte", "eq"})


def check_threshold_crossed(
    observed: Optional[float],
    comparison: str,
    threshold: float,
    last_observed: Optional[float] = None,
) -> bool:
    """Decide whether an alert should fire.

    Returns True iff:
      1. `observed` satisfies the (comparison, threshold) rule, AND
      2. `last_observed` did NOT satisfy it (i.e. this is a crossing,
         not a steady-state hit — without this debounce we'd email
         every poll for as long as the threshold stays exceeded).

    When `last_observed` is None (no prior observation), any rule
    satisfaction fires once.

    Returns False when:
      - `observed` is None (missing data — never alert on absence;
        that's a different kind of signal)
      - comparison is unknown (defensive — never alert on garbage)
      - the rule is satisfied AND was already satisfied last time
        (debounce: same crossing already alerted)
    """
    if observed is None:
        return False
    if comparison not in VALID_COMPARISONS:
        return False

    def _rule(value: float) -> bool:
        if comparison == "gt":
            return value > threshold
        if comparison == "gte":
            return value >= threshold
        if comparison == "lt":
            return value < threshold
        if comparison == "lte":
            return value <= threshold
        if comparison == "eq":
            return value == threshold
        return False

    if not _rule(observed):
        return False

    # Debounce: only fire if last observation did NOT satisfy the rule.
    if last_observed is not None and _rule(last_observed):
        return False

    return True


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AOISubscription:
    subscription_id: str
    user_id: str
    country_code: str
    variable: str
    comparison: str
    threshold: float
    delivery_channel: str = "email"
    delivery_target: Optional[str] = None
    active: bool = True
    last_fired_at: Optional[datetime] = None
    last_observed_value: Optional[float] = None
    fire_count: int = 0
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "country_code": self.country_code,
            "variable": self.variable,
            "comparison": self.comparison,
            "threshold": self.threshold,
            "delivery_channel": self.delivery_channel,
            "delivery_target": self.delivery_target,
            "active": self.active,
            "last_fired_at": self.last_fired_at.isoformat() if self.last_fired_at else None,
            "last_observed_value": self.last_observed_value,
            "fire_count": self.fire_count,
            "label": self.label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AOIService:
    """CRUD + tier gating + crossing-detection orchestration for AOI alerts."""

    @staticmethod
    def _normalize_tier(tier: Optional[str]) -> str:
        if not tier:
            return "anonymous"
        t = tier.lower().strip()
        return t if t in AOI_TIER_LIMITS else "anonymous"

    @classmethod
    def tier_limit(cls, tier: Optional[str]) -> int:
        return AOI_TIER_LIMITS[cls._normalize_tier(tier)]

    @classmethod
    def count_active(cls, user_id: str) -> int:
        """Count the user's active subscriptions."""
        db = get_postgres()
        try:
            rows = db.execute_query(
                """
                SELECT COUNT(*) AS n
                FROM aoi_subscriptions
                WHERE user_id = :uid AND active = TRUE
                """,
                {"uid": user_id},
            )
            return int(rows[0]["n"]) if rows else 0
        except Exception as exc:
            logger.warning(
                "AOI active-count query failed; defaulting to 0",
                user_id=user_id,
                error=str(exc),
            )
            return 0

    @classmethod
    def can_create(cls, user_id: str, tier: Optional[str]) -> tuple[bool, int, int]:
        """Return (allowed, current_count, tier_limit). -1 limit means unlimited."""
        limit = cls.tier_limit(tier)
        if limit == 0:
            return False, 0, 0
        used = cls.count_active(user_id)
        if limit == -1:
            return True, used, -1
        return used < limit, used, limit

    @classmethod
    def create(
        cls,
        user_id: str,
        tier: str,
        country_code: str,
        variable: str,
        comparison: str,
        threshold: float,
        *,
        label: Optional[str] = None,
        delivery_channel: str = "email",
        delivery_target: Optional[str] = None,
    ) -> AOISubscription:
        """Create a new subscription. Raises HTTPException on tier limit / validation failure."""
        # Validation
        if comparison not in VALID_COMPARISONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid comparison: {comparison!r}. Must be one of {sorted(VALID_COMPARISONS)}.",
            )
        if not country_code or len(country_code) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="country_code must be a 2-character ISO code.",
            )
        if not variable or not variable.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="variable is required.",
            )
        if delivery_channel not in ("email", "push", "slack"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid delivery_channel: {delivery_channel!r}.",
            )

        # Tier gate
        allowed, used, limit = cls.can_create(user_id, tier)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "aoi_tier_limit",
                    "tier": cls._normalize_tier(tier),
                    "used": used,
                    "limit": limit,
                    "upgrade_url": "/dashboard/subscription",
                    "message": (
                        f"AOI alerts require Basic+ tier (currently {cls._normalize_tier(tier)})."
                        if limit == 0
                        else f"You've used {used} of {limit} AOI subscriptions on the {cls._normalize_tier(tier)} tier. Upgrade for more."
                    ),
                },
            )

        # Insert
        db = get_postgres()
        subscription_id = str(uuid4())
        try:
            db.execute_update(
                """
                INSERT INTO aoi_subscriptions
                    (subscription_id, user_id, country_code, variable, comparison,
                     threshold, delivery_channel, delivery_target, label, active)
                VALUES
                    (:sid, :uid, :cc, :var, :cmp, :thr, :chan, :target, :label, TRUE)
                """,
                {
                    "sid": subscription_id,
                    "uid": user_id,
                    "cc": country_code.upper(),
                    "var": variable.strip(),
                    "cmp": comparison,
                    "thr": float(threshold),
                    "chan": delivery_channel,
                    "target": delivery_target,
                    "label": label,
                },
            )
        except Exception as exc:
            logger.error(f"AOI subscription insert failed: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create AOI subscription",
            )

        return AOISubscription(
            subscription_id=subscription_id,
            user_id=user_id,
            country_code=country_code.upper(),
            variable=variable.strip(),
            comparison=comparison,
            threshold=float(threshold),
            delivery_channel=delivery_channel,
            delivery_target=delivery_target,
            label=label,
            active=True,
            created_at=datetime.now(timezone.utc),
        )

    @classmethod
    def list_for_user(cls, user_id: str, *, include_inactive: bool = False) -> list[dict]:
        """Return the user's subscriptions as dicts (for JSON responses)."""
        db = get_postgres()
        where_clause = "WHERE user_id = :uid" + ("" if include_inactive else " AND active = TRUE")
        try:
            rows = db.execute_query(
                f"""
                SELECT subscription_id, user_id, country_code, variable, comparison,
                       threshold, delivery_channel, delivery_target, active,
                       last_fired_at, last_observed_value, fire_count, label,
                       created_at, updated_at
                FROM aoi_subscriptions
                {where_clause}
                ORDER BY created_at DESC
                """,
                {"uid": user_id},
            )
            return [dict(r) for r in (rows or [])]
        except Exception as exc:
            logger.warning(f"AOI list_for_user failed: {exc}")
            return []

    @classmethod
    def deactivate(cls, user_id: str, subscription_id: str) -> bool:
        """Soft-delete: set active=FALSE. Returns True if a row was updated."""
        db = get_postgres()
        try:
            result = db.execute_update(
                """
                UPDATE aoi_subscriptions
                SET active = FALSE, updated_at = NOW()
                WHERE subscription_id = :sid AND user_id = :uid AND active = TRUE
                """,
                {"sid": subscription_id, "uid": user_id},
            )
            return bool(result)
        except Exception as exc:
            logger.warning(f"AOI deactivate failed: {exc}")
            return False
