from types import SimpleNamespace

from app.tasks import fact_check_pipeline as pipeline


class _FakeDB:
    def __init__(self, pending_rows):
        self.pending_rows = pending_rows
        self.query_calls = []
        self.update_calls = []

    def execute_query(self, query, params=None):
        self.query_calls.append((query, params or {}))
        normalized = " ".join(query.split()).lower()
        if "from articles" in normalized and "claims_status" in normalized and "limit :batch_size" in normalized:
            return list(self.pending_rows)
        if "select summary_text" in normalized:
            return []
        return []

    def execute_update(self, query, params=None):
        self.update_calls.append((query, params or {}))
        return 1


class _FakeStatusManager:
    stale_to_return = 0

    def __init__(self, db):
        self.db = db

    def reset_stale_processing(self, stale_minutes=120, limit=200):
        return self.stale_to_return


class _FakeVerificationService:
    def __init__(self, db):
        self.db = db

    async def verify_article(self, article_id):
        return SimpleNamespace(
            status="failed",
            error_message="upstream llm unavailable",
            claims_extracted=0,
            claims_verified=0,
            claims_disputed=0,
        )


class _FakeSourceProfileService:
    def __init__(self, db):
        self.db = db

    def update_claim_stats(self, source_domain, verified=0, disputed=0):
        return None


def _invoke_task(task, **kwargs):
    return task.run(**kwargs)


def test_auto_verify_includes_stale_recovery_count(monkeypatch):
    fake_db = _FakeDB(pending_rows=[])
    _FakeStatusManager.stale_to_return = 3

    monkeypatch.setattr(pipeline, "get_db", lambda: fake_db)
    monkeypatch.setattr(pipeline, "ClaimsStatusManager", _FakeStatusManager)

    result = _invoke_task(pipeline.auto_verify_pending_articles, batch_size=5)

    assert result["articles_found"] == 0
    assert result["stale_recovered"] == 3


def test_auto_verify_marks_non_completed_results_failed(monkeypatch):
    pending = [{
        "article_id": "art-1",
        "title": "t",
        "url": "https://news.example.com/a",
        "source_name": "news.example.com",
    }]
    fake_db = _FakeDB(pending_rows=pending)
    _FakeStatusManager.stale_to_return = 0

    monkeypatch.setattr(pipeline, "get_db", lambda: fake_db)
    monkeypatch.setattr(pipeline, "ClaimsStatusManager", _FakeStatusManager)
    monkeypatch.setattr(pipeline, "VerificationService", _FakeVerificationService)
    monkeypatch.setattr(pipeline, "SourceProfileService", _FakeSourceProfileService)

    result = _invoke_task(pipeline.auto_verify_pending_articles, batch_size=1)

    assert result["verified"] == 0
    assert result["failed"] == 1
    assert result["results"][0]["status"] == "failed"
    assert "upstream llm unavailable" in result["results"][0]["error"]


def test_default_verify_batch_is_25():
    """Audit item 7: default throughput raised 10 -> 25."""
    assert pipeline._DEFAULT_VERIFY_BATCH == 25


def test_auto_verify_default_batch_size_reads_env(monkeypatch):
    """When called with no batch_size (the Cloud Scheduler path), the task
    resolves it from FACT_CHECK_BATCH_SIZE so ops can tune throughput without
    a redeploy (audit item 7)."""
    monkeypatch.setenv("FACT_CHECK_BATCH_SIZE", "7")
    fake_db = _FakeDB(pending_rows=[])
    _FakeStatusManager.stale_to_return = 0

    monkeypatch.setattr(pipeline, "get_db", lambda: fake_db)
    monkeypatch.setattr(pipeline, "ClaimsStatusManager", _FakeStatusManager)

    _invoke_task(pipeline.auto_verify_pending_articles)  # no batch_size

    select_params = [
        params for (q, params) in fake_db.query_calls
        if "limit :batch_size" in " ".join(q.split()).lower()
    ]
    assert select_params, "expected a pending-articles SELECT"
    assert select_params[0]["batch_size"] == 7


def test_retry_failed_verifications_reports_stale_recovery(monkeypatch):
    class _RetryDB(_FakeDB):
        def execute_query(self, query, params=None):
            self.query_calls.append((query, params or {}))
            normalized = " ".join(query.split()).lower()
            if "where claims_status = 'failed'" in normalized:
                return []
            return []

    fake_db = _RetryDB(pending_rows=[])
    _FakeStatusManager.stale_to_return = 2

    monkeypatch.setattr(pipeline, "get_db", lambda: fake_db)
    monkeypatch.setattr(pipeline, "ClaimsStatusManager", _FakeStatusManager)

    result = _invoke_task(pipeline.retry_failed_verifications, batch_size=2)

    assert result["retried"] == 0
    assert result["stale_recovered"] == 2
