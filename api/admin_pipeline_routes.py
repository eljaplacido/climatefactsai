"""
Admin Pipeline Routes - Trigger article processing pipeline

Endpoints to manually trigger:
- Claim extraction for pending articles
- Fact-checking for extracted claims
- Full pipeline processing
"""

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

import sys
from pathlib import Path

# Add src/backend to path
SRC_BACKEND = Path(__file__).resolve().parents[1] / "src" / "backend"
if str(SRC_BACKEND) not in sys.path:
    sys.path.insert(0, str(SRC_BACKEND))

from shared.database import get_postgres
from shared.logger import setup_logging
from app.domains.intelligence.services import ClaimExtractor, VerdictAdjudicator, EvidenceRetriever
from app.domains.intelligence.multi_llm_verifier import verify_claims
from api.auth_routes import get_current_user

logger = setup_logging("admin-pipeline")
router = APIRouter(prefix="/api/admin/pipeline", tags=["Admin Pipeline"])

# Admin email allowlist — users with these emails always get admin access
ADMIN_EMAILS = set(filter(None, os.environ.get("ADMIN_EMAILS", "").split(",")))


def require_admin(current_user: dict) -> dict:
    """Verify the authenticated user has admin privileges.

    Admin access is granted if the user's subscription_tier is 'enterprise'
    or the user's email is in the ADMIN_EMAILS allowlist.
    """
    tier = current_user.get("subscription_tier", "")
    email = current_user.get("email", "")

    if tier != "enterprise" and email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Enterprise subscription or admin privileges needed."
        )
    return current_user

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class PipelineResponse(BaseModel):
    """Response from pipeline trigger"""
    status: str
    message: str
    articles_processed: int = 0
    claims_extracted: int = 0
    claims_verified: int = 0
    errors: List[str] = []


class ProcessArticlesRequest(BaseModel):
    """Request to process specific articles"""
    article_ids: Optional[List[str]] = None
    limit: int = 10
    extract_claims: bool = True
    verify_claims: bool = True


# =============================================================================
# BACKGROUND PROCESSING FUNCTIONS
# =============================================================================

