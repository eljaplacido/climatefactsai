"""
Research Report Routes — Analyze academic papers and industry reports.

Endpoints for submitting research documents (URL, DOI, or text),
viewing analysis results, and weather-enriched credibility scoring.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user, get_optional_user

logger = setup_logging("research")
router = APIRouter(prefix="/api/research", tags=["Research Reports"])


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
