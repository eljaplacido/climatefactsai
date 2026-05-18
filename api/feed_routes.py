"""
Feed Preferences Routes

Manages user feed preferences for automatic content discovery.
Users can configure country subscriptions, keywords, and refresh frequency.
Tier-gated: country limits and update frequency depend on subscription.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import UsageTracker, TIER_LIMITS
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("feed-api")
router = APIRouter(prefix="/api/feed", tags=["Feed"])


class FeedPreferencesResponse(BaseModel):
    """User's feed preference configuration."""
    country_codes: List[str] = []
    update_frequency: str = "daily"
    keywords: List[str] = []
    last_updated_at: Optional[str] = None


class UpdateFeedPreferencesRequest(BaseModel):
    """Request to update feed preferences."""
    country_codes: List[str] = Field(
        ..., min_length=1, max_length=30,
        description="ISO 3166-1 alpha-2 country codes"
    )
    keywords: List[str] = Field(
        default_factory=list, max_length=10,
        description="Optional keywords to filter discovery"
    )


class FeedStatusItem(BaseModel):
    """Status of a single country feed."""
    country_code: str
    last_update: Optional[str] = None
    article_count: int = 0


class FeedRefreshResponse(BaseModel):
    """Response from manual feed refresh."""
    status: str
    countries_refreshed: List[str]
    message: str


@router.get("/preferences", response_model=FeedPreferencesResponse)
async def get_feed_preferences(
    current_user: Any = Depends(get_current_user),
):
    """Get the current user's feed preferences."""
    user_id = str(current_user.get("user_id"))
    db = get_postgres()

    rows = db.execute_query(
        """SELECT country_codes, update_frequency, keywords, last_updated_at
           FROM user_feed_preferences WHERE user_id = :uid""",
        {"uid": user_id},
    )

    if not rows:
        return FeedPreferencesResponse()

    row = rows[0]
    return FeedPreferencesResponse(
        country_codes=row.get("country_codes", []),
        update_frequency=row.get("update_frequency", "daily"),
        keywords=row.get("keywords", []),
        last_updated_at=str(row["last_updated_at"]) if row.get("last_updated_at") else None,
    )


@router.put("/preferences", response_model=FeedPreferencesResponse)
async def update_feed_preferences(
    request: UpdateFeedPreferencesRequest,
    current_user: Any = Depends(get_current_user),
):
    """
    Set preferred countries for feed updates.
    Country count is limited by subscription tier.
    """
    user_id = str(current_user.get("user_id"))
    tier = current_user.get("subscription_tier", "freemium")

    # Enforce country limit
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["freemium"])
    country_limit = limits.get("countries_limit")
    if country_limit is not None and len(request.country_codes) > country_limit:
        raise HTTPException(
            status_code=403,
            detail=f"Your tier allows up to {country_limit} countries. "
                   f"You requested {len(request.country_codes)}. Upgrade for more.",
        )

    # Normalize country codes
    codes = [c.upper().strip() for c in request.country_codes if c.strip()]
    keywords = [k.strip() for k in request.keywords if k.strip()][:10]

    # Determine allowed frequency based on tier
    frequency_map = {
        "freemium": "weekly",
        "standard": "daily",
        "basic": "daily",  # alias for standard
        "professional": "daily",
    }
    update_freq = frequency_map.get(tier, "daily")

    db = get_postgres()
    db.execute_update(
        """INSERT INTO user_feed_preferences (user_id, country_codes, update_frequency, keywords)
           VALUES (:uid, :codes, :freq, :kw)
           ON CONFLICT (user_id) DO UPDATE SET
             country_codes = EXCLUDED.country_codes,
             update_frequency = EXCLUDED.update_frequency,
             keywords = EXCLUDED.keywords,
             updated_at = NOW()""",
        {
            "uid": user_id,
            "codes": codes,
            "freq": update_freq,
            "kw": keywords,
        },
    )

    return FeedPreferencesResponse(
        country_codes=codes,
        update_frequency=update_freq,
        keywords=keywords,
    )


