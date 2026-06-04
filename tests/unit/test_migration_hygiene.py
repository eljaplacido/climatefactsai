"""Migration hygiene guard (seq-16).

The migration tracker (schema_migrations_applied) keys on the NNN version prefix
as PRIMARY KEY. Two files sharing a prefix means the second is treated as
already-applied and NEVER runs — which is how 049's journalism-credibility seeds
were silently skipped. This pins "every migration prefix is unique" so the
collision class can't regress, and exercises the run_migrations preflight guard.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "infrastructure" / "database" / "migrations" / "versions"


def _versions():
    files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert files, f"no migration files found in {MIGRATIONS_DIR}"
    return [(re.match(r"^(\d+)_", p.name).group(1), p.name) for p in files]


def test_no_duplicate_version_prefixes():
    counts = Counter(v for v, _ in _versions())
    dupes = {v: c for v, c in counts.items() if c > 1}
    assert not dupes, (
        f"duplicate migration version prefix(es) {sorted(dupes)} — the tracker "
        f"keys on the prefix, so a collision silently skips a migration. "
        f"Rename so each NNN_ prefix is unique."
    )


def test_every_migration_has_a_numeric_prefix():
    for path in MIGRATIONS_DIR.glob("*.sql"):
        assert re.match(r"^\d{3}_", path.name), (
            f"migration {path.name} lacks a 3-digit version prefix — "
            f"run_migrations only globs [0-9][0-9][0-9]_*.sql"
        )


def test_preflight_guard_raises_on_duplicate():
    # Skip cleanly where psycopg2 (a run_migrations import) isn't installed.
    pytest.importorskip("psycopg2")
    from scripts.run_migrations import assert_no_duplicate_versions

    class _P:
        def __init__(self, name):
            self.name = name

    # No SystemExit on a unique set.
    assert_no_duplicate_versions([_P("001_a.sql"), _P("002_b.sql")])

    # SystemExit on a collision.
    with pytest.raises(SystemExit):
        assert_no_duplicate_versions([_P("049_a.sql"), _P("049_b.sql")])
