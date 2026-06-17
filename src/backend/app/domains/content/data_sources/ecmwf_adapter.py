"""
ECMWF & Weather Data Aggregator — Multi-source weather data integration.

Aggregates from: Open-Meteo Climate API, Air Quality API, Flood (GloFAS) API,
Marine API, NOAA Climate Data Online, and NASA POWER.
"""

import asyncio
import os
from datetime import date, timedelta
from typing import Any, Dict, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

OPEN_METEO_CLIMATE = "https://climate-api.open-meteo.com/v1/climate"
OPEN_METEO_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_FLOOD = "https://flood-api.open-meteo.com/v1/flood"
OPEN_METEO_MARINE = "https://marine-api.open-meteo.com/v1/marine"
NOAA_CDO_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
NASA_POWER_BASE = "https://power.larc.nasa.gov/api/temporal"


async def fetch_climate_normals(lat: float, lon: float, start_year: int = 1991, end_year: int = 2020) -> Optional[Dict[str, Any]]:
    """Fetch 30-year climate normals from Open-Meteo Climate API (CMIP6)."""
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{start_year}-01-01", "end_date": f"{end_year}-12-31",
        "models": "EC_Earth3P_HR",
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(OPEN_METEO_CLIMATE, params=params)
            resp.raise_for_status()
            data = resp.json()
        daily = data.get("daily", {})
        return {"source": "Open-Meteo Climate (CMIP6)", "period": f"{start_year}-{end_year}",
                "location": {"lat": lat, "lon": lon}, "dates": daily.get("time", []),
                "temperature_mean": daily.get("temperature_2m_mean", []),
                "precipitation_sum": daily.get("precipitation_sum", [])}
    except Exception as e:
        logger.error(f"Climate normals fetch failed: {e}")
        return None


async def fetch_air_quality(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch current air quality data from Open-Meteo."""
    params = {"latitude": lat, "longitude": lon,
              "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,european_aqi",
              "timezone": "auto"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPEN_METEO_AIR_QUALITY, params=params)
            resp.raise_for_status()
            data = resp.json()
        current = data.get("current", {})
        return {"source": "Open-Meteo Air Quality", "pm2_5": current.get("pm2_5"),
                "pm10": current.get("pm10"), "ozone": current.get("ozone"),
                "no2": current.get("nitrogen_dioxide"), "european_aqi": current.get("european_aqi")}
    except Exception as e:
        logger.error(f"Air quality fetch failed: {e}")
        return None


async def fetch_flood_data(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch river flood forecast data from Open-Meteo / GloFAS."""
    params = {"latitude": lat, "longitude": lon,
              "daily": "river_discharge,river_discharge_mean,river_discharge_max", "forecast_days": 7}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPEN_METEO_FLOOD, params=params)
            resp.raise_for_status()
            data = resp.json()
        daily = data.get("daily", {})
        return {"source": "Open-Meteo Flood (GloFAS)", "dates": daily.get("time", []),
                "river_discharge": daily.get("river_discharge", [])}
    except Exception as e:
        logger.warning(f"Flood data fetch failed: {e}")
        return None


async def fetch_marine_data(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch marine/ocean weather data from Open-Meteo Marine API."""
    params = {"latitude": lat, "longitude": lon,
              "current": "wave_height,wave_period,wave_direction",
              "daily": "wave_height_max,wave_period_max", "forecast_days": 7}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPEN_METEO_MARINE, params=params)
            resp.raise_for_status()
            data = resp.json()
        current = data.get("current", {})
        return {"source": "Open-Meteo Marine", "current_wave_height_m": current.get("wave_height"),
                "current_wave_period_s": current.get("wave_period")}
    except Exception as e:
        logger.warning(f"Marine data fetch failed: {e}")
        return None


async def fetch_noaa_climate_data(country_code: str, dataset: str = "GHCND") -> Optional[Dict[str, Any]]:
    """Fetch climate data from NOAA Climate Data Online API."""
    api_token = os.getenv("NOAA_API_TOKEN")
    if not api_token:
        return None
    end = date.today()
    start = end - timedelta(days=30)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{NOAA_CDO_BASE}/data",
                                     params={"datasetid": dataset, "locationid": f"FIPS:{country_code}",
                                             "startdate": start.isoformat(), "enddate": end.isoformat(), "limit": 100},
                                     headers={"token": api_token})
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception as e:
        logger.error(f"NOAA fetch failed: {e}")
        return None


async def fetch_nasa_power_data(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch solar and meteorological data from NASA POWER API (free, no key)."""
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=30)
    params = {"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,WS2M,ALLSKY_SFC_SW_DWN",
              "community": "RE", "longitude": lon, "latitude": lat,
              "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{NASA_POWER_BASE}/daily/point", params=params)
            resp.raise_for_status()
            data = resp.json()
        return {"source": "NASA POWER", "location": {"lat": lat, "lon": lon},
                "parameters": data.get("properties", {}).get("parameter", {})}
    except Exception as e:
        logger.error(f"NASA POWER fetch failed: {e}")
        return None


async def get_comprehensive_weather_context(lat: float, lon: float, country_code: str = "") -> Dict[str, Any]:
    """Aggregate weather data from all available sources for a location."""
    from app.domains.content.data_sources.open_meteo_adapter import fetch_current_weather

    context: Dict[str, Any] = {
        "location": {"lat": lat, "lon": lon, "country_code": country_code},
        "sources_queried": [], "sources_successful": [],
    }

    results = await asyncio.gather(
        fetch_current_weather(lat, lon),
        fetch_air_quality(lat, lon),
        fetch_climate_normals(lat, lon),
        fetch_nasa_power_data(lat, lon),
        return_exceptions=True,
    )

    source_names = ["open_meteo_current", "air_quality", "climate_normals", "nasa_power"]
    for name, result in zip(source_names, results):
        context["sources_queried"].append(name)
        if isinstance(result, Exception):
            logger.warning(f"Weather source {name} failed: {result}")
        elif result:
            context[name] = result
            context["sources_successful"].append(name)

    return context
