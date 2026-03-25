-- Migration 015: Global RSS feed expansion
-- Date: 2026-03-12
-- Adds climate news sources for US, UK, and underrepresented EU countries

-- Ensure countries exist in the countries table
INSERT INTO countries (country_code, country_name, flag_emoji, language_code, is_eu_member, enabled)
VALUES
    ('US', 'United States', '🇺🇸', 'en', FALSE, TRUE),
    ('GB', 'United Kingdom', '🇬🇧', 'en', FALSE, TRUE),
    ('SI', 'Slovenia', '🇸🇮', 'sl', TRUE, TRUE),
    ('HU', 'Hungary', '🇭🇺', 'hu', TRUE, TRUE),
    ('BG', 'Bulgaria', '🇧🇬', 'bg', TRUE, TRUE),
    ('HR', 'Croatia', '🇭🇷', 'hr', TRUE, TRUE),
    ('SK', 'Slovakia', '🇸🇰', 'sk', TRUE, TRUE),
    ('RO', 'Romania', '🇷🇴', 'ro', TRUE, TRUE)
ON CONFLICT (country_code) DO UPDATE SET enabled = TRUE;

-- US climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('NPR Climate (US)', 'https://feeds.npr.org/1025/rss.xml', 'npr.org', 'US', 'north_america', 'public'),
    ('AP News Climate (US)', 'https://rsshub.app/apnews/topics/climate-and-environment', 'apnews.com', 'US', 'north_america', 'public'),
    ('The Guardian Climate US', 'https://www.theguardian.com/us-news/climate-crisis/rss', 'theguardian.com', 'US', 'north_america', 'public'),
    ('Yale Climate Connections (US)', 'https://yaleclimateconnections.org/feed/', 'yaleclimateconnections.org', 'US', 'north_america', 'research'),
    ('Inside Climate News (US)', 'https://insideclimatenews.org/feed/', 'insideclimatenews.org', 'US', 'north_america', 'research'),
    ('Carbon Brief (US/Global)', 'https://www.carbonbrief.org/feed/', 'carbonbrief.org', 'US', 'global', 'scientific'),
    ('NASA Climate (US)', 'https://climate.nasa.gov/news/rss.xml', 'climate.nasa.gov', 'US', 'north_america', 'scientific'),
    ('NOAA Climate (US)', 'https://www.climate.gov/feeds/all.rss', 'climate.gov', 'US', 'north_america', 'scientific')
ON CONFLICT (feed_name) DO NOTHING;

-- UK climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('The Guardian Environment (GB)', 'https://www.theguardian.com/environment/rss', 'theguardian.com', 'GB', 'europe', 'public'),
    ('BBC Environment (GB)', 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml', 'bbc.co.uk', 'GB', 'europe', 'public'),
    ('Sky News Climate (GB)', 'https://feeds.skynews.com/feeds/rss/technology.xml', 'news.sky.com', 'GB', 'europe', 'public'),
    ('The Independent Climate (GB)', 'https://www.independent.co.uk/climate-change/rss', 'independent.co.uk', 'GB', 'europe', 'public'),
    ('Met Office Blog (GB)', 'https://blog.metoffice.gov.uk/feed/', 'metoffice.gov.uk', 'GB', 'europe', 'scientific')
ON CONFLICT (feed_name) DO NOTHING;

-- Slovenia climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('RTV SLO Okolje (SI)', 'https://www.rtvslo.si/feeds/00', 'rtvslo.si', 'SI', 'europe', 'public'),
    ('24ur Okolje (SI)', 'https://www.24ur.com/rss', '24ur.com', 'SI', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Hungary climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Index.hu Tudomány (HU)', 'https://index.hu/24ora/rss/tudomany/', 'index.hu', 'HU', 'europe', 'public'),
    ('HVG Tudomány (HU)', 'https://hvg.hu/rss/tudomany', 'hvg.hu', 'HU', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Bulgaria climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Dnevnik BG (BG)', 'https://www.dnevnik.bg/rss/', 'dnevnik.bg', 'BG', 'europe', 'public'),
    ('Capital BG (BG)', 'https://www.capital.bg/rss/', 'capital.bg', 'BG', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Additional Spain feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('El Mundo Ciencia (ES)', 'https://e00-elmundo.uecdn.es/elmundo/rss/ciencia.xml', 'elmundo.es', 'ES', 'europe', 'public'),
    ('Climatica La Marea (ES)', 'https://www.climatica.lamarea.com/feed/', 'climatica.lamarea.com', 'ES', 'europe', 'research')
ON CONFLICT (feed_name) DO NOTHING;

-- Additional Austria feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('ORF Klima (AT)', 'https://rss.orf.at/science.xml', 'orf.at', 'AT', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Additional Greece feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Proto Thema Environment (GR)', 'https://www.protothema.gr/rss/', 'protothema.gr', 'GR', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Croatia
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Jutarnji List (HR)', 'https://www.jutarnji.hr/rss', 'jutarnji.hr', 'HR', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Romania
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Digi24 (RO)', 'https://www.digi24.ro/rss', 'digi24.ro', 'RO', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Slovakia
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('SME Veda (SK)', 'https://veda.sme.sk/rss', 'sme.sk', 'SK', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;
