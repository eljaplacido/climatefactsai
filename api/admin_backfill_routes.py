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
from pydantic import BaseModel, Field

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
        from app.domains.trust.source_tier_service import (
            get_source_credibility_score,
            _extract_domain,
            clear_tier_cache,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"source_tier_service import failed: {type(exc).__name__}",
        )

    # Stage-1 B3 follow-up (2026-05-27): _db_lookup has @lru_cache so
    # Cloud Run instances retain stale 'domain unknown' entries from
    # before mig 049 / the hotfix expanded the tier table. Clearing
    # here forces a fresh lookup against the now-populated table.
    clear_tier_cache()

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
        # Bug from Stage-3 review (2026-05-27): backfill was passing the
        # full URL as the `domain` parameter, so get_source_tier_prior's
        # `domain or _extract_domain(source_name)` short-circuited on the
        # URL string and the DB lookup queried `WHERE domain="https://..."`
        # instead of "carbonbrief.org". Pre-extract the domain so the
        # lookup actually matches the mig 027/033/049 seeds.
        extracted = _extract_domain(url) if url else None
        try:
            score = get_source_credibility_score(db, source, extracted)
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
# 4. Entity extraction scheduler trigger — KG Phase 1
# ---------------------------------------------------------------------------

@router.post("/scheduler/extract-entities")
async def trigger_extract_entities(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(default=15, ge=1, le=50),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Run EntityExtractionService.batch_extract_for_pending_articles.

    KG-Robustness-Audit-2026-05-27 §2 Phase 1 — wires the spaCy / LLM
    entity extractor against the canonical knowledge_graph schema (mig
    049). Without this trigger the `entities` + `article_entities` +
    `entity_relationships` tables stay empty in prod and
    `GET /api/articles/{id}/kg` returns the "kg_not_populated" soft-fail.

    Runs in a background task; progress logged via the service's
    structured logger. Cadence target: hourly via cn-ner-extract cron
    until the corpus is fully linked, then nightly.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    try:
        from app.domains.intelligence.entity_extraction_service import (
            EntityExtractionService,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"EntityExtractionService unavailable: {type(exc).__name__}",
        )

    async def _run():
        service = EntityExtractionService(db)
        try:
            summary = await service.batch_extract_for_pending_articles(limit=batch_size)
            logger.info(f"scheduler/extract-entities: {summary}")
        except Exception as exc:
            logger.error(f"scheduler/extract-entities failed: {exc}")

    background_tasks.add_task(_run)
    return {
        "status": "queued",
        "task": "batch_extract_for_pending_articles",
        "batch_size": batch_size,
        "note": "Progress logged via 'batch_extract complete' structured log.",
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


# ---------------------------------------------------------------------------
# 4. Targeted enrichment by article_id list (Golden Example evaluation set)
# ---------------------------------------------------------------------------

class EnrichByIdsRequest(BaseModel):
    article_ids: list[str] = Field(..., min_length=1, max_length=50)


@router.post("/backfill/brief-from-excerpt")
async def backfill_brief_from_excerpt(
    batch_size: int = Query(default=200, ge=1, le=1000),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Derive executive_brief from enriched_excerpt for articles that
    have a substantial excerpt but no brief.

    Audit loop 4 caught: 175 articles failed validation on the brief
    gate even though their excerpt was 1.6-3k chars. These were
    enriched BEFORE the brief-fallback shipped (commit 5d6ab0d).
    Running this endpoint takes the first ~150 words of the excerpt
    and stamps them into executive_brief — same fallback logic the
    live enrichment service uses, just applied retroactively.

    Idempotent — only touches rows where brief is NULL or empty
    string AND excerpt is present.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()
    rows = db.execute_query(
        """SELECT article_id, enriched_excerpt
           FROM articles
           WHERE (executive_brief IS NULL OR octet_length(executive_brief) < 50)
             AND enriched_excerpt IS NOT NULL
             AND octet_length(enriched_excerpt) >= 200
             AND is_synthetic = FALSE
           ORDER BY enriched_at DESC NULLS LAST
           LIMIT :lim""",
        {"lim": batch_size},
    ) or []
    if not rows:
        return {"scanned": 0, "updated": 0, "note": "No articles need brief backfill."}
    updated = 0
    for r in rows:
        excerpt = r.get("enriched_excerpt") or ""
        words = excerpt.split()
        fallback = " ".join(words[:150])
        if len(words) > 150:
            fallback = fallback.rstrip(".,;:") + "…"
        if len(fallback) < 50:
            continue
        try:
            n = db.execute_update(
                """UPDATE articles
                   SET executive_brief = :brief,
                       updated_at = NOW()
                   WHERE article_id = :id
                     AND (executive_brief IS NULL OR octet_length(executive_brief) < 50)""",
                {"brief": fallback, "id": r["article_id"]},
            )
            if n:
                updated += 1
        except Exception as exc:
            logger.debug(f"brief backfill failed for {r['article_id']}: {exc}")
    return {
        "scanned": len(rows),
        "updated": updated,
        "note": "Run again until 'scanned' returns 0 to converge.",
    }


@router.post("/backfill/enrich-articles")
async def enrich_articles_by_id(
    payload: EnrichByIdsRequest,
    background_tasks: BackgroundTasks,
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Run ArticleEnrichmentService.enrich_article on a hand-picked list.

    Companion to /scheduler/enrich-pending, which always pulls the next
    25 un-enriched rows newest-first. This endpoint lets ops nominate the
    exact article_ids to enrich — used to build the Golden Example set
    after the End2End audit found `executive_brief` 0% populated despite
    Golden #5 (b892f5b) shipping the code path.

    Returns immediately with status=queued; per-article completion is
    visible via the article-detail endpoint (`enriched_at` flips from
    NULL to a timestamp, `executive_brief` populates).
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

    rows = db.execute_query(
        """SELECT article_id, title,
                  COALESCE(extracted_text, '') AS extracted_text,
                  COALESCE(source_name, '') AS source_name,
                  COALESCE(country_code, 'FI') AS country_code,
                  content_category
           FROM articles
           WHERE article_id::text = ANY(:ids)
             AND is_synthetic = FALSE""",
        {"ids": payload.article_ids},
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No matching non-synthetic articles for the supplied IDs",
        )

    async def _run():
        service = ArticleEnrichmentService(db)
        processed = 0
        failed = 0
        skipped = 0
        for r in rows:
            text = r.get("extracted_text", "")
            if not text or len(text.strip()) < 50:
                skipped += 1
                continue
            try:
                await service.enrich_article(
                    article_id=str(r["article_id"]),
                    title=r.get("title", ""),
                    extracted_text=text,
                    source_name=r.get("source_name", ""),
                    country_code=r.get("country_code", "FI"),
                    content_category=r.get("content_category"),
                )
                processed += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    f"enrich-articles: {r.get('article_id')} failed: {exc}"
                )
        logger.info(
            f"enrich-articles complete: processed={processed} "
            f"failed={failed} skipped={skipped} requested={len(payload.article_ids)} "
            f"resolved={len(rows)}"
        )

    background_tasks.add_task(_run)
    return {
        "status": "queued",
        "task": "enrich_articles_by_id",
        "requested": len(payload.article_ids),
        "resolved": len(rows),
        "note": "Progress logged via 'enrich-articles complete' structured log.",
    }


# ---------------------------------------------------------------------------
# 5. Golden-priority queue for GX10 Lane A worker
# ---------------------------------------------------------------------------

class GoldenQueueRequest(BaseModel):
    article_ids: list[str] = Field(..., min_length=1, max_length=200)


@router.post("/backfill/golden-queue")
async def golden_queue_articles(
    payload: GoldenQueueRequest,
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Mark articles for GX10 Lane A worker golden-priority processing.

    Use case: the autonomous overnight `golden_pipeline_daemon.py` selects
    300-400 high-quality climate-journalism candidates and queues them
    here. The Lane A worker on the GX10 polls Cloud SQL and processes
    `enriched_at IS NULL` articles — this endpoint:

      1. Resets enriched_at to NULL (so the worker picks them up again
         even if they were previously enriched on a wrong path).
      2. Stamps enrichment_metadata.golden_priority = true so the
         modified batch_enrich SELECT pulls them BEFORE the rest of the
         un-enriched corpus.

    The Lane A worker uses qwen2.5:14b via local Ollama on the GX10 —
    full privacy, no cloud LLM cost. Latency budget hours OK per the
    Lane A pattern in docs/reports/asusgx10inferencestrategy.md.

    Token-gated via CORPORATE_SYNC_TOKEN / SCHEDULER_SECRET, same as the
    other admin backfill endpoints. Max 200 IDs per call.
    """
    _auth(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    affected = db.execute_update(
        """UPDATE articles
           SET enriched_at = NULL,
               enrichment_metadata = jsonb_set(
                   COALESCE(enrichment_metadata, '{}'::jsonb),
                   '{golden_priority}',
                   'true'::jsonb,
                   true
               ),
               updated_at = NOW()
           WHERE article_id::text = ANY(:ids)
             AND is_synthetic = FALSE""",
        {"ids": payload.article_ids},
    )

    logger.info(
        f"golden-queue: requested={len(payload.article_ids)} affected={affected}"
    )

    return {
        "status": "queued",
        "task": "golden_priority_queue",
        "requested": len(payload.article_ids),
        "affected_rows": affected,
        "note": (
            "Articles flagged with enrichment_metadata.golden_priority=true. "
            "Lane A worker (qwen2.5:14b on GX10) will pull them ahead of the "
            "standard newest-un-enriched queue on its next polling cycle."
        ),
    }
