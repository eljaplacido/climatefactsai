"""
Green Transition Routes — Per-country green economy intelligence.

Aggregates article-derived scores for:
  • Green transition (policy, legislation, investment)
  • Renewable energy (solar, wind, hydro, geothermal, hydrogen)
  • Cleantech (innovation, carbon capture, battery tech)
  • Circular economy (EPR, waste reduction, material recovery)
  • Resource efficiency (energy/material efficiency, critical minerals)
  • Regenerative economy (agriculture, nature-based solutions)
  • Sustainability (ESG, biodiversity, SDGs)

Scores are derived from article coverage depth (0–10) and are available
for all 190+ countries tracked by the platform.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_optional_user

logger = setup_logging("green-transition-api")
router = APIRouter(prefix="/api/green-transition", tags=["Green Transition"])

# ---------------------------------------------------------------------------
# The 7 dimensions tracked
# ---------------------------------------------------------------------------
DIMENSIONS = [
    "green_transition",
    "renewable_energy",
    "cleantech",
    "circular_economy",
    "resource_efficiency",
    "regenerative_economy",
    "sustainability",
]

# Associated tags for enhanced querying
DIMENSION_TAGS: Dict[str, List[str]] = {
    "green_transition": ["green-transition", "decarbonization", "clean-energy", "just-transition"],
    "renewable_energy": ["renewable-energy", "solar", "wind", "geothermal", "hydro", "hydrogen"],
    "cleantech": ["cleantech", "carbon-capture", "innovation", "technology", "battery"],
    "circular_economy": ["circular-economy", "waste-reduction", "recycling", "material-recovery", "epr"],
    "resource_efficiency": ["resource-efficiency", "energy-efficiency", "critical-minerals", "water", "rare-earth"],
    "regenerative_economy": ["regenerative", "soil-carbon", "restoration", "nature-based", "agroforestry"],
    "sustainability": ["sustainability", "esg", "biodiversity", "sdg", "net-zero"],
}


class DimensionScore(BaseModel):
    dimension: str
    score: float  # 0–10
    article_count: int
    top_tags: List[str] = []


class CountryGreenProfile(BaseModel):
    country_code: str
    country_name: str
    overall_green_score: float  # average of all 7 dimensions, 0–10
    dimensions: List[DimensionScore]
    total_green_articles: int
    top_sources: List[str] = []
    last_updated: Optional[str] = None


class GlobalLeaderboard(BaseModel):
    leaders: List[CountryGreenProfile]
    dimension: Optional[str] = None
    total_countries: int


def _score(cnt: int) -> float:
    """Convert article count to 0–10 score (2 articles per point, capped at 10)."""
    return round(min(10.0, cnt / 2.0), 2)


@router.get("/country/{cc}", response_model=CountryGreenProfile)
async def get_country_green_profile(
    cc: str,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Full green transition profile for one country.

    Returns scores across all 7 dimensions plus top sources and total article count.
    Useful for agentic country analysis and comparison workflows.
    """
    from app.domains.content.forecast_service import COUNTRY_NAMES
    cc = cc.upper()
    db = get_postgres()
    country_name = COUNTRY_NAMES.get(cc, cc)

    try:
        rows = db.execute_query("""
            SELECT country_name FROM countries WHERE country_code = :cc
        """, {"cc": cc})
        if rows:
            country_name = rows[0].get("country_name", country_name)
    except Exception:
        pass

    dimensions: List[DimensionScore] = []
    total_articles = 0
    last_updated = None

    try:
        cat_rows = db.execute_query("""
            SELECT content_category, COUNT(*) as cnt,
                   MAX(published_date) as latest
            FROM articles
            WHERE country_code = :cc AND content_category IS NOT NULL
            GROUP BY content_category
        """, {"cc": cc})

        cat_map = {r["content_category"]: r for r in (cat_rows or [])}

        for dim in DIMENSIONS:
            row = cat_map.get(dim, {})
            cnt = row.get("cnt", 0) or 0
            total_articles += cnt
            latest = row.get("latest")
            if latest and (last_updated is None or str(latest) > last_updated):
                last_updated = str(latest)

            # Top tags for this dimension
            tags_rows = db.execute_query("""
                SELECT UNNEST(tags) as tag, COUNT(*) as cnt
                FROM articles
                WHERE country_code = :cc AND content_category = :dim AND tags IS NOT NULL
                GROUP BY tag ORDER BY cnt DESC LIMIT 4
            """, {"cc": cc, "dim": dim})
            top_tags = [r["tag"] for r in (tags_rows or [])]

            dimensions.append(DimensionScore(
                dimension=dim,
                score=_score(cnt),
                article_count=cnt,
                top_tags=top_tags,
            ))

    except Exception as e:
        logger.warning(f"Green profile query failed for {cc}: {e}")
        dimensions = [DimensionScore(dimension=d, score=0.0, article_count=0) for d in DIMENSIONS]

    # Top sources
    top_sources: List[str] = []
    try:
        src_rows = db.execute_query("""
            SELECT source_name, COUNT(*) as cnt
            FROM articles
            WHERE country_code = :cc
              AND content_category = ANY(:dims)
              AND source_name IS NOT NULL
            GROUP BY source_name ORDER BY cnt DESC LIMIT 5
        """, {"cc": cc, "dims": DIMENSIONS})
        top_sources = [r["source_name"] for r in (src_rows or [])]
    except Exception:
        pass

    overall = round(sum(d.score for d in dimensions) / len(dimensions), 2) if dimensions else 0.0

    return CountryGreenProfile(
        country_code=cc,
        country_name=country_name,
        overall_green_score=overall,
        dimensions=dimensions,
        total_green_articles=total_articles,
        top_sources=top_sources,
        last_updated=last_updated,
    )


