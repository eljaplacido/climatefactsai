"""
Map Routes — Global geographic article distribution, topic density, and agentic query.

Provides per-country article counts, top topics, source/reliability filtering,
heatmap data, and natural-language query endpoint for chat-driven map updates.
"""

import json
import math
import os
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_optional_user

logger = setup_logging("map-api")
router = APIRouter(prefix="/api/map", tags=["Map"])

# ---------------------------------------------------------------------------
# Simple in-memory TTL cache for weather / layer data
# ---------------------------------------------------------------------------
_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str, ttl_seconds: int = 21600) -> Optional[Any]:
    """Return cached value if it exists and has not expired."""
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl_seconds:
        return entry["value"]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = {"value": value, "ts": time.time()}


# ---------------------------------------------------------------------------
# In-memory session store for enhanced /query follow-ups
# ---------------------------------------------------------------------------
_query_sessions: Dict[str, Dict[str, Any]] = {}


class CountryStats(BaseModel):
    """Per-country article statistics for the map view."""
    country_code: str
    country_name: str
    article_count: int = 0
    top_topics: List[str] = []
    last_updated: Optional[str] = None
    avg_credibility_score: Optional[float] = None
    top_sources: List[str] = []
    region: Optional[str] = None
    temperature_anomaly: Optional[float] = None
    climate_risk_score: Optional[float] = None
    source_count: Optional[int] = None
    company_count: Optional[int] = None
    sbti_validated_count: Optional[int] = None
    net_zero_target_count: Optional[int] = None


class TopicDensityItem(BaseModel):
    """Topic density per country for heatmap overlay."""
    country_code: str
    topic: str
    article_count: int = 0
    density: float = 0.0


class SourceCoverageItem(BaseModel):
    """Which sources cover which countries."""
    source_name: str
    country_code: str
    article_count: int = 0
    avg_credibility: Optional[float] = None


class MapQueryRequest(BaseModel):
    """Natural-language or structured query for map-driven exploration."""
    query: Optional[str] = Field(None, max_length=500, description="Natural language query")
    countries: List[str] = Field(default_factory=list, description="Filter by country codes")
    region: Optional[str] = Field(None, description="Filter by region: europe, africa, asia, etc.")
    sources: List[str] = Field(default_factory=list, description="Filter by source names")
    reliability_min: Optional[int] = Field(None, ge=0, le=100)
    categories: List[str] = Field(default_factory=list)
    topic: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    session_id: Optional[str] = Field(None, description="Session ID for follow-up queries")
    view_context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "What the user is currently viewing on the map (selected country, "
            "compare overlay, etc.). Used to ground pronoun resolution in the "
            "agentic answer; same shape as /api/chat view_context."
        ),
    )
    source_mode: Optional[str] = Field(
        "platform",
        description=(
            "Answer grounding: 'platform' (corpus only — default), 'web' "
            "(external web search), or 'both'. web/both use deep-search."
        ),
    )


class MapQueryResponse(BaseModel):
    """Response with map-ready data from a query."""
    query: Optional[str] = None
    country_highlights: List[CountryStats] = []
    matching_articles: int = 0
    answer: Optional[str] = None
    # Agentic next-step suggestions (audit 2026-06-10) — the frontend renders
    # data.actions for every chat mode, so the map assistant can now act, not
    # just answer.
    actions: List[Dict[str, Any]] = []
    highlighted_countries: List[str] = []
    filters_applied: Dict[str, Any] = {}
    session_id: Optional[str] = None
    queried_at: str


# ---------------------------------------------------------------------------
# New response models for extended endpoints
# ---------------------------------------------------------------------------

class ArticleBrief(BaseModel):
    """Brief article representation for country detail."""
    article_id: str
    title: str
    source_name: Optional[str] = None
    published_date: Optional[str] = None
    credibility: Optional[str] = None
    excerpt: Optional[str] = None


class WeatherInfo(BaseModel):
    """Current weather snapshot."""
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    temperature_anomaly_c: Optional[float] = None


class CountryDetail(BaseModel):
    """Rich detail for a single country."""
    country_code: str
    country_name: str
    continent: Optional[str] = None
    region: Optional[str] = None
    flag_emoji: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    weather: Optional[WeatherInfo] = None
    article_count: int = 0
    articles_by_category: Dict[str, int] = {}
    avg_credibility: Optional[float] = None
    recent_articles: List[ArticleBrief] = []
    source_coverage: List[Dict[str, Any]] = []
    high_severity_claims: int = 0
    disputed_claims_ratio: Optional[float] = None
    # seq-11 (2026-06-02): the panel's risk card read this but /detail never
    # returned it (only /compare did), so every country showed 0/10. Now
    # computed with the same _compute_climate_risk_score as compare + the layer.
    climate_risk_score: Optional[float] = None


class TrendPoint(BaseModel):
    """Single data point in a time series."""
    date: str
    article_count: int = 0
    avg_credibility: Optional[float] = None


class ClimateDataPoint(BaseModel):
    """Temperature / precipitation comparison point."""
    period: str
    temperature_avg_c: Optional[float] = None
    precipitation_avg_mm: Optional[float] = None


class CountryClimateData(BaseModel):
    """Climate comparison data for a country."""
    country_code: str
    current_month: Optional[ClimateDataPoint] = None
    last_year_same_month: Optional[ClimateDataPoint] = None
    five_years_ago_same_month: Optional[ClimateDataPoint] = None
    temperature_trend: Optional[str] = None  # rising / falling / stable
    precipitation_comparison: Optional[str] = None


class CountryComparison(BaseModel):
    """Comparison metrics for one country — includes green transition dimensions."""
    country_code: str
    country_name: str
    article_count: int = 0
    source_count: int = 0
    avg_credibility: Optional[float] = None
    top_topics: List[str] = []
    topic_count: Optional[int] = None
    climate_risk_score: Optional[float] = None
    climate_risk: Optional[float] = None  # frontend-compatible alias
    category_breakdown: Optional[Dict[str, int]] = None
    # Green-transition dimensions (0–10 score derived from article coverage)
    green_transition_score: Optional[float] = None
    renewable_energy_score: Optional[float] = None
    cleantech_score: Optional[float] = None
    circular_economy_score: Optional[float] = None
    resource_efficiency_score: Optional[float] = None
    regenerative_score: Optional[float] = None
    sustainability_score: Optional[float] = None
    # Recent articles for the side-by-side compare view. Keys match the
    # frontend MapCompareView shape (overall_credibility, not `credibility`).
    recent_articles: List[Dict[str, Any]] = []


class CompareResponse(BaseModel):
    """Response for /compare endpoint."""
    countries: List[CountryComparison] = []
    comparison_summary: Optional[str] = None
    # Convenience keys for frontend two-country compare view
    country_a: Optional[CountryComparison] = None
    country_b: Optional[CountryComparison] = None


class TimelineEntry(BaseModel):
    """One time bucket in the timeline."""
    date: str
    data: Dict[str, int] = {}


class TemperatureAnomalyItem(BaseModel):
    """Per-country temperature anomaly for map layer."""
    country_code: str
    anomaly_celsius: Optional[float] = None
    trend: Optional[str] = None
    current_temp: Optional[float] = None
    historical_avg: Optional[float] = None
    current_precipitation_mm: Optional[float] = None
    historical_precipitation_avg_mm: Optional[float] = None


class ClimateRiskItem(BaseModel):
    """Per-country climate risk from article claims."""
    country_code: str
    risk_score: float = 0.0
    claim_count: int = 0
    disputed_ratio: float = 0.0
    top_risks: List[str] = []


class CountryCompanyItem(BaseModel):
    """Company summary scoped to a country."""
    company_id: str
    name: str
    ticker: Optional[str] = None
    country_code: Optional[str] = None
    sector_nace: Optional[str] = None
    disclosure_count: int = 0
    latest_disclosure_year: Optional[int] = None
    sbti_validated: bool = False
    net_zero_target_year: Optional[int] = None


class CorporateDensityItem(BaseModel):
    """Per-country corporate climate-data density for map layer rendering."""
    country_code: str
    company_count: int = 0
    sbti_validated_count: int = 0
    net_zero_target_count: int = 0


class NewsEventItem(BaseModel):
    """Per-country recent news/event intensity for map overlay."""
    country_code: str
    event_count: int = 0
    disputed_count: int = 0
    controversy_score: float = 0.0
    latest_event_at: Optional[str] = None


