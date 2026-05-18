"""
Advanced Filter Routes — Comprehensive article querying with multi-dimensional filters.

Provides endpoints for:
- Multi-criteria article filtering (country, tags, source, date range, credibility)
- Scheduled/interval-based query subscriptions
- Theme/topic exploration
- Time-series data for trend analysis
- Data coverage reporting
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user, get_optional_user

logger = setup_logging("filters")
router = APIRouter(prefix="/api/explore", tags=["Explore & Filter"])


class FilteredArticleRequest(BaseModel):
    countries: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    reliability_tier: Optional[str] = None
    content_categories: List[str] = Field(default_factory=list)
    credibility_min: Optional[int] = Field(None, ge=0, le=100)
    credibility_max: Optional[int] = Field(None, ge=0, le=100)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    keyword: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class QuerySubscription(BaseModel):
    name: str
    filters: FilteredArticleRequest
    frequency: str = Field("daily")
    notify_email: bool = False


class TimeSeriesRequest(BaseModel):
    country_code: Optional[str] = None
    tag: Optional[str] = None
    granularity: str = Field("daily")
    days: int = Field(30, ge=7, le=365)


@router.post("/articles")
async def filter_articles(request: FilteredArticleRequest):
    """Advanced multi-criteria article filtering."""
    db = get_postgres()

    conditions = ["1=1", "a.is_synthetic = FALSE"]
    params: Dict[str, Any] = {"limit": request.limit, "offset": request.offset}

    if request.countries:
        conditions.append("a.country_code = ANY(:countries)")
        params["countries"] = [c.upper() for c in request.countries]

    if request.tags:
        conditions.append("a.tags && :tags")
        params["tags"] = [t.lower() for t in request.tags]

    if request.sources:
        conditions.append("a.source_name = ANY(:sources)")
        params["sources"] = request.sources

    if request.reliability_tier and request.reliability_tier != "all":
        tier_ranges = {"scientific": (90, 100), "research": (75, 89), "public": (0, 74)}
        if request.reliability_tier in tier_ranges:
            low, high = tier_ranges[request.reliability_tier]
            conditions.append("COALESCE(a.reliability_score, 50) BETWEEN :tier_low AND :tier_high")
            params["tier_low"] = low
            params["tier_high"] = high

    if request.content_categories:
        conditions.append("a.content_category = ANY(:categories)")
        params["categories"] = [c.lower() for c in request.content_categories]

    if request.credibility_min is not None:
        conditions.append("COALESCE(a.reliability_score, 50) >= :cred_min")
        params["cred_min"] = request.credibility_min

    if request.credibility_max is not None:
        conditions.append("COALESCE(a.reliability_score, 50) <= :cred_max")
        params["cred_max"] = request.credibility_max

    if request.date_from:
        conditions.append("a.created_at >= :date_from")
        params["date_from"] = request.date_from

    if request.date_to:
        conditions.append("a.created_at <= :date_to::date + interval '1 day'")
        params["date_to"] = request.date_to

    if request.keyword:
        conditions.append("(a.title ILIKE :keyword OR a.excerpt ILIKE :keyword OR :keyword_tag = ANY(a.tags))")
        params["keyword"] = f"%{request.keyword}%"
        params["keyword_tag"] = request.keyword.lower()

    where_clause = " AND ".join(conditions)
    allowed_sorts = {"created_at", "reliability_score", "title", "source_name"}
    sort_col = request.sort_by if request.sort_by in allowed_sorts else "created_at"
    sort_dir = "ASC" if request.sort_order.lower() == "asc" else "DESC"

    try:
        count_row = db.execute_query(f"SELECT COUNT(*) as total FROM articles a WHERE {where_clause}", params)
        total = count_row[0]["total"] if count_row else 0

        rows = db.execute_query(f"""
            SELECT a.article_id, a.title, a.url, a.source_name, a.country_code,
                   a.excerpt, a.tags, a.content_category, a.reliability_score,
                   a.overall_credibility, a.claims_status, a.created_at, a.published_date,
                   (SELECT COUNT(*) FROM claims c WHERE c.article_id = a.article_id) as claim_count
            FROM articles a
            WHERE {where_clause}
            ORDER BY a.{sort_col} {sort_dir}
            LIMIT :limit OFFSET :offset
        """, params)

        return {
            "total": total,
            "limit": request.limit,
            "offset": request.offset,
            "articles": [
                {
                    "article_id": str(r["article_id"]),
                    "title": r["title"],
                    "url": r.get("url"),
                    "source_name": r.get("source_name"),
                    "country_code": r.get("country_code"),
                    "excerpt": r.get("excerpt"),
                    "tags": r.get("tags") or [],
                    "content_category": r.get("content_category"),
                    "reliability_score": r.get("reliability_score"),
                    "overall_credibility": r.get("overall_credibility"),
                    "claim_count": r.get("claim_count", 0),
                    "created_at": str(r["created_at"]) if r.get("created_at") else None,
                }
                for r in (rows or [])
            ],
        }
    except Exception as e:
        logger.error(f"Filter query failed: {e}")
        raise HTTPException(status_code=500, detail="Filter query failed")


@router.get("/topics")
async def explore_topics(country: Optional[str] = None, limit: int = Query(default=30, le=100)):
    """Get trending topics/tags across all articles."""
    db = get_postgres()
    country_filter = ""
    params: Dict[str, Any] = {"limit": limit}
    if country:
        country_filter = "AND a.country_code = :cc"
        params["cc"] = country.upper()

    try:
        rows = db.execute_query(f"""
            SELECT tag, COUNT(*) as article_count, AVG(a.reliability_score) as avg_score,
                   MAX(a.created_at) as latest
            FROM articles a, UNNEST(a.tags) as tag
            WHERE a.is_synthetic = FALSE AND a.tags IS NOT NULL {country_filter}
            GROUP BY tag ORDER BY article_count DESC LIMIT :limit
        """, params)

        return [
            {"tag": r["tag"], "article_count": r["article_count"],
             "avg_credibility": round(float(r["avg_score"]), 1) if r.get("avg_score") else None,
             "latest_article": str(r["latest"]) if r.get("latest") else None}
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Topics query failed: {e}")
        return []


@router.get("/sources")
async def explore_sources(country: Optional[str] = None, limit: int = Query(default=50, le=200)):
    """Get all sources with article counts and credibility scores."""
    db = get_postgres()
    conditions = ["a.is_synthetic = FALSE"]
    params: Dict[str, Any] = {"limit": limit}
    if country:
        conditions.append("a.country_code = :cc")
        params["cc"] = country.upper()

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    try:
        rows = db.execute_query(f"""
            SELECT a.source_name, a.source_domain, a.country_code,
                   COUNT(*) as article_count, AVG(a.reliability_score) as avg_score,
                   MAX(a.created_at) as latest_article
            FROM articles a {where}
            GROUP BY a.source_name, a.source_domain, a.country_code
            ORDER BY article_count DESC LIMIT :limit
        """, params)

        return [
            {"source_name": r["source_name"], "country_code": r.get("country_code"),
             "article_count": r["article_count"],
             "avg_credibility": round(float(r["avg_score"]), 1) if r.get("avg_score") else None}
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Sources query failed: {e}")
        return []


@router.post("/trends")
async def get_article_trends(request: TimeSeriesRequest):
    """Get article count time-series for trend visualization."""
    db = get_postgres()
    granularity_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    trunc = granularity_map.get(request.granularity, "day")

    conditions = [f"a.created_at >= NOW() - interval '{request.days} days'", "a.is_synthetic = FALSE"]
    params: Dict[str, Any] = {}

    if request.country_code:
        conditions.append("a.country_code = :cc")
        params["cc"] = request.country_code.upper()
    if request.tag:
        conditions.append(":tag = ANY(a.tags)")
        params["tag"] = request.tag.lower()

    where = " AND ".join(conditions)

    try:
        rows = db.execute_query(f"""
            SELECT DATE_TRUNC('{trunc}', a.created_at) as period,
                   COUNT(*) as article_count, AVG(a.reliability_score) as avg_score
            FROM articles a WHERE {where}
            GROUP BY period ORDER BY period ASC
        """, params)

        return [
            {"period": str(r["period"]), "article_count": r["article_count"],
             "avg_credibility": round(float(r["avg_score"]), 1) if r.get("avg_score") else None}
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Trends query failed: {e}")
        return []


@router.post("/subscriptions")
async def create_query_subscription(subscription: QuerySubscription, current_user: dict = Depends(get_current_user)):
    """Create a recurring query subscription."""
    db = get_postgres()
    try:
        result = db.execute_query(
            """INSERT INTO query_subscriptions (user_id, name, filters, frequency, notify_email)
               VALUES (:uid, :name, :filters::jsonb, :freq, :notify)
               RETURNING subscription_id, created_at""",
            {"uid": str(current_user["user_id"]), "name": subscription.name,
             "filters": json.dumps(subscription.filters.model_dump()), "freq": subscription.frequency,
             "notify": subscription.notify_email}
        )
        if result:
            return {"subscription_id": str(result[0]["subscription_id"]), "name": subscription.name,
                    "frequency": subscription.frequency, "created_at": str(result[0]["created_at"])}
        raise HTTPException(status_code=500, detail="Failed to create subscription")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscription creation failed: {e}")
        raise HTTPException(status_code=500, detail="Subscription creation failed")


@router.get("/subscriptions")
async def list_subscriptions(current_user: dict = Depends(get_current_user)):
    """List user's active query subscriptions."""
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT subscription_id, name, filters, frequency, notify_email,
                      is_active, created_at, last_run_at
               FROM query_subscriptions WHERE user_id = :uid ORDER BY created_at DESC""",
            {"uid": str(current_user["user_id"])}
        )
        return [
            {"subscription_id": str(r["subscription_id"]), "name": r["name"],
             "filters": r.get("filters") or {}, "frequency": r.get("frequency", "daily"),
             "is_active": r.get("is_active", True), "created_at": str(r["created_at"])}
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"List subscriptions failed: {e}")
        return []


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a query subscription."""
    db = get_postgres()
    db.execute_update(
        "DELETE FROM query_subscriptions WHERE subscription_id = :sid AND user_id = :uid",
        {"sid": subscription_id, "uid": str(current_user["user_id"])}
    )
    return {"status": "deleted"}


