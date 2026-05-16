"""
Scheduler Routes — Lightweight HTTP endpoints for Cloud Scheduler.

These endpoints replace Celery Beat for small-scale deployments.
Cloud Scheduler POSTs to them; they run tasks inline without Redis/Celery.
All endpoints require a SCHEDULER_SECRET header for basic auth.
"""

import os
import traceback
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel

from shared.logger import setup_logging

logger = setup_logging("scheduler")
router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])

SCHEDULER_SECRET = os.getenv("SCHEDULER_SECRET", "")


class SchedulerJobRequest(BaseModel):
    job_name: Optional[str] = None
    params: Optional[dict] = None


def _verify_scheduler_secret(secret: Optional[str]) -> None:
    """Require SCHEDULER_SECRET if one is configured."""
    if SCHEDULER_SECRET and secret != SCHEDULER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing scheduler secret",
        )


def _run_task_safely(task_name: str, func, *args, **kwargs) -> dict:
    """Run a task function and return standardized result."""
    try:
        result = func(*args, **kwargs)
        logger.info(f"Scheduler task completed: {task_name}")
        return {"status": "ok", "task": task_name, "result": result}
    except Exception as exc:
        logger.error(f"Scheduler task failed: {task_name}", error=str(exc), traceback=traceback.format_exc())
        return {"status": "error", "task": task_name, "error": str(exc)}


# =============================================================================
# INGESTION TASKS
# =============================================================================

@router.post("/ingestion/discover")
async def scheduled_discover_articles(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Trigger article discovery for target countries (inline, no Celery)."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.ingestion import discover_articles
        from app.core.logging import get_logger

        task_logger = get_logger(__name__)
        task_logger.info("Scheduler: running discover_articles inline")

        # Run a lightweight discovery — one batch of articles
        background_tasks.add_task(discover_articles)
        return {"status": "queued", "task": "discover_articles"}

    except ImportError as exc:
        logger.warning(f"Celery task module not available, skipping: {exc}")
        return {"status": "skipped", "reason": "task_module_unavailable"}


@router.post("/ingestion/rss")
async def scheduled_rss_ingestion(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Trigger RSS feed polling (inline, no Celery)."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.ingestion import poll_rss_feeds

        background_tasks.add_task(poll_rss_feeds)
        return {"status": "queued", "task": "poll_rss_feeds"}

    except ImportError:
        return {"status": "skipped", "reason": "task_module_unavailable"}


# =============================================================================
# PROCESSING TASKS
# =============================================================================

@router.post("/processing/verify-pending")
async def scheduled_verify_pending(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Trigger verification of pending articles."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.fact_check_pipeline import auto_verify_pending_articles

        background_tasks.add_task(auto_verify_pending_articles)
        return {"status": "queued", "task": "auto_verify_pending_articles"}

    except ImportError:
        return {"status": "skipped", "reason": "task_module_unavailable"}


@router.post("/processing/retry-failed")
async def scheduled_retry_failed(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Retry failed verifications."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.fact_check_pipeline import retry_failed_verifications

        background_tasks.add_task(retry_failed_verifications)
        return {"status": "queued", "task": "retry_failed_verifications"}

    except ImportError:
        return {"status": "skipped", "reason": "task_module_unavailable"}


# =============================================================================
# FEED & TRANSLATION TASKS
# =============================================================================

@router.post("/feeds/update")
async def scheduled_feed_updates(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Update user feeds."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.feed_scheduler import update_user_feeds

        background_tasks.add_task(update_user_feeds)
        return {"status": "queued", "task": "update_user_feeds"}

    except ImportError:
        return {"status": "skipped", "reason": "task_module_unavailable"}


@router.post("/translation/batch")
async def scheduled_batch_translate(
    background_tasks: BackgroundTasks,
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Batch translate recent articles."""
    _verify_scheduler_secret(x_scheduler_secret)

    try:
        from app.tasks.translation import batch_translate_recent

        background_tasks.add_task(batch_translate_recent)
        return {"status": "queued", "task": "batch_translate_recent"}

    except ImportError:
        return {"status": "skipped", "reason": "task_module_unavailable"}


# =============================================================================
# HEALTH CHECK / STATUS
# =============================================================================

@router.get("/health")
async def scheduler_health():
    """Health endpoint for scheduler subsystem."""
    return {"status": "ok", "scheduler_secret_configured": bool(SCHEDULER_SECRET)}
