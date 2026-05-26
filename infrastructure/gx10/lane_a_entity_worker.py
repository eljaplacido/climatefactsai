#!/usr/bin/env python3
"""Lane A entity extraction worker — runs on the GX10.

Sibling to lane_a_worker.py (article enrichment). Polls articles that
have NO entity links yet, extracts entities + relationships via Ollama,
populates `entities` / `article_entities` / `entity_relationships`.

WHY THIS WORKER NEEDS DEEPSEEK ENV SPOOFING
===========================================
EntityExtractionService._llm_extract calls
`app.domains.intelligence.llm_client.llm_chat()` which is hardcoded to
DeepSeek (no provider router). The asusgx10inferencestrategy.md flags
this as "Week 2-3 plumbing work: route through route_chat()". Until
that refactor lands, this worker re-points the DEEPSEEK_* env vars at
the local Ollama endpoint. Since Ollama is OpenAI-compatible, llm_chat
talks to it without code changes:

    DEEPSEEK_BASE_URL = http://localhost:11434/v1
    DEEPSEEK_API_KEY  = ollama
    DEEPSEEK_MODEL    = qwen2.5:7b-instruct

This is a worker-process-local hack — production Cloud Run still has
the real DEEPSEEK_API_KEY pointing at api.deepseek.com. Once
llm_chat gets a proper local-gx10 branch (mirroring what
article_enrichment_service has), delete the env override below.

Environment variables (worker tuning):
  DATABASE_URL                   Postgres connection (same as enrichment worker)
  CLILENS_LOCAL_GX10_BASE_URL    Default: http://localhost:11434/v1
  CLILENS_LOCAL_GX10_API_KEY     Default: "ollama"
  CLILENS_LOCAL_GX10_MODEL       Default: qwen2.5:7b-instruct
  GX10_ENTITY_BATCH_SIZE         Default: 5  (entity extraction is slower per article)
  GX10_ENTITY_IDLE_SLEEP_SEC     Default: 90
  GX10_ENTITY_MAX_BATCHES        Default: 0 (forever)
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Allow imports from the repo's src/backend (same pattern as lane_a_worker)
ROOT_DIR = Path(__file__).resolve().parents[2]
for p in (ROOT_DIR, ROOT_DIR / "src" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Env defaults for the local-gx10 endpoint (used by some service paths).
os.environ.setdefault("CLILENS_LOCAL_GX10_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("CLILENS_LOCAL_GX10_API_KEY", "ollama")
os.environ.setdefault("CLILENS_LOCAL_GX10_MODEL", "qwen2.5:7b-instruct")

# ---- DEEPSEEK env spoofing (see top-of-file rationale) ----
# Re-point llm_client to Ollama. Worker-process-local; doesn't affect prod.
_OLLAMA_BASE = os.environ["CLILENS_LOCAL_GX10_BASE_URL"]
_OLLAMA_MODEL = os.environ["CLILENS_LOCAL_GX10_MODEL"]
os.environ["DEEPSEEK_BASE_URL"] = _OLLAMA_BASE
os.environ["DEEPSEEK_API_KEY"] = os.environ["CLILENS_LOCAL_GX10_API_KEY"]
os.environ["DEEPSEEK_MODEL"] = _OLLAMA_MODEL

# Strip OpenAI/Anthropic so any hidden fallback chain stays local-only.
for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)

from shared.database import get_postgres
from app.domains.intelligence.entity_extraction_service import EntityExtractionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logger = logging.getLogger("lane-a-entity-worker")

BATCH_SIZE = int(os.getenv("GX10_ENTITY_BATCH_SIZE", "5"))
IDLE_SLEEP = int(os.getenv("GX10_ENTITY_IDLE_SLEEP_SEC", "90"))
MAX_BATCHES = int(os.getenv("GX10_ENTITY_MAX_BATCHES", "0"))


_shutdown = False


def _handle_signal(signum, _frame):
    global _shutdown
    logger.info(f"Received signal {signum}; finishing current article then exiting")
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def main() -> int:
    db = get_postgres()
    service = EntityExtractionService(db)

    logger.info(
        "Lane A entity worker starting | batch=%s idle=%ss max=%s model=%s ollama=%s",
        BATCH_SIZE, IDLE_SLEEP, MAX_BATCHES, _OLLAMA_MODEL, _OLLAMA_BASE,
    )

    # Sanity: Ollama reachable?
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{_OLLAMA_BASE}/models")
            r.raise_for_status()
        logger.info("Ollama reachable at %s", _OLLAMA_BASE)
    except Exception as exc:
        logger.error("Ollama unreachable at startup: %s", exc)
        return 2

    batches_run = 0
    consecutive_empty = 0
    while not _shutdown:
        batches_run += 1
        try:
            summary = await service.batch_extract_for_pending_articles(limit=BATCH_SIZE)
        except Exception as exc:
            logger.error("Batch failed: %s", exc, exc_info=True)
            await asyncio.sleep(min(IDLE_SLEEP, 30))
            continue

        logger.info(
            "Batch %s done | processed=%s failed=%s skipped=%s total_found=%s "
            "entities=%s relationships=%s",
            batches_run,
            summary.get("processed", 0),
            summary.get("failed", 0),
            summary.get("skipped", 0),
            summary.get("total_found", 0),
            summary.get("total_entities_extracted", 0),
            summary.get("total_relationships_extracted", 0),
        )

        if MAX_BATCHES and batches_run >= MAX_BATCHES:
            logger.info("Hit MAX_BATCHES=%s; exiting cleanly", MAX_BATCHES)
            break

        if summary.get("total_found", 0) == 0:
            consecutive_empty += 1
            sleep_s = min(IDLE_SLEEP * (2 ** min(consecutive_empty - 1, 5)), 1800)
            logger.info(
                "No un-linked articles; sleeping %ss (empty streak %s)",
                sleep_s, consecutive_empty,
            )
            await asyncio.sleep(sleep_s)
        else:
            consecutive_empty = 0
            await asyncio.sleep(3)

    logger.info("Lane A entity worker stopped after %s batches", batches_run)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
