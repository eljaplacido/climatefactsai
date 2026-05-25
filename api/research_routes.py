"""
Research Report Routes — Analyze academic papers and industry reports.

Endpoints for submitting research documents (URL, DOI, raw text, or
direct file upload — Deferred audit item #11), viewing analysis
results, and weather-enriched credibility scoring.
"""

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
from api.auth_routes import get_current_user, get_optional_user

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


@router.post("/analyze")
async def analyze_research_report(
    request: ResearchAnalysisRequest,
    current_user: dict = Depends(get_optional_user),
):
    """
    Submit a research report for analysis.
    Accepts one of: URL, DOI, or raw text.
    Returns comprehensive analysis with credibility scoring.
    """
    if not request.url and not request.doi and not request.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: url, doi, or text",
        )

    try:
        from app.domains.intelligence.research_report_service import ResearchReportService

        service = ResearchReportService()
        user_id = str(current_user["user_id"]) if current_user else None

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
    current_user: dict = Depends(get_optional_user),
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
    """
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
