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
    """Require SCHEDULER_SECRET — fail closed in production.

    Was previously a no-op when the env var was empty (any unset deploy
    leaked the /api/scheduler/* endpoints publicly). Now if ENVIRONMENT
    is production and SCHEDULER_SECRET is not set, refuse to serve.
    """
    env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").lower()
    if env in {"prod", "production"} and not SCHEDULER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SCHEDULER_SECRET must be configured in production",
        )
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
        logger.error(f"Celery task module not available: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


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

    except ImportError as exc:
        # Surface this as a real error so Cloud Scheduler doesn't report green
        # on a non-functional pipeline. Was previously a silent 200/"skipped"
        # which masked deployment regressions.
        logger.error(f"Scheduler task module unavailable: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


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

    except ImportError as exc:
        # Surface this as a real error so Cloud Scheduler doesn't report green
        # on a non-functional pipeline. Was previously a silent 200/"skipped"
        # which masked deployment regressions.
        logger.error(f"Scheduler task module unavailable: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


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

    except ImportError as exc:
        # Surface this as a real error so Cloud Scheduler doesn't report green
        # on a non-functional pipeline. Was previously a silent 200/"skipped"
        # which masked deployment regressions.
        logger.error(f"Scheduler task module unavailable: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


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

    except ImportError as exc:
        # Surface this as a real error so Cloud Scheduler doesn't report green
        # on a non-functional pipeline. Was previously a silent 200/"skipped"
        # which masked deployment regressions.
        logger.error(f"Scheduler task module unavailable: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


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

    except ImportError as exc:
        # Surface this as a real error so Cloud Scheduler doesn't report green
        # on a non-functional pipeline. Was previously a silent 200/"skipped"
        # which masked deployment regressions.
        logger.error(f"Scheduler task module unavailable: {exc}")
        raise HTTPException(status_code=503, detail={"status": "error", "reason": "task_module_unavailable", "error": str(exc)})


# =============================================================================
# HEALTH CHECK / STATUS
# =============================================================================

@router.get("/health")
async def scheduler_health():
    """Health endpoint for scheduler subsystem."""
    return {"status": "ok", "scheduler_secret_configured": bool(SCHEDULER_SECRET)}


# =============================================================================
# INDICATOR ADAPTER SYNCS (Phase 3 wave 5)
# =============================================================================

# Map source name → adapter class. Adding a new adapter is one line here.
_INDICATOR_ADAPTERS = {
    "climate_trace": "ClimateTRACEAdapter",
    "owid":          "OWIDAdapter",
    "cat":           "ClimateActionTrackerAdapter",
    "unfccc_ndc":    "UNFCCCNdcAdapter",
    "irena":         "IRENAAdapter",
    "nd_gain":       "NDGainAdapter",
}


def _persist_sync_result(db, result, triggered_by: str) -> None:
    """Write one indicator_sync_logs row from a SyncResult. Best-effort."""
    import json as _json
    try:
        db.execute_update(
            """
            INSERT INTO indicator_sync_logs (
                source_name, started_at, finished_at, duration_seconds,
                fetched_count, upserted_count, skipped_count, error_count,
                errors, triggered_by
            ) VALUES (
                :source, :started, :finished, :duration,
                :fetched, :upserted, :skipped, :err_count,
                CAST(:errors AS jsonb), :triggered_by
            )
            """,
            {
                "source": result.source_name,
                "started": result.started_at,
                "finished": result.finished_at,
                "duration": result.duration_seconds,
                "fetched": result.fetched_count,
                "upserted": result.upserted_count,
                "skipped": result.skipped_count,
                "err_count": len(result.errors or []),
                # Preserve first 5 errors verbatim; cap to keep the row small.
                "errors": _json.dumps((result.errors or [])[:5]) if result.errors else None,
                "triggered_by": triggered_by,
            },
        )
    except Exception as exc:
        logger.warning(f"sync log persist failed: {exc}")


@router.post("/indicators/sync")
async def scheduled_indicator_sync(
    source: str = "all",
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret"),
):
    """Run one or all indicator adapters and persist the SyncResult.

    Query params:
      * source = 'climate_trace' | 'owid' | 'cat' | 'all' (default 'all').

    Returns the list of SyncResult dicts. Each adapter runs sequentially
    (rather than concurrently) to keep upstream rate-limit pressure
    bounded — adapters' polite-scraper delays are per-adapter, not
    cross-adapter, so concurrency would race the throttle.
    """
    _verify_scheduler_secret(x_scheduler_secret)

    sources_to_run: list[str]
    if source == "all":
        sources_to_run = list(_INDICATOR_ADAPTERS.keys())
    elif source in _INDICATOR_ADAPTERS:
        sources_to_run = [source]
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown source '{source}'. Available: "
                f"{', '.join(_INDICATOR_ADAPTERS.keys())} | all"
            ),
        )

    # Lazy-import adapters so the route file stays cheap to load.
    try:
        from app.domains.content import indicators as _ind_module
    except Exception as exc:
        return {"status": "error", "detail": f"Indicators module unavailable: {exc}"}

    try:
        from app.core.database import get_db as _get_db_fn  # type: ignore
        db = _get_db_fn()
    except Exception:
        # Fallback to shared database helper used by other routes.
        from shared.database import get_postgres as _get_postgres
        db = _get_postgres()

    results: list[dict] = []
    for src in sources_to_run:
        adapter_cls_name = _INDICATOR_ADAPTERS[src]
        adapter_cls = getattr(_ind_module, adapter_cls_name, None)
        if adapter_cls is None:
            results.append({
                "source_name": src,
                "status": "error",
                "errors": [f"Adapter class {adapter_cls_name} not exported"],
            })
            continue

        try:
            adapter = adapter_cls()
            sync_result = await adapter.sync(db)
            _persist_sync_result(db, sync_result, triggered_by="scheduler")
            results.append(sync_result.as_dict())
        except Exception as exc:
            logger.error(f"Adapter {src} failed: {exc}")
            results.append({
                "source_name": src,
                "status": "error",
                "errors": [f"{type(exc).__name__}: {exc}"],
            })

    return {"status": "ok", "results": results}


@router.get("/indicators/sync/recent")
async def recent_indicator_syncs(
    source: Optional[str] = None,
    limit: int = 20,
):
    """Read the last N indicator_sync_logs rows for ops dashboards."""
    from shared.database import get_postgres
    db = get_postgres()
    limit = max(1, min(limit, 200))

    where = ""
    params: dict = {"lim": limit}
    if source:
        where = "WHERE source_name = :src"
        params["src"] = source

    try:
        rows = db.execute_query(
            f"""
            SELECT
                source_name, started_at, finished_at, duration_seconds,
                fetched_count, upserted_count, skipped_count, error_count,
                errors, triggered_by
            FROM indicator_sync_logs
            {where}
            ORDER BY started_at DESC
            LIMIT :lim
            """,
            params,
        )
    except Exception as exc:
        return {
            "available": False,
            "reason": f"indicator_sync_logs query failed: {type(exc).__name__}",
            "rows": [],
        }

    out = []
    for r in rows or []:
        out.append({
            "source_name": r.get("source_name"),
            "started_at": str(r.get("started_at")) if r.get("started_at") else None,
            "finished_at": str(r.get("finished_at")) if r.get("finished_at") else None,
            "duration_seconds": r.get("duration_seconds"),
            "fetched_count": r.get("fetched_count"),
            "upserted_count": r.get("upserted_count"),
            "skipped_count": r.get("skipped_count"),
            "error_count": r.get("error_count"),
            "errors": r.get("errors"),
            "triggered_by": r.get("triggered_by"),
        })
    return {"available": True, "rows": out, "total": len(out)}
