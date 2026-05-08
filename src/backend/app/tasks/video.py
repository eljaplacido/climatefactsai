"""
Video rendering pipeline hooks.

Real Remotion rendering is not yet wired into the worker. Until that happens
the task only registers a job in DISABLED state so downstream consumers can
see that no video asset exists, instead of pointing at a fabricated URL.
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
    """Mark video jobs as DISABLED until real Remotion rendering is wired in."""
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
            trust_service.video_jobs.update_status(
                job_id=job["job_id"],
                status="DISABLED",
                output_url=None,
            )
            trust_service.update_article_trust(
                article_id=article_id,
                video_status="DISABLED",
                video_url=None,
            )
            job_refs.append({
                "article_id": article_id,
                "job_id": job["job_id"],
                "video_url": None,
                "status": "DISABLED",
            })
        except Exception as exc:  # noqa: BLE001
            logger.error("Video job registration failed", article_id=article_id, error=str(exc))

    workflow_state["video_jobs"] = job_refs
    return workflow_state
