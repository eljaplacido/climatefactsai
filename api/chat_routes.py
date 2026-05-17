"""
General Climate Chat Routes

Provides a general-purpose chat interface for climate news questions
that searches across all articles and sources, not just a single article.
Users can ask broad questions and get insight-driven answers with citations.
"""

import json
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import UsageTracker, TIER_LIMITS
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("chat-api")
router = APIRouter(prefix="/api/chat", tags=["Chat"])


CHAT_LIMITS = {
    "freemium": 5,
    "basic": 25,
    "professional": None,
    "enterprise": None,
}


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: Optional[str] = Field(None, description="Existing session to continue")
    country: Optional[str] = Field(None, max_length=2, description="Filter by country")
    category: Optional[str] = Field(None, description="Filter by category")
    mode: Optional[str] = Field(
        "general",
        description="Chat mode: general, map_intelligence, research_analysis, article_qa",
    )
    view_context: Optional[dict] = Field(
        None,
        description=(
            "What the user is currently viewing. Recognised keys: route, "
            "article_id, country, compare_countries, analysis_id, "
            "deep_search_query, deep_search_compare, source_id, label."
        ),
    )


class ChatSource(BaseModel):
    article_id: str
    title: str
    source_name: str
    credibility: Optional[str] = None
    relevance: float = 0.0


class ChatResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    sources: List[ChatSource] = []
    confidence: float = 0.0
    model: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    # Mode-specific fields
    mode: Optional[str] = "general"
    highlighted_countries: Optional[List[str]] = None
    relevant_articles: Optional[List[dict]] = None
    cynefin_classification: Optional[dict] = None
    # Phase 6 wave 4 (2026-05-17): HallucinationDetector runs on every
    # chat synthesis against the retrieved article excerpts. Surfaces
    # hallucination_risk + is_grounded + flagged_segments so the UI can
    # warn when the answer is poorly grounded. Local checks (entity
    # overlap + statistic verification) always run; the LLM-grounding
    # sub-check degrades to risk=0.5 gracefully when no LLM key is set.
    hallucination_check: Optional[dict] = None


class ChatSessionInfo(BaseModel):
    session_id: str
    title: Optional[str] = None
    message_count: int = 0
    created_at: str
    updated_at: str


class ChatHistory(BaseModel):
    session_id: str
    messages: List[dict] = []
    total: int = 0


