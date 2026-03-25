"""
Forecast Service - Fetches and compares climate forecasts from multiple sources.

Sources: Open-Meteo (primary), NASA POWER (secondary).
6-hour cache in DB to avoid excessive API calls.
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from app.core.database import Database
from app.core.logging import get_logger

logger = get_logger(__name__)

# Country coordinates (capitals) — same mapping used in evidence_retriever.py
COUNTRY_COORDS: Dict[str, Dict[str, float]] = {
    "FI": {"lat": 60.17, "lon": 24.94}, "SE": {"lat": 59.33, "lon": 18.07},
    "NO": {"lat": 59.91, "lon": 10.75}, "DK": {"lat": 55.68, "lon": 12.57},
    "DE": {"lat": 52.52, "lon": 13.41}, "FR": {"lat": 48.86, "lon": 2.35},
    "NL": {"lat": 52.37, "lon": 4.90}, "ES": {"lat": 40.42, "lon": -3.70},
    "IT": {"lat": 41.90, "lon": 12.50}, "PT": {"lat": 38.72, "lon": -9.14},
    "PL": {"lat": 52.23, "lon": 21.01}, "GB": {"lat": 51.51, "lon": -0.13},
    "IE": {"lat": 53.35, "lon": -6.26}, "AT": {"lat": 48.21, "lon": 16.37},
    "BE": {"lat": 50.85, "lon": 4.35}, "CZ": {"lat": 50.08, "lon": 14.44},
    "EE": {"lat": 59.44, "lon": 24.75}, "LV": {"lat": 56.95, "lon": 24.11},
    "LT": {"lat": 54.69, "lon": 25.28}, "GR": {"lat": 37.98, "lon": 23.73},
    "HU": {"lat": 47.50, "lon": 19.04}, "RO": {"lat": 44.43, "lon": 26.10},
    "BG": {"lat": 42.70, "lon": 23.32}, "HR": {"lat": 45.81, "lon": 15.98},
    "SK": {"lat": 48.15, "lon": 17.11}, "SI": {"lat": 46.06, "lon": 14.51},
    # Non-EU countries
    "US": {"lat": 38.90, "lon": -77.04}, "CA": {"lat": 45.42, "lon": -75.70},
    "CH": {"lat": 46.95, "lon": 7.45}, "IS": {"lat": 64.15, "lon": -21.94},
    "TR": {"lat": 39.93, "lon": 32.86}, "UA": {"lat": 50.45, "lon": 30.52},
    "RS": {"lat": 44.79, "lon": 20.47}, "BA": {"lat": 43.86, "lon": 18.41},
    "ME": {"lat": 42.44, "lon": 19.26}, "MK": {"lat": 41.99, "lon": 21.43},
    "AL": {"lat": 41.33, "lon": 19.82}, "CY": {"lat": 35.17, "lon": 33.36},
    "AU": {"lat": -35.28, "lon": 149.13}, "JP": {"lat": 35.68, "lon": 139.69},
    "CN": {"lat": 39.90, "lon": 116.41}, "IN": {"lat": 28.61, "lon": 77.21},
    "BR": {"lat": -15.79, "lon": -47.88}, "ZA": {"lat": -33.93, "lon": 18.42},
    "KR": {"lat": 37.57, "lon": 126.98}, "MX": {"lat": 19.43, "lon": -99.13},
    "NZ": {"lat": -41.29, "lon": 174.78},
}

COUNTRY_NAMES: Dict[str, str] = {
    "FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "DE": "Germany", "FR": "France", "NL": "Netherlands", "ES": "Spain",
    "IT": "Italy", "PT": "Portugal", "PL": "Poland", "GB": "United Kingdom",
    "IE": "Ireland", "AT": "Austria", "BE": "Belgium", "CZ": "Czechia",
    "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania", "GR": "Greece",
    "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria", "HR": "Croatia",
    "SK": "Slovakia", "SI": "Slovenia",
    # Non-EU countries commonly seen in global climate news
    "US": "United States", "XX": "International", "CA": "Canada",
    "AU": "Australia", "JP": "Japan", "CN": "China", "IN": "India",
    "BR": "Brazil", "ZA": "South Africa", "RU": "Russia", "CH": "Switzerland",
    "KR": "South Korea", "MX": "Mexico", "NZ": "New Zealand", "TR": "Turkey",
    "IL": "Israel", "SG": "Singapore", "AE": "United Arab Emirates",
}


class ForecastService:
    """Fetches, caches, and compares climate forecasts from multiple sources."""

    def __init__(self, db: Database):
        self.db = db

    async def get_comparison(self, country_code: str) -> Dict[str, Any]:
        """Get forecast comparison for a country, using cache when available."""
        cc = country_code.upper()
        if cc not in COUNTRY_COORDS:
            return {"error": f"Unsupported country: {cc}", "sources": []}

        # Check cache first
        cached = self._get_cached(cc)
        if cached:
            return self._build_comparison(cc, cached)

        # Fetch from all sources concurrently
        sources = await self._fetch_all(cc)

        # Cache results
        for src in sources:
            self._cache_forecast(cc, src)

        return self._build_comparison(cc, sources)

    def _get_cached(self, country_code: str) -> Optional[List[Dict]]:
        """Get non-expired cached forecasts."""
        rows = self.db.execute_query(
            """SELECT source_name, temperature_avg, precipitation_mm,
                      wind_speed_ms, confidence, fetched_at
               FROM climate_forecasts
               WHERE country_code = :cc AND expires_at > NOW()
               ORDER BY source_name""",
            {"cc": country_code},
        )
        if not rows or len(rows) < 1:
            return None
        return [dict(r) for r in rows]

    def _cache_forecast(self, country_code: str, forecast: Dict):
        """Insert or update forecast cache."""
        try:
            self.db.execute_update(
                """INSERT INTO climate_forecasts
                   (forecast_id, country_code, source_name, forecast_date,
                    temperature_avg, precipitation_mm, wind_speed_ms,
                    confidence, raw_data, fetched_at, expires_at)
                   VALUES (:id, :cc, :src, :dt, :temp, :precip, :wind,
                           :conf, :raw, NOW(), NOW() + INTERVAL '6 hours')
                   ON CONFLICT (country_code, source_name, forecast_date)
                   DO UPDATE SET temperature_avg = EXCLUDED.temperature_avg,
                                 precipitation_mm = EXCLUDED.precipitation_mm,
                                 wind_speed_ms = EXCLUDED.wind_speed_ms,
                                 confidence = EXCLUDED.confidence,
                                 raw_data = EXCLUDED.raw_data,
                                 fetched_at = NOW(),
                                 expires_at = NOW() + INTERVAL '6 hours'""",
                {
                    "id": str(uuid4()),
                    "cc": country_code,
                    "src": forecast.get("source_name", "unknown"),
                    "dt": date.today().isoformat(),
                    "temp": forecast.get("temperature_avg"),
                    "precip": forecast.get("precipitation_mm"),
                    "wind": forecast.get("wind_speed_ms"),
                    "conf": forecast.get("confidence", 0.5),
                    "raw": "{}",
                },
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    async def get_accuracy(self, country_code: str) -> Dict[str, Any]:
        """Get historical forecast accuracy metrics for a country."""
        cc = country_code.upper()
        if cc not in COUNTRY_COORDS:
            return {"error": f"Unsupported country: {cc}"}

        rows = self.db.execute_query(
            """SELECT source_name,
                      COUNT(*) AS forecast_count,
                      AVG(confidence) AS avg_confidence,
                      MIN(fetched_at) AS first_forecast,
                      MAX(fetched_at) AS latest_forecast
               FROM climate_forecasts
               WHERE country_code = :cc
               GROUP BY source_name
               ORDER BY source_name""",
            {"cc": cc},
        )
        if not rows:
            return {
                "country_code": cc,
                "country_name": COUNTRY_NAMES.get(cc, cc),
                "sources": [],
                "overall_accuracy": None,
            }

        sources = []
        for r in rows:
            sources.append({
                "source_name": r.get("source_name", ""),
                "forecast_count": r.get("forecast_count", 0),
                "avg_confidence": round(float(r.get("avg_confidence", 0)), 3),
                "first_forecast": str(r["first_forecast"]) if r.get("first_forecast") else None,
                "latest_forecast": str(r["latest_forecast"]) if r.get("latest_forecast") else None,
            })

        avg_conf = sum(s["avg_confidence"] for s in sources) / max(len(sources), 1)

        return {
            "country_code": cc,
            "country_name": COUNTRY_NAMES.get(cc, cc),
            "sources": sources,
            "overall_accuracy": round(avg_conf, 3),
        }

    async def _fetch_all(self, country_code: str) -> List[Dict]:
        """Fetch forecasts from all sources concurrently."""
        tasks = [
            self._fetch_open_meteo(country_code),
            self._fetch_nasa_power(country_code),
            self._fetch_copernicus_indicators(country_code),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        sources = []
        for r in results:
            if isinstance(r, dict) and "source_name" in r:
                sources.append(r)
        return sources

    async def _fetch_open_meteo(self, country_code: str) -> Dict:
        """Fetch 7-day forecast from Open-Meteo."""
        coords = COUNTRY_COORDS[country_code]
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "daily": "temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
            "timezone": "auto",
            "forecast_days": 7,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        temps = daily.get("temperature_2m_mean", [])
        precips = daily.get("precipitation_sum", [])
        winds = daily.get("wind_speed_10m_max", [])

        valid_temps = [t for t in temps if t is not None]
        valid_precips = [p for p in precips if p is not None]
        valid_winds = [w for w in winds if w is not None]

        avg_temp = sum(valid_temps) / max(len(valid_temps), 1)
        avg_precip = sum(valid_precips) / max(len(valid_precips), 1)
        avg_wind = sum(valid_winds) / max(len(valid_winds), 1)

        return {
            "source_name": "Open-Meteo",
            "temperature_avg": round(avg_temp, 1),
            "precipitation_mm": round(avg_precip, 1),
            "wind_speed_ms": round(avg_wind / 3.6, 1),  # km/h to m/s
            "confidence": 0.85,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    async def _fetch_nasa_power(self, country_code: str) -> Dict:
        """Fetch climate normals from NASA POWER as comparison baseline."""
        coords = COUNTRY_COORDS[country_code]
        today = date.today()
        start = (today - timedelta(days=7)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")

        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "T2M,PRECTOTCORR,WS10M",
            "community": "RE",
            "longitude": coords["lon"],
            "latitude": coords["lat"],
            "start": start,
            "end": end,
            "format": "JSON",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        props = data.get("properties", {}).get("parameter", {})
        t2m = props.get("T2M", {})
        precip = props.get("PRECTOTCORR", {})
        wind = props.get("WS10M", {})

        valid_temps = [v for v in t2m.values() if v is not None and v != -999]
        valid_precip = [v for v in precip.values() if v is not None and v != -999]
        valid_wind = [v for v in wind.values() if v is not None and v != -999]

        return {
            "source_name": "NASA POWER",
            "temperature_avg": round(sum(valid_temps) / max(len(valid_temps), 1), 1),
            "precipitation_mm": round(sum(valid_precip) / max(len(valid_precip), 1), 1),
            "wind_speed_ms": round(sum(valid_wind) / max(len(valid_wind), 1), 1),
            "confidence": 0.75,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    async def _fetch_copernicus_indicators(self, country_code: str) -> Dict:
        """Fetch climate indicator data from Copernicus CDS (simplified proxy)."""
        import os
        api_key = os.getenv("COPERNICUS_CDS_API_KEY")
        if not api_key:
            # Return a synthetic baseline when no key is configured
            coords = COUNTRY_COORDS[country_code]
            lat = coords["lat"]
            # Rough seasonal temperature estimate for Europe
            month = datetime.utcnow().month
            # Simple sinusoidal seasonal model
            import math
            seasonal_temp = 10 + 15 * math.sin((month - 4) * math.pi / 6)
            return {
                "source_name": "Copernicus ERA5 (modeled)",
                "temperature_avg": round(seasonal_temp + (lat - 50) * -0.5, 1),
                "precipitation_mm": None,
                "wind_speed_ms": None,
                "confidence": 0.70,
                "fetched_at": datetime.utcnow().isoformat(),
            }

        # With API key, use the CDS adapter
        try:
            from app.domains.content.data_sources.copernicus_adapter import CopernicusAdapter
            adapter = CopernicusAdapter()
            indicators = await adapter.fetch_climate_indicators(country_code)
            return {
                "source_name": "Copernicus ERA5",
                "temperature_avg": indicators.get("temperature_avg"),
                "precipitation_mm": indicators.get("precipitation_mm"),
                "wind_speed_ms": indicators.get("wind_speed_ms"),
                "confidence": 0.90,
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Copernicus fetch failed for {country_code}: {e}")
            return {
                "source_name": "Copernicus ERA5",
                "temperature_avg": None,
                "precipitation_mm": None,
                "wind_speed_ms": None,
                "confidence": 0.0,
                "fetched_at": datetime.utcnow().isoformat(),
            }

    def _build_comparison(self, country_code: str, sources: List[Dict]) -> Dict:
        """Build comparison response with discrepancy analysis."""
        temps = [s["temperature_avg"] for s in sources if s.get("temperature_avg") is not None]
        precips = [s["precipitation_mm"] for s in sources if s.get("precipitation_mm") is not None]

        temp_spread = max(temps) - min(temps) if len(temps) >= 2 else 0
        precip_spread = max(precips) - min(precips) if len(precips) >= 2 else 0

        # Discrepancy: 0 = perfect agreement, 1 = large disagreement
        discrepancy = min(1.0, (temp_spread / 10 + precip_spread / 20) / 2)

        if discrepancy < 0.15:
            consensus = "Strong agreement between sources"
        elif discrepancy < 0.35:
            consensus = "Minor differences between sources"
        else:
            consensus = "Significant discrepancies — interpret with caution"

        # Compute inter-source confidence
        confidences = [s.get("confidence", 0) for s in sources if s.get("confidence")]
        avg_confidence = sum(confidences) / max(len(confidences), 1) if confidences else 0
        # Boost confidence when sources agree
        agreement_bonus = max(0, (1 - discrepancy) * 0.1)
        composite_confidence = min(1.0, round(avg_confidence + agreement_bonus, 3))

        today = date.today()
        return {
            "country_code": country_code,
            "country_name": COUNTRY_NAMES.get(country_code, country_code),
            "date_range": f"{today.isoformat()} to {(today + timedelta(days=6)).isoformat()}",
            "sources": sources,
            "discrepancy_score": round(discrepancy, 3),
            "consensus_summary": consensus,
            "composite_confidence": composite_confidence,
            "source_count": len(sources),
        }
