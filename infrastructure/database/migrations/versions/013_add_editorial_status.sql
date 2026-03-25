-- Migration 013: Add editorial_status column to articles
-- Date: 2026-03-04

ALTER TABLE articles ADD COLUMN IF NOT EXISTS editorial_status VARCHAR(20) DEFAULT NULL;
CREATE INDEX IF NOT EXISTS idx_articles_editorial_status ON articles(editorial_status);
COMMENT ON COLUMN articles.editorial_status IS 'Editorial gate decision: PUBLISH, HOLD, or ESCALATE. NULL = not yet evaluated.';
