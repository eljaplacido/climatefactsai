-- =============================================================================
-- 020_country_indicators.sql — Real climate indicators with source provenance
-- =============================================================================
-- Phase 3 foundation: replaces the "article count → 0–10 score" coverage_index
-- (audit finding T1) with a proper indicator store sourced from primary
-- datasets — Climate TRACE (sector emissions, satellite-verified), Our World
-- in Data (canonical CSVs), Climate Action Tracker (sovereign policy
-- ratings), World Bank CCKP (adaptation/exposure), UNFCCC NDC Registry
-- (pledges + LT-LEDS targets), IRENA (renewable capacity).
--
-- Design notes:
--
-- 1. `indicator_definitions` is the small reference table (one row per
--    indicator the platform exposes). It carries the user-facing label,
--    unit, category, and a methodology URL — every score the platform
--    surfaces can be traced back to a published methodology.
--
-- 2. `country_indicators` is the wide fact table: one row per
--    (country, indicator, year, source). Multiple sources for the same
--    indicator (e.g. OWID emissions vs Climate TRACE emissions) coexist;
--    the application layer picks or blends. Uncertainty bands are
--    first-class so downstream scores can propagate confidence.
--
-- 3. `raw_record` JSONB keeps the original parsed record so we can
--    re-derive values if the methodology changes or audit a number's
--    lineage years later. This is the Traceability axis of the audit's
--    truth-machine grade.
--
-- 4. `methodology_version` lets a source migrate its methodology without
--    invalidating older values — the application can render the score
--    next to the methodology version it was computed under.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Indicator catalogue
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_definitions (
    indicator_id    VARCHAR(64) PRIMARY KEY,
    display_name    TEXT        NOT NULL,
    unit            TEXT,
    category        VARCHAR(32) NOT NULL,   -- 'emissions' | 'energy' | 'policy' | 'adaptation' | 'biodiversity' | 'finance'
    description     TEXT,
    is_higher_better BOOLEAN    NOT NULL DEFAULT TRUE,
    methodology_url TEXT,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_indicator_category CHECK (
        category IN ('emissions', 'energy', 'policy', 'adaptation', 'biodiversity', 'finance')
    )
);

COMMENT ON TABLE indicator_definitions IS
    'Reference catalogue of indicators the platform surfaces. Each row '
    'pins user-facing label, unit, and methodology URL so every displayed '
    'score traces back to a public methodology.';

-- -----------------------------------------------------------------------------
-- Per-country indicator values
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS country_indicators (
    id                  BIGSERIAL PRIMARY KEY,
    country_code        CHAR(2)        NOT NULL,
    indicator_id        VARCHAR(64)    NOT NULL REFERENCES indicator_definitions(indicator_id) ON DELETE CASCADE,
    year                INTEGER        NOT NULL,
    value               DOUBLE PRECISION,
    uncertainty_low     DOUBLE PRECISION,
    uncertainty_high    DOUBLE PRECISION,
    source_name         VARCHAR(64)    NOT NULL,    -- 'climate_trace' | 'owid' | 'cat' | 'wb_cckp' | 'unfccc_ndc' | 'irena'
    source_url          TEXT,
    fetched_at          TIMESTAMP      NOT NULL DEFAULT NOW(),
    methodology_version VARCHAR(32),
    raw_record          JSONB,                       -- the original record we parsed
    CONSTRAINT uq_country_indicators_natural
        UNIQUE (country_code, indicator_id, year, source_name)
);

CREATE INDEX IF NOT EXISTS idx_country_indicators_cc_ind
    ON country_indicators(country_code, indicator_id);
CREATE INDEX IF NOT EXISTS idx_country_indicators_year
    ON country_indicators(year);
CREATE INDEX IF NOT EXISTS idx_country_indicators_source
    ON country_indicators(source_name);
CREATE INDEX IF NOT EXISTS idx_country_indicators_fetched_at
    ON country_indicators(fetched_at DESC);

