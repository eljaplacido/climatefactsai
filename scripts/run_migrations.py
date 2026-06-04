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


def assert_no_duplicate_versions(files) -> None:
    """Fail loudly if two migration files share a version prefix.

    A duplicate prefix is silently destructive: schema_migrations_applied keys on
    `version` (PK), so once one file with version NNN is applied, every other file
    with the same prefix is treated as already-applied and NEVER runs. That is
    exactly how 049's journalism-credibility seeds were skipped for weeks. Catch
    it before touching the DB rather than discovering it as a prod data gap.
    """
    seen: dict = {}
    dupes: list = []
    for path in files:
        name = getattr(path, "name", str(path))
        version = _version_of(name)
        if version in seen:
            dupes.append((version, seen[version], name))
        else:
            seen[version] = name
    if dupes:
        detail = "\n".join(f"  version {v}: {a}  &  {b}" for v, a, b in dupes)
        raise SystemExit(
            "FATAL: duplicate migration version prefix(es) — rename so every "
            "NNN_ prefix is unique (the tracker keys on the prefix, so a "
            f"collision silently skips a migration):\n{detail}"
        )


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


def _bootstrap_tracker(conn, files) -> int:
    """Mark migrations as pre-applied when their target tables already exist.

    This handles the bootstrap case: a long-lived DB that had migrations
    applied OUTSIDE this script (manually, via earlier tooling, or from a
    prior session). On first run of run_migrations.py against such a DB,
    we don't want to re-run those migrations — most aren't fully idempotent.

    Detection heuristic: for each migration, parse out the first
    `CREATE TABLE IF NOT EXISTS <name>` it declares. If the table is
    already present in the live DB, mark the migration as applied without
    running it. Migrations without a CREATE TABLE clause are skipped from
    bootstrap (they get applied normally next pass).
    """
    import re as _re

    create_table_re = _re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?([a-z_][a-z_0-9]*)",
        _re.IGNORECASE,
    )

    bootstrapped = 0
    with conn.cursor() as cur:
        for path in files:
            version = _version_of(path.name)
            cur.execute(
                "SELECT 1 FROM schema_migrations_applied WHERE version = %s",
                (version,),
            )
            if cur.fetchone():
                continue
            sql = path.read_text(encoding="utf-8")
            m = create_table_re.search(sql)
            if not m:
                continue
            table = m.group(1)
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            )
            if cur.fetchone():
                cur.execute(
                    "INSERT INTO schema_migrations_applied "
                    "(version, filename, sha256) VALUES (%s, %s, %s) "
                    "ON CONFLICT (version) DO NOTHING",
                    (version, path.name, _file_sha256(path)),
                )
                bootstrapped += 1
    conn.commit()
    return bootstrapped


def main() -> int:
    dsn = _dsn_from_env()
    if not MIGRATIONS_DIR.exists():
        print(f"ERROR: migrations dir not found: {MIGRATIONS_DIR}", file=sys.stderr)
        return 2

    files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        print(f"No migration files in {MIGRATIONS_DIR}")
        return 0

    # Preflight: a duplicate version prefix silently skips a migration (see the
    # function docstring). Abort before connecting rather than corrupt coverage.
    assert_no_duplicate_versions(files)

    # Optional MIGRATIONS_FROM env var: hard floor on which versions to apply.
    # Useful for one-shot bootstrap when older migrations are known-applied
    # but their target tables can't be auto-detected.
    floor = os.environ.get("MIGRATIONS_FROM")
    if floor:
        files = [p for p in files if _version_of(p.name) >= floor]
        print(f"MIGRATIONS_FROM={floor} — restricted to {len(files)} file(s)")

    print(f"Found {len(files)} migration file(s) in {MIGRATIONS_DIR}")
    print(f"Connecting to {dsn.split('@')[-1].split('?')[0]} ...")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn, conn.cursor() as cur:
            cur.execute(TRACKER_DDL)

        # Bootstrap detection: mark migrations whose target tables already
        # exist as applied without re-running them.
        bootstrapped = _bootstrap_tracker(conn, files)
        if bootstrapped:
            print(
                f"Bootstrap: detected {bootstrapped} migration(s) whose target "
                f"tables already exist — marked applied without re-running."
            )

        with conn.cursor() as cur:
            cur.execute("SELECT version, sha256 FROM schema_migrations_applied")
            applied = {v: s for v, s in cur.fetchall()}

        # If MIGRATIONS_TOLERATE_ERRORS=true, idempotency failures (duplicate
        # table / column / unique violation) are treated as "already applied"
        # — we mark the migration applied and continue. Useful for first-run
        # bootstrap when a DB has data from a pre-tracker world.
        tolerate = os.environ.get("MIGRATIONS_TOLERATE_ERRORS", "").lower() in (
            "1", "true", "yes",
        )
        TOLERATED_CODES = {
            "42P07",  # duplicate_table
            "42701",  # duplicate_column
            "42710",  # duplicate_object (index, etc.)
            "23505",  # unique_violation
            "42P06",  # duplicate_schema
            "42723",  # duplicate_function
        }

        applied_count = 0
        skipped_count = 0
        tolerated_count = 0
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

            # Per-migration opt-out — a migration can include `-- @notolerate`
            # on its own line (typically the first/second line) to demand
            # loud-fail behaviour regardless of MIGRATIONS_TOLERATE_ERRORS.
            # Added 2026-05-25 after mig 043 silently tolerated 23505 and
            # left the dedup half-done in production (see
            # feedback_migration_tolerate_errors memory).
            notolerate = bool(
                re.search(r"^\s*--\s*@notolerate\s*$", sql, re.MULTILINE)
            )
            local_tolerate = tolerate and not notolerate
            if notolerate:
                print(f"    @notolerate directive — failures will be loud")

            print(f"  > applying {path.name} (version {version}) ...")
            try:
                with conn, conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations_applied "
                        "(version, filename, sha256) VALUES (%s, %s, %s)",
                        (version, path.name, sha),
                    )
                print(f"    OK")
                applied_count += 1
            except psycopg2.Error as exc:
                pgcode = getattr(exc, "pgcode", None)
                if local_tolerate and pgcode in TOLERATED_CODES:
                    print(
                        f"    TOLERATED ({pgcode}: {type(exc).__name__}) — "
                        f"marking as already-applied"
                    )
                    # Rollback the failed tx, mark the migration applied
                    conn.rollback()
                    with conn, conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO schema_migrations_applied "
                            "(version, filename, sha256) VALUES (%s, %s, %s) "
                            "ON CONFLICT (version) DO NOTHING",
                            (version, path.name, sha),
                        )
                    tolerated_count += 1
                else:
                    print(f"    FAILED: {pgcode}: {exc}")
                    raise

        print(
            f"\nDone — {applied_count} applied, "
            f"{tolerated_count} tolerated, "
            f"{skipped_count} already up to date."
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
