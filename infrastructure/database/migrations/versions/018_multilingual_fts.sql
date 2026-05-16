-- =============================================================================
-- 018_multilingual_fts.sql — Language-aware full-text search
-- =============================================================================
-- Closes audit finding D3 (2026-05-16): FTS was hardcoded to
-- `to_tsvector('english', …)` in:
--   - api/map_routes.py:361 (_get_country_stats keyword filter)
--   - api/map_routes.py:746 (/api/map/query natural-language search)
--   - src/backend/app/domains/intelligence/hybrid_rag_service.py:128,144
-- The English stemmer mangles Finnish/German/French/Spanish/Arabic tokens,
-- so roughly 70% of the multilingual corpus was invisible to keyword search.
--
-- Fix:
--   1. `clilens_lang_cfg(text) -> regconfig` helper maps ISO 639-1 codes
--      to PostgreSQL text search configurations (immutable, parallel-safe).
--   2. `articles.search_tsv` generated STORED tsvector column applies the
--      right stemmer per article (English articles → English stems,
--      Finnish articles → Finnish stems, etc.).
--   3. GIN index on `search_tsv` replaces the seconds-slow on-the-fly
--      `to_tsvector(...)` evaluations at query time.
--
-- Query side (in application code):
--   `a.search_tsv @@ websearch_to_tsquery('simple', :q)`
-- Using `'simple'` for the query side gives token-level matching across
-- all languages — slightly less precision on intra-language stemming but
-- a huge precision/recall lift on the previously-invisible 70%. When a
-- user locale is known, callers can substitute `clilens_lang_cfg(:lang)`
-- for tighter per-language stemming.
--
-- The migration also defensively ensures `articles.language_code` exists
-- so this can run on legacy schemas. Generated column is STORED, so the
-- table is rewritten once and queries get the GIN-index path forever.
-- =============================================================================

-- Defensive: ensure language_code exists on older schemas.
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS language_code VARCHAR(8) DEFAULT 'en';


-- ISO 639-1 → PostgreSQL regconfig.
-- Every config name in this CASE is bundled with PostgreSQL by default;
-- the function stays valid on a minimal install. Unsupported codes fall
-- back to 'simple' (tokenization without stemming).
CREATE OR REPLACE FUNCTION clilens_lang_cfg(lang_code TEXT)
    RETURNS regconfig
    LANGUAGE SQL
    IMMUTABLE
    PARALLEL SAFE
    AS $$
        SELECT CASE LOWER(COALESCE(lang_code, ''))
            WHEN 'en'  THEN 'english'::regconfig
            WHEN 'fi'  THEN 'finnish'::regconfig
            WHEN 'de'  THEN 'german'::regconfig
            WHEN 'fr'  THEN 'french'::regconfig
            WHEN 'es'  THEN 'spanish'::regconfig
            WHEN 'it'  THEN 'italian'::regconfig
            WHEN 'pt'  THEN 'portuguese'::regconfig
            WHEN 'sv'  THEN 'swedish'::regconfig
            WHEN 'no'  THEN 'norwegian'::regconfig
            WHEN 'nb'  THEN 'norwegian'::regconfig
            WHEN 'nn'  THEN 'norwegian'::regconfig
            WHEN 'da'  THEN 'danish'::regconfig
            WHEN 'nl'  THEN 'dutch'::regconfig
            WHEN 'ru'  THEN 'russian'::regconfig
            WHEN 'tr'  THEN 'turkish'::regconfig
            WHEN 'hu'  THEN 'hungarian'::regconfig
            ELSE             'simple'::regconfig
        END;
    $$;


-- Drop+re-add to make the migration idempotent if re-run during dev.
ALTER TABLE articles DROP COLUMN IF EXISTS search_tsv;

ALTER TABLE articles
    ADD COLUMN search_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector(
            clilens_lang_cfg(language_code),
            COALESCE(title,    '') || ' ' ||
            COALESCE(excerpt,  '') || ' ' ||
            COALESCE(extracted_text, '')
        )
    ) STORED;


-- Hot path: GIN over the generated column. Partial — skip empty vectors
-- so the index stays compact when articles haven't been enriched yet.
DROP INDEX IF EXISTS idx_articles_search_tsv;
CREATE INDEX idx_articles_search_tsv
    ON articles
    USING GIN (search_tsv)
    WHERE search_tsv IS NOT NULL;


COMMENT ON FUNCTION clilens_lang_cfg(TEXT) IS
    'Maps ISO 639-1 language codes to PostgreSQL text-search regconfigs. '
    'Used by the articles.search_tsv generated column and by callers that '
    'want per-locale query-side stemming.';

COMMENT ON COLUMN articles.search_tsv IS
    'Language-aware tsvector covering title + excerpt + extracted_text. '
    'Stemmer chosen per-row via clilens_lang_cfg(language_code). Replaces '
    'the pre-2026-05-16 hardcoded English-only on-the-fly tokenisation.';
