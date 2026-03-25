"""
Weather Context Service — Local weather enrichment for articles.

Extracts geographic locations from article text and enriches them with
local weather data, historical normals, and anomaly detection.

This creates the "local weather context" panel that contextualizes
climate claims against actual meteorological baselines.
"""

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.database import Database
from app.core.logging import get_logger

logger = get_logger(__name__)

# Extended coordinate database: sub-national regions and major cities
# beyond just capital cities
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # Finland
    "helsinki": (60.17, 24.94),
    "tampere": (61.50, 23.79),
    "turku": (60.45, 22.27),
    "oulu": (65.01, 25.47),
    "rovaniemi": (66.50, 25.73),
    "lapland": (68.00, 26.00),
    "kuopio": (62.89, 27.68),
    "jyväskylä": (62.24, 25.75),
    "jyvaskyla": (62.24, 25.75),
    # Sweden
    "stockholm": (59.33, 18.07),
    "gothenburg": (57.71, 11.97),
    "malmö": (55.61, 13.00),
    "malmo": (55.61, 13.00),
    "kiruna": (67.86, 20.23),
    # Norway
    "oslo": (59.91, 10.75),
    "bergen": (60.39, 5.32),
    "tromsø": (69.65, 18.96),
    "tromso": (69.65, 18.96),
    "svalbard": (78.22, 15.63),
    # Denmark
    "copenhagen": (55.68, 12.57),
    # Germany
    "berlin": (52.52, 13.41),
    "munich": (48.14, 11.58),
    "hamburg": (53.55, 10.00),
    "frankfurt": (50.11, 8.68),
    "cologne": (50.94, 6.96),
    # France
    "paris": (48.86, 2.35),
    "marseille": (43.30, 5.37),
    "lyon": (45.76, 4.84),
    "nice": (43.71, 7.27),
    # Spain
    "madrid": (40.42, -3.70),
    "barcelona": (41.39, 2.17),
    "seville": (37.39, -5.98),
    "valencia": (39.47, -0.38),
    # Italy
    "rome": (41.90, 12.50),
    "milan": (45.46, 9.19),
    "naples": (40.85, 14.27),
    "venice": (45.44, 12.32),
    "sicily": (37.60, 14.02),
    # UK
    "london": (51.51, -0.13),
    "manchester": (53.48, -2.24),
    "edinburgh": (55.95, -3.19),
    "glasgow": (55.86, -4.25),
    "cardiff": (51.48, -3.18),
    # Netherlands
    "amsterdam": (52.37, 4.90),
    "rotterdam": (51.92, 4.48),
    # Belgium
    "brussels": (50.85, 4.35),
    # Poland
    "warsaw": (52.23, 21.01),
    "krakow": (50.06, 19.94),
    # Austria
    "vienna": (48.21, 16.37),
    # Greece
    "athens": (37.98, 23.73),
    "thessaloniki": (40.64, 22.94),
    "crete": (35.24, 24.90),
    # Portugal
    "lisbon": (38.72, -9.14),
    "porto": (41.15, -8.61),
    # Ireland
    "dublin": (53.35, -6.26),
    # Regions / geographic areas
    "mediterranean": (38.0, 15.0),
    "arctic": (71.0, 25.0),
    "scandinavia": (62.0, 15.0),
    "balkans": (42.0, 21.0),
    "iberian peninsula": (39.5, -3.5),
    "alps": (46.8, 10.5),
    "central europe": (50.0, 14.0),
    "southern europe": (40.0, 15.0),
    "northern europe": (60.0, 15.0),
    "western europe": (48.0, 2.0),
    "eastern europe": (50.0, 25.0),
    # North America
    "new york": (40.71, -74.01),
    "los angeles": (34.05, -118.24),
    "chicago": (41.88, -87.63),
    "miami": (25.76, -80.19),
    "san francisco": (37.77, -122.42),
    "washington": (38.90, -77.04),
    "toronto": (43.65, -79.38),
    "vancouver": (49.28, -123.12),
    # Asia-Pacific
    "tokyo": (35.68, 139.69),
    "beijing": (39.90, 116.40),
    "shanghai": (31.23, 121.47),
    "mumbai": (19.08, 72.88),
    "delhi": (28.61, 77.21),
    "sydney": (33.87, 151.21),
    "melbourne": (-37.81, 144.96),
    # Africa
    "cairo": (30.04, 31.24),
    "nairobi": (-1.29, 36.82),
    "cape town": (-33.93, 18.42),
    "lagos": (6.52, 3.38),
    # South America
    "sao paulo": (-23.55, -46.63),
    "rio de janeiro": (-22.91, -43.17),
    "buenos aires": (-34.60, -58.38),
    "santiago": (-33.45, -70.67),
    "bogota": (4.71, -74.07),
}

