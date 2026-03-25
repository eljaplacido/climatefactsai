"""
Open-Meteo Adapter — Free weather & climate data API integration.

Provides current weather, historical climate data, and forecasts.
No authentication required. Primary verification source for weather/climate claims.

API docs: https://open-meteo.com/en/docs
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

OPEN_METEO_BASE = "https://api.open-meteo.com/v1"
OPEN_METEO_HISTORICAL = "https://archive-api.open-meteo.com/v1/archive"


async def fetch_current_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Fetch current weather conditions for a location.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dict with temperature, humidity, wind, precipitation, or None on error.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
        "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{OPEN_METEO_BASE}/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        return {
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_ms": round(current.get("wind_speed_10m", 0) / 3.6, 1),
            "precipitation_mm": current.get("precipitation"),
            "weather_code": current.get("weather_code"),
            "timezone": data.get("timezone"),
        }
    except Exception as e:
        logger.error(f"Open-Meteo current weather failed: {e}")
        return None


async def fetch_historical_climate(
    lat: float, lon: float, start: date, end: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch historical daily climate data for a location and date range.

    Args:
        lat: Latitude
        lon: Longitude
        start: Start date
        end: End date (max 1 year range recommended)

    Returns:
        Dict with daily arrays (dates, temps, precipitation, wind), or None.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(OPEN_METEO_HISTORICAL, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        return {
            "dates": daily.get("time", []),
            "temperature_mean": daily.get("temperature_2m_mean", []),
            "temperature_max": daily.get("temperature_2m_max", []),
            "temperature_min": daily.get("temperature_2m_min", []),
            "precipitation_sum": daily.get("precipitation_sum", []),
            "wind_speed_max": daily.get("wind_speed_10m_max", []),
        }
    except Exception as e:
        logger.error(f"Open-Meteo historical data failed: {e}")
        return None


async def fetch_forecast(
    lat: float, lon: float, days: int = 7
) -> Optional[Dict[str, Any]]:
    """
    Fetch weather forecast for up to 16 days.

    Args:
        lat: Latitude
        lon: Longitude
        days: Forecast days (1-16)

    Returns:
        Dict with daily forecast arrays, or None.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": min(days, 16),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{OPEN_METEO_BASE}/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        return {
            "dates": daily.get("time", []),
            "temperature_mean": daily.get("temperature_2m_mean", []),
            "temperature_max": daily.get("temperature_2m_max", []),
            "temperature_min": daily.get("temperature_2m_min", []),
            "precipitation_sum": daily.get("precipitation_sum", []),
            "precipitation_probability": daily.get("precipitation_probability_max", []),
            "wind_speed_max": daily.get("wind_speed_10m_max", []),
        }
    except Exception as e:
        logger.error(f"Open-Meteo forecast failed: {e}")
        return None
