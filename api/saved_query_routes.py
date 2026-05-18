"""
Saved Query Routes — Recurring themed searches with scheduling.

Users can save search queries with a theme and notification interval.
The system periodically runs these queries and surfaces new results.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from api.rate_limiter import TIER_LIMITS
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("saved-queries-api")
router = APIRouter(prefix="/api/user/saved-queries", tags=["Saved Queries"])

# Tier-based query limits
QUERY_LIMITS = {
    "freemium": 2,
    "basic": 10,
    "professional": 50,
    "enterprise": None,
}

VALID_INTERVALS = {"hourly", "daily", "weekly", "monthly"}


class SavedQueryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query_text: str = Field(..., min_length=3, max_length=500)
    theme: Optional[str] = Field(None, max_length=100, description="E.g. 'EU policy', 'Arctic ice', 'renewable energy'")
    country_codes: List[str] = Field(default_factory=list, max_length=10)
    categories: List[str] = Field(default_factory=list, max_length=5)
    notification_interval: str = Field(default="daily", description="hourly, daily, weekly, monthly")


class SavedQueryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    query_text: Optional[str] = Field(None, max_length=500)
    theme: Optional[str] = Field(None, max_length=100)
    country_codes: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    notification_interval: Optional[str] = None
    is_active: Optional[bool] = None


class SavedQueryResponse(BaseModel):
    query_id: str
    name: str
    query_text: str
    theme: Optional[str] = None
    country_codes: List[str] = []
    categories: List[str] = []
    notification_interval: str = "daily"
    is_active: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_result_count: int = 0
    created_at: str


class QueryResultsResponse(BaseModel):
    query_id: str
    query_text: str
    articles: List[dict] = []
    total: int = 0
    executed_at: str


@router.get("", response_model=List[SavedQueryResponse])
async def list_saved_queries(current_user: dict = Depends(get_current_user)):
    """List all saved queries for the current user."""
    db = get_postgres()
    rows = db.execute_query(
        """SELECT query_id, name, query_text, theme, country_codes, categories,
                  notification_interval, is_active, last_run_at, next_run_at,
                  last_result_count, created_at
           FROM user_saved_queries
           WHERE user_id = :uid
           ORDER BY created_at DESC""",
        {"uid": str(current_user["user_id"])},
    )
    return [
        SavedQueryResponse(
            query_id=str(r["query_id"]),
            name=r["name"],
            query_text=r["query_text"],
            theme=r.get("theme"),
            country_codes=r.get("country_codes") or [],
            categories=r.get("categories") or [],
            notification_interval=r.get("notification_interval", "daily"),
            is_active=r.get("is_active", True),
            last_run_at=str(r["last_run_at"]) if r.get("last_run_at") else None,
            next_run_at=str(r["next_run_at"]) if r.get("next_run_at") else None,
            last_result_count=r.get("last_result_count", 0),
            created_at=str(r["created_at"]),
        )
        for r in (rows or [])
    ]


@router.post("", response_model=SavedQueryResponse, status_code=201)
async def create_saved_query(
    request: SavedQueryCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new saved query with scheduled execution.

    Saved queries run automatically at the configured interval and surface
    new articles matching the search criteria.
    """
    tier = current_user.get("subscription_tier", "freemium")
    limit = QUERY_LIMITS.get(tier)

    if request.notification_interval not in VALID_INTERVALS:
        raise HTTPException(400, f"Invalid interval. Choose from: {', '.join(VALID_INTERVALS)}")

    # Enforce freemium interval restriction
    if tier == "freemium" and request.notification_interval in ("hourly",):
        raise HTTPException(403, "Hourly queries require a paid subscription.")

    # Check query count limit
    if limit is not None:
        db = get_postgres()
        count_rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM user_saved_queries WHERE user_id = :uid",
            {"uid": str(current_user["user_id"])},
        )
        current_count = count_rows[0]["cnt"] if count_rows else 0
        if current_count >= limit:
            raise HTTPException(
                403,
                f"Saved query limit reached ({current_count}/{limit}). Upgrade for more.",
            )
    else:
        db = get_postgres()

    # Calculate next run
    next_run = _calculate_next_run(request.notification_interval)

    result = db.execute_query(
        """INSERT INTO user_saved_queries
           (user_id, name, query_text, theme, country_codes, categories,
            notification_interval, next_run_at)
           VALUES (:uid, :name, :query, :theme, :cc, :cats, :interval, :next_run)
           RETURNING query_id, created_at""",
        {
            "uid": str(current_user["user_id"]),
            "name": request.name,
            "query": request.query_text,
            "theme": request.theme,
            "cc": [c.upper() for c in request.country_codes],
            "cats": request.categories,
            "interval": request.notification_interval,
            "next_run": next_run,
        },
    )

    if not result:
        raise HTTPException(500, "Failed to create saved query")

    return SavedQueryResponse(
        query_id=str(result[0]["query_id"]),
        name=request.name,
        query_text=request.query_text,
        theme=request.theme,
        country_codes=[c.upper() for c in request.country_codes],
        categories=request.categories,
        notification_interval=request.notification_interval,
        is_active=True,
        next_run_at=str(next_run) if next_run else None,
        created_at=str(result[0]["created_at"]),
    )


