"""
Forecast comparison routes — multi-source climate forecast comparison per country.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, field_serializer

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging
from app.domains.content.forecast_service import ForecastService

logger = setup_logging("forecast-api")
router = APIRouter(prefix="/api/forecasts", tags=["Forecasts"])


class ForecastSourceResponse(BaseModel):
    source_name: str
    temperature_avg: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    confidence: float = 0.5
    fetched_at: Optional[Union[str, datetime]] = None

    @field_serializer("fetched_at")
    def serialize_fetched_at(self, v: Any) -> Optional[str]:
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class ForecastComparisonResponse(BaseModel):
    country_code: str
    country_name: str
    date_range: str
    sources: List[ForecastSourceResponse]
    discrepancy_score: float
    consensus_summary: str
    composite_confidence: Optional[float] = None
    source_count: Optional[int] = None


class AccuracySourceResponse(BaseModel):
    source_name: str
    forecast_count: int = 0
    avg_confidence: float = 0.0
    first_forecast: Optional[str] = None
    latest_forecast: Optional[str] = None


class AccuracyResponse(BaseModel):
    country_code: str
    country_name: str
    sources: List[AccuracySourceResponse]
    overall_accuracy: Optional[float] = None


@router.get("/{country_code}", response_model=ForecastComparisonResponse)
async def get_forecast_comparison(
    country_code: str,
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Get multi-source climate forecast comparison for a country.

    Compares forecasts from Open-Meteo and NASA POWER with 6-hour caching.
    Returns discrepancy score and consensus summary.
    """
    db = get_postgres()
    service = ForecastService(db)

    try:
        comparison = await service.get_comparison(country_code.upper())
        if "error" in comparison:
            raise HTTPException(status_code=400, detail=comparison["error"])
        return ForecastComparisonResponse(**comparison)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast comparison failed for {country_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve forecast comparison."
        )


@router.get("/{country_code}/accuracy", response_model=AccuracyResponse)
async def get_forecast_accuracy(
    country_code: str,
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Get historical forecast accuracy metrics for a country.

    Shows per-source forecast count, average confidence, and date range.
    """
    db = get_postgres()
    service = ForecastService(db)

    try:
        result = await service.get_accuracy(country_code.upper())
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return AccuracyResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast accuracy failed for {country_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve forecast accuracy."
        )


@router.get("/", response_model=List[str])
async def list_supported_countries():
    """List country codes supported for forecast comparison."""
    from app.domains.content.forecast_service import COUNTRY_COORDS
    return sorted(COUNTRY_COORDS.keys())
