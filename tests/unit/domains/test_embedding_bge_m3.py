"""Unit tests for the seq-6 bge-m3 embedding write-path (GX10 embeddings).

The HTTP call to Ollama is mocked — these pin the dimension guard, the store
SQL targets the parallel column, and the batch summary accounting. The actual
1024-dim generation runs on the GX10 (localhost Ollama) where it can't be
unit-tested from CI.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.domains.content.embedding_service import EmbeddingService


def _svc():
    return EmbeddingService(MagicMock())


def _mock_httpx(embedding):
    """Patch httpx.AsyncClient so .post(...).json() yields the given embedding."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"data": [{"embedding": embedding}]})
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=ctx)


class TestGenerate:
    def test_returns_1024_dim_embedding(self):
        svc = _svc()
        with _mock_httpx([0.01] * 1024):
            emb = asyncio.run(svc.generate_bge_m3_embedding("climate change in the arctic"))
        assert emb is not None
        assert len(emb) == 1024

    def test_dimension_mismatch_returns_none(self):
        """A wrong-dim response (e.g. someone pointed it at qwen) must not be
        stored — it would corrupt the vector(1024) column."""
        svc = _svc()
        with _mock_httpx([0.1] * 768):
            emb = asyncio.run(svc.generate_bge_m3_embedding("text"))
        assert emb is None

    def test_empty_text_returns_none_without_call(self):
        svc = _svc()
        # No httpx patch — if it tried to call, it would error; it must short-circuit.
        assert asyncio.run(svc.generate_bge_m3_embedding("   ")) is None


class TestStore:
    def test_store_targets_parallel_column(self):
        db = MagicMock()
        svc = EmbeddingService(db)
        ok = asyncio.run(svc.store_bge_m3_embedding("aid-1", [0.5, 0.25]))
        assert ok is True
        sql = db.execute_update.call_args.args[0]
        params = db.execute_update.call_args.args[1]
        assert "embedding_bge_m3" in sql
        assert "embedding" in params and params["embedding"].startswith("[0.5,0.25")
        assert params["article_id"] == "aid-1"


class TestBatch:
    def test_batch_summary_accounting(self):
        db = MagicMock()
        db.execute_query.return_value = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        svc = EmbeddingService(db)
        with patch.object(svc, "populate_bge_m3_embedding",
                          new=AsyncMock(side_effect=[True, True, False])):
            summary = asyncio.run(svc.batch_populate_bge_m3(limit=3))
        assert summary == {"total_found": 3, "processed": 2, "failed": 1}

    def test_batch_empty_corpus(self):
        db = MagicMock()
        db.execute_query.return_value = []
        svc = EmbeddingService(db)
        summary = asyncio.run(svc.batch_populate_bge_m3(limit=10))
        assert summary["total_found"] == 0 and summary["processed"] == 0
