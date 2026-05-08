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
    # Europe — EU & EEA
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
    # Europe — non-EU
    "CH": {"lat": 46.95, "lon": 7.45}, "IS": {"lat": 64.15, "lon": -21.94},
    "TR": {"lat": 39.93, "lon": 32.86}, "UA": {"lat": 50.45, "lon": 30.52},
    "RS": {"lat": 44.79, "lon": 20.47}, "BA": {"lat": 43.86, "lon": 18.41},
    "ME": {"lat": 42.44, "lon": 19.26}, "MK": {"lat": 41.99, "lon": 21.43},
    "AL": {"lat": 41.33, "lon": 19.82}, "CY": {"lat": 35.17, "lon": 33.36},
    "BY": {"lat": 53.90, "lon": 27.57}, "MD": {"lat": 47.01, "lon": 28.86},
    "RU": {"lat": 55.76, "lon": 37.62}, "MT": {"lat": 35.90, "lon": 14.51},
    "LU": {"lat": 49.61, "lon": 6.13}, "LI": {"lat": 47.14, "lon": 9.52},
    "MC": {"lat": 43.73, "lon": 7.42}, "AD": {"lat": 42.51, "lon": 1.52},
    "XK": {"lat": 42.67, "lon": 21.17}, "SM": {"lat": 43.94, "lon": 12.45},
    "VA": {"lat": 41.90, "lon": 12.45},
    # North America
    "US": {"lat": 38.90, "lon": -77.04}, "CA": {"lat": 45.42, "lon": -75.70},
    "MX": {"lat": 19.43, "lon": -99.13}, "GL": {"lat": 64.18, "lon": -51.72},
    # Central America & Caribbean
    "GT": {"lat": 14.63, "lon": -90.51}, "HN": {"lat": 14.07, "lon": -87.19},
    "SV": {"lat": 13.69, "lon": -89.22}, "NI": {"lat": 12.11, "lon": -86.24},
    "CR": {"lat": 9.93, "lon": -84.08}, "PA": {"lat": 8.98, "lon": -79.52},
    "CU": {"lat": 23.11, "lon": -82.37}, "DO": {"lat": 18.47, "lon": -69.90},
    "HT": {"lat": 18.54, "lon": -72.34}, "JM": {"lat": 18.00, "lon": -76.79},
    "TT": {"lat": 10.66, "lon": -61.51}, "BZ": {"lat": 17.25, "lon": -88.77},
    "BS": {"lat": 25.05, "lon": -77.36}, "BB": {"lat": 13.10, "lon": -59.62},
    "AG": {"lat": 17.12, "lon": -61.85}, "GD": {"lat": 12.06, "lon": -61.75},
    "DM": {"lat": 15.30, "lon": -61.39}, "KN": {"lat": 17.30, "lon": -62.73},
    "LC": {"lat": 14.01, "lon": -60.99}, "VC": {"lat": 13.16, "lon": -61.22},
    # South America
    "BR": {"lat": -15.79, "lon": -47.88}, "AR": {"lat": -34.60, "lon": -58.38},
    "CO": {"lat": 4.71, "lon": -74.07}, "CL": {"lat": -33.45, "lon": -70.67},
    "PE": {"lat": -12.05, "lon": -77.03}, "EC": {"lat": -0.18, "lon": -78.47},
    "VE": {"lat": 10.49, "lon": -66.88}, "BO": {"lat": -19.04, "lon": -65.26},
    "PY": {"lat": -25.26, "lon": -57.58}, "UY": {"lat": -34.88, "lon": -56.17},
    "GY": {"lat": 6.80, "lon": -58.16}, "SR": {"lat": 5.85, "lon": -55.17},
    # Africa
    "ZA": {"lat": -33.93, "lon": 18.42}, "NG": {"lat": 9.06, "lon": 7.49},
    "KE": {"lat": -1.29, "lon": 36.82}, "EG": {"lat": 30.04, "lon": 31.24},
    "ET": {"lat": 9.02, "lon": 38.75}, "GH": {"lat": 5.56, "lon": -0.19},
    "TZ": {"lat": -6.16, "lon": 35.75}, "UG": {"lat": 0.35, "lon": 32.58},
    "RW": {"lat": -1.94, "lon": 29.87}, "SN": {"lat": 14.69, "lon": -17.44},
    "MA": {"lat": 34.02, "lon": -6.84}, "DZ": {"lat": 36.74, "lon": 3.06},
    "TN": {"lat": 36.81, "lon": 10.17}, "LY": {"lat": 32.89, "lon": 13.18},
    "SD": {"lat": 15.50, "lon": 32.56}, "SS": {"lat": 4.85, "lon": 31.58},
    "CD": {"lat": -4.32, "lon": 15.31}, "CM": {"lat": 3.87, "lon": 11.52},
    "AO": {"lat": -8.84, "lon": 13.23}, "MZ": {"lat": -15.40, "lon": 28.28},
    "MW": {"lat": -13.97, "lon": 33.79}, "ZM": {"lat": -15.39, "lon": 28.32},
    "ZW": {"lat": -17.83, "lon": 31.05}, "BW": {"lat": -24.65, "lon": 25.91},
    "NA": {"lat": -22.56, "lon": 17.08}, "MG": {"lat": -18.88, "lon": 47.51},
    "ML": {"lat": 12.64, "lon": -8.00}, "BF": {"lat": 12.37, "lon": -1.52},
    "NE": {"lat": 13.51, "lon": 2.13}, "TD": {"lat": 12.13, "lon": 15.05},
    "CI": {"lat": 6.82, "lon": -5.28}, "SO": {"lat": 2.05, "lon": 45.32},
    "ER": {"lat": 15.34, "lon": 38.93}, "BJ": {"lat": 6.50, "lon": 2.60},
    "BI": {"lat": -3.38, "lon": 29.36}, "CV": {"lat": 14.93, "lon": -23.51},
    "CF": {"lat": 4.36, "lon": 18.56}, "KM": {"lat": -11.70, "lon": 43.26},
    "CG": {"lat": -4.27, "lon": 15.27}, "DJ": {"lat": 11.59, "lon": 43.15},
    "GQ": {"lat": 3.75, "lon": 8.78}, "GA": {"lat": 0.42, "lon": 9.47},
    "GM": {"lat": 13.45, "lon": -16.58}, "GW": {"lat": 11.86, "lon": -15.59},
    "GN": {"lat": 9.64, "lon": -13.58}, "LS": {"lat": -29.31, "lon": 27.48},
    "LR": {"lat": 6.30, "lon": -10.80}, "MR": {"lat": 18.07, "lon": -15.97},
    "MU": {"lat": -20.16, "lon": 57.50}, "SZ": {"lat": -26.32, "lon": 31.14},
    "TG": {"lat": 6.13, "lon": 1.22}, "SL": {"lat": 8.48, "lon": -13.23},
    "ST": {"lat": 0.34, "lon": 6.73}, "SC": {"lat": -4.62, "lon": 55.45},
    "EH": {"lat": 27.15, "lon": -13.20},
    # Middle East
    "IL": {"lat": 31.77, "lon": 35.22}, "SA": {"lat": 24.69, "lon": 46.72},
    "AE": {"lat": 24.45, "lon": 54.65}, "QA": {"lat": 25.29, "lon": 51.53},
    "KW": {"lat": 29.38, "lon": 47.99}, "BH": {"lat": 26.23, "lon": 50.59},
    "OM": {"lat": 23.61, "lon": 58.54}, "YE": {"lat": 15.37, "lon": 44.21},
    "IR": {"lat": 35.69, "lon": 51.39}, "IQ": {"lat": 33.31, "lon": 44.37},
    "JO": {"lat": 31.95, "lon": 35.93}, "LB": {"lat": 33.89, "lon": 35.50},
    "SY": {"lat": 33.51, "lon": 36.29}, "PS": {"lat": 31.90, "lon": 35.20},
    # Central Asia
    "KZ": {"lat": 51.17, "lon": 71.43}, "UZ": {"lat": 41.30, "lon": 69.28},
    "TM": {"lat": 37.96, "lon": 58.33}, "KG": {"lat": 42.87, "lon": 74.59},
    "TJ": {"lat": 38.56, "lon": 68.77},
    # South Asia
    "IN": {"lat": 28.61, "lon": 77.21}, "PK": {"lat": 33.69, "lon": 73.04},
    "BD": {"lat": 23.81, "lon": 90.41}, "LK": {"lat": 6.93, "lon": 79.85},
    "NP": {"lat": 27.72, "lon": 85.32}, "AF": {"lat": 34.53, "lon": 69.17},
    "BT": {"lat": 27.47, "lon": 89.64}, "MV": {"lat": 4.18, "lon": 73.51},
    # Southeast Asia
    "MM": {"lat": 19.76, "lon": 96.07}, "TH": {"lat": 13.76, "lon": 100.50},
    "VN": {"lat": 21.03, "lon": 105.85}, "KH": {"lat": 11.56, "lon": 104.92},
    "LA": {"lat": 17.97, "lon": 102.63}, "PH": {"lat": 14.60, "lon": 120.98},
    "MY": {"lat": 3.14, "lon": 101.69}, "ID": {"lat": -6.21, "lon": 106.85},
    "SG": {"lat": 1.35, "lon": 103.82}, "BN": {"lat": 4.93, "lon": 114.95},
    "TL": {"lat": -8.56, "lon": 125.57},
    # East Asia
    "CN": {"lat": 39.90, "lon": 116.41}, "JP": {"lat": 35.68, "lon": 139.69},
    "KR": {"lat": 37.57, "lon": 126.98}, "MN": {"lat": 47.91, "lon": 106.91},
    "TW": {"lat": 25.03, "lon": 121.57}, "HK": {"lat": 22.32, "lon": 114.17},
    # Oceania
    "AU": {"lat": -35.28, "lon": 149.13}, "NZ": {"lat": -41.29, "lon": 174.78},
    "PG": {"lat": -6.21, "lon": 155.55}, "FJ": {"lat": -18.14, "lon": 178.44},
    "WS": {"lat": -13.83, "lon": -171.76}, "TO": {"lat": -21.21, "lon": -175.20},
    "VU": {"lat": -17.73, "lon": 168.32}, "SB": {"lat": -9.43, "lon": 160.03},
    "KI": {"lat": 1.45, "lon": 173.04}, "MH": {"lat": 7.12, "lon": 171.07},
    "FM": {"lat": 6.92, "lon": 158.16}, "NR": {"lat": -0.55, "lon": 166.92},
    "PW": {"lat": 7.50, "lon": 134.62}, "TV": {"lat": -8.52, "lon": 179.20},
    # Caucasus
    "GE": {"lat": 41.72, "lon": 44.79}, "AM": {"lat": 40.18, "lon": 44.51},
    "AZ": {"lat": 40.41, "lon": 49.87},
}

