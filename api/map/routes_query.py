"""Map routes — natural-language query and LLM-powered map interaction."""
import json, time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

# imports from sibling modules
from .models import MapQueryRequest, MapQueryResponse, CountryStats, REGION_COUNTRIES
from .services import _get_country_names, _llm_parse_query, _llm_generate_map_answer, _country_region
from .cache import _query_sessions
from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_optional_user

logger = setup_logging("map-api")
router = APIRouter()


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
