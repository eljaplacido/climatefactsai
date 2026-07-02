"""
General Climate Chat Routes

Provides a general-purpose chat interface for climate news questions
that searches across all articles and sources, not just a single article.
Users can ask broad questions and get insight-driven answers with citations.
"""

import json
from datetime import datetime
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import UsageTracker
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
    source_mode: Optional[str] = Field(
        "platform",
        description=(
            "Where the answer is grounded: 'platform' (ingested corpus only — "
            "default), 'web' (external web search via deep-search), or 'both' "
            "(corpus + web). web/both consume the deep_research quota."
        ),
    )


class ChatSource(BaseModel):
    article_id: str
    title: str
    source_name: str
    credibility: Optional[str] = None
    relevance: float = 0.0


class ChatActionSpec(BaseModel):
    type: str = Field(..., min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)
    label: str = Field(..., min_length=1, max_length=128)


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
    hallucination_check: Optional[dict] = None
    # Phase 8 agentic actions
    actions: Optional[List[ChatActionSpec]] = None


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

    # Source mode (user choice): platform corpus only (default), external web
    # search, or both. web/both route through DeepSearchService (Perplexity +
    # corpus synthesis) so the chat can ANSWER even when the corpus has no
    # matching articles — the long-standing "no articles to reference" dead end.
    source_mode = (request.source_mode or "platform").lower()
    if source_mode in ("web", "both"):
        web_resp = await _answer_via_deep_search(
            db, request.question, effective_country, request.category,
            user_id=user_id, user_tier=user_tier, source_mode=source_mode,
            session_id=session_id, mode=mode,
        )
        if web_resp is not None:
            _store_chat_message(db, session_id, "user", request.question)
            _store_chat_message(
                db, session_id, "assistant", web_resp.answer,
                sources_used=[s.source_name for s in web_resp.sources[:5]],
                article_ids=[s.article_id for s in web_resp.sources[:5] if s.article_id],
                confidence=web_resp.confidence,
            )
            try:
                UsageTracker.log_usage(
                    user_id=user_id, usage_type="general_chat",
                    metadata={"question": request.question[:100], "session_id": session_id,
                              "mode": mode, "source_mode": source_mode},
                )
            except Exception:
                pass
            return web_resp
        # web_resp is None → external path unavailable; fall through to platform.

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

    # 2026-05-28 hotfix: this `return ChatResponse(...)` was previously
    # indented inside the `except: pass` block above — so on the happy
    # path (UsageTracker.log_usage succeeds, no exception), the function
    # fell through to implicit `return None` and FastAPI 500'd trying
    # to validate None against ChatResponse. Dedented to function level.
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
        actions=answer_data.get("actions") or [],
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

    # Ownership guard (audit API-07 — IDOR): never return another authenticated
    # user's session history. Anonymous sessions (user_id NULL) have no owner to
    # protect and are keyed by an unguessable UUID, so they stay readable.
    sess = db.execute_query(
        "SELECT user_id FROM chat_sessions WHERE session_id = :sid LIMIT 1",
        {"sid": session_id},
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    owner_id = sess[0].get("user_id")
    if owner_id is not None:
        requester = str(current_user.get("user_id")) if current_user else None
        if requester != str(owner_id):
            raise HTTPException(status_code=404, detail="Session not found")

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

async def _answer_via_deep_search(
    db,
    question: str,
    country: Optional[str],
    category: Optional[str],
    *,
    user_id: str,
    user_tier: str,
    source_mode: str,
    session_id: str,
    mode: str,
) -> Optional["ChatResponse"]:
    """Answer a chat question through DeepSearchService (corpus + external web).

    Returns a ChatResponse on success, or None to signal the caller to fall
    back to the platform-only path (external provider unavailable / produced no
    answer). Quota exhaustion is raised (429) so the user sees the upgrade hint
    instead of a silent fallback.
    """
    # web/both make a paid external call → gate behind the deep_research quota.
    # Professional/Enterprise are unlimited; anonymous/free get the upgrade hint.
    try:
        from api.quota_service import QuotaService
        QuotaService.check_and_raise(
            user_id=str(user_id) if user_id and user_id != "anonymous" else None,
            tier=user_tier,
            quota_key="deep_research",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.debug(f"deep_research quota check skipped (non-fatal): {exc}")

    try:
        from app.domains.intelligence.deep_search_service import DeepSearchService
        service = DeepSearchService(db)
        result = await service.search(
            query=question,
            country=country,
            category=category,
            include_weather=False,
            limit=10,
            include_hallucination_check=False,
            include_refinements=False,
            platform_only=False,  # web/both → external enrichment allowed
        )
    except Exception as exc:
        logger.warning(f"chat web-mode deep search failed; falling back to platform: {exc}")
        return None

    answer = (result or {}).get("answer") or ""
    if not answer:
        return None

    citations = (result or {}).get("citations") or []
    sources: List[ChatSource] = []
    web_urls: List[str] = []
    for c in citations:
        if c.get("type") == "internal_article" and c.get("article_id"):
            sources.append(ChatSource(
                article_id=str(c.get("article_id")),
                title=c.get("title", ""),
                source_name=c.get("source_name", ""),
                credibility=c.get("credibility"),
                relevance=float(c.get("relevance_score") or 0),
            ))
        elif c.get("type") == "external_web" and c.get("source_url"):
            web_urls.append(c["source_url"])

    # External web sources have no article page to link to via ChatSource, so
    # surface them as a clickable footnote in the answer markdown.
    if web_urls:
        seen: set[str] = set()
        uniq = [u for u in web_urls if not (u in seen or seen.add(u))][:6]
        answer = answer.rstrip() + "\n\n**Web sources:**\n" + "\n".join(f"- {u}" for u in uniq)

    internal_n = int((result or {}).get("internal_articles_count") or 0)
    external_n = int((result or {}).get("external_sources_count") or 0)
    confidence = round(min(0.9, 0.3 + 0.1 * (internal_n + external_n)), 2)
    synth_model = ((result or {}).get("methodology") or {}).get("synthesis_model")

    return ChatResponse(
        session_id=session_id,
        question=question,
        answer=answer,
        sources=sources[:5],
        confidence=confidence,
        model=synth_model,
        created_at=datetime.utcnow().isoformat(),
        mode=mode,
    )


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
              AND country_code IS NOT NULL
              AND is_synthetic = FALSE""",
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
                       a.search_tsv,
                       websearch_to_tsquery('english', :q)
                   ) AS relevance
            FROM articles a
            WHERE a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
              AND a.search_tsv
                  @@ websearch_to_tsquery('english', :q)
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
                    WHERE a.is_synthetic = FALSE AND a.is_off_topic = FALSE AND ({ilike_parts})
                    ORDER BY a.published_date DESC NULLS LAST LIMIT :limit""",
                ilike_params,
            )

    if not rows:
        # Fallback 3: recent articles
        rows = db.execute_query(
            f"""SELECT a.article_id, a.title, a.source_name, a.overall_credibility,
                       0.1 AS relevance
                FROM articles a
                WHERE a.is_synthetic = FALSE AND a.is_off_topic = FALSE AND a.claims_status = 'completed'
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
            WHERE a.article_id IN ({placeholders})
              AND a.is_synthetic = FALSE""",
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

    items = []
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

        items.append({"section": article_section, "cred": (cred or "UNKNOWN").upper()})

    # IntelligentContext budget-fit (Headroom): under a tight token budget keep
    # the most credible articles first, then restore original order for the
    # prompt. Bounds the per-turn context cost on claim-heavy questions.
    from app.domains.intelligence.context_compaction import (
        fit_to_budget, CHAT_CONTEXT_TOKEN_BUDGET,
    )
    _cred_rank = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "UNKNOWN": 0.5}
    fit = fit_to_budget(
        items,
        CHAT_CONTEXT_TOKEN_BUDGET,
        render=lambda it: it["section"],
        score=lambda it: _cred_rank.get(it["cred"], 0.5),
        separator="\n---\n",
    )
    return fit["rendered"] or "No relevant articles found in the database."


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
            "WHERE country_code IS NOT NULL AND country_code <> '' AND is_synthetic = FALSE"
        )
        if country_rows:
            metrics["country_count"] = int(country_rows[0].get("c") or 0)
    except Exception:
        pass

    try:
        source_rows = db.execute_query(
            "SELECT COUNT(DISTINCT source_name) AS c FROM articles "
            "WHERE source_name IS NOT NULL AND source_name <> '' AND is_synthetic = FALSE"
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
                   FROM articles WHERE article_id = :id AND is_synthetic = FALSE LIMIT 1""",
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
        except Exception as exc:
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
                   WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
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
        except Exception as exc:
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
                    except Exception:
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
        except Exception as exc:
            logger.debug(f"view_context url_analysis lookup failed: {exc}")

    # Deep search query / compare topics — these are short strings only; we
    # forward them so the LLM can reference them without re-asking the user.
    if isinstance(view_context.get("deep_search_query"), str):
        hydrated["deep_search_query"] = view_context["deep_search_query"][:300]
        try:
            ds_rows = db.execute_query(
                """SELECT COUNT(*) AS total,
                          COUNT(*) FILTER (WHERE overall_credibility = 'HIGH') AS high_cred,
                          COUNT(DISTINCT source_name) AS source_count
                   FROM articles
                   WHERE search_tsv @@ websearch_to_tsquery('english', :q)
                     AND is_synthetic = FALSE AND is_off_topic = FALSE""",
                {"q": hydrated["deep_search_query"]},
            )
            if ds_rows:
                ds = ds_rows[0]
                hydrated["deep_search_context_stats"] = {
                    "internal_hits": int(ds.get("total") or 0),
                    "high_credibility_hits": int(ds.get("high_cred") or 0),
                    "distinct_sources": int(ds.get("source_count") or 0),
                }
        except Exception as exc:
            logger.debug(f"view_context deep_search_query stats lookup failed: {exc}")
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
                   FROM articles WHERE source_name = :name AND is_synthetic = FALSE AND is_off_topic = FALSE
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
        except Exception as exc:
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
        stats = view.get("deep_search_context_stats") or {}
        stats_suffix = ""
        if stats:
            stats_suffix = (
                f" (internal hits: {stats.get('internal_hits', 0)}, "
                f"high-credibility: {stats.get('high_credibility_hits', 0)}, "
                f"sources: {stats.get('distinct_sources', 0)})"
            )
        parts.append(f"- Deep-search query open: \"{view['deep_search_query']}\"{stats_suffix}")
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


_CHAT_SYSTEM_PROMPT_CACHE: Optional[str] = None


def _chat_system_prompt() -> str:
    """Static system prompt for the agentic chat (Headroom CacheAligner).

    Built once and cached so the large prefix — identity, capabilities, the
    generic feature catalogue, and the full action catalogue — is byte-identical
    on every turn, making it eligible for provider-side prompt/KV-cache reuse.
    All volatile content (live counts, current view, retrieved articles, history,
    the question) lives in the USER message instead.

    Audit INT-05: the ~2 KB action block previously sat at the END of the user
    prompt, after the volatile context — defeating any prefix cache and forcing
    the whole catalogue to be re-tokenized on every single turn.
    """
    global _CHAT_SYSTEM_PROMPT_CACHE
    if _CHAT_SYSTEM_PROMPT_CACHE is not None:
        return _CHAT_SYSTEM_PROMPT_CACHE

    base = (
        "You are Climatefacts.ai's climate intelligence assistant. You help users understand "
        "climate news, platform features, and analysis results.\n\n"
        "CAPABILITIES:\n"
        "- Answer climate questions using the article data provided in the user message\n"
        "- Explain transparency scores, credibility ratings, and verification processes\n"
        "- Guide users through platform features (Map, Deep Search, Feed, Sources, Analysis)\n"
        "- Compare countries' climate coverage and risk profiles\n"
        "- Explain what different metrics mean (confidence intervals, reliability breakdown)\n\n"
        "PLATFORM FEATURES you can explain:\n"
        "- **Climate Map**: Interactive map covering 190+ tracked countries with layers for "
        "article density, temperature anomaly, climate risk, and source diversity. Filters by date, "
        "source, category, region.\n"
        "- **Deep Search**: AI-powered research combining the internal corpus + Perplexity external sources. "
        "Compare mode for side-by-side topic analysis. Weather context is auto-injected for climate queries.\n"
        "- **My Feed**: Personalized feed with source type selection (news, weather, research, "
        "industry, policy, NGO). Configurable update frequency.\n"
        "- **Transparency Reports**: Full breakdown of article analysis — methodology, reliability, "
        "confidence intervals, evidence chains, source profiles.\n"
        "- **URL Analysis**: Submit any URL for AI fact-checking and claim extraction.\n"
        "- **Sources**: A curated set of registered sources across categories (news, government, research, "
        "NGO, weather data, industry). Users can suggest new sources via /suggest-source.\n"
        "- **Green Transition**: Per-country scores across 7 dimensions (renewable energy, cleantech, "
        "circular economy, resource efficiency, regenerative economy, sustainability, overall transition).\n"
        "- **Translation**: Interface available in 11+ languages with auto-translation.\n\n"
        "RESPONSE STYLE: Be concise, use markdown, cite specific articles by name and credibility. "
        "When explaining features, be practical and give step-by-step guidance. Live platform counts, "
        "the user's current view, and retrieved articles are supplied in the user message."
    )

    # ML-07: methodology-honesty guardrail. The heavy generic feature catalogue
    # above says nothing about HOW each score/layer is derived, so the model used
    # to confabulate (e.g. describing the map's Climate Risk layer as a
    # hazard/vulnerability/adaptive-capacity/GDP composite). The always-current,
    # per-score/per-layer basis is injected into the VOLATILE user message as a
    # METHODOLOGY DIGEST; this static instruction tells the model to trust ONLY
    # that digest and never invent factors.
    base += (
        "\n\nMETHODOLOGY HONESTY (critical): When a user asks how a score, rating, "
        "credibility tier, or map layer is calculated, state ONLY the documented "
        "basis given in the METHODOLOGY DIGEST supplied in the user message. NEVER "
        "invent or guess contributing factors. Concretely, the map's Climate Risk "
        "layer is purely IPCC AR6 SSP2-4.5 projected 2050 warming scaled to 0-10 — "
        "it is NOT a hazard/exposure/vulnerability/sensitivity/adaptive-capacity "
        "composite and does NOT use GDP, disaster records, or article volume. If "
        "the digest does not document the basis, say so plainly and offer the "
        "open_methodology_section action instead of fabricating a methodology."
    )

    try:
        from app.domains.intelligence.skills import render_actions_block_for_prompt
        base += (
            "\n\nAFTER your markdown answer, you MAY append a JSON actions block "
            "suggesting 0-3 genuinely useful next steps for the user. Separate it "
            "from your answer with a line containing only '---'. Omit the block "
            "entirely if no action is genuinely helpful.\n"
            "AVAILABLE ACTIONS (use ONLY these `type` values):\n"
            f"{render_actions_block_for_prompt()}\n"
            "Each action is {\"type\": <one above>, \"params\": {..}, \"label\": "
            "\"short button text\"}. Example:\n"
            "Your answer text…\n"
            "---\n"
            "{\"actions\":[{\"type\":\"open_country\",\"params\":{\"code\":\"DE\"},"
            "\"label\":\"Open Germany on the map\"}]}"
        )
    except Exception as _act_exc:  # pragma: no cover - registry import guard
        logger.debug(f"actions block unavailable (non-fatal): {_act_exc}")

    _CHAT_SYSTEM_PROMPT_CACHE = base
    return _CHAT_SYSTEM_PROMPT_CACHE


_METHODOLOGY_DIGEST_CACHE: Optional[str] = None


def _methodology_digest() -> str:
    """Machine-generated, always-current methodology digest (audit ML-07).

    Per-map-layer and per-score basis, sourced from the AUTHORITATIVE backend
    constants (the warming-risk math in ``api.map.services`` and the canonical
    credibility thresholds) so it can never drift from the live scoring code.

    This is injected into the VOLATILE user block — never the cached system
    prefix — so it stays current turn-over-turn while the cache-eligible system
    prefix stays byte-frozen (Headroom CacheAligner, INT-05). It gives the model
    the ONE documented basis for each score/layer so it stops confabulating
    (e.g. describing Climate Risk as a hazard/vulnerability/GDP composite).
    """
    global _METHODOLOGY_DIGEST_CACHE
    if _METHODOLOGY_DIGEST_CACHE is not None:
        return _METHODOLOGY_DIGEST_CACHE

    # Climate Risk basis — sourced from the live warming-risk constants so the
    # exact scenario/horizon/scaling can never disagree with the choropleth.
    try:
        from api.map.services import (
            WARMING_RISK_SCENARIO,
            WARMING_RISK_HORIZON_YEAR,
            WARMING_RISK_FLOOR_C,
            WARMING_RISK_CEILING_C,
        )
        climate_risk = (
            f"projected physical warming ONLY — IPCC AR6 {WARMING_RISK_SCENARIO} at "
            f"{WARMING_RISK_HORIZON_YEAR}, linearly scaled {WARMING_RISK_FLOOR_C}°C→0 "
            f"and {WARMING_RISK_CEILING_C}°C→10. It is NOT a hazard/exposure/"
            f"vulnerability/sensitivity/adaptive-capacity composite, NOT GDP, NOT disaster "
            f"records, NOT article volume. Countries with no AR6 projection show as grey (no data)."
        )
    except Exception:  # pragma: no cover - defensive import guard
        climate_risk = (
            "projected physical warming (IPCC AR6 SSP2-4.5 at 2050) scaled to 0-10. "
            "NOT a vulnerability/GDP composite; NOT article volume."
        )

    # Article reliability level crosswalk — canonical thresholds.
    try:
        from shared.credibility_thresholds import HIGH, MEDIUM
        rel_levels = f"HIGH ≥ {HIGH}, MEDIUM {MEDIUM}–{HIGH - 1}, LOW < {MEDIUM}"
    except Exception:  # pragma: no cover
        rel_levels = "HIGH ≥ 80, MEDIUM 50–79, LOW < 50"

    lines = [
        "MAP LAYERS — documented basis of each (state ONLY these):",
        f"- Climate Risk: {climate_risk}",
        "- Temperature Anomaly: current temperature vs the same month last year (Open-Meteo). "
        "Not a 30-year climatological baseline.",
        "- Warming Outlook: CMIP6 multi-model median warming under SSP2-4.5 at the chosen "
        "horizon (IPCC AR6 Interactive Atlas).",
        "- Article Density: count of indexed climate articles per country. A coverage metric, "
        "not risk and not quality.",
        "- Source Diversity: count of DISTINCT sources covering a country (by source name). "
        "Not a quality score.",
        "- News Events: 21-day rolling article volume + disputed-claim ratio, time-decayed. "
        "Not a live breaking-news feed.",
        "- NDC Targets: Climate Watch UNFCCC NDC registry + Climate Action Tracker rating where "
        "available. The reduction % is a heterogeneous ambition proxy, not directly comparable.",
        "- Adaptation Gap: inverted ND-GAIN country index (a proxy). Not actual finance-flow data.",
        "- Corporate Density: companies with climate disclosures by registered HQ "
        "(CDP / SBTi / Net Zero Tracker).",
        "- Biomes & Climate: Köppen-Geiger climate classification (Beck et al. 2018).",
        "",
        "SCORES & RATINGS — documented basis of each (state ONLY these):",
        f"- Article reliability score (0-100): composite of source credibility (~50%), verified-"
        f"claim support, and content relevance. Levels: {rel_levels}. Zero verified claims cannot "
        f"exceed MEDIUM.",
        "- Source ratings / credibility tiers: platform RELIABILITY tiers — T1 (Scimago Q1 journal "
        "or IFCN-verified fact-checker), T2 (mainstream press with a corrections policy or Q2 "
        "journal), T3 (research NGO / intergovernmental body), unknown, retracted. These are "
        "reliability tiers, NOT political lean and NOT sentiment.",
        "- Green Transition / sustainability score (0-100): weighted sum of normalized country "
        "indicators (weights of missing indicators redistribute); the confidence band widens with "
        "fewer indicators.",
        "- Calibrated confidence (0-1): optional Platt-scaled recalibration, applied only when a "
        "stable fit exists.",
    ]

    _METHODOLOGY_DIGEST_CACHE = "\n".join(lines)
    return _METHODOLOGY_DIGEST_CACHE


# ML-07 eval/guard: factors that must NEVER be attributed to the map's Climate
# Risk layer (it is purely SSP2-4.5 projected 2050 warming). Used by the
# regression test in tests/unit/api/test_chat_methodology_digest.py.
_CLIMATE_RISK_CONFAB_TERMS = (
    "vulnerability",
    "sensitivity",
    "adaptive capacity",
    "adaptive-capacity",
    "gdp",
    "disaster record",
    "socioeconomic",
)
_CONFAB_NEGATIONS = ("not ", "n't", "never", "no longer", "rather than", "instead of")


def flag_climate_risk_confabulation(answer: str) -> List[str]:
    """Return forbidden factors an answer wrongly attributes to Climate Risk.

    The map's Climate Risk layer is purely IPCC AR6 SSP2-4.5 projected 2050
    warming. An *explanation* of it that invokes vulnerability / sensitivity /
    adaptive-capacity / GDP / disaster records is a confabulation (ML-07).

    Heuristic guard for evals/regression tests — it only inspects text that is
    actually describing climate risk, and it skips a term when the sentence
    asserting it carries a negation ("it is NOT a vulnerability/GDP composite")
    so the model correctly *disclaiming* those factors is not itself flagged.
    """
    if not answer:
        return []
    low = answer.lower()
    if "climate risk" not in low and "climate-risk" not in low:
        return []
    hits: List[str] = []
    for term in _CLIMATE_RISK_CONFAB_TERMS:
        idx = low.find(term)
        if idx == -1:
            continue
        # Bound the sentence/clause around the first occurrence.
        start = max(low.rfind(".", 0, idx), low.rfind("\n", 0, idx)) + 1
        ends = [e for e in (low.find(".", idx), low.find("\n", idx)) if e != -1]
        end = (min(ends) + 1) if ends else len(low)
        sentence = low[start:end]
        if any(neg in sentence for neg in _CONFAB_NEGATIONS):
            continue
        hits.append(term)
    return hits


async def _generate_answer(
    question: str, context: str, sources: List[ChatSource], history: List[dict],
    platform_metrics: Optional[dict] = None,
    view_context: Optional[dict] = None,
    cynefin: Optional[dict] = None,
) -> dict:
    """Generate an answer using the LLM with article context.

    2026-05-28 refactor: was DeepSeek-only — if DeepSeek hiccupped, chat
    500'd. Now uses llm_chat_with_fallback which walks
    deepseek -> openai -> anthropic -> local-gx10 until one succeeds.
    The returned `model` field tells the UI which provider actually
    produced the answer so observability stays honest.
    """
    try:
        from app.domains.intelligence.llm_client import llm_chat_with_fallback

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

        # CacheAligner (Headroom, audit INT-05): the heavy, invariant blocks
        # (identity, capabilities, feature + action catalogues) live in a static
        # system prefix; everything volatile goes in the user message below, so
        # the prefix stays cache-eligible turn over turn.
        from app.domains.intelligence.context_compaction import (
            compact_text, guard_input, CHAT_CONTEXT_TOKEN_BUDGET,
        )
        system_prompt = _chat_system_prompt()

        snapshot_bits = []
        if country_count:
            snapshot_bits.append(f"{country_count}+ countries tracked")
        if source_count:
            snapshot_bits.append(f"{source_count} registered sources")
        snapshot = (
            "PLATFORM SNAPSHOT: " + "; ".join(snapshot_bits) + ".\n\n"
            if snapshot_bits else ""
        )

        # ML-07: always-current per-layer/per-score methodology digest, injected
        # into the VOLATILE user block (keeps the cached system prefix frozen).
        methodology_section = (
            "\nMETHODOLOGY DIGEST (authoritative — when explaining how any score, "
            "rating, tier, or map layer is derived, state ONLY the basis below and "
            "never invent contributing factors):\n"
            f"{_methodology_digest()}\n"
        )

        user_prompt = (
            f"{snapshot}"
            f"{view_section}"
            f"{cynefin_section}"
            f"{methodology_section}"
            "RELEVANT ARTICLES FROM DATABASE:\n"
            f"{compact_text(context, CHAT_CONTEXT_TOKEN_BUDGET)}\n"
            f"{history_text}\n"
            f"USER QUESTION: {question}\n\n"
            "Instructions:\n"
            "- If the user asks about articles/news: answer using the article data above, cite sources by name and credibility.\n"
            "- If the user asks about platform features: explain clearly with step-by-step guidance.\n"
            "- If the user asks for analysis help: explain what the scores mean and how to interpret them.\n"
            "- When explaining how a score/rating/tier/map layer is computed, use ONLY the METHODOLOGY DIGEST above; if it is not documented there, say so and offer the open_methodology_section action — do NOT invent factors.\n"
            "- If the user asks to compare countries: use any country data from articles above.\n"
            "- If no relevant articles are found, acknowledge this and suggest using Deep Search or adjusting filters.\n"
            "- Format using markdown with headers, bullet points, and bold for key terms."
        )

        # Safety net: never ship a pathologically large user prompt (runaway
        # history / view payload) to a provider — trim the middle to the ceiling.
        user_prompt = guard_input(user_prompt)

        # Multi-provider fallback chain: tries deepseek -> openai -> anthropic
        # -> local-gx10 until one returns non-empty content. Returns None
        # only when EVERY provider fails (effectively the same as the old
        # "no API key" guard).
        chain_result = llm_chat_with_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1000,
            temperature=0.3,
        )

        if chain_result is None:
            return {
                "answer": (
                    "Chat service is temporarily unavailable — all LLM "
                    "providers in the fallback chain (DeepSeek, OpenAI, "
                    "Anthropic, GX10) are unreachable or returned empty. "
                    "Please retry in a moment."
                ),
                "confidence": 0.0,
                "error": "all_providers_failed",
            }

        answer, used_provider, used_model = chain_result
        answer = answer.strip()

        # Split the optional trailing JSON actions block from the display text
        # so the raw JSON contract never renders in the chat bubble. Actions
        # parse from after the last '---'; only strip when they actually parse.
        actions = _parse_actions(answer)
        if actions:
            _cut = answer.rfind("---")
            if _cut != -1:
                answer = answer[:_cut].rstrip()

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
                # Ground against the article BODIES that fed the answer, not
                # just titles — titles alone made the entity/number overlap
                # check near-useless (audit INT-04). `context` is already
                # length-bounded by _build_multi_article_context.
                if context and context.strip() and "No relevant articles" not in context:
                    source_texts.append(context[:6000])
                for s in sources[:5]:
                    if s.title:
                        source_texts.append(s.title)
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
            # 2026-05-28: stamp provider:model so the UI can tell which
            # backend actually answered (used vs fell-back). Was hard-
            # coded "deepseek:{model}" even when the call used something
            # else — making the displayed model label dishonest.
            "model": f"{used_provider}:{used_model}",
            "hallucination_check": hallucination_check,
            "actions": actions,
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


# Derive the validator from the single source of truth (skills.py registry) so
# it can never lag the 22-skill set again — the old 9-item hardcode silently
# dropped 13 of the registry's actions (open_company, verify_corporate_claim,
# explore_scenario, explore_entity, flag_off_topic, …) before the LLM could
# surface them. Falls back to the legacy 9 if the registry import is unavailable.
try:
    from app.domains.intelligence.skills import SKILLS_REGISTRY as _SKILLS_REGISTRY
    VALID_ACTION_TYPES = frozenset(_SKILLS_REGISTRY.keys())
except Exception:  # pragma: no cover - registry should always import
    VALID_ACTION_TYPES = frozenset({
        "navigate", "analyze_url", "apply_search_filters",
        "apply_map_filters", "open_methodology_section",
        "open_country", "start_deep_search",
        "bookmark_article", "start_calibration_label",
    })


def _parse_actions(answer: str) -> list[dict]:
    """Extract action suggestions from the LLM answer.

    Delegates to the centralized ``chat_actions.parse_actions()`` which
    handles JSON parsing, validation against SKILLS_REGISTRY, capping at 5,
    and error handling.
    """
    from app.domains.intelligence.chat_actions import parse_actions
    return parse_actions(answer)


@router.post("/actions/click")
async def record_action_click(action: ChatActionSpec):
    """Record that a user clicked a suggested chat action (telemetry)."""
    db = get_postgres()
    try:
        # Postgres does not allow ORDER BY / LIMIT directly on UPDATE, so the
        # old query raised a syntax error every click and the telemetry was
        # silently lost (caught below). Target the single most-recent matching
        # row via a ctid subselect (PK-agnostic).
        db.execute_update(
            """UPDATE chat_actions_log
               SET was_clicked = TRUE, clicked_at = NOW()
               WHERE ctid = (
                   SELECT ctid FROM chat_actions_log
                   WHERE action_type = :atype
                     AND params = CAST(:params AS jsonb)
                     AND was_clicked = FALSE
                     AND suggested_at > NOW() - INTERVAL '1 hour'
                   ORDER BY suggested_at DESC
                   LIMIT 1
               )""",
            {
                "atype": action.type,
                "params": json.dumps(action.params),
            },
        )
    except Exception as e:
        logger.debug(f"record_action_click failed (non-fatal): {e}")
    return {"status": "recorded"}
