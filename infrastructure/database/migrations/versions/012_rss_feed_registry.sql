-- Migration 012: Dynamic RSS feed registry and global countries expansion
-- Date: 2026-03-04

-- RSS Feed Registry table
CREATE TABLE IF NOT EXISTS rss_feed_registry (
    feed_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_name VARCHAR(255) NOT NULL UNIQUE,
    feed_url TEXT NOT NULL UNIQUE,
    source_domain VARCHAR(255),
    country_code CHAR(2),
    region VARCHAR(50),
    reliability_tier VARCHAR(20) DEFAULT 'public',
    is_active BOOLEAN DEFAULT true,
    is_system_feed BOOLEAN DEFAULT true,
    last_fetched_at TIMESTAMPTZ,
    fetch_error_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rss_feed_active ON rss_feed_registry(is_active);
CREATE INDEX IF NOT EXISTS idx_rss_feed_region ON rss_feed_registry(region);

-- Seed existing 13 feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Grist', 'https://grist.org/feed/', 'grist.org', 'US', 'north_america', 'public'),
    ('The Daily Climate', 'https://www.dailyclimate.org/rss.xml', 'dailyclimate.org', 'US', 'north_america', 'public'),
    ('IPCC', 'https://www.ipcc.ch/feed/', 'ipcc.ch', 'XX', 'global', 'scientific'),
    ('Inside Climate News', 'https://insideclimatenews.org/feed/', 'insideclimatenews.org', 'US', 'north_america', 'research'),
    ('Climate Change News', 'https://www.climatechangenews.com/feed/', 'climatechangenews.com', 'GB', 'europe', 'public'),
    ('Reuters Environment', 'https://www.reuters.com/arc/outboundfeeds/v3/all/section/environment/?outputType=xml', 'reuters.com', 'XX', 'global', 'public'),
    ('Climate Central', 'https://www.climatecentral.org/feed', 'climatecentral.org', 'US', 'north_america', 'research'),
    ('NYT Climate', 'https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml', 'nytimes.com', 'US', 'north_america', 'public'),
    ('UN Climate News', 'https://news.un.org/feed/subscribe/en/topic/climate-change/feed/rss.xml', 'news.un.org', 'XX', 'global', 'scientific'),
    ('Earth.org', 'https://earth.org/feed/', 'earth.org', 'XX', 'global', 'research'),
    ('Nature Climate Change', 'https://www.nature.com/nclimate.rss', 'nature.com', 'XX', 'global', 'scientific'),
    ('Carbon Brief', 'https://www.carbonbrief.org/feed/', 'carbonbrief.org', 'GB', 'europe', 'research'),
    ('The Guardian Climate', 'https://www.theguardian.com/environment/climate-crisis/rss', 'theguardian.com', 'GB', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- New global feeds (11 additional)
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    -- Asia-Pacific
    ('China Dialogue', 'https://www.chinadialogue.net/feed/', 'chinadialogue.net', 'CN', 'asia_pacific', 'research'),
    ('The Wire Science India', 'https://science.thewire.in/feed/', 'thewire.in', 'IN', 'asia_pacific', 'public'),
    ('Mongabay Asia', 'https://news.mongabay.com/feed/', 'mongabay.com', 'XX', 'asia_pacific', 'research'),
    ('ABC Environment Australia', 'https://www.abc.net.au/news/feed/51120/rss.xml', 'abc.net.au', 'AU', 'asia_pacific', 'public'),
    -- Africa
    ('Daily Maverick Environment', 'https://www.dailymaverick.co.za/section/environment/feed/', 'dailymaverick.co.za', 'ZA', 'africa', 'public'),
    ('Climate Home News', 'https://www.climatechangenews.com/feed/', 'climatechangenews.com', 'GB', 'global', 'research'),
    ('African Arguments', 'https://africanarguments.org/feed/', 'africanarguments.org', 'XX', 'africa', 'public'),
    -- Latin America
    ('Mongabay Latam', 'https://es.mongabay.com/feed/', 'mongabay.com', 'XX', 'latin_america', 'research'),
    ('InfoAmazonia', 'https://infoamazonia.org/en/feed/', 'infoamazonia.org', 'BR', 'latin_america', 'research'),
    ('Dialogo Chino', 'https://dialogochino.net/en/feed/', 'dialogochino.net', 'XX', 'latin_america', 'research'),
    -- Scientific
    ('WMO Climate Press', 'https://wmo.int/feed', 'wmo.int', 'XX', 'global', 'scientific')
ON CONFLICT (feed_name) DO NOTHING;

-- Expand countries table with non-EU countries
INSERT INTO countries (country_code, country_name, country_name_native, flag_emoji, language_code, is_eu_member, enabled) VALUES
    ('US', 'United States', 'United States', '🇺🇸', 'en', false, true),
    ('CA', 'Canada', 'Canada', '🇨🇦', 'en', false, true),
    ('AU', 'Australia', 'Australia', '🇦🇺', 'en', false, true),
    ('JP', 'Japan', '日本', '🇯🇵', 'ja', false, true),
    ('CN', 'China', '中国', '🇨🇳', 'zh', false, true),
    ('IN', 'India', 'भारत', '🇮🇳', 'hi', false, true),
    ('BR', 'Brazil', 'Brasil', '🇧🇷', 'pt', false, true),
    ('ZA', 'South Africa', 'South Africa', '🇿🇦', 'en', false, true),
    ('NG', 'Nigeria', 'Nigeria', '🇳🇬', 'en', false, true),
    ('KE', 'Kenya', 'Kenya', '🇰🇪', 'en', false, true),
    ('MX', 'Mexico', 'México', '🇲🇽', 'es', false, true),
    ('AR', 'Argentina', 'Argentina', '🇦🇷', 'es', false, true),
    ('KR', 'South Korea', '대한민국', '🇰🇷', 'ko', false, true),
    ('ID', 'Indonesia', 'Indonesia', '🇮🇩', 'id', false, true),
    ('EG', 'Egypt', 'مصر', '🇪🇬', 'ar', false, true),
    ('SA', 'Saudi Arabia', 'المملكة العربية السعودية', '🇸🇦', 'ar', false, true),
    ('CL', 'Chile', 'Chile', '🇨🇱', 'es', false, true),
    ('CO', 'Colombia', 'Colombia', '🇨🇴', 'es', false, true)
ON CONFLICT (country_code) DO NOTHING;
