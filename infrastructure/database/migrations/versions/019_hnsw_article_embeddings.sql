-- =============================================================================
-- 019_hnsw_article_embeddings.sql — Switch to HNSW for stable recall at scale
-- =============================================================================
-- Closes audit finding P1 (2026-05-16): the pre-fix index was
-- `idx_articles_embedding USING ivfflat (embedding) WITH (lists=100)` in
-- `infrastructure/database/init.sql`. IVFFlat with lists=100 is sized for
-- roughly 10k rows; recall degrades and probes balloon past ~50k. The
-- production seed already targets 50k+ articles, so the index was a
-- ticking quality regression.
--
-- HNSW is more memory-hungry but gives:
--   * Stable recall at 10k -> 1M scale
--   * ~10x lower P95 latency at production scale
--   * Live insert/delete (IVFFlat needs REINDEX after large batches)
--
-- Parameters:
--   m = 16              — connections per layer (default; balanced)
--   ef_construction = 64 — build-time effort (default; ~2x build cost vs 32)
--
-- Per-query effort can be tuned via `SET LOCAL hnsw.ef_search = N;`
-- inside specific handlers — e.g. 40 for chat retrieval, 100 for deep
-- search. Default ef_search=40 is fine for most paths.
--
-- The index is also made partial (`WHERE embedding IS NOT NULL`) so
-- unenriched articles don't bloat it. Recall and build time both
-- improve when the corpus has a long tail of in-flight ingestion.
--
-- Application code requires no change: pgvector queries use whichever
-- index is present.
-- =============================================================================

DROP INDEX IF EXISTS idx_articles_embedding;

CREATE INDEX idx_articles_embedding
    ON articles
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

COMMENT ON INDEX idx_articles_embedding IS
    'HNSW (m=16, ef_construction=64) partial index over articles.embedding '
    'where the vector is populated. Replaces the legacy IVFFlat lists=100 '
    'index whose recall collapsed past ~20k articles. Tune per-query '
    'effort with SET LOCAL hnsw.ef_search = N.';
