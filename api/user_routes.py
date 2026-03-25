"""
User Dashboard Routes - Preferences, Usage Stats, and Notifications

Provides user-specific functionality for managing profile and viewing usage.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import json

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("user-api")
router = APIRouter(prefix="/api/user", tags=["User Dashboard"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UserPreferences(BaseModel):
    """User preferences and settings"""
    preferred_countries: List[str] = Field(default=[], description="Preferred countries")
    notification_topics: List[str] = Field(default=[], description="Topics of interest")
    email_notifications: bool = Field(default=True, description="Receive email notifications")
    daily_digest: bool = Field(default=False, description="Daily digest emails")
    language_code: str = Field(default="en", description="Preferred language")
    theme: str = Field(default="light", description="UI theme preference")


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences"""
    preferred_countries: Optional[List[str]] = None
    notification_topics: Optional[List[str]] = None
    email_notifications: Optional[bool] = None
    daily_digest: Optional[bool] = None
    language_code: Optional[str] = None
    theme: Optional[str] = None


class UsageStats(BaseModel):
    """User usage statistics"""
    tier: str
    period: str  # daily, monthly, yearly
    articles_viewed: int
    articles_limit: int
    searches_performed: int
    searches_limit: int
    url_analyses: int
    url_analyses_limit: int
    api_calls: int
    api_calls_limit: int
    last_activity: Optional[datetime] = None


class Notification(BaseModel):
    """User notification"""
    id: str
    type: str  # info, warning, success, error
    title: str
    message: str
    link: Optional[str] = None
    read: bool = False
    created_at: datetime


class ActivityLog(BaseModel):
    """User activity log entry"""
    id: str
    usage_type: str
    metadata: Dict[str, Any] = {}
    created_at: datetime


# =============================================================================
# USER PREFERENCES
# =============================================================================

@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's preferences and settings.
    """
    db = get_postgres()

    rows = db.execute_query(
        """
        SELECT preferred_countries, notification_topics, email_notifications,
               daily_digest, theme, language_code
        FROM user_preferences
        WHERE user_id = :user_id
        """,
        {"user_id": current_user["user_id"]}
    )

    if not rows:
        return UserPreferences()

    row = rows[0]
    return UserPreferences(
        preferred_countries=row.get("preferred_countries") or [],
        notification_topics=row.get("notification_topics") or [],
        email_notifications=row.get("email_notifications", True),
        daily_digest=row.get("daily_digest", False),
        language_code=row.get("language_code") or "en",
        theme=row.get("theme") or "light",
    )


@router.put("/preferences", response_model=UserPreferences)
async def update_user_preferences(
    request: UpdatePreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user preferences.

    Only provided fields will be updated. Others remain unchanged.
    """
    db = get_postgres()

    # Check if preferences exist
    rows = db.execute_query(
        "SELECT preference_id FROM user_preferences WHERE user_id = :user_id",
        {"user_id": current_user["user_id"]}
    )

    try:
        update_data = request.dict(exclude_unset=True)

        if rows:
            # Build dynamic UPDATE
            set_clauses = []
            params = {"user_id": current_user["user_id"]}
            for key, value in update_data.items():
                set_clauses.append(f"{key} = :{key}")
                params[key] = value

            if set_clauses:
                query = f"UPDATE user_preferences SET {', '.join(set_clauses)} WHERE user_id = :user_id"
                db.execute_update(query, params)
        else:
            # Insert new
            cols = ["user_id"]
            vals = [":user_id"]
            params = {"user_id": current_user["user_id"]}
            for key, value in update_data.items():
                cols.append(key)
                vals.append(f":{key}")
                params[key] = value

            query = f"INSERT INTO user_preferences ({', '.join(cols)}) VALUES ({', '.join(vals)})"
            db.execute_update(query, params)

        logger.info(f"Preferences updated for user {current_user['user_id']}")

        # Return updated preferences
        return await get_user_preferences(current_user=current_user)

    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


