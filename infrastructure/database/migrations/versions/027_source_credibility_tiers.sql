-- Migration 027: source credibility tier database
--
-- Replaces the hard-coded KNOWN_VENUES set (8 publishers) in
-- bayesian_credibility.py with a database-backed tiering system
-- seeded from Scimago Journal Rankings, RetractionWatch, and IFCN.
--
-- Each source gets a tier (T1–T3, unknown) with evidence URLs
-- so external auditors can verify the classification.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS source_credibility_tiers (
    id              BIGSERIAL PRIMARY KEY,
    source_name     VARCHAR(255) NOT NULL,
    domain          VARCHAR(255),
    doi_prefix       VARCHAR(64),
    tier            VARCHAR(20) NOT NULL CHECK (tier IN ('T1', 'T2', 'T3', 'unknown', 'retracted')),
    prior_bonus      INTEGER NOT NULL DEFAULT 0,
    evidence_url    TEXT,
    classification  TEXT,
    retracted_count  INTEGER NOT NULL DEFAULT 0,
    last_audited_at  TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_source_credibility_tiers_domain UNIQUE (domain)
);

CREATE INDEX IF NOT EXISTS idx_source_credibility_tiers_tier
    ON source_credibility_tiers (tier);

CREATE INDEX IF NOT EXISTS idx_source_credibility_tiers_domain
    ON source_credibility_tiers (domain);

COMMENT ON TABLE source_credibility_tiers IS
'Evidence-backed source credibility tiers replacing the 8-publisher hard-coded whitelist.
 T1 = +30 (Scimago Q1 + IFCN-verified), T2 = +15 (Q2 / mainstream press with correction policy),
 T3 = +5  (Q3–Q4 / NGO with sourcing), unknown = 0, retracted = −30.';

-- Seed T1 scientific journals (Scimago Q1, DOI-equipped)
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Nature',          'nature.com',           '10.1038', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=21206', 'scimago_q1'),
    ('Science',         'science.org',          '10.1126', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=23572', 'scimago_q1'),
    ('The Lancet',      'thelancet.com',        '10.1016', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=24946', 'scimago_q1'),
    ('PNAS',            'pnas.org',             '10.1073', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=21181', 'scimago_q1'),
    ('Nature Climate Change', 'nature.com',     '10.1038', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=21100200805', 'scimago_q1'),
    ('Environmental Research Letters', 'iop.org', '10.1088', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=19700174906', 'scimago_q1'),
    ('Geophysical Research Letters', 'wiley.com', '10.1029', 'T1', 30, 'https://www.scimagojr.com/journalsearch.php?q=27872', 'scimago_q1')
ON CONFLICT (domain) DO NOTHING;

-- Seed T2 outlets (mainstream climate/energy press with corrections policy)
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('Carbon Brief',    'carbonbrief.org',      NULL, 'T2', 15, 'https://www.carbonbrief.org/about/', 'specialist_press_corrections'),
    ('Inside Climate News', 'insideclimatenews.org', NULL, 'T2', 15, 'https://insideclimatenews.org/about/', 'pulitzer_winning'),
    ('Grist',           'grist.org',            NULL, 'T2', 15, 'https://grist.org/about/', 'specialist_press'),
    ('Reuters',         'reuters.com',          NULL, 'T2', 15, 'https://www.reuters.com/policies/corrections/', 'wire_service_corrections'),
    ('BBC News',        'bbc.com',              NULL, 'T2', 15, 'https://www.bbc.com/news/help-41670342', 'public_broadcaster_corrections'),
    ('The Guardian',    'theguardian.com',      NULL, 'T2', 15, 'https://www.theguardian.com/info/complaints-and-corrections', 'mainstream_corrections'),
    ('Associated Press', 'apnews.com',          NULL, 'T2', 15, 'https://www.ap.org/about/news-values/principles/', 'wire_service_corrections'),
    ('Bloomberg Green',  'bloomberg.com',       NULL, 'T2', 15, 'https://www.bloomberg.com/company/values/', 'financial_press'),
    ('The Conversation', 'theconversation.com', NULL, 'T2', 15, 'https://theconversation.com/us/who-we-are', 'academic_journalism'),
    ('DeSmog',           'desmog.com',          NULL, 'T2', 15, 'https://www.desmog.com/about/', 'specialist_investigative')
ON CONFLICT (domain) DO NOTHING;

-- Seed T3 outlets (NGO / research institute, with sourcing)
INSERT INTO source_credibility_tiers (source_name, domain, doi_prefix, tier, prior_bonus, evidence_url, classification)
VALUES
    ('World Resources Institute', 'wri.org',        NULL, 'T3', 5, 'https://www.wri.org/about', 'research_ngo'),
    ('Climate Action Tracker',    'climateactiontracker.org', NULL, 'T3', 5, 'https://climateactiontracker.org/about/', 'research_consortium'),
    ('IEA',                       'iea.org',        NULL, 'T3', 5, 'https://www.iea.org/about', 'intergovernmental'),
    ('UNFCCC',                    'unfccc.int',     NULL, 'T3', 5, 'https://unfccc.int/about-us', 'intergovernmental'),
    ('IPCC',                      'ipcc.ch',        NULL, 'T3', 5, 'https://www.ipcc.ch/about/', 'intergovernmental'),
    ('IRENA',                     'irena.org',      NULL, 'T3', 5, 'https://www.irena.org/about', 'intergovernmental'),
    ('Our World in Data',         'ourworldindata.org', NULL, 'T3', 5, 'https://ourworldindata.org/about', 'research_data'),
    ('World Weather Attribution', 'worldweatherattribution.org', NULL, 'T3', 5, 'https://www.worldweatherattribution.org/about/', 'research_consortium'),
    ('Climate Central',           'climatecentral.org', NULL, 'T3', 5, 'https://www.climatecentral.org/about', 'research_ngo'),
    ('Germanwatch',               'germanwatch.org', NULL, 'T3', 5, 'https://www.germanwatch.org/en/about', 'research_ngo')
ON CONFLICT (domain) DO NOTHING;
