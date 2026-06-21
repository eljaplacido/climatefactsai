"""
Research Report Routes — Analyze academic papers and industry reports.

Endpoints for submitting research documents (URL, DOI, raw text, or
direct file upload — Deferred audit item #11), viewing analysis
results, and weather-enriched credibility scoring.
"""

import json
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
    status,
)
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user
from api.quota_service import QuotaService
from api.rate_limiter import check_premium_feature

logger = setup_logging("research")
router = APIRouter(prefix="/api/research", tags=["Research Reports"])

# Deferred #11 (2026-05-25) — direct file upload cap. 25 MiB lets the
# common 100-page sustainability report or thesis through while
# rejecting accidentally-uploaded videos / archives.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class ResearchAnalysisRequest(BaseModel):
    url: Optional[str] = Field(None, description="URL to PDF or research report")
    doi: Optional[str] = Field(None, description="DOI identifier (e.g., 10.1038/s41586-021-03984-4)")
    text: Optional[str] = Field(None, description="Raw text content to analyze")


class WeatherEnrichRequest(BaseModel):
    article_id: str


@router.get("/analyses")
async def list_recent_research_analyses(
    limit: int = 20,
    status_filter: str = "completed",
):
    """List recent research-analysis runs. Powers the /research page
    'Recent worked analyses' panel — the user complaint was that the
    research surface showed feed subscriptions but no actual analytical
    output like the article surface.

    Returns each url_analyses row with its top-level scores so the FE
    can render a scorecard per analysis.
    """
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT analysis_id::text AS analysis_id,
                      submitted_url,
                      title,
                      status,
                      overall_credibility,
                      reliability_score,
                      processing_time_ms,
                      created_at,
                      completed_at
               FROM url_analyses
               WHERE status = :s
               ORDER BY completed_at DESC NULLS LAST, created_at DESC
               LIMIT :n""",
            {"s": status_filter, "n": max(1, min(limit, 100))},
        ) or []
    except Exception as exc:
        logger.warning(f"research/analyses query failed: {exc}")
        rows = []
    return {
        "analyses": [
            {
                "analysis_id": r["analysis_id"],
                "submitted_url": r.get("submitted_url"),
                "title": r.get("title"),
                "status": r.get("status"),
                "overall_credibility": r.get("overall_credibility"),
                "reliability_score": r.get("reliability_score"),
                "processing_time_ms": r.get("processing_time_ms"),
                "created_at": str(r["created_at"]) if r.get("created_at") else None,
                "completed_at": str(r["completed_at"]) if r.get("completed_at") else None,
            }
            for r in rows
        ],
        "total": len(rows),
        "status_filter": status_filter,
    }


def _coerce_json(value, default):
    """jsonb columns normally come back as parsed list/dict via psycopg, but
    tolerate a raw str (older rows / different driver) by parsing it."""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return default


@router.get("/analyses/{analysis_id}")
async def get_research_analysis(analysis_id: str):
    """Full readable analysis for one completed url_analyses run (F8a).

    Powers /research/analysis/{id} — a human-readable report (title, claims,
    fact-checks, credibility) instead of the raw provenance JSON the panel used
    to link to. Public + completed-only, matching the public list endpoint.
    """
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT analysis_id::text AS analysis_id,
                      submitted_url, title, source_name, source_domain,
                      status, overall_credibility, reliability_score,
                      extracted_claims, fact_checks, evidence,
                      processing_time_ms, created_at, completed_at
               FROM url_analyses
               WHERE analysis_id = :id""",
            {"id": analysis_id},
        ) or []
    except Exception as exc:
        logger.warning(f"research/analyses/{analysis_id} query failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not load analysis")

    if not rows:
        raise HTTPException(status_code=404, detail="Analysis not found")
    r = rows[0]
    if r.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Analysis not completed")

    return {
        "analysis_id": r["analysis_id"],
        "submitted_url": r.get("submitted_url"),
        "title": r.get("title"),
        "source_name": r.get("source_name") or r.get("source_domain"),
        "status": r.get("status"),
        "overall_credibility": r.get("overall_credibility"),
        "reliability_score": r.get("reliability_score"),
        "claims": _coerce_json(r.get("extracted_claims"), []),
        "fact_checks": _coerce_json(r.get("fact_checks"), []),
        "evidence": _coerce_json(r.get("evidence"), []),
        "processing_time_ms": r.get("processing_time_ms"),
        "created_at": str(r["created_at"]) if r.get("created_at") else None,
        "completed_at": str(r["completed_at"]) if r.get("completed_at") else None,
    }


