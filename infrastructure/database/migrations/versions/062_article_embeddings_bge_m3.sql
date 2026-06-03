-- Migration 062: parallel bge-m3 article embeddings (audit seq-6, 2026-06-02)
--
-- Article semantic search / RAG is currently dead: the existing
-- `articles.embedding` column (OpenAI ada-002, vector(1536)) is 0/666 populated
-- because ada-002 is paid and was never backfilled, so EmbeddingService.find_
-- similar / semantic_search return []. The GX10 box runs free local inference,
-- so we move embeddings there with BAAI/bge-m3 (multilingual, 1024-dim) — zero
-- marginal cost and better non-English coverage for the global corpus.
--
-- This is the NON-DESTRUCTIVE parallel-column approach: a new
-- `embedding_bge_m3 vector(1024)` column + its own HNSW index, leaving the
-- ada-002 column untouched so the query path can be cut over only after parity
-- is proven on a held-out set. The GX10-resident embedding_worker.py writes this
-- column; nothing on Cloud Run depends on it until search is flipped over.
--
-- Idempotent: IF NOT EXISTS on both the column and the index.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedding_bge_m3 vector(1024);

COMMENT ON COLUMN articles.embedding_bge_m3 IS
    'bge-m3 (1024-dim) multilingual embedding generated on the GX10 via local '
    'Ollama (seq-6). Parallel to the legacy ada-002 `embedding` column.';

-- HNSW for cosine similarity, same params as the ada-002 index (mig 019).
-- Partial index keeps it small while the column backfills.
CREATE INDEX IF NOT EXISTS idx_articles_embedding_bge_m3_hnsw
    ON articles USING hnsw (embedding_bge_m3 vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

DO $$
DECLARE n INT;
BEGIN
    SELECT COUNT(*) INTO n FROM articles WHERE embedding_bge_m3 IS NOT NULL;
    RAISE NOTICE 'migration 062: articles.embedding_bge_m3 ready (% populated)', n;
END $$;
