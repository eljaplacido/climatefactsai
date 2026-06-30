-- Migration 071: register ND-GAIN vulnerability + readiness sub-scores
-- (data-completeness Fix B, 2026-06-30)
--
-- country_indicators.indicator_id has a FK to indicator_definitions. Migration
-- 020 only registered 'nd_gain_index'. The adaptation-finance-gap map layer
-- (api/map/routes_layers.py) also reads 'nd_gain_vulnerability' and
-- 'nd_gain_readiness', and the reworked ND-GAIN adapter now emits them from the
-- official archive (resources/vulnerability/vulnerability.csv +
-- resources/readiness/readiness.csv inside ndgain_countryindex_2026.zip).
-- Without these reference rows the sub-score upserts would fail the FK and be
-- dropped, so the two sub-scores must be catalogued here first.
--
-- Scales (native ND-GAIN): vulnerability and readiness are published 0-1.
--   * vulnerability: higher = MORE vulnerable = worse  -> is_higher_better FALSE
--   * readiness:     higher = MORE ready to adapt = better -> is_higher_better TRUE
--
-- Idempotent: ON CONFLICT (indicator_id) DO NOTHING.

INSERT INTO indicator_definitions
    (indicator_id, display_name, unit, category, description, is_higher_better, methodology_url)
VALUES
    ('nd_gain_vulnerability',
     'ND-GAIN Vulnerability',
     'score (0-1)',
     'adaptation',
     'Notre Dame Global Adaptation Index — vulnerability component (food, water, health, ecosystem services, human habitat, infrastructure). Higher = more vulnerable to climate disruption.',
     FALSE,
     'https://gain.nd.edu/our-work/country-index/'),
    ('nd_gain_readiness',
     'ND-GAIN Readiness',
     'score (0-1)',
     'adaptation',
     'Notre Dame Global Adaptation Index — readiness component (economic, governance, social). Higher = better positioned to leverage investment for adaptation.',
     TRUE,
     'https://gain.nd.edu/our-work/country-index/')
ON CONFLICT (indicator_id) DO NOTHING;

DO $$
DECLARE n INT;
BEGIN
    SELECT COUNT(*) INTO n FROM indicator_definitions
    WHERE indicator_id IN ('nd_gain_index', 'nd_gain_vulnerability', 'nd_gain_readiness');
    RAISE NOTICE 'migration 071: % of 3 ND-GAIN indicator definitions present', n;
END $$;