COMMENT ON TABLE country_indicators IS
    'Wide fact table — one row per (country, indicator, year, source). '
    'Multiple sources for the same indicator coexist so the application '
    'layer can blend or pick; uncertainty bands propagate to downstream '
    'scores; raw_record retains lineage for audits.';

-- -----------------------------------------------------------------------------
-- Seed the indicator catalogue with the core set used by Phase 3 scoring
-- -----------------------------------------------------------------------------
INSERT INTO indicator_definitions (indicator_id, display_name, unit, category, description, is_higher_better, methodology_url) VALUES
    -- Emissions (lower is better)
    ('emissions_tco2e_total',
     'Total GHG emissions (CO₂-equivalent, 100-yr GWP)',
     'tCO2e',
     'emissions',
     'Aggregate greenhouse-gas emissions across all sectors for a country-year, expressed in CO₂-equivalent tonnes using 100-year global warming potentials. Sourced from Climate TRACE (satellite-verified) where available, fallback to OWID / Global Carbon Project.',
     FALSE,
     'https://climatetrace.org/methodology'),
    ('emissions_tco2e_per_capita',
     'Per-capita GHG emissions',
     'tCO2e/person',
     'emissions',
     'Country-year GHG emissions divided by population. From Our World in Data.',
     FALSE,
     'https://ourworldindata.org/co2-and-greenhouse-gas-emissions'),
    ('emissions_tco2_power',
     'Power-sector CO₂ emissions',
     'tCO2',
     'emissions',
     'Electricity-generation CO₂ emissions per Climate TRACE sector breakdown.',
     FALSE,
     'https://climatetrace.org/methodology'),
    ('emissions_tco2_transportation',
     'Transportation-sector CO₂ emissions',
     'tCO2',
     'emissions',
     'Aggregate road / aviation / shipping CO₂ per Climate TRACE.',
     FALSE,
     'https://climatetrace.org/methodology'),

    -- Energy (mixed direction; per-indicator is_higher_better)
    ('renewable_capacity_mw',
     'Installed renewable energy capacity',
     'MW',
     'energy',
     'Total installed renewable electricity capacity (solar + wind + hydro + geothermal + bioenergy). From IRENA.',
     TRUE,
     'https://www.irena.org/Statistics'),
    ('renewable_share_electricity_percent',
     'Share of electricity from renewables',
     '%',
     'energy',
     'Renewable electricity as a share of total electricity generation. From Our World in Data / Ember.',
     TRUE,
     'https://ourworldindata.org/renewable-energy'),

    -- Policy (higher is better; CAT ratings normalised to 0–100)
    ('cat_overall_rating',
     'Climate Action Tracker overall rating',
     'score (0–100)',
     'policy',
     'Composite policy-ambition score from Climate Action Tracker, normalised 0–100 where 100 = aligned with 1.5°C. Sources: CAT country pages.',
     TRUE,
     'https://climateactiontracker.org/methodology/'),
    ('ndc_target_year',
     'NDC target year',
     'year',
     'policy',
     'Year by which the country has pledged to meet its NDC. From UNFCCC NDC Registry.',
     TRUE,
     'https://unfccc.int/NDCREG'),
    ('ndc_target_reduction_percent',
     'NDC reduction target',
     '%',
     'policy',
     'Pledged emissions reduction (vs base year) in the country''s NDC. From UNFCCC NDC Registry.',
     TRUE,
     'https://unfccc.int/NDCREG'),

    -- Adaptation
    ('nd_gain_index',
     'ND-GAIN Country Index',
     'index (0–100)',
     'adaptation',
     'Notre Dame Global Adaptation Index — combines vulnerability + readiness. Higher = better-positioned to adapt.',
     TRUE,
     'https://gain.nd.edu/our-work/country-index/')
ON CONFLICT (indicator_id) DO NOTHING;

-- Note on `is_higher_better`: this column lives on `indicator_definitions`,
-- not `country_indicators`. Scoring code joins indicator_definitions to
-- know whether higher or lower is better per indicator. (Removed an
-- earlier `COMMENT ON COLUMN country_indicators.is_higher_better` that
-- referenced a non-existent column.)
