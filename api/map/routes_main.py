"""Map routes — country statistics, topic density, source coverage."""
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-api")
router = APIRouter()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Region → country code mapping
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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
