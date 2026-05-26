-- @notolerate
-- Migration 048: default research topics — curated seed for the research feed.
--
-- The user feedback (2026-05-27): "I want at least a few hundred global
-- research reports rigorously analyzed." The CrossRef poller from mig 047
-- only fires against subscriptions a user has explicitly created, so a
-- brand-new account lands on /research with an empty feed and no obvious
-- path to populate it. This migration adds:
--
--   default_research_topics — a curated catalogue of ~10 climate-research
--     topics that ship with the platform. New users can opt-in to any of
--     them with a single click; the CrossRef poller (cn-research-poll
--     cron, mig 047 + provision-infra) then delivers fresh DOIs to their
--     /research feed automatically.
--
-- Idempotent: ON CONFLICT (slug) DO NOTHING means re-running mig 048
-- doesn't duplicate the catalogue. The user-facing subscriptions table
-- (research_subscriptions, mig 047) is untouched — opt-in is per-user.

CREATE TABLE IF NOT EXISTS default_research_topics (
    topic_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug         VARCHAR(80)  NOT NULL UNIQUE,
    label        VARCHAR(200) NOT NULL,
    description  TEXT,
    keywords     TEXT[] DEFAULT '{}',
    category     VARCHAR(80),   -- 'science' | 'policy' | 'corporate' | 'finance' | 'risk'
    sort_order   INTEGER       NOT NULL DEFAULT 100,
    is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_default_research_topics_active_sort
    ON default_research_topics (is_active, sort_order, label)
    WHERE is_active = TRUE;


-- Seed the catalogue. Each row is a topic + reasonable CrossRef keyword
-- list. Sort order grouped so the UI can render them by category. Topics
-- selected to cover the strategic personas (scientist / policymaker /
-- ESG / business decision-maker / financial analyst).
INSERT INTO default_research_topics (slug, label, description, keywords, category, sort_order)
VALUES
    ('arctic-sea-ice',
     'Arctic sea ice',
     'Decadal extent, summer minima, multi-year ice trends, feedback loops.',
     ARRAY['arctic sea ice', 'sea ice extent', 'arctic amplification', 'ice albedo feedback'],
     'science',
     10),
    ('amoc-tipping-points',
     'AMOC + tipping points',
     'Atlantic Meridional Overturning Circulation slowdown + climate tipping point research.',
     ARRAY['amoc', 'atlantic overturning', 'tipping points', 'thermohaline circulation'],
     'science',
     20),
    ('ipcc-ar7-cycle',
     'IPCC AR7 cycle',
     'Working Group preparations, special reports, scoping meetings, methodology updates.',
     ARRAY['ipcc', 'ar7', 'working group', 'climate assessment'],
     'science',
     30),
    ('carbon-dioxide-removal',
     'Carbon dioxide removal',
     'CDR technologies — direct air capture, BECCS, enhanced weathering, ocean alkalinisation.',
     ARRAY['carbon dioxide removal', 'direct air capture', 'BECCS', 'enhanced weathering'],
     'science',
     40),
    ('attribution-extreme-weather',
     'Attribution + extreme weather',
     'Probabilistic attribution of heatwaves, floods, droughts, and storms to climate change.',
     ARRAY['climate attribution', 'extreme weather', 'heatwave attribution', 'storm attribution'],
     'science',
     50),
    ('cbam-eu-compliance',
     'CBAM + EU climate regulation',
     'Carbon Border Adjustment Mechanism, EU ETS reform, CSRD/ESRS implementation.',
     ARRAY['CBAM', 'carbon border adjustment', 'EU ETS', 'CSRD', 'ESRS'],
     'policy',
     60),
    ('ndcs-paris-ambition',
     'NDCs + Paris ambition gap',
     'Nationally Determined Contributions, Climate Action Tracker gap analysis.',
     ARRAY['NDC', 'nationally determined contributions', 'paris agreement', 'ambition gap'],
     'policy',
     70),
    ('sbti-corporate-targets',
     'SBTi + corporate net-zero',
     'Science Based Targets initiative validations, net-zero claim verification, scope-3 accounting.',
     ARRAY['science based targets', 'SBTi', 'corporate net zero', 'scope 3'],
     'corporate',
     80),
    ('greenwashing-ecgt',
     'Greenwashing + ECGT',
     'EU Green Claims Directive, FTC Green Guides, offset-based "climate neutral" claims.',
     ARRAY['greenwashing', 'green claims directive', 'ECGT', 'offset claims', 'climate neutral'],
     'corporate',
     90),
    ('transition-risk-finance',
     'Transition risk + sustainable finance',
     'TCFD/TNFD disclosure, transition plans, stranded asset analysis, IFRS S2.',
     ARRAY['transition risk', 'TCFD', 'TNFD', 'IFRS S2', 'stranded assets', 'sustainable finance'],
     'finance',
     100),
    ('physical-risk-adaptation',
     'Physical risk + adaptation finance',
     'ND-GAIN, Loss & Damage Fund, climate adaptation financing, insurance protection gap.',
     ARRAY['physical risk', 'climate adaptation', 'loss and damage', 'ND-GAIN', 'climate insurance'],
     'risk',
     110),
    ('agri-food-systems',
     'Climate × agriculture + food systems',
     'Yield impacts, methane reductions, fertilizer N2O, plant-based protein, food system emissions.',
     ARRAY['climate agriculture', 'food systems', 'methane livestock', 'fertilizer N2O'],
     'science',
     120)
ON CONFLICT (slug) DO NOTHING;


COMMENT ON TABLE default_research_topics IS
'Curated catalogue of climate-research topics shipped with the platform.
New users opt-in via POST /api/research/subscriptions/default; the
CrossRef poller (cn-research-poll cron) then delivers DOIs to their feed.
Add new topics via INSERT … ON CONFLICT DO NOTHING in a follow-up
migration. See api/research_feed_routes.py.';


DO $$
DECLARE
    n_topics INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_topics FROM default_research_topics WHERE is_active = TRUE;
    RAISE NOTICE 'Migration 048: default_research_topics seeded with % active topics', n_topics;
END
$$;