COUNTRY_NAMES: Dict[str, str] = {
    # Europe — EU & EEA
    "FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "DE": "Germany", "FR": "France", "NL": "Netherlands", "ES": "Spain",
    "IT": "Italy", "PT": "Portugal", "PL": "Poland", "GB": "United Kingdom",
    "IE": "Ireland", "AT": "Austria", "BE": "Belgium", "CZ": "Czechia",
    "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania", "GR": "Greece",
    "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria", "HR": "Croatia",
    "SK": "Slovakia", "SI": "Slovenia",
    # Europe — non-EU
    "CH": "Switzerland", "IS": "Iceland", "TR": "Turkey", "UA": "Ukraine",
    "RS": "Serbia", "BA": "Bosnia and Herzegovina", "ME": "Montenegro",
    "MK": "North Macedonia", "AL": "Albania", "CY": "Cyprus",
    "BY": "Belarus", "MD": "Moldova", "RU": "Russia",
    "MT": "Malta", "LU": "Luxembourg", "LI": "Liechtenstein",
    "MC": "Monaco", "AD": "Andorra", "XK": "Kosovo",
    "SM": "San Marino", "VA": "Vatican City",
    # North America
    "US": "United States", "CA": "Canada", "MX": "Mexico", "GL": "Greenland",
    # Central America & Caribbean
    "GT": "Guatemala", "HN": "Honduras", "SV": "El Salvador", "NI": "Nicaragua",
    "CR": "Costa Rica", "PA": "Panama", "CU": "Cuba", "DO": "Dominican Republic",
    "HT": "Haiti", "JM": "Jamaica", "TT": "Trinidad and Tobago",
    "BZ": "Belize", "BS": "Bahamas", "BB": "Barbados", "AG": "Antigua and Barbuda",
    "GD": "Grenada", "DM": "Dominica", "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia", "VC": "Saint Vincent and the Grenadines",
    # South America
    "BR": "Brazil", "AR": "Argentina", "CO": "Colombia", "CL": "Chile",
    "PE": "Peru", "EC": "Ecuador", "VE": "Venezuela", "BO": "Bolivia",
    "PY": "Paraguay", "UY": "Uruguay", "GY": "Guyana", "SR": "Suriname",
    # Africa
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt",
    "ET": "Ethiopia", "GH": "Ghana", "TZ": "Tanzania", "UG": "Uganda",
    "RW": "Rwanda", "SN": "Senegal", "MA": "Morocco", "DZ": "Algeria",
    "TN": "Tunisia", "LY": "Libya", "SD": "Sudan", "SS": "South Sudan",
    "CD": "DR Congo", "CM": "Cameroon", "AO": "Angola", "MZ": "Mozambique",
    "MW": "Malawi", "ZM": "Zambia", "ZW": "Zimbabwe", "BW": "Botswana",
    "NA": "Namibia", "MG": "Madagascar", "ML": "Mali", "BF": "Burkina Faso",
    "NE": "Niger", "TD": "Chad", "CI": "Ivory Coast", "SO": "Somalia",
    "ER": "Eritrea", "BJ": "Benin", "BI": "Burundi", "CV": "Cape Verde",
    "CF": "Central African Republic", "KM": "Comoros", "CG": "Congo",
    "DJ": "Djibouti", "GQ": "Equatorial Guinea", "GA": "Gabon",
    "GM": "Gambia", "GW": "Guinea-Bissau", "GN": "Guinea", "LS": "Lesotho",
    "LR": "Liberia", "MR": "Mauritania", "MU": "Mauritius", "SZ": "Eswatini",
    "TG": "Togo", "SL": "Sierra Leone", "ST": "São Tomé and Príncipe",
    "SC": "Seychelles", "EH": "Western Sahara",
    # Middle East
    "IL": "Israel", "SA": "Saudi Arabia", "AE": "United Arab Emirates",
    "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman",
    "YE": "Yemen", "IR": "Iran", "IQ": "Iraq", "JO": "Jordan",
    "LB": "Lebanon", "SY": "Syria", "PS": "Palestine",
    # Central Asia
    "KZ": "Kazakhstan", "UZ": "Uzbekistan", "TM": "Turkmenistan",
    "KG": "Kyrgyzstan", "TJ": "Tajikistan",
    # South Asia
    "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka",
    "NP": "Nepal", "AF": "Afghanistan", "BT": "Bhutan", "MV": "Maldives",
    # Southeast Asia
    "MM": "Myanmar", "TH": "Thailand", "VN": "Vietnam", "KH": "Cambodia",
    "LA": "Laos", "PH": "Philippines", "MY": "Malaysia", "ID": "Indonesia",
    "SG": "Singapore", "BN": "Brunei", "TL": "Timor-Leste",
    # East Asia
    "CN": "China", "JP": "Japan", "KR": "South Korea",
    "MN": "Mongolia", "TW": "Taiwan", "HK": "Hong Kong",
    # Oceania
    "AU": "Australia", "NZ": "New Zealand", "PG": "Papua New Guinea",
    "FJ": "Fiji", "WS": "Samoa", "TO": "Tonga",
    "VU": "Vanuatu", "SB": "Solomon Islands",
    "KI": "Kiribati", "MH": "Marshall Islands", "FM": "Micronesia",
    "NR": "Nauru", "PW": "Palau", "TV": "Tuvalu",
    # Caucasus
    "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan",
    # Special
    "XX": "International",
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
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"Open-Meteo fetch failed for {country_code}: {e}")
            return {
                "source_name": "Open-Meteo",
                "temperature_avg": None,
                "precipitation_mm": None,
                "wind_speed_ms": None,
                "confidence": 0.0,
                "fetched_at": datetime.utcnow().isoformat(),
            }

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
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"NASA POWER fetch failed for {country_code}: {e}")
            return {
                "source_name": "NASA POWER",
                "temperature_avg": None,
                "precipitation_mm": None,
                "wind_speed_ms": None,
                "confidence": 0.0,
                "fetched_at": datetime.utcnow().isoformat(),
            }

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

    async def _fetch_copernicus_indicators(self, country_code: str) -> Optional[Dict]:
        """Fetch climate indicator data from Copernicus CDS.

        Returns None when no API key is configured or when the fetch fails —
        callers must skip the source rather than insert fabricated data.
        """
        import os
        api_key = os.getenv("COPERNICUS_CDS_API_KEY")
        if not api_key:
            logger.info(
                "Copernicus skipped for %s: COPERNICUS_CDS_API_KEY not configured",
                country_code,
            )
            return None

        try:
            from app.domains.content.data_sources.copernicus_adapter import CopernicusAdapter
            adapter = CopernicusAdapter()
            indicators = await adapter.fetch_climate_indicators(country_code)
            if not indicators or all(
                indicators.get(k) is None
                for k in ("temperature_avg", "precipitation_mm", "wind_speed_ms")
            ):
                return None
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
            return None

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