# =============================================================================
# USAGE STATISTICS
# =============================================================================

@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    period: str = Query("monthly", description="Stats period (daily, monthly, yearly)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's usage statistics.
    """
    db = get_postgres()

    # Define tier limits
    tier_limits = {
        "freemium": {
            "articles_daily": 5,
            "searches_daily": 10,
            "url_analyses_monthly": 0,
            "api_calls_daily": 0
        },
        "basic": {
            "articles_daily": 50,
            "searches_daily": 50,
            "url_analyses_monthly": 5,
            "api_calls_daily": 0
        },
        "professional": {
            "articles_daily": -1,
            "searches_daily": -1,
            "url_analyses_monthly": 20,
            "api_calls_daily": 1000
        },
        "enterprise": {
            "articles_daily": -1,
            "searches_daily": -1,
            "url_analyses_monthly": -1,
            "api_calls_daily": -1
        }
    }

    limits = tier_limits.get(current_user.get("subscription_tier", "freemium"), tier_limits["freemium"])

    # Calculate time window
    if period == "daily":
        time_window = datetime.utcnow() - timedelta(days=1)
    elif period == "yearly":
        time_window = datetime.utcnow() - timedelta(days=365)
    else:
        time_window = datetime.utcnow() - timedelta(days=30)

    # Get usage counts
    rows = db.execute_query(
        """
        SELECT
            SUM(CASE WHEN usage_type = 'article_view' THEN 1 ELSE 0 END) as articles_viewed,
            SUM(CASE WHEN usage_type = 'search' THEN 1 ELSE 0 END) as searches_performed,
            SUM(CASE WHEN usage_type = 'url_analysis' THEN 1 ELSE 0 END) as url_analyses,
            SUM(CASE WHEN usage_type = 'api_call' THEN 1 ELSE 0 END) as api_calls,
            MAX(created_at) as last_activity
        FROM user_usage
        WHERE user_id = :user_id AND created_at >= :time_window
        """,
        {"user_id": current_user["user_id"], "time_window": time_window}
    )

    usage = rows[0] if rows else {}

    return UsageStats(
        tier=current_user.get("subscription_tier", "freemium"),
        period=period,
        articles_viewed=usage.get("articles_viewed") or 0,
        articles_limit=limits["articles_daily"],
        searches_performed=usage.get("searches_performed") or 0,
        searches_limit=limits["searches_daily"],
        url_analyses=usage.get("url_analyses") or 0,
        url_analyses_limit=limits["url_analyses_monthly"],
        api_calls=usage.get("api_calls") or 0,
        api_calls_limit=limits["api_calls_daily"],
        last_activity=usage.get("last_activity")
    )


# =============================================================================
# NOTIFICATIONS
# =============================================================================

@router.get("/notifications", response_model=List[Notification])
async def get_notifications(
    unread_only: bool = Query(False, description="Return only unread notifications"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user notifications.
    """
    db = get_postgres()

    query = """
        SELECT
            notification_id, type, title, message, resource_url, is_read, created_at
        FROM notifications
        WHERE user_id = :user_id
    """
    params: Dict[str, Any] = {"user_id": current_user["user_id"]}

    if unread_only:
        query += " AND is_read = false"

    query += " ORDER BY created_at DESC LIMIT :lim OFFSET :off"
    params["lim"] = limit
    params["off"] = offset

    results = db.execute_query(query, params)

    return [
        Notification(
            id=str(row["notification_id"]),
            type=row["type"],
            title=row["title"],
            message=row["message"],
            link=row.get("resource_url"),
            read=row.get("is_read", False),
            created_at=row["created_at"]
        )
        for row in results
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a notification as read.
    """
    db = get_postgres()

    result = db.execute_update(
        """
        UPDATE notifications
        SET is_read = true, read_at = NOW()
        WHERE notification_id = :nid AND user_id = :user_id
        """,
        {"nid": notification_id, "user_id": current_user["user_id"]}
    )

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or you don't have access"
        )

    return {"message": "Notification marked as read"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user)
):
    """
    Mark all user's notifications as read.
    """
    db = get_postgres()

    count = db.execute_update(
        """
        UPDATE notifications
        SET is_read = true, read_at = NOW()
        WHERE user_id = :user_id AND is_read = false
        """,
        {"user_id": current_user["user_id"]}
    )

    return {"message": f"{count} notifications marked as read"}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a notification.
    """
    db = get_postgres()

    result = db.execute_update(
        """
        DELETE FROM notifications
        WHERE notification_id = :nid AND user_id = :user_id
        """,
        {"nid": notification_id, "user_id": current_user["user_id"]}
    )

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or you don't have access"
        )

    return {"message": "Notification deleted"}


# =============================================================================
# ACTIVITY LOG
# =============================================================================

@router.get("/activity", response_model=List[ActivityLog])
async def get_activity_log(
    usage_type: Optional[str] = Query(None, description="Filter by usage type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's activity log.
    """
    db = get_postgres()

    query = """
        SELECT
            usage_id, usage_type, metadata, created_at
        FROM user_usage
        WHERE user_id = :user_id
    """
    params: Dict[str, Any] = {"user_id": current_user["user_id"]}

    if usage_type:
        query += " AND usage_type = :usage_type"
        params["usage_type"] = usage_type

    query += " ORDER BY created_at DESC LIMIT :lim OFFSET :off"
    params["lim"] = limit
    params["off"] = offset

    results = db.execute_query(query, params)

    return [
        ActivityLog(
            id=str(row["usage_id"]),
            usage_type=row["usage_type"],
            metadata=row.get("metadata") or {},
            created_at=row["created_at"]
        )
        for row in results
    ]


# =============================================================================
# DASHBOARD SUMMARY
# =============================================================================

@router.get("/dashboard")
async def get_dashboard_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive dashboard summary.
    """
    db = get_postgres()

    # Get usage stats
    usage_stats = await get_usage_stats(period="monthly", current_user=current_user)

    # Get unread notifications count
    notif_rows = db.execute_query(
        """
        SELECT COUNT(*) as unread_count
        FROM notifications
        WHERE user_id = :user_id AND is_read = false
        """,
        {"user_id": current_user["user_id"]}
    )
    unread_count = notif_rows[0].get("unread_count", 0) if notif_rows else 0

    # Get subscription info
    sub_rows = db.execute_query(
        """
        SELECT tier, status, current_period_end
        FROM subscriptions
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"user_id": current_user["user_id"]}
    )
    subscription = sub_rows[0] if sub_rows else None

    # Get URL analyses summary
    analysis_rows = db.execute_query(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status IN ('pending', 'processing') THEN 1 ELSE 0 END) as in_progress
        FROM url_analyses
        WHERE user_id = :user_id
          AND created_at >= DATE_TRUNC('month', NOW())
        """,
        {"user_id": current_user["user_id"]}
    )
    url_summary = analysis_rows[0] if analysis_rows else {}

    return {
        "user": {
            "id": current_user["user_id"],
            "email": current_user.get("email", ""),
            "full_name": current_user.get("full_name", ""),
            "tier": current_user.get("subscription_tier", "freemium")
        },
        "usage": usage_stats.dict(),
        "notifications": {
            "unread_count": unread_count
        },
        "subscription": {
            "tier": subscription.get("tier") if subscription else "freemium",
            "status": subscription.get("status") if subscription else "active",
            "expires": subscription.get("current_period_end") if subscription else None
        },
        "url_analyses": {
            "total": url_summary.get("total") or 0,
            "completed": url_summary.get("completed") or 0,
            "in_progress": url_summary.get("in_progress") or 0
        }
    }
