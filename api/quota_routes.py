"""Quota dashboard endpoint — Phase 1A (2026-05-23).

Single endpoint: GET /api/quota returns the user's standing across all
freemium quota keys. Frontend reads this on mount to render inline
"X/Y remaining" labels on every gated CTA.

Anonymous users get an envelope showing 0/0 across the board — that's
the cue for the UI to render "Sign in to save articles" etc. rather than
"upgrade to Basic".
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from api.auth_routes import get_optional_user
from api.quota_service import (
    QuotaService,
    QUOTA_LIMITS_BY_TIER,
    FREEMIUM_FREE_TIER_LIMITS,
)


router = APIRouter(prefix="/api/quota", tags=["Quota"])


@router.get("")
async def get_quota_summary(
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Return the user's quota standing across every key.

    Response shape:
    {
      "tier": "freemium" | "basic" | "professional" | "enterprise" | "anonymous",
      "quotas": [
        {
          "quota_key": "saved_articles",
          "allowed": true,
          "used": 2,
          "limit": 3,
          "period": "lifetime",
          "reset_at": null,
          "upgrade_url": "/dashboard/subscription",
          "tier": "freemium",
          "label": "saved articles"
        },
        ...
      ]
    }
    """
    if current_user and isinstance(current_user, dict):
        user_id = str(current_user.get("user_id") or "")
        tier = str(current_user.get("subscription_tier") or "freemium")
    else:
        user_id = None
        tier = "anonymous"

    return {
        "tier": tier,
        "quotas": QuotaService.summary(user_id, tier),
    }


@router.get("/{quota_key}")
async def get_single_quota(
    quota_key: str,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Single-quota lookup — useful when a CTA only cares about one key.

    Returns 404 if the quota key is not recognised.
    """
    from fastapi import HTTPException, status

    if quota_key not in FREEMIUM_FREE_TIER_LIMITS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown quota key: {quota_key!r}",
        )

    if current_user and isinstance(current_user, dict):
        user_id = str(current_user.get("user_id") or "")
        tier = str(current_user.get("subscription_tier") or "freemium")
    else:
        user_id = None
        tier = "anonymous"

    return QuotaService.check(user_id, tier, quota_key).to_dict()
