-- Migration 055: backfill off_topic flag on 916 articles from
--                deactivated general-RSS feeds (2026-05-27, release blocker 4)
--
-- Mig 053 stopped FUTURE ingestion from the 4 chatty general-RSS feeds
-- (24ur Okolje SI, Capital BG, Digi24 RO, Dnevnik BG) that were
-- flooding the corpus with non-climate content. But the ~916 existing
-- articles from those feeds remained visible in the default feed and
-- in agent selection waves — the daemon's title-keyword gate excluded
-- them from enrichment but didn't actually hide them.
--
-- This migration writes a topic_feedback row (verdict='off_topic',
-- category='ingest_bias_rebalance') for each existing article from
-- those 4 feeds, so:
--   * /api/feedback/topic/off-topic-ids returns them → daemon skips
--   * Feed display code (when wired) can hide them from default view
--   * The 916 articles become a labeled training set for the future
--     topic classifier
--
-- Idempotent via NOT EXISTS guard: rerunning won't duplicate flags,
-- and won't overwrite user-submitted opinions (on_topic / borderline
-- from real users wins — we only flag articles with NO existing
-- topic_feedback row).
--
-- Reversal path: DELETE FROM topic_feedback
--                WHERE off_topic_category = 'ingest_bias_rebalance';

DO $$
DECLARE
    inserted_count INT;
    skipped_user_opinion INT;
BEGIN
    -- Snapshot the count of articles that ALREADY have any topic_feedback
    -- so we can report how many were respected as user-curated.
    SELECT COUNT(DISTINCT a.article_id) INTO skipped_user_opinion
      FROM articles a
      JOIN topic_feedback tf ON tf.article_id = a.article_id
     WHERE a.source_name IN (
            '24ur Okolje (SI)',
            'Capital BG (BG)',
            'Digi24 (RO)',
            'Dnevnik BG (BG)'
           );

    -- Insert off_topic flag for every article from the 4 deactivated
    -- feeds that has NO existing topic_feedback row. The user can
    -- always submit an `on_topic` override later via the /api/feedback
    -- endpoint, and the per-article view will show both opinions.
    WITH ins AS (
        INSERT INTO topic_feedback (
            feedback_id, article_id, verdict, reason,
            reporter_id, off_topic_category, created_at
        )
        SELECT
            gen_random_uuid(),
            a.article_id,
            'off_topic',
            'Source feed (' || a.source_name
              || ') deactivated in mig 053: general-RSS endpoint,'
              || ' high false-positive rate for climate relevance.',
            NULL,                       -- system-generated, no reporter
            'ingest_bias_rebalance',
            NOW()
          FROM articles a
         WHERE a.source_name IN (
                 '24ur Okolje (SI)',
                 'Capital BG (BG)',
                 'Digi24 (RO)',
                 'Dnevnik BG (BG)'
               )
           AND NOT EXISTS (
                 SELECT 1 FROM topic_feedback tf
                  WHERE tf.article_id = a.article_id
               )
        RETURNING 1
    )
    SELECT COUNT(*) INTO inserted_count FROM ins;

    RAISE NOTICE
      'migration 055: off_topic flag inserted on % articles '
      '(% articles had existing user opinions and were respected).',
      inserted_count, skipped_user_opinion;
END $$;

-- Index on off_topic_category for fast reversal / audit queries.
-- Idempotent — IF NOT EXISTS guards re-runs.
CREATE INDEX IF NOT EXISTS idx_topic_feedback_off_topic_category
    ON topic_feedback(off_topic_category)
 WHERE off_topic_category IS NOT NULL;
