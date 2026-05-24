-- Migration 034: corporate seed data — Phase 7 B3 (2026-05-24)
--
-- Seeds ~15 public companies across sectors with their publicly-known
-- SBTi/CDP/Net Zero Tracker status as of Q1 2026, so the /companies
-- listing isn't empty out of the box and the business-decision-maker
-- persona has something to compare on day one.
--
-- All facts here are public:
--   - SBTi validation status: sciencebasedtargets.org/companies-taking-action
--   - Net-zero target years: zerotracker.net + company public statements
--   - Scope figures: most recent CDP or company sustainability report
--
-- The seed is illustrative — once the CDP/SBTi/NZT ingestion adapters
-- run, they will idempotently overwrite these rows with fresher data.
--
-- Idempotent: every insert uses ON CONFLICT DO NOTHING / DO UPDATE,
-- safe to re-run.


-- ---------------------------------------------------------------------------
-- Tech / consumer (mostly SBTi-validated, climate-leader cohort)
-- ---------------------------------------------------------------------------

INSERT INTO companies (company_id, ticker, name, country_code, sector_nace)
VALUES
    (uuid_generate_v4(), 'MSFT',  'Microsoft Corporation', 'US', '62.01'),
    (uuid_generate_v4(), 'AAPL',  'Apple Inc.',            'US', '26.20'),
    (uuid_generate_v4(), 'GOOGL', 'Alphabet Inc.',         'US', '63.11'),
    (uuid_generate_v4(), 'AMZN',  'Amazon.com Inc.',       'US', '47.91'),
    (uuid_generate_v4(), 'META',  'Meta Platforms Inc.',   'US', '63.12')
ON CONFLICT (ticker) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Consumer goods / retail (mixed validation)
-- ---------------------------------------------------------------------------

INSERT INTO companies (company_id, ticker, name, country_code, sector_nace)
VALUES
    (uuid_generate_v4(), 'NESN',  'Nestle S.A.',           'CH', '10.86'),
    (uuid_generate_v4(), 'UL',    'Unilever PLC',          'GB', '20.41'),
    (uuid_generate_v4(), 'WMT',   'Walmart Inc.',          'US', '47.11')
ON CONFLICT (ticker) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Industrials (mixed validation)
-- ---------------------------------------------------------------------------

INSERT INTO companies (company_id, ticker, name, country_code, sector_nace)
VALUES
    (uuid_generate_v4(), 'MAERSK-B', 'A.P. Moller-Maersk',  'DK', '50.20'),
    (uuid_generate_v4(), 'VOW3',     'Volkswagen AG',       'DE', '29.10'),
    (uuid_generate_v4(), 'TM',       'Toyota Motor Corp.',  'JP', '29.10'),
    (uuid_generate_v4(), 'TSLA',     'Tesla Inc.',          'US', '29.10')
ON CONFLICT (ticker) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Oil & gas / mining (largely SBTi-unvalidated; high-scrutiny cohort)
-- ---------------------------------------------------------------------------

INSERT INTO companies (company_id, ticker, name, country_code, sector_nace)
VALUES
    (uuid_generate_v4(), 'XOM',   'ExxonMobil Corporation', 'US', '06.10'),
    (uuid_generate_v4(), 'SHEL',  'Shell plc',              'GB', '06.10'),
    (uuid_generate_v4(), 'BP',    'BP p.l.c.',              'GB', '06.10'),
    (uuid_generate_v4(), 'GLEN',  'Glencore plc',           'CH', '07.29')
ON CONFLICT (ticker) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Disclosure rows — most recent reporting year per source.
--
-- Status as of Q1 2026 (publicly verifiable):
--   * Microsoft, Apple: SBTi-validated, net-zero 2030
--   * Unilever, Maersk: SBTi-validated, net-zero 2039/2040
--   * Walmart, Nestle, VW, Toyota: SBTi-validated, longer-horizon targets
--   * Amazon, Tesla: Climate-Pledge style commitments, not SBTi-validated
--   * Exxon, Shell, BP, Glencore: net-zero ambitions but NOT SBTi-validated
-- ---------------------------------------------------------------------------

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 144000, 0,  16300000, TRUE, TRUE, 2030, 2020, 50,  2030, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'MSFT'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 55400, 0, 14800000, TRUE, TRUE, 2030, 2015, 75, 2030, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'AAPL'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 76000, 5800, 11800000, TRUE, TRUE, 2030, 2019, 50, 2030, 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'GOOGL'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 17150000, 4800000, 49300000, TRUE, FALSE, 2040, 2019, NULL, 2040, 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'AMZN'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 11500, 0, 7900000, TRUE, FALSE, NULL, 2020, NULL, NULL, 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'META'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 2500000, 750000, 92000000, TRUE, TRUE, 2030, 2018, 50, 2050, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'NESN'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 240000, 580000, 60000000, TRUE, TRUE, 2030, 2015, 100, 2039, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'UL'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 8500000, 4400000, 165000000, TRUE, TRUE, 2030, 2015, 35, 2040, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'WMT'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 32500000, 350000, 5200000, TRUE, TRUE, 2030, 2020, 50, 2040, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'MAERSK-B'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 6800000, 2900000, 380000000, TRUE, TRUE, 2030, 2018, 30, 2050, 'reasonable', 'CDP-2024'
FROM companies c WHERE c.ticker = 'VOW3'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 4900000, 1700000, 545000000, TRUE, TRUE, 2035, 2019, 33, 2050, 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'TM'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 90000, 0, 32000000, FALSE, FALSE, NULL, NULL, NULL, 2050, NULL, 'CDP-2024'
FROM companies c WHERE c.ticker = 'TSLA'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year,
    offset_based_claims, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 109000000, 2700000, 580000000, TRUE, FALSE, NULL, 2016, NULL, 2050,
       'Significant reliance on offsets and CCS for residual emissions', 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'XOM'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year,
    offset_based_claims, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 53000000, 2100000, 1170000000, TRUE, FALSE, 2030, 2016, 50, 2050,
       'Net Carbon Intensity target relies partly on offsets', 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'SHEL'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year,
    offset_based_claims, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 32000000, 1900000, 320000000, TRUE, FALSE, 2030, 2019, 20, 2050,
       'Targets rolled back 2023; offsets remain part of pathway', 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'BP'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

INSERT INTO company_climate_disclosures (
    company_id, source, reporting_year, scope1_tco2e, scope2_tco2e_market,
    scope3_tco2e, scope1_2_verified, sbti_validated, target_year, baseline_year,
    target_pct_reduction, net_zero_target_year,
    offset_based_claims, assurance_level, methodology_version
)
SELECT c.company_id, 'cdp', 2024, 23800000, 1300000, 367000000, TRUE, FALSE, 2035, 2019, 50, 2050,
       'Coal phase-out path includes offset purchases', 'limited', 'CDP-2024'
FROM companies c WHERE c.ticker = 'GLEN'
ON CONFLICT (company_id, source, reporting_year) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Verify count for operator visibility
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    n_companies INTEGER;
    n_disclosures INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_companies FROM companies;
    SELECT COUNT(*) INTO n_disclosures FROM company_climate_disclosures;
    RAISE NOTICE 'Migration 034 complete: % companies, % disclosures',
        n_companies, n_disclosures;
END
$$;
