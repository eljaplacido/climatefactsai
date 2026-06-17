"""
Weather Claim Validator — validates climate claims against actual weather data.

Extracts location, time period, and metric from claims via pattern matching,
then queries Open-Meteo archive API to compare claimed vs actual values.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Expanded country coordinates (global, not just EU)
GLOBAL_COUNTRY_COORDS = {
    # Europe
    "FI": (60.17, 24.94), "SE": (59.33, 18.07), "NO": (59.91, 10.75),
    "DK": (55.68, 12.57), "DE": (52.52, 13.41), "FR": (48.86, 2.35),
    "NL": (52.37, 4.90), "ES": (40.42, -3.70), "IT": (41.90, 12.50),
    "PL": (52.23, 21.01), "GB": (51.51, -0.13), "AT": (48.21, 16.37),
    "BE": (50.85, 4.35), "CZ": (50.08, 14.44), "PT": (38.72, -9.14),
    "GR": (37.98, 23.73), "IE": (53.35, -6.26), "HU": (47.50, 19.04),
    "RO": (44.43, 26.10), "BG": (42.70, 23.32), "HR": (45.81, 15.98),
    "EE": (59.44, 24.75), "LV": (56.95, 24.11), "LT": (54.69, 25.28),
    "SK": (48.15, 17.11), "SI": (46.06, 14.51),
    # North America
    "US": (38.90, -77.04), "CA": (45.42, -75.69), "MX": (19.43, -99.13),
    # Asia-Pacific
    "JP": (35.68, 139.69), "CN": (39.90, 116.40), "IN": (28.61, 77.21),
    "AU": (-33.87, 151.21), "KR": (37.57, 126.98), "ID": (-6.21, 106.85),
    # Africa
    "ZA": (-33.93, 18.42), "NG": (9.08, 7.49), "KE": (-1.29, 36.82),
    "EG": (30.04, 31.24),
    # South America
    "BR": (-15.79, -47.88), "AR": (-34.60, -58.38), "CL": (-33.45, -70.67),
    "CO": (4.71, -74.07),
    # Middle East
    "SA": (24.71, 46.68), "AE": (25.20, 55.27),
}

# City name to coordinates for more specific claims
CITY_COORDS = {
    "helsinki": (60.17, 24.94), "stockholm": (59.33, 18.07),
    "oslo": (59.91, 10.75), "copenhagen": (55.68, 12.57),
    "berlin": (52.52, 13.41), "paris": (48.86, 2.35),
    "london": (51.51, -0.13), "madrid": (40.42, -3.70),
    "rome": (41.90, 12.50), "amsterdam": (52.37, 4.90),
    "washington": (38.90, -77.04), "new york": (40.71, -74.01),
    "tokyo": (35.68, 139.69), "beijing": (39.90, 116.40),
    "sydney": (-33.87, 151.21), "mumbai": (19.08, 72.88),
    "sao paulo": (-23.55, -46.63), "lagos": (6.52, 3.38),
    "cairo": (30.04, 31.24), "nairobi": (-1.29, 36.82),
}

# Weather metric patterns
METRIC_PATTERNS = {
    "temperature": [
        r"(\d+\.?\d*)\s*°?\s*[cC](?:elsius)?",
        r"temperature.*?(\d+\.?\d*)",
        r"(\d+\.?\d*)\s*degrees",
        r"warm(?:est|er).*?(\d+\.?\d*)",
        r"cold(?:est|er).*?(\d+\.?\d*)",
        r"hot(?:test|ter).*?(\d+\.?\d*)",
    ],
    "precipitation": [
        r"(\d+\.?\d*)\s*mm",
        r"rainfall.*?(\d+\.?\d*)",
        r"precipitation.*?(\d+\.?\d*)",
        r"snow(?:fall)?.*?(\d+\.?\d*)\s*(?:cm|mm|inches)",
    ],
    "wind_speed": [
        r"wind.*?(\d+\.?\d*)\s*(?:km/h|m/s|mph|knots)",
        r"(\d+\.?\d*)\s*(?:km/h|m/s)\s*wind",
    ],
}

# Month name to number
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


class WeatherClaimValidator:
    """Validates weather/climate claims against Open-Meteo archive data."""

    BASE_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

    def _extract_location(self, claim: str) -> Optional[Tuple[float, float, str]]:
        """Extract location from claim text. Returns (lat, lon, location_name) or None."""
        claim_lower = claim.lower()

        # Try city names first (more specific)
        for city, coords in CITY_COORDS.items():
            if city in claim_lower:
                return (*coords, city.title())

        # Try country codes/names
        country_names = {
            "finland": "FI", "sweden": "SE", "norway": "NO", "denmark": "DK",
            "germany": "DE", "france": "FR", "netherlands": "NL", "spain": "ES",
            "italy": "IT", "poland": "PL", "united kingdom": "GB", "uk": "GB",
            "united states": "US", "usa": "US", "japan": "JP", "china": "CN",
            "india": "IN", "australia": "AU", "brazil": "BR", "south africa": "ZA",
            "nigeria": "NG", "canada": "CA", "mexico": "MX", "argentina": "AR",
        }
        for name, code in country_names.items():
            if name in claim_lower:
                coords = GLOBAL_COUNTRY_COORDS.get(code)
                if coords:
                    return (*coords, name.title())

        return None

    def _extract_time_period(self, claim: str) -> Optional[Tuple[str, str]]:
        """Extract date range from claim. Returns (start_date, end_date) as YYYY-MM-DD strings."""
        claim_lower = claim.lower()
        now = datetime.utcnow()

        # Try "Month YYYY" pattern
        month_year = re.search(
            r'(january|february|march|april|may|june|july|august|september|october|november|december'
            r'|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})',
            claim_lower,
        )
        if month_year:
            month = MONTH_MAP.get(month_year.group(1))
            year = int(month_year.group(2))
            if month and 2000 <= year <= now.year:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                return (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}")

        # Try "YYYY" pattern
        year_match = re.search(r'\b(20[12]\d)\b', claim_lower)
        if year_match:
            year = int(year_match.group(1))
            if year < now.year:
                return (f"{year}-01-01", f"{year}-12-31")
            elif year == now.year:
                end = min(now, datetime(year, 12, 31))
                return (f"{year}-01-01", end.strftime("%Y-%m-%d"))

        # Default: last 30 days
        end = now
        start = end - timedelta(days=30)
        return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    def _extract_metric_value(self, claim: str) -> Optional[Tuple[str, float]]:
        """Extract the claimed metric and value. Returns (metric_type, value) or None."""
        for metric_type, patterns in METRIC_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, claim, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        return (metric_type, value)
                    except (ValueError, IndexError):
                        continue
        return None

    async def validate(self, claim: str, country_code: str = "FI") -> Dict[str, Any]:
        """
        Validate a weather/climate claim against Open-Meteo archive data.

        Returns dict with:
            - weather_validated: bool
            - verdict: "SUPPORTED" | "CONTRADICTED" | "INCONCLUSIVE"
            - claimed_value: float or None
            - actual_value: float or None
            - deviation_pct: float or None
            - data_source: str
            - details: str
        """
        result: Dict[str, Any] = {
            "weather_validated": False,
            "verdict": "INCONCLUSIVE",
            "claimed_value": None,
            "actual_value": None,
            "deviation_pct": None,
            "data_source": "Open-Meteo Archive API",
            "details": "",
        }

        # Extract claim components
        location = self._extract_location(claim)
        if not location:
            coords = GLOBAL_COUNTRY_COORDS.get(country_code.upper())
            if coords:
                location = (*coords, country_code)
            else:
                result["details"] = "Could not determine location from claim"
                return result

        lat, lon, location_name = location

        time_period = self._extract_time_period(claim)
        if not time_period:
            result["details"] = "Could not determine time period from claim"
            return result

        start_date, end_date = time_period

        metric_info = self._extract_metric_value(claim)

        # Query Open-Meteo archive
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
                    "timezone": "auto",
                }
                resp = await client.get(self.BASE_ARCHIVE, params=params)

                if resp.status_code != 200:
                    result["details"] = f"Open-Meteo API returned {resp.status_code}"
                    return result

                data = resp.json()
                daily = data.get("daily", {})

                if not daily.get("temperature_2m_mean"):
                    result["details"] = "No data returned for the requested period"
                    return result

                result["weather_validated"] = True

                # Compare claimed value against actual data
                if metric_info:
                    metric_type, claimed_value = metric_info
                    result["claimed_value"] = claimed_value

                    if metric_type == "temperature":
                        actuals = [v for v in (daily.get("temperature_2m_mean") or []) if v is not None]
                        if actuals:
                            actual_avg = sum(actuals) / len(actuals)
                            actual_max = max(daily.get("temperature_2m_max") or actuals)

                            # Compare against both mean and max
                            closest = min([actual_avg, actual_max], key=lambda x: abs(x - claimed_value))
                            result["actual_value"] = round(closest, 1)

                            if closest != 0:
                                deviation = abs(claimed_value - closest) / max(abs(closest), 1) * 100
                            else:
                                deviation = abs(claimed_value) * 100
                            result["deviation_pct"] = round(deviation, 1)

                            # Tolerance: 15% for temperature
                            if deviation <= 15:
                                result["verdict"] = "SUPPORTED"
                            elif deviation <= 40:
                                result["verdict"] = "INCONCLUSIVE"
                            else:
                                result["verdict"] = "CONTRADICTED"

                    elif metric_type == "precipitation":
                        actuals = [v for v in (daily.get("precipitation_sum") or []) if v is not None]
                        if actuals:
                            actual_total = sum(actuals)
                            result["actual_value"] = round(actual_total, 1)

                            if actual_total > 0:
                                deviation = abs(claimed_value - actual_total) / actual_total * 100
                            else:
                                deviation = abs(claimed_value) * 100
                            result["deviation_pct"] = round(deviation, 1)

                            if deviation <= 25:
                                result["verdict"] = "SUPPORTED"
                            elif deviation <= 50:
                                result["verdict"] = "INCONCLUSIVE"
                            else:
                                result["verdict"] = "CONTRADICTED"

                    elif metric_type == "wind_speed":
                        actuals = [v for v in (daily.get("wind_speed_10m_max") or []) if v is not None]
                        if actuals:
                            actual_max = max(actuals)
                            result["actual_value"] = round(actual_max, 1)

                            if actual_max > 0:
                                deviation = abs(claimed_value - actual_max) / actual_max * 100
                            else:
                                deviation = abs(claimed_value) * 100
                            result["deviation_pct"] = round(deviation, 1)

                            if deviation <= 20:
                                result["verdict"] = "SUPPORTED"
                            elif deviation <= 50:
                                result["verdict"] = "INCONCLUSIVE"
                            else:
                                result["verdict"] = "CONTRADICTED"

                    result["details"] = (
                        f"Weather validation for {location_name} ({start_date} to {end_date}): "
                        f"Claimed {metric_type}={claimed_value}, "
                        f"Actual={result['actual_value']}, "
                        f"Deviation={result['deviation_pct']}%"
                    )
                else:
                    # No specific metric claimed, but we have data
                    temps = [v for v in (daily.get("temperature_2m_mean") or []) if v is not None]
                    if temps:
                        avg_temp = round(sum(temps) / len(temps), 1)
                        result["actual_value"] = avg_temp
                        result["details"] = (
                            f"Weather data for {location_name} ({start_date} to {end_date}): "
                            f"Avg temperature={avg_temp}\u00b0C. No specific numeric claim to validate."
                        )
                        result["verdict"] = "INCONCLUSIVE"

        except Exception as e:
            logger.error(f"Weather validation failed: {e}")
            result["details"] = f"Validation error: {str(e)}"

        return result
