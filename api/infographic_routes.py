"""
Infographic Routes — SVG infographic generation for articles.

Generates visual summary cards, claim breakdowns, and confidence radar
infographics. Available to all tiers as a core UX element.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("infographic-api")
router = APIRouter(prefix="/api/articles", tags=["Infographics"])


@router.get("/{article_id}/infographic")
async def get_article_infographic(
    article_id: str,
    template: str = Query("summary", description="Template: summary, claims, confidence"),
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Generate an SVG infographic for an article.

    Templates:
    - summary: Overview card with title, score, and key metrics
    - claims: Claim verification breakdown
    - confidence: Confidence radar chart
    """
    # Infographics are a core UX element available to all tiers

    # Try cache
    try:
        from app.core.redis_client import get_redis
        redis = get_redis()
        cache_key = f"infographic:{article_id}:{template}"
        cached = redis.get(cache_key)
        if cached:
            return Response(content=cached, media_type="image/svg+xml")
    except Exception:
        pass

    db = get_postgres()
    rows = db.execute_query(
        """SELECT title, reliability_score, source_name, content_category,
                  claims_count, verified_claims_count, overall_credibility, executive_brief
           FROM articles WHERE article_id = :id AND is_synthetic = FALSE""",
        {"id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    row = rows[0]

    from app.domains.content.infographic_generator import generate_article_infographic
    svg = generate_article_infographic(
        article_data={
            "title": row.get("title", "Untitled"),
            "score": row.get("reliability_score") or 0,
            "source_name": row.get("source_name", "Unknown"),
            "category": row.get("content_category"),
            "claim_count": row.get("claims_count", 0),
            "verified_count": row.get("verified_claims_count", 0),
            "credibility": row.get("overall_credibility", "UNKNOWN"),
            "brief": row.get("executive_brief"),
        },
        template=template,
    )

    # Cache
    try:
        from app.core.redis_client import get_redis
        redis = get_redis()
        redis.setex(f"infographic:{article_id}:{template}", 86400, svg)
    except Exception:
        pass

    return Response(content=svg, media_type="image/svg+xml")
