"""
Backfill article enrichment for the local DB.

Iterates every article where enriched_at IS NULL, runs
ArticleEnrichmentService.enrich_article(...), and (when
CLILENS_TRAINING_DATASET_PATH is set) emits a JSONL training row per
LLM call for later distillation into a smaller model.

Usage (PowerShell):
    $env:CLILENS_ENRICHMENT_PROVIDER = "deepseek"
    $env:CLILENS_TRAINING_DATASET_PATH = "data/training/enrichment_dataset.jsonl"
    python scripts/backfill_enrichment.py --limit 5         # smoke test
    python scripts/backfill_enrichment.py --batch-size 50   # full run

Flags:
    --limit N          Stop after N articles total (0 = no cap; default 0).
    --batch-size N     Articles fetched per DB pass (default 50).
    --concurrency N    Parallel enrichments per batch (default 1; raise to 4-8
                       for DeepSeek which tolerates moderate concurrency).
    --dry-run          Count un-enriched articles but don't call any LLM.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Bootstrap import paths (same pattern api/main.py uses)
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_BACKEND = ROOT_DIR / "src" / "backend"
for p in (ROOT_DIR, SRC_BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT_DIR / ".env")

from shared.database import get_postgres
from app.domains.content.article_enrichment_service import ArticleEnrichmentService


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after N articles total (0 = no cap)")
    p.add_argument("--batch-size", type=int, default=50,
                   help="Articles fetched per DB pass")
    p.add_argument("--concurrency", type=int, default=1,
                   help="Parallel enrichments per batch (DeepSeek-safe up to ~8)")
    p.add_argument("--dry-run", action="store_true",
                   help="Count un-enriched articles but don't call any LLM")
    p.add_argument("--min-text-len", type=int, default=0,
                   help="Skip articles whose extracted_text is shorter than N chars. "
                        "Use 500+ when building training data so the LLM has real body "
                        "text to summarise rather than fabricating from a title.")
    return p.parse_args()


def count_pending(db, min_text_len: int = 0) -> int:
    rows = db.execute_query(
        """SELECT COUNT(*) AS n FROM articles
            WHERE enriched_at IS NULL AND is_synthetic = FALSE
              AND LENGTH(COALESCE(extracted_text, '')) >= :minlen""",
        {"minlen": min_text_len},
    )
    return int(rows[0]["n"]) if rows else 0


def fetch_batch(db, batch_size: int, min_text_len: int = 0):
    return db.execute_query(
        """SELECT article_id, title, COALESCE(extracted_text, '') AS extracted_text,
                  COALESCE(source_name, '') AS source_name,
                  COALESCE(country_code, 'FI') AS country_code,
                  content_category
             FROM articles
            WHERE enriched_at IS NULL
              AND is_synthetic = FALSE
              AND LENGTH(COALESCE(extracted_text, '')) >= :minlen
            ORDER BY created_at DESC
            LIMIT :lim""",
        {"lim": batch_size, "minlen": min_text_len},
    )


async def enrich_one(service: ArticleEnrichmentService, row) -> tuple[str, str]:
    """Returns (article_id, status) where status is processed | skipped | failed."""
    article_id = str(row["article_id"])
    text = row.get("extracted_text", "")
    if not text or len(text.strip()) < 50:
        return article_id, "skipped"
    try:
        await service.enrich_article(
            article_id=article_id,
            title=row.get("title", ""),
            extracted_text=text,
            source_name=row.get("source_name", ""),
            country_code=row.get("country_code", "FI"),
            content_category=row.get("content_category"),
        )
        return article_id, "processed"
    except Exception as exc:
        print(f"  [FAIL] {article_id[:8]}... {exc}", flush=True)
        return article_id, "failed"


async def run(args: argparse.Namespace) -> int:
    db = get_postgres()
    pending = count_pending(db, min_text_len=args.min_text_len)
    print(
        f"Articles eligible (real, non-synthetic, text>={args.min_text_len}c, "
        f"enriched_at IS NULL): {pending}",
        flush=True,
    )

    if args.dry_run or pending == 0:
        return 0

    cap = args.limit if args.limit > 0 else pending
    target = min(cap, pending)
    print(
        f"Plan: enrich up to {target} articles "
        f"(batch_size={args.batch_size}, concurrency={args.concurrency}, "
        f"min_text_len={args.min_text_len}, "
        f"provider={os.getenv('CLILENS_ENRICHMENT_PROVIDER') or 'auto'}, "
        f"jsonl={os.getenv('CLILENS_TRAINING_DATASET_PATH') or '<not set>'})",
        flush=True,
    )

    totals = {"processed": 0, "skipped": 0, "failed": 0}
    start = time.time()

    # Each batch uses ONE service instance per concurrent slot. Per-article
    # state on the service (current_article_id, providers_used) is reset at
    # the top of enrich_article, so a fresh service per coroutine is the
    # safe way to fan out.
    while totals["processed"] + totals["skipped"] + totals["failed"] < target:
        remaining = target - (totals["processed"] + totals["skipped"] + totals["failed"])
        rows = fetch_batch(db, min(args.batch_size, remaining), min_text_len=args.min_text_len)
        if not rows:
            break

        # Chunk the batch by concurrency
        for i in range(0, len(rows), args.concurrency):
            chunk = rows[i : i + args.concurrency]
            services = [ArticleEnrichmentService(db) for _ in chunk]
            coros = [enrich_one(svc, row) for svc, row in zip(services, chunk)]
            results = await asyncio.gather(*coros, return_exceptions=False)
            for _, status in results:
                totals[status] = totals.get(status, 0) + 1

            done = totals["processed"] + totals["skipped"] + totals["failed"]
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (target - done) / rate if rate > 0 else float("inf")
            print(
                f"  progress: {done}/{target} "
                f"(processed={totals['processed']} skipped={totals['skipped']} failed={totals['failed']}) "
                f"rate={rate:.2f}/s eta={eta/60:.1f}min",
                flush=True,
            )

    elapsed = time.time() - start
    print(
        f"\nDone in {elapsed:.1f}s — "
        f"processed={totals['processed']} skipped={totals['skipped']} failed={totals['failed']}",
        flush=True,
    )
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(run(args)))