@router.put("/{query_id}", response_model=SavedQueryResponse)
async def update_saved_query(
    query_id: str,
    request: SavedQueryUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a saved query."""
    db = get_postgres()

    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(400, "No fields to update")

    if "notification_interval" in update_data:
        if update_data["notification_interval"] not in VALID_INTERVALS:
            raise HTTPException(400, f"Invalid interval. Choose from: {', '.join(VALID_INTERVALS)}")
        update_data["next_run_at"] = _calculate_next_run(update_data["notification_interval"])

    if "country_codes" in update_data and update_data["country_codes"] is not None:
        update_data["country_codes"] = [c.upper() for c in update_data["country_codes"]]

    set_clauses = []
    params = {"qid": query_id, "uid": str(current_user["user_id"])}
    for key, value in update_data.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value

    set_clauses.append("updated_at = NOW()")
    query = f"UPDATE user_saved_queries SET {', '.join(set_clauses)} WHERE query_id = :qid AND user_id = :uid"
    db.execute_update(query, params)

    # Return updated
    queries = await list_saved_queries(current_user)
    for q in queries:
        if q.query_id == query_id:
            return q

    raise HTTPException(404, "Query not found")


@router.delete("/{query_id}")
async def delete_saved_query(
    query_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a saved query."""
    db = get_postgres()
    db.execute_update(
        "DELETE FROM user_saved_queries WHERE query_id = :qid AND user_id = :uid",
        {"qid": query_id, "uid": str(current_user["user_id"])},
    )
    return {"status": "deleted"}


@router.post("/{query_id}/run", response_model=QueryResultsResponse)
async def run_saved_query(
    query_id: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    Run a saved query on-demand and return matching articles.

    This executes the query immediately and updates last_run_at.
    """
    db = get_postgres()

    rows = db.execute_query(
        """SELECT query_text, country_codes, categories
           FROM user_saved_queries
           WHERE query_id = :qid AND user_id = :uid""",
        {"qid": query_id, "uid": str(current_user["user_id"])},
    )

    if not rows:
        raise HTTPException(404, "Saved query not found")

    sq = rows[0]
    query_text = sq["query_text"]
    country_codes = sq.get("country_codes") or []
    categories = sq.get("categories") or []

    # Build search
    search_params: dict = {"q": query_text, "limit": limit}
    filters = []

    if country_codes:
        filters.append("a.country_code = ANY(:cc)")
        search_params["cc"] = country_codes
    if categories:
        filters.append("a.content_category = ANY(:cats)")
        search_params["cats"] = categories

    where_extra = ""
    if filters:
        where_extra = "AND " + " AND ".join(filters)

    articles = db.execute_query(
        f"""SELECT a.article_id, a.title, a.url, a.source_name, a.country_code,
                   a.overall_credibility, a.reliability_score, a.excerpt,
                   a.claims_status, a.claims_error_message, a.insight_summary,
                   a.published_date, a.content_category
            FROM articles a
            WHERE a.is_synthetic = FALSE
              AND to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,''))
                  @@ plainto_tsquery('english', :q)
            {where_extra}
            ORDER BY COALESCE(a.published_date, a.created_at) DESC
            LIMIT :limit""",
        search_params,
    )

    result_articles = []
    for a in (articles or []):
        entry = {
            "article_id": str(a["article_id"]),
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source_name": a.get("source_name", ""),
            "country_code": a.get("country_code"),
            "credibility": a.get("overall_credibility"),
            "reliability_score": a.get("reliability_score"),
            "excerpt": a.get("excerpt"),
            "insight_summary": a.get("insight_summary"),
            "content_category": a.get("content_category"),
            "published_date": str(a["published_date"]) if a.get("published_date") else None,
            "claims_status": a.get("claims_status"),
        }
        # If analysis failed, include explanation
        if a.get("claims_status") == "failed":
            entry["failure_explanation"] = _explain_query_failure(
                a.get("claims_error_message")
            )
        result_articles.append(entry)

    # Update last_run
    next_run = _calculate_next_run(
        db.execute_query(
            "SELECT notification_interval FROM user_saved_queries WHERE query_id = :qid",
            {"qid": query_id},
        )[0].get("notification_interval", "daily")
    )

    db.execute_update(
        """UPDATE user_saved_queries
           SET last_run_at = NOW(), next_run_at = :next_run,
               last_result_count = :cnt, updated_at = NOW()
           WHERE query_id = :qid""",
        {"qid": query_id, "next_run": next_run, "cnt": len(result_articles)},
    )

    return QueryResultsResponse(
        query_id=query_id,
        query_text=query_text,
        articles=result_articles,
        total=len(result_articles),
        executed_at=datetime.utcnow().isoformat(),
    )


def _calculate_next_run(interval: str) -> datetime:
    """Calculate the next scheduled run time."""
    now = datetime.utcnow()
    intervals = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }
    return now + intervals.get(interval, timedelta(days=1))


def _explain_query_failure(error_msg: Optional[str]) -> str:
    """Generate user-friendly failure explanation for query results."""
    if not error_msg:
        return "Analysis did not complete. The article may be behind a paywall or the content was too short."

    lower = error_msg.lower()
    if "rate limit" in lower or "429" in lower:
        return "AI service was temporarily overloaded. The article will be retried automatically."
    if "timeout" in lower:
        return "Analysis timed out due to long article or slow external services."
    if "too short" in lower:
        return "Article text was too short for meaningful analysis (often paywalled content)."
    if "api key" in lower or "401" in lower:
        return "Temporary API configuration issue. This has been addressed."
    return f"Analysis error: {error_msg[:150]}"
