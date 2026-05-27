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
from pathlib import Path
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
        # Per-article state populated by enrich_article() so the LLM helpers
        # can attribute training rows + metadata without changing every
        # signature. Safe because enrich_article runs serially per instance.
        self._current_article_id: Optional[str] = None
        self._llm_providers_used: List[str] = []
        self._llm_models_used: List[str] = []

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

        # Reset per-article LLM tracking
        self._current_article_id = article_id
        self._llm_providers_used = []
        self._llm_models_used = []

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
        # Stage 2 (M2): persist the actual weather + trend data points so
        # the FE WeatherTrendCard can render a sparkline + current
        # conditions card. Previously we fetched this data, used it in
        # the LLM prompt, then threw it away — meaning the FE could only
        # show a yes/no boolean instead of the actual numbers. Now stored
        # in enrichment_metadata.weather / .temperature_trend.
        if weather_context:
            metadata["weather"] = {
                "current_temp_c": weather_context.get("current_temp_c"),
                "current_humidity_pct": weather_context.get("current_humidity_pct"),
                "current_precipitation_mm": weather_context.get("current_precipitation_mm"),
                "weather_code": weather_context.get("weather_code"),
                "forecast_7day": weather_context.get("forecast_7day"),
            }
        if temperature_trend:
            metadata["temperature_trend"] = {
                "direction": temperature_trend.get("direction"),
                "total_change_c": temperature_trend.get("total_change_c"),
                "period": temperature_trend.get("period"),
                "annual_averages": temperature_trend.get("annual_averages") or {},
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

        # Golden Example #5 (2026-05-27): generate the executive brief —
        # a tight 100-180 word top-of-article summary that goes ABOVE
        # the enriched_excerpt. The audit showed executive_brief 0%
        # populated across the corpus; this third LLM call closes the gap.
        executive_brief = await self._generate_executive_brief(
            title=title,
            extracted_text=extracted_text,
            country_code=cc,
            content_category=content_category,
        )

        # Golden Example fix follow-up (2026-05-27): the 2026-05-26 cloud
        # backfill landed every other enrichment column correctly but
        # executive_brief came back empty across all 10 curated articles.
        # Either the brief LLM call returned an empty string (so
        # `_call_llm`'s `if text:` guard fell through every provider) or
        # the column was a legacy empty-string default that COALESCE
        # preserved. Either way the FE shows nothing. Fall back to the
        # first ~150 words of the enriched_excerpt so the brief slot is
        # always populated when the long excerpt landed.
        # Diagnostic: log inputs to fallback so we can see why brief stays empty
        logger.info(
            "brief-fallback-check",
            article_id=article_id,
            llm_brief_len=len(executive_brief) if executive_brief else 0,
            llm_brief_is_none=executive_brief is None,
            excerpt_len=len(enriched_excerpt) if enriched_excerpt else 0,
        )
        if not executive_brief and enriched_excerpt:
            words = enriched_excerpt.split()
            fallback = " ".join(words[:150])
            if len(words) > 150:
                fallback = fallback.rstrip(".,;:") + "…"
            executive_brief = fallback
            logger.info(
                "brief-fallback-fired",
                article_id=article_id,
                fallback_chars=len(executive_brief),
            )

        finished_at = datetime.utcnow()
        metadata["finished_at"] = finished_at.isoformat()
        metadata["duration_seconds"] = round(
            (finished_at - started_at).total_seconds(), 2
        )
        # Record which providers/models actually produced this row's output.
        # Distinct list so a single provider used twice (excerpt + summary)
        # shows once. If no LLM was called (all fallbacks), keep "fallback".
        if self._llm_providers_used:
            distinct_providers = list(dict.fromkeys(self._llm_providers_used))
            distinct_models = list(dict.fromkeys(self._llm_models_used))
            metadata["llm_provider"] = ",".join(distinct_providers)
            metadata["llm_model"] = ",".join(distinct_models)
        else:
            metadata["llm_provider"] = "fallback"
            metadata["llm_model"] = "none"

        # Persist to database
        logger.info(
            "brief-before-store",
            article_id=article_id,
            brief_chars=len(executive_brief) if executive_brief else 0,
            brief_is_none=executive_brief is None,
        )
        self._store_enrichment(
            article_id=article_id,
            enriched_excerpt=enriched_excerpt,
            climate_context_summary=climate_context_summary,
            executive_brief=executive_brief,
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
            "executive_brief": executive_brief,
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
        # Lane A worker (GX10) prefers articles flagged
        # enrichment_metadata.golden_priority=true — driven by the
        # autonomous overnight pipeline at scripts/golden_pipeline_daemon.py
        # which queues curated T1-source climate articles via the
        # /api/admin/backfill/golden-queue endpoint. Falls back to the
        # standard newest-first order when no priority articles are pending.
        rows = self.db.execute_query(
            """SELECT article_id, title, COALESCE(extracted_text, '') AS extracted_text,
                      COALESCE(source_name, '') AS source_name,
                      COALESCE(country_code, 'FI') AS country_code,
                      content_category
               FROM articles
               WHERE enriched_at IS NULL
                 AND is_synthetic = FALSE
               ORDER BY
                   COALESCE((enrichment_metadata->>'golden_priority')::boolean, false) DESC,
                   created_at DESC
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

                # Group daily temps by year. Track count separately so we
                # can drop incomplete years (the current year typically has
                # only Jan-current-month, and a partial cool/warm window
                # creates fake "-7°C cooling trend" results — see
                # Golden-Artifact-Examples-2026-05-27.md §1 bug catalog).
                year_temps: Dict[int, List[float]] = {}
                for d_str, t in zip(dates, temps):
                    if t is None:
                        continue
                    year = int(d_str[:4])
                    year_temps.setdefault(year, []).append(t)

                # COMPLETE-YEAR FILTER: a real year has ~340-366 daily
                # observations. Cap the floor at 330 (allows for archive
                # gaps but excludes Jan-May partial years). Without this
                # the trend math compared 2021's 365-day average to
                # 2026's 145-day winter-only average and produced -7.65°C.
                COMPLETE_YEAR_MIN_DAYS = 330
                annual_averages: Dict[int, float] = {}
                for year, values in sorted(year_temps.items()):
                    if values and len(values) >= COMPLETE_YEAR_MIN_DAYS:
                        annual_averages[year] = round(sum(values) / len(values), 2)

                if len(annual_averages) < 2:
                    logger.info(
                        "5-year trend: too few complete years (need 2+, got %s)",
                        len(annual_averages),
                    )
                    return None

                # Compute trend: simple linear comparison first vs last
                # complete year (now safe — both have ~full annual coverage).
                years_sorted = sorted(annual_averages.keys())
                first_avg = annual_averages[years_sorted[0]]
                last_avg = annual_averages[years_sorted[-1]]
                total_change = round(last_avg - first_avg, 2)
                span_years = years_sorted[-1] - years_sorted[0]
                annual_change = round(total_change / max(span_years, 1), 2)

                # Sanity cap: real 5-yr climate trends are bounded at
                # roughly ±2°C even in fast-warming regions. Anything
                # beyond ±4°C indicates instrumentation noise or a
                # remaining math bug — return None rather than feed a
                # nonsense number into the LLM enrichment prompt.
                if abs(total_change) > 4.0:
                    logger.warning(
                        "5-year trend: implausible total_change=%.2f for %s; "
                        "discarding (years=%s)",
                        total_change, country_code, years_sorted,
                    )
                    return None

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
                    "complete_years": list(years_sorted),
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
            "acknowledge it rather than inventing numbers. "
            # Language-default fix (2026-05-25, user-reported): the
            # platform stores enrichments in a single canonical
            # language so cross-country comparisons and search ranking
            # are consistent. User-facing translation is offered as a
            # post-hoc step via /api/translation, NOT by writing the
            # enrichment in the source article's language.
            "ALWAYS write the enriched excerpt in ENGLISH, regardless of "
            "what language the source article is in. If the source is "
            "non-English, translate concepts and quoted figures into "
            "English; do NOT mirror the source language."
        )

        user_prompt = f"""Write an enriched excerpt (200-400 words, plain prose paragraphs, in ENGLISH) for the following climate news article. The excerpt MUST contain all four sections woven into flowing paragraphs (not bullet points):

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

        text, provider, model = result
        self._record_llm_call(provider, model)
        self._append_training_row(
            task="enriched_excerpt",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_output=text,
            provider=provider,
            model=model,
            country_code=country_code,
            source_name=source_name,
        )
        # End2End audit hotfix (2026-05-26) — the audit's top-1 priority
        # was that claim_provenance ledger was empty in production. The
        # 3 existing call sites (url_analysis, deep_search, cynefin) all
        # write provenance, but article_enrichment_service — the HIGHEST
        # VOLUME LLM path — did not. Wiring it here populates the ledger
        # with one row per enrichment call, restoring the "every output
        # traceable" promise at the right point in the pipeline.
        self._record_enrichment_provenance(
            task="enriched_excerpt",
            provider=provider,
            model=model,
            prompt_name="article_enriched_excerpt",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return text

    async def _generate_executive_brief(
        self,
        title: str,
        extracted_text: str,
        country_code: str,
        content_category: Optional[str],
    ) -> Optional[str]:
        """Generate a 100-180 word executive brief — the top-of-article
        summary that goes above the long enriched_excerpt.

        Golden Example #5 (2026-05-27): adds a third LLM call to populate
        the `articles.executive_brief` column that the FE expects but the
        End2End audit caught as 0% populated across the entire corpus.
        Different from enriched_excerpt: this is TIGHT (target ~150
        words), neutral framing, news-style lede. enriched_excerpt is
        the 400-800 word analytical version with credibility + climate
        context layered in. Both have a role on the article page.

        Returns None gracefully on LLM failure — _store_enrichment uses
        COALESCE so an existing brief is preserved rather than nulled.
        """
        country_name = COUNTRY_NAMES.get(country_code, country_code)
        text_snippet = extracted_text[:3500]

        system_prompt = (
            "You write 100-180 word news-style executive briefs summarising "
            "climate articles for a busy professional audience. ALWAYS write "
            "in English. Lead with the most important fact. Be neutral and "
            "concrete. No editorial framing, no boosterism, no value "
            "judgements. Do not invent facts not in the source. If the "
            "article isn't actually about climate, say so plainly in the "
            "first sentence."
        )

        user_prompt = (
            f"Article title: {title}\n"
            f"Source country: {country_name}\n"
            f"Content category hint: {content_category or 'unspecified'}\n\n"
            f"Article body:\n{text_snippet}\n\n"
            "Write a 100-180 word executive brief. Plain prose, no headings, "
            "no bullet lists. End with one sentence on why a climate-focused "
            "reader should or shouldn't care about this article."
        )

        result = await self._call_llm(system_prompt, user_prompt, max_tokens=350)
        if not result:
            return None
        text, provider, model = result
        self._record_llm_call(provider, model)
        self._append_training_row(
            task="executive_brief",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_output=text,
            provider=provider,
            model=model,
            country_code=country_code,
            source_name=None,
        )
        self._record_enrichment_provenance(
            task="executive_brief",
            provider=provider,
            model=model,
            prompt_name="article_executive_brief",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return text.strip()

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
            "Be specific with numbers when available. "
            # Language-default fix (2026-05-25) — always English so the
            # comparison + search layers see one canonical language.
            "ALWAYS write your output in ENGLISH, regardless of the "
            "source article's language."
        )

        user_prompt = f"""Based on the article about "{title}" in {country_name}, write 2-3 sentences (in ENGLISH) explaining how the article's topic maps to local climate data.

{weather_info}{trend_info}

Article snippet: {text_snippet[:800]}

Write 2-3 sentences only, in English. Be specific and data-driven."""

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

        text, provider, model = result
        self._record_llm_call(provider, model)
        self._append_training_row(
            task="climate_context_summary",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_output=text,
            provider=provider,
            model=model,
            country_code=country_code,
            source_name=None,
        )
        self._record_enrichment_provenance(
            task="climate_context_summary",
            provider=provider,
            model=model,
            prompt_name="climate_context_summary",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return text

    def _record_enrichment_provenance(
        self,
        task: str,
        provider: str,
        model: str,
        prompt_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> None:
        """Write one claim_provenance row per enrichment LLM call.

        Best-effort: silently drops on any failure (missing db handle,
        no current_article_id, missing migration). Pipeline NEVER breaks
        because audit trail recording failed.

        Added 2026-05-26 per End2End audit top-1 priority — the ledger
        was empty in production because the highest-volume LLM path
        (article enrichment, every ingested article) never wrote to it.
        """
        if not self._current_article_id or not self.db:
            return
        try:
            import hashlib
            from app.domains.intelligence.provenance import (
                record_provenance,
                ProvenanceRecord,
                EXTRACTION_INGESTION,
            )

            # Fingerprint = first 16 hex chars of sha256(system + user)
            # so prompt-diff replay can group provenance rows by template.
            fp_raw = (system_prompt + "\n" + user_prompt).encode("utf-8", errors="ignore")
            fingerprint = hashlib.sha256(fp_raw).hexdigest()[:16]

            record_provenance(
                self.db,
                ProvenanceRecord(
                    extraction_method=EXTRACTION_INGESTION,
                    article_id=self._current_article_id,
                    model_name=model,
                    prompt_name=prompt_name,
                    prompt_version="v1.0",
                    prompt_fingerprint=fingerprint,
                    retrieval_strategy=f"enrichment.{task}",
                    raw_metadata={"provider": provider, "task": task},
                ),
            )
        except Exception as exc:
            logger.debug(
                "enrichment record_provenance failed (non-fatal): %s",
                exc,
            )

    def _record_llm_call(self, provider: str, model: str) -> None:
        """Track which LLM produced output for the current article so
        metadata + JSONL can attribute it correctly."""
        self._llm_providers_used.append(provider)
        self._llm_models_used.append(model)

    def _append_training_row(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        assistant_output: str,
        provider: str,
        model: str,
        country_code: str,
        source_name: Optional[str],
    ) -> None:
        """Append one ChatML-formatted training row to the JSONL dataset
        when CLILENS_TRAINING_DATASET_PATH is set. Used to build SFT data
        for distilling enrichment quality into a smaller model later."""
        path = os.getenv("CLILENS_TRAINING_DATASET_PATH")
        if not path:
            return

        row = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": assistant_output},
            ],
            "meta": {
                "article_id": self._current_article_id,
                "country_code": country_code,
                "source_name": source_name,
                "provider": provider,
                "model": model,
                "task": task,
                "ts": datetime.utcnow().isoformat() + "Z",
            },
        }
        try:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning(
                "Failed to append training row",
                path=path,
                article_id=self._current_article_id,
                error=str(exc),
            )

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1200,
    ) -> Optional[Tuple[str, str, str]]:
        """Call an LLM provider and return (text, provider, model).

        Default order is DeepSeek → OpenAI → Anthropic (cheap first, premium
        last). Set CLILENS_ENRICHMENT_PROVIDER=deepseek|openai|anthropic to
        pin a single provider and disable fallback (used by the backfill
        runner to keep cost predictable).
        """

        # GX10 polish wave (2026-05-25, audit recommendation #1) —
        # `local-gx10` joins the pin set. Workflow:
        #   1. GX10 serves vLLM at CLILENS_LOCAL_GX10_BASE_URL
        #   2. Set CLILENS_ENRICHMENT_PROVIDER=local-gx10 on Cloud Run
        #   3. This branch runs first; if unreachable / fails for any
        #      reason, the fallback list (deepseek, openai, anthropic)
        #      auto-engages so production never breaks while GX10 is
        #      being warmed up or restarted.
        pin = os.getenv("CLILENS_ENRICHMENT_PROVIDER", "").strip().lower()
        if pin == "local-gx10":
            order = ["local-gx10", "deepseek", "openai", "anthropic"]
        elif pin in {"deepseek", "openai", "anthropic"}:
            order = [pin]
        else:
            order = ["deepseek", "openai", "anthropic"]

        for provider in order:
            if provider == "local-gx10":
                base_url = os.getenv("CLILENS_LOCAL_GX10_BASE_URL")
                api_key = os.getenv("CLILENS_LOCAL_GX10_API_KEY", "EMPTY")
                if not base_url:
                    # GX10 not configured — silent skip to next provider.
                    continue
                try:
                    from openai import OpenAI as OpenAIClient
                    model = os.getenv(
                        "CLILENS_LOCAL_GX10_MODEL", "Qwen/Qwen2.5-14B-Instruct"
                    )
                    # 2026-05-27: bumped from 60s to 240s. Local cold-loads on
                    # Ollama can take 15-25s for a 14B Q4 model on Grace
                    # Blackwell, plus ~10s to generate a 400-word enrichment.
                    # The previous 60s cap was triggering Ollama-side 500s
                    # when the OpenAI client cut the connection mid-generation.
                    # Env override: CLILENS_LOCAL_GX10_TIMEOUT (seconds).
                    timeout_s = float(os.getenv("CLILENS_LOCAL_GX10_TIMEOUT", "240"))
                    client = OpenAIClient(
                        api_key=api_key, base_url=base_url, timeout=timeout_s
                    )
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=0.3,
                    )
                    msg = response.choices[0].message
                    # 2026-05-27: reasoning-style local models (Nemotron-3,
                    # DeepSeek-R1, etc.) on Ollama emit the actual answer in a
                    # non-standard `reasoning` field while `content` stays empty.
                    # The OpenAI SDK exposes such fields via model_extra. Fall
                    # back to that whole-message dump when content is blank so
                    # we don't silently miss a successful call + fall through
                    # to DeepSeek — which is what the End2End audit caught.
                    text = (getattr(msg, "content", None) or "").strip()
                    if not text:
                        try:
                            extras = (msg.model_extra or {}) if hasattr(msg, "model_extra") else {}
                            text = (
                                extras.get("reasoning")
                                or extras.get("thinking")
                                or extras.get("reasoning_content")
                                or ""
                            ).strip()
                        except Exception:
                            text = ""
                    if text:
                        logger.info(
                            "local-gx10 LLM call succeeded",
                            model=model,
                            chars=len(text),
                        )
                        return text, "local-gx10", model
                    # No usable content even after the reasoning-field check.
                    logger.warning(
                        "local-gx10 returned empty content; falling back to next provider",
                        model=model,
                    )
                except Exception as exc:
                    # Fall through to next provider in the chain — never
                    # let local-gx10 unavailability break enrichment.
                    logger.warning(
                        "local-gx10 LLM call failed; falling back to next provider",
                        error=str(exc),
                    )

            elif provider == "deepseek":
                key = os.getenv("DEEPSEEK_API_KEY")
                if not key:
                    continue
                try:
                    from openai import OpenAI as OpenAIClient
                    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                    client = OpenAIClient(
                        api_key=key,
                        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    )
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=0.3,
                    )
                    text = response.choices[0].message.content.strip()
                    if text:
                        return text, "deepseek", model
                except Exception as exc:
                    logger.warning("DeepSeek LLM call failed", error=str(exc))

            elif provider == "openai":
                key = os.getenv("OPENAI_API_KEY")
                if not key:
                    continue
                try:
                    from openai import OpenAI as OpenAIClient
                    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                    client = OpenAIClient(api_key=key)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=0.3,
                    )
                    text = response.choices[0].message.content.strip()
                    if text:
                        return text, "openai", model
                except Exception as exc:
                    logger.warning("OpenAI LLM call failed", error=str(exc))

            elif provider == "anthropic":
                key = os.getenv("ANTHROPIC_API_KEY")
                if not key:
                    continue
                try:
                    import anthropic
                    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
                    client = anthropic.Anthropic(api_key=key)
                    message = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=0.3,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                    )
                    if message.content:
                        text = message.content[0].text.strip()
                        if text:
                            return text, "anthropic", model
                except Exception as exc:
                    logger.warning("Anthropic LLM call failed", error=str(exc))

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
        executive_brief: Optional[str] = None,
    ) -> None:
        """Persist enrichment results to the articles table.

        Golden Example #5 (2026-05-27): now writes executive_brief too.
        Backward compat: callers that don't pass executive_brief just
        leave that column NULL (was the old behavior anyway).
        """
        try:
            self.db.execute_update(
                """UPDATE articles
                   SET enriched_excerpt = :excerpt,
                       climate_context_summary = :climate,
                       executive_brief = COALESCE(NULLIF(:brief, ''), NULLIF(executive_brief, ''), :brief),
                       enrichment_metadata = :meta,
                       enriched_at = NOW(),
                       updated_at = NOW()
                   WHERE article_id = :id""",
                {
                    "id": article_id,
                    "excerpt": enriched_excerpt,
                    "climate": climate_context_summary,
                    "brief": executive_brief,
                    "meta": json.dumps(metadata),
                },
            )
        except Exception as exc:
            logger.error(
                "Failed to store enrichment",
                article_id=article_id,
                error=str(exc),
            )