# Region → country code mapping for region-based queries (comprehensive — 80%+ of world)
REGION_COUNTRIES = {
    "europe": [
        "FI", "SE", "NO", "DK", "IS", "GB", "IE", "FR", "DE", "NL", "BE", "LU",
        "CH", "AT", "LI", "ES", "PT", "IT", "MT", "GR", "CY", "TR", "PL", "CZ",
        "SK", "HU", "SI", "RO", "BG", "HR", "RS", "BA", "ME", "MK", "AL", "XK",
        "EE", "LV", "LT", "UA", "MD", "BY", "GE", "AM", "AZ", "RU", "MC", "AD",
        "SM", "VA",
    ],
    "north_america": ["US", "CA", "MX", "GL"],
    "central_america": [
        "GT", "HN", "SV", "NI", "CR", "PA", "BZ",
        "CU", "DO", "HT", "JM", "TT", "BS", "BB",
        "AG", "GD", "DM", "KN", "LC", "VC",
    ],
    "latin_america": [
        "BR", "AR", "CO", "CL", "PE", "EC", "VE", "UY", "PY", "BO",
        "CR", "PA", "GT", "HN", "SV", "NI", "CU", "DO", "HT", "JM",
        "TT", "GY", "SR", "BS", "BB", "BZ",
    ],
    "africa": [
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD",
        "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET",
        "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG",
        "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW",
        "SN", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG",
        "ZM", "ZW", "ST", "SC", "EH",
    ],
    "asia": [
        "AF", "BD", "BT", "BN", "KH", "CN", "HK", "IN", "ID", "IR", "IQ",
        "IL", "JP", "JO", "KZ", "KW", "KG", "LA", "LB", "MY", "MV",
        "MN", "MM", "NP", "PK", "PH", "QA", "SA", "SG", "KR", "LK",
        "SY", "TW", "TJ", "TH", "TL", "TM", "AE", "UZ", "VN", "YE",
        "OM", "BH", "PS", "GE", "AM", "AZ",
    ],
    "middle_east": [
        "AE", "SA", "IL", "JO", "LB", "IQ", "IR", "QA", "KW", "OM",
        "BH", "YE", "SY", "PS",
    ],
    "oceania": [
        "AU", "NZ", "PG", "FJ", "WS", "SB", "TO", "VU",
        "KI", "MH", "FM", "NR", "PW", "TV",
    ],
    "central_asia": ["KZ", "UZ", "TM", "KG", "TJ"],
}


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


def _reliability_risk_component(avg_reliability: Optional[float]) -> float:
    """Convert average reliability into a small additive risk component."""
    if avg_reliability is None:
        return 1.2

    rel = max(0.0, min(100.0, float(avg_reliability)))
    return max(0.0, min(3.0, (70.0 - rel) / 10.0))


def _compute_climate_risk_score(
    article_count: int,
    claim_count: int,
    risky_claim_count: int,
    avg_reliability: Optional[float],
) -> float:
    """Compute a dense 0-10 climate risk score for map coloring."""
    art = max(int(article_count or 0), 0)
    claims = max(int(claim_count or 0), 0)
    risky = max(int(risky_claim_count or 0), 0)

    volume_component = min(4.0, math.log1p(art) * 1.15)
    claim_component = min(2.5, math.log1p(claims) * 0.9)
    risky_ratio_component = min(2.5, (risky / claims) * 5.0) if claims > 0 else 0.0
    reliability_component = _reliability_risk_component(avg_reliability)

    return round(
        min(10.0, volume_component + claim_component + risky_ratio_component + reliability_component),
        1,
    )


@router.get("/country-stats", response_model=List[CountryStats])
async def get_country_stats(
    category: Optional[str] = Query(default=None, description="Filter by content category"),
    categories: Optional[str] = Query(default=None, description="Comma-separated content categories"),
    source: Optional[str] = Query(default=None, description="Filter by source name"),
    reliability_min: Optional[int] = Query(default=None, ge=0, le=100, description="Min reliability score"),
    credibility: Optional[str] = Query(default=None, description="Credibility tier: HIGH, MEDIUM, LOW, All"),
    region: Optional[str] = Query(default=None, description="Filter by region: europe, africa, asia, etc."),
    date_from: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="End date YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="Filter by month YYYY-MM"),
    keyword: Optional[str] = Query(default=None, description="Full-text keyword search"),
):
    """
    Get per-country article counts, top topics, sources, and credibility.

    Supports filtering by: content category, source name, minimum reliability,
    credibility tier, date range, month, keyword, and geographic region.
    """
    db = get_postgres()

    try:
        conditions = ["a.country_code IS NOT NULL", "a.country_code != ''", "a.is_synthetic = FALSE", "a.is_off_topic = FALSE"]
        params: Dict[str, Any] = {}

        if category:
            conditions.append("a.content_category = :category")
            params["category"] = category.lower()
        if categories:
            cat_list = [c.strip().lower() for c in categories.split(",") if c.strip()]
            if cat_list:
                conditions.append("a.content_category = ANY(:cat_list)")
                params["cat_list"] = cat_list
        if source:
            conditions.append("LOWER(a.source_name) = LOWER(:source)")
            params["source"] = source
        if reliability_min is not None:
            conditions.append("COALESCE(a.reliability_score, 0) >= :rel_min")
            params["rel_min"] = reliability_min
        if credibility and credibility.upper() != "ALL":
            conditions.append("a.overall_credibility = :cred")
            params["cred"] = credibility.upper()
        if region and region in REGION_COUNTRIES:
            conditions.append("a.country_code = ANY(:region_codes)")
            params["region_codes"] = REGION_COUNTRIES[region]
        if date_from:
            conditions.append("a.published_date >= :date_from::date")
            params["date_from"] = date_from
        if date_to:
            conditions.append("a.published_date <= :date_to::date")
            params["date_to"] = date_to
        if month:
            conditions.append("to_char(a.published_date, 'YYYY-MM') = :month")
            params["month"] = month
        if keyword:
            # D3 (migration 018): query the language-aware generated tsvector
            # column. Using 'simple' for the query gives cross-language token
            # match so Finnish/German/French/Spanish articles are findable
            # alongside English ones — pre-fix they were invisible to keyword
            # search because the tsvector side was hardcoded to 'english'.
            conditions.append(
                "a.search_tsv @@ websearch_to_tsquery('simple', :keyword)"
            )
            params["keyword"] = keyword

        where = " AND ".join(conditions)

        rows = db.execute_query(f"""
            SELECT
                a.country_code,
                COUNT(*) as article_count,
                COUNT(DISTINCT a.source_name) as source_count,
                MAX(a.created_at) as last_updated,
                AVG(a.reliability_score) as avg_reliability
            FROM articles a
            WHERE {where}
            GROUP BY a.country_code
            ORDER BY article_count DESC
        """, params)

        country_names = _get_country_names(db)

        # Batch-fetch climate risk data for all countries (dense scoring, includes
        # countries with zero extracted claims via article/reliability fallback).
        risk_map: Dict[str, float] = {}
        try:
            risk_rows = db.execute_query("""
                SELECT a.country_code,
                       COUNT(DISTINCT a.article_id) as article_count,
                       AVG(a.reliability_score) as avg_reliability,
                       COUNT(c.claim_id) as claim_cnt,
                       COUNT(CASE WHEN fc.verification_status
                              IN ('FALSE','MISLEADING','LACKS_CONTEXT','DISPUTED','UNVERIFIED')
                              THEN 1 END) as risky_cnt
                FROM articles a
                LEFT JOIN claims c ON c.article_id = a.article_id
                LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
                WHERE a.country_code IS NOT NULL AND a.is_synthetic = FALSE AND a.is_off_topic = FALSE
                GROUP BY a.country_code
            """)
            for rr in (risk_rows or []):
                cc_r = rr["country_code"]
                risk_map[cc_r] = _compute_climate_risk_score(
                    article_count=int(rr.get("article_count") or 0),
                    claim_count=int(rr.get("claim_cnt") or 0),
                    risky_claim_count=int(rr.get("risky_cnt") or 0),
                    avg_reliability=rr.get("avg_reliability"),
                )
        except Exception:
            pass

        stats = []
        for row in (rows or []):
            cc = row["country_code"]

            # Top topics
            topic_rows = db.execute_query("""
                SELECT UNNEST(tags) as tag, COUNT(*) as cnt
                FROM articles
                WHERE country_code = :cc AND tags IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY tag ORDER BY cnt DESC LIMIT 3
            """, {"cc": cc})
            top_topics = [r["tag"] for r in (topic_rows or [])]

            # Top sources for this country
            source_rows = db.execute_query("""
                SELECT source_name, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND source_name IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY source_name ORDER BY cnt DESC LIMIT 3
            """, {"cc": cc})
            top_sources = [r["source_name"] for r in (source_rows or [])]

            article_count = int(row.get("article_count") or 0)
            source_count = int(row.get("source_count") or 0)
            if source_count == 0 and article_count > 0:
                source_count = 1

            avg_reliability = row.get("avg_reliability")
            fallback_risk = _compute_climate_risk_score(
                article_count=article_count,
                claim_count=0,
                risky_claim_count=0,
                avg_reliability=avg_reliability,
            )

            stats.append(CountryStats(
                country_code=cc,
                country_name=country_names.get(cc, cc),
                article_count=article_count,
                source_count=source_count,
                top_topics=top_topics,
                top_sources=top_sources,
                last_updated=str(row["last_updated"]) if row.get("last_updated") else None,
                avg_credibility_score=round(float(avg_reliability), 1) if avg_reliability is not None else None,
                region=_country_region(cc),
                climate_risk_score=risk_map.get(cc, fallback_risk),
            ))

        return stats

    except Exception as e:
        logger.error(f"Country stats query failed: {e}")
        return []


