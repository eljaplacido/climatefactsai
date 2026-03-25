"""
Source Registry Routes

Allows authenticated users to register, manage, and validate custom RSS/Atom
feed sources. Access is tier-gated: freemium users cannot register sources,
standard users may register up to 3, professional users up to 20, and enterprise
users are unlimited.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field, HttpUrl

from api.auth_routes import get_current_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("source-registry-api")
router = APIRouter(prefix="/api/sources", tags=["Sources"])

# ---------------------------------------------------------------------------
# Tier limits: maps subscription tier → max custom sources (None = unlimited)
# ---------------------------------------------------------------------------

SOURCE_LIMITS: dict = {
    "freemium": 0,
    "standard": 3,
    "basic": 3,       # backward-compatible alias for standard
    "professional": 20,
    "enterprise": None,  # Unlimited
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RegisterSourceRequest(BaseModel):
    """Payload for registering a new custom RSS/Atom source."""

    source_name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for the source")
    source_url: str = Field(..., description="Publicly accessible RSS or Atom feed URL")
    feed_type: str = Field(default="rss", description="Feed format: 'rss' or 'atom'")
    country_code: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (optional)",
    )


class UpdateSourceRequest(BaseModel):
    """Payload for toggling a source active/inactive."""

    is_active: bool = Field(..., description="Whether the source should be actively fetched")


class SourceRegistrationResponse(BaseModel):
    """Serialised representation of a single source registration row."""

    registration_id: str
    user_id: str
    source_name: str
    source_url: str
    feed_type: str
    reliability_tier: str
    country_code: Optional[str]
    is_active: bool
    approved: bool
    last_fetched_at: Optional[Any]
    fetch_error: Optional[str]
    created_at: Optional[Any]


class FeedValidationResponse(BaseModel):
    """Result of validating a feed URL."""

    url: str
    valid: bool
    title: Optional[str] = None
    item_count: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db():
    """Return a synchronous Postgres client."""
    return get_postgres()


def _row_to_response(row: dict) -> SourceRegistrationResponse:
    """Convert a raw SQL row into the response model."""
    return SourceRegistrationResponse(
        registration_id=str(row["registration_id"]),
        user_id=str(row["user_id"]),
        source_name=row["source_name"],
        source_url=row["source_url"],
        feed_type=row.get("feed_type") or "rss",
        reliability_tier=row.get("reliability_tier") or "public",
        country_code=row.get("country_code"),
        is_active=bool(row.get("is_active", True)),
        approved=bool(row.get("approved", False)),
        last_fetched_at=row.get("last_fetched_at"),
        fetch_error=row.get("fetch_error"),
        created_at=row.get("created_at"),
    )


def _check_feed_url(url: str) -> FeedValidationResponse:
    """
    Attempt to parse the given URL as an RSS/Atom feed via feedparser.
    Returns a FeedValidationResponse describing the result.
    """
    try:
        from app.domains.content.data_sources.rss_adapter import _parse_feed
        import feedparser  # feedparser is already a project dependency

        feed = feedparser.parse(url)
        title = feed.feed.get("title") if feed.feed else None

        if feed.bozo and not feed.entries:
            return FeedValidationResponse(
                url=url,
                valid=False,
                error=str(feed.bozo_exception) if feed.bozo_exception else "Feed could not be parsed",
            )

        return FeedValidationResponse(
            url=url,
            valid=True,
            title=title,
            item_count=len(feed.entries),
        )
    except Exception as exc:
        logger.warning("Feed validation error", url=url, error=str(exc))
        return FeedValidationResponse(url=url, valid=False, error=str(exc))


def _get_source_or_404(db, registration_id: str, user_id: str) -> dict:
    """
    Fetch a source registration row by ID, scoped to the requesting user.
    Raises HTTP 404 when not found or not owned by the user.
    """
    rows = db.execute_query(
        """
        SELECT registration_id, user_id, source_name, source_url, feed_type,
               reliability_tier, country_code, is_active, approved,
               last_fetched_at, fetch_error, created_at
        FROM user_source_registrations
        WHERE registration_id = :registration_id
          AND user_id = :user_id
        """,
        params={"registration_id": registration_id, "user_id": user_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source registration not found",
        )
    return rows[0]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=SourceRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a custom RSS/Atom feed source",
)
async def register_source(
    request: RegisterSourceRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Register a new custom feed source for the authenticated user.

    Tier limits:
    - freemium: 0 (not allowed)
    - standard / basic: up to 3
    - professional: up to 20
    - enterprise: unlimited
    """
    user_id = str(current_user["user_id"])
    tier = current_user.get("subscription_tier", "freemium")

    # Enforce tier limits
    limit = SOURCE_LIMITS.get(tier, 0)
    if limit == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your subscription tier does not allow custom source registration. Upgrade to standard or higher.",
        )

    db = _get_db()

    if limit is not None:
        count_rows = db.execute_query(
            "SELECT COUNT(*) AS cnt FROM user_source_registrations WHERE user_id = :user_id",
            params={"user_id": user_id},
        )
        current_count = int(count_rows[0]["cnt"]) if count_rows else 0
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"You have reached the maximum of {limit} custom sources "
                    f"for your {tier} subscription. Upgrade to register more."
                ),
            )

    # Validate the feed URL before persisting
    validation = _check_feed_url(request.source_url)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The URL does not appear to be a valid RSS/Atom feed: {validation.error}",
        )

    # Normalise country code
    country_code = request.country_code.upper() if request.country_code else None

    try:
        rows = db.execute_query(
            """
            INSERT INTO user_source_registrations
                (user_id, source_name, source_url, feed_type, country_code)
            VALUES
                (:user_id, :source_name, :source_url, :feed_type, :country_code)
            RETURNING
                registration_id, user_id, source_name, source_url, feed_type,
                reliability_tier, country_code, is_active, approved,
                last_fetched_at, fetch_error, created_at
            """,
            params={
                "user_id": user_id,
                "source_name": request.source_name.strip(),
                "source_url": request.source_url.strip(),
                "feed_type": request.feed_type.lower(),
                "country_code": country_code,
            },
        )
    except Exception as exc:
        err = str(exc)
        if "unique" in err.lower() or "duplicate" in err.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already registered this feed URL.",
            )
        logger.error("Source registration insert failed", error=err, user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register source",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register source — no row returned",
        )

    logger.info(
        "Source registered",
        user_id=user_id,
        source_url=request.source_url,
        tier=tier,
    )
    return _row_to_response(rows[0])


