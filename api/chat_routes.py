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

    # Use HybridRAGService for retrieval when available, fall back to FTS
    sources = await _hybrid_search_articles(
        db, request.question, request.country, request.category
    )
    if not sources:
        sources = _search_relevant_articles(
            db, request.question, request.country, request.category
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

    # Generate answer
    answer_data = await _generate_answer(
        request.question, context_text, sources, history
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
        # Fallback: recent articles if no full-text match
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


async def _generate_answer(
    question: str, context: str, sources: List[ChatSource], history: List[dict]
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

        system_prompt = (
            "You are CliLens.AI's climate intelligence assistant. You answer questions "
            "about climate news using ONLY the article data provided below. Cite specific "
            "articles and their credibility ratings. If articles have verified claims, "
            "reference them. If no relevant information is found, say so honestly. "
            "For failed analyses, explain what happened. Be concise and use markdown."
        )

        user_prompt = f"""RELEVANT ARTICLES:
{context}
{history_text}
USER QUESTION: {question}

Answer based on the articles above. Cite sources by name. If an article's analysis failed,
explain that the scoring is unavailable and why. Format using markdown."""

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

        return {
            "answer": answer,
            "confidence": round(confidence, 2),
            "model": f"deepseek:{model}",
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
