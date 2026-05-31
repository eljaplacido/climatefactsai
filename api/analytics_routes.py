"""
Advanced analytics API endpoints for Climatefacts.ai dashboard.

Provides trend analysis, source performance, claim category breakdowns,
verification pipeline status, and time-series data.
"""

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shared.database import get_postgres
from api.auth_routes import get_optional_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_db():
    return get_postgres()


# Admin email allowlist — mirrors api/admin_pipeline_routes.py so the same
# operators gate every admin surface. Comma-separated emails in ADMIN_EMAILS.
ADMIN_EMAILS = set(filter(None, os.environ.get("ADMIN_EMAILS", "").split(",")))


def require_analytics_admin(current_user: Optional[dict] = Depends(get_optional_user)) -> dict:
    """Gate the analytics dashboard to admins only.

    These endpoints expose platform-wide aggregates (country distribution,
    verdict distribution, pipeline health) that must NOT be public — they
    reveal ingestion bias and verification-yield internals. Mirrors the
    `/api/admin/dashboard` pattern: anonymous → 401, non-admin → 403.

    Admin = subscription_tier == 'enterprise' OR email in ADMIN_EMAILS.
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for analytics access",
        )
    tier = current_user.get("subscription_tier", "")
    email = current_user.get("email", "")
    if tier != "enterprise" and email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Enterprise subscription or admin privileges needed.",
        )
    return current_user


# --- Response Models ---

class ArticleTrend(BaseModel):
    date: str
    articles_ingested: int = 0
    articles_verified: int = 0
    articles_failed: int = 0


class ClaimCategoryBreakdown(BaseModel):
    category: str
    count: int = 0
    verified: int = 0
    disputed: int = 0
    unverified: int = 0
    avg_confidence: float = 0.0


class SourcePerformance(BaseModel):
    source_name: str
    source_domain: Optional[str] = None
    total_articles: int = 0
    total_claims: int = 0
    verified_claims: int = 0
    disputed_claims: int = 0
    avg_credibility: float = 0.0
    false_claim_rate: float = 0.0


class VerificationVerdictDistribution(BaseModel):
    verified: int = 0
    disputed: int = 0
    partially_true: int = 0
    unverified: int = 0
    total: int = 0


class CountryArticleStats(BaseModel):
    country_code: str
    country_name: Optional[str] = None
    article_count: int = 0
    verified_count: int = 0
    avg_credibility: float = 0.0


class PipelineStatus(BaseModel):
    total_articles: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    ingested_today: int = 0
    verified_today: int = 0
    verification_rate: float = 0.0
    avg_processing_time_hours: Optional[float] = None


class AnalyticsDashboard(BaseModel):
    pipeline: PipelineStatus
    verdict_distribution: VerificationVerdictDistribution
    trends_7d: List[ArticleTrend]
    top_sources: List[SourcePerformance]
    claim_categories: List[ClaimCategoryBreakdown]
    country_stats: List[CountryArticleStats]
    generated_at: str


# --- Endpoints ---

@router.get("/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard(db=Depends(get_db), _admin: dict = Depends(require_analytics_admin)):
    """Full analytics dashboard — aggregates all analytics in one call."""
    try:
        pipeline = _get_pipeline_status(db)
        verdicts = _get_verdict_distribution(db)
        trends = _get_article_trends(db, days=7)
        sources = _get_top_sources(db, limit=10)
        categories = _get_claim_categories(db)
        countries = _get_country_stats(db, limit=15)

        return AnalyticsDashboard(
            pipeline=pipeline,
            verdict_distribution=verdicts,
            trends_7d=trends,
            top_sources=sources,
            claim_categories=categories,
            country_stats=countries,
            generated_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {exc}")


@router.get("/pipeline", response_model=PipelineStatus)
async def get_pipeline_status(db=Depends(get_db), _admin: dict = Depends(require_analytics_admin)):
    """Current verification pipeline status."""
    try:
        return _get_pipeline_status(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/trends", response_model=List[ArticleTrend])
async def get_trends(
    days: int = Query(default=30, ge=1, le=90),
    db=Depends(get_db),
    _admin: dict = Depends(require_analytics_admin),
):
    """Article ingestion and verification trends over time."""
    try:
        return _get_article_trends(db, days=days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sources", response_model=List[SourcePerformance])
async def get_source_performance(
    limit: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="total_articles", pattern=r"^(total_articles|avg_credibility|false_claim_rate)$"),
    db=Depends(get_db),
    _admin: dict = Depends(require_analytics_admin),
):
    """Source performance rankings."""
    try:
        return _get_top_sources(db, limit=limit, sort_by=sort_by)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/claims", response_model=List[ClaimCategoryBreakdown])
async def get_claim_categories(db=Depends(get_db), _admin: dict = Depends(require_analytics_admin)):
    """Claim category breakdown with verification stats."""
    try:
        return _get_claim_categories(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/verdicts", response_model=VerificationVerdictDistribution)
async def get_verdict_distribution(db=Depends(get_db), _admin: dict = Depends(require_analytics_admin)):
    """Distribution of verification verdicts."""
    try:
        return _get_verdict_distribution(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/countries", response_model=List[CountryArticleStats])
async def get_country_analytics(
    limit: int = Query(default=20, ge=1, le=50),
    db=Depends(get_db),
    _admin: dict = Depends(require_analytics_admin),
):
    """Per-country article and verification statistics."""
    try:
        return _get_country_stats(db, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --- Internal Query Functions ---

def _safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return round(float(val), 3)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_pipeline_status(db) -> PipelineStatus:
    rows = db.execute_query(
        """
        SELECT
            COUNT(*) AS total_articles,
            COUNT(*) FILTER (WHERE claims_status IS NULL OR claims_status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE claims_status = 'processing') AS processing,
            COUNT(*) FILTER (WHERE claims_status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE claims_status = 'failed') AS failed,
            COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS ingested_today,
            COUNT(*) FILTER (WHERE DATE(claims_processed_at) = CURRENT_DATE) AS verified_today,
            AVG(
                EXTRACT(EPOCH FROM (claims_processed_at - created_at)) / 3600.0
            ) FILTER (WHERE claims_processed_at IS NOT NULL) AS avg_processing_hours
        FROM articles
        WHERE is_synthetic = FALSE
        """,
        {},
    )
    r = rows[0] if rows else {}
    total = _safe_int(r.get("total_articles"))
    completed = _safe_int(r.get("completed"))

    return PipelineStatus(
        total_articles=total,
        pending=_safe_int(r.get("pending")),
        processing=_safe_int(r.get("processing")),
        completed=completed,
        failed=_safe_int(r.get("failed")),
        ingested_today=_safe_int(r.get("ingested_today")),
        verified_today=_safe_int(r.get("verified_today")),
        verification_rate=round(completed / total, 3) if total > 0 else 0.0,
        avg_processing_time_hours=_safe_float(r.get("avg_processing_hours")) or None,
    )


def _get_verdict_distribution(db) -> VerificationVerdictDistribution:
    rows = db.execute_query(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE UPPER(verification_status) IN ('VERIFIED', 'TRUE')) AS verified,
            COUNT(*) FILTER (WHERE UPPER(verification_status) IN ('DISPUTED', 'FALSE')) AS disputed,
            COUNT(*) FILTER (WHERE UPPER(verification_status) = 'PARTIALLY_TRUE') AS partially_true,
            COUNT(*) FILTER (WHERE UPPER(verification_status) IN ('UNVERIFIED', 'UNKNOWN')) AS unverified
        FROM fact_checks
        """,
        {},
    )
    r = rows[0] if rows else {}
    return VerificationVerdictDistribution(
        total=_safe_int(r.get("total")),
        verified=_safe_int(r.get("verified")),
        disputed=_safe_int(r.get("disputed")),
        partially_true=_safe_int(r.get("partially_true")),
        unverified=_safe_int(r.get("unverified")),
    )


