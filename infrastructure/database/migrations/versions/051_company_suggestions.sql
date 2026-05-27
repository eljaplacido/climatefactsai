-- Migration 051: company_suggestions table (Stage 5 / M6).
--
-- User-submitted requests to add a company to the Corporate Climate
-- Tracker. The /companies feed only covers what the SBTi/CDP/NZT
-- adapters have ingested — advanced users can suggest a specific
-- company (e.g. a Finnish food company, an Indian conglomerate)
-- and the platform queues it for analyst review + data sync.
--
-- User framing: "Besides the ready made given feed, there should be
-- an option to suggest a company to be analyzed (for advanced users)
-- and ask to analyze company report ... for verifying company x's
-- climate claims".

CREATE TABLE IF NOT EXISTS company_suggestions (
    suggestion_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name    TEXT NOT NULL,
    ticker          TEXT,
    country_code    TEXT,
    website         TEXT,
    report_url      TEXT,
    reason          TEXT,
    -- Submitter — null for anonymous; otherwise links to users.user_id.
    reporter_id     UUID,
    -- Workflow status. Admins flip queued → under_review → matched/rejected.
    status          TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','under_review','matched','rejected','duplicate')),
    -- When matched, this points to the canonical company_id in `companies`.
    matched_company_id UUID,
    admin_notes     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_suggestions_status
    ON company_suggestions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_suggestions_name
    ON company_suggestions(lower(company_name));
