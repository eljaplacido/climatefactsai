#!/usr/bin/env python
"""Idempotent migration runner — Phase 8 (2026-05-24).

Reads every `infrastructure/database/migrations/versions/NNN_*.sql` file in
alphabetical order, applies the ones not yet recorded in a tracking table,
and commits each as a single transaction.

Usage (local Docker):
    DATABASE_URL=postgresql://postgres:postgres@localhost:5433/climatenews \
        python scripts/run_migrations.py

Usage (Cloud Build via cloud-sql-proxy):
    DATABASE_URL=postgresql://USER:PASS@127.0.0.1:5432/climatenews \
        python scripts/run_migrations.py

The tracker table `schema_migrations_applied` is created on first run. Each
migration runs inside one transaction — partial apply is impossible. A
migration that fails leaves no row in the tracker so the next run retries it.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "versions"
)

TRACKER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations_applied (
    version       VARCHAR(8) PRIMARY KEY,
    filename      VARCHAR(255) NOT NULL,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sha256        VARCHAR(64) NOT NULL
);
"""


def _version_of(filename: str) -> str:
    """`029_corporate_disclosures.sql` -> `029`."""
    m = re.match(r"^(\d+)_", filename)
    if not m:
        raise ValueError(f"Migration filename missing version prefix: {filename}")
    return m.group(1)


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dsn_from_env() -> str:
    """Pull DATABASE_URL and strip SQLAlchemy-style prefix if present."""
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(2)
    # Normalize: psycopg2 wants `postgresql://` not `postgresql+psycopg2://`
    return raw.replace("postgresql+psycopg2://", "postgresql://", 1)


def main() -> int:
    dsn = _dsn_from_env()
    if not MIGRATIONS_DIR.exists():
        print(f"ERROR: migrations dir not found: {MIGRATIONS_DIR}", file=sys.stderr)
        return 2

    files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        print(f"No migration files in {MIGRATIONS_DIR}")
        return 0

    print(f"Found {len(files)} migration file(s) in {MIGRATIONS_DIR}")
    print(f"Connecting to {dsn.split('@')[-1].split('?')[0]} ...")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn, conn.cursor() as cur:
            cur.execute(TRACKER_DDL)

        with conn.cursor() as cur:
            cur.execute("SELECT version, sha256 FROM schema_migrations_applied")
            applied = {v: s for v, s in cur.fetchall()}

        applied_count = 0
        skipped_count = 0
        for path in files:
            version = _version_of(path.name)
            sha = _file_sha256(path)
            if version in applied:
                if applied[version] != sha:
                    print(
                        f"  ! {path.name} (version {version}) sha mismatch — "
                        f"file has been modified since apply. Skipping but flagging."
                    )
                skipped_count += 1
                continue
            sql = path.read_text(encoding="utf-8")
            print(f"  > applying {path.name} (version {version}) ...")
            with conn, conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations_applied "
                    "(version, filename, sha256) VALUES (%s, %s, %s)",
                    (version, path.name, sha),
                )
            print(f"    OK")
            applied_count += 1

        print(
            f"\nDone — {applied_count} migration(s) applied, "
            f"{skipped_count} already up to date."
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