@router.get("/discussed-country-stats", response_model=List[CountryStats])
async def get_discussed_country_stats(
    category: Optional[str] = Query(default=None, description="Filter by content category"),
    source: Optional[str] = Query(default=None, description="Filter by source name"),
    reliability_min: Optional[int] = Query(default=None, ge=0, le=100, description="Min reliability score"),
    region: Optional[str] = Query(default=None, description="Filter by region"),
):
    """
    Get per-country article counts based on countries DISCUSSED in article claims,
    rather than publisher origin. Groups by claim location_country.

    Supports filtering by: content category, source name, minimum reliability, region.
    """
    db = get_postgres()

    try:
        conditions = [
            "COALESCE(c.location_country, a.country_code) IS NOT NULL",
            "COALESCE(c.location_country, a.country_code) != ''",
            "a.is_synthetic = FALSE",
            "a.is_off_topic = FALSE",
        ]
        params: Dict[str, Any] = {}

        if category:
            conditions.append("a.content_category = :category")
            params["category"] = category.lower()
        if source:
            conditions.append("LOWER(a.source_name) = LOWER(:source)")
            params["source"] = source
        if reliability_min is not None:
            conditions.append("COALESCE(a.reliability_score, 0) >= :rel_min")
            params["rel_min"] = reliability_min
        if region and region in REGION_COUNTRIES:
            conditions.append("COALESCE(c.location_country, a.country_code) = ANY(:region_codes)")
            params["region_codes"] = REGION_COUNTRIES[region]

        where = " AND ".join(conditions)

        rows = db.execute_query(f"""
            SELECT
                COALESCE(c.location_country, a.country_code) as country_code,
                COUNT(DISTINCT a.article_id) as article_count,
                MAX(a.created_at) as last_updated,
                AVG(a.reliability_score) as avg_reliability
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            WHERE {where}
            GROUP BY COALESCE(c.location_country, a.country_code)
            ORDER BY article_count DESC
        """, params)

        country_names = _get_country_names(db)

        stats = []
        for row in (rows or []):
            cc = row["country_code"]

            # Top topics for discussed countries
            topic_rows = db.execute_query("""
                SELECT UNNEST(a.tags) as tag, COUNT(*) as cnt
                FROM articles a
                LEFT JOIN claims c ON c.article_id = a.article_id
                WHERE COALESCE(c.location_country, a.country_code) = :cc
                  AND a.tags IS NOT NULL
                  AND a.is_synthetic = FALSE
                  AND a.is_off_topic = FALSE
                GROUP BY tag ORDER BY cnt DESC LIMIT 3
            """, {"cc": cc})
            top_topics = [r["tag"] for r in (topic_rows or [])]

            # Top sources for discussed country
            source_rows = db.execute_query("""
                SELECT a.source_name, COUNT(DISTINCT a.article_id) as cnt
                FROM articles a
                LEFT JOIN claims c ON c.article_id = a.article_id
                WHERE COALESCE(c.location_country, a.country_code) = :cc
                  AND a.source_name IS NOT NULL
                  AND a.is_synthetic = FALSE
                  AND a.is_off_topic = FALSE
                GROUP BY a.source_name ORDER BY cnt DESC LIMIT 3
            """, {"cc": cc})
            top_sources = [r["source_name"] for r in (source_rows or [])]

            stats.append(CountryStats(
                country_code=cc,
                country_name=country_names.get(cc, cc),
                article_count=row.get("article_count", 0),
                top_topics=top_topics,
                top_sources=top_sources,
                last_updated=str(row["last_updated"]) if row.get("last_updated") else None,
                avg_credibility_score=round(float(row["avg_reliability"]), 1) if row.get("avg_reliability") else None,
                region=_country_region(cc),
            ))

        return stats

    except Exception as e:
        logger.error(f"Discussed country stats query failed: {e}")
        return []


@router.get("/topic-density", response_model=List[TopicDensityItem])
async def get_topic_density(
    topic: str = Query(..., min_length=1, description="Topic/tag to compute density for"),
):
    """
    Get per-country article density for a specific topic.
    Returns heatmap-ready data for the map overlay.
    """
    db = get_postgres()

    try:
        rows = db.execute_query("""
            SELECT
                a.country_code,
                COUNT(*) as article_count
            FROM articles a
            WHERE :topic = ANY(a.tags)
              AND a.country_code IS NOT NULL
              AND a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
            GROUP BY a.country_code
            ORDER BY article_count DESC
        """, {"topic": topic.lower()})

        if not rows:
            return []

        # Compute density as fraction of max for gradient
        max_count = max(r["article_count"] for r in rows) if rows else 1

        return [
            TopicDensityItem(
                country_code=r["country_code"],
                topic=topic,
                article_count=r["article_count"],
                density=round(r["article_count"] / max_count, 3),
            )
            for r in rows
        ]

    except Exception as e:
        logger.error(f"Topic density query failed: {e}")
        return []


