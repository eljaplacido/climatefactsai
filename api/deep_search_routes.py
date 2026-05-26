"""
Deep Search Routes — User-facing Perplexity-type research search.

Provides deep search, comparative analysis, and weather context enrichment.
Deep search and comparison are gated to Professional+ tiers.
Weather context is available to Standard+ tiers.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import check_premium_feature, UsageTracker
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("deep-search-api")
router = APIRouter(prefix="/api/deep-search", tags=["Deep Search"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class DeepSearchRequest(BaseModel):
    """Deep search request."""
    query: str = Field(..., min_length=3, max_length=1000)
    country: Optional[str] = Field(None, max_length=2)
    category: Optional[str] = None
    include_weather: bool = Field(default=True)
    limit: int = Field(default=10, ge=1, le=30)


class CompareRequest(BaseModel):
    """Comparative analysis request."""
    query_a: str = Field(..., min_length=3, max_length=500)
    query_b: str = Field(..., min_length=3, max_length=500)
    country: Optional[str] = Field(None, max_length=2)


class CitationResponse(BaseModel):
    type: str  # internal_article, external_web
    article_id: Optional[str] = None
    title: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    published_date: Optional[str] = None
    credibility: Optional[str] = None
    reliability_score: Optional[float] = None
    relevance_score: Optional[float] = None
    excerpt: Optional[str] = None


class WeatherDataPoint(BaseModel):
    source: str
    content: str
    reliability: Optional[str] = None
    retrieval_method: Optional[str] = None


class WeatherContextResponse(BaseModel):
    country_code: str
    data_points: List[WeatherDataPoint]


class DeepSearchResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationResponse]
    internal_articles_count: int
    external_sources_count: int
    weather_context: Optional[WeatherContextResponse] = None
    filters: dict = {}
    # Methodology: how the answer was assembled. Frontend renders in
    # the "How this was answered" drawer.
    methodology: Optional[dict] = None
    # Scope refinement chips when the search returned zero results.
    clarification_needed: Optional[List[str]] = None
    searched_at: str


class ComparativeAnalysisStructured(BaseModel):
    summary: str
    similarities: List[str]
    differences: List[str]
    evidence_strength: str
    common_gaps: List[str]


class CompareResponse(BaseModel):
    query_a: str
    query_b: str
    result_a: DeepSearchResponse
    result_b: DeepSearchResponse
    comparative_analysis: str
    # Structured equivalent for visual rendering. Frontend prefers this
    # when present and falls back to the markdown blob otherwise.
    comparative_analysis_structured: Optional[ComparativeAnalysisStructured] = None
    compared_at: str


class LocationWeather(BaseModel):
    location_name: str
    coordinates: dict
    current_weather: Optional[dict] = None
    forecast_7day: Optional[dict] = None
    historical_normals: Optional[dict] = None
    anomaly: Optional[dict] = None


class ArticleWeatherContext(BaseModel):
    article_id: str
    locations_found: int
    locations_analyzed: int
    weather_contexts: List[LocationWeather]


# =============================================================================
# DEEP SEARCH (Professional+ only)
# =============================================================================

@router.post("/", response_model=DeepSearchResponse)
async def deep_search(
    request: DeepSearchRequest,
    current_user: Any = Depends(get_optional_user),
):
    """
    Perform a deep research search combining internal corpus + external sources.

    Uses Perplexity AI for external search and pgvector for internal corpus.
    Synthesizes a unified answer with citations and credibility indicators.
    All users get basic access; premium tiers get higher limits.
    """
    user_tier = "freemium"
    user_id = None
    if current_user and isinstance(current_user, dict):
        user_tier = current_user.get("subscription_tier", "freemium") or "freemium"
        user_id = current_user.get("user_id")
    elif current_user:
        user_tier = getattr(current_user, "subscription_tier", "freemium") or "freemium"
        user_id = getattr(current_user, "user_id", None)

    # Phase 1A (2026-05-23) — freemium quota gate (2 deep_research / month
    # on Free tier per the 3/3/2 decision). Runs BEFORE legacy per-day
    # discovery_query check so the user gets the structured upgrade hint.
    from api.quota_service import QuotaService
    QuotaService.check_and_raise(
        user_id=str(user_id) if user_id else None,
        tier=user_tier,
        quota_key="deep_research",
    )

    # Legacy per-day cap still applies on top (different concern: prevents
    # a paid user from runaway spend even though their monthly quota is fine).
    if user_id:
        allowed, current, limit = UsageTracker.check_limit(
            str(user_id), user_tier, "discovery_query", "day"
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Daily deep search limit exceeded ({current}/{limit})."
            )

    db = get_postgres()

    from app.domains.intelligence.deep_search_service import DeepSearchService
    service = DeepSearchService(db)

    try:
        result = await service.search(
            query=request.query,
            country=request.country,
            category=request.category,
            include_weather=request.include_weather,
            limit=request.limit,
        )

        guidance_status = None
        methodology = result.get("methodology") if isinstance(result, dict) else None
        if isinstance(methodology, dict):
            guidance = methodology.get("guidance")
            if isinstance(guidance, dict):
                guidance_status = guidance.get("status")

        # Log usage — both legacy and new quota counters.
        if user_id:
            UsageTracker.log_usage(
                user_id=str(user_id),
                usage_type="discovery_query",
                resource_url=f"deep_search:{request.query[:100]}",
            )
            # Phase 1A: record the deep_research quota consumption so the
            # monthly counter ticks. Best-effort — failure here doesn't fail
            # the user request.
            QuotaService.consume(
                user_id=str(user_id),
                quota_key="deep_research",
                resource_url=f"deep_search:{request.query[:100]}",
            )

        logger.info(
            "Deep search executed",
            user_id=user_id,
            query=request.query[:100],
            internal_count=result.get("internal_articles_count", 0),
            external_count=result.get("external_sources_count", 0),
            guidance_status=guidance_status,
        )

        return DeepSearchResponse(**result)

    except Exception as e:
        logger.error(f"Deep search failed: {e}", query=request.query[:100])
        guidance_hint = (
            " Try narrowing by country/timeframe or use 'Get query help in chat'."
        )
        raise HTTPException(
            status_code=500,
            detail=f"Deep search failed. Please try again.{guidance_hint}",
        )


# =============================================================================
# COMPARATIVE ANALYSIS (Professional+ only)
# =============================================================================

@router.post("/compare", response_model=CompareResponse)
async def compare_topics(
    request: CompareRequest,
    current_user: Any = Depends(get_optional_user),
):
    """
    Compare two climate topics side by side.

    Performs deep search on both topics and generates a comparative analysis.
    All users get basic access; premium tiers get higher limits.
    """
    user_tier = "freemium"
    user_id = None
    if current_user and isinstance(current_user, dict):
        user_tier = current_user.get("subscription_tier", "freemium") or "freemium"
        user_id = current_user.get("user_id")
    elif current_user:
        user_tier = getattr(current_user, "subscription_tier", "freemium") or "freemium"
        user_id = getattr(current_user, "user_id", None)

    # Phase 1A (2026-05-23) — compare counts as its own quota key
    # (separate from deep_research because it costs ~2x the LLM tokens).
    from api.quota_service import QuotaService
    QuotaService.check_and_raise(
        user_id=str(user_id) if user_id else None,
        tier=user_tier,
        quota_key="compare",
    )

    db = get_postgres()

    from app.domains.intelligence.deep_search_service import DeepSearchService
    service = DeepSearchService(db)

    try:
        result = await service.compare(
            query_a=request.query_a,
            query_b=request.query_b,
            country=request.country,
        )

        # Log usage (counts as 2 legacy queries + 1 quota consumption)
        if user_id:
            try:
                UsageTracker.log_usage(str(user_id), "discovery_query", resource_url=f"compare:{request.query_a[:50]}")
                UsageTracker.log_usage(str(user_id), "discovery_query", resource_url=f"compare:{request.query_b[:50]}")
            except Exception as usage_err:
                logger.warning(f"Usage tracking failed for compare: {usage_err}")
            QuotaService.consume(
                user_id=str(user_id),
                quota_key="compare",
                resource_url=f"compare:{request.query_a[:50]} vs {request.query_b[:50]}",
            )

        return CompareResponse(**result)

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail="Comparison failed. Please try again.")


# =============================================================================
# WEATHER CONTEXT (Standard+ for articles, open for location lookup)
# =============================================================================

@router.get("/weather-context/{article_id}", response_model=ArticleWeatherContext)
async def get_article_weather_context(
    article_id: str,
    current_user: Any = Depends(get_current_user),
):
    """
    Get localized weather context for an article.

    Extracts geographic locations mentioned in the article, fetches current
    weather conditions, historical normals, and anomaly detection for each.

    Available to Standard+ tiers.
    """
    user_tier = (
        current_user.get("subscription_tier")
        if isinstance(current_user, dict)
        else getattr(current_user, "subscription_tier", "freemium")
    )

    if not check_premium_feature(user_tier, "weather_context"):
        raise HTTPException(
            status_code=403,
            detail="Weather context requires Standard or higher subscription."
        )

    db = get_postgres()

    from app.domains.content.weather_context_service import WeatherContextService
    service = WeatherContextService(db)

    try:
        result = await service.get_article_weather_context(article_id)
        if not result:
            # End2End audit (2026-05-27, Task G): was raising 404 here which
            # the frontend mapped to the empty state — fine. The Real bug
            # was the catch-all 500 below. Keep the empty/no-locations
            # contract intact.
            raise HTTPException(
                status_code=404,
                detail="No weather context available for this article."
            )
        return ArticleWeatherContext(**result)
    except HTTPException:
        raise
    except Exception as e:
        # End2End audit (2026-05-27, Task G): the catch-all used to return
        # 500 which the frontend rendered as "Weather context temporarily
        # unavailable. Try refreshing in a moment." for every article whose
        # NER didn't surface a GPE entity. Now degrade gracefully to a 200
        # response with an empty weather_contexts list so the frontend
        # shows the proper "No geographic locations detected" empty state.
        # Real infra outages (DB unreachable, Open-Meteo 503) still log
        # but the user-facing UX matches the empty-list contract.
        logger.warning(f"Weather context degraded for {article_id}: {e}")
        return ArticleWeatherContext(
            article_id=article_id,
            locations_found=0,
            weather_contexts=[],
        )


@router.get("/intelligence-brief")
async def get_intelligence_brief(
    topic: str = Query(..., min_length=3, max_length=500, description="Topic for the brief"),
    country: Optional[str] = Query(None, max_length=2, description="Country code filter"),
    current_user: Any = Depends(get_current_user),
):
    """
    Generate a comprehensive intelligence brief on a climate topic.

    Returns a structured brief with summary, key findings, areas of agreement,
    areas of dispute, data gaps, recommended reading, and consensus analysis.

    Requires Professional or Enterprise subscription.
    """
    user_tier = (
        current_user.get("subscription_tier")
        if isinstance(current_user, dict)
        else getattr(current_user, "subscription_tier", "freemium")
    )
    user_id = (
        current_user.get("user_id")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )

    if not check_premium_feature(user_tier, "deep_search"):
        raise HTTPException(
            status_code=403,
            detail="Intelligence briefs require Professional or Enterprise subscription."
        )

    db = get_postgres()

    try:
        from app.domains.intelligence.cross_article_service import CrossArticleService
        service = CrossArticleService(db)
        brief = await service.generate_intelligence_brief(topic=topic, country=country)

        # Log usage
        if user_id:
            UsageTracker.log_usage(
                user_id=str(user_id),
                usage_type="discovery_query",
                resource_url=f"intelligence_brief:{topic[:80]}",
            )

        logger.info(
            "Intelligence brief generated",
            user_id=user_id,
            topic=topic[:100],
            article_count=brief.get("article_count", 0),
        )

        return brief

    except Exception as e:
        logger.error(f"Intelligence brief failed: {e}", topic=topic[:100])
        raise HTTPException(status_code=500, detail="Intelligence brief generation failed.")


@router.get("/weather-location")
async def get_location_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    name: Optional[str] = Query(None, max_length=100),
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Get weather context for a specific location.

    Available to all users (uses free Open-Meteo API).
    Returns current conditions, 7-day forecast, historical normals, and anomaly detection.
    """
    db = get_postgres()

    from app.domains.content.weather_context_service import WeatherContextService
    service = WeatherContextService(db)

    try:
        result = await service.get_location_weather(lat, lon, name)
        if not result:
            raise HTTPException(status_code=404, detail="Weather data unavailable for this location.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Location weather failed for ({lat}, {lon}): {e}")
        raise HTTPException(status_code=500, detail="Weather data unavailable.")
