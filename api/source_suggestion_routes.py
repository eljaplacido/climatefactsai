"""
Source Suggestion Routes — Allow users to suggest new sources for the platform.

Endpoints for submitting source suggestions (news, climate data, research),
viewing user's own suggestions, and admin review/approval flow.

-- Run once on the database:
-- CREATE TABLE IF NOT EXISTS source_suggestions (
--   suggestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   user_id UUID REFERENCES users(user_id),
--   url TEXT NOT NULL,
--   source_type VARCHAR(50) NOT NULL,
--   name VARCHAR(200) NOT NULL,
--   description TEXT,
--   country_code CHAR(2),
--   language VARCHAR(10),
--   status VARCHAR(20) DEFAULT 'pending',
--   admin_notes TEXT,
--   reviewed_by UUID,
--   reviewed_at TIMESTAMPTZ,
--   created_at TIMESTAMPTZ DEFAULT NOW()
-- );
"""

from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user, get_optional_user

logger = setup_logging("source_suggestions")
router = APIRouter(prefix="/api/source-suggestions", tags=["Source Suggestions"])

VALID_SOURCE_TYPES = {"news", "climate_data", "research", "weather_api", "government"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SourceSuggestion(BaseModel):
    url: str = Field(..., description="URL of the suggested source")
    source_type: str = Field(..., description="One of: news, climate_data, research, weather_api, government")
    name: str = Field(..., max_length=200, description="Suggested display name for the source")
    description: str = Field(..., description="Why this source is valuable for the platform")
    country_code: Optional[str] = Field(None, max_length=2, description="ISO 3166-1 alpha-2 country code")
    language: Optional[str] = Field(None, max_length=10, description="Language code (e.g. en, fi, sv)")


class SuggestionResponse(BaseModel):
    suggestion_id: str
    status: str
    message: str


class SuggestionListItem(BaseModel):
    suggestion_id: str
    url: str
    source_type: str
    name: str
    description: Optional[str] = None
    country_code: Optional[str] = None
    language: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None


class ReviewRequest(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    admin_notes: Optional[str] = Field(None, description="Optional notes about the review decision")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db():
    return get_postgres()


async def _validate_url_accessible(url: str) -> bool:
    """Check that the URL is reachable (HEAD or GET with short timeout)."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.head(url)
            if resp.status_code < 400:
                return True
            # Some servers reject HEAD, try GET
            resp = await client.get(url)
            return resp.status_code < 400
    except Exception:
        return False


def _require_admin(user: dict):
    """Check that the user has admin privileges (subscription_tier enterprise or explicit role)."""
    tier = (user.get("subscription_tier") or "").lower()
    if tier not in ("enterprise", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
async def submit_suggestion(
    suggestion: SourceSuggestion,
    current_user: Optional[dict] = Depends(get_optional_user),
    db=Depends(_get_db),
):
    """
    Submit a new source suggestion for admin review.
    Authentication is recommended but not strictly required.
    """
    # Validate source type
    if suggestion.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type. Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}",
        )

    # Validate name length
    if not suggestion.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source name cannot be empty",
        )

    # Validate URL is accessible
    url_ok = await _validate_url_accessible(suggestion.url)
    if not url_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided URL is not accessible. Please check it and try again.",
        )

    # Check for duplicate URL
    existing = db.execute_query(
        "SELECT suggestion_id FROM source_suggestions WHERE url = :url AND status != 'rejected'",
        {"url": suggestion.url},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This URL has already been suggested.",
        )

    user_id = str(current_user["user_id"]) if current_user else None

    try:
        rows = db.execute_query(
            """
            INSERT INTO source_suggestions (
                user_id, url, source_type, name, description,
                country_code, language, status
            )
            VALUES (
                :user_id, :url, :source_type, :name, :description,
                :country_code, :language, 'pending'
            )
            RETURNING suggestion_id
            """,
            {
                "user_id": user_id,
                "url": suggestion.url,
                "source_type": suggestion.source_type,
                "name": suggestion.name.strip(),
                "description": suggestion.description,
                "country_code": suggestion.country_code.upper() if suggestion.country_code else None,
                "language": suggestion.language,
            },
        )

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save suggestion",
            )

        suggestion_id = str(rows[0]["suggestion_id"])
        logger.info("Source suggestion submitted", suggestion_id=suggestion_id, url=suggestion.url)

        return SuggestionResponse(
            suggestion_id=suggestion_id,
            status="pending",
            message="Thank you! Your source suggestion has been submitted for review.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to insert source suggestion", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit suggestion",
        )


@router.get("/my", response_model=List[SuggestionListItem])
async def get_my_suggestions(
    current_user: dict = Depends(get_current_user),
    db=Depends(_get_db),
):
    """Get the authenticated user's own source suggestions with their status."""
    user_id = str(current_user["user_id"])

    rows = db.execute_query(
        """
        SELECT suggestion_id, url, source_type, name, description,
               country_code, language, status, admin_notes,
               created_at, reviewed_at
        FROM source_suggestions
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        """,
        {"user_id": user_id},
    )

    return [
        SuggestionListItem(
            suggestion_id=str(r["suggestion_id"]),
            url=r["url"],
            source_type=r["source_type"],
            name=r["name"],
            description=r.get("description"),
            country_code=r.get("country_code"),
            language=r.get("language"),
            status=r["status"],
            admin_notes=r.get("admin_notes"),
            created_at=r.get("created_at"),
            reviewed_at=r.get("reviewed_at"),
        )
        for r in (rows or [])
    ]


@router.get("/", response_model=List[SuggestionListItem])
async def list_all_suggestions(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: pending, reviewing, approved, rejected"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db=Depends(_get_db),
):
    """Admin: list all source suggestions with optional status filter and pagination."""
    _require_admin(current_user)

    params: dict = {"limit": limit, "offset": offset}
    where_clause = ""

    if status_filter:
        valid_statuses = {"pending", "reviewing", "approved", "rejected"}
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(sorted(valid_statuses))}",
            )
        where_clause = "WHERE status = :status_filter"
        params["status_filter"] = status_filter

    rows = db.execute_query(
        f"""
        SELECT suggestion_id, url, source_type, name, description,
               country_code, language, status, admin_notes,
               created_at, reviewed_at
        FROM source_suggestions
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    return [
        SuggestionListItem(
            suggestion_id=str(r["suggestion_id"]),
            url=r["url"],
            source_type=r["source_type"],
            name=r["name"],
            description=r.get("description"),
            country_code=r.get("country_code"),
            language=r.get("language"),
            status=r["status"],
            admin_notes=r.get("admin_notes"),
            created_at=r.get("created_at"),
            reviewed_at=r.get("reviewed_at"),
        )
        for r in (rows or [])
    ]


@router.put("/{suggestion_id}/review", response_model=SuggestionResponse)
async def review_suggestion(
    suggestion_id: str,
    review: ReviewRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(_get_db),
):
    """Admin: approve or reject a source suggestion."""
    _require_admin(current_user)

    if review.action not in ("approve", "reject"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approve' or 'reject'",
        )

    # Verify the suggestion exists
    existing = db.execute_query(
        "SELECT suggestion_id, url, name, source_type, status FROM source_suggestions WHERE suggestion_id = :sid",
        {"sid": suggestion_id},
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )

    suggestion_row = existing[0]
    current_status = suggestion_row["status"]
    if current_status in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Suggestion has already been {current_status}",
        )

    new_status = "approved" if review.action == "approve" else "rejected"
    reviewer_id = str(current_user["user_id"])

    db.execute_update(
        """
        UPDATE source_suggestions
        SET status = :status,
            admin_notes = :notes,
            reviewed_by = :reviewer,
            reviewed_at = NOW()
        WHERE suggestion_id = :sid
        """,
        {
            "status": new_status,
            "notes": review.admin_notes,
            "reviewer": reviewer_id,
            "sid": suggestion_id,
        },
    )

    # If approved, optionally add to rss_feed_registry
    if new_status == "approved":
        try:
            db.execute_update(
                """
                INSERT INTO rss_feed_registry (feed_url, source_name, country_code, language, is_active)
                VALUES (:url, :name, :country, :lang, true)
                ON CONFLICT (feed_url) DO NOTHING
                """,
                {
                    "url": suggestion_row["url"],
                    "name": suggestion_row["name"],
                    "country": suggestion_row.get("country_code"),
                    "lang": suggestion_row.get("language"),
                },
            )
            logger.info("Approved source added to feed registry", url=suggestion_row["url"])
        except Exception as e:
            # Non-fatal: the suggestion is still approved even if feed registry insert fails
            logger.warning("Could not add approved source to feed registry", error=str(e))

    logger.info(
        "Source suggestion reviewed",
        suggestion_id=suggestion_id,
        action=review.action,
        reviewer=reviewer_id,
    )

    return SuggestionResponse(
        suggestion_id=suggestion_id,
        status=new_status,
        message=f"Suggestion has been {new_status}.",
    )
