"""
Map Routes — Global geographic article distribution, topic density, and agentic query.

Provides per-country article counts, top topics, source/reliability filtering,
heatmap data, and natural-language query endpoint for chat-driven map updates.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-api")
router = APIRouter(prefix="/api/map", tags=["Map"])


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


class MapQueryResponse(BaseModel):
    """Response with map-ready data from a query."""
    query: Optional[str] = None
    country_highlights: List[CountryStats] = []
    matching_articles: int = 0
    answer: Optional[str] = None
    filters_applied: Dict[str, Any] = {}
    queried_at: str


# Region → country code mapping for region-based queries
REGION_COUNTRIES = {
    "europe": ["FI", "SE", "NO", "DK", "IS", "GB", "IE", "FR", "DE", "NL", "BE", "LU",
               "CH", "AT", "LI", "ES", "PT", "IT", "MT", "GR", "CY", "TR", "PL", "CZ",
               "SK", "HU", "SI", "RO", "BG", "HR", "RS", "BA", "ME", "MK", "AL", "XK",
               "EE", "LV", "LT", "UA", "MD", "BY", "GE", "AM", "AZ"],
    "north_america": ["US", "CA", "MX"],
    "latin_america": ["BR", "AR", "CO", "CL", "PE", "EC", "VE", "UY", "PY", "BO", "CR", "PA"],
    "africa": ["KE", "NG", "ZA", "GH", "TZ", "UG", "RW", "ET", "EG", "MA", "SN", "ZM", "MW", "MZ"],
    "asia": ["CN", "IN", "JP", "KR", "ID", "TH", "VN", "PH", "SG", "MY", "BD", "PK", "AU", "NZ", "TW"],
    "middle_east": ["AE", "SA", "IL", "JO", "LB", "IQ", "IR", "QA", "KW", "OM", "BH"],
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


@router.get("/country-stats", response_model=List[CountryStats])
async def get_country_stats(
    category: Optional[str] = Query(default=None, description="Filter by content category"),
    source: Optional[str] = Query(default=None, description="Filter by source name"),
    reliability_min: Optional[int] = Query(default=None, ge=0, le=100, description="Min reliability score"),
    region: Optional[str] = Query(default=None, description="Filter by region: europe, africa, asia, etc."),
):
    """
    Get per-country article counts, top topics, sources, and credibility.

    Supports filtering by: content category, source name, minimum reliability,
    and geographic region (europe, africa, asia, latin_america, middle_east, north_america).
    """
    db = get_postgres()

    try:
        conditions = ["a.country_code IS NOT NULL", "a.country_code != ''"]
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
            conditions.append("a.country_code = ANY(:region_codes)")
            params["region_codes"] = REGION_COUNTRIES[region]

        where = " AND ".join(conditions)

        rows = db.execute_query(f"""
            SELECT
                a.country_code,
                COUNT(*) as article_count,
                MAX(a.created_at) as last_updated,
                AVG(a.reliability_score) as avg_reliability
            FROM articles a
            WHERE {where}
            GROUP BY a.country_code
            ORDER BY article_count DESC
        """, params)

        country_names = _get_country_names(db)

        stats = []
        for row in (rows or []):
            cc = row["country_code"]

            # Top topics
            topic_rows = db.execute_query("""
                SELECT UNNEST(tags) as tag, COUNT(*) as cnt
                FROM articles
                WHERE country_code = :cc AND tags IS NOT NULL
                GROUP BY tag ORDER BY cnt DESC LIMIT 3
            """, {"cc": cc})
            top_topics = [r["tag"] for r in (topic_rows or [])]

            # Top sources for this country
            source_rows = db.execute_query("""
                SELECT source_name, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND source_name IS NOT NULL
                GROUP BY source_name ORDER BY cnt DESC LIMIT 3
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
        conditions = ["a.country_code IS NOT NULL", "a.source_name IS NOT NULL"]
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
async def query_map(request: MapQueryRequest):
    """
    Agentic map query endpoint — accepts natural language or structured filters
    and returns map-ready country highlights with article counts.

    This endpoint powers chat-driven map interactions:
    - "Show me climate news about drought in East Africa"
    - "Highlight countries with high-credibility renewable energy coverage"
    - "Which sources cover Southeast Asian climate?"

    Returns country highlights that can be rendered on the map, plus an
    optional LLM-generated summary answer.
    """
    db = get_postgres()

    conditions = ["a.country_code IS NOT NULL"]
    params: Dict[str, Any] = {"limit": request.limit}

    # Apply structured filters
    if request.countries:
        conditions.append("a.country_code = ANY(:countries)")
        params["countries"] = [c.upper() for c in request.countries]
    if request.region and request.region in REGION_COUNTRIES:
        conditions.append("a.country_code = ANY(:region_codes)")
        params["region_codes"] = REGION_COUNTRIES[request.region]
    if request.sources:
        conditions.append("a.source_name = ANY(:sources)")
        params["sources"] = request.sources
    if request.reliability_min is not None:
        conditions.append("COALESCE(a.reliability_score, 0) >= :rel_min")
        params["rel_min"] = request.reliability_min
    if request.categories:
        conditions.append("a.content_category = ANY(:cats)")
        params["cats"] = [c.lower() for c in request.categories]
    if request.topic:
        conditions.append(":topic = ANY(a.tags)")
        params["topic"] = request.topic.lower()

    # If natural language query, add full-text search
    if request.query:
        conditions.append(
            "to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,'')) "
            "@@ plainto_tsquery('english', :q)"
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

        # Generate a summary answer if it was a natural language query
        answer = None
        if request.query and highlights:
            top_countries = ", ".join(f"{h.country_name} ({h.article_count})" for h in highlights[:5])
            answer = (
                f"Found {total} articles matching your query across {len(highlights)} countries. "
                f"Top coverage: {top_countries}."
            )
        elif request.query and not highlights:
            answer = f"No articles found matching: \"{request.query}\". Try broadening your search."

        filters_applied = {k: v for k, v in {
            "query": request.query,
            "countries": request.countries or None,
            "region": request.region,
            "sources": request.sources or None,
            "reliability_min": request.reliability_min,
            "categories": request.categories or None,
            "topic": request.topic,
        }.items() if v}

        return MapQueryResponse(
            query=request.query,
            country_highlights=highlights,
            matching_articles=total,
            answer=answer,
            filters_applied=filters_applied,
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
            WHERE source_name IS NOT NULL
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
            WHERE tags IS NOT NULL
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
