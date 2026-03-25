"""
Trust domain services orchestrating publisher trust, compliance, and HITL flows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.database import Database
from app.core.logging import get_logger
from .repository import (
    PublisherRepository,
    TrustArticleRepository,
    ModerationQueueRepository,
    VideoJobRepository,
)

logger = get_logger(__name__)


class TrustService:
    """High level operations defined in the refactor alignment docs."""

    def __init__(self, db: Database):
        self.publishers = PublisherRepository(db)
        self.articles = TrustArticleRepository(db)
        self.moderation = ModerationQueueRepository(db)
        self.video_jobs = VideoJobRepository(db)

    def ensure_publisher(
        self,
        *,
        domain: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        trust_score: Optional[int] = None,
        credibility_rating: Optional[str] = None,
        tdm_opt_out: Optional[bool] = None,
        nutrition_label: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upsert publisher metadata so ingestion/compliance can re-use it."""
        publisher = self.publishers.upsert_publisher(
            domain=domain,
            name=name,
            description=description,
            trust_score=trust_score,
            credibility_rating=credibility_rating,
            tdm_opt_out=tdm_opt_out,
            nutrition_label=nutrition_label,
        )
        logger.info("Publisher metadata synced", domain=domain, trust_score=publisher.get("trust_score"))
        return publisher

    def record_compliance_decision(
        self,
        *,
        article_id: str,
        domain: str,
        allowed: bool,
        reason: Optional[str],
        robots_status: str,
        tdm_opt_out: bool,
    ):
        """Persist compliance outcome at publisher + article level."""
        self.publishers.record_compliance_result(
            domain=domain,
            robots_status=robots_status,
            tdm_opt_out=tdm_opt_out,
            last_checked=datetime.utcnow(),
        )
        self.articles.update_trust_metadata(
            article_id,
            compliance_passed=allowed,
            compliance_reason=reason,
        )
        logger.info(
            "Compliance decision recorded",
            article_id=article_id,
            domain=domain,
            allowed=allowed,
            reason=reason,
        )

    def update_article_trust(
        self,
        *,
        article_id: str,
        trust_score: Optional[int] = None,
        provenance: Optional[Dict[str, Any]] = None,
        summary_type: Optional[str] = None,
        hitl_status: Optional[str] = None,
        video_status: Optional[str] = None,
        video_url: Optional[str] = None,
    ):
        """Store trust score, HITL state, and LangGraph provenance."""
        self.articles.update_trust_metadata(
            article_id,
            trust_score=trust_score,
            provenance=provenance,
            summary_type=summary_type,
            hitl_status=hitl_status,
            video_status=video_status,
            video_url=video_url,
        )
        logger.info(
            "Article trust metadata updated",
            article_id=article_id,
            trust_score=trust_score,
            hitl_status=hitl_status,
        )

    def queue_hitl_review(
        self,
        *,
        article_id: str,
        priority: int,
        assigned_to: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert into moderation queue when LangGraph routes to HITL."""
        queue_row = self.moderation.enqueue(
            article_id=article_id,
            priority=priority,
            assigned_to=assigned_to,
            feedback=reason,
        )
        self.articles.update_trust_metadata(
            article_id,
            hitl_status="PENDING",
        )
        return queue_row

    def complete_hitl_review(
        self,
        *,
        queue_id: int,
        article_id: str,
        status: str,
        reviewer: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        edits: Optional[Dict[str, Any]] = None,
    ):
        self.moderation.update_status(
            queue_id,
            status=status,
            reviewer=reviewer,
            rejection_reason=rejection_reason,
            edits=edits,
        )
        self.articles.update_trust_metadata(
            article_id,
            hitl_status=status,
        )

    def register_video_job(
        self,
        *,
        article_id: str,
        render_provider: str = "remotion",
        assets: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a video job row so Lambda workers can update status."""
        job_id = f"video-{uuid4()}"
        job = self.video_jobs.create_job(
            article_id=article_id,
            job_id=job_id,
            render_provider=render_provider,
            assets=assets,
        )
        self.articles.update_trust_metadata(
            article_id,
            video_status="QUEUED",
        )
        return job
