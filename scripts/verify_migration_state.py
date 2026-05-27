#!/usr/bin/env python3
"""Verify critical database state after migrations applied.

Runs after `scripts/run_migrations.py` in cloudbuild.yaml so the deploy
fails fast if a migration silently no-op'd. Designed to catch the
mig-049-class of bug where ON CONFLICT DO NOTHING masked a substantive
upgrade (50 source_credibility_tiers were supposed to be UPGRADED to
T1/T2 but instead 0 changed; runner reported SUCCESS).

Each check returns (ok, message). On any failure, exits non-zero so
Cloud Build halts the deploy. Idempotent — safe to rerun.

Checks live in CRITICAL_INVARIANTS below. To add a new one: append a
function returning (bool, str). Keep them defensive: prefer ">=" over
"==" so adding rows doesn't break the assertion.

Environment:
    DATABASE_URL   required, postgresql:// connection string

Exit codes:
    0   all assertions passed
    1   at least one invariant violated
    2   couldn't connect to database
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Tuple

try:
    import psycopg2
except ImportError:
    print("[verify-migration-state] psycopg2 not installed", file=sys.stderr)
    sys.exit(2)


CheckResult = Tuple[bool, str]
Check = Callable[["psycopg2.extensions.cursor"], CheckResult]


def _scalar(cur, sql: str) -> int:
    cur.execute(sql)
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def check_source_credibility_tiers_populated(cur) -> CheckResult:
    n = _scalar(cur, "SELECT COUNT(*) FROM source_credibility_tiers")
    if n >= 100:
        return True, f"source_credibility_tiers: {n} rows (>=100)"
    return False, f"source_credibility_tiers has only {n} rows; expected >=100"


def check_rss_feed_registry_active(cur) -> CheckResult:
    n = _scalar(
        cur,
        "SELECT COUNT(*) FROM rss_feed_registry WHERE is_active = true",
    )
    if n >= 150:
        return True, f"rss_feed_registry: {n} active feeds (>=150)"
    return False, f"rss_feed_registry has only {n} active feeds; expected >=150"


def check_t1_sources_exist(cur) -> CheckResult:
    """Mig 049 was supposed to upgrade ~10 outlets to T1.

    The original ON CONFLICT DO NOTHING silently skipped them; mig 054
    fixed the data. Verify T1 actually exists post-migrations."""
    n = _scalar(
        cur,
        "SELECT COUNT(*) FROM source_credibility_tiers WHERE tier = 'T1'",
    )
    if n >= 5:
        return True, f"T1 source tier: {n} rows (>=5)"
    return False, f"T1 source tier has only {n} rows; expected >=5"


def check_default_research_topics(cur) -> CheckResult:
    """Mig 048 seeds the default-research-topics list."""
    n = _scalar(cur, "SELECT COUNT(*) FROM default_research_topics")
    if n >= 5:
        return True, f"default_research_topics: {n} rows (>=5)"
    return False, f"default_research_topics has only {n} rows; expected >=5"


def check_topic_feedback_schema(cur) -> CheckResult:
    """Mig 050 + 055 require the topic_feedback table + indexes."""
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
           WHERE table_name = 'topic_feedback'
        )
        """
    )
    exists = bool(cur.fetchone()[0])
    if not exists:
        return False, "topic_feedback table missing"
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
         WHERE table_name = 'topic_feedback'
           AND column_name IN
               ('article_id','verdict','off_topic_category','reporter_id')
        """
    )
    cols = int(cur.fetchone()[0])
    if cols < 4:
        return False, f"topic_feedback missing required columns ({cols}/4)"
    return True, "topic_feedback schema OK"


def check_articles_table_has_source_url(cur) -> CheckResult:
    """Mig 046 added source_url_status."""
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
         WHERE table_name = 'articles'
           AND column_name IN ('source_url_status', 'source_url_checked_at')
        """
    )
    cols = int(cur.fetchone()[0])
    if cols == 2:
        return True, "articles has source_url_{status,checked_at}"
    return False, f"articles missing source_url_* columns ({cols}/2)"


def check_companies_seed(cur) -> CheckResult:
    """Mig 034 + 043 + 044 should have 200+ corporate disclosures."""
    n = _scalar(cur, "SELECT COUNT(*) FROM companies")
    if n >= 100:
        return True, f"companies: {n} rows (>=100)"
    return False, f"companies has only {n} rows; expected >=100"


def check_knowledge_graph_schema(cur) -> CheckResult:
    """Mig 013 + 049 create the KG entity tables."""
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
         WHERE table_name IN
               ('entities', 'article_entities', 'entity_relationships')
        """
    )
    tables = int(cur.fetchone()[0])
    if tables == 3:
        return True, "knowledge-graph tables present (entities, article_entities, entity_relationships)"
    return False, f"KG schema incomplete ({tables}/3 tables)"


CRITICAL_INVARIANTS: list[tuple[str, Check]] = [
    ("source_credibility_tiers_populated", check_source_credibility_tiers_populated),
    ("rss_feed_registry_active", check_rss_feed_registry_active),
    ("t1_sources_exist", check_t1_sources_exist),
    ("default_research_topics", check_default_research_topics),
    ("topic_feedback_schema", check_topic_feedback_schema),
    ("articles_source_url_columns", check_articles_table_has_source_url),
    ("companies_seed", check_companies_seed),
    ("knowledge_graph_schema", check_knowledge_graph_schema),
]


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[verify-migration-state] DATABASE_URL not set", file=sys.stderr)
        return 2

    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        print(f"[verify-migration-state] connect failed: {e}", file=sys.stderr)
        return 2

    failures: list[str] = []
    with conn:
        with conn.cursor() as cur:
            for name, check in CRITICAL_INVARIANTS:
                try:
                    ok, msg = check(cur)
                except Exception as e:
                    ok = False
                    msg = f"check raised: {type(e).__name__}: {e}"
                marker = "[OK]" if ok else "[FAIL]"
                print(f"{marker} {name}: {msg}")
                if not ok:
                    failures.append(f"{name} — {msg}")

    conn.close()

    if failures:
        print("", file=sys.stderr)
        print(
            f"[verify-migration-state] {len(failures)} invariant(s) failed:",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nDeploy halted. Inspect the failing assertion above, then "
            "re-trigger after the underlying migration is fixed.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\n[verify-migration-state] all "
        f"{len(CRITICAL_INVARIANTS)} invariants passed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
