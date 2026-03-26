"""
Article Enrichment Service - Generates rich excerpts with weather context
and source reliability assessment.

This service enriches articles with:
- LLM-generated 200-400 word excerpts covering key findings, insights,
  source reliability, and localized climate context
- Climate context summaries mapping article topics to local weather data
- 5-year temperature trend analysis from Open-Meteo historical API
- Source credibility scoring from the source_credibility table

Primary LLM: Anthropic Claude
Fallback LLM: OpenAI GPT / DeepSeek
"""

import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.database import Database
from app.core.logging import get_logger
from app.domains.content.forecast_service import COUNTRY_COORDS, COUNTRY_NAMES

logger = get_logger(__name__)


class ArticleEnrichmentService:
    """Enriches articles with LLM-generated excerpts, weather context,
    and source reliability assessments."""

    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enrich_article(
        self,
        article_id: str,
        title: str,
        extracted_text: str,
        source_name: str,
        country_code: str,
        content_category: str = None,
    ) -> dict:
        """
        Enrich a single article with an LLM-generated excerpt, climate
        context summary, and enrichment metadata.

        The enrichment combines:
        1. Source credibility score from the database
        2. Current and historical weather context for the country
        3. 5-year temperature trend from Open-Meteo
        4. LLM synthesis of all the above into a rich excerpt

        Returns:
            dict with enriched_excerpt, climate_context_summary, and metadata.
        """
        cc = (country_code or "FI").upper()
        started_at = datetime.utcnow()

        # Gather data concurrently where possible
        credibility = self._fetch_source_credibility(source_name)
        weather_context = await self._fetch_weather_context(cc)
        temperature_trend = await self._fetch_5year_temperature_trend(cc)

        # Build the metadata bundle before LLM call
        metadata = {
            "source_name": source_name,
            "country_code": cc,
            "content_category": content_category,
            "credibility_score": credibility.get("overall_score") if credibility else None,
            "credibility_tier": credibility.get("reliability_tier") if credibility else None,
            "weather_available": weather_context is not None,
            "trend_available": temperature_trend is not None,
            "started_at": started_at.isoformat(),
        }

        # Generate enriched excerpt via LLM
        enriched_excerpt = await self._generate_enriched_excerpt(
            title=title,
            extracted_text=extracted_text,
            source_name=source_name,
            country_code=cc,
            credibility=credibility,
            weather_context=weather_context,
            temperature_trend=temperature_trend,
            content_category=content_category,
        )

        # Generate climate context summary via LLM
        climate_context_summary = await self._generate_climate_context_summary(
            title=title,
            extracted_text=extracted_text,
            country_code=cc,
            weather_context=weather_context,
            temperature_trend=temperature_trend,
        )

        finished_at = datetime.utcnow()
        metadata["finished_at"] = finished_at.isoformat()
        metadata["duration_seconds"] = round(
            (finished_at - started_at).total_seconds(), 2
        )
        metadata["llm_provider"] = metadata.get("llm_provider", "unknown")

        # Persist to database
        self._store_enrichment(
            article_id=article_id,
            enriched_excerpt=enriched_excerpt,
            climate_context_summary=climate_context_summary,
            metadata=metadata,
        )

        logger.info(
            "Article enriched",
            article_id=article_id,
            duration_s=metadata["duration_seconds"],
            weather=metadata["weather_available"],
            trend=metadata["trend_available"],
        )

        return {
            "enriched_excerpt": enriched_excerpt,
            "climate_context_summary": climate_context_summary,
            "metadata": metadata,
        }

    async def batch_enrich(self, limit: int = 50) -> dict:
        """
        Find and enrich articles that have not yet been enriched.

        Selects up to *limit* articles where enriched_at IS NULL,
        ordered by created_at DESC (newest first).

        Returns:
            dict with processed, failed, and skipped counts.
        """
        rows = self.db.execute_query(
            """SELECT article_id, title, COALESCE(extracted_text, '') AS extracted_text,
                      COALESCE(source_name, '') AS source_name,
                      COALESCE(country_code, 'FI') AS country_code,
                      content_category
               FROM articles
               WHERE enriched_at IS NULL
               ORDER BY created_at DESC
               LIMIT :lim""",
            {"lim": limit},
        )

        if not rows:
            logger.info("batch_enrich: no un-enriched articles found")
            return {"processed": 0, "failed": 0, "skipped": 0, "total_found": 0}

        processed = 0
        failed = 0
        skipped = 0

        for row in rows:
            article_id = str(row["article_id"])
            text = row.get("extracted_text", "")

            if not text or len(text.strip()) < 50:
                skipped += 1
                continue

            try:
                await self.enrich_article(
                    article_id=article_id,
                    title=row.get("title", ""),
                    extracted_text=text,
                    source_name=row.get("source_name", ""),
                    country_code=row.get("country_code", "FI"),
                    content_category=row.get("content_category"),
                )
                processed += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "batch_enrich: article failed",
                    article_id=article_id,
                    error=str(exc),
                )

        summary = {
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "total_found": len(rows),
        }
        logger.info("batch_enrich complete", **summary)
        return summary

    # ------------------------------------------------------------------
    # Data retrieval helpers
    # ------------------------------------------------------------------

    def _fetch_source_credibility(self, source_name: str) -> Optional[Dict[str, Any]]:
        """Look up the source credibility record by name.

        Tries exact match first, then falls back to domain-based ILIKE
        search so that e.g. 'www.yle.fi' matches 'YLE'.
        """
        if not source_name:
            return None

        # Exact match
        rows = self.db.execute_query(
            """SELECT overall_score, factual_reporting_score,
                      transparency_score, reliability_tier, source_type
               FROM source_credibility
               WHERE source_name = :name
               LIMIT 1""",
            {"name": source_name},
        )
        if rows:
            return dict(rows[0])

        # Domain-based fuzzy match (strip www. and TLD)
        domain_core = source_name.replace("www.", "").split(".")[0]
        if len(domain_core) >= 3:
            rows = self.db.execute_query(
                """SELECT overall_score, factual_reporting_score,
                          transparency_score, reliability_tier, source_type
                   FROM source_credibility
                   WHERE source_name ILIKE :pattern
                      OR source_url ILIKE :url_pattern
                   ORDER BY overall_score DESC
                   LIMIT 1""",
                {
                    "pattern": f"%{domain_core}%",
                    "url_pattern": f"%{domain_core}%",
                },
            )
            if rows:
                return dict(rows[0])

        return None

    async def _fetch_weather_context(self, country_code: str) -> Optional[Dict[str, Any]]:
        """Fetch current weather and 7-day forecast for a country's capital."""
        coords = COUNTRY_COORDS.get(country_code)
        if not coords:
            return None

        lat, lon = coords["lat"], coords["lon"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                        "timezone": "auto",
                        "forecast_days": 7,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Weather API returned non-200",
                        status=resp.status_code,
                        country=country_code,
                    )
                    return None

                data = resp.json()
                current = data.get("current", {})
                daily = data.get("daily", {})

                return {
                    "country_code": country_code,
                    "country_name": COUNTRY_NAMES.get(country_code, country_code),
                    "current_temp_c": current.get("temperature_2m"),
                    "current_humidity_pct": current.get("relative_humidity_2m"),
                    "current_precipitation_mm": current.get("precipitation"),
                    "weather_code": current.get("weather_code"),
                    "forecast_7day": {
                        "dates": daily.get("time", []),
                        "max_temps": daily.get("temperature_2m_max", []),
                        "min_temps": daily.get("temperature_2m_min", []),
                        "precipitation": daily.get("precipitation_sum", []),
                    },
                }
        except Exception as exc:
            logger.warning("Weather context fetch failed", country=country_code, error=str(exc))
            return None

    async def _fetch_5year_temperature_trend(
        self, country_code: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch 5 years of daily mean temperatures and compute annual
        averages plus overall trend direction."""
        coords = COUNTRY_COORDS.get(country_code)
        if not coords:
            return None

        lat, lon = coords["lat"], coords["lon"]
        today = date.today()
        start_date = date(today.year - 5, today.month, today.day)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": start_date.isoformat(),
                        "end_date": today.isoformat(),
                        "daily": "temperature_2m_mean",
                        "timezone": "auto",
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Historical API non-200",
                        status=resp.status_code,
                        country=country_code,
                    )
                    return None

                data = resp.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                temps = daily.get("temperature_2m_mean", [])

                if not dates or not temps:
                    return None

                # Group by year and compute annual averages
                year_temps: Dict[int, List[float]] = {}
                for d_str, t in zip(dates, temps):
                    if t is None:
                        continue
                    year = int(d_str[:4])
                    year_temps.setdefault(year, []).append(t)

                annual_averages: Dict[int, float] = {}
                for year, values in sorted(year_temps.items()):
                    if values:
                        annual_averages[year] = round(sum(values) / len(values), 2)

                if len(annual_averages) < 2:
                    return None

                # Compute trend: simple linear comparison first year vs last year
                years_sorted = sorted(annual_averages.keys())
                first_avg = annual_averages[years_sorted[0]]
                last_avg = annual_averages[years_sorted[-1]]
                total_change = round(last_avg - first_avg, 2)
                span_years = years_sorted[-1] - years_sorted[0]
                annual_change = round(total_change / max(span_years, 1), 2)

                if total_change > 0.3:
                    direction = "warming"
                elif total_change < -0.3:
                    direction = "cooling"
                else:
                    direction = "stable"

                return {
                    "country_code": country_code,
                    "country_name": COUNTRY_NAMES.get(country_code, country_code),
                    "period": f"{years_sorted[0]}-{years_sorted[-1]}",
                    "annual_averages": annual_averages,
                    "total_change_c": total_change,
                    "annual_change_c": annual_change,
                    "direction": direction,
                    "data_points": sum(len(v) for v in year_temps.values()),
                }
        except Exception as exc:
            logger.warning(
                "5-year trend fetch failed", country=country_code, error=str(exc)
            )
            return None

    # ------------------------------------------------------------------
    # LLM generation
    # ------------------------------------------------------------------

    async def _generate_enriched_excerpt(
        self,
        title: str,
        extracted_text: str,
        source_name: str,
        country_code: str,
        credibility: Optional[Dict],
        weather_context: Optional[Dict],
        temperature_trend: Optional[Dict],
        content_category: Optional[str],
    ) -> str:
        """Generate a 200-400 word enriched excerpt using an LLM."""
        # Truncate article text to keep prompt within limits
        text_snippet = extracted_text[:4000]
        country_name = COUNTRY_NAMES.get(country_code, country_code)

        # Build credibility section for the prompt
        cred_section = "No credibility data available for this source."
        if credibility:
            score = credibility.get("overall_score")
            tier = credibility.get("reliability_tier", "unknown")
            factual = credibility.get("factual_reporting_score")
            transparency = credibility.get("transparency_score")
            cred_section = (
                f"Source: {source_name}\n"
                f"Overall credibility score: {score}/100\n"
                f"Factual reporting score: {factual}/100\n"
                f"Transparency score: {transparency}/100\n"
                f"Reliability tier: {tier}"
            )

        # Build weather section
        weather_section = "No weather data available for this region."
        if weather_context:
            temp = weather_context.get("current_temp_c")
            humidity = weather_context.get("current_humidity_pct")
            precip = weather_context.get("current_precipitation_mm")
            weather_section = (
                f"Current conditions in {country_name}:\n"
                f"Temperature: {temp}C, Humidity: {humidity}%, "
                f"Precipitation: {precip}mm"
            )

        # Build trend section
        trend_section = "No 5-year temperature trend data available."
        if temperature_trend:
            direction = temperature_trend["direction"]
            total_change = temperature_trend["total_change_c"]
            period = temperature_trend["period"]
            annual_avgs = temperature_trend.get("annual_averages", {})
            avg_str = ", ".join(
                f"{y}: {t}C" for y, t in sorted(annual_avgs.items())
            )
            trend_section = (
                f"5-year temperature trend for {country_name} ({period}):\n"
                f"Direction: {direction} ({total_change:+.2f}C total change)\n"
                f"Annual averages: {avg_str}"
            )

        system_prompt = (
            "You are CliLens.AI, a climate news analysis platform. "
            "You write precise, informative article enrichments that help "
            "readers quickly understand climate news articles in context. "
            "Your output must be factual, measured, and evidence-based. "
            "Never fabricate data. If weather or trend data is unavailable, "
            "acknowledge it rather than inventing numbers."
        )

        user_prompt = f"""Write an enriched excerpt (200-400 words, plain prose paragraphs) for the following climate news article. The excerpt MUST contain all four sections woven into flowing paragraphs (not bullet points):

a) CONTENT DESCRIPTION: Summarize the article's main topic, key findings, and any data or claims presented.
b) KEY INSIGHTS: Explain the broader implications of the findings - why they matter and what they suggest.
c) SOURCE RELIABILITY: Assess the source's credibility using the data below. State the credibility score and what it means for the reader.
d) LOCALIZED CLIMATE CONTEXT: Connect the article's topic to the local weather and climate data provided. For example, if the article discusses rising temperatures, relate it to the observed temperature trend in the region. If weather data is unavailable, note that local verification was not possible.

