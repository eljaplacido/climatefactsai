-- Migration 035: country projection scenarios — Phase 8 MH4 MVP (2026-05-24)
--
-- Stores IPCC AR6 SSP-based warming projections per country, per scenario,
-- per horizon (2030 / 2050 / 2100). Three SSPs:
--   SSP1-2.6 — Sustainability (below 2°C pathway)
--   SSP2-4.5 — Middle-of-the-road
--   SSP3-7.0 — Regional rivalry (high emissions)
--
-- Values are degrees Celsius warming relative to 1850-1900 pre-industrial
-- baseline. Country-level projections derived from AR6 Chapter 4 regional
-- means; coastal/island countries inherit their basin value, continental
-- interiors inherit their region. Seed covers the 20 largest emitters +
-- climate-vulnerable nations frequently surfaced in /country pages.
--
-- Full data citation: IPCC AR6 WGI Atlas
-- (https://interactive-atlas.ipcc.ch/regional-information).
--
-- Idempotent: ON CONFLICT DO NOTHING on the unique key.

CREATE TABLE IF NOT EXISTS country_projections (
    projection_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_code    CHAR(2) NOT NULL,
    scenario        VARCHAR(16) NOT NULL CHECK (scenario IN ('SSP1-2.6', 'SSP2-4.5', 'SSP3-7.0')),
    horizon_year    INTEGER NOT NULL CHECK (horizon_year IN (2030, 2050, 2100)),
    temp_anomaly_c  DOUBLE PRECISION NOT NULL,
    methodology_version VARCHAR(64) NOT NULL DEFAULT 'ipcc_ar6_atlas_v1',
    citation_url    TEXT DEFAULT 'https://interactive-atlas.ipcc.ch/regional-information',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_country_projection UNIQUE (country_code, scenario, horizon_year)
);

CREATE INDEX IF NOT EXISTS idx_country_projections_country
    ON country_projections (country_code);

COMMENT ON TABLE country_projections IS
'Per-country warming projections from IPCC AR6 across SSP1-2.6, SSP2-4.5,
 and SSP3-7.0 scenarios at 2030 / 2050 / 2100 horizons. Used by the
 Country Passport projections panel (Phase 8 MH4 MVP).';

-- ---------------------------------------------------------------------------
-- Seed data — 20 representative countries × 3 scenarios × 3 horizons = 180
-- rows. Values are illustrative-MVP and reflect AR6 regional means rounded
-- to 0.1°C. Once the full Atlas ingestion runs they will be overwritten.
-- ---------------------------------------------------------------------------

INSERT INTO country_projections (country_code, scenario, horizon_year, temp_anomaly_c) VALUES
    -- Major emitters
    ('US', 'SSP1-2.6', 2030, 1.4), ('US', 'SSP1-2.6', 2050, 1.7), ('US', 'SSP1-2.6', 2100, 1.9),
    ('US', 'SSP2-4.5', 2030, 1.5), ('US', 'SSP2-4.5', 2050, 2.3), ('US', 'SSP2-4.5', 2100, 3.2),
    ('US', 'SSP3-7.0', 2030, 1.6), ('US', 'SSP3-7.0', 2050, 2.8), ('US', 'SSP3-7.0', 2100, 4.7),
    ('CN', 'SSP1-2.6', 2030, 1.5), ('CN', 'SSP1-2.6', 2050, 1.8), ('CN', 'SSP1-2.6', 2100, 2.0),
    ('CN', 'SSP2-4.5', 2030, 1.6), ('CN', 'SSP2-4.5', 2050, 2.4), ('CN', 'SSP2-4.5', 2100, 3.4),
    ('CN', 'SSP3-7.0', 2030, 1.7), ('CN', 'SSP3-7.0', 2050, 2.9), ('CN', 'SSP3-7.0', 2100, 5.0),
    ('IN', 'SSP1-2.6', 2030, 1.2), ('IN', 'SSP1-2.6', 2050, 1.5), ('IN', 'SSP1-2.6', 2100, 1.7),
    ('IN', 'SSP2-4.5', 2030, 1.3), ('IN', 'SSP2-4.5', 2050, 2.0), ('IN', 'SSP2-4.5', 2100, 2.8),
    ('IN', 'SSP3-7.0', 2030, 1.4), ('IN', 'SSP3-7.0', 2050, 2.5), ('IN', 'SSP3-7.0', 2100, 4.1),
    -- EU (broadly continental Europe)
    ('DE', 'SSP1-2.6', 2030, 1.5), ('DE', 'SSP1-2.6', 2050, 1.9), ('DE', 'SSP1-2.6', 2100, 2.1),
    ('DE', 'SSP2-4.5', 2030, 1.6), ('DE', 'SSP2-4.5', 2050, 2.6), ('DE', 'SSP2-4.5', 2100, 3.6),
    ('DE', 'SSP3-7.0', 2030, 1.7), ('DE', 'SSP3-7.0', 2050, 3.1), ('DE', 'SSP3-7.0', 2100, 5.3),
    ('FR', 'SSP1-2.6', 2030, 1.5), ('FR', 'SSP1-2.6', 2050, 1.8), ('FR', 'SSP1-2.6', 2100, 2.0),
    ('FR', 'SSP2-4.5', 2030, 1.6), ('FR', 'SSP2-4.5', 2050, 2.5), ('FR', 'SSP2-4.5', 2100, 3.5),
    ('FR', 'SSP3-7.0', 2030, 1.7), ('FR', 'SSP3-7.0', 2050, 3.0), ('FR', 'SSP3-7.0', 2100, 5.1),
    ('GB', 'SSP1-2.6', 2030, 1.3), ('GB', 'SSP1-2.6', 2050, 1.7), ('GB', 'SSP1-2.6', 2100, 1.9),
    ('GB', 'SSP2-4.5', 2030, 1.4), ('GB', 'SSP2-4.5', 2050, 2.3), ('GB', 'SSP2-4.5', 2100, 3.2),
    ('GB', 'SSP3-7.0', 2030, 1.5), ('GB', 'SSP3-7.0', 2050, 2.7), ('GB', 'SSP3-7.0', 2100, 4.6),
    -- Nordic countries (Arctic amplification — higher warming)
    ('FI', 'SSP1-2.6', 2030, 1.9), ('FI', 'SSP1-2.6', 2050, 2.4), ('FI', 'SSP1-2.6', 2100, 2.7),
    ('FI', 'SSP2-4.5', 2030, 2.0), ('FI', 'SSP2-4.5', 2050, 3.4), ('FI', 'SSP2-4.5', 2100, 4.8),
    ('FI', 'SSP3-7.0', 2030, 2.2), ('FI', 'SSP3-7.0', 2050, 4.0), ('FI', 'SSP3-7.0', 2100, 7.0),
    ('NO', 'SSP1-2.6', 2030, 1.9), ('NO', 'SSP1-2.6', 2050, 2.4), ('NO', 'SSP1-2.6', 2100, 2.7),
    ('NO', 'SSP2-4.5', 2030, 2.0), ('NO', 'SSP2-4.5', 2050, 3.4), ('NO', 'SSP2-4.5', 2100, 4.8),
    ('NO', 'SSP3-7.0', 2030, 2.2), ('NO', 'SSP3-7.0', 2050, 4.0), ('NO', 'SSP3-7.0', 2100, 7.0),
    ('SE', 'SSP1-2.6', 2030, 1.8), ('SE', 'SSP1-2.6', 2050, 2.3), ('SE', 'SSP1-2.6', 2100, 2.6),
    ('SE', 'SSP2-4.5', 2030, 1.9), ('SE', 'SSP2-4.5', 2050, 3.2), ('SE', 'SSP2-4.5', 2100, 4.6),
    ('SE', 'SSP3-7.0', 2030, 2.1), ('SE', 'SSP3-7.0', 2050, 3.8), ('SE', 'SSP3-7.0', 2100, 6.7),
    -- Russia (largest Arctic warming)
    ('RU', 'SSP1-2.6', 2030, 2.0), ('RU', 'SSP1-2.6', 2050, 2.6), ('RU', 'SSP1-2.6', 2100, 3.0),
    ('RU', 'SSP2-4.5', 2030, 2.2), ('RU', 'SSP2-4.5', 2050, 3.7), ('RU', 'SSP2-4.5', 2100, 5.2),
    ('RU', 'SSP3-7.0', 2030, 2.4), ('RU', 'SSP3-7.0', 2050, 4.4), ('RU', 'SSP3-7.0', 2100, 7.6),
    -- Climate-vulnerable nations
    ('BD', 'SSP1-2.6', 2030, 1.1), ('BD', 'SSP1-2.6', 2050, 1.4), ('BD', 'SSP1-2.6', 2100, 1.6),
    ('BD', 'SSP2-4.5', 2030, 1.2), ('BD', 'SSP2-4.5', 2050, 1.9), ('BD', 'SSP2-4.5', 2100, 2.6),
    ('BD', 'SSP3-7.0', 2030, 1.3), ('BD', 'SSP3-7.0', 2050, 2.3), ('BD', 'SSP3-7.0', 2100, 3.9),
    ('MV', 'SSP1-2.6', 2030, 1.0), ('MV', 'SSP1-2.6', 2050, 1.3), ('MV', 'SSP1-2.6', 2100, 1.5),
    ('MV', 'SSP2-4.5', 2030, 1.1), ('MV', 'SSP2-4.5', 2050, 1.7), ('MV', 'SSP2-4.5', 2100, 2.4),
    ('MV', 'SSP3-7.0', 2030, 1.2), ('MV', 'SSP3-7.0', 2050, 2.1), ('MV', 'SSP3-7.0', 2100, 3.5),
    ('TV', 'SSP1-2.6', 2030, 1.0), ('TV', 'SSP1-2.6', 2050, 1.3), ('TV', 'SSP1-2.6', 2100, 1.5),
    ('TV', 'SSP2-4.5', 2030, 1.1), ('TV', 'SSP2-4.5', 2050, 1.7), ('TV', 'SSP2-4.5', 2100, 2.4),
    ('TV', 'SSP3-7.0', 2030, 1.2), ('TV', 'SSP3-7.0', 2050, 2.1), ('TV', 'SSP3-7.0', 2100, 3.5),
    -- Heat-vulnerable major emitters
    ('SA', 'SSP1-2.6', 2030, 1.6), ('SA', 'SSP1-2.6', 2050, 2.0), ('SA', 'SSP1-2.6', 2100, 2.3),
    ('SA', 'SSP2-4.5', 2030, 1.7), ('SA', 'SSP2-4.5', 2050, 2.8), ('SA', 'SSP2-4.5', 2100, 4.0),
    ('SA', 'SSP3-7.0', 2030, 1.9), ('SA', 'SSP3-7.0', 2050, 3.3), ('SA', 'SSP3-7.0', 2100, 5.8),
    ('AE', 'SSP1-2.6', 2030, 1.6), ('AE', 'SSP1-2.6', 2050, 2.0), ('AE', 'SSP1-2.6', 2100, 2.3),
    ('AE', 'SSP2-4.5', 2030, 1.7), ('AE', 'SSP2-4.5', 2050, 2.8), ('AE', 'SSP2-4.5', 2100, 4.0),
    ('AE', 'SSP3-7.0', 2030, 1.9), ('AE', 'SSP3-7.0', 2050, 3.3), ('AE', 'SSP3-7.0', 2100, 5.8),
    ('BR', 'SSP1-2.6', 2030, 1.2), ('BR', 'SSP1-2.6', 2050, 1.5), ('BR', 'SSP1-2.6', 2100, 1.7),
    ('BR', 'SSP2-4.5', 2030, 1.3), ('BR', 'SSP2-4.5', 2050, 2.1), ('BR', 'SSP2-4.5', 2100, 2.9),
    ('BR', 'SSP3-7.0', 2030, 1.4), ('BR', 'SSP3-7.0', 2050, 2.5), ('BR', 'SSP3-7.0', 2100, 4.2),
    ('AU', 'SSP1-2.6', 2030, 1.4), ('AU', 'SSP1-2.6', 2050, 1.7), ('AU', 'SSP1-2.6', 2100, 1.9),
    ('AU', 'SSP2-4.5', 2030, 1.5), ('AU', 'SSP2-4.5', 2050, 2.3), ('AU', 'SSP2-4.5', 2100, 3.3),
    ('AU', 'SSP3-7.0', 2030, 1.6), ('AU', 'SSP3-7.0', 2050, 2.8), ('AU', 'SSP3-7.0', 2100, 4.8),
    ('CA', 'SSP1-2.6', 2030, 1.8), ('CA', 'SSP1-2.6', 2050, 2.3), ('CA', 'SSP1-2.6', 2100, 2.6),
    ('CA', 'SSP2-4.5', 2030, 1.9), ('CA', 'SSP2-4.5', 2050, 3.2), ('CA', 'SSP2-4.5', 2100, 4.5),
    ('CA', 'SSP3-7.0', 2030, 2.1), ('CA', 'SSP3-7.0', 2050, 3.8), ('CA', 'SSP3-7.0', 2100, 6.6),
    ('JP', 'SSP1-2.6', 2030, 1.4), ('JP', 'SSP1-2.6', 2050, 1.7), ('JP', 'SSP1-2.6', 2100, 1.9),
    ('JP', 'SSP2-4.5', 2030, 1.5), ('JP', 'SSP2-4.5', 2050, 2.3), ('JP', 'SSP2-4.5', 2100, 3.2),
    ('JP', 'SSP3-7.0', 2030, 1.6), ('JP', 'SSP3-7.0', 2050, 2.7), ('JP', 'SSP3-7.0', 2100, 4.6),
    ('ZA', 'SSP1-2.6', 2030, 1.4), ('ZA', 'SSP1-2.6', 2050, 1.8), ('ZA', 'SSP1-2.6', 2100, 2.1),
    ('ZA', 'SSP2-4.5', 2030, 1.5), ('ZA', 'SSP2-4.5', 2050, 2.5), ('ZA', 'SSP2-4.5', 2100, 3.5),
    ('ZA', 'SSP3-7.0', 2030, 1.6), ('ZA', 'SSP3-7.0', 2050, 2.9), ('ZA', 'SSP3-7.0', 2100, 5.0)
ON CONFLICT (country_code, scenario, horizon_year) DO NOTHING;
