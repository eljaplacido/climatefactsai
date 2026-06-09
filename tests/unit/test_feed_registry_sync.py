"""P0 #2 guard — sync_feed_registry_from_code seeds the in-code feeds into
rss_feed_registry idempotently, normalizes country codes, and never disturbs
existing rows. Uses a fake DB (no Postgres needed)."""

from __future__ import annotations

from app.domains.content.data_sources.rss_adapter import sync_feed_registry_from_code


class _FakeDB:
    """Minimal stand-in: tracks existing URLs/names and records inserts."""

    def __init__(self, existing_urls=None, existing_names=None):
        self.urls = set(existing_urls or [])
        self.names = set(existing_names or [])
        self.inserted = []

    def execute_query(self, sql, params):
        if params.get("u") in self.urls or params.get("n") in self.names:
            return [{"exists": 1}]
        return []

    def execute_update(self, sql, params):
        self.inserted.append(params)
        # The row now exists — so a second sync pass is a no-op (idempotency).
        self.urls.add(params["url"])
        self.names.add(params["name"])


def test_sync_seeds_missing_country_feeds():
    db = _FakeDB()
    result = sync_feed_registry_from_code(db)
    assert result["total_in_code"] >= 200
    assert result["inserted"] == result["total_in_code"] - result["skipped_existing"]
    seeded_codes = {row["cc"] for row in db.inserted}
    # The previously-zero-coverage countries now get real feeds.
    for cc in ("AU", "ZA", "NG", "EG", "SA"):
        assert cc in seeded_codes, f"{cc} should be seeded"


def test_pan_regional_codes_normalized_not_truncated():
    db = _FakeDB()
    sync_feed_registry_from_code(db)
    inserted_codes = {row["cc"] for row in db.inserted}
    # No pan-regional or truncated-wrong code is ever written.
    for bad in ("XX-AF", "XX-LA", "XX-AS", "XX-ME"):
        assert bad not in inserted_codes
    # The pan-regional feeds still land (as 'XX') with the region preserved.
    xx_rows = [r for r in db.inserted if r["cc"] == "XX"]
    assert xx_rows, "pan-regional feeds should be seeded as XX"
    assert any(r.get("region") for r in xx_rows)


def test_sync_is_idempotent():
    db = _FakeDB()
    first = sync_feed_registry_from_code(db)
    second = sync_feed_registry_from_code(db)
    assert first["inserted"] > 0
    assert second["inserted"] == 0
    assert second["skipped_existing"] == second["total_in_code"]


def test_existing_rows_not_reinserted():
    # Seed one known feed as already-present; it must be skipped.
    db = _FakeDB(existing_names={"African Arguments"})
    result = sync_feed_registry_from_code(db)
    inserted_names = {row["name"] for row in db.inserted}
    assert "African Arguments" not in inserted_names
    assert result["skipped_existing"] >= 1
