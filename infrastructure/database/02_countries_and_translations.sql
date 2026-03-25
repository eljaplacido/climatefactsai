-- =============================================================================
-- COUNTRIES AND TRANSLATIONS - EU/Europe Focus MVP
-- =============================================================================

-- Countries table (EU + Europe)
CREATE TABLE IF NOT EXISTS countries (
    country_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_code CHAR(2) UNIQUE NOT NULL, -- ISO 3166-1 alpha-2
    country_name VARCHAR(100) NOT NULL,
    country_name_native VARCHAR(100), -- Native name
    continent VARCHAR(50) DEFAULT 'Europe',
    is_eu_member BOOLEAN DEFAULT FALSE,
    language_code CHAR(2) NOT NULL, -- ISO 639-1
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    news_sources_count INT DEFAULT 0,
    articles_count INT DEFAULT 0,
    flag_emoji VARCHAR(10),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_countries_code ON countries(country_code);
CREATE INDEX IF NOT EXISTS idx_countries_enabled ON countries(enabled);
CREATE INDEX IF NOT EXISTS idx_countries_eu ON countries(is_eu_member);

-- Insert EU countries
INSERT INTO countries (country_code, country_name, country_name_native, is_eu_member, language_code, latitude, longitude, flag_emoji) VALUES
-- Nordic countries
('FI', 'Finland', 'Suomi', TRUE, 'fi', 64.0, 26.0, '🇫🇮'),
('SE', 'Sweden', 'Sverige', TRUE, 'sv', 62.0, 15.0, '🇸🇪'),
('DK', 'Denmark', 'Danmark', TRUE, 'da', 56.0, 10.0, '🇩🇰'),
('NO', 'Norway', 'Norge', FALSE, 'no', 60.0, 8.0, '🇳🇴'),
('IS', 'Iceland', 'Ísland', FALSE, 'is', 65.0, -18.0, '🇮🇸'),

-- Western Europe
('DE', 'Germany', 'Deutschland', TRUE, 'de', 51.0, 9.0, '🇩🇪'),
('GB', 'United Kingdom', 'United Kingdom', FALSE, 'en', 54.0, -2.0, '🇬🇧'),
('FR', 'France', 'France', TRUE, 'fr', 46.0, 2.0, '🇫🇷'),
('NL', 'Netherlands', 'Nederland', TRUE, 'nl', 52.3, 5.7, '🇳🇱'),
('BE', 'Belgium', 'België', TRUE, 'nl', 50.8, 4.3, '🇧🇪'),
('LU', 'Luxembourg', 'Luxembourg', TRUE, 'lb', 49.8, 6.1, '🇱🇺'),
('IE', 'Ireland', 'Éire', TRUE, 'ga', 53.0, -8.0, '🇮🇪'),
('AT', 'Austria', 'Österreich', TRUE, 'de', 47.5, 14.5, '🇦🇹'),
('CH', 'Switzerland', 'Schweiz', FALSE, 'de', 47.0, 8.0, '🇨🇭'),

-- Southern Europe
('ES', 'Spain', 'España', TRUE, 'es', 40.0, -4.0, '🇪🇸'),
('PT', 'Portugal', 'Portugal', TRUE, 'pt', 39.5, -8.0, '🇵🇹'),
('IT', 'Italy', 'Italia', TRUE, 'it', 42.8, 12.8, '🇮🇹'),
('GR', 'Greece', 'Ελλάδα', TRUE, 'el', 39.0, 22.0, '🇬🇷'),
('MT', 'Malta', 'Malta', TRUE, 'mt', 35.9, 14.4, '🇲🇹'),
('CY', 'Cyprus', 'Κύπρος', TRUE, 'el', 35.1, 33.4, '🇨🇾'),

-- Eastern Europe
('PL', 'Poland', 'Polska', TRUE, 'pl', 52.0, 20.0, '🇵🇱'),
('CZ', 'Czech Republic', 'Česko', TRUE, 'cs', 49.8, 15.5, '🇨🇿'),
('SK', 'Slovakia', 'Slovensko', TRUE, 'sk', 48.7, 19.7, '🇸🇰'),
('HU', 'Hungary', 'Magyarország', TRUE, 'hu', 47.0, 20.0, '🇭🇺'),
('RO', 'Romania', 'România', TRUE, 'ro', 46.0, 25.0, '🇷🇴'),
('BG', 'Bulgaria', 'България', TRUE, 'bg', 43.0, 25.0, '🇧🇬'),
('SI', 'Slovenia', 'Slovenija', TRUE, 'sl', 46.1, 15.0, '🇸🇮'),
('HR', 'Croatia', 'Hrvatska', TRUE, 'hr', 45.8, 16.0, '🇭🇷'),
('EE', 'Estonia', 'Eesti', TRUE, 'et', 59.0, 26.0, '🇪🇪'),
('LV', 'Latvia', 'Latvija', TRUE, 'lv', 57.0, 25.0, '🇱🇻'),
('LT', 'Lithuania', 'Lietuva', TRUE, 'lt', 56.0, 24.0, '🇱🇹')

ON CONFLICT (country_code) DO UPDATE SET
    country_name = EXCLUDED.country_name,
    country_name_native = EXCLUDED.country_name_native,
    is_eu_member = EXCLUDED.is_eu_member,
    flag_emoji = EXCLUDED.flag_emoji;

-- Add country_code to articles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS country_code CHAR(2) REFERENCES countries(country_code);
CREATE INDEX IF NOT EXISTS idx_articles_country ON articles(country_code);

-- Update existing articles to Finland
UPDATE articles SET country_code = 'FI' WHERE country_code IS NULL;

-- Article translations table
CREATE TABLE IF NOT EXISTS article_translations (
    translation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(article_id) ON DELETE CASCADE,
    from_language CHAR(2) NOT NULL,
    to_language CHAR(2) NOT NULL,
    translated_title TEXT,
    translated_summary TEXT,
    translated_content TEXT,
    translation_service VARCHAR(50) DEFAULT 'deepl',
    translation_confidence DECIMAL(4, 3),
    translated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, to_language)
);

CREATE INDEX IF NOT EXISTS idx_translations_article ON article_translations(article_id);
CREATE INDEX IF NOT EXISTS idx_translations_language ON article_translations(to_language);

-- Update stats view to include country info
CREATE OR REPLACE VIEW article_stats AS
SELECT 
    a.article_id,
    a.title,
    a.url,
    a.published_date,
    a.source_name,
    a.source_credibility_score,
    a.country_code,
    c.country_name,
    c.flag_emoji,
    a.overall_credibility,
    COUNT(DISTINCT cl.claim_id) as total_claims,
    COUNT(DISTINCT CASE WHEN fc.verification_status = 'VERIFIED' THEN fc.claim_id END) as verified_claims,
    COUNT(DISTINCT CASE WHEN fc.verification_status = 'DISPUTED' THEN fc.claim_id END) as disputed_claims,
    COUNT(DISTINCT CASE WHEN fc.verification_status = 'FALSE' THEN fc.claim_id END) as false_claims,
    AVG(fc.confidence_score) as avg_confidence
FROM articles a
LEFT JOIN countries c ON a.country_code = c.country_code
LEFT JOIN claims cl ON a.article_id = cl.article_id
LEFT JOIN fact_checks fc ON cl.claim_id = fc.claim_id
GROUP BY a.article_id, c.country_name, c.flag_emoji;

COMMIT;

