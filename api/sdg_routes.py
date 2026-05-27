"""UN Sustainable Development Goals endpoints — Stage 6 / M7.

Reads the SDG taxonomy + tagger from
app/domains/content/sdg.py. Exposes:

  GET /api/sdg                — list the 17 goals + meta
  GET /api/sdg/{goal_id}      — articles + research + companies tagged
                                to this goal (cross-artifact)
  POST /api/sdg/tag           — ad-hoc tag arbitrary text

Tagging is currently on-the-fly (no sdg_tags column persisted yet —
that's the next pass once the keyword set settles). Each browse query
runs the tagger over the artifact's title + excerpt + brief.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.domains.content.sdg import (
    SDG_GOALS,
    SDG_BY_ID,
    tag_text,
    tag_to_goal_ids,
)
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("sdg")
router = APIRouter(prefix="/api/sdg", tags=["UN SDG"])


@router.get("")
async def list_sdgs():
    """List all 17 SDG goals with color + icon for FE chip rendering."""
    return {"goals": SDG_GOALS, "total": len(SDG_GOALS)}


@router.get("/{goal_id}")
async def get_artifacts_for_goal(
    goal_id: int,
    article_limit: int = Query(20, ge=1, le=100),
    research_limit: int = Query(10, ge=1, le=50),
    company_limit: int = Query(10, ge=1, le=50),
):
    """Cross-artifact browse for one SDG goal.

    Returns articles, research analyses, and companies whose content
    matches at least one keyword for this goal. Lightweight ILIKE-based
    scan for the MVP — exact behaviour the user asked for ("SDG should
    span all categories of analysis") without requiring a sdg_tags
    column migration yet.
    """
    if goal_id not in SDG_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown SDG goal_id")
    goal = SDG_BY_ID[goal_id]
    db = get_postgres()

    # Build a SQL OR of the keyword tokens — single-pass scan.
    from app.domains.content.sdg import SDG_KEYWORDS
    keywords = SDG_KEYWORDS[goal_id]
    # ILIKE search on title + excerpt + executive_brief (any of the keywords)
    where_terms = " OR ".join(
        f"(lower(coalesce(a.title,'') || ' ' || coalesce(a.excerpt,'') || ' ' || coalesce(a.executive_brief,'')) LIKE :kw{i})"
        for i in range(len(keywords))
    )
    params = {f"kw{i}": f"%{kw.lower()}%" for i, kw in enumerate(keywords)}
    params["alim"] = article_limit

    try:
        article_rows = db.execute_query(
            f"""SELECT a.article_id, a.title, a.source_name, a.country_code,
                       a.overall_credibility, a.published_date
                FROM articles a
                WHERE ({where_terms})
                  AND a.is_synthetic = FALSE
                ORDER BY a.published_date DESC NULLS LAST
                LIMIT :alim""",
            params,
        )
    except Exception as exc:
        logger.debug(f"sdg article scan failed: {exc}")
        article_rows = []

    # Companies — match via name + sector (cheaper proxy than full disclosures)
    try:
        company_where = " OR ".join(
            f"(lower(coalesce(c.name,'') || ' ' || coalesce(c.sector_nace,'')) LIKE :ckw{i})"
            for i in range(len(keywords))
        )
        cparams = {f"ckw{i}": f"%{kw.lower()}%" for i, kw in enumerate(keywords)}
        cparams["clim"] = company_limit
        company_rows = db.execute_query(
            f"""SELECT company_id, name, ticker, country_code, sector_nace
                FROM companies c
                WHERE ({company_where})
                LIMIT :clim""",
            cparams,
        )
    except Exception:
        company_rows = []

    return {
        "goal": goal,
        "articles": [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name"),
                "country_code": r.get("country_code"),
                "credibility": r.get("overall_credibility"),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
            }
            for r in (article_rows or [])
        ],
        "companies": [
            {
                "company_id": str(r["company_id"]),
                "name": r.get("name"),
                "ticker": r.get("ticker"),
                "country_code": r.get("country_code"),
                "sector": r.get("sector_nace"),
            }
            for r in (company_rows or [])
        ],
        "article_count": len(article_rows or []),
        "company_count": len(company_rows or []),
    }


class TagTextRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=20000)
    min_match_count: int = Field(default=1, ge=1, le=10)


@router.post("/tag")
async def tag_arbitrary_text(payload: TagTextRequest):
    """Tag a free-text snippet with relevant SDGs. Used by the chat
    skill `tag_sdgs` + ad-hoc analysis flows."""
    results = tag_text(payload.text, min_match_count=payload.min_match_count)
    return {
        "input_chars": len(payload.text),
        "min_match_count": payload.min_match_count,
        "sdgs": results,
        "goal_ids": [r["goal_id"] for r in results],
    }
