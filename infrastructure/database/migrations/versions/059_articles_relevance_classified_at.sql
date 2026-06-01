-- Migration 059: articles.relevance_classified_at — dedicated F1 backfill marker
--
-- Bugfix (review of 7c7b204): the relevance-flag backfill resumed on
-- `content_relevance_score IS NULL`, but the verification/reliability pipeline
-- (shared/reliability_scorer.py) ALSO writes content_relevance_score with its
-- keyword heuristic after every fact-check. So any article already fact-checked
-- had a non-NULL score and was permanently skipped by the backfill — exactly the
-- off-topic corpus the feature targets. This dedicated timestamp decouples the
-- two: the backfill marks ONLY rows it has actually LLM-classified, and only on
-- a real verdict (a transient classifier error leaves it NULL so the row retries).
--
-- Bulletproof (ADD COLUMN IF NOT EXISTS, can't fail). Partial index supports the
-- "not yet classified" candidate scan.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS relevance_classified_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_articles_relevance_unclassified
    ON articles(created_at)
 WHERE relevance_classified_at IS NULL AND is_synthetic = FALSE;
