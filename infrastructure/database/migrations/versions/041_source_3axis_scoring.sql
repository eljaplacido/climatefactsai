-- Migration 041: 3-axis source scoring (editorial / factcheck / transparency)
-- Phase 10 (2026-05-25). Per production-review feedback: "many sources
-- not scored in editorial standards, fact-check and transparency".
--
-- Adds three scoring columns to source_credibility_tiers + populates
-- them with tier-based defaults. The defaults are starting points
-- the editorial team can override per source.
--
-- Rubric:
--   editorial_score (0-100): editorial standards rigor — masthead, correction
--     policy, named author bylines, ownership transparency
--   factcheck_score (0-100): independent fact-check engagement — IFCN
--     verification, third-party retraction record, claim-level corrections
--   transparency_score (0-100): funding transparency, ownership disclosure,
--     methodology publication, conflict-of-interest disclosures
--
-- Tier defaults (each source can be hand-tuned via UPDATE):
--   T1 (Q1 / IFCN-verified)         → 90 / 90 / 90
--   T2 (Q2 / mainstream w/ corrections) → 70 / 75 / 65
--   T3 (Q3-Q4 / NGO w/ sourcing)    → 55 / 50 / 60
--   unknown                          → 30 / 25 / 30
--   retracted                       →  5 /  5 /  5

ALTER TABLE source_credibility_tiers
    ADD COLUMN IF NOT EXISTS editorial_score    INTEGER CHECK (editorial_score    BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS factcheck_score    INTEGER CHECK (factcheck_score    BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS transparency_score INTEGER CHECK (transparency_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS scoring_rubric_url TEXT
        DEFAULT 'https://github.com/eljaplacido/climatefactsai/blob/main/docs/methodology/source-scoring.md',
    ADD COLUMN IF NOT EXISTS scoring_last_reviewed_at TIMESTAMPTZ;

-- Tier-based defaults for rows that don't have explicit scores yet.
UPDATE source_credibility_tiers
SET editorial_score    = COALESCE(editorial_score,    90),
    factcheck_score    = COALESCE(factcheck_score,    90),
    transparency_score = COALESCE(transparency_score, 90)
WHERE tier = 'T1';

UPDATE source_credibility_tiers
SET editorial_score    = COALESCE(editorial_score,    70),
    factcheck_score    = COALESCE(factcheck_score,    75),
    transparency_score = COALESCE(transparency_score, 65)
WHERE tier = 'T2';

UPDATE source_credibility_tiers
SET editorial_score    = COALESCE(editorial_score,    55),
    factcheck_score    = COALESCE(factcheck_score,    50),
    transparency_score = COALESCE(transparency_score, 60)
WHERE tier = 'T3';

UPDATE source_credibility_tiers
SET editorial_score    = COALESCE(editorial_score,    30),
    factcheck_score    = COALESCE(factcheck_score,    25),
    transparency_score = COALESCE(transparency_score, 30)
WHERE tier = 'unknown';

UPDATE source_credibility_tiers
SET editorial_score    = COALESCE(editorial_score,     5),
    factcheck_score    = COALESCE(factcheck_score,     5),
    transparency_score = COALESCE(transparency_score,  5)
WHERE tier = 'retracted';

-- Hand-curated overrides for known sources where the tier default
-- doesn't reflect actual practice. Each row carries an evidence
-- note so future maintainers know why.

-- Reuters: IFCN-verified, NewsGuard 100/100, strong corrections.
UPDATE source_credibility_tiers
SET editorial_score = 92, factcheck_score = 88, transparency_score = 85,
    notes = COALESCE(notes, '') || ' | IFCN-verified, NewsGuard 100/100'
WHERE source_name ILIKE '%Reuters%';

-- Associated Press: similar profile to Reuters.
UPDATE source_credibility_tiers
SET editorial_score = 92, factcheck_score = 90, transparency_score = 82,
    notes = COALESCE(notes, '') || ' | AP standards manual, IFCN cooperative'
WHERE source_name ILIKE '%Associated Press%' OR source_name ILIKE '%AP News%';

-- Carbon Brief: research-tier with explicit methodology pages.
UPDATE source_credibility_tiers
SET editorial_score = 88, factcheck_score = 92, transparency_score = 95,
    notes = COALESCE(notes, '') || ' | Methodology pages, funding disclosure'
WHERE source_name ILIKE '%Carbon Brief%';

-- IPCC: institutional scientific source.
UPDATE source_credibility_tiers
SET editorial_score = 95, factcheck_score = 95, transparency_score = 98,
    notes = COALESCE(notes, '') || ' | Peer review + open methodology'
WHERE source_name ILIKE '%IPCC%';

-- Inside Climate News: Pulitzer-winning specialist outlet.
UPDATE source_credibility_tiers
SET editorial_score = 85, factcheck_score = 85, transparency_score = 80,
    notes = COALESCE(notes, '') || ' | Pulitzer 2013, nonprofit + funding disclosed'
WHERE source_name ILIKE '%Inside Climate News%';

-- Google News aggregator: aggregates from local publishers; lower
-- editorial/transparency since it doesn't have its own newsroom.
UPDATE source_credibility_tiers
SET editorial_score = 40, factcheck_score = 35, transparency_score = 50,
    notes = COALESCE(notes, '') || ' | Aggregator; per-publisher scoring applies'
WHERE source_name ILIKE '%Google News%';

-- Track when this migration ran for the methodology audit trail.
UPDATE source_credibility_tiers
SET scoring_last_reviewed_at = NOW()
WHERE scoring_last_reviewed_at IS NULL;

-- Summary
DO $$
DECLARE
    n_scored INTEGER;
    n_total INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_total FROM source_credibility_tiers;
    SELECT COUNT(*) INTO n_scored
    FROM source_credibility_tiers
    WHERE editorial_score IS NOT NULL
      AND factcheck_score IS NOT NULL
      AND transparency_score IS NOT NULL;
    RAISE NOTICE 'Migration 041 complete: %/% sources have 3-axis scores',
        n_scored, n_total;
END
$$;
