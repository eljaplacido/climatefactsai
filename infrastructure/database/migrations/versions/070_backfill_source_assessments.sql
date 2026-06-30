-- Migration 070: backfill source_profiles editorial/factcheck/transparency
-- (data-completeness Fix A, 2026-06-30)
--
-- THE BUG: source_profiles.editorial_standards / fact_check_record /
-- transparency_level default to 'unknown' and were written by NO code path,
-- so the Sources UI rendered "Not assessed" for every single source — the
-- loudest data-completeness complaint. Yet the same rows carry real signals:
-- credibility_score, average_reliability_score, reliability_tier and
-- false_claim_rate.
--
-- THE FIX: derive the three string labels from those numeric/tier signals.
-- This mirrors EXACTLY the Python derive_source_assessment() used going
-- forward in the upsert path (app/domains/content/source_profiles.py), so the
-- backfill and the live path agree.
--
-- HONESTY: these labels are a defensible restatement of the platform's OWN
-- reliability tiering and historical article analysis — NOT an independent
-- third-party editorial or fact-check audit. The Sources page + SourceProfile
-- card + benchmark evaluation copy all say so explicitly. We never invent a
-- rating: rows with genuinely no signal keep 'unknown'.
--
-- Derivation (must match derive_source_assessment):
--   high-quality tier (scientific/research)  -> band 'high'
--   else effective score (credibility_score, falling back to
--        average_reliability_score):  >=75 high | >=50 moderate | <50 low
--   editorial:     high->rigorous  moderate->moderate  low->limited
--   transparency:  high->high      moderate->moderate  low->low
--   fact_check:    false_claim_rate >=15% -> poor; >=5% -> mixed; else
--                  high band -> excellent (score>=85) / good, otherwise mixed
--   no signal (no articles, no curated tier, no false-claim rate) -> unchanged
--
-- Idempotent: only fills columns that are currently NULL / 'unknown' (an
-- existing non-unknown value is preserved), and only touches rows that carry a
-- genuine signal. Re-running is a no-op once a row's labels are filled.

-- Guarantee the tier column exists (some clusters seed it only via
-- apply_all_migrations.sql; the service also guards for its absence).
ALTER TABLE source_profiles
    ADD COLUMN IF NOT EXISTS reliability_tier VARCHAR(20) DEFAULT 'public';

WITH derived AS (
    SELECT
        source_id,
        LOWER(COALESCE(reliability_tier, '')) IN ('scientific', 'research') AS hq_tier,
        COALESCE(false_claim_rate, 0)::float AS fcr,
        COALESCE(credibility_score, average_reliability_score)::float AS score,
        (
            COALESCE(total_articles_analyzed, 0) > 0
            OR average_reliability_score IS NOT NULL
            OR LOWER(COALESCE(reliability_tier, '')) IN ('scientific', 'research')
            OR COALESCE(false_claim_rate, 0) > 0
        ) AS has_signal
    FROM source_profiles
),
banded AS (
    SELECT
        source_id, fcr, score,
        CASE
            WHEN NOT has_signal THEN NULL
            WHEN hq_tier         THEN 'high'
            WHEN score IS NULL   THEN NULL
            WHEN score >= 75     THEN 'high'
            WHEN score >= 50     THEN 'moderate'
            ELSE 'low'
        END AS band
    FROM derived
)
UPDATE source_profiles sp
SET
    editorial_standards = CASE
        WHEN sp.editorial_standards IS NULL OR sp.editorial_standards = 'unknown'
        THEN CASE b.band
                 WHEN 'high'     THEN 'rigorous'
                 WHEN 'moderate' THEN 'moderate'
                 WHEN 'low'      THEN 'limited'
             END
        ELSE sp.editorial_standards
    END,
    transparency_level = CASE
        WHEN sp.transparency_level IS NULL OR sp.transparency_level = 'unknown'
        THEN CASE b.band
                 WHEN 'high'     THEN 'high'
                 WHEN 'moderate' THEN 'moderate'
                 WHEN 'low'      THEN 'low'
             END
        ELSE sp.transparency_level
    END,
    fact_check_record = CASE
        WHEN sp.fact_check_record IS NULL OR sp.fact_check_record = 'unknown'
        THEN CASE
                 WHEN b.fcr >= 0.15 THEN 'poor'
                 WHEN b.fcr >= 0.05 THEN 'mixed'
                 WHEN b.band = 'high' AND COALESCE(b.score, 0) >= 85 THEN 'excellent'
                 WHEN b.band = 'high' THEN 'good'
                 ELSE 'mixed'
             END
        ELSE sp.fact_check_record
    END,
    last_updated_at = CURRENT_TIMESTAMP
FROM banded b
WHERE b.source_id = sp.source_id
  AND b.band IS NOT NULL
  AND (
        sp.editorial_standards IS NULL OR sp.editorial_standards = 'unknown'
     OR sp.fact_check_record   IS NULL OR sp.fact_check_record   = 'unknown'
     OR sp.transparency_level  IS NULL OR sp.transparency_level  = 'unknown'
  );

DO $$
DECLARE
    assessed INT;
    total INT;
BEGIN
    SELECT COUNT(*) INTO total FROM source_profiles;
    SELECT COUNT(*) INTO assessed
    FROM source_profiles
    WHERE editorial_standards IS NOT NULL AND editorial_standards <> 'unknown';
    RAISE NOTICE 'migration 070: %/% source_profiles now carry a derived editorial assessment', assessed, total;
END $$;
