"""
Content Domain Router

Thin FastAPI router that delegates to domain services.
"""

from typing import Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

from app.core.database import Database, get_db
from .services import ArticleService, ArticleNotFoundError
from .models import Article, ArticleDetail, TagStat
from .source_profiles import SourceProfileService

router = APIRouter(prefix="/api/v2", tags=["Content"])


# Dependency injection
def get_article_service(db: Database = Depends(get_db)) -> ArticleService:
    """Get ArticleService instance."""
    return ArticleService(db)


ArticleServiceDep = Annotated[ArticleService, Depends(get_article_service)]


def get_source_profile_service(db: Database = Depends(get_db)) -> SourceProfileService:
    """Get SourceProfileService instance."""
    return SourceProfileService(db)


SourceProfileServiceDep = Annotated[SourceProfileService, Depends(get_source_profile_service)]


@router.get("/articles", response_model=list[Article])
async def list_articles(
    q: Optional[str] = Query(None, description="Search query"),
    country: Optional[str] = Query(None, description="Country code (e.g., US, FI)"),
    credibility: Optional[str] = Query(None, description="Credibility level: high, medium, low"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    service: ArticleServiceDep = None
):
    """
    List and search articles.
    
    Supports full-text search and filtering by country, credibility, and tags.
    
    **Example:**
    ```
    GET /api/v2/articles?q=solar&country=US&credibility=high&limit=10
    ```
    """
    # Parse tags
    tag_list = tags.split(',') if tags else None
    
    articles = service.search_articles(
        query=q,
        country=country,
        credibility=credibility,
        tags=tag_list,
        limit=limit,
        offset=offset
    )
    
    return articles


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def get_article_detail(
    article_id: UUID,
    service: ArticleServiceDep = None
):
    """
    Get article with full content, claims, and fact-checks.
    
    **Example:**
    ```
    GET /api/v2/articles/550e8400-e29b-41d4-a716-446655440000
    ```
    """
    try:
        article = service.get_article_detail(article_id)
        return article
    except ArticleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found"
        )


@router.get("/tags", response_model=list[TagStat])
async def get_popular_tags(
    limit: int = Query(50, ge=1, le=100, description="Max tags to return"),
    service: ArticleServiceDep = None
):
    """
    Get popular tags with article counts.
    
    **Example:**
    ```
    GET /api/v2/tags?limit=20
    ```
    """
    return service.get_popular_tags(limit=limit)


@router.get("/stats")
async def get_platform_stats(
    service: ArticleServiceDep = None
):
    """
    Get platform-wide statistics.
    
    Returns aggregate counts for articles, claims, and fact-checks.
    
    **Example:**
    ```
    GET /api/v2/stats
    ```
    """
    return service.get_platform_stats()


@router.get("/sources")
async def list_source_profiles(
    limit: int = Query(50, ge=1, le=200, description="Max sources to return"),
    min_credibility: Optional[int] = Query(None, ge=0, le=100, description="Minimum credibility score"),
    source_type: Optional[str] = Query(None, description="Source type filter"),
    service: SourceProfileServiceDep = None,
):
    """
    List source profiles with trust metadata.

    Returns source credibility, editorial standards, and historical stats.
    """
    return service.list_profiles(
        limit=limit,
        min_credibility=min_credibility,
        source_type=source_type,
    )


@router.get("/sources/{source_domain}")
async def get_source_profile(
    source_domain: str,
    service: SourceProfileServiceDep = None,
):
    """
    Get source trust profile by domain.

    Returns credibility metrics, editorial standards, and historical reliability.
    """
    profile = service.get_profile_by_domain(source_domain)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source profile for '{source_domain}' not found",
        )
    return profile


@router.get("/sources/by-name/{source_name}")
async def get_source_profile_by_name(
    source_name: str,
    service: SourceProfileServiceDep = None,
):
    """
    Get source trust profile by name.
    """
    profile = service.get_profile_by_name(source_name)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source profile for '{source_name}' not found",
        )
    return profile

