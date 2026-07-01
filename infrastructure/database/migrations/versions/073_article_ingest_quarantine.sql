-- Migration 073: article_ingest_quarantine — auditable sink for rejected
--                ingest inputs (ML-03, 2026-07-01, launch blocker).
--
-- The ML-03 ingestion quality gate
-- (app/domains/content/ingest_quality_gate.py) rejects consent-wall /
-- interstitial / thin bodies and unresolved redirector URLs BEFORE a row is
-- inserted — so no LLM enrichment / embedding / claim-verification spend is
-- wasted on Google cookie-consent walls. Rejected inputs are written here
-- instead of being silently dropped, so every drop is reviewable and the set
-- becomes a labeled corpus for tuning the gate.
--
-- Split from the backfill (mig 074) ON PURPOSE: this file only CREATEs a NEW
-- table (bulletproof — IF NOT EXISTS can never fail), so the gate can start
-- quarantining even if the one-shot backfill errors and rolls back. See
-- run_migrations.py: each file is its own transaction.
--
-- Idempotent: IF NOT EXISTS on the table and every index.

CREATE TABLE IF NOT EXISTS article_ingest_quarantine (
    quarantine_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url            TEXT,
    title          TEXT,
    source_name    VARCHAR(255),
    body_md5       CHAR(32),
    reason         TEXT NOT NULL,
    category       VARCHAR(40) NOT NULL,   -- consent_wall|boilerplate_md5|thin_body|missing_title|redirector_url
    raw_input      JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE article_ingest_quarantine IS
    'ML-03 (mig 073): inputs rejected by the ingestion quality gate before '
    'insert/enrichment/embedding/claims. Audit trail + gate-tuning corpus.';

CREATE INDEX IF NOT EXISTS idx_aiq_category    ON article_ingest_quarantine(category);
CREATE INDEX IF NOT EXISTS idx_aiq_created_at  ON article_ingest_quarantine(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aiq_body_md5    ON article_ingest_quarantine(body_md5);

DO $$
DECLARE n INT;
BEGIN
    SELECT COUNT(*) INTO n FROM article_ingest_quarantine;
    RAISE NOTICE 'migration 073: article_ingest_quarantine ready (% existing rows)', n;
END $$;
