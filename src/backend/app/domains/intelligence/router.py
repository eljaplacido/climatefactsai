"""
Intelligence Domain Router

Admin endpoints for triggering and monitoring fact-checking.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status

from app.core.database import Database, get_db
from .services import VerificationService
from .schemas import VerificationResult, ClaimExtractionRequest
from .analysis_engine import AnalysisEngine

# Auth dependency for gating the monetizable insights endpoint. Imported from
# the api package (no cycle: auth_routes does not import this domain router).
# Supports both JWT bearer tokens and X-API-Key (the future paid-API channel).
from api.auth_routes import get_optional_user

router = APIRouter(prefix="/api/v2/intelligence", tags=["Intelligence"])


# Dependency injection
def get_verification_service(db: Database = Depends(get_db)) -> VerificationService:
    """Get VerificationService instance."""
    return VerificationService(db)


VerificationServiceDep = Annotated[VerificationService, Depends(get_verification_service)]


def get_analysis_engine(db: Database = Depends(get_db)) -> AnalysisEngine:
    """Get AnalysisEngine instance."""
    return AnalysisEngine(db)


AnalysisEngineDep = Annotated[AnalysisEngine, Depends(get_analysis_engine)]


@router.post("/verify/{article_id}", response_model=VerificationResult)
async def verify_article(
    article_id: UUID,
    background_tasks: BackgroundTasks,
    service: VerificationServiceDep = None,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Trigger fact-checking verification for an article.

    This will:
    1. Extract atomic claims from the article
    2. Retrieve evidence from trusted sources
    3. Adjudicate each claim
    4. Calculate overall article credibility

    **Processing time**: 30-60 seconds for typical article

    Gated + metered through QuotaService (insights_extraction) — this runs the
    full LLM pipeline, so it was previously an unauthenticated cost sink.
    """
    from api.quota_service import QuotaService

    user_id = str(current_user["user_id"]) if current_user else None
    tier = (current_user or {}).get("subscription_tier")
    QuotaService.check_and_raise(user_id, tier, "insights_extraction")

    result = await service.verify_article(article_id)

    try:
        QuotaService.consume(user_id, "insights_extraction")
    except Exception:
        pass

    return result


@router.post("/verify-batch")
async def verify_batch(
    article_ids: list[UUID],
    background_tasks: BackgroundTasks,
    service: VerificationServiceDep = None
):
    """
    Trigger verification for multiple articles (admin only).
    
    Processes articles in background and returns immediately.
    
    **Example:**
    ```json
    POST /api/v2/intelligence/verify-batch
    {
      "article_ids": ["uuid1", "uuid2", "uuid3"]
    }
    ```
    """
    if len(article_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 articles per batch"
        )
    
    # Queue each verification
    for article_id in article_ids:
        background_tasks.add_task(service.verify_article, article_id)
    
    return {
        "status": "queued",
        "articles_count": len(article_ids),
        "message": f"Verification queued for {len(article_ids)} articles"
    }


@router.get("/verification-status/{article_id}")
async def get_verification_status(
    article_id: UUID,
    db: Database = Depends(get_db)
):
    """
    Get verification status for an article.
    
    Returns claim counts and credibility scores.
    """
    results = db.execute_query(
        """
        SELECT
            claims_count,
            verified_claims_count,
            reliability_score,
            overall_credibility
        FROM articles
        WHERE article_id = :article_id
        """,
        {"article_id": str(article_id)}
    )
    
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found"
        )
    
    data = results[0]
    
    return {
        "article_id": article_id,
        "claims_extracted": data["claims_count"] or 0,
        "claims_verified": data["verified_claims_count"] or 0,
        "reliability_score": data["reliability_score"],
        "credibility_level": data["overall_credibility"],
        "verification_complete": (data["claims_count"] or 0) > 0
    }


@router.get("/insights/{article_id}")
async def get_article_insights(
    article_id: UUID,
    engine: AnalysisEngineDep = None,
):
    """
    Get pre-computed analysis insights for an article.

    Returns decomposed confidence, claims breakdown, and AI-generated summary.
    """
    insights = await engine.get_article_insights(article_id)
    if not insights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found",
        )
    return insights


@router.post("/analyze-text")
async def analyze_text(
    request: ClaimExtractionRequest,
    engine: AnalysisEngineDep = None,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Analyze raw text without storing results.

    Extracts and classifies claims, returning structured breakdown — the same
    LLM-backed insights-extraction capability sold via the API. Gated + metered
    on the `insights_extraction` quota (anonymous=0 → sign in required;
    free=50 lifetime test calls; paid tiers scale up). This stops the endpoint
    from being an unauthenticated LLM-cost sink that also gave the product away.
    """
    # Lazy import keeps the api.quota_service dependency out of this domain
    # module's import-time graph (avoids any startup-order coupling).
    from api.quota_service import QuotaService

    user_id = str(current_user["user_id"]) if current_user else None
    tier = (current_user or {}).get("subscription_tier")
    QuotaService.check_and_raise(user_id, tier, "insights_extraction")

    result = await engine.analyze_text(
        text=request.text,
        max_claims=request.max_claims,
    )

    # Meter the successful call (lifetime usage event). Best-effort.
    try:
        QuotaService.consume(user_id, "insights_extraction")
    except Exception:
        pass

    return result


@router.post("/full-analysis/{article_id}")
async def run_full_analysis(
    article_id: UUID,
    engine: AnalysisEngineDep = None,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Run complete analysis pipeline on an article.

    Combines verification, reliability scoring, and insight generation.
    Gated + metered through QuotaService (insights_extraction) — it runs the
    full multi-LLM pipeline and was previously unauthenticated/unmetered.
    """
    from api.quota_service import QuotaService

    user_id = str(current_user["user_id"]) if current_user else None
    tier = (current_user or {}).get("subscription_tier")
    QuotaService.check_and_raise(user_id, tier, "insights_extraction")

    result = await engine.full_analysis(article_id)

    try:
        QuotaService.consume(user_id, "insights_extraction")
    except Exception:
        pass

    return result

