-- Migration 056: articles.is_off_topic display flag (F1 second half / T12)
--
-- F1's ingest gate (commit c56b79a) blocks NEW off-topic articles, but the
-- existing corpus still served them: e.g. a "bus accident" story from a
-- general feed remained visible in the feed / map / search. The off_topic
-- verdicts in topic_feedback (mig 050/055) were only read by the enrichment
-- daemon, never by the display layer.
--
-- This migration adds the column the display filter keys on. It is split
-- from the backfill (mig 057) ON PURPOSE: this file is bulletproof
-- (ADD COLUMN IF NOT EXISTS can never fail), so the API can deploy with the
-- new `AND is_off_topic = FALSE` filter and be guaranteed the column exists
-- even if the backfill (057) errors and rolls back. See run_migrations.py:
-- each file is one transaction; decoupling protects the user-facing path.
--
-- is_off_topic semantics: TRUE => hide from LISTING surfaces (feed, map,
-- search, country counts). The article stays reachable by direct URL and a
-- user can submit on_topic feedback to clear the flag (the per-article page
-- is intentionally NOT filtered). Mirrors the is_synthetic = FALSE pattern.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS is_off_topic BOOLEAN NOT NULL DEFAULT FALSE;

-- Partial index supports the backfill / audit / reversal queries (the small
-- TRUE set). The common FALSE filter rides existing predicates + LIMIT.
CREATE INDEX IF NOT EXISTS idx_articles_is_off_topic
    ON articles(is_off_topic)
 WHERE is_off_topic = TRUE;
