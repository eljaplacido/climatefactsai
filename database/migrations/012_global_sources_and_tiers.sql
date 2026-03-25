-- =============================================================================
-- MIGRATION 012: Global News Sources and Scientific Reliability Tiers
-- =============================================================================
-- Adds:
--   1. reliability_tier column on source_credibility
--   2. US and International (XX) country entries
--   3. 9 new global climate source credibility entries
--   4. Updates existing sources with reliability tiers
--   5. Ensures user_feed_preferences table exists
-- =============================================================================

-- 1. Add reliability_tier to source_credibility
ALTER TABLE source_credibility
    ADD COLUMN IF NOT EXISTS reliability_tier VARCHAR(20) DEFAULT 'public';

COMMENT ON COLUMN source_credibility.reliability_tier IS
    'scientific = IPCC, NASA, UN, EEA; research = Inside Climate News, Climate Central, Carbon Brief; public = all others';

-- 2. Insert US and International countries (schema matches actual countries table)
INSERT INTO countries (country_code, country_name, country_name_native, is_eu_member, language_code, flag_emoji, enabled)
VALUES
    ('US', 'United States', 'United States', false, 'en', '🇺🇸', true),
    ('XX', 'International', 'International', false, 'en', '🌍', true)
ON CONFLICT (country_code) DO NOTHING;

-- 3. Insert 9 new global climate source credibility entries
INSERT INTO source_credibility (source_name, source_url, source_type, overall_score, factual_reporting_score, transparency_score, country_code, language_code, reliability_tier)
VALUES
    ('Grist', 'https://grist.org/', 'news_website', 75, 78, 72, 'US', 'en', 'public'),
    ('The Daily Climate', 'https://www.dailyclimate.org/', 'news_website', 70, 72, 68, 'US', 'en', 'public'),
    ('IPCC', 'https://www.ipcc.ch/', 'scientific_organization', 98, 99, 97, 'XX', 'en', 'scientific'),
    ('Inside Climate News', 'https://insideclimatenews.org/', 'news_website', 85, 88, 82, 'US', 'en', 'research'),
    ('Climate Change News', 'https://www.climatechangenews.com/', 'news_website', 72, 74, 70, 'GB', 'en', 'public'),
    ('Reuters Environment', 'https://www.reuters.com/business/environment/', 'news_agency', 90, 92, 88, 'XX', 'en', 'public'),
    ('Climate Central', 'https://www.climatecentral.org/', 'research_organization', 88, 90, 86, 'US', 'en', 'research'),
    ('NYT Climate', 'https://www.nytimes.com/section/climate', 'news_website', 82, 84, 80, 'US', 'en', 'public'),
    ('UN Climate News', 'https://news.un.org/en/topic/climate-change', 'intergovernmental', 95, 96, 94, 'XX', 'en', 'scientific')
ON CONFLICT (source_name) DO UPDATE SET
    reliability_tier = EXCLUDED.reliability_tier,
    updated_at = NOW();

-- 4. Update existing sources with appropriate reliability tiers
UPDATE source_credibility SET reliability_tier = 'research'
WHERE source_name ILIKE '%Carbon Brief%' AND reliability_tier = 'public';

UPDATE source_credibility SET reliability_tier = 'scientific'
WHERE source_name ILIKE '%European Environment Agency%' AND reliability_tier = 'public';

UPDATE source_credibility SET reliability_tier = 'scientific'
WHERE source_name ILIKE '%EEA%' AND reliability_tier = 'public';

-- 5. Ensure user_feed_preferences exists (idempotent)
CREATE TABLE IF NOT EXISTS user_feed_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    country_codes TEXT[] DEFAULT '{}',
    update_frequency VARCHAR(30) DEFAULT 'daily',
    keywords TEXT[] DEFAULT '{}',
    last_updated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feed_prefs_user ON user_feed_preferences(user_id);
