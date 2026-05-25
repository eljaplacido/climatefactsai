-- Migration 039: local_llm_fallbacks table + shadow_predictions for GX10 rollout
-- Phase 10 (2026-05-25). Foundation for routing LLM calls through a
-- provider abstraction with circuit-breaker fallback to a local GX10.
--
-- - local_llm_fallbacks: every time the primary provider for a workload
--   fails or its breaker is open and a fallback succeeds, we log the
--   primary, fallback, error class, error message, and latency. Lets
--   ops see provider reliability over time.
--
-- - shadow_predictions: when a workload is being shadow-tested before
--   promoting local-gx10 to primary, the call goes to BOTH providers,
--   the cloud answer is returned to the user, and the local answer is
--   stored here for offline scoring. Promotion criterion: local
--   accuracy >= cloud on the eval set.

CREATE TABLE IF NOT EXISTS local_llm_fallbacks (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workload          VARCHAR(64) NOT NULL,
    primary_provider  VARCHAR(64) NOT NULL,
    fallback_provider VARCHAR(64) NOT NULL,
    error_class       VARCHAR(64),
    error_message     TEXT,
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_fallbacks_workload_time
    ON local_llm_fallbacks (workload, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_fallbacks_primary
    ON local_llm_fallbacks (primary_provider, created_at DESC);

COMMENT ON TABLE local_llm_fallbacks IS
'Every LLM-routing fallback event (Phase 10, 2026-05-25). Used by ops
 dashboards + GX10 rollout health monitoring.';


CREATE TABLE IF NOT EXISTS shadow_predictions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workload            VARCHAR(64) NOT NULL,
    -- The actual provider whose response was returned to the user.
    primary_provider    VARCHAR(64) NOT NULL,
    -- The shadowed candidate (typically local-gx10 during rollout).
    shadow_provider     VARCHAR(64) NOT NULL,
    -- Snapshot of the request so we can replay + score offline.
    prompt_hash         CHAR(64),
    request_meta        JSONB,
    primary_response    TEXT,
    shadow_response     TEXT,
    primary_latency_ms  INTEGER,
    shadow_latency_ms   INTEGER,
    -- Scored offline by a judge LLM (Tier 1 eval harness).
    judge_score         DOUBLE PRECISION,
    judge_verdict       VARCHAR(16) CHECK (judge_verdict IN (
        'shadow_better', 'tie', 'primary_better', 'shadow_failed', NULL
    )),
    scored_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shadow_predictions_workload
    ON shadow_predictions (workload, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shadow_predictions_scored
    ON shadow_predictions (workload, judge_verdict)
    WHERE judge_verdict IS NOT NULL;

COMMENT ON TABLE shadow_predictions IS
'Shadow-mode comparisons between primary cloud LLM and a candidate
 local-gx10 model. Promote local → primary when judge_verdict counts
 indicate parity or better over a meaningful sample.';


-- Optional: eval_runs table for the Tier-1 prompt regression harness.
-- Each row = one full pass of the prompt eval suite against the
-- held-out article set, scored by the judge LLM.

CREATE TABLE IF NOT EXISTS prompt_eval_runs (
    run_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_name      VARCHAR(128) NOT NULL,
    prompt_version   VARCHAR(32),
    prompt_fingerprint CHAR(64),
    provider         VARCHAR(64),
    model            VARCHAR(128),
    -- Aggregate scores
    sample_size      INTEGER,
    mean_score       DOUBLE PRECISION,
    median_score     DOUBLE PRECISION,
    pass_rate        DOUBLE PRECISION,
    -- Failure analysis
    error_count      INTEGER DEFAULT 0,
    notes            TEXT,
    -- Raw per-sample (gzip-compressed JSON) for replay
    raw_results      JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_eval_runs_prompt_time
    ON prompt_eval_runs (prompt_name, created_at DESC);

COMMENT ON TABLE prompt_eval_runs IS
'Tier-1 prompt regression harness output. Tracks score regressions per
 (prompt, version, provider) so we never ship a prompt edit that drops
 quality below baseline.';
