"""
User Activity Routes — History management, saved analyses, bookmarks.

Enables users to save their analysis work, track browsing history,
and manage bookmarks for later reference.
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user

logger = setup_logging("activity")
router = APIRouter(prefix="/api/user", tags=["User Activity"])


class ActivityEntry(BaseModel):
    activity_id: str
    activity_type: str
    activity_data: dict = {}
    created_at: str


class SavedAnalysis(BaseModel):
    analysis_id: Optional[str] = None
    title: str
    analysis_type: str
    content: dict = {}
    tags: List[str] = []
    is_public: bool = False
    created_at: Optional[str] = None


class BookmarkEntry(BaseModel):
    bookmark_id: Optional[str] = None
    article_id: str
    note: Optional[str] = None
    created_at: Optional[str] = None
    article_title: Optional[str] = None
    article_source: Optional[str] = None


# ── Activity History ──

@router.get("/activity", response_model=List[ActivityEntry])
async def get_activity_history(
    activity_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """Get user's activity history, optionally filtered by type."""
    db = get_postgres()
    params = {"uid": str(current_user["user_id"]), "limit": limit, "offset": offset}

    type_filter = ""
    if activity_type:
        type_filter = "AND activity_type = :atype"
        params["atype"] = activity_type

    rows = db.execute_query(f"""
        SELECT activity_id, activity_type, activity_data, created_at
        FROM user_activity
        WHERE user_id = :uid {type_filter}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """, params)

    return [
        ActivityEntry(
            activity_id=str(r["activity_id"]),
            activity_type=r["activity_type"],
            activity_data=r.get("activity_data") or {},
            created_at=str(r["created_at"]),
        )
        for r in (rows or [])
    ]


@router.post("/activity")
async def log_activity(
    activity_type: str,
    activity_data: dict = {},
    current_user: dict = Depends(get_current_user),
):
    """Log a user activity event."""
    db = get_postgres()
    db.execute_update(
        """INSERT INTO user_activity (user_id, activity_type, activity_data)
           VALUES (:uid, :atype, :adata::jsonb)""",
        {"uid": str(current_user["user_id"]), "atype": activity_type, "adata": json.dumps(activity_data)}
    )
    return {"status": "logged"}


# ── Saved Analyses ──

@router.get("/analyses", response_model=List[SavedAnalysis])
async def list_saved_analyses(
    analysis_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user),
):
    """List user's saved analyses/reports."""
    db = get_postgres()
    params = {"uid": str(current_user["user_id"]), "limit": limit}

    type_filter = ""
    if analysis_type:
        type_filter = "AND analysis_type = :atype"
        params["atype"] = analysis_type

    rows = db.execute_query(f"""
        SELECT analysis_id, title, analysis_type, content, tags, is_public, created_at
        FROM saved_analyses
        WHERE user_id = :uid {type_filter}
        ORDER BY created_at DESC LIMIT :limit
    """, params)

    return [
        SavedAnalysis(
            analysis_id=str(r["analysis_id"]),
            title=r["title"],
            analysis_type=r["analysis_type"],
            content=r.get("content") or {},
            tags=r.get("tags") or [],
            is_public=r.get("is_public", False),
            created_at=str(r["created_at"]),
        )
        for r in (rows or [])
    ]


@router.post("/analyses", response_model=SavedAnalysis, status_code=201)
async def save_analysis(analysis: SavedAnalysis, current_user: dict = Depends(get_current_user)):
    """Save an analysis or report for later reference."""
    db = get_postgres()
    result = db.execute_query(
        """INSERT INTO saved_analyses (user_id, title, analysis_type, content, tags, is_public)
           VALUES (:uid, :title, :atype, :content::jsonb, :tags, :public)
           RETURNING analysis_id, created_at""",
        {
            "uid": str(current_user["user_id"]),
            "title": analysis.title,
            "atype": analysis.analysis_type,
            "content": json.dumps(analysis.content),
            "tags": analysis.tags,
            "public": analysis.is_public,
        }
    )
    if result:
        analysis.analysis_id = str(result[0]["analysis_id"])
        analysis.created_at = str(result[0]["created_at"])
    return analysis


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a saved analysis."""
    db = get_postgres()
    db.execute_update(
        "DELETE FROM saved_analyses WHERE analysis_id = :aid AND user_id = :uid",
        {"aid": analysis_id, "uid": str(current_user["user_id"])}
    )
    return {"status": "deleted"}


# ── Bookmarks ──

@router.get("/bookmarks", response_model=List[BookmarkEntry])
async def list_bookmarks(limit: int = Query(default=50, le=200), current_user: dict = Depends(get_current_user)):
    """List user's bookmarked articles."""
    db = get_postgres()
    rows = db.execute_query("""
        SELECT b.bookmark_id, b.article_id, b.note, b.created_at,
               a.title as article_title, a.source_name as article_source
        FROM user_bookmarks b
        LEFT JOIN articles a ON a.article_id = b.article_id
        WHERE b.user_id = :uid
        ORDER BY b.created_at DESC LIMIT :limit
    """, {"uid": str(current_user["user_id"]), "limit": limit})

    return [
        BookmarkEntry(
            bookmark_id=str(r["bookmark_id"]),
            article_id=str(r["article_id"]),
            note=r.get("note"),
            created_at=str(r["created_at"]),
            article_title=r.get("article_title"),
            article_source=r.get("article_source"),
        )
        for r in (rows or [])
    ]


@router.post("/bookmarks", status_code=201)
async def add_bookmark(article_id: str, note: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Bookmark an article."""
    db = get_postgres()
    try:
        db.execute_update(
            """INSERT INTO user_bookmarks (user_id, article_id, note)
               VALUES (:uid, :aid, :note)
               ON CONFLICT (user_id, article_id) DO UPDATE SET note = :note""",
            {"uid": str(current_user["user_id"]), "aid": article_id, "note": note}
        )
        return {"status": "bookmarked"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/bookmarks/{article_id}")
async def remove_bookmark(article_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a bookmark."""
    db = get_postgres()
    db.execute_update(
        "DELETE FROM user_bookmarks WHERE user_id = :uid AND article_id = :aid",
        {"uid": str(current_user["user_id"]), "aid": article_id}
    )
    return {"status": "removed"}
