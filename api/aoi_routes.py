"""AOI alert subscription routes — Phase 3 (2026-05-23).

REST surface for the MH5 (Area of Interest) alerts feature.

  POST   /api/aoi-subscriptions             — create a new alert
  GET    /api/aoi-subscriptions             — list the current user's alerts
  DELETE /api/aoi-subscriptions/{id}        — soft-delete (set active=FALSE)

All endpoints require authentication. The POST endpoint enforces the
Basic+ tier gate via the AOIService — the 429 envelope follows the same
shape as the freemium quota gate so the frontend's UpgradeModal can
render either without translation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.aoi_service import AOIService, AOI_TIER_LIMITS
from api.auth_routes import get_current_user
from shared.logger import setup_logging


logger = setup_logging("aoi_routes")

router = APIRouter(prefix="/api/aoi-subscriptions", tags=["AOI Alerts"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateAOISubscriptionRequest(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=2)
    variable: str = Field(..., min_length=1, max_length=64)
    comparison: str = Field(..., description="One of: gt, gte, lt, lte, eq")
    threshold: float
    label: Optional[str] = Field(None, max_length=200)
    delivery_channel: str = Field("email", description="email | push | slack")
    delivery_target: Optional[str] = None


class AOISubscriptionResponse(BaseModel):
    subscription_id: str
    user_id: str
    country_code: str
    variable: str
    comparison: str
    threshold: float
    delivery_channel: str
    delivery_target: Optional[str]
    active: bool
    last_fired_at: Optional[str]
    last_observed_value: Optional[float]
    fire_count: int
    label: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=AOISubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_aoi_subscription(
    request: CreateAOISubscriptionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new AOI alert subscription.

    Tier-gated: only Basic+ users can create (freemium = 0). On over-limit,
    returns HTTP 429 with structured envelope matching the freemium-quota
    shape so the frontend UpgradeModal renders identically.
    """
    user_id = str(current_user["user_id"])
    tier = str(current_user.get("subscription_tier", "freemium"))

    subscription = AOIService.create(
        user_id=user_id,
        tier=tier,
        country_code=request.country_code,
        variable=request.variable,
        comparison=request.comparison,
        threshold=request.threshold,
        label=request.label,
        delivery_channel=request.delivery_channel,
        delivery_target=request.delivery_target,
    )
    return AOISubscriptionResponse(**subscription.to_dict())


@router.get("", response_model=list[AOISubscriptionResponse])
async def list_aoi_subscriptions(
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """List the current user's AOI subscriptions.

    By default returns only active subscriptions; set `include_inactive=true`
    to see soft-deleted ones too (e.g. for the dashboard's "show history").
    """
    user_id = str(current_user["user_id"])
    rows = AOIService.list_for_user(user_id, include_inactive=include_inactive)
    # Coerce datetime fields to ISO strings for JSON
    out = []
    for r in rows:
        for k in ("last_fired_at", "created_at", "updated_at"):
            v = r.get(k)
            if v is not None and hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        out.append(AOISubscriptionResponse(**r))
    return out


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_aoi_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete an AOI subscription (set active=FALSE).

    Returns 404 if the subscription doesn't exist or doesn't belong to
    the requesting user. We DON'T differentiate "not found" from "not yours"
    to avoid leaking subscription IDs of other users.
    """
    user_id = str(current_user["user_id"])
    ok = AOIService.deactivate(user_id, subscription_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    # 204 — no body


@router.get("/tier-info")
async def get_tier_info(current_user: dict = Depends(get_current_user)):
    """Return the user's AOI tier limit + current usage. Powers the
    subscribe-modal CTA copy ('5 used / 5 — upgrade to Pro for 50')."""
    user_id = str(current_user["user_id"])
    tier = str(current_user.get("subscription_tier", "freemium"))
    allowed, used, limit = AOIService.can_create(user_id, tier)
    normalized_tier = AOIService._normalize_tier(tier)
    return {
        "tier": normalized_tier,
        "limit": limit,  # -1 = unlimited
        "used": used,
        "allowed": allowed,
        "upgrade_url": "/dashboard/subscription",
        "all_tier_limits": AOI_TIER_LIMITS,
    }
