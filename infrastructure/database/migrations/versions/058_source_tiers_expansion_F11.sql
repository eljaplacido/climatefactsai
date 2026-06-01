-- Migration 058: source_credibility_tiers expansion — F11 (2026-06-01)
--
-- The user flagged "STILL many sources that are not rated" on /sources.
-- Migrations 049/054 tiered ~88 outlets, but a re-scan of the distinct
-- source_names actually present in the corpus surfaced ~40 climate-dedicated
-- outlets with no tier match (they fall back to "Unrated" in the UI):
-- science agencies (NASA, NOAA, CSIRO, NIWA), specialist climate press
-- (Clean Energy Wire, DeSmog, Reporterre, Novethic, Observatório do Clima),
-- newspaper climate desks (SCMP, The Hindu, NPR, La Repubblica, Spiegel,
-- El Tiempo), data/intergov bodies (Copernicus, CEPAL, UNEP, IEA-adjacent),
-- and national mainstream where a climate beat exists.
--
-- Tier rubric (same as mig 049/027/033):
--   T1 = +30 canonical climate/science with editorial+corrections standards
--   T2 = +15 regional/specialist outlets, met agencies, climate desks
--   T3 = +5  national mainstream where the climate beat isn't the focus
--
-- Idempotent: ON CONFLICT (domain) DO NOTHING — a domain already seeded by
-- 049/054 is left untouched, so this only adds net-new rows. Safe to re-run.

INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    -- T1 — science agencies, intergovernmental data, academic journals
    ('NASA',                          'climate.nasa.gov',     NULL, 'T1', 30, 'https://science.nasa.gov/climate-change/',                 'science_agency'),
    ('NOAA',                          'climate.gov',          NULL, 'T1', 30, 'https://www.climate.gov/about',                            'science_agency'),
    ('CSIRO Australia',               'csiro.au',             NULL, 'T1', 30, 'https://www.csiro.au/en/about',                            'science_agency'),
    ('NIWA New Zealand',              'niwa.co.nz',           NULL, 'T1', 30, 'https://niwa.co.nz/about',                                 'science_agency'),
    ('NCAR Climate',                  'ncar.ucar.edu',        NULL, 'T1', 30, 'https://ncar.ucar.edu/who-we-are',                         'science_agency'),
    ('Nature Climate Change',         'nature.com',           NULL, 'T1', 30, 'https://www.nature.com/nclimate/',                         'academic_journal'),
    ('Environmental Research Letters','iopscience.iop.org',   NULL, 'T1', 30, 'https://iopscience.iop.org/journal/1748-9326',             'academic_journal'),
    ('Copernicus Climate Service',    'climate.copernicus.eu',NULL, 'T1', 30, 'https://climate.copernicus.eu/about-us',                   'intergovernmental_agency'),
    ('CEPAL',                         'cepal.org',            NULL, 'T1', 30, 'https://www.cepal.org/en/about',                           'un_regional_commission'),
    ('UNEP Africa',                   'unep.org',             NULL, 'T1', 30, 'https://www.unep.org/about-un-environment',                'un_specialised_body'),
    ('Clean Energy Wire (DE)',        'cleanenergywire.org',  NULL, 'T1', 30, 'https://www.cleanenergywire.org/about-us',                 'specialist_climate_press'),
    ('DeSmog',                        'desmog.com',           NULL, 'T1', 30, 'https://www.desmog.com/about/',                            'investigative_climate_press'),
    ('NRDC',                          'nrdc.org',             NULL, 'T1', 30, 'https://www.nrdc.org/about',                               'science_advocacy_org'),
    ('Environment and Climate Change Canada', 'canada.ca',    NULL, 'T1', 30, 'https://www.canada.ca/en/environment-climate-change.html', 'gov_climate_agency'),
    ('TERI India',                    'teriin.org',           NULL, 'T1', 30, 'https://www.teriin.org/about-us',                          'climate_policy_research'),
    ('Observatorio do Clima',         'oc.eco.br',            NULL, 'T1', 30, 'https://www.oc.eco.br/en/about/',                          'specialist_climate_org'),

    -- T2 — climate/science desks, met agencies, regional specialist press
    ('Reporterre (FR)',               'reporterre.net',       NULL, 'T2', 15, 'https://reporterre.net/Qui-sommes-nous',                   'specialist_env_press'),
    ('Novethic Climat (FR)',          'novethic.fr',          NULL, 'T2', 15, 'https://www.novethic.fr/qui-sommes-nous',                  'specialist_esg_press'),
    ('SCMP Climate',                  'scmp.com',             NULL, 'T2', 15, 'https://www.scmp.com/print/news/climate-change',           'newspaper_climate_desk'),
    ('The Hindu Climate',             'thehindu.com',         NULL, 'T2', 15, 'https://www.thehindu.com/sci-tech/energy-and-environment/', 'newspaper_climate_desk'),
    ('NPR Climate',                   'npr.org',              NULL, 'T2', 15, 'https://www.npr.org/sections/climate/',                    'broadcaster_climate_desk'),
    ('La Repubblica Ambiente (IT)',   'repubblica.it',        NULL, 'T2', 15, 'https://www.repubblica.it/green-and-blue/',                'newspaper_climate_desk'),
    ('Spiegel Wissenschaft (DE)',     'spiegel.de',           NULL, 'T2', 15, 'https://www.spiegel.de/wissenschaft/',                     'newspaper_science_desk'),
    ('El Tiempo Medio Ambiente',      'eltiempo.com',         NULL, 'T2', 15, 'https://www.eltiempo.com/noticias/medio-ambiente',         'newspaper_climate_desk'),
    ('Al Jazeera Climate',            'aljazeera.com',        NULL, 'T2', 15, 'https://www.aljazeera.com/climate-crisis/',                'broadcaster_climate_desk'),
    ('ABC Environment Australia',     'abc.net.au',           NULL, 'T2', 15, 'https://www.abc.net.au/news/environment',                  'broadcaster_climate_desk'),
    ('African Arguments',             'africanarguments.org', NULL, 'T2', 15, 'https://africanarguments.org/about/',                      'specialist_regional_press'),
    ('African Climate Foundation',    'africanclimatefoundation.org', NULL, 'T2', 15, 'https://africanclimatefoundation.org/about-us/',  'specialist_climate_org'),
    ('China Meteorological Administration', 'cma.gov.cn',      NULL, 'T2', 15, 'https://www.cma.gov.cn/en/',                               'met_agency'),
    ('Japan Meteorological Agency',   'jma.go.jp',            NULL, 'T2', 15, 'https://www.jma.go.jp/jma/en/menu.html',                   'met_agency'),
    ('Estonian Environment Agency',   'keskkonnaagentuur.ee', NULL, 'T2', 15, 'https://keskkonnaagentuur.ee/en',                          'gov_climate_agency'),
    ('SEAI',                          'seai.ie',              NULL, 'T2', 15, 'https://www.seai.ie/about-seai/',                          'gov_energy_agency'),
    ('BloombergNEF',                  'bnef.com',             NULL, 'T2', 15, 'https://about.bnef.com/',                                  'climate_finance_research'),

    -- T3 — national mainstream / general where a climate beat exists
    ('The Jakarta Post',              'thejakartapost.com',   NULL, 'T3', 5,  'https://www.thejakartapost.com/about-us',                  'newspaper_general'),
    ('La Nacion Argentina',           'lanacion.com.ar',      NULL, 'T3', 5,  'https://www.lanacion.com.ar/institucional/',               'newspaper_general'),
    ('Buenos Aires Times',            'batimes.com.ar',       NULL, 'T3', 5,  'https://www.batimes.com.ar/about-us',                      'newspaper_general'),
    ('Proto Thema Environment (GR)',  'protothema.gr',        NULL, 'T3', 5,  'https://www.protothema.gr/',                               'newspaper_general'),
    ('Times of Israel Environment',   'timesofisrael.com',    NULL, 'T3', 5,  'https://www.timesofisrael.com/about/',                     'newspaper_general'),
    ('Joy Online Ghana',              'myjoyonline.com',      NULL, 'T3', 5,  'https://www.myjoyonline.com/about-us/',                    'newspaper_general'),
    ('HVG Tudomány (HU)',             'hvg.hu',               NULL, 'T3', 5,  'https://hvg.hu/info/impresszum',                           'newspaper_general'),
    ('Clarin Sociedad',               'clarin.com',           NULL, 'T3', 5,  'https://www.clarin.com/sociedad/',                         'newspaper_general')
ON CONFLICT (domain) DO NOTHING;

DO $$
DECLARE total_count INT;
BEGIN
    SELECT COUNT(*) INTO total_count FROM source_credibility_tiers;
    RAISE NOTICE 'migration 058: source_credibility_tiers now has % rows', total_count;
END $$;