@router.post("/refresh", response_model=FeedRefreshResponse)
async def refresh_feed(
    current_user: Any = Depends(get_current_user),
):
    """
    Trigger an on-demand feed refresh. Counts toward discovery rate limit.
    """
    user_id = str(current_user.get("user_id"))
    tier = current_user.get("subscription_tier", "freemium")

    # Check discovery limit
    allowed, current, limit = UsageTracker.check_limit(
        user_id, tier, "discovery_query", "day"
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily discovery limit reached ({current}/{limit}). Try again tomorrow or upgrade.",
        )

    db = get_postgres()
    rows = db.execute_query(
        "SELECT country_codes FROM user_feed_preferences WHERE user_id = :uid",
        {"uid": user_id},
    )

    if not rows or not rows[0].get("country_codes"):
        raise HTTPException(
            status_code=400,
            detail="No feed preferences configured. Set your preferred countries first.",
        )

    countries = rows[0]["country_codes"]
    refreshed = []

    for cc in countries[:5]:  # Cap manual refresh to 5 countries
        try:
            from app.tasks.ingestion import discover_articles
            discover_articles.delay(country=cc.upper(), max_articles=3)
            refreshed.append(cc.upper())
        except Exception as e:
            logger.warning(f"Manual refresh dispatch failed for {cc}: {e}")

    # Also refresh user's custom registered sources
    try:
        user_sources = db.execute_query(
            """SELECT registration_id, source_url, source_name, country_code
               FROM user_source_registrations
               WHERE user_id = :uid AND is_active = true AND approved = true""",
            {"uid": user_id},
        )
        if user_sources:
            from app.domains.content.data_sources.rss_adapter import _parse_feed, dedup_against_existing
            from app.tasks.ingestion import _insert_discovered_articles
            for src in user_sources:
                try:
                    articles = _parse_feed(src["source_url"], max_items=5)
                    for a in articles:
                        a["source_name"] = src["source_name"]
                        a["country_code"] = src.get("country_code") or "XX"
                    new_articles = dedup_against_existing(articles, db)
                    if new_articles:
                        _insert_discovered_articles(db, new_articles, src.get("country_code") or "XX")
                    db.execute_query(
                        "UPDATE user_source_registrations SET last_fetched_at = NOW(), fetch_error = NULL WHERE registration_id = :rid",
                        {"rid": str(src["registration_id"])},
                    )
                except Exception as e:
                    logger.warning(f"User source refresh failed for {src['source_url']}: {e}")
                    db.execute_query(
                        "UPDATE user_source_registrations SET fetch_error = :err WHERE registration_id = :rid",
                        {"err": str(e)[:500], "rid": str(src["registration_id"])},
                    )
    except Exception as e:
        logger.warning(f"User sources refresh skipped: {e}")

    # Log usage
    UsageTracker.log_usage(
        user_id=user_id,
        usage_type="discovery_query",
        metadata={"countries": refreshed, "source": "manual_refresh"},
    )

    return FeedRefreshResponse(
        status="dispatched",
        countries_refreshed=refreshed,
        message=f"Refresh dispatched for {len(refreshed)} countries. Articles will appear within minutes.",
    )


@router.get("/status", response_model=List[FeedStatusItem])
async def get_feed_status(
    current_user: Any = Depends(get_current_user),
):
    """Get last update time and article count per configured country."""
    user_id = str(current_user.get("user_id"))
    db = get_postgres()

    # Get user's countries
    pref_rows = db.execute_query(
        "SELECT country_codes FROM user_feed_preferences WHERE user_id = :uid",
        {"uid": user_id},
    )
    if not pref_rows or not pref_rows[0].get("country_codes"):
        return []

    countries = pref_rows[0]["country_codes"]

    # Get stats per country
    result = []
    for cc in countries:
        stats_rows = db.execute_query(
            """SELECT
                 COUNT(*) as article_count,
                 MAX(created_at) as last_article_at
               FROM articles
               WHERE is_synthetic = FALSE
                 AND country_code = :cc""",
            {"cc": cc.upper()},
        )
        row = stats_rows[0] if stats_rows else {}
        result.append(FeedStatusItem(
            country_code=cc.upper(),
            last_update=str(row["last_article_at"]) if row.get("last_article_at") else None,
            article_count=row.get("article_count", 0),
        ))

    return result
