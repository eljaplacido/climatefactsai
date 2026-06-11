"""Semantic layer routes — Stage 4 / M5 ("why are these connected").

Goal (user framing): "see how phenomena are connected to bigger climate
trends and weather patterns, news or releases in the same area etc.
and ask questions like how and why things are connected."

Three endpoints power the drill-down:

  GET  /api/semantic/entity/{entity_id}
       Full entity profile + N-hop entity neighborhood + ALL articles
       mentioning the entity (paginated). Used by the
       /explore/entity/{id} page.

  GET  /api/semantic/entities/search?q=...
       Free-text entity lookup so users can jump to an entity directly
       (e.g. "COP30", "Eneva", "Amazon rainforest").

  POST /api/semantic/explain
       LLM-driven "why connected" — given a list of article_ids OR
       entity_ids, return a structured paragraph explaining the
       relationship. Uses GX10 Lane A when available, falls back to
       cloud DeepSeek. Cites specific shared entities + relationships.

The graph data is populated by clilens-lane-a-entity systemd worker
on GX10; this module never extracts entities itself — only reads +
LLM-synthesises explanations.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("semantic")
router = APIRouter(prefix="/api/semantic", tags=["Semantic Layer"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_query(db, sql: str, params: dict, default: list | None = None) -> list:
    """Query that returns [] on KG-schema-missing errors instead of 500.

    The knowledge_graph tables (entities, article_entities,
    entity_relationships) live under infrastructure/database/migrations
    OR legacy database/migrations depending on which branch built the
    image — this guard lets the semantic surface degrade to an empty
    state rather than crash when the schema isn't deployed.
    """
    try:
        return db.execute_query(sql, params) or []
    except Exception as exc:
        logger.debug(f"semantic safe-query soft-fail: {exc}")
        return default if default is not None else []


# ---------------------------------------------------------------------------
# Entity profile + neighborhood
# ---------------------------------------------------------------------------

@router.get("/entity/{entity_id}")
async def get_entity_profile(
    entity_id: str,
    article_limit: int = Query(20, ge=1, le=100),
    neighbor_limit: int = Query(20, ge=1, le=100),
):
    """Full entity drill-down: profile + connected entities + articles.

    Powers the /explore/entity/{id} page. Returns:
      - entity: name, type, description, article_count, total_mentions
      - neighbors: entities directly connected via relationships
      - articles: every article that mentions this entity (paginated)
      - relationships: structured edges from this entity
    """
    db = get_postgres()

    # Entity profile
    profile_rows = _safe_query(
        db,
        """SELECT entity_id, entity_name, entity_type, description,
                  article_count, first_seen_at
           FROM entities WHERE entity_id::text = :eid""",
        {"eid": entity_id},
    )
    if not profile_rows:
        raise HTTPException(status_code=404, detail="Entity not found or KG schema not deployed")
    e = profile_rows[0]

    # All relationships involving this entity (in + out)
    relationships = _safe_query(
        db,
        """SELECT er.relationship_id,
                  e_src.entity_id AS src_id, e_src.entity_name AS src_name, e_src.entity_type AS src_type,
                  e_tgt.entity_id AS tgt_id, e_tgt.entity_name AS tgt_name, e_tgt.entity_type AS tgt_type,
                  er.relationship_type, er.strength, er.confidence, er.evidence_text
           FROM entity_relationships er
           JOIN entities e_src ON e_src.entity_id = er.source_entity_id
           JOIN entities e_tgt ON e_tgt.entity_id = er.target_entity_id
           WHERE er.source_entity_id::text = :eid OR er.target_entity_id::text = :eid
           ORDER BY er.confidence DESC, er.strength DESC
           LIMIT :nl""",
        {"eid": entity_id, "nl": neighbor_limit},
    )

    # Articles mentioning this entity
    articles = _safe_query(
        db,
        """SELECT a.article_id, a.title, a.source_name, a.country_code,
                  a.published_date, a.overall_credibility,
                  ae.mention_count, ae.salience
           FROM article_entities ae
           JOIN articles a ON a.article_id = ae.article_id
           WHERE ae.entity_id::text = :eid
           ORDER BY ae.salience DESC, a.published_date DESC NULLS LAST
           LIMIT :al""",
        {"eid": entity_id, "al": article_limit},
    )

    # Build the unique neighbor entity set from relationships
    neighbor_set: dict[str, dict] = {}
    for r in relationships:
        for prefix in ("src", "tgt"):
            nid = str(r.get(f"{prefix}_id"))
            if nid != str(entity_id):
                neighbor_set.setdefault(nid, {
                    "entity_id": nid,
                    "name": r.get(f"{prefix}_name", ""),
                    "type": r.get(f"{prefix}_type", ""),
                })

    return {
        "entity": {
            "entity_id": str(e["entity_id"]),
            "name": e.get("entity_name", ""),
            "type": e.get("entity_type", ""),
            "description": e.get("description") or "",
            "article_count": int(e.get("article_count") or 0),
            "created_at": str(e["first_seen_at"]) if e.get("first_seen_at") else None,
        },
        "neighbors": list(neighbor_set.values()),
        "relationships": [
            {
                "relationship_id": str(r["relationship_id"]),
                "source": {"id": str(r["src_id"]), "name": r["src_name"], "type": r.get("src_type")},
                "target": {"id": str(r["tgt_id"]), "name": r["tgt_name"], "type": r.get("tgt_type")},
                "type": r.get("relationship_type"),
                "strength": float(r.get("strength") or 0),
                "confidence": float(r.get("confidence") or 0),
                "evidence_text": r.get("evidence_text") or "",
            }
            for r in relationships
        ],
        "articles": [
            {
                "article_id": str(a["article_id"]),
                "title": a.get("title", ""),
                "source_name": a.get("source_name", ""),
                "country_code": a.get("country_code", ""),
                "published_date": str(a["published_date"]) if a.get("published_date") else None,
                "credibility": a.get("overall_credibility", "UNKNOWN"),
                "mention_count": int(a.get("mention_count") or 1),
                "salience": float(a.get("salience") or 0),
            }
            for a in articles
        ],
    }


@router.get("/entities/search")
async def search_entities(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(10, ge=1, le=50),
):
    """Free-text entity lookup. Powers a future search box on
    /explore. ILIKE on entity_name; ranks by article_count DESC so
    well-known entities surface first."""
    db = get_postgres()
    rows = _safe_query(
        db,
        """SELECT entity_id, entity_name, entity_type, description,
                  article_count
           FROM entities
           WHERE entity_name ILIKE :q
           ORDER BY article_count DESC NULLS LAST, entity_name ASC
           LIMIT :lim""",
        {"q": f"%{q}%", "lim": limit},
    )
    return {
        "query": q,
        "results": [
            {
                "entity_id": str(r["entity_id"]),
                "name": r["entity_name"],
                "type": r["entity_type"],
                "description": r.get("description") or "",
                "article_count": int(r.get("article_count") or 0),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# "Why connected" — LLM explanation
# ---------------------------------------------------------------------------

class ExplainRequest(BaseModel):
    article_ids: Optional[list[str]] = Field(None, max_length=5)
    entity_ids: Optional[list[str]] = Field(None, max_length=5)


@router.post("/explain")
async def explain_connection(
    payload: ExplainRequest,
    current_user: Any = Depends(get_optional_user),
):
    """LLM-driven "why are these connected" for a pair / small set.

    Strategy:
      1. Find shared entities (if articles) OR shared articles (if entities)
      2. Build a structured context with those bridges
      3. Ask the LLM to write a 100-200 word paragraph explaining the
         relationship, citing specific bridges by name
      4. Return paragraph + structured `bridges` list so the FE can
         render highlights

    Uses the same _call_llm chain as ArticleEnrichmentService — local
    GX10 first when CLILENS_ENRICHMENT_PROVIDER=local-gx10 is pinned,
    falls back to cloud DeepSeek. No retry / no fallback expected to
    be visible to the user.
    """
    if not (payload.article_ids or payload.entity_ids):
        raise HTTPException(status_code=400, detail="Provide article_ids OR entity_ids")
    if payload.article_ids and len(payload.article_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 article_ids")
    if payload.entity_ids and len(payload.entity_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 entity_ids")

    # Quota gate (2026-06-10 audit): this runs an LLM per call and was fully
    # anonymous + unmetered. Meter it against deep_research — matching the
    # frontend copy ("Counts against your deep-search quota") and its existing
    # 429 handling. Anonymous callers get the anonymous envelope.
    user_tier = "anonymous"
    user_id = None
    if current_user is not None:
        user_tier = getattr(current_user, "subscription_tier", "freemium") or "freemium"
        user_id = getattr(current_user, "user_id", None)
    from api.quota_service import QuotaService
    QuotaService.check_and_raise(
        user_id=str(user_id) if user_id else None,
        tier=user_tier,
        quota_key="deep_research",
    )

    db = get_postgres()

    # --- Build the bridge context ------------------------------------
    bridges: list[dict] = []
    item_meta: list[dict] = []

    if payload.article_ids:
        # Shared entities across the article set
        ids = payload.article_ids
        # Article titles for context
        titles = _safe_query(
            db,
            "SELECT article_id, title FROM articles WHERE article_id::text = ANY(:ids)",
            {"ids": ids},
        )
        item_meta = [
            {"id": str(r["article_id"]), "label": r.get("title", "")[:120]}
            for r in titles
        ]
        # Entities shared by 2+ of the supplied articles
        shared = _safe_query(
            db,
            """SELECT e.entity_id, e.entity_name, e.entity_type, e.description,
                      COUNT(DISTINCT ae.article_id) AS shared_count
               FROM article_entities ae
               JOIN entities e ON e.entity_id = ae.entity_id
               WHERE ae.article_id::text = ANY(:ids)
               GROUP BY e.entity_id, e.entity_name, e.entity_type, e.description
               HAVING COUNT(DISTINCT ae.article_id) >= 2
               ORDER BY shared_count DESC, e.article_count DESC
               LIMIT 15""",
            {"ids": ids},
        )
        bridges = [
            {
                "kind": "shared_entity",
                "id": str(r["entity_id"]),
                "name": r["entity_name"],
                "type": r["entity_type"],
                "description": (r.get("description") or "")[:200],
                "shared_count": int(r["shared_count"]),
            }
            for r in shared
        ]
    else:
        # Shared articles across the entity set
        ids = payload.entity_ids
        ent_meta = _safe_query(
            db,
            "SELECT entity_id, entity_name FROM entities WHERE entity_id::text = ANY(:ids)",
            {"ids": ids},
        )
        item_meta = [
            {"id": str(r["entity_id"]), "label": r.get("entity_name", "")}
            for r in ent_meta
        ]
        shared = _safe_query(
            db,
            """SELECT a.article_id, a.title, a.source_name,
                      COUNT(DISTINCT ae.entity_id) AS shared_count
               FROM article_entities ae
               JOIN articles a ON a.article_id = ae.article_id
               WHERE ae.entity_id::text = ANY(:ids)
               GROUP BY a.article_id, a.title, a.source_name
               HAVING COUNT(DISTINCT ae.entity_id) >= 2
               ORDER BY shared_count DESC, a.published_date DESC NULLS LAST
               LIMIT 15""",
            {"ids": ids},
        )
        bridges = [
            {
                "kind": "shared_article",
                "id": str(r["article_id"]),
                "name": (r.get("title") or "")[:120],
                "source_name": r.get("source_name"),
                "shared_count": int(r["shared_count"]),
            }
            for r in shared
        ]

    if not bridges:
        return {
            "explanation": (
                "No shared entities or articles found between these items. "
                "They may be conceptually related but the knowledge graph hasn't "
                "captured a bridge yet — try asking again after the entity worker "
                "has processed more articles."
            ),
            "bridges": [],
            "items": item_meta,
            "llm_provider": "none",
        }

    # --- LLM synthesis ----------------------------------------------
    try:
        from app.domains.content.article_enrichment_service import ArticleEnrichmentService
    except Exception as exc:
        return {
            "explanation": f"LLM unavailable ({type(exc).__name__}); see bridges list below.",
            "bridges": bridges,
            "items": item_meta,
            "llm_provider": "unavailable",
        }

    service = ArticleEnrichmentService(db)
    items_text = "\n".join(
        f"- {i+1}. {it['label']}" + (f" (source: {it.get('source_name')})" if it.get("source_name") else "")
        for i, it in enumerate(item_meta)
    )
    bridges_text = "\n".join(
        f"- {b['name']} ({b.get('type', b.get('kind'))}): shared by {b['shared_count']} items"
        + (f" — {b['description']}" if b.get("description") else "")
        for b in bridges[:10]
    )
    system_prompt = (
        "You explain how multiple climate-related items (articles or entities) are "
        "connected through their shared knowledge-graph context. Write a single "
        "100-200 word paragraph in plain English. Cite specific bridge entities by "
        "name. Do not invent connections not supported by the bridges list. If the "
        "bridges are weak, say so directly."
    )
    user_prompt = (
        f"Items to connect:\n{items_text}\n\n"
        f"Bridges from the knowledge graph (entities or articles shared between items):\n"
        f"{bridges_text}\n\n"
        f"Write the explanation now."
    )

    try:
        import asyncio
        result = await service._call_llm(system_prompt, user_prompt, max_tokens=400)
    except Exception as exc:
        logger.warning(f"semantic/explain LLM call failed: {exc}")
        result = None

    if not result:
        return {
            "explanation": (
                "These items share the following bridge entities/articles "
                f"({len(bridges)} found): {', '.join(b['name'] for b in bridges[:5])}. "
                "An LLM-generated narrative explanation is currently unavailable."
            ),
            "bridges": bridges,
            "items": item_meta,
            "llm_provider": "fallback",
        }

    text, provider, model = result
    return {
        "explanation": text,
        "bridges": bridges,
        "items": item_meta,
        "llm_provider": provider,
        "llm_model": model,
    }
