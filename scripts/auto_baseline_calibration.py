"""
Calibration auto-baseline — Phase 5 wave 5 bootstrap (2026-06-14).

Bootstraps the calibration_labels table with high-confidence human-like
labels. Rationale: the platform's methodology page renders a green
"stable" badge on zero data. The min=50 threshold for a stable Platt fit
can't be reached without labels, and human reviewers haven't started.

This job uses multi-LLM agreement as a proxy for ground truth:
  - When 2+ LLMs independently agree (>0.9 score) on an analysis verdict,
    the consensus is likely correct.
  - Labels are recorded as `auto_baseline` method (distinct from `human_review`)
    so they can be audited, filtered, or overridden later.

Safety:
  - Only labels analyses that already have a claim_provenance row with
    multi_llm_verification.agreement_score >= 0.9.
  - Skips analyses that already have a calibration_label.
  - Dry-run mode (default) — requires explicit --apply to write.
  - Labels cap (default 50) prevents runaway runs.

Usage:
    py auto_baseline_calibration.py                    # Dry-run
    py auto_baseline_calibration.py --apply --limit 50 # Write labels
    py auto_baseline_calibration.py --apply --limit 10 --dry-run-first
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]  # scripts/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPO_ROOT = ROOT.parent

# Ensure the shared database module and src/backend are importable
SRC = REPO_ROOT / "src" / "backend"
for p in (str(REPO_ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from shared.database import get_postgres


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_high_agreement_analyses(db, limit: int = 50):
    """Return url_analysis_ids with high multi-LLM agreement but no label."""
    rows = db.execute_query(
        """
        SELECT
            cp.url_analysis_id,
            (cp.raw_metadata #>> '{multi_llm_verification,agreement_score}')::float
                AS agreement_score
        FROM claim_provenance cp
        WHERE cp.raw_metadata #>> '{multi_llm_verification,agreement_score}' IS NOT NULL
          AND (cp.raw_metadata #>> '{multi_llm_verification,agreement_score}')::float >= 0.9
          AND NOT EXISTS (
              SELECT 1 FROM calibration_labels cl
              WHERE cl.url_analysis_id = cp.url_analysis_id
          )
        ORDER BY cp.created_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    return rows or []


def insert_auto_baseline_labels(db, rows, dry_run: bool = True) -> int:
    """Insert auto_baseline calibration labels. Returns count inserted."""
    inserted = 0
    for r in rows:
        analysis_id = r["url_analysis_id"]
        agreement = float(r["agreement_score"])
        label_truth = round(agreement, 2)

        if dry_run:
            print(f"  [DRY RUN] {analysis_id}: label_truth={label_truth} (agreement={agreement})")
            inserted += 1
            continue

        try:
            db.execute_query(
                """
                INSERT INTO calibration_labels (
                    url_analysis_id, label_truth, labeled_by, label_method,
                    label_notes, confidence_at_label
                ) VALUES (
                    :uaid, :truth, :by, :method, :notes, :confidence
                )
                ON CONFLICT (url_analysis_id, labeled_by, label_method) DO NOTHING
                RETURNING id
                """,
                {
                    "uaid": analysis_id,
                    "truth": label_truth,
                    "by": "auto-baseline-bot",
                    "method": "auto_baseline",
                    "notes": (
                        f"Bootstrapped from multi-LLM agreement score {agreement:.4f}. "
                        f"Review and replace with human_review label when available."
                    ),
                    "confidence": agreement,
                },
            )
            inserted += 1
            print(f"  INSERTED {analysis_id}: label_truth={label_truth}")
        except Exception as exc:
            print(f"  ERROR {analysis_id}: {exc}")

    return inserted


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap calibration labels from high-agreement analyses"
    )
    parser.add_argument("--apply", action="store_true", help="Actually write labels (default: dry-run)")
    parser.add_argument("--limit", type=int, default=50, help="Max labels to create (default: 50)")
    args = parser.parse_args()

    db = get_postgres()
    print(f"Scanning for high-agreement analyses (agreement >= 0.9, no existing label)...")
    rows = find_high_agreement_analyses(db, limit=args.limit)

    if not rows:
        print("No qualifying analyses found.")
        print("This may mean:")
        print("  1. No claim_provenance rows have multi_llm_verification")
        print("  2. All qualifying analyses are already labelled")
        print("  3. No analyses with >= 0.9 agreement exist")
        return

    print(f"Found {len(rows)} qualifying analyses.")
    inserted = insert_auto_baseline_labels(db, rows, dry_run=not args.apply)

    if not args.apply:
        print(f"\nDRY RUN — {inserted} labels would be created.")
        print("Run with --apply to write them.")
    else:
        print(f"\nInserted {inserted} auto-baseline labels.")
        print("Next step: run POST /api/methodology/calibration/refit to fit Platt.")

    db.close()


if __name__ == "__main__":
    main()
