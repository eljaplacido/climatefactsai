-- =============================================================================
-- 023_claim_provenance_more_signals.sql — Provenance for deep-search + Cynefin
-- =============================================================================
-- Phase 4 wave 4: the URL-analysis pipeline records provenance into
-- `claim_provenance` since migration 021. The other LLM-using paths
-- (deep-search synthesis, Cynefin classification) don't have a natural
-- identity from {claim_id, url_analysis_id, article_id} — they're
-- ephemeral query handlers, not artifact creators.
--
-- This migration:
--   1. Adds two new identity columns to `claim_provenance`:
--      * `deep_search_session_id` — a per-request UUID we mint client-side
--        or per-call server-side; lets the audit trail group all the LLM
--        calls that contributed to one deep-search response.
--      * `cynefin_classification_id` — UUID minted per LLM classification
--        run; ephemeral but lets us join Cynefin output back to the
--        triggering deep-search / chat session.
--   2. Relaxes the CHECK constraint to allow rows that carry only
--      `extraction_method` + at least one of the FIVE identity columns
--      (the original three + these two new ones).
--
-- Existing rows aren't touched; the constraint relaxation is additive.
-- =============================================================================

ALTER TABLE claim_provenance
    ADD COLUMN IF NOT EXISTS deep_search_session_id  UUID NULL,
    ADD COLUMN IF NOT EXISTS cynefin_classification_id UUID NULL;

-- Drop and re-add the CHECK with the expanded set of allowed identities.
ALTER TABLE claim_provenance
    DROP CONSTRAINT IF EXISTS chk_claim_provenance_has_link;

ALTER TABLE claim_provenance
    ADD CONSTRAINT chk_claim_provenance_has_link CHECK (
        claim_id IS NOT NULL
        OR url_analysis_id IS NOT NULL
        OR article_id IS NOT NULL
        OR deep_search_session_id IS NOT NULL
        OR cynefin_classification_id IS NOT NULL
    );

-- Hot paths: time-series queries grouping by session id.
CREATE INDEX IF NOT EXISTS idx_claim_provenance_deep_search_session_id
    ON claim_provenance(deep_search_session_id)
    WHERE deep_search_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claim_provenance_cynefin_classification_id
    ON claim_provenance(cynefin_classification_id)
    WHERE cynefin_classification_id IS NOT NULL;

COMMENT ON COLUMN claim_provenance.deep_search_session_id IS
    'UUID minted at the start of one /api/deep-search request. All LLM '
    'calls produced during that request (synthesis + cynefin + hallucination) '
    'share this ID so the audit-trail endpoint can group them.';

COMMENT ON COLUMN claim_provenance.cynefin_classification_id IS
    'UUID minted per Cynefin classification run. Links the classification '
    'output back to the triggering session.';
