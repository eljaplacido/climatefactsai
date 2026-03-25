"""
Similarity routes - Find articles similar to a given article using pgvector.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging
from app.domains.content.embedding_service import EmbeddingService

logger = setup_logging("similarity-api")
router = APIRouter(prefix="/api/articles", tags=["Similarity"])


class SimilarArticleResponse(BaseModel):
    article_id: str
    title: str
    source_name: str
    similarity_score: float
    published_date: Optional[str] = None
    overall_credibility: str = "UNKNOWN"


@router.get("/{article_id}/similar", response_model=List[SimilarArticleResponse])
async def get_similar_articles(
    article_id: str,
    limit: int = Query(5, ge=1, le=20),
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Find articles similar to the given article using vector embeddings.

    Uses pgvector cosine similarity to find semantically related articles.
    Returns up to `limit` similar articles sorted by similarity score.
    """
    db = get_postgres()
    service = EmbeddingService(db)

    try:
        similar = await service.find_similar(
            article_id=article_id,
            limit=limit,
        )
        return [SimilarArticleResponse(**s) for s in similar]
    except Exception as e:
        logger.error(f"Similar articles lookup failed for {article_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve similar articles."
        )
