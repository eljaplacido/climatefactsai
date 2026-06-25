"""
Advanced Search Routes - Enhanced Search Capabilities

Provides semantic search (Premium) and saved searches functionality.
"""

from typing import Any, List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.models import Article
from api.rate_limiter import check_premium_feature
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("search-api")
router = APIRouter(prefix="/api/search", tags=["Search"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SemanticSearchRequest(BaseModel):
    """Semantic search using pgvector"""
    query: str = Field(..., min_length=3, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    country: Optional[str] = None
    credibility_level: Optional[str] = None


class SavedSearch(BaseModel):
    """Saved search configuration"""
    id: str
    user_id: str
    name: str
    query: dict
    notify_on_new: bool
    created_at: datetime
    last_executed: Optional[datetime] = None
    result_count: int = 0


class SaveSearchRequest(BaseModel):
    """Request to save a search"""
    name: str = Field(..., min_length=1, max_length=100)
    query: dict = Field(..., description="Search parameters as JSON")
    notify_on_new: bool = Field(default=False, description="Email notification for new results")


class SearchSuggestion(BaseModel):
    """Auto-complete suggestion"""
    text: str
    category: str  # tag, country, source
    count: int


# =============================================================================
# BASIC SEARCH (All Users)
# =============================================================================

@router.get("/", response_model=List[Article])
async def basic_search(
    q: str = Query(..., min_length=3, max_length=500, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    country: Optional[str] = Query(None, description="Filter by country code (e.g., FI, SE)"),
    credibility_level: Optional[str] = Query(None, description="Filter by credibility (HIGH, MEDIUM, LOW)"),
    current_user: Optional[Any] = Depends(get_optional_user)
):
    """
    Basic full-text search available to all users (including freemium).

    Searches article titles and excerpts using PostgreSQL full-text search.
    Results are ranked by relevance and publication date.

    **Example queries:**
    - `/api/search/?q=climate`
    - `/api/search/?q=renewable energy&country=FI`
    - `/api/search/?q=emissions&credibility_level=HIGH`
    """
    db = get_postgres()

    query = """
        SELECT
            a.article_id,
            a.title,
            a.url,
            a.source_name,
            a.published_date,
            a.excerpt,
            a.enriched_excerpt,
            a.climate_context_summary,
            a.enrichment_metadata,
            a.source_credibility_score,
            a.overall_credibility,
            a.country_code,
            a.tags,
            a.created_at,
            a.claims_count,
            a.verified_claims_count,
            a.content_relevance_score,
            a.reliability_score,
            a.author,
            a.extracted_text,
            ts_rank(
                to_tsvector('english', a.title || ' ' || COALESCE(a.excerpt, '')),
                plainto_tsquery('english', :query)
            ) as relevance
        FROM articles a
        WHERE a.is_synthetic = FALSE
          AND a.is_off_topic = FALSE
          AND to_tsvector('english', a.title || ' ' || COALESCE(a.excerpt, ''))
              @@ plainto_tsquery('english', :query)
    """

    params = {"query": q, "limit": limit}

    # Add filters
    if country:
        query += " AND a.country_code = :country"
        params["country"] = country

    if credibility_level:
        query += " AND a.overall_credibility = :credibility_level"
        params["credibility_level"] = credibility_level

    query += " ORDER BY relevance DESC, a.published_date DESC LIMIT :limit"

    try:
        results = db.execute_query(query, params)
        logger.info(
            "Basic search executed",
            user_id=current_user.get("user_id") if current_user and isinstance(current_user, dict) else None,
            query=q,
            result_count=len(results),
            filters={"country": country, "credibility": credibility_level}
        )
    except Exception as e:
        logger.error(
            "Basic search query failed",
            error=str(e),
            query=q
        )
        raise HTTPException(
            status_code=500,
            detail="Search query failed. Please try again."
        )

    # Convert to Article models
    from api.main import _row_to_article

    try:
        articles = [_row_to_article(row) for row in results]
        return articles
    except Exception as e:
        logger.error(
            "Failed to convert search results",
            error=str(e),
            result_count=len(results)
        )
        raise HTTPException(
            status_code=500,
            detail="Search results could not be processed."
        )


# =============================================================================
# SEMANTIC SEARCH (Premium Feature)
# =============================================================================

@router.get("/semantic", response_model=List[Article])
@router.post("/semantic", response_model=List[Article])
async def semantic_search(
    request: SemanticSearchRequest = None,
    query: Optional[str] = Query(None, min_length=3, max_length=500),
    limit: int = Query(10, ge=1, le=50),
    country: Optional[str] = Query(None),
    credibility_level: Optional[str] = Query(None),
    current_user: Any = Depends(get_current_user)
):
    """
    Semantic search using vector embeddings (Professional+ only).

    Uses pgvector to find semantically similar articles based on
    meaning rather than exact keyword matching.

    **Example:**
    - Query: "renewable energy investments"
    - Will find: "solar power funding", "wind farm financing", etc.

    Supports both GET and POST methods:
    - GET: Pass parameters as query strings
    - POST: Pass SemanticSearchRequest JSON body
    """
    # Handle both GET (query params) and POST (request body)
    if request is None:
        # GET method - use query parameters
        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query parameter is required"
            )
        request = SemanticSearchRequest(
            query=query,
            limit=limit,
            country=country,
            credibility_level=credibility_level
        )

    # Check premium feature access - handle both dict and database row object
    user_tier = current_user.get("subscription_tier") if isinstance(current_user, dict) else getattr(current_user, "subscription_tier", "freemium")

    if not check_premium_feature(user_tier, "semantic_search"):
        raise HTTPException(
            status_code=403,
            detail="Semantic search requires Professional or Enterprise subscription"
        )

    db = get_postgres()

    # Generate the query embedding with bge-m3 — the LIVE column (2026-06-11
    # audit, semantic split-brain). The old ada-002 OpenAI embed matched the
    # EMPTY `embedding` column, so it spent on OpenAI and still degraded to FTS.
    # On Cloud Run the GX10 endpoint is unreachable, so this returns None and we
    # fall back to FTS — but without the wasted ada-002 call.
    query_embedding = None
    try:
        from app.domains.content.embedding_service import EmbeddingService
        query_embedding = await EmbeddingService(db).generate_bge_m3_embedding(
            request.query[:8000]
        )
    except Exception as emb_err:
        logger.warning(f"bge-m3 query embedding failed, falling back to FTS: {emb_err}")

    if query_embedding:
        # Hybrid search: 0.6 semantic + 0.4 FTS
        vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query_sql = """
            WITH semantic AS (
                SELECT article_id,
                       1 - (embedding_bge_m3 <=> :embedding::vector) AS sem_score
                FROM articles
                WHERE is_synthetic = FALSE
                  AND is_off_topic = FALSE
                  AND embedding_bge_m3 IS NOT NULL
            ),
            fts AS (
                SELECT article_id,
                       ts_rank(
                           to_tsvector('english', title || ' ' || COALESCE(excerpt, '')),
                           plainto_tsquery('english', :query)
                       ) AS fts_score
                FROM articles
                WHERE is_synthetic = FALSE
                  AND is_off_topic = FALSE
                  AND to_tsvector('english', title || ' ' || COALESCE(excerpt, ''))
                      @@ plainto_tsquery('english', :query)
            )
            SELECT
                a.article_id, a.title, a.url, a.source_name,
                a.published_date, a.excerpt, a.enriched_excerpt,
                a.climate_context_summary, a.enrichment_metadata,
                a.source_credibility_score,
                a.overall_credibility, a.country_code, a.tags,
                a.created_at, a.claims_count, a.verified_claims_count,
                a.content_relevance_score, a.reliability_score,
                a.author, a.extracted_text,
                COALESCE(0.6 * s.sem_score, 0) + COALESCE(0.4 * f.fts_score, 0) AS relevance
            FROM articles a
            LEFT JOIN semantic s ON a.article_id = s.article_id
            LEFT JOIN fts f ON a.article_id = f.article_id
            WHERE a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
              AND (s.sem_score IS NOT NULL OR f.fts_score IS NOT NULL)
        """
        params = {"embedding": vector_str, "query": request.query, "limit": request.limit}

        if request.country:
            query_sql += " AND a.country_code = :country"
            params["country"] = request.country
        if request.credibility_level:
            query_sql += " AND a.overall_credibility = :credibility_level"
            params["credibility_level"] = request.credibility_level

        query_sql += " ORDER BY relevance DESC LIMIT :limit"
    else:
        # Fallback to pure FTS
        query_sql = """
            SELECT
                a.article_id, a.title, a.url, a.source_name,
                a.published_date, a.excerpt, a.source_credibility_score,
                a.overall_credibility, a.country_code, a.tags,
                a.created_at, a.claims_count, a.verified_claims_count,
                a.content_relevance_score, a.reliability_score,
                a.author, a.extracted_text,
                ts_rank(
                    to_tsvector('english', a.title || ' ' || COALESCE(a.excerpt, '')),
                    plainto_tsquery('english', :query)
                ) as relevance
            FROM articles a
            WHERE a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
              AND to_tsvector('english', a.title || ' ' || COALESCE(a.excerpt, ''))
                  @@ plainto_tsquery('english', :query)
        """
        params = {"query": request.query, "limit": request.limit}

        if request.country:
            query_sql += " AND a.country_code = :country"
            params["country"] = request.country
        if request.credibility_level:
            query_sql += " AND a.overall_credibility = :credibility_level"
            params["credibility_level"] = request.credibility_level

        query_sql += " ORDER BY relevance DESC, a.published_date DESC LIMIT :limit"

    try:
        results = db.execute_query(query_sql, params)
        logger.info(
            "Semantic search executed",
            user_id=current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None),
            query=request.query,
            result_count=len(results),
            filters={"country": request.country, "credibility": request.credibility_level}
        )
    except Exception as e:
        logger.error(
            "Semantic search query failed",
            error=str(e),
            query=request.query,
            user_id=current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "user_id", None)
        )
        raise HTTPException(
            status_code=500,
            detail="Search query failed. Please try again or contact support."
        )

    # Convert to Article models using the correct helper function
    from api.main import _row_to_article

    try:
        articles = [_row_to_article(row) for row in results]
        logger.info(
            "Semantic search completed successfully",
            articles_returned=len(articles),
            query=request.query
        )
    except Exception as e:
        logger.error(
            "Failed to convert search results to Article models",
            error=str(e),
            result_count=len(results)
        )
        raise HTTPException(
            status_code=500,
            detail="Search results could not be processed. Please contact support."
        )

    return articles


# =============================================================================
# SAVED SEARCHES (Basic+ Feature)
# =============================================================================

@router.post("/save", response_model=SavedSearch)
async def save_search(
    request: SaveSearchRequest,
    current_user: Any = Depends(get_current_user)
):
    """
    Save a search for later reuse (Basic+ only).

    Allows users to save complex search queries and optionally
    receive notifications when new matching articles are published.
    """
    # Check premium feature access
    if not check_premium_feature(current_user.get('subscription_tier'), "saved_searches"):
        raise HTTPException(
            status_code=403,
            detail="Saved searches require Basic, Professional, or Enterprise subscription"
        )

    db = get_postgres()
    search_id = str(uuid4())

    try:
        # Store saved search
        db.execute_update(
            """
            INSERT INTO user_preferences (
                user_id, preference_key, preference_value, created_at, updated_at
            ) VALUES (:user_id, :key, :value, NOW(), NOW())
            """,
            {
                "user_id": current_user['user_id'],
                "key": f"saved_search_{search_id}",
                "value": {
                    "id": search_id,
                    "name": request.name,
                    "query": request.query,
                    "notify_on_new": request.notify_on_new
                }
            }
        )

        logger.info(f"Search saved: {search_id} by user {current_user['user_id']}")

        return SavedSearch(
            id=search_id,
            user_id=current_user['user_id'],
            name=request.name,
            query=request.query,
            notify_on_new=request.notify_on_new,
            created_at=datetime.utcnow(),
            last_executed=None,
            result_count=0
        )

    except Exception as e:
        logger.error(f"Error saving search: {e}")
        raise HTTPException(status_code=500, detail="Failed to save search")


@router.get("/saved", response_model=List[SavedSearch])
async def get_saved_searches(
    current_user: Any = Depends(get_current_user)
):
    """
    Get user's saved searches.

    Returns all saved search configurations for the current user.
    """
    # Check premium feature access
    if not check_premium_feature(current_user.get('subscription_tier'), "saved_searches"):
        raise HTTPException(
            status_code=403,
            detail="Saved searches require Basic, Professional, or Enterprise subscription"
        )

    db = get_postgres()

    results = db.execute_query(
        """
        SELECT
            preference_key,
            preference_value,
            created_at,
            updated_at
        FROM user_preferences
        WHERE user_id = :user_id
          AND preference_key LIKE 'saved_search_%'
        ORDER BY created_at DESC
        """,
        {"user_id": current_user['user_id']}
    )

    saved_searches = []
    for row in results:
        value = row["preference_value"]
        if isinstance(value, dict):
            saved_searches.append(SavedSearch(
                id=value.get("id", ""),
                user_id=current_user['user_id'],
                name=value.get("name", "Untitled"),
                query=value.get("query", {}),
                notify_on_new=value.get("notify_on_new", False),
                created_at=row["created_at"],
                last_executed=row.get("updated_at"),
                result_count=value.get("result_count", 0)
            ))

    return saved_searches


@router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: str,
    current_user: Any = Depends(get_current_user)
):
    """
    Delete a saved search.

    Only the owner can delete their saved searches.
    """
    db = get_postgres()

    result = db.execute_update(
        """
        DELETE FROM user_preferences
        WHERE user_id = :user_id AND preference_key = :key
        """,
        {"user_id": current_user['user_id'], "key": f"saved_search_{search_id}"}
    )

    logger.info(f"Saved search {search_id} deleted by user {current_user['user_id']}")

    return {"message": "Saved search deleted successfully"}


