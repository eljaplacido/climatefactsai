-- Migration 036: dedupe companies created by adapter syncs before the
-- repository.upsert_company name+country fallback was added.
--
-- Background: SBTi rows mostly lack ticker / isin / lei. The original
-- upsert_company only dedupe'd on those identifier columns, so each
-- SBTi target row created a fresh company_id. Cloud DB had hundreds of
-- duplicates after the first live sync (e.g., "100 Percent Group Limited"
-- twice, "Aaseya IT Services Pvt Ltd" twice).
--
-- This migration:
--   1. For each (LOWER(TRIM(name)), country_code) group with >1 row,
--      pick the company_id with the most existing disclosures as the
--      canonical row (tie-broken by oldest created_at).
--   2. Reassign all disclosures and claims from duplicates to the
--      canonical company_id.
--   3. Delete the duplicate company rows.
--   4. Wrap in a transaction so partial-apply is impossible.
--
-- Idempotent: re-running it after the first pass is a no-op because
-- there will be no duplicates to find.

BEGIN;

WITH ranked AS (
    SELECT
        company_id,
        LOWER(TRIM(name)) AS canonical_name,
        country_code,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(name)), COALESCE(country_code, '__null__')
            ORDER BY (
                SELECT COUNT(*) FROM company_climate_disclosures cd
                WHERE cd.company_id = c.company_id
            ) DESC,
            c.created_at ASC
        ) AS rn
    FROM companies c
),
canonicals AS (
    SELECT canonical_name, country_code, company_id AS keep_id
    FROM ranked WHERE rn = 1
),
duplicates AS (
    SELECT r.company_id AS drop_id, k.keep_id
    FROM ranked r
    JOIN canonicals k
      ON r.canonical_name = k.canonical_name
     AND COALESCE(r.country_code, '__null__') = COALESCE(k.country_code, '__null__')
    WHERE r.rn > 1
)
-- 1) Reassign disclosures
UPDATE company_climate_disclosures cd
SET company_id = d.keep_id
FROM duplicates d
WHERE cd.company_id = d.drop_id;

-- (Same WITH-block can't span statements; re-build duplicates set inline.)
WITH ranked AS (
    SELECT
        company_id,
        LOWER(TRIM(name)) AS canonical_name,
        country_code,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(name)), COALESCE(country_code, '__null__')
            ORDER BY (
                SELECT COUNT(*) FROM company_climate_disclosures cd
                WHERE cd.company_id = c.company_id
            ) DESC,
            c.created_at ASC
        ) AS rn
    FROM companies c
),
canonicals AS (
    SELECT canonical_name, country_code, company_id AS keep_id
    FROM ranked WHERE rn = 1
),
duplicates AS (
    SELECT r.company_id AS drop_id, k.keep_id
    FROM ranked r
    JOIN canonicals k
      ON r.canonical_name = k.canonical_name
     AND COALESCE(r.country_code, '__null__') = COALESCE(k.country_code, '__null__')
    WHERE r.rn > 1
)
-- 2) Reassign claims
UPDATE company_claims cc
SET company_id = d.keep_id
FROM duplicates d
WHERE cc.company_id = d.drop_id;

-- 3) Delete duplicate company rows
WITH ranked AS (
    SELECT
        company_id,
        LOWER(TRIM(name)) AS canonical_name,
        country_code,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(name)), COALESCE(country_code, '__null__')
            ORDER BY (
                SELECT COUNT(*) FROM company_climate_disclosures cd
                WHERE cd.company_id = c.company_id
            ) DESC,
            c.created_at ASC
        ) AS rn
    FROM companies c
)
DELETE FROM companies
WHERE company_id IN (SELECT company_id FROM ranked WHERE rn > 1);

-- 4) Add a partial-unique index so future inserts can't recreate the dup
--    when both name + country_code are present. Lower(trim) functional
--    index for case/whitespace-insensitive matching.
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_country
    ON companies (LOWER(TRIM(name)), country_code)
    WHERE country_code IS NOT NULL;

DO $$
DECLARE
    n_companies INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_companies FROM companies;
    RAISE NOTICE 'Migration 036 complete: % companies after dedupe', n_companies;
END
$$;

COMMIT;
