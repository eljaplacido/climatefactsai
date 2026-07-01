"""ML-03 — structural pins for the quarantine + backfill migrations.

No Postgres needed: asserts the migration SQL carries the guarantees the task
requires (quarantine table created; backfill is @notolerate, reverses claims,
nulls both embeddings, hides via is_off_topic, keys on the consent-wall
signature, and never CREATE-TABLEs an existing table).

Run: python -m pytest tests/unit/test_ml03_backfill_migration.py -o addopts=""
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS = REPO_ROOT / "infrastructure" / "database" / "migrations" / "versions"
QUARANTINE = VERSIONS / "073_article_ingest_quarantine.sql"
BACKFILL = VERSIONS / "074_backfill_consent_wall_poison.sql"
CONSENT_MD5 = "94a38797a13f417b263c9c7c78c93f08"


def test_quarantine_migration_creates_table():
    sql = QUARANTINE.read_text(encoding="utf-8").lower()
    assert "create table if not exists article_ingest_quarantine" in sql
    for col in ("url", "source_name", "reason", "category", "raw_input", "created_at"):
        assert col in sql, f"quarantine table missing {col}"


def test_backfill_is_notolerate():
    sql = BACKFILL.read_text(encoding="utf-8")
    assert "-- @notolerate" in sql, "backfill must fail loud, not be silently tolerated"


def test_backfill_reverses_claims_and_hides_rows():
    import re
    raw = BACKFILL.read_text(encoding="utf-8").lower()
    sql = re.sub(r"\s+", " ", raw)  # normalise the alignment whitespace
    assert "delete from claims" in sql
    assert "is_off_topic = true" in sql
    assert "embedding = null" in sql
    assert "embedding_bge_m3 = null" in sql
    assert CONSENT_MD5 in sql, "backfill must key on the consent-wall md5 signature"


def test_backfill_does_not_create_existing_tables():
    sql = BACKFILL.read_text(encoding="utf-8").lower()
    for tbl in ("articles", "claims", "fact_checks"):
        assert f"create table if not exists {tbl}" not in sql
        assert f"create table {tbl}" not in sql


@pytest.mark.parametrize("path", [QUARANTINE, BACKFILL])
def test_migration_files_exist(path):
    assert path.exists(), f"missing migration {path.name}"