@router.get(
    "/my-sources",
    response_model=List[SourceRegistrationResponse],
    summary="List the current user's registered sources",
)
async def list_my_sources(
    current_user: dict = Depends(get_current_user),
):
    """Return all source registrations belonging to the authenticated user."""
    user_id = str(current_user["user_id"])
    db = _get_db()

    rows = db.execute_query(
        """
        SELECT registration_id, user_id, source_name, source_url, feed_type,
               reliability_tier, country_code, is_active, approved,
               last_fetched_at, fetch_error, created_at
        FROM user_source_registrations
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        """,
        params={"user_id": user_id},
    )

    return [_row_to_response(row) for row in rows]


@router.put(
    "/{registration_id}",
    response_model=SourceRegistrationResponse,
    summary="Toggle a source active or inactive",
)
async def update_source(
    registration_id: str,
    request: UpdateSourceRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update the active/inactive state of a registered source.

    Only the owning user may modify their own sources.
    """
    user_id = str(current_user["user_id"])
    db = _get_db()

    # Verify ownership (raises 404 if not found)
    _get_source_or_404(db, registration_id, user_id)

    try:
        rows = db.execute_query(
            """
            UPDATE user_source_registrations
            SET is_active = :is_active
            WHERE registration_id = :registration_id
              AND user_id = :user_id
            RETURNING
                registration_id, user_id, source_name, source_url, feed_type,
                reliability_tier, country_code, is_active, approved,
                last_fetched_at, fetch_error, created_at
            """,
            params={
                "is_active": request.is_active,
                "registration_id": registration_id,
                "user_id": user_id,
            },
        )
    except Exception as exc:
        logger.error("Source update failed", error=str(exc), registration_id=registration_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update source",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source registration not found",
        )

    logger.info(
        "Source updated",
        registration_id=registration_id,
        user_id=user_id,
        is_active=request.is_active,
    )
    return _row_to_response(rows[0])


@router.delete(
    "/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a registered source",
)
async def delete_source(
    registration_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Permanently remove a source registration.

    Only the owning user may delete their own sources.
    """
    user_id = str(current_user["user_id"])
    db = _get_db()

    # Verify ownership (raises 404 if not found)
    _get_source_or_404(db, registration_id, user_id)

    try:
        db.execute_update(
            """
            DELETE FROM user_source_registrations
            WHERE registration_id = :registration_id
              AND user_id = :user_id
            """,
            params={"registration_id": registration_id, "user_id": user_id},
        )
    except Exception as exc:
        logger.error("Source deletion failed", error=str(exc), registration_id=registration_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete source",
        )

    logger.info("Source deleted", registration_id=registration_id, user_id=user_id)
    # HTTP 204 — no response body


@router.get(
    "/validate",
    response_model=FeedValidationResponse,
    summary="Validate a feed URL without registering it",
)
async def validate_feed(
    url: str = Query(..., description="Publicly accessible RSS or Atom feed URL to validate"),
    current_user: dict = Depends(get_current_user),
):
    """
    Parse the given URL as an RSS/Atom feed and report whether it is valid.

    Returns the feed title and item count on success, or an error message on
    failure. Does not persist anything to the database.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must begin with http:// or https://",
        )

    return _check_feed_url(url)
