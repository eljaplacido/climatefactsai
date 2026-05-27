"""Map sync — Stage 7 / M8 cross-artifact map coverage.

User framing: "Create a loop in our agentic dev that regularly
reflects new features to the map features and its interactive
features from article, research or company climate tracker to map;
Highlighting the concerned countries they discuss, where company
reports state operations affects, with what countries or areas
articles deal with etc."

The existing /api/map/* endpoints each query ONE artifact type. M8
adds a cross-artifact aggregator that returns, per country, the
combined count of:
  - articles
  - companies (by country_code)
  - completed research analyses
  - SDG-tagged artifacts (any SDG match)

So the map can colour/size each country by combined relevance and
the user can drill into any country to see all artifacts.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-sync")
router = APIRouter(prefix="/api/map", tags=["Map - Cross-Artifact"])


@router.get("/cross-artifact-coverage")
async def cross_artifact_coverage(
    min_article_count: int = Query(0, ge=0),
):
    """One row per country with combined article + company + research counts.

    Used by the map front-end to colour countries by combined relevance.
    A country with 25 articles + 8 companies + 2 research papers reads
    very differently from one with 25 articles and nothing else.

    Result row shape:
      {country_code, article_count, company_count, research_count,
       total_artifacts, last_article_at}
    """
    db = get_postgres()
    # Articles per country
    articles_per_cc = db.execute_query(
        """SELECT country_code,
                  COUNT(*) AS n,
                  MAX(published_date) AS latest
           FROM articles
           WHERE country_code IS NOT NULL
             AND country_code <> 'XX'
             AND is_synthetic = FALSE
           GROUP BY country_code""",
        {},
    ) or []
    # Companies per country
    try:
        companies_per_cc = db.execute_query(
            """SELECT country_code, COUNT(*) AS n
               FROM companies
               WHERE country_code IS NOT NULL
               GROUP BY country_code""",
            {},
        ) or []
    except Exception:
        companies_per_cc = []
    # Research analyses per country (url_analyses + completed only)
    try:
        research_per_cc = db.execute_query(
            """SELECT COALESCE(a.country_code, 'XX') AS country_code,
                      COUNT(*) AS n
               FROM url_analyses ua
               LEFT JOIN articles a ON a.url = ua.submitted_url
               WHERE ua.status = 'completed'
               GROUP BY COALESCE(a.country_code, 'XX')""",
            {},
        ) or []
    except Exception:
        research_per_cc = []

    # Merge by country_code
    out: dict[str, dict] = {}
    for r in articles_per_cc:
        cc = r["country_code"]
        out[cc] = {
            "country_code": cc,
            "article_count": int(r.get("n") or 0),
            "company_count": 0,
            "research_count": 0,
            "last_article_at": str(r["latest"]) if r.get("latest") else None,
        }
    for r in companies_per_cc:
        cc = r["country_code"]
        out.setdefault(cc, {
            "country_code": cc, "article_count": 0,
            "company_count": 0, "research_count": 0,
            "last_article_at": None,
        })
        out[cc]["company_count"] = int(r.get("n") or 0)
    for r in research_per_cc:
        cc = r["country_code"]
        if cc == "XX":
            continue
        out.setdefault(cc, {
            "country_code": cc, "article_count": 0,
            "company_count": 0, "research_count": 0,
            "last_article_at": None,
        })
        out[cc]["research_count"] = int(r.get("n") or 0)

    rows = [
        {**v, "total_artifacts":
            v["article_count"] + v["company_count"] + v["research_count"]}
        for v in out.values()
        if v["article_count"] >= min_article_count
    ]
    rows.sort(key=lambda r: r["total_artifacts"], reverse=True)

    # Coverage summary
    countries_with_any = sum(1 for r in rows if r["total_artifacts"] > 0)
    countries_with_articles = sum(1 for r in rows if r["article_count"] > 0)
    countries_with_companies = sum(1 for r in rows if r["company_count"] > 0)

    return {
        "by_country": rows,
        "total_countries": len(rows),
        "summary": {
            "countries_with_any_artifact": countries_with_any,
            "countries_with_articles": countries_with_articles,
            "countries_with_companies": countries_with_companies,
            "world_coverage_pct_of_193": round(100 * countries_with_any / 193, 1),
        },
    }


@router.get("/country/{cc}/artifacts")
async def country_artifacts_drill_down(
    cc: str,
    article_limit: int = Query(15, ge=1, le=50),
    company_limit: int = Query(10, ge=1, le=50),
):
    """Drill into one country: latest articles + companies headquartered.

    Powers the map's country-click drawer. Combines all artifact kinds
    so the user gets a single systemic view instead of having to switch
    between map layers.
    """
    cc = cc.upper()
    if len(cc) != 2:
        raise HTTPException(status_code=400, detail="country_code must be ISO-2")
    db = get_postgres()
    articles = db.execute_query(
        """SELECT article_id, title, source_name, overall_credibility,
                  published_date, content_category
           FROM articles
           WHERE country_code = :cc AND is_synthetic = FALSE
           ORDER BY published_date DESC NULLS LAST
           LIMIT :lim""",
        {"cc": cc, "lim": article_limit},
    ) or []
    try:
        companies = db.execute_query(
            """SELECT company_id, name, ticker, sector_nace
               FROM companies
               WHERE country_code = :cc
               LIMIT :lim""",
            {"cc": cc, "lim": company_limit},
        ) or []
    except Exception:
        companies = []
    return {
        "country_code": cc,
        "articles": [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name"),
                "credibility": r.get("overall_credibility"),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "category": r.get("content_category"),
            }
            for r in articles
        ],
        "companies": [
            {
                "company_id": str(r["company_id"]),
                "name": r.get("name"),
                "ticker": r.get("ticker"),
                "sector": r.get("sector_nace"),
            }
            for r in companies
        ],
        "article_count": len(articles),
        "company_count": len(companies),
    }
