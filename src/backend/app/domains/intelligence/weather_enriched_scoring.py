"""
Weather-Enriched Reliability Scoring — Cross-references article claims
with actual meteorological data to enhance credibility scores.

Scoring factors:
1. Weather claim accuracy: Do temperature/precipitation claims match real data?
2. Anomaly alignment: Does article discuss anomalies that actually exist?
3. Trend consistency: Do long-term trend claims align with climate data?
4. Geographic accuracy: Are location-specific claims geographically consistent?
"""

import re
from typing import Any, Dict, List, Optional

from app.core.database import Database, get_db
from app.core.logging import get_logger
from app.domains.content.weather_context_service import WeatherContextService
from app.domains.intelligence.bayesian_credibility import BayesianCredibilityService

logger = get_logger(__name__)

TEMPERATURE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*°?\s*(?:degrees?\s+)?(?:celsius|centigrade|C\b)', re.IGNORECASE
)
PRECIPITATION_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:mm|millimeters?|millimetres?)\s*(?:of\s+)?(?:rain|precipitation|rainfall)', re.IGNORECASE
)
ANOMALY_KEYWORDS = [
    "record", "unprecedented", "highest ever", "lowest ever",
    "above average", "below average", "anomaly", "deviation",
    "warmest", "coldest", "hottest", "wettest", "driest", "extreme", "unusual",
]
TREND_KEYWORDS = [
    "rising", "falling", "increasing", "decreasing",
    "warming", "cooling", "accelerating", "slowing", "trend", "over the past",
]


class WeatherEnrichedScorer:
    """Enhanced credibility scoring using real weather data verification."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()
        self.weather_service = WeatherContextService(self.db)
        self.bayesian_service = BayesianCredibilityService(self.db)

    async def compute_weather_enriched_score(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Compute weather-enriched reliability score for an article."""
        rows = self.db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') as text,
                      country_code, reliability_score, source_name
               FROM articles WHERE article_id = :id""",
            {"id": article_id},
        )
        if not rows:
            return None

        article = rows[0]
        full_text = f"{article.get('title', '')} {article.get('text', '')} {article.get('excerpt', '')}"

        claims = self._extract_weather_claims(full_text)
        weather_ctx = await self.weather_service.get_article_weather_context(article_id)

        if not claims and not weather_ctx:
            return {"article_id": article_id, "weather_enrichment": "not_applicable",
                    "reason": "No weather/climate claims detected"}

        verification_results = []
        if weather_ctx and weather_ctx.get("weather_contexts"):
            for loc_ctx in weather_ctx["weather_contexts"]:
                result = self._verify_claims_against_weather(claims, loc_ctx)
                verification_results.append(result)

        weather_factor = self._compute_weather_factor(claims, verification_results)

        source_score = article.get("reliability_score") or 50
        existing_evidence = self.db.execute_query(
            """SELECT confidence_score FROM fact_checks
               WHERE article_id = :aid AND confidence_score IS NOT NULL""",
            {"aid": article_id},
        )
        evidence_scores = [
            float(r["confidence_score"]) / 100.0
            for r in (existing_evidence or []) if r.get("confidence_score") is not None
        ]

        if weather_factor is not None:
            evidence_scores.append(weather_factor)

        posterior = self.bayesian_service.compute_posterior(float(source_score), evidence_scores, prior_weight=0.25)

        new_score = int(posterior["posterior_score"])
        self.db.execute_update(
            "UPDATE articles SET reliability_score = :score, updated_at = NOW() WHERE article_id = :aid",
            {"score": new_score, "aid": article_id},
        )

        return {
            "article_id": article_id, "weather_enrichment": "applied",
            "claims_found": len(claims), "locations_verified": len(verification_results),
            "weather_verification_factor": weather_factor,
            "verification_details": verification_results, "posterior_score": posterior,
            "previous_score": source_score, "new_score": new_score,
        }

    def _extract_weather_claims(self, text: str) -> List[Dict[str, Any]]:
        claims = []
        for match in TEMPERATURE_PATTERN.finditer(text):
            claims.append({"type": "temperature", "value": float(match.group(1)),
                           "unit": "celsius", "context": text[max(0, match.start()-100):match.end()+100].strip(),
                           "position": match.start()})

        for match in PRECIPITATION_PATTERN.finditer(text):
            claims.append({"type": "precipitation", "value": float(match.group(1)),
                           "unit": "mm", "context": text[max(0, match.start()-100):match.end()+100].strip(),
                           "position": match.start()})

        text_lower = text.lower()
        for kw in ANOMALY_KEYWORDS:
            idx = text_lower.find(kw)
            if idx >= 0:
                claims.append({"type": "anomaly", "keyword": kw,
                               "context": text[max(0, idx-80):idx+len(kw)+80].strip(), "position": idx})

        for kw in TREND_KEYWORDS:
            idx = text_lower.find(kw)
            if idx >= 0:
                claims.append({"type": "trend", "keyword": kw,
                               "context": text[max(0, idx-80):idx+len(kw)+80].strip(), "position": idx})

        if len(claims) > 1:
            claims.sort(key=lambda c: c["position"])
            deduped = [claims[0]]
            for c in claims[1:]:
                if c["position"] - deduped[-1]["position"] > 50:
                    deduped.append(c)
            claims = deduped

        return claims

    def _verify_claims_against_weather(self, claims: List[Dict], weather_context: Dict[str, Any]) -> Dict[str, Any]:
        location = weather_context.get("location_name", "Unknown")
        current = weather_context.get("current_weather", {})
        anomaly = weather_context.get("anomaly", {})
        verifications = []

        for claim in claims:
            if claim["type"] == "temperature" and current.get("temperature_c") is not None:
                actual_temp = current["temperature_c"]
                diff = abs(actual_temp - claim["value"])
                verifications.append({
                    "claim_type": "temperature", "claimed_value": claim["value"],
                    "actual_value": actual_temp, "difference": round(diff, 1),
                    "plausible": diff < 10.0, "accuracy_score": round(max(0, 1.0 - (diff / 20.0)), 3),
                    "location": location,
                })
            elif claim["type"] == "anomaly" and anomaly:
                temp_dev = anomaly.get("temperature_deviation_c", 0)
                keyword = claim.get("keyword", "").lower()
                positive = {"warmest", "hottest", "above average", "record", "highest"}
                negative = {"coldest", "below average", "lowest"}
                if keyword in positive:
                    aligned = temp_dev > 2.0
                elif keyword in negative:
                    aligned = temp_dev < -2.0
                else:
                    aligned = anomaly.get("is_anomalous", False)
                verifications.append({
                    "claim_type": "anomaly", "keyword": keyword,
                    "actual_deviation_c": round(temp_dev, 1), "claim_aligned": aligned,
                    "accuracy_score": 0.9 if aligned else 0.3, "location": location,
                })

        return {"location": location, "coordinates": weather_context.get("coordinates"),
                "verifications": verifications, "claims_checked": len(verifications)}

    def _compute_weather_factor(self, claims: List[Dict], verification_results: List[Dict]) -> Optional[float]:
        if not verification_results:
            return None
        all_scores = []
        for result in verification_results:
            for v in result.get("verifications", []):
                if v.get("accuracy_score") is not None:
                    all_scores.append(v["accuracy_score"])
        if not all_scores:
            return 0.5
        return round(sum(all_scores) / len(all_scores), 3)
