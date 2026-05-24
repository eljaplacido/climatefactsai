-- Migration 031: structured failure classification for url_analyses
--
-- Adds failure_reason (enum-shaped VARCHAR) and failure_detail (JSONB)
-- columns so the Analyze URL flow can surface *why* an analysis failed
-- (paywall / robots-blocked / JS-rendered SPA / non-text content / timeout
-- / network error / etc.) instead of the opaque "Analysis failed" string
-- the frontend has been showing.
--
-- The frontend then renders a structured failure block with an icon,
-- explanation, and a remediation hint per reason.
--
-- Backward-compat: legacy `error_message` is preserved unchanged; the new
-- columns are additive. Old rows just have NULLs here.
-- Idempotent: safe to re-run.

ALTER TABLE url_analyses
    ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(64),
    ADD COLUMN IF NOT EXISTS failure_detail JSONB;

CREATE INDEX IF NOT EXISTS idx_url_analyses_failure_reason
    ON url_analyses (failure_reason)
    WHERE failure_reason IS NOT NULL;

COMMENT ON COLUMN url_analyses.failure_reason IS
    'Structured failure classification. One of: http_forbidden, http_not_found, '
    'http_legal_block, http_4xx_other, http_5xx, timeout, response_too_large, '
    'extraction_too_short, paywall_suspected, js_rendered_spa, redirect_blocked, '
    'network_error, validation_failed, claim_extraction_failed, unknown. '
    'NULL on success or for legacy rows predating migration 031.';

COMMENT ON COLUMN url_analyses.failure_detail IS
    'JSONB metadata attached to a structured failure. Shape varies by failure_reason '
    'but always includes {"reason": <same as column>, "message": <human-readable>, '
    '"remediation": <hint>, optional fields like "status_code", "content_length", '
    '"detected_keywords"}.';
