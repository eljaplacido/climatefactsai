-- =============================================================================
-- 072_fts_english_rebuild.sql — Rebuild articles.search_tsv on a FIXED
-- 'english' text-search config (launch-blocker ML-01).
-- =============================================================================
-- SYMPTOM: full-text search matched 0 articles platform-wide.
--   GET /api/search/?q=climate -> []
--   DB: search_tsv @@ websearch_to_tsquery('english','climate') ~= 2062 rows,
--       search_tsv @@ websearch_to_tsquery('simple' ,'climate')  = 0 rows.
--
-- ROOT CAUSE: migration 018 built articles.search_tsv as a GENERATED STORED
-- column using `to_tsvector(clilens_lang_cfg(language_code), …)`. Because
-- articles.language_code is mislabelled 'fi' on ~100% of rows (a separate
-- ingestion/attribution bug), clilens_lang_cfg() resolved to the *finnish*
-- regconfig, so every stored lexeme was Finnish-stemmed. Meanwhile every
-- query site used `websearch_to_tsquery('simple', …)`. Finnish-stemmed
-- lexemes never matched the 'simple' (or 'english') query tokens, so keyword
-- search returned nothing for the entire corpus.
--
-- FIX: rebuild search_tsv with a FIXED `to_tsvector('english', …)` over the
-- SAME source columns (title + excerpt + extracted_text) with the SAME weights
-- as migration 018 (mig 018 applied NO setweight, so all lexemes keep the
-- default 'D' weight — we preserve that so existing ts_rank ordering is
-- unchanged). In the SAME commit, every application query site is pinned to
-- `websearch_to_tsquery('english', …)` so both sides use the identical config.
-- The corpus is English-dominant, so a fixed 'english' stemmer is correct AND
-- it decouples FTS from the language_code mislabelling.
--
-- SCOPE: this migration deliberately does NOT fix the language_code
-- mislabelling itself (true-language attribution / display) — that is tracked
-- separately as ML-20. Fixed-'english' FTS makes ML-20 irrelevant to *search*.
--
-- clilens_lang_cfg(TEXT) is LEFT IN PLACE. After this migration it is no longer
-- referenced by search_tsv, but it is a harmless immutable helper and other
-- callers may reference it (per its mig-018 comment). Dropping it is out of
-- scope.
--
-- Idempotent: DROP COLUMN IF EXISTS + re-ADD, DROP INDEX IF EXISTS + CREATE.
-- No CREATE TABLE. Safe to re-run. Single transaction via run_migrations.py.
-- =============================================================================

-- @notolerate  — a silent tolerate of a rebuild here would leave FTS dead.

-- Defensive: ensure the source columns exist on legacy schemas.
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS language_code VARCHAR(8) DEFAULT 'en';

-- Rebuild the generated column with a FIXED 'english' config.
-- DROP first so the re-ADD is idempotent when the migration is replayed by hand
-- (the tracker prevents re-runs in normal operation).
ALTER TABLE articles DROP COLUMN IF EXISTS search_tsv;

ALTER TABLE articles
    ADD COLUMN search_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector(
            'english',
            COALESCE(title,          '') || ' ' ||
            COALESCE(excerpt,        '') || ' ' ||
            COALESCE(extracted_text, '')
        )
    ) STORED;

-- Recreate the GIN index every FTS query path relies on. Partial — skip empty
-- vectors so the index stays compact for not-yet-enriched articles.
DROP INDEX IF EXISTS idx_articles_search_tsv;
CREATE INDEX idx_articles_search_tsv
    ON articles
    USING GIN (search_tsv)
    WHERE search_tsv IS NOT NULL;

COMMENT ON COLUMN articles.search_tsv IS
    'FTS tsvector over title + excerpt + extracted_text, FIXED english config '
    '(migration 072, launch-blocker ML-01). Query side MUST use '
    'websearch_to_tsquery(''english'', …) to match. Replaced the mig-018 '
    'per-row clilens_lang_cfg(language_code) build, which produced '
    'Finnish-stemmed lexemes (language_code mislabelled ''fi'') that matched '
    'nothing at query time. True-language attribution fix tracked as ML-20.';
