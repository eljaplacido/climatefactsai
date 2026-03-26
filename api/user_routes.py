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
# READING HISTORY
# =============================================================================

class RecordReadingRequest(BaseModel):
    """Request to record article reading"""
    article_id: str
    read_duration_seconds: Optional[int] = None
    scroll_depth_pct: Optional[float] = None


@router.get("/reading-history")
async def get_reading_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    days: Optional[int] = Query(None, ge=1, le=365, description="Filter by last N days"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's reading history (paginated).
    """
    db = get_postgres()
    offset = (page - 1) * limit
    params: Dict[str, Any] = {"user_id": current_user["user_id"], "lim": limit, "off": offset}

    time_filter = ""
    if days:
        time_filter = " AND rh.read_at >= NOW() - INTERVAL ':days days'"
        # Use explicit date math for safety
        time_filter = f" AND rh.read_at >= NOW() - INTERVAL '{days} days'"

    query = f"""
        SELECT rh.article_id, a.title, a.source_name, rh.read_at,
               rh.read_duration_seconds, rh.scroll_depth_pct,
               a.overall_credibility as credibility
        FROM user_reading_history rh
        LEFT JOIN articles a ON a.article_id = rh.article_id
        WHERE rh.user_id = :user_id{time_filter}
        ORDER BY rh.read_at DESC
        LIMIT :lim OFFSET :off
    """

    try:
        rows = db.execute_query(query, params)
    except Exception:
        # Table may not exist yet - return empty
        rows = []

    items = [
        {
            "article_id": str(row.get("article_id", "")),
            "title": row.get("title", "Unknown Article"),
            "source_name": row.get("source_name", "Unknown"),
            "read_at": str(row.get("read_at", "")),
            "read_duration_seconds": row.get("read_duration_seconds"),
            "scroll_depth_pct": row.get("scroll_depth_pct"),
            "credibility": row.get("credibility"),
        }
        for row in rows
    ]

    return {"items": items, "page": page, "limit": limit}


@router.post("/reading-history")
async def record_reading(
    request: RecordReadingRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Record that a user read an article.
    """
    db = get_postgres()

    try:
        db.execute_update(
            """
            INSERT INTO user_reading_history (user_id, article_id, read_duration_seconds, scroll_depth_pct)
            VALUES (:user_id, :article_id, :duration, :depth)
            ON CONFLICT (user_id, article_id) DO UPDATE
            SET read_at = NOW(),
                read_duration_seconds = COALESCE(EXCLUDED.read_duration_seconds, user_reading_history.read_duration_seconds),
                scroll_depth_pct = COALESCE(EXCLUDED.scroll_depth_pct, user_reading_history.scroll_depth_pct)
            """,
            {
                "user_id": current_user["user_id"],
                "article_id": request.article_id,
                "duration": request.read_duration_seconds,
                "depth": request.scroll_depth_pct,
            },
        )
    except Exception as e:
        logger.warning(f"Could not record reading history (table may not exist): {e}")
        # Graceful fallback - don't fail the request
        pass

    return {"message": "Reading recorded"}


# =============================================================================
# BOOKMARKS
# =============================================================================

class CreateBookmarkRequest(BaseModel):
    """Request to bookmark an article"""
    folder: str = Field(default="default")
    notes: Optional[str] = None


@router.get("/bookmarks")
async def get_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    folder: str = Query("default"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's bookmarked articles (paginated).
    """
    db = get_postgres()
    offset = (page - 1) * limit
    params: Dict[str, Any] = {
        "user_id": current_user["user_id"],
        "lim": limit,
        "off": offset,
    }

    folder_filter = ""
    if folder != "default":
        folder_filter = " AND b.folder = :folder"
        params["folder"] = folder

    query = f"""
        SELECT b.article_id, a.title, a.source_name, b.bookmarked_at,
               b.folder, b.notes, a.overall_credibility as credibility
        FROM user_bookmarks b
        LEFT JOIN articles a ON a.article_id = b.article_id
        WHERE b.user_id = :user_id{folder_filter}
        ORDER BY b.bookmarked_at DESC
        LIMIT :lim OFFSET :off
    """

    try:
        rows = db.execute_query(query, params)
    except Exception:
        rows = []

    # Get distinct folders
    try:
        folder_rows = db.execute_query(
            "SELECT DISTINCT folder FROM user_bookmarks WHERE user_id = :user_id ORDER BY folder",
            {"user_id": current_user["user_id"]},
        )
        folders = [r["folder"] for r in folder_rows] if folder_rows else ["default"]
    except Exception:
        folders = ["default"]

    if "default" not in folders:
        folders.insert(0, "default")

    items = [
        {
            "article_id": str(row.get("article_id", "")),
            "title": row.get("title", "Unknown Article"),
            "source_name": row.get("source_name", "Unknown"),
            "bookmarked_at": str(row.get("bookmarked_at", "")),
            "folder": row.get("folder", "default"),
            "notes": row.get("notes"),
            "credibility": row.get("credibility"),
        }
        for row in rows
    ]

    return {"items": items, "folders": folders, "page": page, "limit": limit}


@router.post("/bookmarks/{article_id}")
async def create_bookmark(
    article_id: str,
    request: CreateBookmarkRequest = CreateBookmarkRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Bookmark an article.
    """
    db = get_postgres()

    try:
        db.execute_update(
            """
            INSERT INTO user_bookmarks (user_id, article_id, folder, notes)
            VALUES (:user_id, :article_id, :folder, :notes)
            ON CONFLICT (user_id, article_id) DO UPDATE
            SET folder = EXCLUDED.folder, notes = EXCLUDED.notes, bookmarked_at = NOW()
            """,
            {
                "user_id": current_user["user_id"],
                "article_id": article_id,
                "folder": request.folder,
                "notes": request.notes,
            },
        )
    except Exception as e:
        logger.error(f"Error creating bookmark: {e}")
        raise HTTPException(status_code=500, detail="Failed to create bookmark")

    return {"message": "Article bookmarked", "article_id": article_id}


@router.delete("/bookmarks/{article_id}")
async def delete_bookmark(
    article_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove a bookmark.
    """
    db = get_postgres()

    try:
        result = db.execute_update(
            "DELETE FROM user_bookmarks WHERE user_id = :user_id AND article_id = :article_id",
            {"user_id": current_user["user_id"], "article_id": article_id},
        )
    except Exception as e:
        logger.error(f"Error deleting bookmark: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")

    if result == 0:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    return {"message": "Bookmark removed"}


# =============================================================================
# SEARCH HISTORY
# =============================================================================

@router.get("/search-history")
async def get_search_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's search history (paginated).
    """
    db = get_postgres()
    offset = (page - 1) * limit

    try:
        rows = db.execute_query(
            """
            SELECT query, filters, result_count, created_at
            FROM user_search_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :lim OFFSET :off
            """,
            {"user_id": current_user["user_id"], "lim": limit, "off": offset},
        )
    except Exception:
        rows = []

    items = [
        {
            "query": row.get("query", ""),
            "filters": row.get("filters") or {},
            "result_count": row.get("result_count", 0),
            "searched_at": str(row.get("created_at", "")),
        }
        for row in rows
    ]

    return {"items": items, "page": page, "limit": limit}


# =============================================================================
# DASHBOARD STATS
# =============================================================================

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
):
    """
    Get aggregated dashboard statistics for the current user.
    Returns article counts, bookmark count, search count, days active, and tier usage.
    """
    db = get_postgres()
    user_id = current_user["user_id"]
    tier = current_user.get("subscription_tier", "freemium")

    tier_limits = {
        "freemium": {"articles_daily": 5, "searches_daily": 10},
        "basic": {"articles_daily": 50, "searches_daily": 50},
        "professional": {"articles_daily": -1, "searches_daily": -1},
        "enterprise": {"articles_daily": -1, "searches_daily": -1},
    }
    limits = tier_limits.get(tier, tier_limits["freemium"])

    # Collect stats in parallel-safe manner
    articles_read_week = 0
    articles_read_total = 0
    bookmarks_count = 0
    searches_count = 0
    days_active = 0
    articles_today = 0
    searches_today = 0

    try:
        # Articles read this week
        rows = db.execute_query(
            """
            SELECT COUNT(*) as cnt FROM user_reading_history
            WHERE user_id = :uid AND read_at >= NOW() - INTERVAL '7 days'
            """,
            {"uid": user_id},
        )
        articles_read_week = (rows[0].get("cnt", 0) if rows else 0) or 0

        # Articles read total
        rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM user_reading_history WHERE user_id = :uid",
            {"uid": user_id},
        )
        articles_read_total = (rows[0].get("cnt", 0) if rows else 0) or 0

        # Articles today
        rows = db.execute_query(
            """
            SELECT COUNT(*) as cnt FROM user_reading_history
            WHERE user_id = :uid AND read_at >= DATE_TRUNC('day', NOW())
            """,
            {"uid": user_id},
        )
        articles_today = (rows[0].get("cnt", 0) if rows else 0) or 0
    except Exception:
        pass

    try:
        # Bookmarks count
        rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM user_bookmarks WHERE user_id = :uid",
            {"uid": user_id},
        )
        bookmarks_count = (rows[0].get("cnt", 0) if rows else 0) or 0
    except Exception:
        pass

    try:
        # Searches count (from user_usage or search_history table)
        rows = db.execute_query(
            """
            SELECT COUNT(*) as cnt FROM user_usage
            WHERE user_id = :uid AND usage_type = 'search'
            """,
            {"uid": user_id},
        )
        searches_count = (rows[0].get("cnt", 0) if rows else 0) or 0

        # Searches today
        rows = db.execute_query(
            """
            SELECT COUNT(*) as cnt FROM user_usage
            WHERE user_id = :uid AND usage_type = 'search' AND created_at >= DATE_TRUNC('day', NOW())
            """,
            {"uid": user_id},
        )
        searches_today = (rows[0].get("cnt", 0) if rows else 0) or 0
    except Exception:
        pass

    try:
        # Days active (distinct days with any usage)
        rows = db.execute_query(
            """
            SELECT COUNT(DISTINCT DATE(created_at)) as cnt FROM user_usage
            WHERE user_id = :uid
            """,
            {"uid": user_id},
        )
        days_active = (rows[0].get("cnt", 0) if rows else 0) or 0
    except Exception:
        pass

    return {
        "articles_read_week": articles_read_week,
        "articles_read_total": articles_read_total,
        "bookmarks_count": bookmarks_count,
        "searches_count": searches_count,
        "days_active": days_active,
        "current_tier": tier,
        "tier_usage": {
            "articles_used": articles_today,
            "articles_limit": limits["articles_daily"],
            "searches_used": searches_today,
            "searches_limit": limits["searches_daily"],
        },
    }


# =============================================================================
# DASHBOARD SUMMARY (legacy)
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
