-- Migration 036: dedupe companies created by adapter syncs before the
-- repository.upsert_company name+country fallback was added.
--
-- Background: SBTi rows mostly lack ticker / isin / lei. The original
-- upsert_company only dedupe'd on those identifier columns, so each
-- SBTi target row created a fresh company_id. Cloud DB had hundreds of
-- duplicates after the first live sync (e.g., "100 Percent Group Limited"
-- twice, "Aaseya IT Services Pvt Ltd" twice).
--
-- Strategy: materialise the duplicate-set into a temp table so it
-- survives across multiple statements (CTEs are per-statement only).
--
-- This migration:
--   1. Materialise the (drop_id, keep_id) pairs into _dup_pairs
--   2. Drop duplicate disclosures conflicting with the canonical
--   3. Reassign remaining (non-conflicting) disclosures to canonical
--   4. Reassign claims to canonical
--   5. Delete the duplicate company rows
--   6. Add a partial-unique index so future inserts can't recreate
--      the dup pattern (case/whitespace-insensitive on name + country)
--
-- Idempotent: re-running it after the first pass finds no duplicates
-- and is a no-op.
--
-- Note: NO explicit BEGIN/COMMIT — scripts/run_migrations.py already
-- wraps each migration in its own transaction via the psycopg2
-- connection context manager.


-- 1) Materialise (drop_id, keep_id) into a session-temp table.
DROP TABLE IF EXISTS _dup_pairs;
CREATE TEMP TABLE _dup_pairs (
    drop_id UUID NOT NULL,
    keep_id UUID NOT NULL
);

INSERT INTO _dup_pairs (drop_id, keep_id)
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
),
canonicals AS (
    SELECT canonical_name, country_code, company_id AS keep_id
    FROM ranked WHERE rn = 1
)
SELECT r.company_id AS drop_id, k.keep_id
FROM ranked r
JOIN canonicals k
  ON r.canonical_name = k.canonical_name
 AND COALESCE(r.country_code, '__null__') = COALESCE(k.country_code, '__null__')
WHERE r.rn > 1;


-- 2) Drop disclosures from the duplicate side that conflict with the
-- canonical's existing disclosure for the same (source, reporting_year).
DELETE FROM company_climate_disclosures cd
USING _dup_pairs d
WHERE cd.company_id = d.drop_id
  AND EXISTS (
      SELECT 1 FROM company_climate_disclosures canonical
      WHERE canonical.company_id = d.keep_id
        AND canonical.source = cd.source
        AND canonical.reporting_year = cd.reporting_year
  );


-- 3) Reassign remaining disclosures to the canonical company_id.
UPDATE company_climate_disclosures cd
SET company_id = d.keep_id
FROM _dup_pairs d
WHERE cd.company_id = d.drop_id;


-- 4) Reassign claims to the canonical company_id.
UPDATE company_claims cc
SET company_id = d.keep_id
FROM _dup_pairs d
WHERE cc.company_id = d.drop_id;


-- 5) Delete the duplicate company rows themselves.
DELETE FROM companies
WHERE company_id IN (SELECT drop_id FROM _dup_pairs);


-- 6) Add a partial-unique index so future inserts can't recreate the dup
-- when both name + country_code are present. Lower(trim) functional index
-- for case/whitespace-insensitive matching. Skipped when country_code is
-- NULL because (NULL, NULL) compares as NULL — would let unidentified
-- companies still duplicate; that's an upsert_company concern.
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_country
    ON companies (LOWER(TRIM(name)), country_code)
    WHERE country_code IS NOT NULL;


-- Cleanup + summary
DROP TABLE IF EXISTS _dup_pairs;

DO $$
DECLARE
    n_companies INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_companies FROM companies;
    RAISE NOTICE 'Migration 036 complete: % companies after dedupe', n_companies;
END
$$;
