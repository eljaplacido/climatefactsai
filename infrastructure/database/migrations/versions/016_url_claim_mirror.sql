-- Migration 016: URL-claim mirror
-- Date: 2026-05-05
--
-- Closes the semantic-layer gap where URL-analyzed claims are trapped in
-- url_analyses.extracted_claims JSONB and never reach the canonical claims
-- table.  After this migration the URL analyzer can mirror its extracted
-- article + claims into articles + claims so they participate in deep-search,
-- hybrid RAG, and transparency cross-references like the rest of the corpus.
--
-- Articles inserted by the URL flow are flagged with is_user_submitted=TRUE
-- so they can be filtered out of editorial views when needed, and carry a
-- url_analysis_id backref so the original analysis row can be located.
--
-- Claims gain an importance_score (carried over from the LLM extractor) and
-- a source_kind discriminator: 'corpus' (default — regular ingestion) or
-- 'url_analysis' (mirrored from a user-submitted URL analysis).

-- 1. articles: provenance flags ------------------------------------------------
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS is_user_submitted BOOLEAN DEFAULT FALSE;

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS url_analysis_id UUID
        REFERENCES url_analyses(analysis_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_articles_user_submitted
    ON articles(is_user_submitted)
    WHERE is_user_submitted = TRUE;

CREATE INDEX IF NOT EXISTS idx_articles_url_analysis
    ON articles(url_analysis_id)
    WHERE url_analysis_id IS NOT NULL;

-- 2. claims: importance + source provenance -----------------------------------
ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS importance_score DECIMAL(3,2);

ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS source_kind VARCHAR(20) DEFAULT 'corpus';
-- source_kind values:
--   'corpus'       -> claim originated from regular ingestion pipeline
--   'url_analysis' -> claim mirrored from a user-submitted URL analysis
