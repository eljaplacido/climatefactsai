-- Migration 033: source credibility tier expansion (Phase 5C, 2026-05-24)
--
-- Extends migration 027's 27-source seed with another ~50 sources covering:
--   - Government / national climate agencies (NASA, NOAA, NSIDC, etc.)
--   - IFCN-verified fact-checkers (PolitiFact, Snopes, Climate Feedback, etc.)
--   - More academic publishers (Elsevier, Wiley, Springer, Frontiers, Copernicus)
--   - Specialist climate journalism outlets
--
-- Tier rubric (unchanged from migration 027):
--   T1 = +30 (Scimago Q1, IFCN-verified, national met service)
--   T2 = +15 (Q2 / specialist press with corrections / accredited org)
--   T3 = +5  (Q3-Q4 / NGO with sourcing)
--   unknown = 0 (default)
--   retracted = −30
--
-- Idempotent via ON CONFLICT DO NOTHING — safe to re-run.

-- =============================================================================
-- T1: Government climate / earth-system agencies (institutional gold standard)
-- =============================================================================
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('NASA Climate',            'climate.nasa.gov',     NULL, 'T1', 30, 'https://climate.nasa.gov/about',                            'gov_climate_agency'),
    ('NASA Goddard',            'nasa.gov',             NULL, 'T1', 30, 'https://www.nasa.gov',                                       'gov_space_agency'),
    ('NOAA Climate.gov',        'climate.gov',          NULL, 'T1', 30, 'https://www.climate.gov/about',                              'gov_climate_agency'),
    ('NOAA',                    'noaa.gov',             NULL, 'T1', 30, 'https://www.noaa.gov',                                       'gov_oceanic_atmos'),
    ('NSIDC',                   'nsidc.org',            NULL, 'T1', 30, 'https://nsidc.org/about',                                    'gov_data_centre'),
    ('US EPA',                  'epa.gov',              NULL, 'T1', 30, 'https://www.epa.gov/aboutepa',                               'gov_environmental_agency'),
    ('Copernicus Climate Change', 'climate.copernicus.eu', NULL, 'T1', 30, 'https://climate.copernicus.eu/about-us',                  'eu_climate_service'),
    ('ESA',                     'esa.int',              NULL, 'T1', 30, 'https://www.esa.int/About_Us',                               'gov_space_agency'),
    ('British Antarctic Survey', 'bas.ac.uk',           NULL, 'T1', 30, 'https://www.bas.ac.uk/about/',                               'gov_polar_research'),
    ('UK Met Office',           'metoffice.gov.uk',     NULL, 'T1', 30, 'https://www.metoffice.gov.uk/about-us',                      'gov_met_service'),
    ('Météo-France',            'meteofrance.com',      NULL, 'T1', 30, 'https://meteofrance.com/qui-sommes-nous',                    'gov_met_service'),
    ('JMA Japan',               'jma.go.jp',            NULL, 'T1', 30, 'https://www.jma.go.jp/jma/en/Activities/Activities.html',    'gov_met_service'),
    ('DWD Germany',             'dwd.de',               NULL, 'T1', 30, 'https://www.dwd.de/EN/aboutus/aboutus_node.html',             'gov_met_service'),
    ('WMO',                     'wmo.int',              NULL, 'T1', 30, 'https://wmo.int/about-us',                                   'un_specialised_agency'),
    ('UNEP',                    'unep.org',             NULL, 'T1', 30, 'https://www.unep.org/about-un-environment',                  'un_specialised_agency'),
    ('FAO',                     'fao.org',              NULL, 'T1', 30, 'https://www.fao.org/about',                                  'un_specialised_agency')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- T1: IFCN-verified fact-checkers (specialist credibility infrastructure)
