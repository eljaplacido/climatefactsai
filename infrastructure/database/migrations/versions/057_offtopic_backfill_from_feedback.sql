-- @notolerate
-- Migration 057: backfill articles.is_off_topic from curated topic_feedback
--                verdicts (F1 second half / T12).
--
-- Sets is_off_topic = TRUE for every article that already has an off_topic
-- verdict in topic_feedback (mig 055 wrote ~916 of these for the 4 deactivated
-- general-RSS feeds — 24ur Okolje SI, Capital BG, Digi24 RO, Dnevnik BG — which
-- are also the bulk of the Eastern-EU ingestion skew the owner flagged). Once
-- mig 056's column + the display filter ship, these finally drop out of the
-- feed / map / search instead of only being skipped by the enrichment daemon.
--
-- DELIBERATELY backfills ONLY from the curated topic_feedback set. A blind
-- keyword/relevance sweep was measured to mis-flag 65%+ of the real corpus
-- (truncated RSS text + non-English climate sources lack English keywords —
-- even BBC Climate / NYT Climate fail it), so the accurate per-article
-- relevance backfill is an LLM/source-aware job (the §3/§8 GX10 relevance
-- gate), NOT something safe to bake into SQL here.
--
-- Respects user opinion: an article with ANY on_topic verdict is never hidden.
-- @notolerate so a failure is loud, never silently marked applied.
-- Guarded with to_regclass so a stale DB without topic_feedback is a no-op,
-- not an error. Idempotent (only flips FALSE -> TRUE).
-- Reversal: UPDATE articles SET is_off_topic = FALSE WHERE is_off_topic = TRUE;

DO $$
DECLARE
    v_flagged INT := 0;
BEGIN
    IF to_regclass('public.topic_feedback') IS NULL THEN
        RAISE NOTICE 'mig 057: topic_feedback table absent (stale DB) — skipping backfill.';
        RETURN;
    END IF;

    UPDATE articles a
       SET is_off_topic = TRUE
     WHERE a.is_off_topic = FALSE
       AND EXISTS (
             SELECT 1 FROM topic_feedback tf
              WHERE tf.article_id = a.article_id
                AND tf.verdict = 'off_topic'
           )
       AND NOT EXISTS (
             SELECT 1 FROM topic_feedback tf2
              WHERE tf2.article_id = a.article_id
                AND tf2.verdict = 'on_topic'
           );
    GET DIAGNOSTICS v_flagged = ROW_COUNT;

    RAISE NOTICE 'mig 057: is_off_topic set TRUE on % article(s) from curated off_topic feedback.', v_flagged;
END $$;
