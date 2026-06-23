#!/usr/bin/env python3
"""Lane A worker — runs on the GX10, polls Cloud SQL for un-enriched
articles, runs ArticleEnrichmentService locally against Ollama, writes
results back.

This replaces the Cloud Run → tunnel → GX10 architecture (which hit
mysterious egress blocks on both Tailscale Funnel and Cloudflare Tunnel
from europe-west4). Matches the asusgx10inferencestrategy.md "Lane A
overnight batch" pattern: GX10 always, latency budget hours OK, runs
locally without any tunnel reachability requirement.

Workflow:
  1. Connect to Cloud SQL via DATABASE_URL (public IP + authorized network
     OR cloud-sql-proxy on localhost).
  2. SELECT articles WHERE enriched_at IS NULL ORDER BY created_at DESC.
  3. For each article, call ArticleEnrichmentService.enrich_article
     against http://localhost:11434/v1 (Ollama).
  4. Sleep when corpus is caught up; resume polling on a cadence.

Environment variables:
  DATABASE_URL                   Postgres connection (Cloud SQL via auth proxy or pub IP)
  CLILENS_LOCAL_GX10_BASE_URL    Default: http://localhost:11434/v1
  CLILENS_LOCAL_GX10_API_KEY     Default: "ollama"
  CLILENS_LOCAL_GX10_MODEL       Default: qwen2.5:14b-instruct
  CLILENS_ENRICHMENT_PROVIDER    Default: local-gx10
  GX10_WORKER_BATCH_SIZE         Default: 10  (per-cycle batch)
  GX10_WORKER_IDLE_SLEEP_SEC     Default: 60  (sleep when no work)
  GX10_WORKER_MAX_BATCHES        Default: 0   (0 = forever)
  GX10_WORKER_DEEPSEEK_FALLBACK  Default: 0   (1 = let service fall back to cloud)
                                              The whole point of Lane A is local-only;
                                              0 prevents API spend from leaks.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Make the existing repo's modules importable. Worker expects to be invoked
# from inside the climatenews repo (cloned to ~/climatenews on GX10).
ROOT_DIR = Path(__file__).resolve().parents[2]
for p in (ROOT_DIR, ROOT_DIR / "src" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Force the enrichment service to use ONLY local-gx10 by default. The
# fallback chain (deepseek/openai/anthropic) would defeat the point of a
# Lane A worker — we want to know loudly when GX10 is broken, not silently
# burn cloud tokens.
os.environ.setdefault("CLILENS_LOCAL_GX10_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("CLILENS_LOCAL_GX10_API_KEY", "ollama")
os.environ.setdefault("CLILENS_LOCAL_GX10_MODEL", "qwen2.5:14b-instruct")
os.environ.setdefault("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")

# Optional fallback toggle. Default 0 = local-only; flip to 1 if you
# explicitly want to keep enrichment moving when Ollama is down.
_FALLBACK_OK = os.getenv("GX10_WORKER_DEEPSEEK_FALLBACK", "0") == "1"
if not _FALLBACK_OK:
    # Wipe cloud provider keys so the enrichment fallback chain has
    # nothing to attempt. The service's GX10 branch then returns the
    # error verbatim and we log it, instead of silently using cloud.
    for k in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(k, None)

from shared.database import get_postgres
from app.domains.content.article_enrichment_service import ArticleEnrichmentService


def send_telegram(message: str) -> None:
    """Send a brief notification to the Climatefacts bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message[:4000],
            "parse_mode": "Markdown",
        }).encode()
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception:
        pass  # Never let notifications break the worker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logger = logging.getLogger("lane-a-worker")

# --- Tunables -----------------------------------------------------------
BATCH_SIZE = int(os.getenv("GX10_WORKER_BATCH_SIZE", "10"))
IDLE_SLEEP = int(os.getenv("GX10_WORKER_IDLE_SLEEP_SEC", "60"))
MAX_BATCHES = int(os.getenv("GX10_WORKER_MAX_BATCHES", "0"))


_shutdown = False


def _handle_signal(signum, _frame):
    global _shutdown
    logger.info(f"Received signal {signum}; finishing current article then exiting")
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def _run_one_batch(service: ArticleEnrichmentService) -> dict:
    """One pass through the enrichment service's batch_enrich.

    Returns the structured summary so the outer loop can decide whether
    to sleep (no work found) or immediately go again.
    """
    return await service.batch_enrich(limit=BATCH_SIZE)


async def main() -> int:
    db = get_postgres()
    service = ArticleEnrichmentService(db)

    logger.info(
        "Lane A worker starting",
        extra={
            "batch_size": BATCH_SIZE,
            "idle_sleep_s": IDLE_SLEEP,
            "max_batches": MAX_BATCHES,
            "model": os.environ.get("CLILENS_LOCAL_GX10_MODEL"),
            "ollama": os.environ.get("CLILENS_LOCAL_GX10_BASE_URL"),
            "deepseek_fallback": _FALLBACK_OK,
        },
    )

    # Sanity check: hit Ollama once before entering the loop. If unreachable,
    # we fail loudly so systemd surfaces the problem instead of spinning.
    try:
        import httpx
        base_url = os.environ["CLILENS_LOCAL_GX10_BASE_URL"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base_url}/models")
            r.raise_for_status()
        logger.info("Ollama reachable at %s", base_url)
    except Exception as exc:
        logger.error("Ollama unreachable at startup: %s", exc)
        return 2

    batches_run = 0
    consecutive_empty = 0
    while not _shutdown:
        batches_run += 1
        try:
            summary = await _run_one_batch(service)
        except Exception as exc:
            logger.error("Batch failed: %s", exc, exc_info=True)
            await asyncio.sleep(min(IDLE_SLEEP, 30))
            continue

        logger.info(
            "Batch %s done | processed=%s failed=%s skipped=%s total_found=%s",
            batches_run,
            summary.get("processed", 0),
            summary.get("failed", 0),
            summary.get("skipped", 0),
            summary.get("total_found", 0),
        )
        send_telegram(
            f"✅ Enriched batch {batches_run} | "
            f"{summary.get('processed', 0)} ok, {summary.get('failed', 0)} failed "
            f"({os.environ.get('CLILENS_ENRICHMENT_PROVIDER', 'local-gx10')})"
        )

        if MAX_BATCHES and batches_run >= MAX_BATCHES:
            logger.info("Hit MAX_BATCHES=%s; exiting cleanly", MAX_BATCHES)
            break

        if summary.get("total_found", 0) == 0:
            consecutive_empty += 1
            # Back off more aggressively when the corpus is fully caught up,
            # capped at 30 min. Resets to IDLE_SLEEP as soon as we find work.
            sleep_s = min(IDLE_SLEEP * (2 ** min(consecutive_empty - 1, 5)), 1800)
            logger.info(
                "No un-enriched articles; sleeping %ss (empty streak %s)",
                sleep_s,
                consecutive_empty,
            )
            await asyncio.sleep(sleep_s)
        else:
            consecutive_empty = 0
            # Short breather between back-to-back batches so we don't peg
            # Ollama at 100% — concurrency is set inside the service.
            await asyncio.sleep(2)

    logger.info("Lane A worker stopped after %s batches", batches_run)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
