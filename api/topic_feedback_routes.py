"""Topic-feedback routes — Stage 3 / M4 (evolving validation corpus).

User-facing endpoints to mark articles as off-topic (or confirm
on-topic). Stores opinions in topic_feedback (mig 050) so the golden
pipeline daemon + future topic-classifier can exclude flagged content
from selection / training.

The user's framing was: "we should build some sort of evolving
validation corpus on what articles, research etc. we filter on the
platform." These two endpoints are the data substrate for that.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth_routes import get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("topic-feedback")
router = APIRouter(prefix="/api/feedback", tags=["Topic Feedback"])


class TopicFeedbackRequest(BaseModel):
    verdict: str = Field(..., pattern="^(on_topic|off_topic|borderline)$")
    reason: Optional[str] = Field(None, max_length=500)
    off_topic_category: Optional[str] = Field(
        None,
        max_length=50,
        description="Free-form category: politics, sports, finance, crime, etc.",
    )


@router.post("/topic/{article_id}")
async def submit_topic_feedback(
    article_id: str,
    payload: TopicFeedbackRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Mark an article as on-topic / off-topic / borderline.

    Anonymous users may flag — schema allows null reporter_id. Logged-in
    users get their user_id attached so future consensus weighting can
    distinguish authenticated opinions from anonymous flags.
    """
    db = get_postgres()
    reporter_id = (current_user or {}).get("user_id")

    # Sanity-check the article exists before recording feedback
    rows = db.execute_query(
        "SELECT 1 FROM articles WHERE article_id = :aid LIMIT 1",
        {"aid": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    db.execute_update(
        """INSERT INTO topic_feedback (
               feedback_id, article_id, verdict, reason,
               reporter_id, off_topic_category
           ) VALUES (:fid, :aid, :v, :r, :rep, :cat)""",
        {
            "fid": str(uuid4()),
            "aid": article_id,
            "v": payload.verdict,
            "r": payload.reason,
            "rep": reporter_id,
            "cat": payload.off_topic_category,
        },
    )
    logger.info(
        f"topic-feedback: article={article_id} verdict={payload.verdict} "
        f"reporter={reporter_id or 'anon'} cat={payload.off_topic_category}"
    )
    return {
        "status": "recorded",
        "article_id": article_id,
        "verdict": payload.verdict,
    }


@router.get("/topic/off-topic-ids")
async def list_off_topic_article_ids(limit: int = 1000):
    """Return article_ids with at least one off_topic verdict.

    Used by the golden_pipeline_daemon to exclude flagged articles from
    selection waves. Simple "any-flag-wins" rule for the MVP — consensus
    weighting can come later when there's enough volume to need it.
    """
    db = get_postgres()
    rows = db.execute_query(
        """SELECT DISTINCT article_id::text AS aid
           FROM topic_feedback
           WHERE verdict = 'off_topic'
           ORDER BY article_id::text
           LIMIT :lim""",
        {"lim": limit},
    )
    return {
        "off_topic_ids": [r["aid"] for r in rows],
        "total": len(rows),
    }


@router.get("/topic/{article_id}")
async def get_topic_feedback_for_article(article_id: str):
    """Return all topic-feedback opinions on a specific article."""
    db = get_postgres()
    rows = db.execute_query(
        """SELECT feedback_id::text AS feedback_id,
                  verdict, reason, off_topic_category,
                  reporter_id::text AS reporter_id,
                  created_at
           FROM topic_feedback
           WHERE article_id = :aid
           ORDER BY created_at DESC""",
        {"aid": article_id},
    )
    on = sum(1 for r in rows if r["verdict"] == "on_topic")
    off = sum(1 for r in rows if r["verdict"] == "off_topic")
    return {
        "article_id": article_id,
        "feedback": [dict(r) for r in rows],
        "on_topic_count": on,
        "off_topic_count": off,
        "is_flagged": off > 0,
    }