@router.post("/analyze")
async def analyze_research_report(
    request: ResearchAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a research report for analysis.
    Accepts one of: URL, DOI, or raw text.
    Returns comprehensive analysis with credibility scoring.
    """
    if not check_premium_feature(current_user.get("tier"), "url_analysis"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "premium_feature_required",
                "feature": "url_analysis",
                "current_tier": current_user.get("subscription_tier", "freemium"),
                "required_tier": "standard",
                "upgrade_url": "/dashboard/subscription",
                "message": "URL analysis requires a Standard subscription or higher.",
            },
        )

    if not request.url and not request.doi and not request.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: url, doi, or text",
        )

    try:
        from app.domains.intelligence.research_report_service import ResearchReportService

        service = ResearchReportService()
        user_id = str(current_user["user_id"])

        result = await service.analyze_report(
            url=request.url,
            doi=request.doi,
            text=request.text,
            user_id=user_id,
        )
        return result

    except Exception as e:
        logger.error(f"Research analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Research analysis failed",
        )


@router.post("/upload")
async def upload_research_document(
    file: UploadFile = File(..., description="PDF, DOCX, TXT, MD, or HTML file"),
    doi: Optional[str] = Form(None, description="Optional DOI to attach"),
    current_user: dict = Depends(get_current_user),
):
    """Submit a research document by direct file upload.

    Closes audit deferred item #11 — previously /research/analyze took
    only url/doi/text, so a researcher couldn't drop a local thesis or
    sustainability report PDF without first hosting it publicly.

    Supports: PDF (PyPDF2, up to 100 pages), DOCX (python-docx with
    zipfile XML fallback when the package isn't installed), TXT, MD,
    HTML. Text is capped at 200 KB per the shared extractor (handles
    100+ page documents — earlier "50KB cap" mentioned in the audit
    only applied to the URL-fallback HTML path, not file uploads).

    The extracted text is fed to the same ResearchReportService used
    by POST /research/analyze so the response shape is identical.

    End2End audit gap (2026-05-27 §6.5): this endpoint was ungated — a
    free-tier user could run a 25 MiB PDF through heavy LLM extraction
    for free. Now requires Standard+ ("document_ingestion"). Free-tier
    users can still paste raw text into /api/research/analyze.
    """
    if not check_premium_feature(current_user, "document_ingestion"):
        tier = current_user.get("subscription_tier", "freemium")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "premium_feature_required",
                "feature": "document_ingestion",
                "current_tier": tier,
                "required_tier": "standard",
                "upgrade_url": "/dashboard/subscription",
                "message": (
                    "Research document upload requires a Standard subscription "
                    "or higher. Free-tier users can paste raw text via POST "
                    "/api/research/analyze with the `text` field."
                ),
            },
        )

    # Size guard — read at most MAX_UPLOAD_BYTES + 1 to detect overage.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024*1024)} MiB. "
                "For larger documents, host the file publicly and use POST "
                "/api/research/analyze with the url parameter."
            ),
        )
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")

    # Reuse the article-ingestion file-type extractor — it handles PDF,
    # DOCX (with zipfile fallback), TXT, MD, HTML. Underscore-prefixed
    # but module-level + the only "public" file-decoding helper we have.
    try:
        from api.article_ingestion_routes import _extract_text_from_upload
        text = _extract_text_from_upload(
            content,
            file.filename or "upload",
            file.content_type or "",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"upload: text extraction failed for {file.filename}: {exc}")
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract text from {file.filename}: {type(exc).__name__}",
        )

    if not text or len(text) < 200:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Extracted text is too short ({len(text) if text else 0} chars). "
                "This usually means the file is scanned/image-only (no embedded "
                "text layer) or the format isn't supported. Try OCR'ing the PDF "
                "first or paste the text directly via POST /api/research/analyze "
                "with the `text` field."
            ),
        )

    try:
        from app.domains.intelligence.research_report_service import ResearchReportService
        service = ResearchReportService()
        user_id = str(current_user["user_id"]) if current_user else None
        result = await service.analyze_report(
            text=text,
            doi=doi,
            user_id=user_id,
        )
        # Surface useful upload-specific metadata so the FE can show
        # "32 pages processed, 187,000 chars analysed" even if the
        # downstream service didn't echo it.
        if isinstance(result, dict):
            result.setdefault("source", "upload")
            result.setdefault("filename", file.filename)
            result.setdefault("text_length", len(text))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"upload analysis failed for {file.filename}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {type(exc).__name__}",
        )


@router.post("/weather-enrich")
async def weather_enrich_article(
    request: WeatherEnrichRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Enrich an article's credibility score with weather verification.
    Cross-references article claims with actual meteorological data.
    """
    if not check_premium_feature(current_user.get("tier"), "weather_context"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "premium_feature_required",
                "feature": "weather_context",
                "current_tier": current_user.get("subscription_tier", "freemium"),
                "required_tier": "standard",
                "upgrade_url": "/dashboard/subscription",
                "message": "Weather-enriched scoring requires a Standard subscription or higher.",
            },
        )

    try:
        from app.domains.intelligence.weather_enriched_scoring import WeatherEnrichedScorer

        scorer = WeatherEnrichedScorer()
        result = await scorer.compute_weather_enriched_score(request.article_id)

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Weather enrichment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Weather enrichment failed",
        )
