-- Migration 043: companies dedup pass 2 — fresh hash so it actually runs.
--
-- Why this exists:
--   - Mig 038 was supposed to be the "final" dedup with a hard P0001
--     assertion. It ran successfully at the time. Subsequent SBTi adapter
--     syncs (refactored to a background-task pattern in Phase 8) re-inserted
--     duplicates because:
--       (a) upsert_company was read-then-INSERT with no ON CONFLICT, so
--           two concurrent adapter rows could pass the SELECT and both
--           INSERT. The non-null partial unique index `uq_companies_name_country`
--           caught the second one — but the first survived.
--       (b) The partial index only covers `WHERE country_code IS NOT NULL`.
--           SBTi rows whose location wasn't in the adapter's tiny 33-entry
--           map stored country_code=NULL, free to duplicate without bound.
--   - Production verification on 2026-05-25 still showed 12× "2Connect",
--     9× "2050 Consulting" SE, 6× "20Cube Logistics Limited" etc.
--
-- This migration:
--   1. Re-dedupes by (LOWER(TRIM(name)), COALESCE(country_code,'')) — same
--      keep-canonical strategy as 038.
--   2. Adds a complementary partial unique index for the NULL-country case
--      so the upsert_company ON CONFLICT clause can protect it too.
--   3. Hard-asserts both dup spaces are empty post-cleanup.
--
-- See feedback_migration_tolerate_errors.md for why a NEW migration is
-- required rather than editing 038.


-- 1) Materialise (drop_id, keep_id) pairs.
DROP TABLE IF EXISTS _dedup_pairs_43;
CREATE TEMP TABLE _dedup_pairs_43 (
    drop_id UUID NOT NULL,
    keep_id UUID NOT NULL
);

INSERT INTO _dedup_pairs_43 (drop_id, keep_id)
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


-- 2) Drop disclosures that would violate uq_disclosure on (source, reporting_year).
DELETE FROM company_climate_disclosures cd
USING _dedup_pairs_43 d
WHERE cd.company_id = d.drop_id
  AND EXISTS (
      SELECT 1 FROM company_climate_disclosures canonical
      WHERE canonical.company_id = d.keep_id
        AND canonical.source = cd.source
        AND canonical.reporting_year = cd.reporting_year
  );


-- 3) Reassign remaining disclosures to canonical.
UPDATE company_climate_disclosures cd
SET company_id = d.keep_id
FROM _dedup_pairs_43 d
WHERE cd.company_id = d.drop_id;


-- 4) Reassign company_claims to canonical.
UPDATE company_claims cc
SET company_id = d.keep_id
FROM _dedup_pairs_43 d
WHERE cc.company_id = d.drop_id;


-- 5) Delete duplicate company rows.
DELETE FROM companies
WHERE company_id IN (SELECT drop_id FROM _dedup_pairs_43);


-- 6) Recreate the non-null partial unique index (idempotent).
DROP INDEX IF EXISTS uq_companies_name_country;
CREATE UNIQUE INDEX uq_companies_name_country
    ON companies (LOWER(TRIM(name)), country_code)
    WHERE country_code IS NOT NULL;


-- 7) NEW: complementary partial unique index for NULL country_code. Without
-- this, unmapped SBTi rows have no DB-level uniqueness — exactly the regression
-- pattern that produced the live dup explosion.
DROP INDEX IF EXISTS uq_companies_name_nocountry;
CREATE UNIQUE INDEX uq_companies_name_nocountry
    ON companies (LOWER(TRIM(name)))
    WHERE country_code IS NULL;


-- 8) Hard assertion: post-dedup, neither dup space has any group > 1.
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

    RAISE NOTICE 'Migration 043: % companies; % with-country dup groups; % null-country dup groups',
        final_count, dup_with_cc, dup_no_cc;

    IF dup_with_cc > 0 OR dup_no_cc > 0 THEN
        RAISE EXCEPTION 'Migration 043 FAILED: % with-country + % null-country dup groups remain',
            dup_with_cc, dup_no_cc;
    END IF;
END
$$;

DROP TABLE IF EXISTS _dedup_pairs_43;
