-- Migration 063: LLM cost telemetry (audit seq-8, 2026-06-04)
--
-- LLM spend is currently invisible: there was no cost table and no /cost
-- endpoint, so an Anthropic deep-search runaway (or, conversely, the savings
-- from moving enrichment/embeddings to the free GX10) could not be seen. This
-- table records one row per successful provider call from llm_chat_with_fallback
-- with token counts + an estimated USD cost, so /api/admin/llm/cost can show the
-- cloud-vs-GX10(free) split over a window.
--
-- Idempotent.

CREATE TABLE IF NOT EXISTS llm_cost_log (
    id                BIGSERIAL PRIMARY KEY,
    provider          VARCHAR(32)  NOT NULL,   -- deepseek | openai | anthropic | local-gx10
    model             VARCHAR(128),
    purpose           VARCHAR(64),             -- llm_chat | enrichment | deep_search | ...
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    est_cost_usd      NUMERIC(12, 6) DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_cost_log_created ON llm_cost_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_cost_log_provider ON llm_cost_log (provider, created_at DESC);

DO $$
BEGIN
    RAISE NOTICE 'migration 063: llm_cost_log ready';
END $$;
