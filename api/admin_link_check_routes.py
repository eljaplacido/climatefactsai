"""Link-rot detection admin endpoint — Slice 5a (2026-05-25).

Honest-Gap-Audit v2 item 7: many article source_url links point at
404 / paywalled / removed pages but the platform never re-checks URLs
after first ingest. This endpoint runs a batch HEAD probe against the
oldest-unchecked articles and writes the result back to
articles.source_url_status (mig 046).

Operator workflow (manual or via Cloud Scheduler):

  curl -X POST \\
       -H "x-corporate-sync-token: $CORPORATE_SYNC_TOKEN" \\
       "https://api.example/api/admin/link-check?batch_size=100"

Suggested Cloud Scheduler cron: nightly at 02:00 UTC, payload
batch_size=200. With ~6000 articles in the corpus and a 7-day
re-check interval, 200 / night clears the backlog comfortably.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Query

from shared.database import get_postgres

logger = logging.getLogger("admin-link-check")
router = APIRouter(prefix="/api/admin/link-check", tags=["Admin / Link check"])

DEFAULT_TIMEOUT = 10.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; ClimatefactsLinkChecker/1.0; "
    "+https://climatefacts.ai/about/crawler)"
)


def _auth(token: Optional[str]) -> None:
    expected = os.environ.get("CORPORATE_SYNC_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Link-check endpoint disabled — set CORPORATE_SYNC_TOKEN to enable",
        )
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _classify(status_code: int) -> str:
    """Map HTTP status to source_url_status taxonomy from mig 046."""
    if 200 <= status_code < 300:
        return "ok"
    if 300 <= status_code < 400:
        return "redirect"
    return "broken"


async def _probe(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """HEAD-probe a single URL and return the status string. Some
    publishers reject HEAD; fall back to a 1-byte ranged GET."""
    if not url or not url.startswith(("http://", "https://")):
        return "broken"
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.head(url)
            # Some servers return 405 / 403 for HEAD. Retry as ranged GET
            # to confirm the URL is reachable.
            if resp.status_code in (403, 405):
                resp = await client.get(url, headers={"Range": "bytes=0-1"})
            return _classify(resp.status_code)
    except httpx.TimeoutException:
        return "broken"
    except httpx.RequestError:
        return "broken"
    except Exception as exc:
        logger.debug(f"link-check unexpected error for {url}: {exc}")
        return "broken"


@router.post("")
async def run_link_check(
    batch_size: int = Query(default=100, ge=1, le=500),
    x_corporate_sync_token: Optional[str] = Header(default=None),
):
    """Run a batched link-rot check.

    Selects up to `batch_size` articles whose source_url_status is NULL
    or stale (>7 days old), HEAD-probes each, and writes back the new
    status + timestamp. Concurrent probes (max 8 at a time) keep the
    job under a minute for a 200-article batch.
    """
    _auth(x_corporate_sync_token)
    db = get_postgres()

    rows = db.execute_query(
        """SELECT article_id, source_url
           FROM articles
           WHERE source_url IS NOT NULL
             AND (source_url_status IS NULL
                  OR source_url_checked_at < NOW() - INTERVAL '7 days')
           ORDER BY source_url_checked_at NULLS FIRST
           LIMIT :n""",
        {"n": batch_size},
    )

    if not rows:
        return {
            "checked": 0,
            "ok": 0,
            "redirect": 0,
            "broken": 0,
            "note": "Nothing due for re-check.",
        }

    # Run up to 8 probes concurrently — politer than 200-at-once and
    # still well under a minute per batch.
    sem = asyncio.Semaphore(8)

    async def _bounded(article_id: str, url: str) -> tuple[str, str]:
        async with sem:
            status = await _probe(url)
            return article_id, status

    pairs = await asyncio.gather(
        *(_bounded(str(r["article_id"]), r["source_url"]) for r in rows),
        return_exceptions=False,
    )

    # Single-statement batch update.
    counts = {"ok": 0, "redirect": 0, "broken": 0}
    for article_id, status in pairs:
        counts[status] += 1
        db.execute_update(
            """UPDATE articles
               SET source_url_status = :s,
                   source_url_checked_at = NOW()
               WHERE article_id = :id""",
            {"s": status, "id": article_id},
        )

    logger.info(
        f"link-check: probed {len(pairs)} articles "
        f"(ok={counts['ok']} redirect={counts['redirect']} broken={counts['broken']})"
    )
    return {"checked": len(pairs), **counts}


@router.get("/summary")
async def link_check_summary(
    x_corporate_sync_token: Optional[str] = Header(default=None),
):
    """Snapshot of current link-status distribution across the corpus."""
    _auth(x_corporate_sync_token)
    db = get_postgres()
    rows = db.execute_query(
        """SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE source_url_status = 'ok') AS ok,
              COUNT(*) FILTER (WHERE source_url_status = 'redirect') AS redirect,
              COUNT(*) FILTER (WHERE source_url_status = 'broken') AS broken,
              COUNT(*) FILTER (WHERE source_url_status IS NULL) AS pending,
              COUNT(*) FILTER (WHERE source_url_checked_at IS NOT NULL
                               AND source_url_checked_at < NOW() - INTERVAL '7 days') AS stale
           FROM articles
           WHERE source_url IS NOT NULL"""
    )
    r = rows[0] if rows else {}
    return {
        "total": int(r.get("total") or 0),
        "ok": int(r.get("ok") or 0),
        "redirect": int(r.get("redirect") or 0),
        "broken": int(r.get("broken") or 0),
        "pending": int(r.get("pending") or 0),
        "stale_over_7d": int(r.get("stale") or 0),
    }