@router.get("/leaderboard", response_model=GlobalLeaderboard)
async def get_green_leaderboard(
    dimension: Optional[str] = Query(
        None,
        description=f"Sort by specific dimension. One of: {', '.join(DIMENSIONS)}",
    ),
    region: Optional[str] = Query(None, description="Filter by region (europe, africa, asia, etc.)"),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Global green transition leaderboard.

    Returns top countries ranked by overall green score (default) or
    a specific dimension. Can be filtered by region.

    Powers agentic comparisons: "Which African countries lead on circular economy?"
    """
    from api.map_routes import REGION_COUNTRIES
    from app.domains.content.forecast_service import COUNTRY_NAMES
    db = get_postgres()

    dim = dimension.lower() if dimension and dimension.lower() in DIMENSIONS else None

    country_filter = ""
    params: Dict[str, Any] = {"dims": DIMENSIONS, "limit": limit}
    if region and region in REGION_COUNTRIES:
        country_filter = "AND a.country_code = ANY(:region_codes)"
        params["region_codes"] = REGION_COUNTRIES[region]

    try:
        cat_rows = db.execute_query(f"""
            SELECT a.country_code,
                   a.content_category,
                   COUNT(*) as cnt
            FROM articles a
            WHERE a.content_category = ANY(:dims)
              AND a.country_code IS NOT NULL
              {country_filter}
            GROUP BY a.country_code, a.content_category
        """, params)
    except Exception as e:
        logger.error(f"Leaderboard query failed: {e}")
        return GlobalLeaderboard(leaders=[], total_countries=0, dimension=dimension)

    # Aggregate per country
    by_country: Dict[str, Dict[str, int]] = {}
    for row in (cat_rows or []):
        cc = row["country_code"]
        cat = row["content_category"]
        by_country.setdefault(cc, {})[cat] = row.get("cnt", 0) or 0

    # Compute score
    def country_score(cat_map: Dict[str, int]) -> float:
        if dim:
            return _score(cat_map.get(dim, 0))
        scores = [_score(cat_map.get(d, 0)) for d in DIMENSIONS]
        return round(sum(scores) / len(scores), 2)

    ranked = sorted(by_country.items(), key=lambda kv: country_score(kv[1]), reverse=True)[:limit]

    leaders: List[CountryGreenProfile] = []
    for cc, cat_map in ranked:
        dims = [
            DimensionScore(dimension=d, score=_score(cat_map.get(d, 0)), article_count=cat_map.get(d, 0))
            for d in DIMENSIONS
        ]
        overall = round(sum(d.score for d in dims) / len(dims), 2)
        leaders.append(CountryGreenProfile(
            country_code=cc,
            country_name=COUNTRY_NAMES.get(cc, cc),
            overall_green_score=overall,
            dimensions=dims,
            total_green_articles=sum(cat_map.values()),
        ))

    return GlobalLeaderboard(
        leaders=leaders,
        dimension=dimension,
        total_countries=len(by_country),
    )


@router.get("/dimensions")
async def list_dimensions():
    """List all tracked green transition dimensions with associated tags."""
    return {
        "dimensions": [
            {"id": d, "tags": DIMENSION_TAGS.get(d, [])} for d in DIMENSIONS
        ],
        "total": len(DIMENSIONS),
    }


@router.get("/compare")
async def compare_green_profiles(
    countries: str = Query(..., description="Comma-separated ISO country codes, e.g. FI,DE,KE"),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Compare green transition profiles across multiple countries.

    Returns per-dimension scores for each country, plus a narrative summary.
    Supports agentic queries like: compare Finland, Germany and Kenya on renewable energy.
    """
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()][:10]
    if not codes:
        return {"error": "No country codes provided"}

    from app.domains.content.forecast_service import COUNTRY_NAMES
    db = get_postgres()

    profiles = []
    for cc in codes:
        try:
            cat_rows = db.execute_query("""
                SELECT content_category, COUNT(*) as cnt
                FROM articles
                WHERE country_code = :cc AND content_category = ANY(:dims)
                GROUP BY content_category
            """, {"cc": cc, "dims": DIMENSIONS})

            cat_map = {r["content_category"]: r.get("cnt", 0) for r in (cat_rows or [])}
            dims = [DimensionScore(dimension=d, score=_score(cat_map.get(d, 0)), article_count=cat_map.get(d, 0)) for d in DIMENSIONS]
            overall = round(sum(d.score for d in dims) / len(dims), 2)
            profiles.append({
                "country_code": cc,
                "country_name": COUNTRY_NAMES.get(cc, cc),
                "overall_green_score": overall,
                "dimensions": {d.dimension: {"score": d.score, "articles": d.article_count} for d in dims},
            })
        except Exception as e:
            logger.warning(f"Green compare failed for {cc}: {e}")
            profiles.append({
                "country_code": cc,
                "country_name": COUNTRY_NAMES.get(cc, cc),
                "overall_green_score": 0.0,
                "dimensions": {d: {"score": 0.0, "articles": 0} for d in DIMENSIONS},
            })

    # Narrative summary
    if profiles:
        best = max(profiles, key=lambda p: p["overall_green_score"])
        summary = (
            f"Comparing {len(codes)} countries on green transition. "
            f"{best['country_name']} leads with overall score {best['overall_green_score']}/10. "
        )
        if len(profiles) > 1:
            worst = min(profiles, key=lambda p: p["overall_green_score"])
            summary += f"{worst['country_name']} has the lowest coverage ({worst['overall_green_score']}/10)."
    else:
        summary = "No data available for the requested countries."

    return {
        "countries": profiles,
        "summary": summary,
        "dimensions_tracked": DIMENSIONS,
    }
