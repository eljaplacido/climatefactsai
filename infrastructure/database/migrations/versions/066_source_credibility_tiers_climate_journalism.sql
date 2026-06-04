-- Migration 066: source credibility tier expansion — climate journalism
-- (authored 2026-05-27; renamed 049 -> 066 on 2026-06-04 to break a duplicate
-- version-prefix collision with 049_knowledge_graph_canonical.sql. The tracker
-- keys on the NNN prefix, so this file's INSERTs were silently skipped — they
-- finally run now. Idempotent, see ON CONFLICT below.)
--
-- Stage-1 B3 finding: 458 of 464 articles processed by the golden pipeline
-- daemon showed source_credibility_score = 50 (unknown default) because the
-- ingested sources weren't in source_credibility_tiers. T1/T2/T3 allowlist
-- in scripts/golden_pipeline_daemon.py was scoring them at SELECTION but
-- the DB-level tier table the source_tier_service queries had no matches.
--
-- This migration seeds the climate-journalism outlets actually present in
-- the cloud corpus today, with conservative tier assignments based on the
-- migration 027/033 rubric:
--
--   T1 = +30 (canonical climate journalism with editorial standards,
--             corrections policy, dedicated climate desk)
--   T2 = +15 (regional or specialist outlets with editorial track record,
--             national mainstream papers with climate coverage)
--   T3 = +5  (regional/national mainstream where the climate beat exists
--             but isn't the editorial focus)
--
-- Idempotent via ON CONFLICT DO NOTHING — safe to re-run.

INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    -- T1 — global climate journalism gold standard
    ('Carbon Brief',                'carbonbrief.org',          NULL, 'T1', 30, 'https://www.carbonbrief.org/about-us/',                                        'specialist_climate_press'),
    ('Climate Change News',         'climatechangenews.com',    NULL, 'T1', 30, 'https://www.climatechangenews.com/about-us/',                                  'specialist_climate_press'),
    ('Climate Home News',           'climatechangenews.com',    NULL, 'T1', 30, 'https://www.climatechangenews.com/about-us/',                                  'specialist_climate_press'),
    ('Yale Climate Connections',    'yaleclimateconnections.org', NULL, 'T1', 30, 'https://yaleclimateconnections.org/about/',                                  'specialist_climate_press'),
    ('Inside Climate News',         'insideclimatenews.org',    NULL, 'T1', 30, 'https://insideclimatenews.org/about/',                                         'specialist_climate_press'),
    ('Grist',                       'grist.org',                NULL, 'T1', 30, 'https://grist.org/about/',                                                     'specialist_climate_press'),
    ('Climate Central',             'climatecentral.org',       NULL, 'T1', 30, 'https://www.climatecentral.org/who-we-are',                                    'specialist_climate_org'),
    ('Earth.org',                   'earth.org',                NULL, 'T1', 30, 'https://earth.org/about/',                                                     'specialist_climate_press'),

    -- T1 — major outlets with dedicated climate desks
    ('NYT Climate',                 'nytimes.com',              NULL, 'T1', 30, 'https://www.nytimes.com/spotlight/climate-and-environment',                    'newspaper_climate_desk'),
    ('The Guardian Climate',        'theguardian.com',          NULL, 'T1', 30, 'https://www.theguardian.com/environment/climate-crisis',                       'newspaper_climate_desk'),
    ('Guardian Environment',        'theguardian.com',          NULL, 'T1', 30, 'https://www.theguardian.com/environment',                                      'newspaper_climate_desk'),
    ('Reuters Climate',             'reuters.com',              NULL, 'T1', 30, 'https://www.reuters.com/business/environment/',                                'newspaper_climate_desk'),
    ('BBC Climate (GB)',            'bbc.co.uk',                NULL, 'T1', 30, 'https://www.bbc.co.uk/news/science_and_environment',                           'broadcaster_climate_desk'),
    ('BBC News',                    'bbc.com',                  NULL, 'T1', 30, 'https://www.bbc.com/news/science_and_environment',                             'broadcaster_climate_desk'),
    ('Bloomberg Green',             'bloomberg.com',            NULL, 'T1', 30, 'https://www.bloomberg.com/green',                                              'newspaper_climate_desk'),
    ('Le Monde Planete (FR)',       'lemonde.fr',               NULL, 'T1', 30, 'https://www.lemonde.fr/planete/',                                              'newspaper_climate_desk'),
    ('El Pais Clima (ES)',          'elpais.com',               NULL, 'T1', 30, 'https://elpais.com/clima-y-medio-ambiente/',                                   'newspaper_climate_desk'),
    ('DW Climate',                  'dw.com',                   NULL, 'T1', 30, 'https://www.dw.com/en/environment/',                                           'broadcaster_climate_desk'),

    -- T1 — institutional / NGO with rigorous sourcing
    ('Rocky Mountain Institute',    'rmi.org',                  NULL, 'T1', 30, 'https://rmi.org/about/',                                                       'specialist_climate_org'),
    ('Union of Concerned Scientists', 'ucsusa.org',             NULL, 'T1', 30, 'https://www.ucsusa.org/about',                                                 'science_advocacy_org'),
    ('Climate Policy Initiative',   'climatepolicyinitiative.org', NULL, 'T1', 30, 'https://www.climatepolicyinitiative.org/about/',                            'climate_finance_research'),
    ('Energy Transitions Commission', 'energy-transitions.org', NULL, 'T1', 30, 'https://www.energy-transitions.org/about-us/',                                 'specialist_climate_org'),
    ('International Energy Agency', 'iea.org',                  NULL, 'T1', 30, 'https://www.iea.org/about',                                                    'intergovernmental_agency'),
    ('IPCC',                        'ipcc.ch',                  NULL, 'T1', 30, 'https://www.ipcc.ch/about/',                                                   'un_specialised_body'),
    ('UNFCCC',                      'unfccc.int',               NULL, 'T1', 30, 'https://unfccc.int/about-us',                                                  'un_treaty_body'),
    ('World Resources Institute',   'wri.org',                  NULL, 'T1', 30, 'https://www.wri.org/about',                                                    'specialist_climate_org'),
    ('Our World in Data',           'ourworldindata.org',       NULL, 'T1', 30, 'https://ourworldindata.org/about',                                             'data_research_org'),
    ('Climate Action Tracker',      'climateactiontracker.org', NULL, 'T1', 30, 'https://climateactiontracker.org/about/',                                      'climate_policy_tracker'),
    ('Climate TRACE',               'climatetrace.org',         NULL, 'T1', 30, 'https://climatetrace.org/about',                                               'emissions_data_org'),

    -- T2 — regional climate-focused press
    ('Climatica La Marea (ES)',     'climatica.lamarea.com',    NULL, 'T2', 15, 'https://climatica.lamarea.com/quienes-somos/',                                 'specialist_climate_press'),
    ('ORF Klima (AT)',              'orf.at',                   NULL, 'T2', 15, 'https://orf.at/stories/3340111/',                                              'broadcaster_climate_desk'),
    ('YLE News Climate (FI)',       'yle.fi',                   NULL, 'T2', 15, 'https://yle.fi/news',                                                          'broadcaster_climate_desk'),
    ('Mongabay India',              'india.mongabay.com',       NULL, 'T2', 15, 'https://india.mongabay.com/about/',                                            'specialist_env_press'),
    ('Mongabay Asia',               'asia.mongabay.com',        NULL, 'T2', 15, 'https://asia.mongabay.com/about/',                                             'specialist_env_press'),
    ('Mongabay Latam',              'es.mongabay.com',          NULL, 'T2', 15, 'https://es.mongabay.com/about/',                                               'specialist_env_press'),
    ('Mongabay',                    'mongabay.com',             NULL, 'T2', 15, 'https://mongabay.com/about/',                                                  'specialist_env_press'),
    ('China Dialogue',              'chinadialogue.net',        NULL, 'T2', 15, 'https://chinadialogue.net/en/about/',                                          'specialist_climate_press'),
    ('The Wire Science India',      'science.thewire.in',       NULL, 'T2', 15, 'https://thewire.in/about-us',                                                  'specialist_science_press'),
    ('Folha de Sao Paulo Ambiente', 'folha.uol.com.br',         NULL, 'T2', 15, 'https://www1.folha.uol.com.br/ambiente/',                                      'newspaper_climate_desk'),
    ('INPE Brazil',                 'inpe.br',                  NULL, 'T2', 15, 'http://www.inpe.br/institucional/',                                            'gov_climate_agency'),
    ('The Conversation',            'theconversation.com',      NULL, 'T2', 15, 'https://theconversation.com/who-we-are',                                       'academic_journalism'),
    ('Mother Jones',                'motherjones.com',          NULL, 'T2', 15, 'https://www.motherjones.com/about/',                                           'investigative_journalism'),
    ('InfoAmazonia',                'infoamazonia.org',         NULL, 'T2', 15, 'https://infoamazonia.org/en/about/',                                           'specialist_env_press'),
    ('Helsingin Sanomat',           'hs.fi',                    NULL, 'T2', 15, 'https://www.hs.fi/info/',                                                      'newspaper_general'),
    ('24ur Okolje (SI)',            '24ur.com',                 NULL, 'T2', 15, 'https://www.24ur.com/o-portalu',                                               'newspaper_general'),

    -- T3 — national mainstream where climate beat exists but isn't editorial focus
    ('Capital BG (BG)',             'capital.bg',               NULL, 'T3', 5,  'https://www.capital.bg/o-nas/',                                                'newspaper_business'),
    ('Dnevnik BG (BG)',             'dnevnik.bg',               NULL, 'T3', 5,  'https://www.dnevnik.bg/o_dnevnik/',                                            'newspaper_general'),
    ('Digi24 (RO)',                 'digi24.ro',                NULL, 'T3', 5,  'https://www.digi24.ro/despre-noi',                                             'broadcaster_general'),
    ('Index.hu Tudomány (HU)',     'index.hu',                 NULL, 'T3', 5,  'https://index.hu/24ora/elerhetosegek/',                                        'newspaper_general'),
    ('Premium Times Nigeria',       'premiumtimesng.com',       NULL, 'T3', 5,  'https://www.premiumtimesng.com/about',                                         'newspaper_general'),
    ('IOL South Africa',            'iol.co.za',                NULL, 'T3', 5,  'https://www.iol.co.za/about-iol',                                              'newspaper_general'),
    ('Andina Peru',                 'andina.pe',                NULL, 'T3', 5,  'https://andina.pe/agencia/seccion-quienes-somos.aspx',                         'news_agency_state'),
    ('Colombia Reports',            'colombiareports.com',      NULL, 'T3', 5,  'https://colombiareports.com/about/',                                           'newspaper_general'),
    ('Santiago Times',              'santiagotimes.cl',         NULL, 'T3', 5,  'https://santiagotimes.cl/about/',                                              'newspaper_general')
ON CONFLICT (domain) DO NOTHING;

-- Sanity log so deploy ops can see how many net-new rows landed
DO $$
DECLARE
    total_count INT;
BEGIN
    SELECT COUNT(*) INTO total_count FROM source_credibility_tiers;
    RAISE NOTICE 'migration 049: source_credibility_tiers now has % rows', total_count;
END $$;
