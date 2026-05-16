-- =============================================================================
-- 021_claim_provenance.sql — Per-claim audit trail (Phase 4 wave 3)
-- =============================================================================
-- Every analytical output the platform produces (extracted claim, synthesised
-- answer, classified domain, hallucination-checked text) leaves a row here
-- recording HOW it was produced. The audit-trail API surfaces these to users
-- and external auditors so any displayed score can be traced to:
--
--   * The model that produced it
--   * The exact prompt (name + version + content-fingerprint)
--   * The retrieval strategy used to gather context
--   * The source articles that fed into the LLM call
--   * The hallucination-check verdict (when run)
--   * The wall-clock timestamp
--
-- This is the Traceability axis of the truth-machine grade. Combined with
-- the methodology endpoint (wave 2), a user can answer "where did this
-- number come from?" by walking from the displayed value through
-- claim_provenance back to the indicator → adapter → upstream source.
--
-- Linkage:
--   * claim_id        — when a row in `claims` was produced
--   * url_analysis_id — when a URL-analysis claim extraction ran
--   * article_id      — when ingestion-time enrichment produced metadata
-- At least ONE of these must be set (CHECK constraint).
-- =============================================================================

CREATE TABLE IF NOT EXISTS claim_provenance (
    id                  BIGSERIAL PRIMARY KEY,

    -- Linkage to the artifact this provenance describes. Nullable so a row
    -- can attach to whichever object exists for this extraction path; the
    -- CHECK constraint requires at least one to be set.
    claim_id            UUID NULL,
    url_analysis_id     UUID NULL,
    article_id          UUID NULL,

    -- What ran
    extraction_method   VARCHAR(64) NOT NULL,
        -- e.g. 'url_analysis_claim_extraction',
        --      'deep_search_synthesis',
        --      'cynefin_classification',
        --      'hallucination_check',
        --      'article_ingestion_enrichment'
    model_name          VARCHAR(128),
        -- e.g. 'deepseek-chat', 'claude-sonnet-4-5', 'gpt-4o', 'onnx-minilm'

    -- Prompt provenance (resolved via prompts.PROMPTS registry where applicable)
    prompt_name         VARCHAR(64),
    prompt_version      VARCHAR(16),
    prompt_fingerprint  CHAR(16),

    -- Retrieval / context
    retrieval_strategy  TEXT,
        -- Human-readable description: 'fts+semantic+graph+RRF' /
        -- 'internal_corpus+perplexity_external+weather' / etc.
    source_article_ids  JSONB,
        -- ['uuid1','uuid2',...] — articles that fed into this call.

    -- Quality signals
    hallucination_score DOUBLE PRECISION,    -- 0–1 when computed by HallucinationDetector
    confidence          DOUBLE PRECISION,    -- 0–1 model/system-reported

    -- Metadata
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    raw_metadata        JSONB,               -- adapter-specific catch-all

    CONSTRAINT chk_claim_provenance_has_link CHECK (
        claim_id IS NOT NULL
        OR url_analysis_id IS NOT NULL
        OR article_id IS NOT NULL
    )
);

-- Hot paths: look up provenance by the artifact id.
CREATE INDEX IF NOT EXISTS idx_claim_provenance_claim_id
    ON claim_provenance(claim_id)
    WHERE claim_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claim_provenance_url_analysis_id
    ON claim_provenance(url_analysis_id)
    WHERE url_analysis_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claim_provenance_article_id
    ON claim_provenance(article_id)
    WHERE article_id IS NOT NULL;

-- Time-series queries (recent activity, drift detection in Phase 6).
CREATE INDEX IF NOT EXISTS idx_claim_provenance_created_at
    ON claim_provenance(created_at DESC);

-- Prompt-fingerprint queries — "find every claim produced under v1.0 of the
-- synthesis prompt" / "did anyone serve a response under fingerprint X?"
CREATE INDEX IF NOT EXISTS idx_claim_provenance_prompt_fingerprint
    ON claim_provenance(prompt_fingerprint)
    WHERE prompt_fingerprint IS NOT NULL;

COMMENT ON TABLE claim_provenance IS
    'Per-extraction audit trail. One row per analytical output describing '
    'which model + prompt + retrieval strategy produced it. Surfaced via '
    '/api/methodology/audit-trail/* endpoints.';

COMMENT ON COLUMN claim_provenance.extraction_method IS
    'The pipeline that produced this row. Use a stable, slugged string so '
    'downstream analytics (Phase 5 calibration) can group by method.';

COMMENT ON COLUMN claim_provenance.prompt_fingerprint IS
    '16-hex SHA-256 prefix of the prompt template + system. Drift detector '
    'in Phase 6 watches this distribution.';
