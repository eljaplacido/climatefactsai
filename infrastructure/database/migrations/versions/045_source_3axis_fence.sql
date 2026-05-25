-- @notolerate
-- Migration 045: source 3-axis scoring fence (Slice 7, 2026-05-25).
--
-- Honest-Gap-Audit v2 item 10 documented: Mig 041 backfilled
-- source_credibility_tiers.{editorial_score, factcheck_score,
-- transparency_score} for every existing row, but only logged a NOTICE
-- if any rows remained NULL — so we couldn't be sure the fence held.
-- The Slice 7 fix:
--   1. NULL-fill any leftover rows with the "unknown" tier defaults
--      (30/25/30 from the Mig 041 rubric).
--   2. Hard-assert via P0001 that no NULLs remain post-fill. The
--      @notolerate directive ensures any failure is loud rather than
--      silently swallowed (see feedback_migration_tolerate_errors).
--
-- Future work: a Mig 046 could add NOT NULL constraints once every
-- ingestion path is verified to set the scores at insert time. Today
-- those paths aren't fully audited; setting NOT NULL too early would
-- break adapter syncs that omit the columns. NULL-fill plus a loud
-- audit trail is the conservative middle ground.

-- 1) Fill any rows that still have NULLs in any of the 3 axes. Apply
--    tier-appropriate defaults from the Mig 041 rubric where the tier
--    is known; fall back to the "unknown" defaults otherwise.
UPDATE source_credibility_tiers
SET
    editorial_score = COALESCE(
        editorial_score,
        CASE tier
            WHEN 'T1' THEN 90
            WHEN 'T2' THEN 70
            WHEN 'T3' THEN 55
            WHEN 'retracted' THEN 5
            ELSE 30
        END
    ),
    factcheck_score = COALESCE(
        factcheck_score,
        CASE tier
            WHEN 'T1' THEN 90
            WHEN 'T2' THEN 75
            WHEN 'T3' THEN 50
            WHEN 'retracted' THEN 5
            ELSE 25
        END
    ),
    transparency_score = COALESCE(
        transparency_score,
        CASE tier
            WHEN 'T1' THEN 90
            WHEN 'T2' THEN 65
            WHEN 'T3' THEN 60
            WHEN 'retracted' THEN 5
            ELSE 30
        END
    ),
    scoring_last_reviewed_at = COALESCE(scoring_last_reviewed_at, NOW())
WHERE editorial_score IS NULL
   OR factcheck_score IS NULL
   OR transparency_score IS NULL;


-- 2) Hard-assert no NULLs remain. P0001 not in TOLERATED_CODES, plus
--    the @notolerate directive at top of file disables tolerance for
--    this migration explicitly.
DO $$
DECLARE
    n_null INTEGER;
    n_total INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_total FROM source_credibility_tiers;
    SELECT COUNT(*) INTO n_null
    FROM source_credibility_tiers
    WHERE editorial_score IS NULL
       OR factcheck_score IS NULL
       OR transparency_score IS NULL;

    RAISE NOTICE 'Migration 045: % of % sources have full 3-axis scores',
        n_total - n_null, n_total;

    IF n_null > 0 THEN
        RAISE EXCEPTION
            'Migration 045 FAILED: % source(s) still have NULL in editorial/factcheck/transparency_score',
            n_null
            USING ERRCODE = 'P0001';
    END IF;
END
$$;