# =============================================================================
# SEARCH SUGGESTIONS (All Users)
# =============================================================================

@router.get("/suggestions", response_model=List[SearchSuggestion])
async def get_search_suggestions(
    q: str = Query(..., min_length=2, max_length=50, description="Query prefix"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=20),
    current_user: Optional[Any] = Depends(get_optional_user)
):
    """
    Get auto-complete suggestions for search.

    Returns suggestions based on:
    - Popular tags
    - Countries
    - News sources
    - Past search terms (if authenticated)
    """
    db = get_postgres()
    suggestions = []

    # Get tag suggestions
    if not category or category == "tag":
        tag_results = db.execute_query(
            """
            SELECT tag, COUNT(*) as count
            FROM articles, UNNEST(tags) as tag
            WHERE is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND tag ILIKE :pattern
            GROUP BY tag
            ORDER BY count DESC
            LIMIT :limit
            """,
            {"pattern": f"%{q}%", "limit": limit}
        )

        for row in tag_results:
            suggestions.append(SearchSuggestion(
                text=row["tag"],
                category="tag",
                count=row["count"]
            ))

    # Get country suggestions
    if not category or category == "country":
        country_results = db.execute_query(
            """
            SELECT country_code, COUNT(*) as count
            FROM articles
            WHERE is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND country_code ILIKE :pattern
            GROUP BY country_code
            ORDER BY count DESC
            LIMIT :limit
            """,
            {"pattern": f"%{q}%", "limit": limit}
        )

        for row in country_results:
            if row["country_code"]:
                suggestions.append(SearchSuggestion(
                    text=row["country_code"],
                    category="country",
                    count=row["count"]
                ))

    # Get source suggestions
    if not category or category == "source":
        source_results = db.execute_query(
            """
            SELECT source_name, COUNT(*) as count
            FROM articles
            WHERE is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND source_name ILIKE :pattern
            GROUP BY source_name
            ORDER BY count DESC
            LIMIT :limit
            """,
            {"pattern": f"%{q}%", "limit": limit}
        )

        for row in source_results:
            if row["source_name"]:
                suggestions.append(SearchSuggestion(
                    text=row["source_name"],
                    category="source",
                    count=row["count"]
                ))

    # Sort by count and limit
    suggestions.sort(key=lambda x: x.count, reverse=True)
    return suggestions[:limit]


@router.get("/history")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[Any] = Depends(get_optional_user)
):
    """
    Get user's recent search history.

    Returns list of recent search queries with timestamps.
    """
    # If unauthenticated, return empty history (client can fallback to local)
    if not current_user:
        return []

    db = get_postgres()

    results = db.execute_query(
        """
        SELECT action, metadata, created_at
        FROM user_usage
        WHERE user_id = :user_id
          AND feature = 'search'
        ORDER BY created_at DESC
        LIMIT :limit
        """,
        {"user_id": current_user['user_id'], "limit": limit}
    )

    history = []
    for row in results:
        metadata = row.get("metadata", {})
        if isinstance(metadata, dict):
            history.append({
                "query": metadata.get("query", ""),
                "filters": metadata.get("filters", {}),
                "result_count": metadata.get("result_count", 0),
                "timestamp": row["created_at"]
            })

    return history