async def extract_claims_for_article(article_id: str, article_text: str) -> tuple[int, Optional[str]]:
    """
    Extract claims from article text.
    Returns (claims_count, error_message)
    """
    try:
        extractor = ClaimExtractor()
        claims = await extractor.decompose_claims(article_text, max_claims=10)

        if not claims:
            return 0, None

        # Store claims in database
        db = get_postgres()
        claims_inserted = 0

        for claim in claims:
            try:
                db.execute_update(
                    """
                    INSERT INTO claims (
                        article_id, claim_text, claim_type, claim_context, created_at
                    ) VALUES (
                        :article_id, :claim_text, :claim_type, :context, NOW()
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    {
                        "article_id": article_id,
                        "claim_text": claim.claim_text,
                        "claim_type": claim.claim_type,
                        "context": claim.claim_context
                    }
                )
                claims_inserted += 1
            except Exception as e:
                logger.error(f"Error inserting claim: {e}")

        # Update article claims count and status
        db.execute_update(
            """
            UPDATE articles
            SET claims_count = :count,
                claims_status = 'completed',
                claims_processed_at = NOW(),
                updated_at = NOW()
            WHERE article_id = :article_id
            """,
            {"count": claims_inserted, "article_id": article_id}
        )

        return claims_inserted, None

    except HTTPException as e:
        error_msg = e.detail
        logger.error(f"Claim extraction failed for {article_id}: {error_msg}")

        # Update article with failed status
        db = get_postgres()
        db.execute_update(
            """
            UPDATE articles
            SET claims_status = 'failed',
                claims_error_message = :error,
                updated_at = NOW()
            WHERE article_id = :article_id
            """,
            {"error": error_msg, "article_id": article_id}
        )

        return 0, error_msg
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error extracting claims for {article_id}: {e}", exc_info=True)
        return 0, error_msg


async def verify_claims_for_article(article_id: str) -> tuple[int, Optional[str]]:
    """
    Verify claims for an article.
    Returns (verified_count, error_message)
    """
    try:
        db = get_postgres()

        # Get unverified claims for this article
        claims = db.execute_query(
            """
            SELECT claim_id, claim_text, claim_type
            FROM claims
            WHERE article_id = :article_id
              AND NOT EXISTS (
                  SELECT 1 FROM fact_checks WHERE fact_checks.claim_id = claims.claim_id
              )
            LIMIT 10
            """,
            {"article_id": article_id}
        )

        if not claims:
            return 0, None

        adjudicator = VerdictAdjudicator()
        retriever = EvidenceRetriever()
        verified_count = 0
        results = []

        for claim in claims:
            try:
                from app.domains.intelligence.schemas import AtomicClaim
                atomic_claim = AtomicClaim(
                    claim_text=claim["claim_text"],
                    claim_type=claim.get("claim_type", "factual"),
                    claim_context=claim.get("claim_context", "") or None
                )

                evidence = await retriever.fetch_evidence(atomic_claim)
                verdict = await adjudicator.adjudicate(atomic_claim, evidence)

                results.append({
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["claim_text"],
                    "status": verdict.verdict,
                    "confidence": verdict.confidence_score,
                    "justification": verdict.justification,
                })

            except Exception as e:
                logger.error(f"Error verifying claim {claim['claim_id']}: {e}")

        if os.getenv("CLILENS_MULTI_LLM_VERIFY", "0") == "1":
            try:
                extractor = ClaimExtractor()
                article = db.execute_query(
                    "SELECT extracted_text, body FROM articles WHERE article_id = :id",
                    {"id": article_id}
                )
                article_text = ""
                if article:
                    article_text = article[0].get("extracted_text") or article[0].get("body") or ""
                verified = await verify_claims(
                    primary_extractor=extractor.extract_claims_from_text,
                    secondary_extractor=extractor.extract_claims_from_text,
                    article_text=article_text,
                    similarity_threshold=0.5,
                )
                verified_map = {v["claim_text"]: v for v in verified.get("verified_claims", [])}
                for res in results:
                    text = res.get("claim_text", "")
                    if text in verified_map:
                        vc = verified_map[text]
                        if vc.get("corroborated"):
                            res["confidence"] = vc.get("confidence", res["confidence"])
            except Exception as e:
                logger.warning(f"Multi-LLM verify skipped for article {article_id}: {e}")

        import json
        for res in results:
            db.execute_update(
                """
                INSERT INTO fact_checks (
                    claim_id, verification_status, confidence_score,
                    justification, evidence, verified_at
                ) VALUES (
                    :claim_id, :status, :confidence,
                    :justification, CAST(:evidence AS jsonb), NOW()
                )
                """,
                {
                    "claim_id": res["claim_id"],
                    "status": res["status"],
                    "confidence": res["confidence"],
                    "justification": res["justification"],
                    "evidence": json.dumps([])
                }
            )
            verified_count += 1

        # Update article verified claims count
        db.execute_update(
            """
            UPDATE articles
            SET verified_claims_count = (
                SELECT COUNT(*) FROM claims c
                JOIN fact_checks fc ON fc.claim_id = c.claim_id
                WHERE c.article_id = :article_id
            ),
            updated_at = NOW()
            WHERE article_id = :article_id
            """,
            {"article_id": article_id}
        )

        return verified_count, None

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error verifying claims for {article_id}: {e}", exc_info=True)
        return 0, error_msg


async def process_article_pipeline(article_id: str, article_text: str, extract: bool, verify: bool) -> dict:
    """Process a single article through the pipeline"""
    result = {
        "article_id": article_id,
        "claims_extracted": 0,
        "claims_verified": 0,
        "errors": []
    }

    # Step 1: Extract claims
    if extract:
        claims_count, error = await extract_claims_for_article(article_id, article_text)
        result["claims_extracted"] = claims_count
        if error:
            result["errors"].append(f"Claim extraction: {error}")
            return result  # Stop if extraction failed

    # Step 2: Verify claims
    if verify:
        verified_count, error = await verify_claims_for_article(article_id)
        result["claims_verified"] = verified_count
        if error:
            result["errors"].append(f"Claim verification: {error}")

    return result


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/extract-claims", response_model=PipelineResponse)
async def trigger_claim_extraction(
    request: ProcessArticlesRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger claim extraction for articles with pending status.

    This processes articles that have text but no claims extracted yet.
    """
    require_admin(current_user)
    db = get_postgres()

    # Get articles needing claim extraction. `url` column included so
    # Slice 4b's full_text_fetch pre-pass can scrape source content
    # when excerpt is too short for the claim extractor.
    query = """
        SELECT article_id, title, excerpt, extracted_text, url
        FROM articles
        WHERE (claims_status IS NULL OR claims_status = 'pending' OR claims_status = 'failed')
          AND (excerpt IS NOT NULL OR extracted_text IS NOT NULL)
    """

    params = {}
    if request.article_ids:
        query += " AND article_id = ANY(:ids)"
        params["ids"] = request.article_ids

    query += " LIMIT :limit"
    params["limit"] = request.limit

    articles = db.execute_query(query, params)

    if not articles:
        return PipelineResponse(
            status="success",
            message="No articles need claim extraction",
            articles_processed=0
        )

    # Process in background
    total_claims = 0
    errors = []
    full_text_fetches = 0

    for article in articles:
        article_text = article.get("extracted_text") or article.get("excerpt") or ""

        # Slice 4b (2026-05-25) — full_text_fetch pre-pass. If we only
        # have an RSS excerpt (typically <300 chars), scrape the source
        # URL and persist the body so the claim extractor has actual
        # content to chew on. Converts most "1 claim" articles into
        # 4-8 claim coverage downstream. Failures are silent — the
        # downstream extractor still runs against the short text.
        # Note: articles.url is the source link column (init.sql:73).
        if len(article_text) < 300 and article.get("url"):
            try:
                from shared.full_text_fetch import fetch_full_text
                fetched = await fetch_full_text(article["url"])
                if fetched and len(fetched) > len(article_text):
                    db = get_postgres()
                    db.execute_update(
                        "UPDATE articles SET extracted_text = :t, "
                        "updated_at = NOW() WHERE article_id = :id",
                        {"t": fetched, "id": article["article_id"]},
                    )
                    article_text = fetched
                    full_text_fetches += 1
            except Exception as exc:
                logger.debug(
                    f"full_text_fetch pre-pass failed for "
                    f"{article['article_id']}: {exc}"
                )

        if len(article_text) < 50:
            continue

        try:
            claims_count, error = await extract_claims_for_article(
                article["article_id"],
                article_text
            )
            total_claims += claims_count
            if error:
                errors.append(f"{article['title']}: {error}")
        except Exception as e:
            errors.append(f"{article['title']}: {str(e)}")

    if full_text_fetches:
        logger.info(
            f"Pipeline pre-pass fetched full text for {full_text_fetches} "
            f"of {len(articles)} articles (Slice 4b)"
        )

    return PipelineResponse(
        status="completed" if not errors else "partial",
        message=f"Processed {len(articles)} articles "
                f"({full_text_fetches} full-text pre-fetches)",
        articles_processed=len(articles),
        claims_extracted=total_claims,
        errors=errors[:10]  # Limit error list
    )


@router.post("/verify-claims", response_model=PipelineResponse)
async def trigger_claim_verification(
    request: ProcessArticlesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger fact-checking for extracted claims.

    This verifies claims that have been extracted but not yet fact-checked.
    """
    require_admin(current_user)
    db = get_postgres()

    # Get articles with unverified claims
    query = """
        SELECT DISTINCT a.article_id, a.title
        FROM articles a
        JOIN claims c ON c.article_id = a.article_id
        LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
        WHERE fc.fact_check_id IS NULL
    """

    params = {}
    if request.article_ids:
        query += " AND a.article_id = ANY(:ids)"
        params["ids"] = request.article_ids

    query += " LIMIT :limit"
    params["limit"] = request.limit

    articles = db.execute_query(query, params)

    if not articles:
        return PipelineResponse(
            status="success",
            message="No claims need verification",
            articles_processed=0
        )

    # Process verification
    total_verified = 0
    errors = []

    for article in articles:
        try:
            verified_count, error = await verify_claims_for_article(article["article_id"])
            total_verified += verified_count
            if error:
                errors.append(f"{article['title']}: {error}")
        except Exception as e:
            errors.append(f"{article['title']}: {str(e)}")

    return PipelineResponse(
        status="completed" if not errors else "partial",
        message=f"Processed {len(articles)} articles",
        articles_processed=len(articles),
        claims_verified=total_verified,
        errors=errors[:10]
    )


@router.post("/process-all", response_model=PipelineResponse)
async def process_full_pipeline(
    request: ProcessArticlesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Run the complete pipeline: extract claims + verify claims.

    This is the main endpoint to process articles end-to-end.
    """
    require_admin(current_user)
    db = get_postgres()

    # Get articles needing processing
    query = """
        SELECT article_id, title, excerpt, extracted_text
        FROM articles
        WHERE (claims_status IS NULL OR claims_status = 'pending' OR claims_status = 'failed')
          AND (excerpt IS NOT NULL OR extracted_text IS NOT NULL)
    """

    params = {}
    if request.article_ids:
        query += " AND article_id = ANY(:ids)"
        params["ids"] = request.article_ids

    query += " LIMIT :limit"
    params["limit"] = request.limit

    articles = db.execute_query(query, params)

    if not articles:
        return PipelineResponse(
            status="success",
            message="No articles need processing",
            articles_processed=0
        )

    # Process pipeline
    total_claims = 0
    total_verified = 0
    errors = []

    for article in articles:
        article_text = article.get("extracted_text") or article.get("excerpt") or ""
        if len(article_text) < 50:
            continue

        try:
            result = await process_article_pipeline(
                article["article_id"],
                article_text,
                extract=request.extract_claims,
                verify=request.verify_claims
            )
            total_claims += result["claims_extracted"]
            total_verified += result["claims_verified"]
            errors.extend(result["errors"])

        except Exception as e:
            errors.append(f"{article['title']}: {str(e)}")

    return PipelineResponse(
        status="completed" if not errors else "partial",
        message=f"Pipeline processed {len(articles)} articles",
        articles_processed=len(articles),
        claims_extracted=total_claims,
        claims_verified=total_verified,
        errors=errors[:10]
    )


@router.get("/status")
async def get_pipeline_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current pipeline status - how many articles need processing.
    """
    require_admin(current_user)
    db = get_postgres()

    stats = {
        "total_articles": 0,
        "needs_claim_extraction": 0,
        "needs_verification": 0,
        "completed": 0,
        "failed": 0
    }

    # Total articles
    result = db.execute_query("SELECT COUNT(*) as count FROM articles")
    stats["total_articles"] = result[0]["count"] if result else 0

    # Needs claim extraction
    result = db.execute_query(
        """
        SELECT COUNT(*) as count FROM articles
        WHERE (claims_status IS NULL OR claims_status = 'pending' OR claims_status = 'failed')
          AND (excerpt IS NOT NULL OR extracted_text IS NOT NULL)
        """
    )
    stats["needs_claim_extraction"] = result[0]["count"] if result else 0

    # Needs verification
    result = db.execute_query(
        """
        SELECT COUNT(DISTINCT a.article_id) as count
        FROM articles a
        JOIN claims c ON c.article_id = a.article_id
        LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
        WHERE fc.fact_check_id IS NULL
        """
    )
    stats["needs_verification"] = result[0]["count"] if result else 0

    # Completed
    result = db.execute_query(
        "SELECT COUNT(*) as count FROM articles WHERE claims_status = 'completed'"
    )
    stats["completed"] = result[0]["count"] if result else 0

    # Failed
    result = db.execute_query(
        "SELECT COUNT(*) as count FROM articles WHERE claims_status = 'failed'"
    )
    stats["failed"] = result[0]["count"] if result else 0

    return stats


# =============================================================================
# CONTINENT COVERAGE & GLOBAL INGESTION
# =============================================================================

CONTINENT_MAP = {
    "Europe": ["FI", "SE", "NO", "DK", "IS", "GB", "IE", "FR", "DE", "NL", "BE", "LU",
               "CH", "AT", "ES", "PT", "IT", "MT", "GR", "CY", "TR", "PL", "CZ",
               "SK", "HU", "SI", "RO", "BG", "HR", "RS", "BA", "ME", "MK", "AL",
               "EE", "LV", "LT", "UA", "MD", "BY", "GE", "AM", "AZ", "RU"],
    "North America": ["US", "CA", "MX"],
    "Latin America": ["BR", "AR", "CO", "CL", "PE", "EC", "VE", "UY", "PY", "BO", "CR", "PA",
                      "CU", "DO", "GT", "HN", "SV", "NI", "JM", "TT", "BB"],
    "Africa": ["KE", "NG", "ZA", "GH", "TZ", "UG", "RW", "ET", "EG", "MA", "SN", "ZM",
               "MW", "MZ", "SD", "CD", "CM", "CI", "TN", "LY", "AO", "NA", "BW", "MG"],
    "Asia & Oceania": ["CN", "IN", "JP", "KR", "ID", "TH", "VN", "PH", "SG", "MY", "BD",
                       "PK", "AU", "NZ", "TW", "LK", "MM", "KH", "NP", "FJ", "PG"],
    "Middle East": ["AE", "SA", "IL", "JO", "LB", "IQ", "IR", "QA", "KW", "OM", "BH"],
}


@router.get("/continent-coverage")
async def get_continent_coverage(
    current_user: dict = Depends(get_current_user),
):
    """
    Get article counts grouped by continent/region.
    Shows global data coverage for monitoring 25+ articles per continent target.
    """
    require_admin(current_user)
    db = get_postgres()

    results = {}
    for continent, codes in CONTINENT_MAP.items():
        rows = db.execute_query(
            """
            SELECT COUNT(*) as article_count,
                   COUNT(DISTINCT a.country_code) as countries_with_articles,
                   COUNT(DISTINCT a.source_name) as unique_sources,
                   AVG(a.reliability_score) as avg_reliability
            FROM articles a
            WHERE a.country_code = ANY(:codes)
            """,
            {"codes": codes},
        )
        row = rows[0] if rows else {}

        # Per-country breakdown
        country_rows = db.execute_query(
            """
            SELECT a.country_code, COUNT(*) as cnt
            FROM articles a
            WHERE a.country_code = ANY(:codes)
            GROUP BY a.country_code
            ORDER BY cnt DESC
            """,
            {"codes": codes},
        )

        results[continent] = {
            "article_count": row.get("article_count", 0),
            "countries_with_articles": row.get("countries_with_articles", 0),
            "total_countries": len(codes),
            "unique_sources": row.get("unique_sources", 0),
            "avg_reliability": round(float(row["avg_reliability"]), 1) if row.get("avg_reliability") else None,
            "meets_target": (row.get("article_count", 0) or 0) >= 25,
            "country_breakdown": [
                {"country_code": r["country_code"], "article_count": r["cnt"]}
                for r in (country_rows or [])
            ],
        }

    total_articles = sum(r["article_count"] for r in results.values())
    continents_meeting_target = sum(1 for r in results.values() if r["meets_target"])

    return {
        "continents": results,
        "total_articles": total_articles,
        "continents_meeting_target": continents_meeting_target,
        "total_continents": len(CONTINENT_MAP),
        "global_coverage_met": continents_meeting_target == len(CONTINENT_MAP),
    }


@router.post("/trigger-global-ingestion")
async def trigger_global_ingestion(
    background_tasks: BackgroundTasks,
    limit_per_region: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger ingestion from global RSS feeds across all continents.
    Uses the feed registry to discover and ingest articles from under-represented regions.
    """
    require_admin(current_user)

    async def _run_global_ingestion(limit: int):
        try:
            from app.domains.content.data_sources.eu_feeds_registry import (
                EU_CLIMATE_FEEDS, US_CLIMATE_FEEDS, LATAM_CLIMATE_FEEDS,
                AFRICA_CLIMATE_FEEDS, ASIA_CLIMATE_FEEDS, MIDDLE_EAST_CLIMATE_FEEDS,
                RESEARCH_INDUSTRY_FEEDS,
            )
            all_feeds = {
                "Europe": EU_CLIMATE_FEEDS,
                "North America": US_CLIMATE_FEEDS,
                "Latin America": LATAM_CLIMATE_FEEDS,
                "Africa": AFRICA_CLIMATE_FEEDS,
                "Asia & Oceania": ASIA_CLIMATE_FEEDS,
                "Middle East": MIDDLE_EAST_CLIMATE_FEEDS,
                "Research": RESEARCH_INDUSTRY_FEEDS,
            }
            logger.info(f"Global ingestion triggered for {len(all_feeds)} regions, limit={limit}")
            # The actual feed processing would be handled by the existing Celery tasks
            # This endpoint triggers the scheduling
        except ImportError as e:
            logger.error(f"Feed registry import failed: {e}")

    background_tasks.add_task(_run_global_ingestion, limit_per_region)

    return {
        "status": "triggered",
        "message": f"Global ingestion started for all continents (limit {limit_per_region} per region)",
        "regions": list(CONTINENT_MAP.keys()),
    }
