-- @notolerate
-- Migration 074: backfill — neutralise the Google cookie-consent-wall poison
--                (ML-03, 2026-07-01, launch blocker).
--
-- 1,433 articles were ingested with `extracted_text` = Google's cookie-consent
-- interstitial (one identical 835-char body, md5 94a38797a13f417b263c9c7c78c93f08,
-- all from "Google News Climate - <country>" feeds). 1,298 are still served;
-- 858 got bge-m3 embeddings; ~813 were given claim sets (9,206 claims / 9,167
-- fact_checks) — broken data served with full credibility. Root cause is fixed
-- forward by the ingestion quality gate (mig 073 + ingest_quality_gate.py); this
-- migration cleans the existing rows.
--
-- For each consent-wall row it:
--   1. DELETEs the bogus claim sets (fact_checks + claim_entity_mentions cascade
--      via ON DELETE CASCADE — verified against the live FK graph);
--   2. sets is_off_topic = TRUE  (removes them from every listing surface);
--   3. NULLs both embedding columns (embedding, embedding_bge_m3) that were
--      generated over the consent text.
--
-- extracted_text is PRESERVED (audit trail + idempotent re-match; search_tsv is
-- a generated column and is left untouched). The row stays reachable by direct
-- URL like every other off-topic row.
--
-- Idempotent: the predicate matches on the unchanged extracted_text, so a
-- re-run re-sets the same flags (no-op) and finds zero claims left to delete.
-- @notolerate so a failure is LOUD (never silently marked applied). No
-- CREATE TABLE — all target tables pre-exist.

DO $$
DECLARE
    n_target   INT;
    n_served   INT;
    n_emb      INT;
    n_fc       INT;
    n_claims   INT;
    n_flagged  INT;
BEGIN
    -- Target set: primary md5 signature OR the (equivalent) textual signature.
    -- Both resolve to the same 1,433 rows in production; the OR future-proofs
    -- against minor byte drift in the interstitial copy.
    -- DROP-guard so re-execution inside a single session is safe (the temp
    -- table is ON COMMIT DROP, but a manual re-run in one open tx would collide).
    DROP TABLE IF EXISTS _ml03_targets;
    CREATE TEMP TABLE _ml03_targets ON COMMIT DROP AS
        SELECT article_id
          FROM articles
         WHERE md5(extracted_text) = '94a38797a13f417b263c9c7c78c93f08'
            OR (extracted_text ILIKE '%g.co/privacytools%'
                AND extracted_text ILIKE '%Accept all%'
                AND extracted_text ILIKE '%Reject all%');

    SELECT COUNT(*) INTO n_target FROM _ml03_targets;

    SELECT COUNT(*) INTO n_served
      FROM articles a JOIN _ml03_targets t USING (article_id)
     WHERE a.is_off_topic = FALSE;

    SELECT COUNT(*) INTO n_emb
      FROM articles a JOIN _ml03_targets t USING (article_id)
     WHERE a.embedding IS NOT NULL OR a.embedding_bge_m3 IS NOT NULL;

    -- fact_checks reversed via the claims cascade — count BEFORE deleting.
    SELECT COUNT(*) INTO n_fc
      FROM fact_checks fc
      JOIN claims c ON c.claim_id = fc.claim_id
     WHERE c.article_id IN (SELECT article_id FROM _ml03_targets);

    -- 1. Reverse the bogus claim sets (cascades fact_checks + claim_entity_mentions).
    DELETE FROM claims
     WHERE article_id IN (SELECT article_id FROM _ml03_targets);
    GET DIAGNOSTICS n_claims = ROW_COUNT;

    -- 2. Remove from serving + null the embeddings built over the consent text.
    UPDATE articles a
       SET is_off_topic     = TRUE,
           embedding        = NULL,
           embedding_bge_m3 = NULL
      FROM _ml03_targets t
     WHERE a.article_id = t.article_id;
    GET DIAGNOSTICS n_flagged = ROW_COUNT;

    RAISE NOTICE 'migration 074 (ML-03): % consent-wall rows targeted (% were served, % carried embeddings); reversed % claims (+ % fact_checks via cascade); set is_off_topic + nulled embeddings on % rows.',
        n_target, n_served, n_emb, n_claims, n_fc, n_flagged;
END $$;
