-- Migration 053: ingestion bias rebalance (2026-05-27, audit slice 4)
--
-- Master-prompt audit caught a real corpus-skew: the 14k-article corpus
-- was 23% Slovenian (24ur Okolje SI: 463 articles), 13% Bulgarian
-- (Capital BG + Dnevnik BG: 287), 8% Romanian (Digi24 RO: 166) — while
-- Carbon Brief had 32, NYT Climate 20, BBC Climate 33. The 24ur / Capital
-- / Digi24 / Dnevnik feeds use the *general* RSS endpoint of those
-- outlets, not a climate-section feed, so they flood with everything
-- from politics to crime, then mis-classify as climate_science at
-- ingest.
--
-- Two-part rebalance:
--   1. Deactivate the 4 general-RSS over-fetchers. Their articles ARE
--      flagged as off-topic by the title-keyword gate when the golden
--      pipeline daemon picks them, but at ingest they bypass the gate
--      and pollute the corpus. Setting is_active=false stops new
--      ingestion; existing articles stay so the daemon can keep
--      training the off-topic classifier on them.
--   2. Add ~12 high-priority feeds for the under-represented major
--      markets the user flagged (US/UK/FR/DE big climate desks,
--      Brazil, India, South Africa, Mexico).
--
-- Idempotent on the (feed_name) unique constraint.

-- ---------------------------------------------------------------------------
-- Step 1: deactivate the 4 general-RSS chatty feeds
-- ---------------------------------------------------------------------------
UPDATE rss_feed_registry
   SET is_active = false
 WHERE feed_name IN (
   '24ur Okolje (SI)',
   'Capital BG (BG)',
   'Digi24 (RO)',
   'Dnevnik BG (BG)'
 );

-- ---------------------------------------------------------------------------
-- Step 2: add T1 climate-section feeds for major under-represented markets
-- ---------------------------------------------------------------------------
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    -- US — beyond Grist / Inside Climate News which we already have
    ('Yale Climate Connections feed', 'https://yaleclimateconnections.org/feed/', 'yaleclimateconnections.org', 'US', 'north_america', 'research'),
    ('Mother Jones Environment',     'https://www.motherjones.com/topics/environment/feed/', 'motherjones.com', 'US', 'north_america', 'public'),
    ('Rocky Mountain Institute feed', 'https://rmi.org/feed/',                                 'rmi.org',                  'US', 'north_america', 'research'),
    -- UK — Carbon Brief + Guardian additions
    ('Guardian Environment feed',    'https://www.theguardian.com/environment/rss', 'theguardian.com', 'GB', 'europe', 'public'),
    -- France
    ('Reporterre feed',              'https://reporterre.net/spip.php?page=backend', 'reporterre.net', 'FR', 'europe', 'public'),
    -- Germany
    ('Clean Energy Wire feed',       'https://www.cleanenergywire.org/rss-feed.xml', 'cleanenergywire.org', 'DE', 'europe', 'public'),
    -- Brazil — InfoAmazonia + Folha + Observatorio
    ('InfoAmazonia feed',            'https://infoamazonia.org/feed/',                'infoamazonia.org',         'BR', 'south_america', 'research'),
    ('Observatorio do Clima',        'https://www.oc.eco.br/feed/',                    'oc.eco.br',                'BR', 'south_america', 'public'),
    -- India — Mongabay India + The Wire Science
    ('Mongabay India climate feed',  'https://india.mongabay.com/feed/',              'india.mongabay.com',       'IN', 'asia',          'research'),
    ('Wire Science India climate',   'https://science.thewire.in/feed/',              'science.thewire.in',       'IN', 'asia',          'public'),
    -- South Africa
    ('Daily Maverick Environment',   'https://www.dailymaverick.co.za/section/our-burning-planet/feed/', 'dailymaverick.co.za', 'ZA', 'africa', 'public'),
    -- Mexico — Latin America regional
    ('Diálogo Chino feed',           'https://dialogochino.net/en/feed/',             'dialogochino.net',         'XX', 'south_america', 'research')
ON CONFLICT (feed_name) DO NOTHING;

-- Sanity log so deploy ops see the rebalance landed
DO $$
DECLARE
    active_count INT;
    deactivated_count INT;
BEGIN
    SELECT COUNT(*) INTO active_count FROM rss_feed_registry WHERE is_active = true;
    SELECT COUNT(*) INTO deactivated_count FROM rss_feed_registry WHERE is_active = false;
    RAISE NOTICE 'migration 053: rss_feed_registry now has % active feeds, % deactivated', active_count, deactivated_count;
END $$;
