"""
Climate News API - FastAPI Backend

Serves live climate intelligence sourced from Perplexity-assisted news discovery
and authoritative climate datasets (Open-Meteo, NOAA, NASA).
"""

import json
import os
import sys
from pathlib import Path
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Ensure project root and shared backend package are importable when running locally
ROOT_DIR = Path(__file__).resolve().parents[1]  # points to repo root (climatenews)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SRC_BACKEND = ROOT_DIR / "src" / "backend"
if SRC_BACKEND.exists() and str(SRC_BACKEND) not in sys.path:
    sys.path.insert(0, str(SRC_BACKEND))

# Load environment variables from .env so JWT_SECRET_KEY and others are available
load_dotenv(dotenv_path=ROOT_DIR / ".env")

from shared.database import get_postgres
from shared.logger import setup_logging
from api.models import (
    Article,
    ArticleDetail,
    ClaimDetail,
    DashboardStats,
    FactCheck,
    WorkflowStatus,
    TriggerWorkflowRequest,
    TriggerWorkflowResponse,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    TagStat,
    Country,
)
from celery import chain
from app.tasks.ingestion import discover_articles
from app.tasks.processing import verify_claims, create_summary
from app.tasks.video import render_video_preview
from app.tasks.publication import publish_article


def _parse_tags(value: Any) -> List[str]:
    """Convert stored Postgres text[] representation into a Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    text = str(value).strip()
    if not text or text == '{}':
        return []
    stripped = text.strip('{}')
    if not stripped:
        return []
    parts: List[str] = []
    for part in stripped.split(','):
        cleaned = part.strip().strip('"').strip("'")
        if cleaned:
            parts.append(cleaned)
    return parts


def _to_pg_array(items: List[str]) -> str:
    """Convert python list to Postgres text[] string."""
    if not items:
        return '{}'
    escaped: List[str] = []
    for item in items:
        safe = str(item).replace('"', '\\"')
        escaped.append('"' + safe + '"')
    return '{' + ','.join(escaped) + '}'


def _to_int(value: Any) -> Optional[int]:
    """Best-effort conversion to int (supports Decimal)."""
    if value is None:
        return None
    if isinstance(value, bool):  # Guard against bools
        return int(value)
    try:
        if isinstance(value, Decimal):
            return int(value.to_integral_value())
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    """Best-effort conversion to float (supports Decimal)."""
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_to_article(row: Dict[str, Any]) -> Article:
    """Serialize a raw SQL row into an Article model."""
    excerpt = row.get("excerpt")
    if not excerpt:
        extracted = row.get("extracted_text") or ""
        excerpt = extracted[:280].strip() or None

    # Parse enrichment_metadata from JSON string if needed
    enrichment_meta = row.get("enrichment_metadata")
    if isinstance(enrichment_meta, str):
        try:
            enrichment_meta = json.loads(enrichment_meta)
        except (json.JSONDecodeError, TypeError):
            enrichment_meta = None

    article = Article(
        article_id=str(row.get("article_id")),
        title=row.get("title", ""),
        url=row.get("url", ""),
        author=row.get("author"),
        published_date=row.get("published_date"),
        source_name=row.get("source_name", ""),
        source_credibility_score=_to_int(row.get("source_credibility_score")),
        excerpt=excerpt,
        enriched_excerpt=row.get("enriched_excerpt"),
        climate_context_summary=row.get("climate_context_summary"),
        enrichment_metadata=enrichment_meta,
        claim_count=_to_int(row.get("claims_count")) or 0,
        verified_claim_count=_to_int(row.get("verified_claims_count")) or 0,
        tags=_parse_tags(row.get("tags")),
        content_relevance_score=_to_float(row.get("content_relevance_score")),
        reliability_score=_to_int(row.get("reliability_score")),
        overall_credibility=row.get("overall_credibility"),
        created_at=row.get("created_at"),
        country_code=row.get("country_code"),
        claims_status=row.get("claims_status"),
        claims_error_message=row.get("claims_error_message"),
        claims_processed_at=row.get("claims_processed_at"),
        content_category=row.get("content_category"),
    )
    return article


# Initialise FastAPI
app = FastAPI(
    title="Climate News API",
    description="REST API for European climate news, fact checks, and live climate data",
    version="2.0.0",  # Updated to 2.0 with auth and premium features
)

# Request/trace correlation middleware (adds X-Request-ID and X-Trace-ID)
from api.observability_middleware import ObservabilityMiddleware
app.add_middleware(ObservabilityMiddleware)

# CORS (allow local frontend dev servers)
allowed_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:5300",
)
ALLOWED_ORIGINS = [
    origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "traceparent", "tracestate"],
    expose_headers=["X-Request-ID", "X-Trace-ID"],
    max_age=600,
)

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Content Security Policy — restrict where scripts/styles/images can load
        # from. Permissive enough for the Next.js frontend, blocks classic XSS
        # vectors. Production-only because dev tools (HMR) need eval.
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.open-meteo.com https://archive-api.open-meteo.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware
from api.rate_limiter import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Include authentication routes
from api.auth_routes import router as auth_router, get_optional_user
app.include_router(auth_router)

from api.url_analysis_routes import router as url_analysis_router
app.include_router(url_analysis_router)

# Stage 3 / M4 (2026-05-27) — topic-feedback table (mig 050) for the
# evolving validation corpus. Lets users mark articles as off-topic
# from the article-detail page; daemon excludes flagged IDs from
# future selection.
from api.topic_feedback_routes import router as topic_feedback_router
app.include_router(topic_feedback_router)

# Stage 4 / M5 (2026-05-27) — semantic layer for the "why are these
# connected" drill-down the user has been asking for. Reads the
# clilens-lane-a-entity knowledge graph and adds an LLM-explained
# "explain the bridge" endpoint.
from api.semantic_routes import router as semantic_router
app.include_router(semantic_router)

# Stage 5 follow-up (2026-05-27) — golden examples corpus. Curated
# "best of" set across all artifact kinds; doubles as the LoRA
# training-data seed for the GX10 specialist fine-tunes
# (claim-extractor-7B, context-summarizer-7B, verdict-adjudicator-7B
# per docs/reports/asusgx10inferencestrategy.md).
from api.golden_examples_routes import router as golden_examples_router
app.include_router(golden_examples_router)

# Phase 1A (2026-05-23) — quota dashboard endpoint (3/3/2 freemium).
from api.quota_routes import router as quota_router
app.include_router(quota_router)

# Phase 3 (2026-05-23) — MH5 AOI alert subscriptions (Basic+ tier).
from api.aoi_routes import router as aoi_router
app.include_router(aoi_router)

# Phase 4C (2026-05-24) — agentic skills registry introspection endpoint.
from api.skills_routes import router as skills_router
app.include_router(skills_router)

# Admin pipeline routes
from api.admin_pipeline_routes import router as admin_pipeline_router
app.include_router(admin_pipeline_router)

# Article ingestion routes
from api.article_ingestion_routes import router as ingestion_router
app.include_router(ingestion_router)

from api.search_routes import router as search_router
app.include_router(search_router)

from api.subscription_routes import router as subscription_router
app.include_router(subscription_router)

# Include user dashboard routes
from api.user_routes import router as user_router
app.include_router(user_router)

# Include API key management routes
from api.api_key_routes import router as api_key_router
app.include_router(api_key_router)

# Include export routes
from api.export_routes import router as export_router
app.include_router(export_router)

# Include discovery routes (on-demand Perplexity discovery)
from api.discovery_routes import router as discovery_router
app.include_router(discovery_router)

# Include conversation Q&A routes
from api.conversation_routes import router as conversation_router
app.include_router(conversation_router)

# Include similarity routes (pgvector-based similar article discovery)
from api.similarity_routes import router as similarity_router
app.include_router(similarity_router)

# Include feed preference routes (auto-update configuration)
from api.feed_routes import router as feed_router
app.include_router(feed_router)

# Include source registry routes (user-registered custom RSS/Atom feeds)
from api.source_registry_routes import router as source_registry_router
app.include_router(source_registry_router)

# Include forecast routes
from api.forecast_routes import router as forecast_router
app.include_router(forecast_router)

# Include OG image routes (social sharing)
from api.og_image_routes import router as og_image_router
app.include_router(og_image_router)

# Include map routes (geographic article distribution)
from api.map_routes import router as map_router
app.include_router(map_router)

# Include infographic routes (SVG infographic generation)
from api.infographic_routes import router as infographic_router
app.include_router(infographic_router)

# Include deep search routes (Perplexity-type search, weather context, comparison)
from api.deep_search_routes import router as deep_search_router
app.include_router(deep_search_router)

from api.analytics_routes import router as analytics_router
app.include_router(analytics_router)

# Include translation routes (multi-language content access)
from api.translation_routes import router as translation_router
app.include_router(translation_router)

# Include scheduler routes (Cloud Scheduler HTTP triggers, replaces Celery Beat)
from api.scheduler_routes import router as scheduler_router
app.include_router(scheduler_router)

# Include benchmark & audit routes (scientific benchmarking, KPI auditing)
from api.benchmark_routes import router as benchmark_router
app.include_router(benchmark_router)

# Logger (initialize before v2 routers)
logger = setup_logging("api")

# Include DDD domain routers (v2 API)
try:
    from app.domains.content.router import router as content_router_v2
    app.include_router(content_router_v2)
    logger.info("Loaded v2 content router")
except ImportError as e:
    logger.warning(f"Could not load v2 content router: {e}")

try:
    from app.domains.intelligence.router import router as intelligence_router_v2
    app.include_router(intelligence_router_v2)
    logger.info("Loaded v2 intelligence router")
except ImportError as e:
    logger.warning(f"Could not load v2 intelligence router: {e}")

try:
    from app.domains.intelligence.transparency import router as transparency_router
    app.include_router(transparency_router)
    logger.info("Loaded transparency router")
except ImportError as e:
    logger.warning(f"Could not load transparency router: {e}")

# New routers: OAuth, User Activity, Research Reports, CARF, Advanced Filters
from api.oauth_routes import router as oauth_router
app.include_router(oauth_router)

from api.activity_routes import router as activity_router
app.include_router(activity_router)

from api.research_routes import router as research_router
app.include_router(research_router)

from api.carf_routes import router as carf_router
app.include_router(carf_router)

from api.advanced_filter_routes import router as filter_router
app.include_router(filter_router)

logger.info("Loaded OAuth, Activity, Research, CARF, and Advanced Filter routers")

# General chat routes (cross-article Q&A)
from api.chat_routes import router as chat_router
app.include_router(chat_router)

# Saved query scheduling routes
from api.saved_query_routes import router as saved_query_router
app.include_router(saved_query_router)

# Include source suggestion routes (user-submitted source suggestions)
from api.source_suggestion_routes import router as source_suggestion_router
app.include_router(source_suggestion_router)

# Include green transition routes (per-country sustainability intelligence)
from api.green_transition_routes import router as green_transition_router
app.include_router(green_transition_router)

# Phase 4 wave 2 (2026-05-16): public methodology surface — every prompt,
# formula, and indicator the platform uses, all inspectable via API.
from api.methodology_routes import router as methodology_router
app.include_router(methodology_router)

# Phase 6 wave 1 (2026-05-16): KL-divergence drift detection on source mix.
from api.drift_routes import router as drift_router
app.include_router(drift_router)

logger.info("Loaded Chat, Saved Query, Green Transition, Methodology, and Drift routers")

# Phase 8 (2026-05-20): Corporate climate disclosure verification
from api.company_routes import router as company_router
app.include_router(company_router)

# Phase 10 (2026-05-25) — LLM routing admin endpoints
from api.llm_admin_routes import router as llm_admin_router
app.include_router(llm_admin_router)

# Phase 10 (2026-05-25) — polymorphic saved_items (save anything, not just articles)
from api.saved_items_routes import router as saved_items_router
app.include_router(saved_items_router)

# Slice 5a (2026-05-25) — link-rot detection admin endpoint (token-gated).
from api.admin_link_check_routes import router as admin_link_check_router
app.include_router(admin_link_check_router)

# Deferred #13 (2026-05-25) — research feed: subscribe-to-topic +
# CrossRef poller. Public user routes + token-gated admin poll endpoint.
from api.research_feed_routes import (
    router as research_feed_router,
    admin_router as research_feed_admin_router,
)
app.include_router(research_feed_router)
app.include_router(research_feed_admin_router)

# Deferred #14 (2026-05-25) — scenario explorer (linear interpolation
# between IPCC AR6 SSP projections; transparent disclaimer that this
# is interpolation, not simulation).
from api.scenario_routes import router as scenario_router
app.include_router(scenario_router)

# 2026-05-27 Section II audit — backfill admin endpoints for
# source_credibility_score, extracted-text HTML strip, and the missing
# enrichment scheduler trigger. All three accept SCHEDULER_SECRET so
# they can be driven by Cloud Scheduler cron jobs.
from api.admin_backfill_routes import router as admin_backfill_router
app.include_router(admin_backfill_router)

logger.info("Loaded Company router")


# ---------------------------------------------------------------------------
# Generic text translation endpoint (used by frontend i18n-context)
# ---------------------------------------------------------------------------

class GenericTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    target_language: str = Field(..., min_length=2, max_length=5)

@app.post("/api/translate/")
@app.post("/api/translate")
async def translate_text_generic(
    request: GenericTranslateRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Translate arbitrary text to a target language using DeepSeek or Anthropic."""
    target = request.target_language.lower()[:2]
    if target == "en":
        return {"translated_text": request.text, "source_language": "en", "target_language": "en"}

    prompt = (
        f"Translate the following text to {target}. "
        "Return ONLY the translated text, nothing else.\n\n"
        f"{request.text}"
    )

    # Try Anthropic first
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            message = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            if message.content:
                return {
                    "translated_text": message.content[0].text.strip(),
                    "source_language": "en",
                    "target_language": target,
                }
        except Exception as e:
            logger.warning(f"Anthropic translation failed: {e}")

    # Fallback to DeepSeek
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        try:
            from openai import OpenAI as OpenAIClient
            client = OpenAIClient(
                api_key=deepseek_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            response = client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1,
            )
            return {
                "translated_text": response.choices[0].message.content.strip(),
                "source_language": "en",
                "target_language": target,
            }
        except Exception as e:
            logger.warning(f"DeepSeek translation failed: {e}")

    raise HTTPException(status_code=503, detail="Translation service unavailable")


