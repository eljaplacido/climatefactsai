-- Migration 038: force re-dedup of companies because 036 was silently tolerated.
--
-- Background: migration 036 ran with MIGRATIONS_TOLERATE_ERRORS=true and
-- a sequencing bug. The runner marked it as "applied" but the dedup
-- DELETE/UPDATE never completed. Cloud DB still has 3x copies of every
-- SBTi-ingested company. This migration does it again, clean.
--
-- Strategy (each statement self-contained):
--   1. Insert (drop_id, keep_id) pairs into a session temp table
--   2. Delete disclosure rows that would conflict with canonical on
--      (source, reporting_year) — canonical wins
--   3. Reassign remaining disclosure rows to canonical
--   4. Reassign claim rows to canonical
--   5. Delete duplicate company rows
--   6. Hard assertion: no more (name, country_code) groups with rn > 1
--
-- Idempotent: re-runs after success find no duplicates and exit clean.


-- 1) Materialise pairs.
DROP TABLE IF EXISTS _dedup_pairs_38;
CREATE TEMP TABLE _dedup_pairs_38 (
    drop_id UUID NOT NULL,
    keep_id UUID NOT NULL
);

INSERT INTO _dedup_pairs_38 (drop_id, keep_id)
WITH ranked AS (
    SELECT
        company_id,
        LOWER(TRIM(name)) AS canonical_name,
        country_code,
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
    SELECT canonical_name, country_code, company_id AS keep_id
    FROM ranked WHERE rn = 1
)
SELECT r.company_id, k.keep_id
FROM ranked r
JOIN canonicals k
  ON r.canonical_name = k.canonical_name
 AND COALESCE(r.country_code, '') = COALESCE(k.country_code, '')
WHERE r.rn > 1;


-- 2) Drop disclosures that would violate uq_disclosure on (source, reporting_year)
DELETE FROM company_climate_disclosures cd
USING _dedup_pairs_38 d
WHERE cd.company_id = d.drop_id
  AND EXISTS (
      SELECT 1 FROM company_climate_disclosures canonical
      WHERE canonical.company_id = d.keep_id
        AND canonical.source = cd.source
        AND canonical.reporting_year = cd.reporting_year
  );


-- 3) Reassign remaining disclosures.
UPDATE company_climate_disclosures cd
SET company_id = d.keep_id
FROM _dedup_pairs_38 d
WHERE cd.company_id = d.drop_id;


-- 4) Reassign claims.
UPDATE company_claims cc
SET company_id = d.keep_id
FROM _dedup_pairs_38 d
WHERE cc.company_id = d.drop_id;


-- 5) Delete duplicate company rows.
DELETE FROM companies
WHERE company_id IN (SELECT drop_id FROM _dedup_pairs_38);


-- 6) Drop and recreate the partial-unique index so future inserts can't
-- re-create the duplication pattern at all.
DROP INDEX IF EXISTS uq_companies_name_country;
CREATE UNIQUE INDEX uq_companies_name_country
    ON companies (LOWER(TRIM(name)), country_code)
    WHERE country_code IS NOT NULL;


-- 7) Hard assertion: post-dedup, no (name, country_code) group has > 1 row.
DO $$
DECLARE
    dup_count INTEGER;
    final_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT LOWER(TRIM(name)), country_code, COUNT(*) AS n
        FROM companies
        WHERE country_code IS NOT NULL
        GROUP BY LOWER(TRIM(name)), country_code
        HAVING COUNT(*) > 1
    ) dups;

    SELECT COUNT(*) INTO final_count FROM companies;

    RAISE NOTICE 'Migration 038 complete: % companies, % duplicate groups remaining',
        final_count, dup_count;

    IF dup_count > 0 THEN
        RAISE EXCEPTION 'Migration 038 FAILED — % duplicate groups still exist', dup_count;
    END IF;
END
$$;

DROP TABLE IF EXISTS _dedup_pairs_38;
