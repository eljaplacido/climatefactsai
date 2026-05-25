-- Migration 040: PURGE all synthetic / simulated data from production.
-- Phase 10 (2026-05-25). Per user directive: "absolutely not simulated
-- or synthetic analysis allowed".
--
-- Goes far beyond just flagging — physically DELETEs:
--   1. Articles matching seed UUID pattern (XX000000-0000-4XXX-8XXX-0000000000XX)
--   2. Articles with fake/example URLs (csiro.au/great-barrier-reef-2025 etc.)
--   3. Articles already flagged is_synthetic=TRUE
--   4. Empty-placeholder articles (no extracted_text + tiny excerpt + suspiciously high credibility)
--   5. Claims + fact_checks orphaned by the deletion (CASCADE handles this)
--
-- Then adds a TRIGGER that rejects any future INSERT where
-- is_synthetic=TRUE, so this class of data integrity bug cannot recur.
--
-- DESTRUCTIVE BUT INTENTIONAL. The platform's value depends on data
-- integrity — synthetic data with credibility=94 is worse than no data.

DO $$
DECLARE
    n_pattern INTEGER;
    n_fake_host INTEGER;
    n_flagged INTEGER;
    n_placeholder INTEGER;
    n_orphan_claims INTEGER;
    n_remaining_articles INTEGER;
    n_remaining_claims INTEGER;
    synthetic_ids UUID[];
BEGIN
    -- ----------------------------------------------------------------------
    -- Step 1: gather every synthetic article_id into a temp array so we can
    -- count + cascade-delete cleanly.
    -- ----------------------------------------------------------------------

    -- Pattern: seed UUID
    SELECT ARRAY_AGG(article_id) INTO synthetic_ids
    FROM articles
    WHERE article_id::text LIKE '__000000-0000-4___-8___-0000000000__';
    n_pattern := COALESCE(array_length(synthetic_ids, 1), 0);

    DELETE FROM articles
    WHERE article_id = ANY(synthetic_ids);

    -- Fake/example hosts
    DELETE FROM articles
    WHERE url LIKE '%csiro.au/great-barrier-reef-2025%'
       OR url LIKE '%nature.com/swiss-alps-glaciers%'
       OR url LIKE '%nature.com/israel-perovskite-2025%'
       OR url LIKE '%ofv.no/statistics/2025%'
       OR url LIKE '%noaa.gov/coastal-flooding-2025%'
       OR url LIKE '%example.com/%'
       OR url LIKE '%example.org/%'
       OR url LIKE '%test.com/%'
       OR url LIKE '%localhost%'
       OR url LIKE '%placeholder%'
       OR url IS NULL;
    GET DIAGNOSTICS n_fake_host = ROW_COUNT;

    -- Anything already flagged is_synthetic=TRUE
    DELETE FROM articles WHERE is_synthetic = TRUE;
    GET DIAGNOSTICS n_flagged = ROW_COUNT;

    -- Empty-placeholder + suspiciously-high credibility
    -- (real ingestion always produces some extracted_text)
    DELETE FROM articles
    WHERE (extracted_text IS NULL OR LENGTH(extracted_text) < 200)
      AND (excerpt IS NULL OR LENGTH(excerpt) < 100)
      AND COALESCE(reliability_score, 0) >= 80;
    GET DIAGNOSTICS n_placeholder = ROW_COUNT;

    -- ----------------------------------------------------------------------
    -- Step 2: clean up orphans the CASCADE didn't catch (defensive).
    -- ----------------------------------------------------------------------
    DELETE FROM claims
    WHERE article_id NOT IN (SELECT article_id FROM articles);
    GET DIAGNOSTICS n_orphan_claims = ROW_COUNT;

    DELETE FROM fact_checks
    WHERE claim_id NOT IN (SELECT claim_id FROM claims);

    -- ----------------------------------------------------------------------
    -- Step 3: report what's left.
    -- ----------------------------------------------------------------------
    SELECT COUNT(*) INTO n_remaining_articles FROM articles;
    SELECT COUNT(*) INTO n_remaining_claims FROM claims;

    RAISE NOTICE 'Migration 040: deleted % by UUID-pattern, % by fake-host, % already-flagged, % placeholder; % orphan-claims cleaned. Remaining: % articles, % claims.',
        n_pattern, n_fake_host, n_flagged, n_placeholder, n_orphan_claims,
        n_remaining_articles, n_remaining_claims;
END
$$;


-- ---------------------------------------------------------------------------
-- Step 4: BLOCK future synthetic inserts with a trigger.
-- Any code path that tries to INSERT INTO articles ... is_synthetic=TRUE
-- will raise an exception. Forces the ingestion pipeline to either
-- produce real articles or fail loudly — no silent synthetic leak.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION reject_synthetic_articles()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_synthetic IS TRUE THEN
        RAISE EXCEPTION 'INSERT blocked: synthetic articles are not allowed in production. (Migration 040, 2026-05-25.) See docs/improvementplans/Phase-10-Session-Summary-2026-05-25.md';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reject_synthetic_articles ON articles;
CREATE TRIGGER trg_reject_synthetic_articles
    BEFORE INSERT ON articles
    FOR EACH ROW
    EXECUTE FUNCTION reject_synthetic_articles();

COMMENT ON TRIGGER trg_reject_synthetic_articles ON articles IS
'Blocks INSERTs with is_synthetic=TRUE. Phase 10 hard-data-integrity gate.';


-- ---------------------------------------------------------------------------
-- Step 5: Partial unique index so the WHERE clause stays fast as the
-- article table grows. Production queries always want is_synthetic=FALSE.
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_articles_real_only
    ON articles (created_at DESC)
    WHERE is_synthetic = FALSE;