ARTICLE TITLE: {title}
CONTENT CATEGORY: {content_category or 'general climate news'}
COUNTRY: {country_name} ({country_code})

ARTICLE TEXT (first 4000 chars):
{text_snippet}

SOURCE CREDIBILITY DATA:
{cred_section}

CURRENT WEATHER DATA:
{weather_section}

TEMPERATURE TREND DATA:
{trend_section}

Write the enriched excerpt now. Use flowing prose paragraphs, not bullet points or numbered lists. Weave all four aspects naturally together."""

        result = await self._call_llm(system_prompt, user_prompt, max_tokens=1200)

        if not result:
            # Fallback: generate a basic excerpt without LLM
            return self._generate_fallback_excerpt(
                title, extracted_text, source_name, credibility, weather_context, temperature_trend
            )

        return result

    async def _generate_climate_context_summary(
        self,
        title: str,
        extracted_text: str,
        country_code: str,
        weather_context: Optional[Dict],
        temperature_trend: Optional[Dict],
    ) -> str:
        """Generate a 2-3 sentence climate context summary mapping the
        article topic to local climate data."""
        country_name = COUNTRY_NAMES.get(country_code, country_code)
        text_snippet = extracted_text[:2000]

        # If no climate data at all, return a brief note
        if not weather_context and not temperature_trend:
            return (
                f"Local climate context for {country_name} is currently unavailable. "
                f"This article's claims could not be cross-referenced with regional weather data."
            )

        weather_info = ""
        if weather_context:
            temp = weather_context.get("current_temp_c")
            weather_info = f"Current temperature in {country_name}: {temp}C. "

        trend_info = ""
        if temperature_trend:
            direction = temperature_trend["direction"]
            total_change = temperature_trend["total_change_c"]
            period = temperature_trend["period"]
            trend_info = (
                f"The {period} temperature trend shows a {direction} pattern "
                f"with {total_change:+.2f}C total change. "
            )

        system_prompt = (
            "You are a climate data analyst. Write exactly 2-3 sentences "
            "connecting the article topic to local climate observations. "
            "Be specific with numbers when available."
        )

        user_prompt = f"""Based on the article about "{title}" in {country_name}, write 2-3 sentences explaining how the article's topic maps to local climate data.