# Country code to capital coordinate fallback
COUNTRY_CAPITAL_COORDS: Dict[str, Tuple[float, float]] = {
    "FI": (60.17, 24.94), "SE": (59.33, 18.07), "NO": (59.91, 10.75),
    "DK": (55.68, 12.57), "DE": (52.52, 13.41), "FR": (48.86, 2.35),
    "NL": (52.37, 4.90), "ES": (40.42, -3.70), "IT": (41.90, 12.50),
    "PT": (38.72, -9.14), "PL": (52.23, 21.01), "GB": (51.51, -0.13),
    "IE": (53.35, -6.26), "AT": (48.21, 16.37), "BE": (50.85, 4.35),
    "CZ": (50.08, 14.44), "GR": (37.98, 23.73), "HU": (47.50, 19.04),
    "RO": (44.43, 26.10), "BG": (42.70, 23.32), "HR": (45.81, 15.98),
    "EE": (59.44, 24.75), "LV": (56.95, 24.11), "LT": (54.69, 25.28),
    "SK": (48.15, 17.11), "SI": (46.06, 14.51),
    "US": (38.90, -77.04), "CA": (45.42, -75.69), "MX": (19.43, -99.13),
    "JP": (35.68, 139.69), "CN": (39.90, 116.40), "IN": (28.61, 77.21),
    "AU": (-33.87, 151.21), "BR": (-15.79, -47.88), "ZA": (-33.93, 18.42),
}