@router.get("/source-coverage", response_model=List[SourceCoverageItem])
async def get_source_coverage(
    country: Optional[str] = Query(default=None, description="Filter by country code"),
    source: Optional[str] = Query(default=None, description="Filter by source name"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Get source-to-country coverage matrix.

    Shows which sources publish articles about which countries,
    enabling "filter by source" on the map.
    """
    db = get_postgres()

    try:
        conditions = ["a.country_code IS NOT NULL", "a.source_name IS NOT NULL", "a.is_synthetic = FALSE", "a.is_off_topic = FALSE"]
        params: Dict[str, Any] = {"limit": limit}

        if country:
            conditions.append("a.country_code = :cc")
            params["cc"] = country.upper()
        if source:
            conditions.append("LOWER(a.source_name) = LOWER(:source)")
            params["source"] = source

        where = " AND ".join(conditions)

        rows = db.execute_query(f"""
            SELECT a.source_name, a.country_code, COUNT(*) as article_count,
                   AVG(a.reliability_score) as avg_reliability
            FROM articles a
            WHERE {where}
            GROUP BY a.source_name, a.country_code
            ORDER BY article_count DESC
            LIMIT :limit
        """, params)

        return [
            SourceCoverageItem(
                source_name=r["source_name"],
                country_code=r["country_code"],
                article_count=r.get("article_count", 0),
                avg_credibility=round(float(r["avg_reliability"]), 1) if r.get("avg_reliability") else None,
            )
            for r in (rows or [])
        ]

    except Exception as e:
        logger.error(f"Source coverage query failed: {e}")
        return []


@router.post("/query", response_model=MapQueryResponse)
async def query_map(
    request: MapQueryRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Agentic map query endpoint — accepts natural language or structured filters
    and returns map-ready country highlights with article counts.
    Supports both JWT and API key authentication.

    Enhanced with LLM-powered query parsing, highlighted countries, and
    contextual summaries with article citations.

    This endpoint powers chat-driven map interactions:
    - "Show me climate news about drought in East Africa"
    - "Highlight countries with high-credibility renewable energy coverage"
    - "Which sources cover Southeast Asian climate?"

    Supports `session_id` for follow-up queries that maintain conversation context.
    """
    db = get_postgres()

    # --- Source mode: external web / both --------------------------------------
    # When the user picks "Web" or "Both", route the question through
    # DeepSearchService (corpus + Perplexity synthesis) so the map chat can
    # answer even when no platform article matches — instead of the
    # "no articles to reference" dead end. Best-effort: on any failure we fall
    # through to the platform-only path below.
    source_mode = (getattr(request, "source_mode", None) or "platform").lower()
    if request.query and source_mode in ("web", "both"):
        try:
            from app.domains.intelligence.deep_search_service import DeepSearchService
            _ctx = request.view_context or {}
            _country = None
            if request.countries:
                _country = request.countries[0]
            elif isinstance(_ctx, dict) and isinstance(_ctx.get("country"), str):
                _country = _ctx["country"]
            ds = DeepSearchService(db)
            ds_result = await ds.search(
                query=request.query,
                country=_country,
                category=None,
                include_weather=False,
                limit=request.limit,
                include_hallucination_check=False,
                include_refinements=False,
                platform_only=False,
            )
            ds_answer = (ds_result or {}).get("answer") or ""
            if ds_answer:
                web_urls = [
                    c.get("source_url")
                    for c in (ds_result.get("citations") or [])
                    if c.get("type") == "external_web" and c.get("source_url")
                ]
                if web_urls:
                    seen: set = set()
                    uniq = [u for u in web_urls if not (u in seen or seen.add(u))][:6]
                    ds_answer = ds_answer.rstrip() + "\n\n**Web sources:**\n" + "\n".join(f"- {u}" for u in uniq)
                return MapQueryResponse(
                    query=request.query,
                    country_highlights=[],
                    matching_articles=int((ds_result or {}).get("internal_articles_count") or 0),
                    answer=ds_answer,
                    highlighted_countries=[_country.upper()] if _country else [],
                    filters_applied={"source_mode": source_mode},
                    session_id=request.session_id,
                    queried_at=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            logger.warning(f"map web-mode deep search failed; falling back to platform: {exc}")

    # --- LLM-based query parsing for natural language queries -----------------
    parsed_filters: Dict[str, Any] = {}
    if request.query:
        parsed_filters = await _llm_parse_query(request.query, request.session_id)

    # Promote view_context country into the request when nothing else specified
    # one — lets "this country" / "what about it?" follow-ups retain focus.
    view_ctx = request.view_context or {}
    if isinstance(view_ctx, dict):
        ctx_country = view_ctx.get("country")
        if (
            isinstance(ctx_country, str)
            and len(ctx_country) in (2, 3)
            and not request.countries
            and not parsed_filters.get("countries")
        ):
            parsed_filters.setdefault("countries", []).append(ctx_country.upper())
        ctx_compare = view_ctx.get("compare_countries")
        if (
            isinstance(ctx_compare, list)
            and not request.countries
            and not parsed_filters.get("countries")
        ):
            parsed_filters["countries"] = [
                c.upper() for c in ctx_compare if isinstance(c, str) and len(c) in (2, 3)
            ][:4]

    # Merge LLM-parsed filters with explicit request filters (explicit wins)
    effective_countries = request.countries or parsed_filters.get("countries", [])
    effective_region = request.region or parsed_filters.get("region")
    effective_sources = request.sources or parsed_filters.get("sources", [])
    effective_categories = request.categories or parsed_filters.get("categories", [])
    effective_topic = request.topic or parsed_filters.get("topic")
    effective_date_from = parsed_filters.get("date_from")
    effective_date_to = parsed_filters.get("date_to")

    conditions = ["a.country_code IS NOT NULL", "a.is_synthetic = FALSE", "a.is_off_topic = FALSE"]
    params: Dict[str, Any] = {"limit": request.limit}

    # Apply structured filters
    if effective_countries:
        conditions.append("a.country_code = ANY(:countries)")
        params["countries"] = [c.upper() for c in effective_countries]
    if effective_region and effective_region in REGION_COUNTRIES:
        conditions.append("a.country_code = ANY(:region_codes)")
        params["region_codes"] = REGION_COUNTRIES[effective_region]
    if effective_sources:
        conditions.append("a.source_name = ANY(:sources)")
        params["sources"] = effective_sources
    if request.reliability_min is not None:
        conditions.append("COALESCE(a.reliability_score, 0) >= :rel_min")
        params["rel_min"] = request.reliability_min
    if effective_categories:
        conditions.append("a.content_category = ANY(:cats)")
        params["cats"] = [c.lower() for c in effective_categories]
    if effective_topic:
        # LLM may emit topics as "renewable energy" (with space), but seed
        # tags use the hyphenated form "renewable-energy" and content_category
        # uses underscores ("renewable_energy"). Generate every separator
        # variant so natural-language queries actually return results.
        topic_lower = effective_topic.lower().strip()
        topic_variants = list({
            topic_lower,
            topic_lower.replace(" ", "-"),
            topic_lower.replace(" ", "_"),
            topic_lower.replace("_", "-"),
            topic_lower.replace("-", "_"),
            topic_lower.replace("_", " "),
            topic_lower.replace("-", " "),
        })
        conditions.append(
            "(a.tags && CAST(:topic_variants AS text[]) "
            "OR a.content_category = ANY(:topic_variants))"
        )
        params["topic_variants"] = topic_variants
    if effective_date_from:
        conditions.append("a.created_at >= :date_from")
        params["date_from"] = effective_date_from
    if effective_date_to:
        conditions.append("a.created_at <= :date_to")
        params["date_to"] = effective_date_to

    # If natural language query, add full-text search.
    # D3 (migration 018): query the language-aware generated tsvector column
    # instead of computing to_tsvector('english', …) at query time. websearch
    # handles AND/OR/quoted phrases the way users expect from Google-style
    # search bars. 'simple' on the query side gives cross-language token
    # match; per-locale stemming is a future enhancement when the API gains
    # an explicit `lang` parameter.
    if request.query:
        conditions.append(
            "a.search_tsv @@ websearch_to_tsquery('simple', :q)"
        )
        params["q"] = request.query

    where = " AND ".join(conditions)

    try:
        # Get matching article count
        count_rows = db.execute_query(
            f"SELECT COUNT(*) as total FROM articles a WHERE {where}", params
        )
        total = count_rows[0]["total"] if count_rows else 0

        # Get per-country breakdown
        rows = db.execute_query(f"""
            SELECT a.country_code, COUNT(*) as article_count,
                   AVG(a.reliability_score) as avg_reliability,
                   MAX(a.created_at) as last_updated
            FROM articles a WHERE {where}
            GROUP BY a.country_code
            ORDER BY article_count DESC
            LIMIT :limit
        """, params)

        country_names = _get_country_names(db)

        highlights = [
            CountryStats(
                country_code=r["country_code"],
                country_name=country_names.get(r["country_code"], r["country_code"]),
                article_count=r.get("article_count", 0),
                avg_credibility_score=round(float(r["avg_reliability"]), 1) if r.get("avg_reliability") else None,
                last_updated=str(r["last_updated"]) if r.get("last_updated") else None,
                region=_country_region(r["country_code"]),
            )
            for r in (rows or [])
        ]

        highlighted_codes = [h.country_code for h in highlights[:10]]

        # --- Generate LLM-powered answer with article citations ---------------
        answer = None
        actions: List[Dict[str, Any]] = []
        session_id = request.session_id
        if request.query:
            answer, session_id, actions = await _llm_generate_map_answer(
                db, request.query, highlights, total, where, params, session_id,
            )
        if answer is None and request.query and highlights:
            top_countries = ", ".join(f"{h.country_name} ({h.article_count})" for h in highlights[:5])
            answer = (
                f"Found {total} articles matching your query across {len(highlights)} countries. "
                f"Top coverage: {top_countries}."
            )
        elif answer is None and request.query and not highlights:
            answer = f"No articles found matching: \"{request.query}\". Try broadening your search."

        filters_applied = {k: v for k, v in {
            "query": request.query,
            "countries": effective_countries or None,
            "region": effective_region,
            "sources": effective_sources or None,
            "reliability_min": request.reliability_min,
            "categories": effective_categories or None,
            "topic": effective_topic,
            "llm_parsed": parsed_filters or None,
        }.items() if v}

        return MapQueryResponse(
            query=request.query,
            country_highlights=highlights,
            matching_articles=total,
            answer=answer,
            actions=actions,
            highlighted_countries=highlighted_codes,
            filters_applied=filters_applied,
            session_id=session_id,
            queried_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Map query failed: {e}")
        raise HTTPException(status_code=500, detail="Map query failed")


@router.get("/regions")
async def list_regions():
    """List available geographic regions and their country codes."""
    return {
        region: {
            "countries": codes,
            "count": len(codes),
        }
        for region, codes in REGION_COUNTRIES.items()
    }


@router.get("/available-sources")
async def list_available_sources():
    """
    List all source names present in the articles table, with article counts.

    Used by the frontend to populate source filter dropdowns.
    Accessible via agentic features for programmatic source discovery.
    """
    db = get_postgres()
    try:
        rows = db.execute_query("""
            SELECT source_name, COUNT(*) as article_count,
                   AVG(reliability_score) as avg_reliability
            FROM articles
            WHERE source_name IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
            GROUP BY source_name
            ORDER BY article_count DESC
        """)
        return [
            {
                "source_name": r["source_name"],
                "article_count": r.get("article_count", 0),
                "avg_reliability": round(float(r["avg_reliability"]), 1) if r.get("avg_reliability") else None,
            }
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Available sources query failed: {e}")
        return []


@router.get("/available-themes")
async def list_available_themes():
    """
    List all tags/themes present in articles, ranked by frequency.

    Used by frontend for theme-based global filtering.
    Accessible via agentic features for programmatic topic discovery.
    """
    db = get_postgres()
    try:
        rows = db.execute_query("""
            SELECT UNNEST(tags) as theme, COUNT(*) as article_count
            FROM articles
            WHERE tags IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
            GROUP BY theme
            ORDER BY article_count DESC
            LIMIT 50
        """)
        return [
            {
                "theme": r["theme"],
                "article_count": r.get("article_count", 0),
            }
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Available themes query failed: {e}")
        return []


# ==========================================================================
# NEW ENDPOINTS — country detail, trends, climate-data, compare, timeline,
#                 map layers (temperature-anomaly, climate-risk)
# ==========================================================================


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
            return None, session_id

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


# ---------------------------------------------------------------------------
# 1. GET /country/{cc}/detail
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/detail", response_model=CountryDetail)
async def get_country_detail(cc: str):
    """
    Rich country detail endpoint.

    Returns country metadata, current weather, temperature anomaly,
    article statistics, top 5 recent articles, source coverage,
    and climate risk indicators from article claims.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS, COUNTRY_NAMES

    cc = cc.upper()
    db = get_postgres()

    # --- Country info from DB -------------------------------------------------
    country_row = None
    try:
        rows = db.execute_query(
            """SELECT country_code, country_name, continent, flag_emoji,
                      latitude, longitude
               FROM countries WHERE country_code = :cc""",
            {"cc": cc},
        )
        if rows:
            country_row = rows[0]
    except Exception:
        pass

    country_name = (
        (country_row or {}).get("country_name")
        or COUNTRY_NAMES.get(cc, cc)
    )
    continent = (country_row or {}).get("continent")
    flag = (country_row or {}).get("flag_emoji")
    lat = float((country_row or {}).get("latitude") or 0)
    lon = float((country_row or {}).get("longitude") or 0)

    coords = COUNTRY_COORDS.get(cc)
    if coords:
        lat = lat or coords["lat"]
        lon = lon or coords["lon"]

    # --- Weather (Open-Meteo) -------------------------------------------------
    weather = None
    if lat and lon:
        current_wx = await _fetch_current_weather(lat, lon)
        if current_wx:
            # Historical average for same month to compute anomaly
            today = date.today()
            hist_start = date(today.year - 1, today.month, 1).isoformat()
            hist_end = date(today.year - 1, today.month,
                           min(28, today.day)).isoformat()
            hist = await _fetch_historical_weather(lat, lon, hist_start, hist_end)
            anomaly = None
            if hist and hist.get("temperature_avg") is not None and current_wx.get("temperature_c") is not None:
                anomaly = round(current_wx["temperature_c"] - hist["temperature_avg"], 1)
            weather = WeatherInfo(
                temperature_c=current_wx.get("temperature_c"),
                humidity_pct=current_wx.get("humidity_pct"),
                precipitation_mm=current_wx.get("precipitation_mm"),
                wind_speed_kmh=current_wx.get("wind_speed_kmh"),
                temperature_anomaly_c=anomaly,
            )

    # --- Article statistics ---------------------------------------------------
    try:
        stat_rows = db.execute_query("""
            SELECT COUNT(*) as total,
                   AVG(reliability_score) as avg_cred
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
        """, {"cc": cc})
        total = stat_rows[0]["total"] if stat_rows else 0
        avg_cred = (
            round(float(stat_rows[0]["avg_cred"]), 1)
            if stat_rows and stat_rows[0].get("avg_cred") else None
        )
    except Exception:
        total, avg_cred = 0, None

    # Count by category
    articles_by_cat: Dict[str, int] = {}
    try:
        cat_rows = db.execute_query("""
            SELECT COALESCE(content_category, 'uncategorised') as cat, COUNT(*) as cnt
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            GROUP BY cat ORDER BY cnt DESC
        """, {"cc": cc})
        articles_by_cat = {r["cat"]: r["cnt"] for r in (cat_rows or [])}
    except Exception:
        pass

    # --- Top 5 recent articles ------------------------------------------------
    recent: List[ArticleBrief] = []
    try:
        art_rows = db.execute_query("""
            SELECT article_id, title, source_name, published_date,
                   overall_credibility, excerpt
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            ORDER BY created_at DESC LIMIT 5
        """, {"cc": cc})
        recent = [
            ArticleBrief(
                article_id=str(r["article_id"]),
                title=r.get("title", ""),
                source_name=r.get("source_name"),
                published_date=str(r["published_date"]) if r.get("published_date") else None,
                credibility=r.get("overall_credibility"),
                excerpt=(r.get("excerpt") or "")[:200],
            )
            for r in (art_rows or [])
        ]
    except Exception:
        pass

    # --- Source coverage -------------------------------------------------------
    # End2End audit (2026-05-27 §7.4 + §8.2): top-source breakdown was a single
    # "avg_credibility" number per source. Now JOIN source_credibility_tiers
    # (mig 027 + 041) so the map country panel can render the 3-axis editorial
    # / factcheck / transparency chip per source instead of a single rolled-up
    # number. LEFT JOIN so un-tiered sources still appear (with NULL axes).
    source_coverage: List[Dict[str, Any]] = []
    try:
        src_rows = db.execute_query("""
            SELECT a.source_name,
                   COUNT(*) as cnt,
                   AVG(a.reliability_score) as avg_rel,
                   MAX(sct.tier) as tier,
                   MAX(sct.editorial_score) as editorial_score,
                   MAX(sct.factcheck_score) as factcheck_score,
                   MAX(sct.transparency_score) as transparency_score
            FROM articles a
            LEFT JOIN source_credibility_tiers sct
              ON sct.domain = LOWER(a.source_name)
              OR sct.source_name = a.source_name
            WHERE a.country_code = :cc
              AND a.source_name IS NOT NULL
              AND a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
            GROUP BY a.source_name
            ORDER BY cnt DESC
            LIMIT 10
        """, {"cc": cc})
        source_coverage = [
            {
                "source_name": r["source_name"],
                "article_count": r["cnt"],
                "avg_credibility": round(float(r["avg_rel"]), 1) if r.get("avg_rel") else None,
                "tier": r.get("tier"),
                "editorial_score": int(r["editorial_score"]) if r.get("editorial_score") is not None else None,
                "factcheck_score": int(r["factcheck_score"]) if r.get("factcheck_score") is not None else None,
                "transparency_score": int(r["transparency_score"]) if r.get("transparency_score") is not None else None,
            }
            for r in (src_rows or [])
        ]
    except Exception:
        pass

    # --- Climate risk indicators from claims -----------------------------------
    high_severity = 0
    disputed_ratio: Optional[float] = None
    total_claims = 0
    disputed_count = 0
    try:
        risk_rows = db.execute_query("""
            SELECT
                COUNT(c.claim_id) as total_claims,
                COUNT(CASE WHEN fc.verification_status IN ('FALSE','MISLEADING','LACKS_CONTEXT')
                      THEN 1 END) as disputed,
                COUNT(CASE WHEN c.claim_type IN ('prediction','factual_data')
                      THEN 1 END) as high_severity
            FROM claims c
            JOIN articles a ON a.article_id = c.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code = :cc
        """, {"cc": cc})
        if risk_rows and risk_rows[0]["total_claims"]:
            total_claims = risk_rows[0]["total_claims"]
            high_severity = risk_rows[0].get("high_severity", 0) or 0
            disputed_count = risk_rows[0].get("disputed", 0) or 0
            disputed_ratio = round(disputed_count / total_claims, 3) if total_claims > 0 else 0.0
    except Exception:
        pass

    # seq-11: same risk formula as /compare + the choropleth layer so the panel's
    # risk card matches the map coloring (was always 0/10 — field never returned).
    climate_risk_score = _compute_climate_risk_score(
        article_count=total,
        claim_count=total_claims,
        risky_claim_count=disputed_count,
        avg_reliability=avg_cred,
    )

    return CountryDetail(
        country_code=cc,
        country_name=country_name,
        continent=continent,
        region=_country_region(cc),
        flag_emoji=flag,
        latitude=lat or None,
        longitude=lon or None,
        weather=weather,
        article_count=total,
        articles_by_category=articles_by_cat,
        avg_credibility=avg_cred,
        recent_articles=recent,
        source_coverage=source_coverage,
        high_severity_claims=high_severity,
        disputed_claims_ratio=disputed_ratio,
        climate_risk_score=climate_risk_score,
    )


# ---------------------------------------------------------------------------
# 2. GET /country/{cc}/trends
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/trends", response_model=List[TrendPoint])
async def get_country_trends(
    cc: str,
    period: str = Query("6m", description="Time period: 1m, 3m, 6m, 1y, 2y"),
    granularity: str = Query("month", description="Granularity: week or month"),
):
    """
    Article volume time series for a country.
    Returns array of {date, article_count, avg_credibility} grouped by month or week.
    """
    cc = cc.upper()
    db = get_postgres()

    # Resolve period to an interval string
    period_map = {"1m": "1 month", "3m": "3 months", "6m": "6 months", "1y": "1 year", "2y": "2 years"}
    interval = period_map.get(period, "6 months")

    trunc = "month" if granularity != "week" else "week"

    try:
        rows = db.execute_query(f"""
            SELECT DATE_TRUNC(:trunc, created_at) as bucket,
                   COUNT(*) as article_count,
                   AVG(reliability_score) as avg_cred
            FROM articles
            WHERE country_code = :cc
              AND is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND created_at >= NOW() - INTERVAL '{interval}'
            GROUP BY bucket
            ORDER BY bucket ASC
        """, {"cc": cc, "trunc": trunc})

        return [
            TrendPoint(
                date=str(r["bucket"].date()) if hasattr(r["bucket"], "date") else str(r["bucket"]),
                article_count=r["article_count"],
                avg_credibility=round(float(r["avg_cred"]), 1) if r.get("avg_cred") else None,
            )
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Country trends query failed for {cc}: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. GET /country/{cc}/climate-data
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/climate-data", response_model=CountryClimateData)
async def get_country_climate_data(cc: str):
    """
    Temperature anomaly and precipitation data for a country.

    Compares current month averages against the same month last year
    and five years ago using the Open-Meteo archive API.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS

    cc = cc.upper()
    coords = COUNTRY_COORDS.get(cc)
    if not coords:
        # Return an empty payload rather than 404 so the UI can render
        # an article-only view for countries without coordinate data.
        return CountryClimateData(country_code=cc)

    lat, lon = coords["lat"], coords["lon"]
    today = date.today()
    m, d = today.month, min(today.day, 28)

    async def _period_data(year: int) -> Optional[ClimateDataPoint]:
        start = date(year, m, 1).isoformat()
        end = date(year, m, d).isoformat()
        h = await _fetch_historical_weather(lat, lon, start, end)
        if not h:
            return None
        return ClimateDataPoint(
            period=f"{year}-{m:02d}",
            temperature_avg_c=h.get("temperature_avg"),
            precipitation_avg_mm=h.get("precipitation_avg"),
        )

    current = await _period_data(today.year)
    last_year = await _period_data(today.year - 1)
    five_ago = await _period_data(today.year - 5)

    # Determine trend
    trend = None
    if current and last_year and five_ago:
        temps = [
            p.temperature_avg_c for p in [five_ago, last_year, current]
            if p and p.temperature_avg_c is not None
        ]
        if len(temps) >= 2:
            diff = temps[-1] - temps[0]
            if diff > 0.5:
                trend = "rising"
            elif diff < -0.5:
                trend = "falling"
            else:
                trend = "stable"

    # Precipitation comparison
    precip_cmp = None
    if current and last_year:
        cp = current.precipitation_avg_mm
        lp = last_year.precipitation_avg_mm
        if cp is not None and lp is not None and lp > 0:
            pct = ((cp - lp) / lp) * 100
            if pct > 10:
                precip_cmp = f"{pct:+.0f}% wetter than last year"
            elif pct < -10:
                precip_cmp = f"{pct:+.0f}% drier than last year"
            else:
                precip_cmp = "similar to last year"

    return CountryClimateData(
        country_code=cc,
        current_month=current,
        last_year_same_month=last_year,
        five_years_ago_same_month=five_ago,
        temperature_trend=trend,
        precipitation_comparison=precip_cmp,
    )


# ---------------------------------------------------------------------------
# 4. GET /compare
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=CompareResponse)
async def compare_countries(
    countries: str = Query(..., description="Comma-separated country codes, e.g. FI,SE,NO"),
):
    """
    Compare multiple countries across article coverage, credibility,
    top topics, and climate risk score.
    """
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not codes or len(codes) > 10:
        raise HTTPException(status_code=400, detail="Provide 1-10 comma-separated country codes")

    db = get_postgres()
    country_names = _get_country_names(db)
    results: List[CountryComparison] = []

    for cc in codes:
        try:
            # Basic stats
            stat_rows = db.execute_query("""
                SELECT COUNT(*) as cnt,
                       COUNT(DISTINCT source_name) as src_cnt,
                       AVG(reliability_score) as avg_cred
                FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            """, {"cc": cc})
            s = stat_rows[0] if stat_rows else {}

            # Top topics
            topic_rows = db.execute_query("""
                SELECT UNNEST(tags) as tag, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND tags IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY tag ORDER BY cnt DESC LIMIT 5
            """, {"cc": cc})
            top_topics = [r["tag"] for r in (topic_rows or [])]

            # Category breakdown (sustainability dimensions)
            cat_rows = db.execute_query("""
                SELECT content_category, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND content_category IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY content_category ORDER BY cnt DESC
            """, {"cc": cc})
            category_breakdown = {r["content_category"]: r["cnt"] for r in (cat_rows or [])}

            # Climate risk score (normalised 0-10)
            risk_rows = db.execute_query("""
                SELECT COUNT(c.claim_id) as total_claims,
                       COUNT(CASE WHEN fc.verification_status
                             IN ('FALSE','MISLEADING','LACKS_CONTEXT') THEN 1 END) as disputed
                FROM claims c
                JOIN articles a ON a.article_id = c.article_id
                LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
                WHERE a.country_code = :cc
            """, {"cc": cc})
            risk_score = 0.0
            if risk_rows and risk_rows[0]["total_claims"]:
                tc = risk_rows[0]["total_claims"]
                disp = risk_rows[0].get("disputed", 0) or 0
                # Score: base from claim volume + penalty for disputed ratio
                risk_score = round(min(10.0, (tc / 5.0) + (disp / max(tc, 1)) * 5), 1)

            # Green transition dimension scores (0-10 scale, 2 articles/point)
            def _cat_score(cat: str) -> float:
                return round(min(10.0, category_breakdown.get(cat, 0) / 2.0), 1)

            # Recent articles (5) for the side-by-side compare view. Frontend
            # MapCompareView reads article_id/title/source_name/overall_credibility.
            recent_articles: List[Dict[str, Any]] = []
            try:
                ra_rows = db.execute_query("""
                    SELECT article_id, title, source_name, published_date, overall_credibility
                    FROM articles
                    WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
                    ORDER BY created_at DESC LIMIT 5
                """, {"cc": cc})
                recent_articles = [
                    {
                        "article_id": str(r["article_id"]),
                        "title": r.get("title", ""),
                        "source_name": r.get("source_name"),
                        "published_date": str(r["published_date"]) if r.get("published_date") else None,
                        "overall_credibility": r.get("overall_credibility") or "UNKNOWN",
                    }
                    for r in (ra_rows or [])
                ]
            except Exception:
                pass

            results.append(CountryComparison(
                country_code=cc,
                country_name=country_names.get(cc, cc),
                article_count=s.get("cnt", 0),
                source_count=s.get("src_cnt", 0),
                avg_credibility=round(float(s["avg_cred"]), 1) if s.get("avg_cred") else None,
                top_topics=top_topics,
                topic_count=len(top_topics),
                climate_risk_score=risk_score,
                climate_risk=risk_score,
                category_breakdown=category_breakdown if category_breakdown else None,
                green_transition_score=_cat_score("green_transition"),
                renewable_energy_score=_cat_score("renewable_energy"),
                cleantech_score=_cat_score("cleantech"),
                circular_economy_score=_cat_score("circular_economy"),
                resource_efficiency_score=_cat_score("resource_efficiency"),
                regenerative_score=_cat_score("regenerative_economy"),
                sustainability_score=_cat_score("sustainability"),
                recent_articles=recent_articles,
            ))
        except Exception as e:
            logger.warning(f"Compare failed for {cc}: {e}")
            results.append(CountryComparison(
                country_code=cc,
                country_name=country_names.get(cc, cc),
            ))

    # Build comparison summary
    summary = None
    if len(results) >= 2:
        ranked = sorted(results, key=lambda r: r.article_count, reverse=True)
        parts = [f"{r.country_name}: {r.article_count} articles" for r in ranked]
        top = ranked[0]
        summary = (
            f"Coverage comparison: {'; '.join(parts)}. "
            f"{top.country_name} has the most coverage"
        )
        if top.avg_credibility:
            summary += f" with avg credibility {top.avg_credibility}"
        summary += "."
        highest_risk = max(results, key=lambda r: r.climate_risk_score or 0)
        if highest_risk.climate_risk_score and highest_risk.climate_risk_score > 0:
            summary += (
                f" {highest_risk.country_name} has the highest climate risk score "
                f"({highest_risk.climate_risk_score}/10)."
            )

    return CompareResponse(
        countries=results,
        comparison_summary=summary,
        country_a=results[0] if results else None,
        country_b=results[1] if len(results) > 1 else None,
    )


# ---------------------------------------------------------------------------
# 5. GET /timeline
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=List[TimelineEntry])
async def get_timeline(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    granularity: str = Query("month", description="Granularity: day, week, or month"),
):
    """
    Time series of article distribution across countries.
    Returns array of {date, data: {country_code: article_count}}.
    """
    db = get_postgres()

    trunc = granularity if granularity in ("day", "week", "month") else "month"

    try:
        rows = db.execute_query(f"""
            SELECT DATE_TRUNC(:trunc, created_at) as bucket,
                   country_code,
                   COUNT(*) as cnt
            FROM articles
            WHERE country_code IS NOT NULL
              AND is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND created_at >= :start_d
              AND created_at <= :end_d
            GROUP BY bucket, country_code
            ORDER BY bucket ASC
        """, {"trunc": trunc, "start_d": start_date, "end_d": end_date})

        # Pivot into {date -> {cc: count}}
        buckets: Dict[str, Dict[str, int]] = {}
        for r in (rows or []):
            d = str(r["bucket"].date()) if hasattr(r["bucket"], "date") else str(r["bucket"])
            buckets.setdefault(d, {})[r["country_code"]] = r["cnt"]

        return [
            TimelineEntry(date=d, data=cc_map)
            for d, cc_map in sorted(buckets.items())
        ]
    except Exception as e:
        logger.error(f"Timeline query failed: {e}")
        return []


# ---------------------------------------------------------------------------
# 6. GET /layers/temperature-anomaly
# ---------------------------------------------------------------------------

@router.get("/layers/temperature-anomaly", response_model=List[TemperatureAnomalyItem])
async def get_temperature_anomaly_layer():
    """
    Per-country temperature anomaly data for map layer rendering.

    For each country with articles in the DB, fetches current temperature
    and compares to the same month last year. Results cached for 6 hours.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS

    cache_key = "layer:temp_anomaly"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()

    # Countries that have articles
    try:
        cc_rows = db.execute_query("""
            SELECT DISTINCT country_code FROM articles
            WHERE country_code IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
        """)
        active_codes = [r["country_code"] for r in (cc_rows or [])]
    except Exception:
        active_codes = []

    results: List[TemperatureAnomalyItem] = []
    today = date.today()
    hist_start = date(today.year - 1, today.month, 1).isoformat()
    hist_end = date(today.year - 1, today.month, min(28, today.day)).isoformat()

    import asyncio

    async def _fetch_anomaly_for(cc: str) -> Optional[TemperatureAnomalyItem]:
        coords = COUNTRY_COORDS.get(cc)
        if not coords:
            logger.debug(f"Skipping temperature anomaly for {cc}: no coordinates registered")
            return None
        lat, lon = coords["lat"], coords["lon"]
        current_wx = await _fetch_current_weather(lat, lon)
        hist = await _fetch_historical_weather(lat, lon, hist_start, hist_end)
        current_temp = current_wx.get("temperature_c") if current_wx else None
        current_precip = current_wx.get("precipitation_mm") if current_wx else None
        hist_avg = hist.get("temperature_avg") if hist else None
        hist_precip = hist.get("precipitation_avg") if hist else None
        anomaly = None
        trend = None
        if current_temp is not None and hist_avg is not None:
            anomaly = round(current_temp - hist_avg, 1)
            trend = "warmer" if anomaly > 1.0 else ("cooler" if anomaly < -1.0 else "normal")
        return TemperatureAnomalyItem(
            country_code=cc, anomaly_celsius=anomaly,
            trend=trend, current_temp=current_temp, historical_avg=hist_avg,
            current_precipitation_mm=current_precip,
            historical_precipitation_avg_mm=hist_precip,
        )

    # Fetch all countries concurrently (batches of 10 to avoid flooding)
    for i in range(0, len(active_codes), 10):
        batch = active_codes[i:i+10]
        batch_results = await asyncio.gather(
            *[_fetch_anomaly_for(cc) for cc in batch],
            return_exceptions=True,
        )
        for item in batch_results:
            if isinstance(item, TemperatureAnomalyItem):
                results.append(item)

    _cache_set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# 7. GET /layers/climate-risk
# ---------------------------------------------------------------------------

@router.get("/layers/climate-risk", response_model=List[ClimateRiskItem])
async def get_climate_risk_layer():
    """
    Per-country climate risk scores computed from article claims.

    For each country: counts high-importance claims, computes disputed/unverified
    ratio, and derives a severity score (0-10).
    """
    cache_key = "layer:climate_risk"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()

    try:
        rows = db.execute_query("""
            SELECT
                a.country_code,
                COUNT(DISTINCT a.article_id) as article_count,
                AVG(a.reliability_score) as avg_reliability,
                COUNT(c.claim_id) as total_claims,
                COUNT(CASE WHEN fc.verification_status
                      IN ('FALSE','MISLEADING','LACKS_CONTEXT','DISPUTED')
                      THEN 1 END) as disputed,
                COUNT(CASE WHEN fc.verification_status = 'UNVERIFIED'
                      THEN 1 END) as unverified
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code IS NOT NULL AND a.is_synthetic = FALSE AND a.is_off_topic = FALSE
            GROUP BY a.country_code
            ORDER BY article_count DESC
        """)
    except Exception as e:
        logger.error(f"Climate risk layer query failed: {e}")
        return []

    results: List[ClimateRiskItem] = []
    for r in (rows or []):
        article_count = int(r.get("article_count") or 0)
        avg_reliability = r.get("avg_reliability")
        tc = r["total_claims"] or 0
        disp = r.get("disputed", 0) or 0
        unver = r.get("unverified", 0) or 0
        ratio = round((disp + unver) / tc, 3) if tc > 0 else 0.0
        score = _compute_climate_risk_score(
            article_count=article_count,
            claim_count=tc,
            risky_claim_count=disp + unver,
            avg_reliability=avg_reliability,
        )

        # Top risk categories
        top_risks: List[str] = []
        if tc > 0:
            try:
                risk_type_rows = db.execute_query("""
                    SELECT c.claim_type, COUNT(*) as cnt
                    FROM claims c
                    JOIN articles a ON a.article_id = c.article_id
                    WHERE a.country_code = :cc AND c.claim_type IS NOT NULL
                    GROUP BY c.claim_type ORDER BY cnt DESC LIMIT 3
                """, {"cc": r["country_code"]})
                top_risks = [rt["claim_type"] for rt in (risk_type_rows or [])]
            except Exception:
                pass

        results.append(ClimateRiskItem(
            country_code=r["country_code"],
            risk_score=score,
            claim_count=tc,
            disputed_ratio=ratio,
            top_risks=top_risks,
        ))

    _cache_set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# 8. GET /country/{cc}/companies
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/companies", response_model=List[CountryCompanyItem])
async def get_country_companies(
    cc: str,
    sbti_only: bool = Query(False, description="Only companies with SBTi-validated disclosures"),
    limit: int = Query(25, ge=1, le=200),
):
    """Return companies associated with a country code.

    This is the map-side reverse lookup for the Corporate Tracker surface,
    powering the country panel's Companies tab.
    """
    db = get_postgres()
    cc = (cc or "").upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    try:
        rows = db.execute_query(
            """
            SELECT c.company_id,
                   c.name,
                   c.ticker,
                   c.country_code,
                   c.sector_nace,
                   COUNT(cd.disclosure_id) AS disclosure_count,
                   MAX(cd.reporting_year) AS latest_disclosure_year,
                   COALESCE(BOOL_OR(cd.sbti_validated), FALSE) AS sbti_validated,
                   MAX(cd.net_zero_target_year) AS net_zero_target_year
            FROM companies c
            LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
            WHERE c.country_code = :cc
            GROUP BY c.company_id, c.name, c.ticker, c.country_code, c.sector_nace
            HAVING (:sbti_only = FALSE OR COALESCE(BOOL_OR(cd.sbti_validated), FALSE) = TRUE)
            ORDER BY COALESCE(BOOL_OR(cd.sbti_validated), FALSE) DESC,
                     COUNT(cd.disclosure_id) DESC,
                     c.name ASC
            LIMIT :limit
            """,
            {"cc": cc, "sbti_only": sbti_only, "limit": limit},
        )
    except Exception as exc:
        logger.error(f"Country companies query failed for {cc}: {exc}")
        return []

    return [
        CountryCompanyItem(
            company_id=str(r["company_id"]),
            name=r.get("name") or "",
            ticker=r.get("ticker"),
            country_code=r.get("country_code"),
            sector_nace=r.get("sector_nace"),
            disclosure_count=int(r.get("disclosure_count") or 0),
            latest_disclosure_year=int(r["latest_disclosure_year"]) if r.get("latest_disclosure_year") is not None else None,
            sbti_validated=bool(r.get("sbti_validated") or False),
            net_zero_target_year=int(r["net_zero_target_year"]) if r.get("net_zero_target_year") is not None else None,
        )
        for r in (rows or [])
    ]


# ---------------------------------------------------------------------------
# 9. GET /layers/corporate-density
# ---------------------------------------------------------------------------

@router.get("/layers/corporate-density", response_model=List[CorporateDensityItem])
async def get_corporate_density_layer():
    """Per-country corporate disclosure density for map choropleth rendering."""
    cache_key = "layer:corporate_density"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT c.country_code,
                   COUNT(DISTINCT c.company_id) AS company_count,
                   COUNT(DISTINCT CASE WHEN cd.sbti_validated THEN c.company_id END) AS sbti_validated_count,
                   COUNT(DISTINCT CASE WHEN cd.net_zero_target_year IS NOT NULL THEN c.company_id END) AS net_zero_target_count
            FROM companies c
            LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
            WHERE c.country_code IS NOT NULL AND c.country_code <> ''
            GROUP BY c.country_code
            ORDER BY company_count DESC
            """
        )
    except Exception as exc:
        logger.error(f"Corporate density layer query failed: {exc}")
        return []

    payload = [
        CorporateDensityItem(
            country_code=r["country_code"],
            company_count=int(r.get("company_count") or 0),
            sbti_validated_count=int(r.get("sbti_validated_count") or 0),
            net_zero_target_count=int(r.get("net_zero_target_count") or 0),
        )
        for r in (rows or [])
    ]
    _cache_set(cache_key, payload)
    return payload


# ---------------------------------------------------------------------------
# 10. GET /layers/news-events
# ---------------------------------------------------------------------------

@router.get("/layers/news-events", response_model=List[NewsEventItem])
async def get_news_events_layer(
    window_days: int = Query(21, ge=1, le=90, description="Lookback window in days"),
):
    """Recent country-level news/event intensity with a controversy signal.

    Uses article volume in a rolling window plus disputed/unverified claim ratio
    to expose where climate news is currently most contentious.
    """
    cache_key = f"layer:news_events:{window_days}"
    cached = _cache_get(cache_key, ttl_seconds=3600)
    if cached is not None:
        return cached

    db = get_postgres()
    interval = f"{int(window_days)} days"
    try:
        rows = db.execute_query(
            """
            SELECT a.country_code,
                   COUNT(DISTINCT a.article_id) AS event_count,
                   COUNT(CASE WHEN fc.verification_status
                         IN ('FALSE','MISLEADING','LACKS_CONTEXT','DISPUTED','UNVERIFIED')
                         THEN 1 END) AS disputed_count,
                   MAX(a.created_at) AS latest_event_at
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code IS NOT NULL
              AND a.country_code <> ''
              AND a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
              AND a.created_at >= NOW() - :interval::interval
            GROUP BY a.country_code
            ORDER BY event_count DESC
            """,
            {"interval": interval},
        )
    except Exception as exc:
        logger.error(f"News-events layer query failed: {exc}")
        return []

    payload: List[NewsEventItem] = []
    for r in (rows or []):
        event_count = int(r.get("event_count") or 0)
        disputed_count = int(r.get("disputed_count") or 0)
        disputed_ratio = (disputed_count / event_count) if event_count > 0 else 0.0
        # Dense but bounded 0-10 score; volume + controversy contribution.
        controversy_score = round(min(10.0, math.log1p(event_count) * 1.8 + disputed_ratio * 4.0), 1)
        payload.append(
            NewsEventItem(
                country_code=r["country_code"],
                event_count=event_count,
                disputed_count=disputed_count,
                controversy_score=controversy_score,
                latest_event_at=str(r["latest_event_at"]) if r.get("latest_event_at") else None,
            )
        )

    _cache_set(cache_key, payload)
    return payload


@router.get("/country/{cc}/claim-ledger")
async def get_country_claim_ledger(
    cc: str,
    since_days: int = Query(365, ge=1, le=730),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_postgres()
    cc = cc.upper()[:2]
    interval = f"{int(since_days)} days"
    try:
        rows = db.execute_query(
            """SELECT c.claim_id, c.claim_text, c.claim_type, c.claim_category,
                      a.title AS article_title, a.source_name, a.published_date,
                      a.overall_credibility, cp.confidence
               FROM claims c
               JOIN articles a ON a.article_id = c.article_id
               LEFT JOIN claim_provenance cp ON cp.claim_id = c.claim_id
               WHERE a.country_code = :cc AND a.is_synthetic = FALSE AND a.is_off_topic = FALSE
                 AND c.created_at > NOW() - :interval::interval
               ORDER BY c.created_at DESC LIMIT :limit""",
            {"cc": cc, "interval": interval, "limit": limit},
        )
    except Exception as exc:
        logger.warning(f"claim_ledger query failed: {exc}")
        rows = []
    claims = []
    for r in rows or []:
        claims.append({
            "claim_id": str(r["claim_id"]),
            "claim_text": r["claim_text"],
            "claim_type": r.get("claim_type"),
            "claim_category": r.get("claim_category"),
            "article_title": r.get("article_title"),
            "source_name": r.get("source_name"),
            "published_date": str(r.get("published_date")) if r.get("published_date") else None,
            "overall_credibility": r.get("overall_credibility"),
            "confidence": r.get("confidence"),
        })
    return {"country_code": cc, "since_days": since_days, "claims": claims, "total": len(claims)}


# ---------------------------------------------------------------------------
# Phase 8 MH4 (2026-05-24) — Country warming projections.
#
# Returns IPCC AR6 SSP-based warming projections at 2030 / 2050 / 2100
# horizons for the three canonical scenarios (SSP1-2.6 / SSP2-4.5 /
# SSP3-7.0). Read-only, cache-friendly. Backing table seeded by
# migration 035.
# ---------------------------------------------------------------------------


@router.get("/country/{cc}/biome")
async def get_country_biome_route(cc: str):
    """Per-country biome + climate-effects narrative + drill-down hooks
    + symbol metadata for map rendering.

    Phase 11 (2026-05-25) — merges the curated narrative (22 countries)
    with the comprehensive biome+Köppen mapping (195 countries) so the
    Country Passport biome panel + the world map biome layer pull from
    the same response.
    """
    from app.domains.content.country_biome import country_biome_payload
    from app.domains.content.country_biome_map import country_biome_map_entry

    cc = (cc or "").upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    narrative = country_biome_payload(cc)
    map_entry = country_biome_map_entry(cc)
    # Merge: keep the narrative shape but add the symbol/koppen metadata.
    return {
        **narrative,
        "biome_symbol": {
            "biome_id": map_entry["biome_id"],
            "biome_label": map_entry["biome_label"],
            "biome_emoji": map_entry["biome_emoji"],
            "koppen_id": map_entry["koppen_id"],
            "koppen_label": map_entry["koppen_label"],
            "koppen_color": map_entry["koppen_color"],
        },
    }


@router.get("/biome-overview")
async def get_biome_overview_route():
    """All-countries biome + Köppen-Geiger climate-zone map (Phase 11).

    Single response feeds the world-map biome layer (chloropleth fill
    by Köppen colour + emoji marker at country centroid). Includes the
    biome + Köppen taxonomies so the frontend renders a legend without
    a second round-trip.
    """
    from app.domains.content.country_biome_map import biome_overview_payload
    return biome_overview_payload()


@router.get("/country/{cc}/projections")
async def get_country_projections(cc: str):
    """Warming projections per scenario + horizon for a single country."""
    cc = cc.upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT scenario, horizon_year, temp_anomaly_c,
                      methodology_version, citation_url
               FROM country_projections
               WHERE country_code = :cc
               ORDER BY scenario, horizon_year""",
            {"cc": cc},
        )
    except Exception as exc:
        logger.warning(f"Country projections query failed for {cc}: {exc}")
        rows = []

    # Group rows by scenario for the frontend.
    scenarios: dict = {}
    citation_url = None
    methodology_version = None
    for r in rows or []:
        sc = r["scenario"]
        scenarios.setdefault(sc, []).append({
            "horizon_year": r["horizon_year"],
            "temp_anomaly_c": float(r["temp_anomaly_c"]),
        })
        citation_url = citation_url or r.get("citation_url")
        methodology_version = methodology_version or r.get("methodology_version")

    return {
        "country_code": cc,
        "scenarios": scenarios,
        "available": bool(scenarios),
        "methodology_version": methodology_version,
        "citation_url": citation_url,
        "baseline_note": "Warming relative to 1850-1900 pre-industrial baseline.",
    }
