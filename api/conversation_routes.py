"""
Article Conversation Routes

Provides Q&A endpoints for article-level conversations.
Tier-limited: free=2/article/day, basic=10, pro=unlimited.
Supports multi-turn conversational context.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import UsageTracker, TIER_LIMITS
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("conversation-api")
router = APIRouter(prefix="/api/articles", tags=["Conversations"])


# Tier-specific Q&A limits per article per day
QA_LIMITS = {
    "freemium": 2,
    "basic": 10,
    "professional": None,  # Unlimited
    "enterprise": None,
}


class AskQuestionRequest(BaseModel):
    """Request to ask a question about an article."""
    question: str = Field(..., min_length=5, max_length=500, description="Question about the article")
    conversation_context: Optional[List[dict]] = Field(
        default=None,
        description="Previous Q&A pairs for multi-turn context: [{question, answer}]"
    )


class ConversationEntry(BaseModel):
    """A single Q&A exchange."""
    conversation_id: Optional[str] = None
    question: str
    answer: str
    confidence: float = 0.0
    context_used: List[str] = []
    model: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None


class ConversationHistory(BaseModel):
    """Conversation history for an article."""
    article_id: str
    entries: List[ConversationEntry]
    total: int


@router.post("/{article_id}/ask", response_model=ConversationEntry)
async def ask_article_question(
    article_id: str,
    request: AskQuestionRequest,
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """
    Ask a question about an article.

    Uses the article's verified claims and evidence as grounded context.
    Only answers based on article content — no hallucination.

    Supports multi-turn conversation via `conversation_context` field
    which passes previous Q&A pairs for contextual follow-up questions.

    **Rate limits per article per day:**
    - Free: 2 questions
    - Basic: 10 questions
    - Professional/Enterprise: Unlimited
    """
    # Determine user tier and ID
    if current_user and isinstance(current_user, dict):
        user_tier = current_user.get("subscription_tier", "freemium")
        user_id = str(current_user.get("user_id", "anonymous"))
    else:
        user_tier = "freemium"
        user_id = "anonymous"

    # Check Q&A rate limit
    qa_limit = QA_LIMITS.get(user_tier)
    if qa_limit is not None:
        try:
            count = UsageTracker.get_usage_count(
                user_id=f"{user_id}:{article_id}",
                usage_type="article_qa",
                period="day",
            )
            if count >= qa_limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily Q&A limit reached for this article ({count}/{qa_limit}). Upgrade for more questions.",
                )
        except HTTPException:
            raise
        except Exception:
            pass  # Don't block on usage tracking failure

    # Log usage
    try:
        UsageTracker.log_usage(
            user_id=f"{user_id}:{article_id}",
            usage_type="article_qa",
            resource_id=article_id,
            metadata={"question": request.question[:100]},
        )
    except Exception:
        pass

    # Run conversation engine
    db = get_postgres()

    try:
        from app.domains.intelligence.conversation_engine import ConversationEngine
        engine = ConversationEngine(db)

        result = None
        # Run async function
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await loop.run_in_executor(
                        pool,
                        lambda: asyncio.run(engine.ask(
                            article_id=UUID(article_id),
                            question=request.question,
                            user_id=UUID(user_id) if user_id != "anonymous" else None,
                            conversation_context=request.conversation_context,
                        ))
                    )
            else:
                result = await engine.ask(
                    article_id=UUID(article_id),
                    question=request.question,
                    user_id=UUID(user_id) if user_id != "anonymous" else None,
                    conversation_context=request.conversation_context,
                )
        except RuntimeError:
            result = asyncio.run(engine.ask(
                article_id=UUID(article_id),
                question=request.question,
                user_id=UUID(user_id) if user_id != "anonymous" else None,
                conversation_context=request.conversation_context,
            ))

        if result is None:
            raise HTTPException(status_code=500, detail="Failed to generate answer")

        return ConversationEntry(
            conversation_id=result.get("conversation_id"),
            question=request.question,
            answer=result["answer"],
            confidence=result.get("confidence", 0.0),
            context_used=result.get("context_used", []),
            model=result.get("model"),
            error=result.get("error"),
        )

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=503, detail="Conversation engine not available")
    except Exception as e:
        logger.error(f"Q&A failed for article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")


@router.get("/{article_id}/conversations", response_model=ConversationHistory)
async def get_article_conversations(
    article_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[Any] = Depends(get_optional_user),
):
    """Get conversation history for an article."""
    db = get_postgres()

    try:
        rows = db.execute_query(
            """SELECT conversation_id, question, answer, confidence, created_at
               FROM article_conversations
               WHERE article_id = :id
               ORDER BY created_at DESC
               LIMIT :limit""",
            {"id": article_id, "limit": limit},
        )

        entries = [
            ConversationEntry(
                conversation_id=str(r.get("conversation_id", "")),
                question=r.get("question", ""),
                answer=r.get("answer", ""),
                confidence=r.get("confidence", 0.0),
                created_at=str(r["created_at"]) if r.get("created_at") else None,
            )
            for r in (rows or [])
        ]

        return ConversationHistory(
            article_id=article_id,
            entries=entries,
            total=len(entries),
        )
    except Exception as e:
        logger.error(f"Failed to fetch conversations for {article_id}: {e}")
        return ConversationHistory(article_id=article_id, entries=[], total=0)
