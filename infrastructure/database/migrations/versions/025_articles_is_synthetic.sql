-- Migration 025: mark synthetic/demo seed articles
--
-- Background: an earlier dev session ran scripts/populate_demo_articles.py
-- (2026-03-28, 1,008 example.com rows) and scripts/seed_full_global.py
-- (2026-03-30, 2,580 clilens.ai rows) to populate the UI before real
-- ingestion covered all countries. Those rows have ~130-character "text"
-- (essentially just titles) and would teach the enrichment LLM to fabricate
-- detail. This migration adds a flag so they can be excluded from enrichment,
-- LLM paths, and (later) the frontend, without destroying them.
--
-- Idempotent: safe to re-run.

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_articles_is_synthetic
  ON articles (is_synthetic)
  WHERE is_synthetic = FALSE;

-- Backfill: flag known synthetic URL patterns
UPDATE articles
   SET is_synthetic = TRUE
 WHERE is_synthetic = FALSE
   AND (url LIKE 'https://clilens.ai/%' OR url LIKE '%example.com%');