# Basic health check
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/healthz/ready")
async def readiness():
    """Readiness checks for local debugging (DB/Redis connectivity)."""
    results: Dict[str, Any] = {"status": "ok", "checks": {}}

    # Postgres
    try:
        db = get_postgres()
        db.execute_query("SELECT 1")
        results["checks"]["postgres"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        results["status"] = "degraded"
        results["checks"]["postgres"] = {"status": "error", "error": str(exc)}

    # Redis
    try:
        from shared.database import get_redis

        redis_client = get_redis()
        redis_client.client.ping()
        results["checks"]["redis"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        results["status"] = "degraded"
        results["checks"]["redis"] = {"status": "error", "error": str(exc)}

    return results


# Database dependency
async def get_db():
    """Dependency injection for database access."""
    db = get_postgres()
    try:
        yield db
    finally:
        pass  # Connection pooling handled by shared client


@app.get("/api/articles", response_model=List[Article])
async def list_articles(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    credibility: Optional[str] = Query(default=None, regex=r"^(HIGH|MEDIUM|LOW|high|medium|low)$"),
    country: Optional[str] = Query(default=None, min_length=2, max_length=2),
    source: Optional[str] = Query(default=None),
    tags: Optional[List[str]] = Query(default=None),
    category: Optional[str] = Query(default=None, description="Filter by content category (e.g. policy, climate_science)"),
    q: Optional[str] = Query(default=None, description="Full-text search on title and excerpt"),
    db=Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Return published articles with optional filters.

    Reliability tier filtering:
    - Free users: only 'public' sources
    - Standard users: 'public' + 'research' sources
    - Professional users: all sources including 'scientific'
    """
    from api.rate_limiter import TIER_LIMITS

    filters: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if date_from is not None:
        filters.append("COALESCE(a.published_date, a.created_at)::date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        filters.append("COALESCE(a.published_date, a.created_at)::date <= :date_to")
        params["date_to"] = date_to
    if credibility:
        filters.append("UPPER(a.overall_credibility) = UPPER(:credibility)")
        params["credibility"] = credibility
    if country:
        filters.append("a.country_code = :country")
        params["country"] = country.upper()
    if source:
        filters.append("LOWER(a.source_name) = LOWER(:source)")
        params["source"] = source
    if tags:
        filters.append("a.tags && CAST(:tags_filter AS text[])")
        params["tags_filter"] = _to_pg_array(tags)
    if category:
        filters.append("a.content_category = :category")
        params["category"] = category.lower()

    # Determine user tier for reliability tier filtering
    user_tier = "freemium"
    if current_user:
        user_tier = current_user.get("subscription_tier", "freemium")
    tier_config = TIER_LIMITS.get(user_tier, TIER_LIMITS["freemium"])
    allowed_source_tiers = tier_config.get("data_source_tiers", ["public"])

    query = """
        SELECT
            a.article_id,
            a.title,
            a.url,
            a.author,
            a.published_date,
            a.source_name,
            a.source_credibility_score,
            a.excerpt,
            a.extracted_text,
            a.tags,
            a.content_relevance_score,
            a.reliability_score,
            a.overall_credibility,
            a.created_at,
            a.country_code,
            a.claims_count,
            a.verified_claims_count,
            a.claims_status,
            a.claims_error_message,
            a.claims_processed_at,
            a.content_category,
            a.enriched_excerpt,
            a.climate_context_summary,
            a.enrichment_metadata
        FROM articles a
        LEFT JOIN source_credibility sc ON LOWER(a.source_name) = LOWER(sc.source_name)
        WHERE a.is_synthetic = FALSE
    """

    # Filter by allowed reliability tiers (sources without a tier default to 'public')
    if "scientific" not in allowed_source_tiers:
        filters.append("COALESCE(sc.reliability_tier, 'public') = ANY(CAST(:allowed_tiers AS text[]))")
        params["allowed_tiers"] = _to_pg_array(allowed_source_tiers)

    if filters:
        query += "\n        AND " + "\n        AND ".join(filters)

    # Optional full-text search against title + excerpt
    if q:
        query += (
            "\n        AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.excerpt, '')) "
            "@@ plainto_tsquery('english', :q)"
        )
        params["q"] = q

    query += """
        ORDER BY
            CASE WHEN COALESCE(a.reliability_score, 0) > 0 THEN 0 ELSE 1 END ASC,
            CASE UPPER(COALESCE(a.overall_credibility, ''))
                WHEN 'HIGH' THEN 0
                WHEN 'MEDIUM' THEN 1
                WHEN 'LOW' THEN 2
                ELSE 3
            END ASC,
            COALESCE(a.reliability_score, 0) DESC,
            COALESCE(a.source_credibility_score, 0) DESC,
            COALESCE(a.published_date, a.created_at) DESC
        LIMIT :limit OFFSET :offset
    """

    try:
        rows = db.execute_query(query, params=params)
        return [_row_to_article(row) for row in rows]
    except Exception as exc:
        logger.error("Failed to list articles", error=str(exc))
        raise HTTPException(status_code=500, detail="Unable to fetch articles")


@app.get("/api/articles/{article_id}", response_model=ArticleDetail)
async def get_article_detail(article_id: str, db=Depends(get_db)):
    """Return a single article with claim and fact-check details."""
    article_query = """
        SELECT
            a.article_id,
            a.title,
            a.url,
            a.author,
            a.published_date,
            a.source_name,
            a.source_credibility_score,
            a.excerpt,
            a.extracted_text,
            a.language_code,
            a.tags,
            a.content_relevance_score,
            a.reliability_score,
            a.overall_credibility,
            a.created_at,
            a.country_code,
            a.claims_count,
            a.verified_claims_count,
            a.claims_status,
            a.claims_error_message,
            a.claims_processed_at,
            a.content_category,
            a.enriched_excerpt,
            a.climate_context_summary,
            a.enrichment_metadata,
            a.executive_brief,
            a.analysis_article_generated_at,
            a.decomposed_confidence,
            a.insight_summary
        FROM articles a
        WHERE a.article_id = :article_id
          AND a.is_synthetic = FALSE
    """

    rows = db.execute_query(article_query, params={"article_id": article_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    article_row = rows[0]
    article = _row_to_article(article_row)

    claims_query = """
        SELECT
            c.claim_id,
            c.claim_text,
            c.claim_context,
            c.claim_type,
            c.claim_category,
            fc.fact_check_id,
            fc.verification_status,
            fc.confidence_score,
            fc.justification,
            fc.evidence,
            fc.evidence_chain,
            fc.decomposed_confidence,
            fc.climatecheck_hazard_type,
            fc.climatecheck_risk_score,
            fc.verified_at
        FROM claims c
        LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
        WHERE c.article_id = :article_id
        ORDER BY c.created_at ASC
    """

    claim_rows = db.execute_query(claims_query, params={"article_id": article_id})
    claims: List[ClaimDetail] = []
    for row in claim_rows:
        fact_check: Optional[FactCheck] = None
        if row.get("fact_check_id"):
            evidence_payload = row.get("evidence")
            if isinstance(evidence_payload, str):
                try:
                    evidence_payload = json.loads(evidence_payload)
                except json.JSONDecodeError:
                    evidence_payload = {"raw": evidence_payload}

            # Parse evidence_chain and decomposed_confidence JSONB
            ec_payload = row.get("evidence_chain")
            if isinstance(ec_payload, str):
                try:
                    ec_payload = json.loads(ec_payload)
                except json.JSONDecodeError:
                    ec_payload = []
            dc_payload = row.get("decomposed_confidence")
            if isinstance(dc_payload, str):
                try:
                    dc_payload = json.loads(dc_payload)
                except json.JSONDecodeError:
                    dc_payload = None

            fact_check = FactCheck(
                verification_status=row.get("verification_status") or "",
                confidence_score=_to_float(row.get("confidence_score")) or 0.0,
                justification=row.get("justification"),
                evidence=evidence_payload if isinstance(evidence_payload, dict) else None,
                climatecheck_hazard_type=row.get("climatecheck_hazard_type"),
                climatecheck_risk_score=_to_float(row.get("climatecheck_risk_score")),
                verified_date=row.get("verified_at"),
                decomposed_confidence=dc_payload if isinstance(dc_payload, dict) else None,
                evidence_chain=ec_payload if isinstance(ec_payload, list) else [],
            )

        claims.append(
            ClaimDetail(
                claim_id=str(row.get("claim_id")),
                claim_text=row.get("claim_text", ""),
                claim_context=row.get("claim_context"),
                claim_type=row.get("claim_type"),
                fact_check=fact_check,
            )
        )

    claims_available = (
        article.claims_status == "completed"
        and (article.claim_count or 0) > 0
    )

    detail = ArticleDetail(
        **article.dict(),
        full_text=article_row.get("extracted_text"),
        language_code=article_row.get("language_code"),
        claims=claims,
        claims_available=claims_available,
    )
    return detail


@app.get("/api/countries", response_model=List[Country])
async def list_countries(db=Depends(get_db)):
    """Return enabled countries with article counts."""
    query = """
        SELECT
            c.country_code,
            c.country_name,
            c.country_name_native,
            c.flag_emoji,
            c.language_code,
            c.is_eu_member,
            COALESCE(article_counts.article_count, 0) AS articles_count
        FROM countries c
        LEFT JOIN (
            SELECT country_code, COUNT(*) AS article_count
            FROM articles
            WHERE is_synthetic = FALSE
            GROUP BY country_code
        ) AS article_counts ON article_counts.country_code = c.country_code
        WHERE c.enabled = TRUE
        ORDER BY c.country_name ASC
    """
    rows = db.execute_query(query)
    return [
        Country(
            country_code=row.get("country_code"),
            country_name=row.get("country_name"),
            country_name_native=row.get("country_name_native"),
            flag_emoji=row.get("flag_emoji"),
            language_code=row.get("language_code"),
            is_eu_member=bool(row.get("is_eu_member")),
            articles_count=_to_int(row.get("articles_count")) or 0,
        )
        for row in rows
    ]


@app.get("/api/articles/{article_id}/translations")
async def get_article_translations(article_id: str, db=Depends(get_db)):
    """Return available translations for an article."""
    rows = db.execute_query(
        """
        SELECT to_language, translated_title, translated_summary,
               translation_confidence, translated_at
        FROM article_translations
        WHERE article_id = :article_id
        ORDER BY to_language
        """,
        {"article_id": article_id},
    )
    return [
        {
            "language": row.get("to_language"),
            "title": row.get("translated_title"),
            "summary": row.get("translated_summary"),
            "confidence": float(row.get("translation_confidence") or 0),
            "translated_at": row.get("translated_at"),
        }
        for row in (rows or [])
    ]


@app.post("/api/articles/{article_id}/translate")
async def request_article_translation(
    article_id: str,
    target_lang: str = Query(default="en", min_length=2, max_length=2),
    db=Depends(get_db),
):
    """Request translation of an article into a target language."""
    from app.tasks.translation import translate_article

    # Verify article exists
    rows = db.execute_query(
        "SELECT article_id FROM articles WHERE article_id = :aid",
        {"aid": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    task = translate_article.delay(article_id, [target_lang])
    return {"status": "queued", "task_id": task.id, "target_language": target_lang}


@app.get("/api/tags", response_model=List[TagStat])
async def list_tags(
    country: Optional[str] = Query(default=None, min_length=2, max_length=2),
    db=Depends(get_db),
):
    """Return the most frequently used tags."""
    query = """
        SELECT
            tag,
            COUNT(*) AS article_count
        FROM (
            SELECT unnest(tags) AS tag, country_code
            FROM articles
            WHERE tags IS NOT NULL AND array_length(tags, 1) > 0
              AND is_synthetic = FALSE
        ) AS expanded
        WHERE (:country IS NULL OR expanded.country_code = :country)
        GROUP BY tag
        ORDER BY article_count DESC, tag ASC
        LIMIT 50
    """
    params = {"country": country.upper() if country else None}
    rows = db.execute_query(query, params=params)
    return [
        TagStat(tag=row.get("tag"), article_count=_to_int(row.get("article_count")) or 0)
        for row in rows
    ]


def _ensure_article_exists(db, article_id: str) -> None:
    exists_query = (
        "SELECT 1 FROM articles "
        "WHERE article_id = :article_id AND is_synthetic = FALSE"
    )
    rows = db.execute_query(exists_query, params={"article_id": article_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")


@app.post("/api/articles/{article_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(article_id: str, payload: FeedbackRequest, db=Depends(get_db)):
    """Persist article feedback from end users."""
    _ensure_article_exists(db, article_id)

    insert_query = """
        INSERT INTO article_feedback (
            article_id,
            feedback_type,
            reliability_score,
            comment,
            submitted_by
        )
        VALUES (
            :article_id,
            :feedback_type,
            :reliability_score,
            :comment,
            :submitted_by
        )
        RETURNING feedback_id, article_id, feedback_type, reliability_score, comment, submitted_at
    """

    params = {
        "article_id": article_id,
        "feedback_type": payload.feedback_type,
        "reliability_score": payload.reliability_score,
        "comment": payload.comment,
        "submitted_by": payload.submitted_by,
    }

    try:
        rows = db.execute_query(insert_query, params=params)
        if not rows:
            raise HTTPException(status_code=500, detail="Failed to store feedback")
        row = rows[0]
        return FeedbackResponse(
            feedback_id=str(row.get("feedback_id")),
            article_id=str(row.get("article_id")),
            feedback_type=row.get("feedback_type"),
            reliability_score=_to_int(row.get("reliability_score")),
            comment=row.get("comment"),
            submitted_at=row.get("submitted_at"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Feedback insertion failed", error=str(exc), article_id=article_id)
        raise HTTPException(status_code=500, detail="Unable to save feedback")


@app.get("/api/articles/{article_id}/feedback", response_model=FeedbackSummary)
async def get_feedback_summary(article_id: str, db=Depends(get_db)):
    """Aggregate user feedback for an article."""
    _ensure_article_exists(db, article_id)

    summary_query = """
        SELECT
            COUNT(*) AS total_feedback,
            COUNT(*) FILTER (WHERE feedback_type = 'USEFUL') AS useful,
            COUNT(*) FILTER (WHERE feedback_type = 'NOT_USEFUL') AS not_useful,
            COUNT(*) FILTER (WHERE feedback_type = 'FLAGGED') AS flagged,
            AVG(reliability_score) AS average_reliability
        FROM article_feedback
        WHERE article_id = :article_id
    """

    rows = db.execute_query(summary_query, params={"article_id": article_id})
    row = rows[0] if rows else {}

    return FeedbackSummary(
        article_id=article_id,
        total_feedback=_to_int(row.get("total_feedback")) or 0,
        useful=_to_int(row.get("useful")) or 0,
        not_useful=_to_int(row.get("not_useful")) or 0,
        flagged=_to_int(row.get("flagged")) or 0,
        average_reliability=_to_float(row.get("average_reliability")),
    )


def _collect_stats(db) -> DashboardStats:
    """Compute dashboard statistics."""
    article_stats = db.execute_query(
        """
        SELECT
            COUNT(*) AS total_articles,
            COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS articles_today,
            MAX(updated_at) AS last_updated
        FROM articles
        WHERE is_synthetic = FALSE
        """
    )

    fact_stats = db.execute_query(
        """
        SELECT
            COUNT(*) AS total_fact_checks,
            COUNT(*) FILTER (WHERE verification_status = 'VERIFIED') AS verified_claims,
            AVG(confidence_score) AS average_confidence
        FROM fact_checks
        """
    )

    article_row = article_stats[0] if article_stats else {}
    fact_row = fact_stats[0] if fact_stats else {}

    average_confidence = _to_float(fact_row.get("average_confidence"))
    if average_confidence is not None:
        average_confidence *= 100.0

    return DashboardStats(
        total_articles=_to_int(article_row.get("total_articles")) or 0,
        articles_today=_to_int(article_row.get("articles_today")) or 0,
        total_fact_checks=_to_int(fact_row.get("total_fact_checks")) or 0,
        verified_claims=_to_int(fact_row.get("verified_claims")) or 0,
        average_confidence=average_confidence or 0.0,
        last_updated=article_row.get("last_updated"),
    )


@app.get("/api/stats", response_model=DashboardStats)
async def get_public_stats(db=Depends(get_db)):
    """Public dashboard statistics."""
    try:
        return _collect_stats(db)
    except Exception as exc:
        logger.error("Stats query failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Unable to compute statistics")


@app.get("/api/admin/dashboard", response_model=DashboardStats)
async def get_admin_dashboard(db=Depends(get_db), current_user: dict = Depends(get_optional_user)):
    """Admin dashboard — requires authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required for admin access")
    return await get_public_stats(db)


@app.post("/api/admin/trigger-workflow", response_model=TriggerWorkflowResponse)
async def trigger_workflow(request: TriggerWorkflowRequest, current_user: dict = Depends(get_optional_user)):
    """Manually trigger the ingestion, verification, and publishing workflow. Requires authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required for admin access")
    task_id = request.task_id or f"task-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    logger.info(
        "Triggering Celery workflow",
        task_id=task_id,
        country=request.country,
        max_articles=request.max_articles,
    )

    try:
        # Propagate incoming trace context to Celery workers when available.
        headers = {}
        try:
            from opentelemetry import propagate

            propagate.inject(headers)
        except Exception:
            headers = {}

        workflow = chain(
            discover_articles.s(
                country=request.country or "FI",
                max_articles=request.max_articles or 5,
                seed_article_ids=request.article_ids,
                task_metadata={"task_id": task_id},
            ),
            verify_claims.s(),
            create_summary.s(),
            render_video_preview.s(),
            publish_article.s(),
        )

        async_result = workflow.apply_async(headers=headers)

        logger.info("Workflow enqueued", task_id=task_id, celery_id=async_result.id)

        return TriggerWorkflowResponse(
            task_id=task_id,
            status="queued",
            message="Workflow enqueued via Celery",
            celery_id=async_result.id,
        )

    except Exception as exc:
        logger.error("Error triggering workflow", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {exc}")


@app.get("/api/admin/workflows", response_model=List[WorkflowStatus])
async def get_workflows(limit: int = Query(default=10, ge=1, le=50), db=Depends(get_db), current_user: dict = Depends(get_optional_user)):
    """Return recent workflow executions (deduplicated per task). Requires authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required for admin access")
    query = """
        WITH latest AS (
            SELECT DISTINCT ON (task_id)
                task_id,
                stage,
                status,
                metadata,
                timestamp
            FROM workflow_logs
            ORDER BY task_id, timestamp DESC
        ),
        started AS (
            SELECT task_id, MIN(timestamp) AS started_at
            FROM workflow_logs
            WHERE event_type = 'WORKFLOW_STARTED'
            GROUP BY task_id
        )
        SELECT
            latest.task_id,
            latest.status,
            latest.stage,
            latest.metadata,
            latest.timestamp,
            started.started_at
        FROM latest
        LEFT JOIN started ON started.task_id = latest.task_id
        ORDER BY latest.timestamp DESC NULLS LAST
        LIMIT :limit
    """

    rows = db.execute_query(query, params={"limit": limit})
    workflows: List[WorkflowStatus] = []
    for row in rows:
        metadata_payload = row.get("metadata")
        if isinstance(metadata_payload, str):
            try:
                metadata_payload = json.loads(metadata_payload)
            except json.JSONDecodeError:
                metadata_payload = {"raw": metadata_payload}
        elif metadata_payload is None:
            metadata_payload = {}

        workflows.append(
            WorkflowStatus(
                task_id=row.get("task_id"),
                status=row.get("status") or "IN_PROGRESS",
                current_stage=row.get("stage"),
                started_at=row.get("started_at"),
                completed_at=None,
                metadata=metadata_payload if isinstance(metadata_payload, dict) else {},
            )
        )

    return workflows


@app.post("/api/articles/{article_id}/reanalyze")
async def reanalyze_article(
    article_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Re-run verification analysis on an article.

    Clears previous claims and fact-checks, resets status to 'pending',
    and triggers the verification pipeline in the background.

    Returns explanation of why the previous analysis may have failed.
    """
    # Verify article exists and get current state
    rows = db.execute_query(
        """
        SELECT article_id, title, claims_status, claims_error_message,
               extracted_text, source_name
        FROM articles
        WHERE article_id = :article_id
          AND is_synthetic = FALSE
        """,
        {"article_id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    article = rows[0]
    text = article.get("extracted_text") or ""

    # Build failure explanation
    previous_status = article.get("claims_status")
    previous_error = article.get("claims_error_message")
    failure_reason = _explain_failure(previous_status, previous_error, text)

    # Check if text is available
    if len(text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Article text is too short for analysis (minimum 50 characters). "
                   "The original content may not have been scraped successfully.",
        )

    # Clear old claims and fact-checks for this article
    db.execute_update(
        "DELETE FROM fact_checks WHERE claim_id IN (SELECT claim_id FROM claims WHERE article_id = :aid)",
        {"aid": article_id},
    )
    db.execute_update(
        "DELETE FROM claims WHERE article_id = :aid",
        {"aid": article_id},
    )

    # Reset article status
    db.execute_update(
        """
        UPDATE articles
        SET claims_status = 'pending',
            claims_error_message = NULL,
            claims_count = 0,
            verified_claims_count = 0,
            reliability_score = NULL,
            overall_credibility = NULL,
            claims_processed_at = NULL,
            updated_at = NOW()
        WHERE article_id = :aid
        """,
        {"aid": article_id},
    )

    # Trigger verification in background via Celery
    try:
        from app.tasks.fact_check_pipeline import auto_verify_pending_articles
        auto_verify_pending_articles.delay(batch_size=1)
    except Exception as e:
        logger.warning(f"Could not queue Celery task, will be picked up by scheduler: {e}")

    logger.info(f"Re-analysis triggered for article {article_id}")

    return {
        "status": "queued",
        "article_id": article_id,
        "message": "Re-analysis has been queued. The article will be re-processed shortly.",
        "previous_status": previous_status,
        "failure_explanation": failure_reason,
    }


def _explain_failure(status: Optional[str], error_msg: Optional[str], text: str) -> str:
    """Generate a user-friendly explanation of why analysis failed or is incomplete."""
    if status == "completed":
        return "Previous analysis completed successfully. Re-running for updated results."

    if status == "pending" or status is None:
        return "This article has not been analyzed yet."

    if not error_msg:
        if len(text.strip()) < 100:
            return (
                "The article text is very short, which may not provide enough content "
                "for meaningful claim extraction. This can happen with paywalled articles "
                "or sites that block automated content retrieval."
            )
        return "The previous analysis did not complete. No specific error was recorded."

    error_lower = error_msg.lower()

    if "rate limit" in error_lower or "429" in error_lower:
        return (
            "The AI service rate limit was exceeded during the previous attempt. "
            "This is a temporary issue — re-running should succeed."
        )
    if "api key" in error_lower or "authentication" in error_lower or "401" in error_lower:
        return (
            "There was an API authentication issue with the AI service. "
            "This has been addressed — please try again."
        )
    if "timeout" in error_lower or "timed out" in error_lower:
        return (
            "The analysis timed out during processing. This can happen with "
            "very long articles or when external services are slow."
        )
    if "too short" in error_lower or "minimum" in error_lower:
        return (
            "The extracted article text was too short for meaningful analysis. "
            "This often occurs with paywalled content or JavaScript-rendered pages."
        )
    if "anthropic" in error_lower:
        return (
            "The previous analysis attempted to use a deprecated AI provider. "
            "The system has been updated to use DeepSeek — re-running should succeed."
        )
    if "connection" in error_lower or "network" in error_lower:
        return (
            "A network connectivity issue prevented the analysis from completing. "
            "Please try again."
        )

    return f"Previous analysis failed: {error_msg}"


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