@router.get("/coverage")
async def get_data_coverage():
    """Get comprehensive data coverage report across all countries and sources."""
    db = get_postgres()
    try:
        country_rows = db.execute_query("""
            SELECT c.country_code, c.country_name, c.is_eu_member,
                   COALESCE(ac.cnt, 0) as article_count, ac.latest
            FROM countries c LEFT JOIN (
                SELECT country_code, COUNT(*) as cnt, MAX(created_at) as latest
                FROM articles WHERE is_synthetic = FALSE GROUP BY country_code
            ) ac ON ac.country_code = c.country_code
            ORDER BY COALESCE(ac.cnt, 0) DESC
        """)

        stats = db.execute_query("""
            SELECT COUNT(*) as total_articles, COUNT(DISTINCT country_code) as countries_covered,
                   COUNT(DISTINCT source_name) as sources_active, AVG(reliability_score) as avg_score
            FROM articles
            WHERE is_synthetic = FALSE
        """)

        return {
            "summary": {
                "total_articles": stats[0]["total_articles"] if stats else 0,
                "countries_covered": stats[0]["countries_covered"] if stats else 0,
                "sources_active": stats[0]["sources_active"] if stats else 0,
                "avg_credibility": round(float(stats[0]["avg_score"]), 1) if stats and stats[0].get("avg_score") else None,
            },
            "countries": [
                {"country_code": r["country_code"], "country_name": r.get("country_name", r["country_code"]),
                 "is_eu_member": r.get("is_eu_member", False), "article_count": r.get("article_count", 0)}
                for r in (country_rows or [])
            ],
        }
    except Exception as e:
        logger.error(f"Coverage report failed: {e}")
        return {"summary": {}, "countries": []}
