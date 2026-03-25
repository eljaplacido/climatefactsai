-- Migration 011: Add semantic search indexes for pgvector
-- Requires pgvector extension (already enabled for similarity search)

-- Ensure pgvector extension exists
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column if not exists (may already exist from similarity service)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'embedding'
    ) THEN
        ALTER TABLE articles ADD COLUMN embedding vector(1536);
    END IF;
END $$;

-- HNSW index for fast approximate nearest-neighbor search
-- ef_construction=128 and m=16 are good defaults for 1536-dim embeddings
CREATE INDEX IF NOT EXISTS idx_articles_embedding_hnsw
    ON articles USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

-- Composite index for filtered semantic search
CREATE INDEX IF NOT EXISTS idx_articles_category_country
    ON articles (content_category, country_code)
    WHERE content_category IS NOT NULL;

-- Full-text search index for hybrid search
CREATE INDEX IF NOT EXISTS idx_articles_fts
    ON articles USING gin (
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(extracted_text, ''))
    );
