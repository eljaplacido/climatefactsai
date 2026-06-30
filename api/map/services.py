import json
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import httpx

from shared.logger import setup_logging
from .cache import _cache_get, _cache_set, _query_sessions
from .models import REGION_COUNTRIES, CountryStats

logger = setup_logging("map-api")


def _get_country_names(db) -> Dict[str, str]:
    """Build country name lookup."""
    from app.domains.content.forecast_service import COUNTRY_NAMES
    names = dict(COUNTRY_NAMES)
    try:
        rows = db.execute_query("SELECT country_code, country_name FROM countries")
        for r in (rows or []):
            names[r["country_code"]] = r["country_name"]
    except Exception:
        pass
    return names


def _country_region(cc: str) -> Optional[str]:
    """Determine which region a country belongs to."""
    for region, codes in REGION_COUNTRIES.items():
        if cc in codes:
            return region
    return None


# The article-volume `_compute_climate_risk_score` / `_reliability_risk_component`
# were removed (2026-06-30): physical climate risk now derives from projected
# warming everywhere (choropleth, /country-stats, /detail, /compare). The
# duplicate is gone for good — see `warming_to_risk_score` below.


# ---------------------------------------------------------------------------
# Physical climate risk (Phase 1) — derived from projected warming, NOT
# article volume. Uses IPCC AR6 SSP2-4.5 warming at 2050 from
# `country_projections` (migration 035). This replaces the article-volume
# proxy as the score that colours the map's "Climate Risk" layer so the layer
# means hazard, not media coverage.
# ---------------------------------------------------------------------------

WARMING_RISK_SCENARIO = "SSP2-4.5"
WARMING_RISK_HORIZON_YEAR = 2050
# Map a projected warming anomaly (°C) onto a 0-10 hazard band. 1.5°C (Paris
# floor) → 0; 5.0°C (high-end regional warming) → 10.
WARMING_RISK_FLOOR_C = 1.5
WARMING_RISK_CEILING_C = 5.0


def warming_to_risk_score(temp_anomaly_c: Optional[float]) -> Optional[float]:
    """Convert a projected warming anomaly (°C) into a 0-10 physical-risk score.

    Returns None when no projection is available so callers can render a
    distinct "no data" colour instead of a misleading low/zero risk.
    """
    if temp_anomaly_c is None:
        return None
    try:
        anomaly = float(temp_anomaly_c)
    except (TypeError, ValueError):
        return None
    span = WARMING_RISK_CEILING_C - WARMING_RISK_FLOOR_C
    score = (anomaly - WARMING_RISK_FLOOR_C) / span * 10.0
    return round(max(0.0, min(10.0, score)), 1)


def fetch_warming_risk_map(
    db,
    scenario: str = WARMING_RISK_SCENARIO,
    horizon_year: int = WARMING_RISK_HORIZON_YEAR,
) -> Dict[str, Optional[float]]:
    """Per-country physical climate-risk scores from `country_projections`.

    Reads SSP2-4.5 warming at the given horizon and maps it to 0-10.
    Excludes the invalid placeholder country code 'XX'. Returns an empty map
    (callers fall back to None → grey) if the table is unavailable.
    """
    out: Dict[str, Optional[float]] = {}
    try:
        rows = db.execute_query(
            """
            SELECT country_code, temp_anomaly_c
            FROM country_projections
            WHERE scenario = :scenario AND horizon_year = :horizon
            """,
            {"scenario": scenario, "horizon": horizon_year},
        )
    except Exception as exc:
        logger.warning(f"Warming-risk projection fetch failed: {exc}")
        return out
    for r in (rows or []):
        cc = r.get("country_code")
        if not cc or cc == "XX":
            continue
        out[cc] = warming_to_risk_score(r.get("temp_anomaly_c"))
    return out


# ---------------------------------------------------------------------------
# Weather helpers (Open-Meteo, free, no key)
# ---------------------------------------------------------------------------

