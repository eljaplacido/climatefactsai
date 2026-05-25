-- @notolerate
-- Migration 044: companies dedup pass 3 — true cleanup with conflict-safe
-- reassignment.
--
-- WHY THIS EXISTS:
--   Migration 043 was silently tolerated during the 2026-05-25 Slice 2 deploy.
--   Build log: "TOLERATED (23505: UniqueViolation) -> marking as already-applied".
--   The runner has 23505 in TOLERATED_CODES; 043 partially ran, hit a unique
--   collision when reassigning multiple drop_ids' disclosures to the same
--   keep_id (two drops with the same source+reporting_year both wanted to
--   become (keep_id, source, reporting_year)), and the index recreation
--   then collided too. The runner marked 043 applied without doing the
--   work. Live verification showed 27x "2degrees" NZ, 16x "2 Sisters",
--   12x "2Connect" still in production.
--
-- WHAT THIS DOES DIFFERENTLY:
--   1. The `-- @notolerate` directive at the top forces the runner to NOT
--      swallow 23505 / 42P07 / etc. for this migration. Any failure is
--      loud and fails the build (see scripts/run_migrations.py changes
--      in the same commit).
--   2. Disclosure reassignment uses INSERT...SELECT...ON CONFLICT DO NOTHING
--      so multi-drop-per-keep no longer collides — the SECOND row to want
--      (keep, source, year) is silently dropped, which is the right outcome
--      because the dups are the source of truth's choice of which to keep.
--   3. CREATE UNIQUE INDEX is wrapped in a PL/pgSQL DO block that catches
--      unique_violation and re-raises as P0001 (which is NOT in TOLERATED_CODES
--      so the runner has no way to swallow it even without @notolerate).


-- 1) Build (drop_id, keep_id) pairs.
DROP TABLE IF EXISTS _dedup_pairs_44;
CREATE TEMP TABLE _dedup_pairs_44 (
    drop_id UUID NOT NULL,
    keep_id UUID NOT NULL
);

INSERT INTO _dedup_pairs_44 (drop_id, keep_id)
WITH ranked AS (
    SELECT
        company_id,
        LOWER(TRIM(name)) AS canonical_name,
        COALESCE(country_code, '') AS canonical_cc,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(name)), COALESCE(country_code, '')
            ORDER BY (
                SELECT COUNT(*) FROM company_climate_disclosures cd
                WHERE cd.company_id = c.company_id
            ) DESC,
            c.created_at ASC
        ) AS rn
    FROM companies c
),
canonicals AS (
    SELECT canonical_name, canonical_cc, company_id AS keep_id
    FROM ranked WHERE rn = 1
)
SELECT r.company_id, k.keep_id
FROM ranked r
JOIN canonicals k
  ON r.canonical_name = k.canonical_name
 AND r.canonical_cc = k.canonical_cc
WHERE r.rn > 1;


-- 2) Reassign disclosures to canonical safely. INSERT...SELECT into canonical
--    with ON CONFLICT DO NOTHING — handles BOTH:
--      a) drop's disclosure conflicts with keep's existing one -> skip
--      b) two drops have same (source, year) -> first wins, second skipped
--    (a) was 043's only-handled case; (b) is what crashed 043.
INSERT INTO company_climate_disclosures (
    disclosure_id, company_id, source, reporting_year,
    scope1_tco2e, scope2_tco2e_market, scope2_tco2e_location, scope3_tco2e,
    scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, offset_based_claims,
    assurance_level, assurance_provider, methodology_version, raw_record,
    fetched_at
)
SELECT
    uuid_generate_v4(), d.keep_id, cd.source, cd.reporting_year,
    cd.scope1_tco2e, cd.scope2_tco2e_market, cd.scope2_tco2e_location, cd.scope3_tco2e,
    cd.scope1_2_verified, cd.sbti_validated, cd.target_year, cd.baseline_year,
    cd.target_pct_reduction, cd.net_zero_target_year, cd.offset_based_claims,
    cd.assurance_level, cd.assurance_provider, cd.methodology_version, cd.raw_record,
    cd.fetched_at
FROM company_climate_disclosures cd
JOIN _dedup_pairs_44 d ON cd.company_id = d.drop_id
WHERE NOT EXISTS (
    SELECT 1 FROM company_climate_disclosures keep_cd
    WHERE keep_cd.company_id = d.keep_id
      AND keep_cd.source = cd.source
      AND keep_cd.reporting_year = cd.reporting_year
)
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;


-- 3) Reassign company_claims to canonical. No unique constraint on this table,
--    so a plain UPDATE is safe.
UPDATE company_claims cc
SET company_id = d.keep_id
FROM _dedup_pairs_44 d
WHERE cc.company_id = d.drop_id;


-- 4) Delete duplicate company rows. ON DELETE CASCADE on
--    company_climate_disclosures.company_id (mig 029) cleans up any
--    remaining drop disclosures that step 2 didn't move.
DELETE FROM companies
WHERE company_id IN (SELECT drop_id FROM _dedup_pairs_44);


-- 5) Recreate the non-null partial unique index inside a DO block so 23505
--    surfaces as P0001 (untolerated) instead of being silently swallowed.
DO $$
BEGIN
    DROP INDEX IF EXISTS uq_companies_name_country;
    CREATE UNIQUE INDEX uq_companies_name_country
        ON companies (LOWER(TRIM(name)), country_code)
        WHERE country_code IS NOT NULL;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION
            'Migration 044: uq_companies_name_country create failed - duplicates remain in non-null country space'
            USING ERRCODE = 'P0001';
END $$;


-- 6) Create the null-country partial unique index. Same defensive wrapping.
DO $$
BEGIN
    DROP INDEX IF EXISTS uq_companies_name_nocountry;
    CREATE UNIQUE INDEX uq_companies_name_nocountry
        ON companies (LOWER(TRIM(name)))
        WHERE country_code IS NULL;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION
            'Migration 044: uq_companies_name_nocountry create failed - duplicates remain in null country space'
            USING ERRCODE = 'P0001';
END $$;


-- 7) Final hard assertion across both dup spaces. P0001 never tolerated.
DO $$
DECLARE
    dup_with_cc INTEGER;
    dup_no_cc INTEGER;
    final_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_with_cc
    FROM (
        SELECT LOWER(TRIM(name)), country_code, COUNT(*) AS n
        FROM companies
        WHERE country_code IS NOT NULL
        GROUP BY LOWER(TRIM(name)), country_code
        HAVING COUNT(*) > 1
    ) dups;

    SELECT COUNT(*) INTO dup_no_cc
    FROM (
        SELECT LOWER(TRIM(name)), COUNT(*) AS n
        FROM companies
        WHERE country_code IS NULL
        GROUP BY LOWER(TRIM(name))
        HAVING COUNT(*) > 1
    ) dups;

    SELECT COUNT(*) INTO final_count FROM companies;

    RAISE NOTICE 'Migration 044: % companies; % with-country dup groups; % null-country dup groups',
        final_count, dup_with_cc, dup_no_cc;

    IF dup_with_cc > 0 OR dup_no_cc > 0 THEN
        RAISE EXCEPTION
            'Migration 044 FAILED: % with-country + % null-country dup groups remain',
            dup_with_cc, dup_no_cc
            USING ERRCODE = 'P0001';
    END IF;
END
$$;

DROP TABLE IF EXISTS _dedup_pairs_44;