def _get_article_trends(db, days: int = 7) -> List[ArticleTrend]:
    rows = db.execute_query(
        """
        SELECT
            d.day::text AS date,
            COUNT(a.article_id) FILTER (WHERE a.article_id IS NOT NULL) AS articles_ingested,
            COUNT(a.article_id) FILTER (WHERE a.claims_status = 'completed') AS articles_verified,
            COUNT(a.article_id) FILTER (WHERE a.claims_status = 'failed') AS articles_failed
        FROM generate_series(
            CURRENT_DATE - INTERVAL '1 day' * :days,
            CURRENT_DATE,
            '1 day'
        ) AS d(day)
        LEFT JOIN articles a ON DATE(a.created_at) = d.day
        GROUP BY d.day
        ORDER BY d.day
        """,
        {"days": days},
    )

    return [
        ArticleTrend(
            date=str(r.get("date", "")),
            articles_ingested=_safe_int(r.get("articles_ingested")),
            articles_verified=_safe_int(r.get("articles_verified")),
            articles_failed=_safe_int(r.get("articles_failed")),
        )
        for r in rows
    ]


def _get_top_sources(db, limit: int = 10, sort_by: str = "total_articles") -> List[SourcePerformance]:
    order_col = {
        "total_articles": "total_articles DESC",
        "avg_credibility": "avg_credibility DESC",
        "false_claim_rate": "false_claim_rate ASC",
    }.get(sort_by, "total_articles DESC")

    rows = db.execute_query(
        f"""
        WITH source_claims AS (
            SELECT
                a.source_name,
                COUNT(DISTINCT a.article_id) AS total_articles,
                COUNT(c.claim_id) AS total_claims,
                COUNT(c.claim_id) FILTER (
                    WHERE fc.verification_status IN ('VERIFIED', 'verified', 'true')
                ) AS verified_claims,
                COUNT(c.claim_id) FILTER (
                    WHERE fc.verification_status IN ('DISPUTED', 'disputed', 'false')
                ) AS disputed_claims,
                AVG(fc.confidence_score) AS avg_credibility
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.is_synthetic = FALSE AND a.source_name IS NOT NULL AND a.source_name != ''
            GROUP BY a.source_name
            HAVING COUNT(DISTINCT a.article_id) >= 1
        )
        SELECT
            source_name,
            total_articles,
            total_claims,
            verified_claims,
            disputed_claims,
            COALESCE(avg_credibility, 0) AS avg_credibility,
            CASE WHEN total_claims > 0
                THEN ROUND(disputed_claims::numeric / total_claims, 3)
                ELSE 0
            END AS false_claim_rate
        FROM source_claims
        ORDER BY {order_col}
        LIMIT :limit
        """,
        {"limit": limit},
    )

    return [
        SourcePerformance(
            source_name=r.get("source_name", "Unknown"),
            total_articles=_safe_int(r.get("total_articles")),
            total_claims=_safe_int(r.get("total_claims")),
            verified_claims=_safe_int(r.get("verified_claims")),
            disputed_claims=_safe_int(r.get("disputed_claims")),
            avg_credibility=_safe_float(r.get("avg_credibility")),
            false_claim_rate=_safe_float(r.get("false_claim_rate")),
        )
        for r in rows
    ]


