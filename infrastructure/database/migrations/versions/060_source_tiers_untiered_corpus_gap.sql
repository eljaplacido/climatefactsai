-- Migration 060: source_credibility_tiers — close the untiered corpus gap (2026-06-02)
--
-- A live scan of /api/v2/sources surfaced 84 "Unrated" profiles. The vast
-- majority were a display artefact: phantom source_profiles rows carry a
-- fabricated slug domain (legacy seed pollution, e.g. `carbon-brief-c078`)
-- that never joined the tier table even though the source IS tiered under its
-- real domain. That half is fixed in code by matching the tier join on
-- source_name OR domain (source_profiles._attach_credibility_tiers, 2026-06-02).
--
-- This migration seeds the genuine remainder: 11 sources whose NAME is absent
-- from the tier table. Five of them carry live articles whose credibility was
-- defaulting to 50 because source_tier_service._db_lookup is domain-keyed — so
-- the `domain` here is the source's real article-URL host (verified against the
-- live profiles) to fix scoring as well as display:
--   European Commission  ec.europa.eu   (95 articles)
--   SEMARNAT             gob.mx         (40 articles — Mexican federal env ministry)
--   Masdar UAE           masdar.ae      (35 articles)
--   Norwegian Road Fed.  ofv.no         (30 articles — EV registration data org)
--   Polish Climate Mon.  polishclimatemonitor.pl (15 articles)
-- (UNEP Africa + INPE Brazil were already covered — unep.org is tiered and both
--  names match existing rows via the name-aware join — so they are NOT re-seeded.)
--
-- Tier rubric (same as mig 027/033/049/058):
--   T1 = +30 canonical climate/science/gov with editorial+corrections standards
--   T2 = +15 regional/specialist outlets, data/met agencies, climate desks
--   T3 = +5  national mainstream / corporate where the climate beat isn't the focus
--
-- Idempotent: ON CONFLICT (domain) DO NOTHING — re-runnable, only adds net-new
-- rows. Sources whose real domain is already tiered under a different name
-- (Reuters Environment, UN Climate News, NRDC Blog, yle.fi, Le Monde, www.hs.fi,
-- Al Jazeera English) are intentionally NOT seeded here — they are zero-article
-- phantom duplicates handled by the separate profile-cleanup decision.

INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    -- T1 — government / intergovernmental climate authorities
    ('European Commission',       'ec.europa.eu',            NULL, 'T1', 30, 'https://commission.europa.eu/about_en',                              'intergovernmental_agency'),
    ('SEMARNAT',                  'gob.mx',                  NULL, 'T1', 30, 'https://www.gob.mx/semarnat/que-hacemos',                            'gov_climate_agency'),

    -- T2 — specialist / regional climate press, government data orgs
    ('Norwegian Road Federation', 'ofv.no',                  NULL, 'T2', 15, 'https://ofv.no/om-ofv',                                              'transport_data_org'),
    ('Rijkswaterstaat',           'rijkswaterstaat.nl',      NULL, 'T2', 15, 'https://www.rijkswaterstaat.nl/en/about-us',                         'gov_infrastructure_agency'),
    ('EurActiv Climate',          'euractiv.com',            NULL, 'T2', 15, 'https://www.euractiv.com/sections/climate-environment/',             'specialist_eu_policy_press'),
    ('Eco-Business',              'eco-business.com',        NULL, 'T2', 15, 'https://www.eco-business.com/about-us/',                             'specialist_sustainability_press'),
    ('The Daily Climate',         'dailyclimate.org',        NULL, 'T2', 15, 'https://www.dailyclimate.org/about',                                 'specialist_climate_press'),
    ('Dialogo Chino',             'dialogochino.net',        NULL, 'T2', 15, 'https://dialogochino.net/en/about-us/',                              'specialist_climate_press'),
    ('Daily Maverick Environment','dailymaverick.co.za',     NULL, 'T2', 15, 'https://www.dailymaverick.co.za/section/our-burning-planet/',        'newspaper_climate_desk'),

    -- T3 — corporate / niche where the climate beat is not editorial journalism
    ('Masdar UAE',                'masdar.ae',               NULL, 'T3', 5,  'https://masdar.ae/en/about-us',                                      'corporate_clean_energy'),
    ('Polish Climate Monitor',    'polishclimatemonitor.pl', NULL, 'T3', 5,  'https://polishclimatemonitor.pl/',                                   'niche_climate_site')
ON CONFLICT (domain) DO NOTHING;

DO $$
DECLARE total_count INT;
BEGIN
    SELECT COUNT(*) INTO total_count FROM source_credibility_tiers;
    RAISE NOTICE 'migration 060: source_credibility_tiers now has % rows', total_count;
END $$;
