"""
One-shot source credibility tier seed — applies migration 027 data.

Run:  python scripts/seed_source_tiers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC_BACKEND))

from shared.database import get_postgres

MIGRATION_SQL = ROOT / "infrastructure" / "database" / "migrations" / "versions" / "027_source_credibility_tiers.sql"


def main() -> None:
    if not MIGRATION_SQL.exists():
        print(f"Migration file not found: {MIGRATION_SQL}")
        sys.exit(1)

    sql = MIGRATION_SQL.read_text(encoding="utf-8")
    db = get_postgres()

    db.execute_raw(sql)
    print("source_credibility_tiers seeded successfully.")


if __name__ == "__main__":
    main()
