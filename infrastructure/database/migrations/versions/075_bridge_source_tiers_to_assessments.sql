-- Migration 075: bridge source_credibility_tiers -> source_profiles labels
-- (ML-12 data-correctness fix, 2026-07-02)
--
-- THE BUG: 68/109 source_profiles still render editorial/fact_check/
-- transparency = 'unknown' (Reuters, Carbon Brief, the Guardian, ...) even
-- though source_credibility_tiers holds an evidence-backed T1/T2/T3
-- classification for them — with a public evidence_url AND 3-axis numeric
-- scores (mig 041). Migration 070 only derived labels from a profile's OWN
-- per-article signals; it left every no-article profile 'unknown', which is
-- exactly the set that IS tier-classified.
--
-- THE FIX: for rows still 'unknown' (or NULL), copy the evidence-backed tier
-- classification across, joining source_profiles -> source_credibility_tiers by
-- normalised domain OR source_name (the tier table is keyed by domain, but a
-- large slice of profiles carry a fabricated slug domain and only match by
-- name — same recovery the read-path _attach_credibility_tiers uses).
--
-- Derivation from the tier's 3-axis scores MUST match the Python
-- _assessment_from_tier_scores() (app/domains/content/source_profiles.py):
--   editorial_score    >=75 rigorous | >=50 moderate | else limited
--   transparency_score >=75 high     | >=50 moderate | else low
--   factcheck_score    >=85 excellent| >=70 good | >=50 mixed | else poor
-- Each axis uses the tier row's explicit score when present, else the tier-LEVEL
-- default (copied from migration 041): T1 90/90/90, T2 70/75/65, T3 55/50/60.
-- Most tier rows added by the feed-expansion migrations (033/054/058/060/066/068)
-- ran AFTER 041 and so have NULL axis scores, but the T1/T2/T3 level is itself
-- evidence-backed (public evidence_url) — so we bridge from the level.
-- 'unknown'/'retracted' tiers are left untouched (no invented rating).
--
-- HONESTY: these labels remain a restatement of THIS platform's reliability
-- tiering (now sourced from the evidence-backed tier table with a public
-- evidence_url), NOT an independent third-party audit — the Sources card +
-- methodology copy say so.
--
-- Idempotent: only fills columns currently NULL / 'unknown'; existing
-- non-unknown values are preserved. Re-running is a no-op.

WITH best_tier AS (
    -- Highest tier per profile when several rows match (T1 > T2 > T3). Each axis
    -- coalesces the explicit score with the tier-level default (mig 041).
    SELECT DISTINCT ON (sp.source_id)
        sp.source_id,
        sct.tier,
        COALESCE(sct.editorial_score,
                 CASE sct.tier WHEN 'T1' THEN 90 WHEN 'T2' THEN 70 WHEN 'T3' THEN 55 END
        ) AS editorial_score,
        COALESCE(sct.factcheck_score,
                 CASE sct.tier WHEN 'T1' THEN 90 WHEN 'T2' THEN 75 WHEN 'T3' THEN 50 END
        ) AS factcheck_score,
        COALESCE(sct.transparency_score,
                 CASE sct.tier WHEN 'T1' THEN 90 WHEN 'T2' THEN 65 WHEN 'T3' THEN 60 END
        ) AS transparency_score
    FROM source_profiles sp
    JOIN source_credibility_tiers sct
      ON (
            COALESCE(sp.source_domain, '') <> ''
            AND regexp_replace(lower(sp.source_domain), '^www\.', '')
              = regexp_replace(lower(COALESCE(sct.domain, '')), '^www\.', '')
         )
      OR (
            COALESCE(sp.source_name, '') <> ''
            AND lower(sp.source_name) = lower(COALESCE(sct.source_name, ''))
         )
    WHERE sct.tier IN ('T1', 'T2', 'T3')
    ORDER BY sp.source_id,
             CASE sct.tier WHEN 'T1' THEN 3 WHEN 'T2' THEN 2 WHEN 'T3' THEN 1 ELSE 0 END DESC
)
UPDATE source_profiles sp
SET
    editorial_standards = CASE
        WHEN sp.editorial_standards IS NULL OR sp.editorial_standards = 'unknown'
        THEN CASE
                 WHEN bt.editorial_score >= 75 THEN 'rigorous'
                 WHEN bt.editorial_score >= 50 THEN 'moderate'
                 ELSE 'limited'
             END
        ELSE sp.editorial_standards
    END,
    transparency_level = CASE
        WHEN sp.transparency_level IS NULL OR sp.transparency_level = 'unknown'
        THEN CASE
                 WHEN bt.transparency_score >= 75 THEN 'high'
                 WHEN bt.transparency_score >= 50 THEN 'moderate'
                 ELSE 'low'
             END
        ELSE sp.transparency_level
    END,
    fact_check_record = CASE
        WHEN sp.fact_check_record IS NULL OR sp.fact_check_record = 'unknown'
        THEN CASE
                 WHEN bt.factcheck_score >= 85 THEN 'excellent'
                 WHEN bt.factcheck_score >= 70 THEN 'good'
                 WHEN bt.factcheck_score >= 50 THEN 'mixed'
                 ELSE 'poor'
             END
        ELSE sp.fact_check_record
    END,
    last_updated_at = CURRENT_TIMESTAMP
FROM best_tier bt
WHERE bt.source_id = sp.source_id
  AND (
        sp.editorial_standards IS NULL OR sp.editorial_standards = 'unknown'
     OR sp.fact_check_record   IS NULL OR sp.fact_check_record   = 'unknown'
     OR sp.transparency_level  IS NULL OR sp.transparency_level  = 'unknown'
  );

DO $$
DECLARE
    bridged INT;
    total INT;
BEGIN
    SELECT COUNT(*) INTO total FROM source_profiles;
    SELECT COUNT(*) INTO bridged
    FROM source_profiles
    WHERE editorial_standards IS NOT NULL AND editorial_standards <> 'unknown';
    RAISE NOTICE 'migration 075: %/% source_profiles now carry an editorial assessment (tier-bridged where no article signal)', bridged, total;
END $$;
