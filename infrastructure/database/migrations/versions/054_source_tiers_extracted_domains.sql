-- Migration 054: source tier seed for the actual URL-extracted domains.
-- 2026-05-27 — Slice S6 of audit loop 2.
--
-- After mig 049 + the post-deploy backfill, ~679 articles still had
-- source_credibility_score=50 (unknown). Direct DB diagnostic showed
-- the URLs extracted to subdomains / different domains than what
-- mig 049 seeded. Examples:
--   - 'Mongabay Asia' articles URL extract to news.mongabay.com,
--     not mongabay.com (which mig 049 inserted).
--   - 'Union of Concerned Scientists' articles → blog.ucs.org, not ucsusa.org.
--   - 'BloombergNEF' → about.bnef.com, not bloomberg.com.
--   - 'China Dialogue' migrated their site to dialogue.earth.
--   - 'NCAR Climate' uses news.ucar.edu.
--   - All major non-English desks (El Pais Clima, Le Monde Planete,
--     ORF Klima, Spiegel Wissenschaft, Repubblica, HVG, Reporterre,
--     Novethic, Clean Energy Wire) had no tier rows for their
--     extracted domains.
--
-- This migration adds the 30 actual extracted domains the corpus
-- ingestion is producing. ON CONFLICT (domain) DO UPDATE so existing
-- rows get correctly re-tiered if the prior seeded value was wrong.

INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    -- ── T1 — major dedicated climate / environment desks (international) ──
    ('El Pais Clima (ES)',         'elpais.com',          NULL, 'T1', 30, 'https://elpais.com/clima-y-medio-ambiente/',                  'newspaper_climate_desk'),
    ('Le Monde Planete (FR)',      'lemonde.fr',          NULL, 'T1', 30, 'https://www.lemonde.fr/planete/',                             'newspaper_climate_desk'),
    ('Spiegel Wissenschaft (DE)',  'spiegel.de',          NULL, 'T1', 30, 'https://www.spiegel.de/wissenschaft/',                        'newspaper_science_desk'),
    ('La Repubblica Ambiente (IT)', 'repubblica.it',      NULL, 'T1', 30, 'https://www.repubblica.it/ambiente/',                         'newspaper_climate_desk'),
    ('ORF Klima (AT)',             'science.orf.at',      NULL, 'T1', 30, 'https://science.orf.at/stories/3340111/',                     'broadcaster_climate_desk'),
    ('Clean Energy Wire (DE)',     'cleanenergywire.org', NULL, 'T1', 30, 'https://www.cleanenergywire.org/about-us',                    'specialist_climate_press'),
    ('China Dialogue',             'dialogue.earth',      NULL, 'T1', 30, 'https://dialogue.earth/en/about/',                            'specialist_climate_press'),
    ('Rocky Mountain Institute',   'rmi.org',             NULL, 'T1', 30, 'https://rmi.org/about/',                                      'specialist_climate_org'),
    ('Union of Concerned Scientists', 'blog.ucs.org',     NULL, 'T1', 30, 'https://www.ucsusa.org/about',                                'science_advocacy_org'),
    ('Union of Concerned Scientists', 'ucsusa.org',       NULL, 'T1', 30, 'https://www.ucsusa.org/about',                                'science_advocacy_org'),
    ('NPR Climate',                'npr.org',             NULL, 'T1', 30, 'https://www.npr.org/sections/climate/',                       'broadcaster_climate_desk'),
    ('NCAR Climate',               'news.ucar.edu',       NULL, 'T1', 30, 'https://news.ucar.edu/about',                                  'research_org_climate'),
    ('BloombergNEF',               'about.bnef.com',      NULL, 'T1', 30, 'https://about.bnef.com/about/',                                'specialist_climate_org'),

    -- ── T2 — regional climate-focused / national desks with editorial track ──
    ('Reporterre (FR)',            'reporterre.net',      NULL, 'T2', 15, 'https://reporterre.net/A-propos-de-Reporterre',               'specialist_env_press'),
    ('Novethic Climat (FR)',       'novethic.fr',         NULL, 'T2', 15, 'https://www.novethic.fr/qui-sommes-nous',                     'specialist_climate_press'),
    ('HVG Tudomány (HU)',          'hvg.hu',              NULL, 'T2', 15, 'https://hvg.hu/tudomany',                                     'newspaper_science_desk'),
    ('Mongabay Asia',              'news.mongabay.com',   NULL, 'T2', 15, 'https://news.mongabay.com/about/',                            'specialist_env_press'),
    ('Observatorio do Clima',      'oc.eco.br',           NULL, 'T2', 15, 'https://www.oc.eco.br/sobre/',                                'specialist_climate_org'),
    ('SCMP Climate',               'scmp.com',            NULL, 'T2', 15, 'https://www.scmp.com/about',                                  'newspaper_climate_desk'),
    ('Al Jazeera Climate',         'aljazeera.com',       NULL, 'T2', 15, 'https://www.aljazeera.com/topics/climate',                    'broadcaster_climate_desk'),
    ('The Hindu Climate',          'thehindu.com',        NULL, 'T2', 15, 'https://www.thehindu.com/sci-tech/energy-and-environment/',   'newspaper_climate_desk'),
    ('African Arguments',          'africanarguments.org', NULL, 'T2', 15, 'https://africanarguments.org/about/',                        'specialist_climate_press'),
    ('Proto Thema Environment (GR)', 'protothema.gr',     NULL, 'T2', 15, 'https://www.protothema.gr/about-us/',                         'newspaper_general'),

    -- ── T3 — national mainstream where climate beat exists ──
    ('El Tiempo Medio Ambiente',   'eltiempo.com',        NULL, 'T3', 5,  'https://www.eltiempo.com/nosotros',                            'newspaper_general'),
    ('Buenos Aires Times',         'batimes.com.ar',      NULL, 'T3', 5,  'https://www.batimes.com.ar/about',                             'newspaper_general'),
    ('Clarin Sociedad',            'clarin.com',          NULL, 'T3', 5,  'https://www.clarin.com/sociedad/',                             'newspaper_general'),
    ('Times of Israel Environment', 'timesofisrael.com',  NULL, 'T3', 5,  'https://www.timesofisrael.com/about/',                         'newspaper_general'),
    ('Joy Online Ghana',           'myjoyonline.com',     NULL, 'T3', 5,  'https://www.myjoyonline.com/about-us/',                        'newspaper_general'),
    ('IOL South Africa',           'iol.co.za',           NULL, 'T3', 5,  'https://www.iol.co.za/about-iol',                              'newspaper_general'),
    ('Santiago Times',             'santiagotimes.com',   NULL, 'T3', 5,  'https://santiagotimes.com/about/',                             'newspaper_general')
ON CONFLICT (domain) DO UPDATE
   SET tier = EXCLUDED.tier,
       prior_bonus = EXCLUDED.prior_bonus,
       source_name = COALESCE(source_credibility_tiers.source_name, EXCLUDED.source_name);

-- Sanity log
DO $$
DECLARE
    n INT;
BEGIN
    SELECT COUNT(*) INTO n FROM source_credibility_tiers;
    RAISE NOTICE 'migration 054: source_credibility_tiers now has % rows', n;
END $$;
