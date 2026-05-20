-- Migration 029: corporate climate disclosure data layer
--
-- Adds companies + disclosures + claims so the platform can verify
-- corporate climate claims (net-zero targets, scope coverage, offset-based
-- "climate neutral" labels) against public regulatory datasets.
--
-- Positioned for ECGT enforcement (27 Sep 2026) and CSRD/IFRS S2 alignment.
-- All three seed datasets (CDP open, SBTi commitments, Net Zero Tracker)
-- are public and free — no third-party API contracts needed.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS companies (
    company_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker          VARCHAR(16) UNIQUE,
    name            VARCHAR(255) NOT NULL,
    country_code    CHAR(2),
    sector_nace     VARCHAR(8),
    isin            VARCHAR(12) UNIQUE,
    lei             VARCHAR(20) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_companies_country
    ON companies (country_code);

CREATE TABLE IF NOT EXISTS company_climate_disclosures (
    disclosure_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    source              VARCHAR(64) NOT NULL CHECK (source IN ('cdp', 'sbti', 'net_zero_tracker')),
    reporting_year      INTEGER NOT NULL,
    scope1_tco2e        DOUBLE PRECISION,
    scope2_tco2e_market DOUBLE PRECISION,
    scope2_tco2e_location DOUBLE PRECISION,
    scope3_tco2e        DOUBLE PRECISION,
    scope1_2_verified   BOOLEAN DEFAULT FALSE,
    sbti_validated      BOOLEAN DEFAULT FALSE,
    target_year         INTEGER,
    baseline_year       INTEGER,
    target_pct_reduction DOUBLE PRECISION,
    net_zero_target_year INTEGER,
    offset_based_claims TEXT,
    assurance_level     VARCHAR(32),
    assurance_provider  VARCHAR(255),
    methodology_version  VARCHAR(64),
    raw_record          JSONB,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_disclosure UNIQUE (company_id, source, reporting_year)
);

CREATE INDEX IF NOT EXISTS idx_disclosures_company_source
    ON company_climate_disclosures (company_id, source);

CREATE INDEX IF NOT EXISTS idx_disclosures_sbti_validated
    ON company_climate_disclosures (sbti_validated)
    WHERE sbti_validated = TRUE;

CREATE TABLE IF NOT EXISTS company_claims (
    claim_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    claim_text          TEXT NOT NULL,
    claim_type          VARCHAR(32) CHECK (claim_type IN (
        'net_zero_target', 'carbon_neutral_product', 'emissions_reduction',
        'renewable_energy', 'scope_coverage', 'offset_claim',
        'sustainability_label', 'other'
    )),
    verdict             VARCHAR(20) CHECK (verdict IN (
        'verified', 'partially_true', 'disputed', 'unverified', 'flagged'
    )),
    evidence_url        TEXT,
    flag_reason         TEXT,
    methodology_version  VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_claims_company
    ON company_claims (company_id, claim_type);

COMMENT ON TABLE companies IS
'Corporations tracked by the platform for climate-claim verification.
 Seeded from CDP open data, SBTi commitments, and Net Zero Tracker.';

COMMENT ON TABLE company_climate_disclosures IS
'Annual climate disclosures per company per reporting year.
 Scope 1/2/3 emissions, SBTi validation status, net-zero target year,
 assurance level. Sources: CDP, SBTi, NZT.';

COMMENT ON TABLE company_claims IS
'Verified corporate climate claims. Claim types include net-zero targets,
 carbon-neutral product labels, emissions reduction claims, and offset-based
 marketing. Verdicts are machine-generated from disclosure data + LLM
 analysis; flagged claims carry a reason for audit.';
