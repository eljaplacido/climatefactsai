#!/usr/bin/env python3
"""Embedding worker — runs on the GX10, polls Cloud SQL for articles missing a
bge-m3 embedding, generates them locally via Ollama, writes them back.

Companion to lane_a_worker.py (enrichment) — same resident-on-GX10 pattern:
Cloud Run cannot reach the GX10 (egress blocks on Funnel + Cloudflare Tunnel
from europe-west4), so the GX10 polls Cloud SQL directly and embeds locally.
This is the seq-6 "embeddings -> GX10" write path: free, multilingual (bge-m3),
no OpenAI ada-002 spend.

Workflow:
  1. Connect to Cloud SQL via DATABASE_URL (public IP + authorized network, or
     cloud-sql-proxy on localhost).
  2. SELECT articles WHERE embedding_bge_m3 IS NULL (EmbeddingService.batch_...).
  3. For each, POST localhost:11434/v1/embeddings (model bge-m3) and store the
     1024-dim vector in articles.embedding_bge_m3.
  4. Sleep with backoff when the corpus is caught up.

One-time setup on the GX10 (the part the operator runs):
    ollama pull bge-m3
    DATABASE_URL=postgres://... python infrastructure/gx10/embedding_worker.py

Environment variables:
  DATABASE_URL                   Postgres connection (Cloud SQL via proxy / pub IP)
  CLILENS_LOCAL_GX10_BASE_URL    Default: http://localhost:11434/v1
  CLILENS_LOCAL_GX10_API_KEY     Default: "ollama"
  CLILENS_EMBEDDING_MODEL        Default: bge-m3
  GX10_EMBED_BATCH_SIZE          Default: 25  (per-cycle batch)
  GX10_EMBED_IDLE_SLEEP_SEC      Default: 60  (base sleep when no work)
  GX10_EMBED_MAX_BATCHES         Default: 0   (0 = forever)
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Make the repo's modules importable (worker runs from inside the cloned repo).
ROOT_DIR = Path(__file__).resolve().parents[2]
for p in (ROOT_DIR, ROOT_DIR / "src" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("CLILENS_LOCAL_GX10_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("CLILENS_LOCAL_GX10_API_KEY", "ollama")
os.environ.setdefault("CLILENS_EMBEDDING_MODEL", "bge-m3")

from shared.database import get_postgres
from app.domains.content.embedding_service import EmbeddingService


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
logger = logging.getLogger("gx10-embedding-worker")

BATCH_SIZE = int(os.getenv("GX10_EMBED_BATCH_SIZE", "25"))
IDLE_SLEEP = int(os.getenv("GX10_EMBED_IDLE_SLEEP_SEC", "60"))
MAX_BATCHES = int(os.getenv("GX10_EMBED_MAX_BATCHES", "0"))

_shutdown = False


def _handle_signal(signum, _frame):
    global _shutdown
    logger.info(f"Received signal {signum}; finishing current batch then exiting")
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def main() -> int:
    db = get_postgres()
    service = EmbeddingService(db)
    base_url = os.environ["CLILENS_LOCAL_GX10_BASE_URL"]
    model = os.environ["CLILENS_EMBEDDING_MODEL"]

    logger.info(
        "Embedding worker starting | batch=%s idle=%ss model=%s ollama=%s",
        BATCH_SIZE, IDLE_SLEEP, model, base_url,
    )

    # Fail loudly if Ollama / the embedding model is unreachable, rather than
    # silently writing nothing. A single embed call is the cleanest smoke test.
    probe = await service.generate_bge_m3_embedding("climate smoke test")
    if not probe:
        logger.error(
            "Embedding smoke test failed — is Ollama up and `ollama pull %s` done?",
            model,
        )
        return 2
    logger.info("Ollama reachable; %s returns %d-dim vectors", model, len(probe))

    batches_run = 0
    consecutive_empty = 0
    while not _shutdown:
        batches_run += 1
        try:
            summary = await service.batch_populate_bge_m3(limit=BATCH_SIZE)
        except Exception as exc:
            logger.error("Batch failed: %s", exc, exc_info=True)
            await asyncio.sleep(min(IDLE_SLEEP, 30))
            continue

        logger.info(
            "Batch %s | found=%s processed=%s failed=%s",
            batches_run,
            summary.get("total_found", 0),
            summary.get("processed", 0),
            summary.get("failed", 0),
        )
        send_telegram(
            f"📊 Embedding batch {batches_run} | "
            f"{summary.get('processed', 0)} embedded, {summary.get('failed', 0)} failed"
        )

        if MAX_BATCHES and batches_run >= MAX_BATCHES:
            logger.info("Hit MAX_BATCHES=%s; exiting cleanly", MAX_BATCHES)
            break

        found = summary.get("total_found", 0)
        processed = summary.get("processed", 0)
        # Back off when caught up (found==0) OR when no article in the batch could
        # be embedded (processed==0, e.g. Ollama 500s on a permanently-bad row) —
        # otherwise a single failing article hot-loops the GPU forever.
        if found == 0 or processed == 0:
            consecutive_empty += 1
            reason = "no articles to embed" if found == 0 else f"batch made no progress ({found} failed)"
            sleep_s = min(IDLE_SLEEP * (2 ** min(consecutive_empty - 1, 5)), 1800)
            logger.info("%s; sleeping %ss (streak %s)", reason, sleep_s, consecutive_empty)
            await asyncio.sleep(sleep_s)
        else:
            consecutive_empty = 0
            await asyncio.sleep(1)

    logger.info("Embedding worker stopped after %s batches", batches_run)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
