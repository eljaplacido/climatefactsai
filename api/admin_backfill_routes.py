"""Admin backfill endpoints — 2026-05-27 follow-up to End2End audit.

Three operator-driven jobs that fix data the End2End audit flagged as
inconsistent. Token-gated via CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET so
Cloud Scheduler can drive them on cadence without operator intervention.

  POST /api/admin/backfill/source-credibility-score
        - Re-stamps articles.source_credibility_score via source_tier_service
          for rows where the score is NULL or the constant fallback 50.
        - Limit + offset to walk the corpus in batches.

  POST /api/admin/backfill/extracted-text-html
        - Re-cleans articles.extracted_text + articles.excerpt via
          shared.html_cleaner for rows whose extracted_text still
          contains raw HTML markup (e.g. `<img`, `<p>`, "appeared first on").
        - Backfills historical Premium Times / WordPress feed pollution.

  POST /api/admin/scheduler/enrich-pending
        - Triggers ArticleEnrichmentService.batch_enrich for articles
          where enriched_at IS NULL. This endpoint exists because the
          enrichment service was wired but had no scheduler trigger —
          the End2End audit found `enriched_excerpt` was 0% populated
          across the entire production corpus.

All three accept either CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET in
their respective headers so Cloud Scheduler's default X-Scheduler-Secret
header works alongside ops curl.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query

from shared.database import get_postgres

logger = logging.getLogger("admin-backfill")
router = APIRouter(prefix="/api/admin", tags=["Admin / Backfill"])


def _auth(token: Optional[str], scheduler_secret: Optional[str] = None) -> None:
    """Accept CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET — same pattern as
    admin_link_check_routes._auth + research_feed_routes._auth_admin."""
    corp_expected = os.environ.get("CORPORATE_SYNC_TOKEN")
    sched_expected = os.environ.get("SCHEDULER_SECRET")
    if not corp_expected and not sched_expected:
        raise HTTPException(
            status_code=503,
            detail="Backfill endpoints disabled — set CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET",
        )
    if corp_expected and token == corp_expected:
        return
    if sched_expected and scheduler_secret == sched_expected:
        return
    raise HTTPException(status_code=401, detail="Invalid admin token")


# ---------------------------------------------------------------------------
# 1. Source credibility backfill
# ---------------------------------------------------------------------------

@router.post("/backfill/source-credibility-score")
async def backfill_source_credibility_score(
    batch_size: int = Query(default=200, ge=1, le=1000),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Re-stamp articles.source_credibility_score via source_tier_service.

    Targets rows where source_credibility_score IS NULL or is exactly the
    historical hardcoded fallback (50) — those are the rows ingested before
    the tier-driven score path landed on 2026-05-27. T1 sources stamp at 90,
    T2 at 75, T3 at 60, unknown stays at 50, retracted at 20.

    Re-runnable: an already-stamped non-50 row is left alone, so the cron
    converges over a few nights as the corpus refreshes.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    try:
        from app.domains.trust.source_tier_service import get_source_credibility_score
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"source_tier_service import failed: {type(exc).__name__}",
        )

    rows = db.execute_query(
        """SELECT article_id, source_name, url
             FROM articles
            WHERE source_name IS NOT NULL
              AND (source_credibility_score IS NULL OR source_credibility_score = 50)
              AND is_synthetic = FALSE
            ORDER BY created_at DESC NULLS LAST
            LIMIT :n""",
        {"n": batch_size},
    )

    if not rows:
        return {"scanned": 0, "updated": 0, "note": "No articles due for credibility backfill."}

    updated = 0
    distribution = {"T1": 0, "T2": 0, "T3": 0, "unknown": 0, "retracted": 0, "other": 0}
    for r in rows:
        article_id = r["article_id"]
        source = r.get("source_name") or ""
        url = r.get("url") or ""
        try:
            score = get_source_credibility_score(db, source, url)
        except Exception as exc:
            logger.debug(f"credibility lookup failed for {article_id}: {exc}")
            continue
        # Map score to band for the response summary.
        band = (
            "T1" if score == 90 else
            "T2" if score == 75 else
            "T3" if score == 60 else
            "unknown" if score == 50 else
            "retracted" if score == 20 else "other"
        )
        distribution[band] = distribution.get(band, 0) + 1
        # Only write if the value would actually change.
        try:
            n = db.execute_update(
                """UPDATE articles
                      SET source_credibility_score = :s, updated_at = NOW()
                    WHERE article_id = :id
                      AND (source_credibility_score IS NULL OR source_credibility_score <> :s)""",
                {"s": score, "id": article_id},
            )
            if n:
                updated += 1
        except Exception as exc:
            logger.debug(f"credibility UPDATE failed for {article_id}: {exc}")

    return {
        "scanned": len(rows),
        "updated": updated,
        "distribution": distribution,
        "note": "Run again until 'scanned' returns 0 to converge.",
    }


# ---------------------------------------------------------------------------
# 2. Extracted-text HTML strip backfill
# ---------------------------------------------------------------------------

@router.post("/backfill/extracted-text-html")
async def backfill_extracted_text_html(
    batch_size: int = Query(default=100, ge=1, le=500),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Re-clean articles.extracted_text + articles.excerpt via the shared
    HTML cleaner for any row that still has raw markup.

    Targeted at the historical pollution from RSS-summary fallbacks where
    publishers (Premium Times Nigeria, various WordPress sites) embed
    `<img>` / `<p>` / "appeared first on" footers verbatim in their feeds.
    The cleaner normalises these to plain text so the Full Article panel
    no longer renders raw tags.

    Re-runnable: rows whose cleaned text matches the existing extracted
    text are skipped via the UPDATE WHERE clause.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    try:
        from shared.html_cleaner import clean_article_text, looks_like_html
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"html_cleaner import failed: {type(exc).__name__}",
        )

    rows = db.execute_query(
        """SELECT article_id, extracted_text, excerpt
             FROM articles
            WHERE (
                  POSITION('<img' IN COALESCE(extracted_text, '')) > 0
               OR POSITION('<p>' IN COALESCE(extracted_text, '')) > 0
               OR POSITION('<a ' IN COALESCE(extracted_text, '')) > 0
               OR POSITION('appeared first on' IN COALESCE(extracted_text, '')) > 0
               OR POSITION('<img' IN COALESCE(excerpt, '')) > 0
               OR POSITION('<p>' IN COALESCE(excerpt, '')) > 0
            )
              AND is_synthetic = FALSE
            ORDER BY created_at DESC NULLS LAST
            LIMIT :n""",
        {"n": batch_size},
    )

    if not rows:
        return {"scanned": 0, "cleaned": 0, "note": "No articles contain HTML markup."}

    cleaned = 0
    bytes_removed = 0
    for r in rows:
        article_id = r["article_id"]
        raw_text = r.get("extracted_text") or ""
        raw_excerpt = r.get("excerpt") or ""
        try:
            new_text = clean_article_text(raw_text)
            new_excerpt = clean_article_text(raw_excerpt)[:500] if raw_excerpt else None
            if new_text == raw_text and new_excerpt == raw_excerpt:
                continue
            bytes_removed += max(0, len(raw_text) - len(new_text))
            n = db.execute_update(
                """UPDATE articles
                      SET extracted_text = :t, excerpt = :e, updated_at = NOW()
                    WHERE article_id = :id""",
                {"t": new_text, "e": new_excerpt, "id": article_id},
            )
            if n:
                cleaned += 1
        except Exception as exc:
            logger.debug(f"html clean failed for {article_id}: {exc}")

    return {
        "scanned": len(rows),
        "cleaned": cleaned,
        "approx_bytes_removed": bytes_removed,
        "note": "Run again until 'scanned' returns 0 to converge.",
    }


# ---------------------------------------------------------------------------
# 3. Enrichment scheduler trigger
# ---------------------------------------------------------------------------

@router.post("/scheduler/enrich-pending")
async def trigger_enrich_pending(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(default=25, ge=1, le=100),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Run ArticleEnrichmentService.batch_enrich on the oldest un-enriched
    articles.

    End2End audit found enriched_excerpt / climate_context_summary /
    executive_brief were 0% populated across the live corpus despite the
    enrichment service being wired — root cause was that NO scheduler
    endpoint ever called batch_enrich. This endpoint closes that loop.

    Runs in a background task so the scheduler request returns quickly;
    progress is logged via the service's existing structured logger.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    try:
        from app.domains.content.article_enrichment_service import ArticleEnrichmentService
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ArticleEnrichmentService unavailable: {type(exc).__name__}",
        )

    async def _run():
        service = ArticleEnrichmentService(db)
        try:
            summary = await service.batch_enrich(limit=batch_size)
            logger.info(f"scheduler/enrich-pending: {summary}")
        except Exception as exc:
            logger.error(f"scheduler/enrich-pending failed: {exc}")

    background_tasks.add_task(_run)
    return {
        "status": "queued",
        "task": "batch_enrich",
        "batch_size": batch_size,
        "note": "Progress logged via 'batch_enrich complete' structured log.",
    }