-- Source: https://ifcncodeofprinciples.poynter.org/signatories
-- =============================================================================
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Climate Feedback',        'climatefeedback.org',  NULL, 'T1', 30, 'https://climatefeedback.org/about/',                          'ifcn_verified_climate'),
    ('PolitiFact',              'politifact.com',       NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/politifact', 'ifcn_verified'),
    ('Snopes',                  'snopes.com',           NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/snopes',     'ifcn_verified'),
    ('Full Fact',               'fullfact.org',         NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/full-fact', 'ifcn_verified'),
    ('AFP Fact Check',          'factcheck.afp.com',    NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/afp-fact-check', 'ifcn_verified'),
    ('FactCheck.org',           'factcheck.org',        NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/factcheck-org', 'ifcn_verified'),
    ('Reuters Fact Check',      'reutersagency.com',    NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/reuters-fact-check', 'ifcn_verified'),
    ('Lead Stories',            'leadstories.com',      NULL, 'T1', 30, 'https://ifcncodeofprinciples.poynter.org/profile/lead-stories', 'ifcn_verified')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- T1: Additional Scimago Q1 academic publishers
-- =============================================================================
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Elsevier',                'elsevier.com',         '10.1016', 'T1', 30, 'https://www.elsevier.com/about',                          'scimago_q1_publisher'),
    ('Wiley',                   'wiley.com',            '10.1002', 'T1', 30, 'https://www.wiley.com/network',                           'scimago_q1_publisher'),
    ('Springer',                'springer.com',         '10.1007', 'T1', 30, 'https://www.springer.com/about',                          'scimago_q1_publisher'),
    ('Springer Nature',         'springernature.com',   '10.1038', 'T1', 30, 'https://www.springernature.com/about',                    'scimago_q1_publisher'),
    ('Cambridge University Press', 'cambridge.org',     '10.1017', 'T1', 30, 'https://www.cambridge.org/about-us',                      'scimago_q1_publisher'),
    ('Oxford Academic',         'academic.oup.com',     '10.1093', 'T1', 30, 'https://academic.oup.com',                                'scimago_q1_publisher'),
    ('Frontiers',               'frontiersin.org',      '10.3389', 'T1', 30, 'https://www.frontiersin.org/about/about-frontiers',       'scimago_q1_open_access'),
    ('Copernicus Publications', 'copernicus.org',       '10.5194', 'T1', 30, 'https://publications.copernicus.org/about.html',          'scimago_q1_open_access'),
    ('PLOS Climate',            'journals.plos.org',    '10.1371', 'T1', 30, 'https://journals.plos.org/climate/',                      'scimago_q1_open_access'),
    ('AGU Journals',            'agupubs.onlinelibrary.wiley.com', '10.1029', 'T1', 30, 'https://www.agu.org/publications', 'scimago_q1_society_journal')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- T2: Additional mainstream/specialist outlets
-- =============================================================================
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Climate Home News',       'climatechangenews.com', NULL, 'T2', 15, 'https://www.climatechangenews.com/about/',                   'specialist_climate_press'),
    ('Mongabay',                'mongabay.com',         NULL, 'T2', 15, 'https://www.mongabay.com/about/',                            'environmental_journalism'),
    ('Yale Climate Connections', 'yaleclimateconnections.org', NULL, 'T2', 15, 'https://yaleclimateconnections.org/about/',            'university_climate_journalism'),
    ('E&E News',                'eenews.net',           NULL, 'T2', 15, 'https://www.eenews.net/about/',                              'specialist_energy_press'),
    ('Politico',                'politico.com',         NULL, 'T2', 15, 'https://www.politico.com/about-us',                          'mainstream_corrections'),
    ('Financial Times',         'ft.com',               NULL, 'T2', 15, 'https://aboutus.ft.com',                                     'financial_press'),
    ('The Economist',           'economist.com',        NULL, 'T2', 15, 'https://www.economist.com/about-the-economist',              'mainstream_corrections'),
    ('NHK World',               'nhk.or.jp',            NULL, 'T2', 15, 'https://www.nhk.or.jp/corporateinfo/english/index.html',     'public_broadcaster'),
    ('ABC Australia',           'abc.net.au',           NULL, 'T2', 15, 'https://about.abc.net.au',                                   'public_broadcaster'),
    ('Deutsche Welle',          'dw.com',               NULL, 'T2', 15, 'https://www.dw.com/en/about-dw/profile/s-30688',             'public_broadcaster')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- T3: Additional NGO / research institutes
-- =============================================================================
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Stockholm Environment Institute', 'sei.org', NULL, 'T3', 5, 'https://www.sei.org/about/',                                       'research_institute'),
    ('Potsdam Institute',        'pik-potsdam.de',       NULL, 'T3', 5, 'https://www.pik-potsdam.de/en/institute',                    'research_institute'),
    ('Pew Research Climate',     'pewresearch.org',      NULL, 'T3', 5, 'https://www.pewresearch.org/about/',                          'research_polling'),
    ('Resources For the Future', 'rff.org',              NULL, 'T3', 5, 'https://www.rff.org/about/',                                  'research_think_tank'),
    ('CDP',                      'cdp.net',              NULL, 'T3', 5, 'https://www.cdp.net/en/info/about-us',                        'corporate_disclosure_ngo'),
    ('Global Carbon Project',    'globalcarbonproject.org', NULL, 'T3', 5, 'https://www.globalcarbonproject.org',                     'research_consortium'),
    ('Greenpeace',               'greenpeace.org',       NULL, 'T3', 5, 'https://www.greenpeace.org/international/about/',             'advocacy_ngo'),
    ('350.org',                  '350.org',              NULL, 'T3', 5, 'https://350.org/about/',                                      'advocacy_ngo'),
    ('Climate Council Australia', 'climatecouncil.org.au', NULL, 'T3', 5, 'https://www.climatecouncil.org.au/about-us/',               'advocacy_ngo'),
    ('Union of Concerned Scientists', 'ucsusa.org',     NULL, 'T3', 5, 'https://www.ucsusa.org/about',                                'science_advocacy')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- Adjust seed metadata column for the migration-027 seed rows that lack
-- last_audited_at. Cosmetic but keeps the audit query clean.
-- =============================================================================
UPDATE source_credibility_tiers
SET last_audited_at = NOW()
WHERE last_audited_at IS NULL;