def _get_claim_categories(db) -> List[ClaimCategoryBreakdown]:
    rows = db.execute_query(
        """
        SELECT
            COALESCE(c.claim_category, 'uncategorized') AS category,
            COUNT(*) AS count,
            COUNT(*) FILTER (WHERE fc.verification_status IN ('VERIFIED', 'verified', 'true')) AS verified,
            COUNT(*) FILTER (WHERE fc.verification_status IN ('DISPUTED', 'disputed', 'false')) AS disputed,
            COUNT(*) FILTER (
                WHERE fc.verification_status IS NULL
                   OR fc.verification_status IN ('UNVERIFIED', 'unverified', 'unknown')
            ) AS unverified,
            AVG(fc.confidence_score) AS avg_confidence
        FROM claims c
        LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
        GROUP BY COALESCE(c.claim_category, 'uncategorized')
        ORDER BY count DESC
        """,
        {},
    )

    return [
        ClaimCategoryBreakdown(
            category=r.get("category", "uncategorized"),
            count=_safe_int(r.get("count")),
            verified=_safe_int(r.get("verified")),
            disputed=_safe_int(r.get("disputed")),
            unverified=_safe_int(r.get("unverified")),
            avg_confidence=_safe_float(r.get("avg_confidence")),
        )
        for r in rows
    ]


def _get_country_stats(db, limit: int = 15) -> List[CountryArticleStats]:
    rows = db.execute_query(
        """
        SELECT
            a.country_code,
            c.country_name,
            COUNT(DISTINCT a.article_id) AS article_count,
            COUNT(DISTINCT a.article_id) FILTER (WHERE a.claims_status = 'completed') AS verified_count,
            AVG(fc.confidence_score) AS avg_credibility
        FROM articles a
        LEFT JOIN countries c ON c.country_code = a.country_code
        LEFT JOIN claims cl ON cl.article_id = a.article_id
        LEFT JOIN fact_checks fc ON fc.claim_id = cl.claim_id
        WHERE a.is_synthetic = FALSE AND a.country_code IS NOT NULL
        GROUP BY a.country_code, c.country_name
        ORDER BY article_count DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    return [
        CountryArticleStats(
            country_code=r.get("country_code", "XX"),
            country_name=r.get("country_name"),
            article_count=_safe_int(r.get("article_count")),
            verified_count=_safe_int(r.get("verified_count")),
            avg_credibility=_safe_float(r.get("avg_credibility")),
        )
        for r in rows
    ]