class WeatherContextService:
    """Enriches articles with localized weather context."""

    def __init__(self, db: Database):
        self.db = db

    async def get_article_weather_context(
        self, article_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get localized weather context for an article.

        Extracts locations from article text, fetches current + historical
        weather, and computes anomaly indicators.
        """
        # Fetch article text and country
        rows = self.db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') as text,
                      country_code
               FROM articles WHERE article_id = :id""",
            {"id": article_id},
        )
        if not rows:
            return None

        article = rows[0]
        full_text = f"{article.get('title', '')} {article.get('text', '')} {article.get('excerpt', '')}"
        country_code = article.get("country_code", "FI")

        # Extract locations from text
        locations = self._extract_locations(full_text)

        # If no specific locations found, use country capital
        if not locations and country_code:
            capital_coords = COUNTRY_CAPITAL_COORDS.get(country_code.upper())
            if capital_coords:
                locations = [{"name": f"{country_code} (capital)", "lat": capital_coords[0], "lon": capital_coords[1]}]

        if not locations:
            return None

        # Fetch weather for each location (max 3 to avoid excessive API calls)
        location_contexts = []
        for loc in locations[:3]:
            ctx = await self._fetch_location_context(loc["lat"], loc["lon"], loc["name"])
            if ctx:
                location_contexts.append(ctx)

        if not location_contexts:
            return None

        return {
            "article_id": article_id,
            "locations_found": len(locations),
            "locations_analyzed": len(location_contexts),
            "weather_contexts": location_contexts,
        }

    async def get_location_weather(
        self, lat: float, lon: float, location_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather context for a specific coordinate."""
        return await self._fetch_location_context(lat, lon, location_name or f"({lat}, {lon})")

    def _extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """Extract geographic locations from text and resolve to coordinates."""
        text_lower = text.lower()
        found = []
        seen_coords = set()

        for city_name, (lat, lon) in CITY_COORDS.items():
            # Match as whole word (with word boundaries)
            pattern = r'\b' + re.escape(city_name) + r'\b'
            if re.search(pattern, text_lower):
                coord_key = (round(lat, 1), round(lon, 1))
                if coord_key not in seen_coords:
                    found.append({"name": city_name.title(), "lat": lat, "lon": lon})
                    seen_coords.add(coord_key)

        # Sort by order of appearance in text
        found.sort(key=lambda loc: text_lower.index(loc["name"].lower()))
        return found

    async def _fetch_location_context(
        self, lat: float, lon: float, name: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch current weather + historical normals for a location."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch current weather
                current_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                        "timezone": "auto",
                        "forecast_days": 7,
                    },
                )

                # Fetch historical normals (same period last year)
                today = date.today()
                hist_start = date(today.year - 1, today.month, today.day) - timedelta(days=3)
                hist_end = date(today.year - 1, today.month, today.day) + timedelta(days=3)

                historical_resp = await client.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params={
                        "latitude": lat, "longitude": lon,
                        "start_date": hist_start.isoformat(),
                        "end_date": hist_end.isoformat(),
                        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum",
                        "timezone": "auto",
                    },
                )

            current_data = None
            forecast_data = None
            if current_resp.status_code == 200:
                cdata = current_resp.json()
                current = cdata.get("current", {})
                daily = cdata.get("daily", {})
                current_data = {
                    "temperature_c": current.get("temperature_2m"),
                    "humidity_pct": current.get("relative_humidity_2m"),
                    "precipitation_mm": current.get("precipitation"),
                    "wind_speed_kmh": current.get("wind_speed_10m"),
                    "weather_code": current.get("weather_code"),
                }
                if daily.get("temperature_2m_max"):
                    forecast_data = {
                        "dates": daily.get("time", []),
                        "max_temps": daily.get("temperature_2m_max", []),
                        "min_temps": daily.get("temperature_2m_min", []),
                        "precipitation": daily.get("precipitation_sum", []),
                    }

            historical_normals = None
            anomaly = None
            if historical_resp.status_code == 200:
                hdata = historical_resp.json()
                hdaily = hdata.get("daily", {})
                hist_temps = [t for t in (hdaily.get("temperature_2m_mean") or []) if t is not None]
                hist_precip = [p for p in (hdaily.get("precipitation_sum") or []) if p is not None]

                if hist_temps:
                    avg_hist_temp = sum(hist_temps) / len(hist_temps)
                    historical_normals = {
                        "period": f"{hist_start.isoformat()} to {hist_end.isoformat()}",
                        "avg_temperature_c": round(avg_hist_temp, 1),
                        "avg_precipitation_mm": round(sum(hist_precip) / max(len(hist_precip), 1), 1),
                    }

                    # Compute anomaly
                    if current_data and current_data.get("temperature_c") is not None:
                        current_temp = current_data["temperature_c"]
                        temp_diff = current_temp - avg_hist_temp
                        anomaly = {
                            "temperature_deviation_c": round(temp_diff, 1),
                            "is_anomalous": abs(temp_diff) > 5.0,
                            "anomaly_description": _describe_anomaly(temp_diff),
                        }

            if not current_data:
                return None

            return {
                "location_name": name,
                "coordinates": {"lat": lat, "lon": lon},
                "current_weather": current_data,
                "forecast_7day": forecast_data,
                "historical_normals": historical_normals,
                "anomaly": anomaly,
            }

        except Exception as e:
            logger.warning(f"Weather context fetch failed for {name}: {e}")
            return None


def _describe_anomaly(temp_diff: float) -> str:
    """Generate human-readable anomaly description."""
    abs_diff = abs(temp_diff)
    if abs_diff <= 2.0:
        return "Within normal range for this time of year"
    elif abs_diff <= 5.0:
        direction = "warmer" if temp_diff > 0 else "cooler"
        return f"Slightly {direction} than usual ({temp_diff:+.1f}°C)"
    elif abs_diff <= 10.0:
        direction = "warmer" if temp_diff > 0 else "cooler"
        return f"Significantly {direction} than historical average ({temp_diff:+.1f}°C)"
    else:
        direction = "warmer" if temp_diff > 0 else "cooler"
        return f"Extreme anomaly: {temp_diff:+.1f}°C {direction} than normal"
