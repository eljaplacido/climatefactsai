"""
Video rendering placeholders for the Remotion pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.celery_app import app
from app.core.database import get_db
from app.domains.trust import TrustService
from app.core.logging import get_logger

logger = get_logger(__name__)


@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def render_video_preview(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schedule (mock) Remotion video jobs and mark completion.
    """
    workflow_state = workflow_state or {}
    article_ids: List[str] = workflow_state.get("article_ids") or []
    if not article_ids:
        workflow_state["video_jobs"] = []
        return workflow_state

    db = get_db()
    trust_service = TrustService(db)
    job_refs: List[Dict[str, Any]] = []

    for article_id in article_ids:
        try:
            job = trust_service.register_video_job(article_id=article_id)
            video_url = f"https://videos.climatenews.local/{article_id}.mp4"
            trust_service.video_jobs.update_status(
                job_id=job["job_id"],
                status="COMPLETED",
                output_url=video_url,
            )
            trust_service.update_article_trust(
                article_id=article_id,
                video_status="COMPLETED",
                video_url=video_url,
            )
            job_refs.append({"article_id": article_id, "job_id": job["job_id"], "video_url": video_url})
        except Exception as exc:  # noqa: BLE001
            logger.error("Video rendering failed", article_id=article_id, error=str(exc))

    workflow_state["video_jobs"] = job_refs
    return workflow_state
