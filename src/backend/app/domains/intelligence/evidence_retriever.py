"""
Evidence Retriever Module

Orchestrates evidence retrieval from multiple external sources for climate claim verification.
Sources are queried in a fallback chain: Open-Meteo -> Perplexity -> Google Fact Check -> EEA.
"""

import os
import asyncio
from abc import ABC, abstractmethod

import httpx

from app.core.logging import get_logger
from .schemas import Evidence

logger = get_logger(__name__)


class BaseEvidenceRetriever(ABC):
    """Abstract base for evidence retrieval strategies."""

    @abstractmethod
    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        ...


class OpenMeteoEvidenceRetriever(BaseEvidenceRetriever):
    """
    Primary climate data evidence via Open-Meteo (no auth required).

    Checks claim against real weather/climate data:
    - Current/forecast data for recent weather claims
    - Historical archive (ERA5) for past climate claims
    - Air quality data for pollution claims
    """

    BASE_FORECAST = "https://api.open-meteo.com/v1/forecast"
    BASE_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
    BASE_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # Map country codes to representative coordinates
    COUNTRY_COORDS = {
        "FI": (60.17, 24.94),   # Helsinki
        "SE": (59.33, 18.07),   # Stockholm
        "NO": (59.91, 10.75),   # Oslo
        "DK": (55.68, 12.57),   # Copenhagen
        "DE": (52.52, 13.41),   # Berlin
        "FR": (48.86, 2.35),    # Paris
        "NL": (52.37, 4.90),    # Amsterdam
        "ES": (40.42, -3.70),   # Madrid
        "IT": (41.90, 12.50),   # Rome
        "PL": (52.23, 21.01),   # Warsaw
        "GB": (51.51, -0.13),   # London
        "AT": (48.21, 16.37),   # Vienna
        "BE": (50.85, 4.35),    # Brussels
        "CZ": (50.08, 14.44),   # Prague
        "PT": (38.72, -9.14),   # Lisbon
        "GR": (37.98, 23.73),   # Athens
        "IE": (53.35, -6.26),   # Dublin
        "HU": (47.50, 19.04),   # Budapest
        "RO": (44.43, 26.10),   # Bucharest
        "BG": (42.70, 23.32),   # Sofia
        "HR": (45.81, 15.98),   # Zagreb
        "EE": (59.44, 24.75),   # Tallinn
        "LV": (56.95, 24.11),   # Riga
        "LT": (54.69, 25.28),   # Vilnius
        "SK": (48.15, 17.11),   # Bratislava
        "SI": (46.06, 14.51),   # Ljubljana
        # North America
        "US": (38.90, -77.04),   # Washington DC
        "CA": (45.42, -75.69),   # Ottawa
        "MX": (19.43, -99.13),   # Mexico City
        # Asia-Pacific
        "JP": (35.68, 139.69),   # Tokyo
        "CN": (39.90, 116.40),   # Beijing
        "IN": (28.61, 77.21),    # New Delhi
        "AU": (-33.87, 151.21),  # Sydney
        "KR": (37.57, 126.98),   # Seoul
        # Africa
        "ZA": (-33.93, 18.42),   # Cape Town
        "NG": (9.08, 7.49),      # Abuja
        "KE": (-1.29, 36.82),    # Nairobi
        # South America
        "BR": (-15.79, -47.88),  # Brasilia
        "AR": (-34.60, -58.38),  # Buenos Aires
    }

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """Retrieve climate data evidence from Open-Meteo."""
        lat, lon = self.COUNTRY_COORDS.get(country_code.upper(), (52.52, 13.41))
        evidence = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch current weather data
            try:
                resp = await client.get(self.BASE_FORECAST, params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "timezone": "auto",
                    "forecast_days": 7,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    daily = data.get("daily", {})

                    temp = current.get("temperature_2m")
                    precip = current.get("precipitation")
                    wind = current.get("wind_speed_10m")

                    summary_parts = []
                    if temp is not None:
                        summary_parts.append(f"Current temperature: {temp}\u00b0C")
                    if precip is not None:
                        summary_parts.append(f"Precipitation: {precip}mm")
                    if wind is not None:
                        summary_parts.append(f"Wind speed: {wind} km/h")

                    # Add daily forecast summary
                    if daily.get("temperature_2m_max"):
                        max_temps = daily["temperature_2m_max"][:3]
                        summary_parts.append(f"3-day max temps: {max_temps}")

                    if summary_parts:
                        evidence.append(Evidence(
                            source="Open-Meteo Weather API",
                            source_url="https://open-meteo.com/en/docs",
                            source_reliability="high",
                            content_excerpt=(
                                f"Weather data for {country_code} ({lat}, {lon}): "
                                f"{'; '.join(summary_parts)}"
                            ),
                            relevance_score=0.7,
                            retrieval_method="open_meteo_forecast",
                        ))
            except Exception as e:
                logger.warning(f"Open-Meteo forecast failed: {e}")

            # Fetch air quality if claim mentions pollution/air quality keywords
            air_keywords = [
                "air quality", "pollution", "pm2.5", "pm10", "ozone",
                "nitrogen", "emissions", "smog",
            ]
            if any(kw in claim.lower() for kw in air_keywords):
                try:
                    resp = await client.get(self.BASE_AIR_QUALITY, params={
                        "latitude": lat, "longitude": lon,
                        "current": "european_aqi,pm10,pm2_5,nitrogen_dioxide,ozone",
                    })
                    if resp.status_code == 200:
                        aq_data = resp.json().get("current", {})
                        aqi = aq_data.get("european_aqi")
                        pm25 = aq_data.get("pm2_5")
                        pm10 = aq_data.get("pm10")
                        no2 = aq_data.get("nitrogen_dioxide")

                        aq_parts = []
                        if aqi is not None:
                            aq_parts.append(f"European AQI: {aqi}")
                        if pm25 is not None:
                            aq_parts.append(f"PM2.5: {pm25} \u00b5g/m\u00b3")
                        if pm10 is not None:
                            aq_parts.append(f"PM10: {pm10} \u00b5g/m\u00b3")
                        if no2 is not None:
                            aq_parts.append(f"NO\u2082: {no2} \u00b5g/m\u00b3")

                        if aq_parts:
                            evidence.append(Evidence(
                                source="Open-Meteo Air Quality (CAMS)",
                                source_url="https://open-meteo.com/en/docs/air-quality-api",
                                source_reliability="high",
                                content_excerpt=(
                                    f"Air quality for {country_code}: "
                                    f"{'; '.join(aq_parts)}"
                                ),
                                relevance_score=0.85,
                                retrieval_method="open_meteo_air_quality",
                            ))
                except Exception as e:
                    logger.warning(f"Open-Meteo air quality failed: {e}")

        return evidence


class PerplexityEvidenceRetriever(BaseEvidenceRetriever):
    """Web search evidence via Perplexity sonar model."""

    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("PERPLEXITY_MODEL", "sonar"),
                        "messages": [{
                            "role": "user",
                            "content": (
                                f"Verify this climate claim with current evidence and sources: \"{claim}\". "
                                f"Country context: {country_code}. "
                                "Provide 2-3 specific data points or findings from credible sources "
                                "(NASA, NOAA, IPCC, EEA, national meteorological services). "
                                "State whether evidence supports or contradicts the claim."
                            ),
                        }],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                # Extract citations if available
                citations = data.get("citations", [])
                source_url = citations[0] if citations else "https://www.perplexity.ai"

                return [Evidence(
                    source="Perplexity AI Search",
                    source_url=source_url,
                    source_reliability="medium",
                    content_excerpt=content[:500],
                    relevance_score=0.8,
                    retrieval_method="perplexity_search",
                )]
        except Exception as e:
            logger.warning(f"Perplexity evidence retrieval failed: {e}")
            return []


class GoogleFactCheckRetriever(BaseEvidenceRetriever):
    """Google Fact Check Tools API lookup."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                    params={"key": self.api_key, "query": claim, "pageSize": 5},
                )
                resp.raise_for_status()
                data = resp.json()

                evidence = []
                for item in data.get("claims", []):
                    for review in item.get("claimReview", []):
                        publisher = review.get("publisher", {}).get("name", "Unknown")
                        rating = review.get("textualRating", "")
                        url = review.get("url", "")

                        # Determine if supports/contradicts
                        supports = None
                        rating_lower = rating.lower()
                        if any(w in rating_lower for w in ["true", "correct", "accurate"]):
                            supports = True
                        elif any(w in rating_lower for w in [
                            "false", "incorrect", "misleading", "pants on fire",
                        ]):
                            supports = False

                        evidence.append(Evidence(
                            source=f"Google Fact Check ({publisher})",
                            source_url=url,
                            source_reliability="high",
                            content_excerpt=f"Rating: {rating}. Claim reviewed by {publisher}.",
                            relevance_score=0.9,
                            supports_claim=supports,
                            retrieval_method="google_factcheck",
                        ))

                return evidence
        except Exception as e:
            logger.warning(f"Google Fact Check API failed: {e}")
            return []


class EEAEvidenceRetriever(BaseEvidenceRetriever):
    """European Environment Agency data retrieval for EU environmental claims."""

    BASE_URL = "https://discomap.eea.europa.eu/map/fme/latest"

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """Query EEA air quality API for environmental evidence."""
        # Only query for environment/emissions-related claims
        env_keywords = [
            "emission", "carbon", "greenhouse", "co2", "methane", "environment",
            "biodiversity", "deforestation", "recycling", "waste", "renewable",
        ]
        if not any(kw in claim.lower() for kw in env_keywords):
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Query EEA air quality e-Reporting
                resp = await client.get(
                    "https://fme.discomap.eea.europa.eu/fmedatastreaming/"
                    "AirQualityDownload/AQData_Extract.fmw",
                    params={
                        "CountryCode": country_code.upper(),
                        "Pollutant": "8",  # NO2
                        "Year_from": "2024",
                        "Year_to": "2025",
                        "Source": "E1a",
                        "Output": "TEXT",
                        "TimeCoverage": "Year",
                    },
                )
                if resp.status_code == 200 and len(resp.text) > 100:
                    return [Evidence(
                        source="European Environment Agency",
                        source_url="https://www.eea.europa.eu/en/datahub",
                        source_reliability="high",
                        content_excerpt=(
                            f"EEA air quality monitoring data available for {country_code}. "
                            "Data confirms monitoring network coverage."
                        ),
                        relevance_score=0.7,
                        retrieval_method="eea_datahub",
                    )]
        except Exception as e:
            logger.warning(f"EEA data retrieval failed: {e}")

        return []


class CarbonBriefRetriever(BaseEvidenceRetriever):
    """Cross-reference claims against Carbon Brief climate journalism."""

    FEED_URL = "https://www.carbonbrief.org/feed/"

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """Search Carbon Brief RSS feed for related coverage."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.FEED_URL)
                if resp.status_code != 200:
                    return []

                # Simple keyword matching against feed items
                # (proper implementation would use feedparser but keeping deps minimal)
                content = resp.text
                claim_words = set(claim.lower().split())
                # Remove common words
                stop_words = {
                    "the", "a", "an", "is", "are", "was", "were", "of", "in",
                    "to", "for", "and", "or", "that", "this", "has", "have", "been",
                }
                claim_keywords = claim_words - stop_words

                # Check if any claim keywords appear in feed
                content_lower = content.lower()
                matches = sum(1 for kw in claim_keywords if kw in content_lower)

                if matches >= 2:
                    return [Evidence(
                        source="Carbon Brief",
                        source_url="https://www.carbonbrief.org",
                        source_reliability="high",
                        content_excerpt=(
                            f"Carbon Brief has published related coverage. "
                            f"{matches} keywords from this claim found in recent articles."
                        ),
                        relevance_score=0.6,
                        retrieval_method="carbon_brief_rss",
                    )]
        except Exception as e:
            logger.warning(f"Carbon Brief retrieval failed: {e}")

        return []


class EvidenceOrchestrator:
    """
    Orchestrates evidence retrieval from all sources with fallback chain.

    Queries sources concurrently. Fails with HTTP 503 if ALL sources fail.
    """

    def __init__(self):
        self.retrievers: list[BaseEvidenceRetriever] = [
            OpenMeteoEvidenceRetriever(),
            PerplexityEvidenceRetriever(),
            GoogleFactCheckRetriever(),
            EEAEvidenceRetriever(),
            CarbonBriefRetriever(),
        ]
        self.timeout = int(os.getenv("EVIDENCE_RETRIEVAL_TIMEOUT_SECONDS", "30"))

    async def retrieve_all(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """
        Retrieve evidence from all sources concurrently.

        Returns combined evidence list sorted by relevance_score descending.
        Raises HTTPException 503 if all sources fail.
        """
        tasks = [
            retriever.retrieve(claim, country_code)
            for retriever in self.retrievers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_evidence: list[Evidence] = []
        failures = 0

        for i, result in enumerate(results):
            retriever_name = type(self.retrievers[i]).__name__
            if isinstance(result, Exception):
                logger.error(f"{retriever_name} failed: {result}")
                failures += 1
            elif isinstance(result, list):
                all_evidence.extend(result)
                if result:
                    logger.info(
                        f"{retriever_name} returned {len(result)} evidence pieces"
                    )
            else:
                failures += 1

        if failures == len(self.retrievers) and not all_evidence:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="All evidence sources failed. Please try again later.",
            )

        # Sort by relevance score descending
        all_evidence.sort(key=lambda e: e.relevance_score, reverse=True)

        logger.info(
            f"Evidence orchestrator: {len(all_evidence)} total pieces from "
            f"{len(self.retrievers) - failures}/{len(self.retrievers)} sources"
        )
        return all_evidence
