-- Migration 061: source_profiles hygiene + final tier-gap close (2026-06-02)
--
-- Companion to mig 060 + the name-OR-domain tier join (source_profiles.py).
-- After 060 + Fix A, a live /api/v2/sources scan left 21 "Unrated" profiles.
-- Root cause for most: mig 058's `ON CONFLICT (domain) DO NOTHING` silently
-- dropped name-variant rows whose domain was already seeded under a canonical
-- name (e.g. 'Nature Climate Change'→nature.com lost to mig 027 'Nature'), so
-- the name-aware join can't find them; and the phantom profiles carry a
-- fabricated slug-hex domain that the domain join can't use either.
--
-- This migration finishes the slice with four guarded steps:
--   1. Seed the 13 tier rows still genuinely missing (incl. INPE Brazil, a top
--      earth-observation institute, and UN/UNFCCC climate news).
--   2. Repair the fabricated phantom domains to their real canonical domain so
--      the (more robust) domain join rates them — collision-guarded against the
--      source_profiles UNIQUE(source_domain) constraint.
--   3. Strip URL paths from any source_domain (fixes UNEP Africa's
--      'unep.org/regions/africa' → 'unep.org', which is already T1).
--   4. Delete the two residual ambiguous zero-article phantom stubs with no
--      resolvable real source (Science Climate, Capital FM Ethiopia).
--
-- Idempotent: tier inserts use ON CONFLICT DO NOTHING; repairs only touch
-- fabricated-domain zero-article rows and skip on collision; the delete is
-- pattern + zero-article + no-tier-match guarded.

-- 1. Missing tier rows -------------------------------------------------------
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('UN Climate News',             'unfccc.int',            NULL, 'T1', 30, 'https://unfccc.int/about-us',                              'un_climate_body'),
    ('INPE Brazil',                 'inpe.br',               NULL, 'T1', 30, 'https://www.gov.br/inpe/pt-br/acesso-a-informacao/institucional', 'science_agency'),
    ('BBC Climate (GB)',            'bbc.co.uk',             NULL, 'T2', 15, 'https://www.bbc.co.uk/news/science_and_environment',       'broadcaster_climate_desk'),
    ('yle.fi',                      'yle.fi',                NULL, 'T2', 15, 'https://yle.fi/aihe/tiede',                                'public_broadcaster'),
    ('Climate Change News',         'climatechangenews.com', NULL, 'T2', 15, 'https://www.climatechangenews.com/about/',                 'specialist_climate_press'),
    ('Le Monde',                    'lemonde.fr',            NULL, 'T2', 15, 'https://www.lemonde.fr/planete/',                          'newspaper_climate_desk'),
    ('Dnevnik BG (BG)',             'dnevnik.bg',            NULL, 'T3', 5,  'https://www.dnevnik.bg/',                                  'newspaper_general'),
    ('Index.hu Tudomány (HU)',      'index.hu',              NULL, 'T3', 5,  'https://index.hu/tudomany/',                               'newspaper_general'),
    ('Digi24 (RO)',                 'digi24.ro',             NULL, 'T3', 5,  'https://www.digi24.ro/',                                   'newspaper_general'),
    ('www.hs.fi',                   'hs.fi',                 NULL, 'T3', 5,  'https://www.hs.fi/tiede/',                                 'newspaper_general'),
    ('Folha de Sao Paulo Ambiente', 'folha.uol.com.br',      NULL, 'T3', 5,  'https://www1.folha.uol.com.br/ambiente/',                  'newspaper_general'),
    ('24ur Okolje (SI)',            '24ur.com',              NULL, 'T3', 5,  'https://www.24ur.com/novice/okolje',                       'newspaper_general'),
    ('Capital BG (BG)',             'capital.bg',            NULL, 'T3', 5,  'https://www.capital.bg/',                                  'newspaper_general')
ON CONFLICT (domain) DO NOTHING;

-- 2. Repair fabricated phantom domains to canonical (collision-guarded) -------
WITH canonical(name, domain) AS (VALUES
    ('BBC Climate (GB)','bbc.co.uk'),
    ('UN Climate News','unfccc.int'),
    ('Dnevnik BG (BG)','dnevnik.bg'),
    ('Index.hu Tudomány (HU)','index.hu'),
    ('yle.fi','yle.fi'),
    ('Digi24 (RO)','digi24.ro'),
    ('Climate Change News','climatechangenews.com'),
    ('www.hs.fi','hs.fi'),
    ('Nature Climate Change','nature.com'),
    ('Folha de Sao Paulo Ambiente','folha.uol.com.br'),
    ('ABC Environment Australia','abc.net.au'),
    ('24ur Okolje (SI)','24ur.com'),
    ('NRDC Blog','nrdc.org'),
    ('Le Monde','lemonde.fr'),
    ('Al Jazeera English','aljazeera.com'),
    ('Capital BG (BG)','capital.bg'),
    ('Copernicus Climate Service','climate.copernicus.eu')
)
UPDATE source_profiles sp
   SET source_domain = c.domain,
       last_updated_at = CURRENT_TIMESTAMP
  FROM canonical c
 WHERE LOWER(sp.source_name) = LOWER(c.name)
   AND COALESCE(sp.total_articles_analyzed, 0) = 0
   AND sp.source_domain ~ '-[0-9a-f]{4}$'
   AND NOT EXISTS (
       SELECT 1 FROM source_profiles s2
        WHERE LOWER(s2.source_domain) = LOWER(c.domain)
          AND s2.source_id <> sp.source_id
   );

-- 3. Strip URL paths from any source_domain (UNEP Africa etc.) ----------------
UPDATE source_profiles sp
   SET source_domain = split_part(sp.source_domain, '/', 1),
       last_updated_at = CURRENT_TIMESTAMP
 WHERE sp.source_domain LIKE '%/%'
   AND NOT EXISTS (
       SELECT 1 FROM source_profiles s2
        WHERE LOWER(s2.source_domain) = LOWER(split_part(sp.source_domain, '/', 1))
          AND s2.source_id <> sp.source_id
   );

-- 4. Delete residual ambiguous zero-article phantom stubs --------------------
DELETE FROM source_profiles sp
 WHERE COALESCE(sp.total_articles_analyzed, 0) = 0
   AND sp.source_domain ~ '-[0-9a-f]{4}$'
   AND NOT EXISTS (
       SELECT 1 FROM source_credibility_tiers t
        WHERE LOWER(t.source_name) = LOWER(sp.source_name)
           OR t.domain = LOWER(sp.source_domain)
   );

DO $$
DECLARE prof INT; tiers INT;
BEGIN
    SELECT COUNT(*) INTO prof FROM source_profiles;
    SELECT COUNT(*) INTO tiers FROM source_credibility_tiers;
    RAISE NOTICE 'migration 061: source_profiles=% rows, source_credibility_tiers=% rows', prof, tiers;
END $$;