{weather_info}{trend_info}

Article snippet: {text_snippet[:800]}

Write 2-3 sentences only. Be specific and data-driven."""

        result = await self._call_llm(system_prompt, user_prompt, max_tokens=300)

        if not result:
            # Fallback
            parts = []
            if weather_info:
                parts.append(weather_info.strip())
            if trend_info:
                parts.append(trend_info.strip())
            parts.append(
                f"This article on \"{title}\" should be evaluated "
                f"in the context of these regional climate observations."
            )
            return " ".join(parts)

        return result

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
    ) -> Optional[str]:
        """Call an LLM provider. Tries Anthropic first, then OpenAI, then DeepSeek."""

        # --- Anthropic Claude (primary) ---
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=anthropic_key)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                    max_tokens=max_tokens,
                    temperature=0.3,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                if message.content:
                    text = message.content[0].text.strip()
                    if text:
                        logger.debug("LLM response from Anthropic")
                        return text
            except Exception as exc:
                logger.warning("Anthropic LLM call failed", error=str(exc))

        # --- OpenAI GPT (first fallback) ---
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI as OpenAIClient

                client = OpenAIClient(api_key=openai_key)
                response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                text = response.choices[0].message.content.strip()
                if text:
                    logger.debug("LLM response from OpenAI")
                    return text
            except Exception as exc:
                logger.warning("OpenAI LLM call failed", error=str(exc))

        # --- DeepSeek (second fallback) ---
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                from openai import OpenAI as OpenAIClient

                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                )
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                text = response.choices[0].message.content.strip()
                if text:
                    logger.debug("LLM response from DeepSeek")
                    return text
            except Exception as exc:
                logger.warning("DeepSeek LLM call failed", error=str(exc))

        logger.error("All LLM providers failed — no API keys set or all calls errored")
        return None

    # ------------------------------------------------------------------
    # Fallback & persistence
    # ------------------------------------------------------------------

    def _generate_fallback_excerpt(
        self,
        title: str,
        extracted_text: str,
        source_name: str,
        credibility: Optional[Dict],
        weather_context: Optional[Dict],
        temperature_trend: Optional[Dict],
    ) -> str:
        """Generate a basic enriched excerpt without an LLM.

        Used when all LLM providers are unavailable.
        """
        parts = []

        # Content summary
        snippet = extracted_text[:600].strip()
        if snippet:
            parts.append(f"This article titled \"{title}\" reports: {snippet}")

        # Credibility
        if credibility:
            score = credibility.get("overall_score", "N/A")
            tier = credibility.get("reliability_tier", "unknown")
            parts.append(
                f"The source ({source_name}) has a credibility score of "
                f"{score}/100 (tier: {tier})."
            )
        else:
            parts.append(
                f"No credibility assessment is available for {source_name}."
            )

        # Weather & trend
        if weather_context:
            temp = weather_context.get("current_temp_c")
            country = weather_context.get("country_name", "the region")
            parts.append(
                f"Current temperature in {country} is {temp}C."
            )
        if temperature_trend:
            direction = temperature_trend["direction"]
            change = temperature_trend["total_change_c"]
            period = temperature_trend["period"]
            parts.append(
                f"The {period} temperature trend for this region shows "
                f"a {direction} pattern ({change:+.2f}C)."
            )

        return " ".join(parts)

    def _store_enrichment(
        self,
        article_id: str,
        enriched_excerpt: str,
        climate_context_summary: str,
        metadata: dict,
    ) -> None:
        """Persist enrichment results to the articles table."""
        try:
            self.db.execute_update(
                """UPDATE articles
                   SET enriched_excerpt = :excerpt,
                       climate_context_summary = :climate,
                       enrichment_metadata = :meta,
                       enriched_at = NOW(),
                       updated_at = NOW()
                   WHERE article_id = :id""",
                {
                    "id": article_id,
                    "excerpt": enriched_excerpt,
                    "climate": climate_context_summary,
                    "meta": json.dumps(metadata),
                },
            )
        except Exception as exc:
            logger.error(
                "Failed to store enrichment",
                article_id=article_id,
                error=str(exc),
            )