async def _fetch_current_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch current weather from Open-Meteo forecast API."""
    cache_key = f"weather:current:{lat:.2f},{lon:.2f}"
    cached = _cache_get(cache_key, ttl_seconds=3600)  # 1-hour cache
    if cached is not None:
        return cached
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
            f"&daily=precipitation_sum&forecast_days=1"
            f"&timezone=auto"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        current = data.get("current", {})
        daily = data.get("daily", {})
        daily_precip = (daily.get("precipitation_sum") or [None])[0]
        result = {
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "precipitation_mm": daily_precip if daily_precip is not None else current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
        }
        _cache_set(cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"Open-Meteo current fetch failed ({lat},{lon}): {e}")
        return None


async def _fetch_historical_weather(
    lat: float, lon: float, start_date: str, end_date: str,
) -> Optional[Dict[str, Any]]:
    """Fetch historical daily data from Open-Meteo archive API."""
    cache_key = f"weather:hist:{lat:.2f},{lon:.2f}:{start_date}:{end_date}"
    cached = _cache_get(cache_key, ttl_seconds=86400)  # 24-hour cache
    if cached is not None:
        return cached
    try:
        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&daily=temperature_2m_mean,precipitation_sum"
            f"&timezone=auto"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        daily = data.get("daily", {})
        temps = [t for t in (daily.get("temperature_2m_mean") or []) if t is not None]
        precip = [p for p in (daily.get("precipitation_sum") or []) if p is not None]
        result = {
            "temperature_avg": round(sum(temps) / len(temps), 1) if temps else None,
            "precipitation_avg": round(sum(precip) / len(precip), 1) if precip else None,
        }
        _cache_set(cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"Open-Meteo archive fetch failed ({lat},{lon}): {e}")
        return None


# ---------------------------------------------------------------------------
# LLM helpers for enhanced /query
# ---------------------------------------------------------------------------

async def _llm_parse_query(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Use LLM to parse natural-language query into structured filters."""
    try:
        from app.domains.intelligence.llm_client import get_llm_client
        client, model = get_llm_client()
        if not client:
            return {}

        # Include prior context for follow-ups
        session_context = ""
        if session_id and session_id in _query_sessions:
            prev = _query_sessions[session_id]
            session_context = (
                f"\nPrevious query context: {json.dumps(prev.get('last_parsed', {}))}\n"
                f"Previous query: {prev.get('last_query', '')}\n"
            )

        system_prompt = (
            "You are a query parser for a climate news map. Extract structured filters "
            "from the user's natural language query. Return ONLY valid JSON with these "
            "optional fields: countries (list of ISO 2-letter codes), region (one of: "
            "europe, north_america, latin_america, africa, asia, middle_east), "
            "sources (list of source names), categories (list), topic (string), "
            "date_from (YYYY-MM-DD), date_to (YYYY-MM-DD), intent (string describing "
            "what the user wants). If you cannot determine a field, omit it."
        )
        user_prompt = f"{session_context}User query: {query}\n\nReturn JSON only."

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(raw)

        # Store in session
        if session_id:
            _query_sessions[session_id] = {
                "last_query": query,
                "last_parsed": parsed,
                "ts": time.time(),
            }

        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        logger.warning(f"LLM query parse failed: {e}")
        return {}


async def _llm_generate_map_answer(
    db, query: str, highlights: List[CountryStats], total: int,
    where_clause: str, params: Dict[str, Any],
    session_id: Optional[str] = None,
) -> tuple:
    """Generate an LLM answer with article citations for the map query."""
    try:
        from app.domains.intelligence.llm_client import get_llm_client
        client, model = get_llm_client()
        if not client:
            # No LLM configured/reachable — degrade gracefully. MUST return the
            # 3-tuple shape the caller unpacks (answer, session_id, actions);
            # returning a 2-tuple here 500'd every map "ask" query whenever the
            # LLM was unavailable (and broke CI, which has no keys).
            return None, session_id, []

        # Fetch a handful of matching articles for citation context
        article_rows = db.execute_query(f"""
            SELECT a.title, a.source_name, a.excerpt, a.country_code,
                   a.overall_credibility, a.published_date
            FROM articles a WHERE {where_clause}
            ORDER BY a.created_at DESC LIMIT 8
        """, params)

        articles_context = ""
        for i, ar in enumerate(article_rows or [], 1):
            articles_context += (
                f"[{i}] \"{ar.get('title', 'Untitled')}\" "
                f"({ar.get('source_name', 'Unknown')}, "
                f"credibility: {ar.get('overall_credibility', 'N/A')}) "
                f"— {(ar.get('excerpt') or '')[:150]}\n"
            )

        # Session history
        session_context = ""
        if session_id and session_id in _query_sessions:
            prev = _query_sessions[session_id]
            session_context = f"Previous question: {prev.get('last_query', '')}\n"

        country_names_map = _get_country_names(db)
        top_countries = ", ".join(
            f"{country_names_map.get(h.country_code, h.country_code)} ({h.article_count} articles)"
            for h in highlights[:5]
        )

        system_prompt = (
            "You are Climatefacts.ai's climate map assistant. Answer the user's question "
            "about climate news using the article data below. Cite articles by their "
            "number [1], [2] etc. Be concise (2-4 sentences). Mention relevant "
            "countries and credibility when appropriate."
        )
        from app.domains.intelligence.chat_actions import (
            actions_prompt_suffix, split_actions,
        )
        user_prompt = (
            f"{session_context}"
            f"ARTICLES:\n{articles_context}\n"
            f"STATS: {total} articles across {len(highlights)} countries. "
            f"Top: {top_countries}.\n\n"
            f"QUESTION: {query}"
            f"{actions_prompt_suffix()}"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        # Strip the trailing JSON actions block from the display text so the
        # chips render but the raw JSON never leaks into the bubble.
        answer, actions = split_actions(answer)

        # Generate or reuse session_id
        if not session_id:
            from uuid import uuid4
            session_id = str(uuid4())
        _query_sessions[session_id] = {
            "last_query": query,
            "last_parsed": {},
            "last_answer": answer,
            "ts": time.time(),
        }

        return answer, session_id, actions
    except Exception as e:
        logger.warning(f"LLM map answer generation failed: {e}")
        return None, session_id, []
