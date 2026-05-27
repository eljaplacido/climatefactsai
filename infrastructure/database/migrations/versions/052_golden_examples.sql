-- Migration 052: golden_examples table (2026-05-27, post-Stage-5)
--
-- The user's framing: "Also remember to update and maintain the
-- 'golden examples' of generated article / their data insights, as
-- well as report, company climate tracker and map insights etc.
-- artifacts. So that we always have the best case examples to refer
-- to and which guide also the development of gx10 local inference
-- workflows, when we stop again to run those in the background for
-- enrichments."
--
-- Two uses:
--   1. Reference quality benchmark — "what does a great X look like?"
--   2. Training data seeds for the LoRA specialists referenced in
--      docs/reports/asusgx10inferencestrategy.md (claim-extractor-7B,
--      context-summarizer-7B, verdict-adjudicator-7B).

CREATE TABLE IF NOT EXISTS golden_examples (
    golden_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- What kind of artifact this points to
    artifact_kind   TEXT NOT NULL CHECK (artifact_kind IN (
        'article_enrichment',     -- a specific article's brief/excerpt/context
        'research_analysis',      -- a research-paper analysis run
        'company_verdict',        -- a corporate claim verdict
        'semantic_explanation',   -- an /api/semantic/explain output
        'map_insight',            -- a map-derived systemic insight (M8)
        'kg_drill_down'           -- an /explore/entity/{id} traversal
    )),
    -- Foreign key into the appropriate table (loose ref — no constraint
    -- since artifact_kind picks the table). Stored as text to allow UUID
    -- or composite keys (e.g. (article_id, claim_id) for fact-check golden).
    artifact_ref    TEXT NOT NULL,
    -- Why this is golden — short curator note. Surfaces in the
    -- /api/golden-examples listing + docs/golden-examples/<kind>.md.
    why_golden      TEXT NOT NULL,
    -- Numeric quality rating 1-5 (5 = best). For LoRA training the
    -- exporter filters to >= 4.
    quality_score   SMALLINT NOT NULL DEFAULT 4 CHECK (quality_score BETWEEN 1 AND 5),
    -- Optional category tag for browse / filtering
    domain_tag      TEXT,
    -- Curator identity (user_id for signed-in, null for auto-promoted)
    curator_id      UUID,
    -- Audit trail
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Idempotent per kind+ref so re-promotion doesn't insert duplicates
    CONSTRAINT golden_examples_kind_ref_uq UNIQUE (artifact_kind, artifact_ref)
);

CREATE INDEX IF NOT EXISTS idx_golden_examples_kind
    ON golden_examples(artifact_kind, quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_golden_examples_recent
    ON golden_examples(created_at DESC);
