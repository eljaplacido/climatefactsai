from shared.claims_status_manager import ClaimsStatusManager


class _FakeDB:
    def __init__(self, stale_rows, update_rowcount=1):
        self._stale_rows = stale_rows
        self._update_rowcount = update_rowcount
        self.query_calls = []
        self.update_calls = []

    def execute_query(self, query, params=None):
        self.query_calls.append((query, params or {}))
        return list(self._stale_rows)

    def execute_update(self, query, params=None):
        self.update_calls.append((query, params or {}))
        return self._update_rowcount


def test_reset_stale_processing_resets_articles_to_pending():
    db = _FakeDB(stale_rows=[{"article_id": "a-1"}, {"article_id": "a-2"}])
    manager = ClaimsStatusManager(db)

    recovered = manager.reset_stale_processing(stale_minutes=45, limit=10)

    assert recovered == 2
    assert len(db.query_calls) == 1
    assert len(db.update_calls) == 2

    for _, params in db.update_calls:
        assert params["status"] == ClaimsStatusManager.STATUS_PENDING
        assert params["processing_status"] == ClaimsStatusManager.STATUS_PROCESSING
        assert "exceeded 45 minutes" in params["error_message"]


def test_reset_stale_processing_skips_rows_without_article_id():
    db = _FakeDB(stale_rows=[{}, {"article_id": "a-1"}])
    manager = ClaimsStatusManager(db)

    recovered = manager.reset_stale_processing(stale_minutes=30, limit=5)

    assert recovered == 1
    assert len(db.update_calls) == 1