@router.post("", response_model=ChatResponse)
async def ask_general_question(
    request: ChatRequest,
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Ask a general climate news question across all articles.

    The system searches the article database for relevant content,
    then generates an answer grounded in real articles with citations.

    Rate limits per day:
    - Free: 5 questions
    - Basic: 25 questions
    - Professional/Enterprise: Unlimited
    """
    if current_user and isinstance(current_user, dict):
        user_tier = current_user.get("subscription_tier", "freemium")
        user_id = str(current_user.get("user_id", "anonymous"))
    else:
        user_tier = "freemium"
        user_id = "anonymous"

    # Check rate limit
    chat_limit = CHAT_LIMITS.get(user_tier)
    if chat_limit is not None:
        try:
            count = UsageTracker.get_usage_count(
                user_id=user_id, usage_type="general_chat", period="day"
            )
            if count >= chat_limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily chat limit reached ({count}/{chat_limit}). Upgrade for more.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    db = get_postgres()

    # Find or create session
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid4())
        try:
            db.execute_update(
                """INSERT INTO chat_sessions (session_id, user_id, title, session_type)
                   VALUES (:sid, :uid, :title, 'general')""",
                {
                    "sid": session_id,
                    "uid": user_id if user_id != "anonymous" else None,
                    "title": request.question[:100],
                },
            )
        except Exception as e:
            logger.warning(f"Could not create chat session: {e}")

    mode = (request.mode or "general").lower()

    # Hydrate the user's current view (article body, country stats, URL
    # analysis row, etc.) so the chat can answer "this article" / "this
    # country" without guessing. The hydrator is purely best-effort: if any
    # lookup fails the chat still works against the general corpus.
    view_context = request.view_context or {}
    # Backwards-compat: lift `country` from the request body into view_context
    # so old clients that didn't send view_context still get country-aware
    # answers.
    if request.country and "country" not in view_context:
        view_context = {**view_context, "country": request.country}
    hydrated_view = _hydrate_view_context(db, view_context)

    # If view_context provides a country and the request didn't, use it as a
    # corpus filter so retrieval matches the user's focus.
    effective_country = request.country or hydrated_view.get("country_code")

    # Use HybridRAGService for retrieval when available, fall back to FTS
    sources = await _hybrid_search_articles(
        db, request.question, effective_country, request.category
    )
    if not sources:
        sources = _search_relevant_articles(
            db, request.question, effective_country, request.category
        )

    # Build context from found articles
    context_text = _build_multi_article_context(db, sources)

    # Get conversation history for context
    history = _get_session_history(db, session_id, limit=5)

    # Mode-specific enrichment
    highlighted_countries = None
    relevant_articles_extra = None
    cynefin_classification = None

    if mode == "map_intelligence":
        # Extract unique country codes from sources for map highlighting
        highlighted_countries = list(set(
            s.credibility[:2] if s.credibility and len(s.credibility) == 2 else ""
            for s in sources
        ))
        # Better: extract from article data
        highlighted_countries = _extract_countries_from_sources(db, sources)
        relevant_articles_extra = [
            {"article_id": s.article_id, "title": s.title, "source": s.source_name}
            for s in sources[:10]
        ]

    elif mode == "research_analysis":
        # Route through Cynefin classification for analysis depth
        try:
            from app.domains.intelligence.cynefin_router import CynefinRouter
            cynefin = CynefinRouter()
            cynefin_classification = cynefin.classify(request.question)
        except Exception as e:
            logger.warning(f"Cynefin classification failed: {e}")

    # Resolve live platform metrics so the system prompt stays accurate
    platform_metrics = _get_platform_metrics(db)

    # Generate answer with the hydrated view context — this makes pronoun
    # resolution ("this country", "the article I'm reading") deterministic.
    # cynefin_classification (when present) steers the answer style:
    # direct_lookup → terse facts; multi_source_analysis → cross-referenced;
    # causal_analysis → counterfactual reasoning; rapid_assessment → flagged uncertainty.
    answer_data = await _generate_answer(
        request.question, context_text, sources, history, platform_metrics,
        view_context=hydrated_view,
        cynefin=cynefin_classification,
    )

    # Store message
    _store_chat_message(db, session_id, "user", request.question)
    _store_chat_message(
        db, session_id, "assistant", answer_data["answer"],
        sources_used=[s.source_name for s in sources[:5]],
        article_ids=[s.article_id for s in sources[:5]],
        confidence=answer_data["confidence"],
    )

    # Log usage
    try:
        UsageTracker.log_usage(
            user_id=user_id, usage_type="general_chat",
            metadata={"question": request.question[:100], "session_id": session_id, "mode": mode},
        )
    except Exception:
        pass

    return ChatResponse(
        session_id=session_id,
        question=request.question,
        answer=answer_data["answer"],
        sources=sources[:5],
        confidence=answer_data["confidence"],
        model=answer_data.get("model"),
        error=answer_data.get("error"),
        created_at=datetime.utcnow().isoformat(),
        mode=mode,
        highlighted_countries=highlighted_countries,
        relevant_articles=relevant_articles_extra,
        cynefin_classification=cynefin_classification,
        hallucination_check=answer_data.get("hallucination_check"),
    )


@router.get("/sessions", response_model=List[ChatSessionInfo])
async def list_chat_sessions(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List the user's chat sessions."""
    db = get_postgres()
    rows = db.execute_query(
        """SELECT s.session_id, s.title, s.created_at, s.updated_at,
                  COUNT(m.message_id) as message_count
           FROM chat_sessions s
           LEFT JOIN chat_messages m ON m.session_id = s.session_id
           WHERE s.user_id = :uid
           GROUP BY s.session_id
           ORDER BY s.updated_at DESC
           LIMIT :limit""",
        {"uid": str(current_user["user_id"]), "limit": limit},
    )
    return [
        ChatSessionInfo(
            session_id=str(r["session_id"]),
            title=r.get("title"),
            message_count=r.get("message_count", 0),
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
        )
        for r in (rows or [])
    ]


@router.get("/sessions/{session_id}", response_model=ChatHistory)
async def get_chat_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """Get message history for a chat session."""
    db = get_postgres()
    rows = db.execute_query(
        """SELECT message_id, role, content, sources_used, article_ids,
                  confidence, created_at
           FROM chat_messages
           WHERE session_id = :sid
           ORDER BY created_at ASC
           LIMIT :limit""",
        {"sid": session_id, "limit": limit},
    )
    messages = [
        {
            "id": str(r["message_id"]),
            "role": r["role"],
            "content": r["content"],
            "sources": r.get("sources_used") or [],
            "article_ids": r.get("article_ids") or [],
            "confidence": r.get("confidence", 0.0),
            "created_at": str(r["created_at"]),
        }
        for r in (rows or [])
    ]
    return ChatHistory(session_id=session_id, messages=messages, total=len(messages))


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    db = get_postgres()
    db.execute_update(
        "DELETE FROM chat_sessions WHERE session_id = :sid AND user_id = :uid",
        {"sid": session_id, "uid": str(current_user["user_id"])},
    )
    return {"status": "deleted"}


# ── Internal helpers ──

async def _hybrid_search_articles(
    db, question: str, country: Optional[str], category: Optional[str]
) -> List[ChatSource]:
    """Search articles using HybridRAGService with RRF fusion."""
    try:
        from app.domains.intelligence.hybrid_rag_service import HybridRAGService

        hybrid = HybridRAGService(db)
        filters = {}
        if country:
            filters["country_code"] = country.upper()
        if category:
            filters["content_category"] = category.lower()

        results = await hybrid.retrieve(query=question, limit=10, filters=filters)

        return [
            ChatSource(
                article_id=str(r.get("article_id", "")),
                title=r.get("title", ""),
                source_name=r.get("source_name", ""),
                credibility=r.get("credibility"),
                relevance=float(r.get("rrf_score", r.get("similarity_score", 0))),
            )
            for r in results
        ]
    except ImportError:
        logger.debug("HybridRAGService not available, using FTS fallback")
        return []
    except Exception as e:
        logger.warning(f"Hybrid search failed, falling back to FTS: {e}")
        return []


def _extract_countries_from_sources(db, sources: List[ChatSource]) -> List[str]:
    """Extract unique country codes from article sources for map highlighting."""
    if not sources:
        return []

    article_ids = [s.article_id for s in sources[:15]]
    placeholders = ", ".join(f":id{i}" for i in range(len(article_ids)))
    params = {f"id{i}": aid for i, aid in enumerate(article_ids)}

    rows = db.execute_query(
        f"""SELECT DISTINCT country_code
            FROM articles
            WHERE article_id IN ({placeholders})
              AND country_code IS NOT NULL""",
        params,
    )
    return [r["country_code"] for r in (rows or []) if r.get("country_code")]


def _search_relevant_articles(
    db, question: str, country: Optional[str], category: Optional[str]
) -> List[ChatSource]:
    """Full-text search articles relevant to the question."""
    params: dict = {"q": question, "limit": 10}
    filters = []

    if country:
        filters.append("a.country_code = :cc")
        params["cc"] = country.upper()
    if category:
        filters.append("a.content_category = :cat")
        params["cat"] = category.lower()

    where_extra = ""
    if filters:
        where_extra = "AND " + " AND ".join(filters)

    rows = db.execute_query(
        f"""SELECT a.article_id, a.title, a.source_name, a.overall_credibility,
                   ts_rank(
                       to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,'') || ' ' || COALESCE(a.extracted_text,'')),
                       plainto_tsquery('english', :q)
                   ) AS relevance
            FROM articles a
            WHERE to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,'') || ' ' || COALESCE(a.extracted_text,''))
                  @@ plainto_tsquery('english', :q)
            {where_extra}
            ORDER BY relevance DESC
            LIMIT :limit""",
        params,
    )

    if not rows:
        # Fallback 2: ILIKE keyword search
        keywords = [w.strip() for w in question.split() if len(w.strip()) > 2][:4]
        if keywords:
            ilike_parts = " OR ".join(
                f"LOWER(a.title) LIKE :kw{i} OR LOWER(a.excerpt) LIKE :kw{i}"
                for i in range(len(keywords))
            )
            ilike_params: dict = {"limit": 10}
            for i, kw in enumerate(keywords):
                ilike_params[f"kw{i}"] = f"%{kw.lower()}%"
            rows = db.execute_query(
                f"""SELECT a.article_id, a.title, a.source_name, a.overall_credibility,
                           0.15 AS relevance
                    FROM articles a
                    WHERE ({ilike_parts})
                    ORDER BY a.published_date DESC NULLS LAST LIMIT :limit""",
                ilike_params,
            )

    if not rows:
        # Fallback 3: recent articles
        rows = db.execute_query(
            f"""SELECT a.article_id, a.title, a.source_name, a.overall_credibility,
                       0.1 AS relevance
                FROM articles a
                WHERE a.claims_status = 'completed'
                {where_extra}
                ORDER BY a.created_at DESC LIMIT 5""",
            params,
        )

    return [
        ChatSource(
            article_id=str(r["article_id"]),
            title=r.get("title", ""),
            source_name=r.get("source_name", ""),
            credibility=r.get("overall_credibility"),
            relevance=float(r.get("relevance", 0)),
        )
        for r in (rows or [])
    ]


def _build_multi_article_context(db, sources: List[ChatSource]) -> str:
    """Build grounded context from multiple articles."""
    if not sources:
        return "No relevant articles found in the database."

    article_ids = [s.article_id for s in sources[:5]]
    placeholders = ", ".join(f":id{i}" for i in range(len(article_ids)))
    params = {f"id{i}": aid for i, aid in enumerate(article_ids)}

    rows = db.execute_query(
        f"""SELECT a.article_id, a.title, a.source_name, a.excerpt,
                   SUBSTRING(a.extracted_text FROM 1 FOR 500) as text_preview,
                   a.overall_credibility, a.insight_summary,
                   a.claims_status, a.claims_error_message
            FROM articles a
            WHERE a.article_id IN ({placeholders})""",
        params,
    )

    # Also fetch verified claims for these articles
    claims_rows = db.execute_query(
        f"""SELECT c.article_id, c.claim_text, fc.verification_status, fc.confidence_score
            FROM claims c
            LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
            WHERE c.article_id IN ({placeholders})
            ORDER BY fc.confidence_score DESC NULLS LAST
            LIMIT 20""",
        params,
    )

    claims_by_article: dict = {}
    for cr in (claims_rows or []):
        aid = str(cr["article_id"])
        claims_by_article.setdefault(aid, []).append(cr)

    parts = []
    for r in (rows or []):
        aid = str(r["article_id"])
        text = r.get("text_preview") or r.get("excerpt") or ""
        insight = r.get("insight_summary") or ""
        cred = r.get("overall_credibility") or "UNKNOWN"

        article_section = f"ARTICLE: {r.get('title', 'Untitled')}\nSOURCE: {r.get('source_name', 'Unknown')} (Credibility: {cred})\n"
        if insight:
            article_section += f"INSIGHT: {insight}\n"
        article_section += f"CONTENT: {text[:400]}\n"

        # Add claims
        article_claims = claims_by_article.get(aid, [])
        if article_claims:
            article_section += "VERIFIED CLAIMS:\n"
            for cl in article_claims[:3]:
                status = cl.get("verification_status", "unverified")
                conf = cl.get("confidence_score") or 0
                article_section += f"  - [{status}] ({conf:.0%}) {cl.get('claim_text', '')[:150]}\n"

        # If article failed analysis, note why
        if r.get("claims_status") == "failed":
            err = r.get("claims_error_message") or "Unknown error"
            article_section += f"NOTE: Analysis failed - {err[:200]}\n"

        parts.append(article_section)

    return "\n---\n".join(parts)


_METRICS_CACHE: dict = {"value": None, "ts": 0.0}


def _get_platform_metrics(db) -> dict:
    """Return live country/source counts (cached for 10 minutes)."""
    import time as _time

    now = _time.time()
    cached = _METRICS_CACHE.get("value")
    if cached and (now - _METRICS_CACHE.get("ts", 0)) < 600:
        return cached

    metrics = {"country_count": 0, "source_count": 0}
    try:
        country_rows = db.execute_query(
            "SELECT COUNT(DISTINCT country_code) AS c FROM articles "
            "WHERE country_code IS NOT NULL AND country_code <> ''"
        )
        if country_rows:
            metrics["country_count"] = int(country_rows[0].get("c") or 0)
    except Exception:
        pass

    try:
        source_rows = db.execute_query(
            "SELECT COUNT(DISTINCT source_name) AS c FROM articles "
            "WHERE source_name IS NOT NULL AND source_name <> ''"
        )
        if source_rows:
            metrics["source_count"] = int(source_rows[0].get("c") or 0)
    except Exception:
        pass

    _METRICS_CACHE["value"] = metrics
    _METRICS_CACHE["ts"] = now
    return metrics


def _get_session_history(db, session_id: str, limit: int = 5) -> List[dict]:
    """Get recent messages from a session for multi-turn context."""
    try:
        rows = db.execute_query(
            """SELECT role, content FROM chat_messages
               WHERE session_id = :sid
               ORDER BY created_at DESC LIMIT :limit""",
            {"sid": session_id, "limit": limit},
        )
        return list(reversed(rows or []))
    except Exception:
        return []


def _hydrate_view_context(db, view_context: Optional[dict]) -> dict:
    """Resolve the client-supplied view context into a richer server-side dict.

    Adds article body / country aggregates / URL-analysis row / source profile
    so the chat system prompt can reference real platform state. Each lookup
    is best-effort; failures degrade silently because chat still works without
    grounding.
    """
    if not view_context or not isinstance(view_context, dict):
        return {}

    hydrated: dict = {}
    raw_route = view_context.get("route")
    if isinstance(raw_route, str):
        hydrated["route"] = raw_route[:120]
    if isinstance(view_context.get("label"), str):
        hydrated["label"] = view_context["label"][:200]

    # Article currently being read
    article_id = view_context.get("article_id")
    if isinstance(article_id, str) and article_id and article_id != "new":
        try:
            rows = db.execute_query(
                """SELECT article_id, title, source_name, country_code,
                          overall_credibility, content_category, claims_status,
                          COALESCE(insight_summary, '') AS insight_summary,
                          SUBSTRING(COALESCE(extracted_text, excerpt, '') FROM 1 FOR 1500) AS body_preview
                   FROM articles WHERE article_id = :id LIMIT 1""",
                {"id": article_id},
            )
            if rows:
                row = rows[0]
                hydrated["article"] = {
                    "article_id": str(row["article_id"]),
                    "title": row.get("title") or "",
                    "source_name": row.get("source_name") or "",
                    "country_code": row.get("country_code"),
                    "credibility": row.get("overall_credibility"),
                    "category": row.get("content_category"),
                    "claims_status": row.get("claims_status"),
                    "insight": row.get("insight_summary") or "",
                    "body_preview": row.get("body_preview") or "",
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"view_context article lookup failed: {exc}")

    # Country focus (selected on map / passed via filter)
    country_code = view_context.get("country")
    if isinstance(country_code, str) and len(country_code) in (2, 3):
        cc = country_code.upper()
        hydrated["country_code"] = cc
        try:
            rows = db.execute_query(
                """SELECT country_code,
                          COUNT(*) AS article_count,
                          COUNT(DISTINCT source_name) AS source_count,
                          COUNT(*) FILTER (WHERE overall_credibility='HIGH') AS high_cred_articles,
                          MAX(published_date) AS latest_published
                   FROM articles
                   WHERE country_code = :cc
                   GROUP BY country_code""",
                {"cc": cc},
            )
            stats = rows[0] if rows else None
            if stats:
                hydrated["country_stats"] = {
                    "country_code": cc,
                    "article_count": int(stats.get("article_count") or 0),
                    "source_count": int(stats.get("source_count") or 0),
                    "high_credibility_articles": int(stats.get("high_cred_articles") or 0),
                    "latest_published": (
                        str(stats["latest_published"]) if stats.get("latest_published") else None
                    ),
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"view_context country lookup failed: {exc}")

    # Compare countries (map compare overlay or deep-search compare)
    compare_countries = view_context.get("compare_countries")
    if isinstance(compare_countries, list):
        cleaned = [
            str(c).upper() for c in compare_countries
            if isinstance(c, str) and len(c) in (2, 3)
        ][:4]
        if cleaned:
            hydrated["compare_countries"] = cleaned

    # URL analysis result currently displayed
    analysis_id = view_context.get("analysis_id")
    if isinstance(analysis_id, str) and analysis_id:
        try:
            rows = db.execute_query(
                """SELECT analysis_id, submitted_url, source_name, source_domain,
                          title, status, reliability_score, overall_credibility,
                          extracted_claims
                   FROM url_analyses WHERE analysis_id = :id LIMIT 1""",
                {"id": analysis_id},
            )
            if rows:
                row = rows[0]
                claims_payload = row.get("extracted_claims") or []
                if isinstance(claims_payload, str):
                    try:
                        claims_payload = json.loads(claims_payload)
                    except Exception:  # noqa: BLE001
                        claims_payload = []
                hydrated["url_analysis"] = {
                    "analysis_id": str(row["analysis_id"]),
                    "submitted_url": row.get("submitted_url"),
                    "source_name": row.get("source_name"),
                    "source_domain": row.get("source_domain"),
                    "title": row.get("title"),
                    "status": row.get("status"),
                    "reliability_score": row.get("reliability_score"),
                    "credibility": row.get("overall_credibility"),
                    "claims": (claims_payload or [])[:5] if isinstance(claims_payload, list) else [],
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"view_context url_analysis lookup failed: {exc}")

    # Deep search query / compare topics — these are short strings only; we
    # forward them so the LLM can reference them without re-asking the user.
    if isinstance(view_context.get("deep_search_query"), str):
        hydrated["deep_search_query"] = view_context["deep_search_query"][:300]
    if isinstance(view_context.get("deep_search_compare"), dict):
        cmp = view_context["deep_search_compare"]
        if isinstance(cmp.get("query_a"), str) and isinstance(cmp.get("query_b"), str):
            hydrated["deep_search_compare"] = {
                "query_a": cmp["query_a"][:200],
                "query_b": cmp["query_b"][:200],
            }

    # Source page focus (e.g. user is on /sources/<id>)
    source_id = view_context.get("source_id")
    if isinstance(source_id, str) and source_id:
        try:
            rows = db.execute_query(
                """SELECT source_name, COUNT(*) AS article_count,
                          COUNT(DISTINCT country_code) AS country_count,
                          AVG(reliability_score) AS avg_reliability
                   FROM articles WHERE source_name = :name
                   GROUP BY source_name LIMIT 1""",
                {"name": source_id},
            )
            if rows:
                row = rows[0]
                hydrated["source_focus"] = {
                    "source_name": row.get("source_name"),
                    "article_count": int(row.get("article_count") or 0),
                    "country_count": int(row.get("country_count") or 0),
                    "avg_reliability": (
                        round(float(row["avg_reliability"]), 1)
                        if row.get("avg_reliability") is not None else None
                    ),
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"view_context source lookup failed: {exc}")

    return hydrated


def _format_view_context_block(view: dict) -> str:
    """Render the hydrated view-context as plain text for the LLM prompt."""
    if not view:
        return ""

    parts: List[str] = []
    if view.get("route"):
        parts.append(f"- Route: {view['route']}")

    article = view.get("article")
    if article:
        cred = article.get("credibility") or "UNKNOWN"
        body = (article.get("body_preview") or "").strip().replace("\n", " ")
        if len(body) > 800:
            body = body[:800] + "…"
        parts.append(
            f"- Article being viewed: \"{article.get('title', 'Untitled')}\""
            f" (id={article.get('article_id')}, source={article.get('source_name', 'Unknown')},"
            f" credibility={cred}, country={article.get('country_code') or 'n/a'})"
        )
        if article.get("insight"):
            parts.append(f"  Insight: {article['insight'][:300]}")
        if body:
            parts.append(f"  Excerpt: {body}")

    if view.get("country_stats"):
        cs = view["country_stats"]
        parts.append(
            f"- Country focus: {cs.get('country_code')} —"
            f" {cs.get('article_count', 0)} articles from"
            f" {cs.get('source_count', 0)} sources;"
            f" {cs.get('high_credibility_articles', 0)} HIGH-credibility."
        )

    if view.get("compare_countries"):
        parts.append(f"- Comparing countries: {', '.join(view['compare_countries'])}")

    if view.get("url_analysis"):
        ua = view["url_analysis"]
        cred = ua.get("credibility") or "PENDING"
        rel = ua.get("reliability_score")
        rel_str = f"{rel}" if rel is not None else "n/a"
        parts.append(
            f"- URL analysis open: {ua.get('title') or ua.get('submitted_url')}"
            f" ({ua.get('source_domain') or ua.get('source_name') or 'unknown source'})"
            f" — credibility={cred}, reliability={rel_str}, status={ua.get('status')}."
        )
        claims = ua.get("claims") or []
        if claims:
            for c in claims[:3]:
                if isinstance(c, dict):
                    parts.append(f"  Claim: {str(c.get('claim_text') or c)[:200]}")

    if view.get("deep_search_query"):
        parts.append(f"- Deep-search query open: \"{view['deep_search_query']}\"")
    if view.get("deep_search_compare"):
        cmp = view["deep_search_compare"]
        parts.append(
            f"- Deep-search compare: A=\"{cmp.get('query_a', '')}\" vs B=\"{cmp.get('query_b', '')}\""
        )

    if view.get("source_focus"):
        sf = view["source_focus"]
        parts.append(
            f"- Source focus: {sf.get('source_name')} —"
            f" {sf.get('article_count', 0)} articles across"
            f" {sf.get('country_count', 0)} countries"
            + (f", avg reliability {sf.get('avg_reliability')}" if sf.get('avg_reliability') is not None else "")
            + "."
        )

    if view.get("label") and not parts:
        parts.append(f"- {view['label']}")

    return "\n".join(parts)


_CYNEFIN_GUIDANCE = {
    "direct_lookup": (
        "ANALYSIS DEPTH (Cynefin: clear/direct lookup):\n"
        "- The question is a factual lookup. Answer concisely with the specific "
        "fact and the citing article. Do not speculate or extrapolate. If the "
        "fact is not in the corpus above, say so and stop — do not pad."
    ),
    "multi_source_analysis": (
        "ANALYSIS DEPTH (Cynefin: complicated/multi-source):\n"
        "- Cross-reference at least two sources before stating a claim. "
        "Highlight where sources agree or disagree. Quote credibility ratings "
        "explicitly when sources disagree. Structure: claim → evidence chain → "
        "remaining uncertainty."
    ),
    "causal_analysis": (
        "ANALYSIS DEPTH (Cynefin: complex/causal):\n"
        "- Trace cause-and-effect chains rather than reporting correlations. "
        "Surface counterfactuals (\"if X had not happened\"), feedback loops, "
        "and emergent dynamics. Mark predictions with explicit confidence "
        "ranges and name the assumptions they rest on."
    ),
    "rapid_assessment": (
        "ANALYSIS DEPTH (Cynefin: chaotic/rapid assessment):\n"
        "- This is a fast-evolving situation. Lead with the single most "
        "actionable fact, then list what is unknown. Flag every uncertainty "
        "explicitly. Do not synthesise a tidy narrative — preserve ambiguity."
    ),
}


async def _generate_answer(
    question: str, context: str, sources: List[ChatSource], history: List[dict],
    platform_metrics: Optional[dict] = None,
    view_context: Optional[dict] = None,
    cynefin: Optional[dict] = None,
) -> dict:
    """Generate an answer using the LLM with article context."""
    try:
        from app.domains.intelligence.llm_client import get_llm_client
        client, model = get_llm_client()

        if not client:
            return {
                "answer": "Chat service unavailable: no LLM API key configured.",
                "confidence": 0.0,
                "error": "no_api_key",
            }

        # Build conversation history
        history_text = ""
        if history:
            turns = []
            for msg in history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:300]
                turns.append(f"{role.upper()}: {content}")
            if turns:
                history_text = "\nCONVERSATION HISTORY:\n" + "\n".join(turns) + "\n---\n"

        metrics = platform_metrics or {}
        country_count = metrics.get("country_count") or 0
        source_count = metrics.get("source_count") or 0
        country_phrase = (
            f"{country_count}+ countries" if country_count
            else "190+ tracked countries"
        )
        source_phrase = (
            f"{source_count} registered sources" if source_count
            else "a curated set of registered sources"
        )

        view_block = _format_view_context_block(view_context or {})
        view_section = (
            "\nCURRENT VIEW (what the user is looking at right now):\n"
            f"{view_block}\n"
            "When the user says \"this article\", \"this country\", \"these results\", "
            "\"the analysis\", \"compare them\", etc., resolve those pronouns against "
            "the CURRENT VIEW above first. If the view does not name what the user "
            "asked about, fall back to the article corpus below.\n"
            if view_block else ""
        )

        cynefin_strategy = (cynefin or {}).get("recommended_strategy")
        cynefin_section = (
            f"\n{_CYNEFIN_GUIDANCE[cynefin_strategy]}\n"
            if cynefin_strategy in _CYNEFIN_GUIDANCE else ""
        )

        system_prompt = (
            "You are Climatefacts.ai's climate intelligence assistant. You help users understand "
            "climate news, platform features, and analysis results.\n\n"
            f"{view_section}"
            f"{cynefin_section}"
            "CAPABILITIES:\n"
            "- Answer climate questions using article data provided below\n"
            "- Explain transparency scores, credibility ratings, and verification processes\n"
            "- Guide users through platform features (Map, Deep Search, Feed, Sources, Analysis)\n"
            "- Compare countries' climate coverage and risk profiles\n"
            "- Explain what different metrics mean (confidence intervals, reliability breakdown)\n\n"
            "PLATFORM FEATURES you can explain:\n"
            f"- **Climate Map**: Interactive map covering {country_phrase} with layers for "
            "article density, temperature anomaly, climate risk, and source diversity. Filters by date, "
            "source, category, region.\n"
            "- **Deep Search**: AI-powered research combining the internal corpus + Perplexity external sources. "
            "Compare mode for side-by-side topic analysis. Weather context is auto-injected for climate queries.\n"
            "- **My Feed**: Personalized feed with source type selection (news, weather, research, "
            "industry, policy, NGO). Configurable update frequency.\n"
            "- **Transparency Reports**: Full breakdown of article analysis — methodology, reliability, "
            "confidence intervals, evidence chains, source profiles.\n"
            "- **URL Analysis**: Submit any URL for AI fact-checking and claim extraction.\n"
            f"- **Sources**: {source_phrase} across categories (news, government, research, NGO, weather data, industry). "
            "Users can suggest new sources via /suggest-source.\n"
            "- **Green Transition**: Per-country scores across 7 dimensions (renewable energy, cleantech, "
            "circular economy, resource efficiency, regenerative economy, sustainability, overall transition).\n"
            "- **Translation**: Interface available in 11+ languages with auto-translation.\n\n"
            "RESPONSE STYLE: Be concise, use markdown, cite specific articles by name and credibility. "
            "When explaining features, be practical and give step-by-step guidance."
        )

        user_prompt = f"""RELEVANT ARTICLES FROM DATABASE:
{context}
{history_text}
USER QUESTION: {question}

Instructions:
- If the user asks about articles/news: answer using the article data above, cite sources by name and credibility.
- If the user asks about platform features: explain clearly with step-by-step guidance.
- If the user asks for analysis help: explain what the scores mean and how to interpret them.
- If the user asks to compare countries: use any country data from articles above.
- If no relevant articles are found, acknowledge this and suggest using Deep Search or adjusting filters.
- Format using markdown with headers, bullet points, and bold for key terms."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        answer = response.choices[0].message.content.strip()

        # Estimate confidence
        confidence = 0.5
        if sources:
            avg_relevance = sum(s.relevance for s in sources[:5]) / len(sources[:5])
            confidence = min(0.95, 0.4 + avg_relevance * 2)
            high_cred = sum(1 for s in sources[:5] if s.credibility == "HIGH")
            confidence = min(0.95, confidence + high_cred * 0.05)

        # Phase 6 wave 4: ground the synthesized answer against the article
        # excerpts that fed into it. Returns hallucination_risk +
        # flagged_segments so the UI can warn the user when the answer
        # isn't well-grounded. Best-effort — never blocks the response.
        hallucination_check: Optional[dict] = None
        try:
            if answer and sources:
                from app.domains.intelligence.hallucination_detector import (
                    HallucinationDetector,
                )
                # The detector's db parameter is vestigial (only used in
                # earlier prototypes); the check() method doesn't touch it.
                # Pass None to avoid threading another argument through.
                detector = HallucinationDetector(db=None)
                source_texts = []
                for s in sources[:5]:
                    chunk = f"{s.title or ''}".strip()
                    if chunk:
                        source_texts.append(chunk)
                if source_texts:
                    hallucination_check = await detector.check(
                        generated_text=answer[:4000],
                        source_texts=source_texts,
                    )
                    # Downgrade confidence when the grounding is weak.
                    risk = hallucination_check.get("hallucination_risk")
                    if isinstance(risk, (int, float)) and risk > 0.5:
                        confidence = max(0.1, confidence - 0.25)
        except Exception as _h_exc:
            logger.debug(f"Chat hallucination check failed (non-fatal): {_h_exc}")

        return {
            "answer": answer,
            "confidence": round(confidence, 2),
            "model": f"deepseek:{model}",
            "hallucination_check": hallucination_check,
        }

    except ImportError:
        return {
            "answer": "Chat engine dependencies not available.",
            "confidence": 0.0,
            "error": "import_error",
        }
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        return {
            "answer": f"An error occurred while generating the answer: {str(e)[:200]}",
            "confidence": 0.0,
            "error": str(e)[:200],
        }


def _store_chat_message(
    db, session_id: str, role: str, content: str,
    sources_used: Optional[List[str]] = None,
    article_ids: Optional[List[str]] = None,
    confidence: float = 0.0,
):
    """Store a message in the chat session."""
    try:
        db.execute_update(
            """INSERT INTO chat_messages (session_id, role, content, sources_used, article_ids, confidence)
               VALUES (:sid, :role, :content, :sources, :articles, :conf)""",
            {
                "sid": session_id,
                "role": role,
                "content": content,
                "sources": sources_used or [],
                "articles": article_ids or [],
                "conf": confidence,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to store chat message: {e}")
