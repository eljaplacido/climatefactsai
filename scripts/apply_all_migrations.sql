-- =============================================================================
-- CONSOLIDATED MIGRATIONS (002-012) — Idempotent
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < scripts/apply_all_migrations.sql
-- =============================================================================

BEGIN;

-- ============================================================================
-- 002: Claims status tracking
-- ============================================================================

DO $$ BEGIN CREATE TYPE claims_status_enum AS ENUM ('pending','processing','completed','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE articles ADD COLUMN IF NOT EXISTS claims_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS claims_error_message TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS claims_processed_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_articles_claims_status ON articles(claims_status);
CREATE INDEX IF NOT EXISTS idx_articles_claims_status_count ON articles(claims_status, claims_count);

UPDATE articles SET claims_status = CASE
    WHEN claims_count > 0 THEN 'completed'
    ELSE 'pending'
END WHERE claims_status IS NULL;

CREATE OR REPLACE FUNCTION article_has_claims_available(
    p_claims_status VARCHAR(50), p_claims_count INTEGER
) RETURNS BOOLEAN AS $fn$
BEGIN RETURN p_claims_status = 'completed' AND p_claims_count > 0; END;
$fn$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE VIEW articles_claims_status_view AS
SELECT a.article_id, a.title, a.url, a.claims_status, a.claims_count,
       a.verified_claims_count, a.claims_error_message, a.claims_processed_at,
       article_has_claims_available(a.claims_status, a.claims_count) as claims_available,
       a.created_at, a.updated_at
FROM articles a ORDER BY a.created_at DESC;

-- ============================================================================
-- 003: URL analyses table
-- ============================================================================

CREATE TABLE IF NOT EXISTS url_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    submitted_url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    source_domain VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    title TEXT,
    source_name VARCHAR(255),
    extracted_text TEXT,
    language_code VARCHAR(10),
    published_date TIMESTAMPTZ,
    extracted_claims JSONB,
    fact_checks JSONB,
    evidence JSONB,
    reliability_score INTEGER,
    overall_credibility VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_time_ms INTEGER,
    error_message TEXT,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT valid_priority CHECK (priority IN ('normal', 'high')),
    CONSTRAINT valid_credibility CHECK (overall_credibility IS NULL OR overall_credibility IN ('HIGH', 'MEDIUM', 'LOW'))
);

CREATE INDEX IF NOT EXISTS idx_url_analyses_user_id ON url_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_url_analyses_status ON url_analyses(status);
CREATE INDEX IF NOT EXISTS idx_url_analyses_url_hash ON url_analyses(url_hash);
CREATE INDEX IF NOT EXISTS idx_url_analyses_created_at ON url_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_url_analyses_user_created ON url_analyses(user_id, created_at DESC);

-- ============================================================================
-- 004: Decomposed confidence & evidence chains
-- ============================================================================

ALTER TABLE fact_checks ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE fact_checks ADD COLUMN IF NOT EXISTS evidence_chain JSONB DEFAULT NULL;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS claim_category VARCHAR(50) DEFAULT 'statistical';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS insight_summary TEXT DEFAULT NULL;
ALTER TABLE url_analyses ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE url_analyses ADD COLUMN IF NOT EXISTS reliability_breakdown JSONB DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_claims_category ON claims(claim_category);

-- ============================================================================
-- 005: Source profiles
-- ============================================================================

CREATE TABLE IF NOT EXISTS source_profiles (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(255) NOT NULL UNIQUE,
    source_domain VARCHAR(255) NOT NULL UNIQUE,
    credibility_score INT DEFAULT 50 CHECK (credibility_score >= 0 AND credibility_score <= 100),
    editorial_standards VARCHAR(50) DEFAULT 'unknown',
    fact_check_record VARCHAR(50) DEFAULT 'unknown',
    transparency_level VARCHAR(50) DEFAULT 'unknown',
    total_articles_analyzed INT DEFAULT 0,
    average_reliability_score FLOAT DEFAULT NULL,
    total_claims_verified INT DEFAULT 0,
    total_claims_disputed INT DEFAULT 0,
    false_claim_rate FLOAT DEFAULT 0.0,
    source_type VARCHAR(50) DEFAULT 'news_outlet',
    country_code VARCHAR(2) DEFAULT NULL,
    description TEXT DEFAULT NULL,
    website_url VARCHAR(2048) DEFAULT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_profiles_domain ON source_profiles(source_domain);
CREATE INDEX IF NOT EXISTS idx_source_profiles_name ON source_profiles(source_name);
CREATE INDEX IF NOT EXISTS idx_source_profiles_credibility ON source_profiles(credibility_score DESC);

-- /api/v2/sources reads reliability_tier from source_profiles for tier gating
ALTER TABLE source_profiles ADD COLUMN IF NOT EXISTS reliability_tier VARCHAR(20) DEFAULT 'public';
CREATE INDEX IF NOT EXISTS idx_source_profiles_reliability_tier ON source_profiles(reliability_tier);

ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_profile_id UUID REFERENCES source_profiles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_source_profile ON articles(source_profile_id);

-- ============================================================================
-- 006: Analysis article HTML
-- ============================================================================

ALTER TABLE articles ADD COLUMN IF NOT EXISTS analysis_article_html TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS analysis_article_generated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_articles_analysis_generated
ON articles (analysis_article_generated_at)
WHERE analysis_article_generated_at IS NOT NULL;

-- ============================================================================
-- 007: Article conversations
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    user_id UUID,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    context_used TEXT[],
    model_used VARCHAR(100) DEFAULT 'claude-3-5-sonnet-20240620',
    confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_article ON article_conversations(article_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON article_conversations(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_created ON article_conversations(created_at DESC);

-- ============================================================================
-- 008: Climate forecasts
-- ============================================================================

CREATE TABLE IF NOT EXISTS climate_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    forecast_date DATE NOT NULL,
    temperature_avg FLOAT,
    temperature_min FLOAT,
    temperature_max FLOAT,
    precipitation_mm FLOAT,
    wind_speed_ms FLOAT,
    humidity_pct FLOAT,
    confidence FLOAT DEFAULT 0.5,
    raw_data JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '6 hours'
);

CREATE INDEX IF NOT EXISTS idx_forecasts_country ON climate_forecasts(country_code);
CREATE INDEX IF NOT EXISTS idx_forecasts_date ON climate_forecasts(forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_expires ON climate_forecasts(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_forecasts_unique ON climate_forecasts(country_code, source_name, forecast_date);

-- ============================================================================
-- 009: Content categories
-- ============================================================================

ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_category VARCHAR(50);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS executive_brief TEXT;

CREATE INDEX IF NOT EXISTS idx_articles_content_category
    ON articles (content_category) WHERE content_category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_articles_category_country
    ON articles (content_category, country_code) WHERE content_category IS NOT NULL;

-- ============================================================================
-- 010: User feed preferences (only if users table exists)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
        CREATE TABLE IF NOT EXISTS user_feed_preferences (
            preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            country_codes TEXT[] NOT NULL DEFAULT '{}',
            update_frequency VARCHAR(30) NOT NULL DEFAULT 'daily',
            keywords TEXT[] DEFAULT '{}',
            last_updated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT fk_user_feed_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_feed_preferences_user ON user_feed_preferences (user_id);
        CREATE INDEX IF NOT EXISTS idx_user_feed_preferences_frequency ON user_feed_preferences (update_frequency, last_updated_at);
    END IF;
END $$;

-- ============================================================================
-- 011: Semantic search indexes
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'articles' AND column_name = 'embedding'
    ) THEN
        ALTER TABLE articles ADD COLUMN embedding vector(1536);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_articles_embedding_hnsw
    ON articles USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

CREATE INDEX IF NOT EXISTS idx_articles_fts
    ON articles USING gin (
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(extracted_text, ''))
    );

-- ============================================================================
-- 012: Global sources and tiers
-- ============================================================================

ALTER TABLE source_credibility ADD COLUMN IF NOT EXISTS reliability_tier VARCHAR(20) DEFAULT 'public';

INSERT INTO countries (country_code, country_name, country_name_native, is_eu_member, language_code, flag_emoji, enabled)
VALUES
    ('US', 'United States', 'United States', false, 'en', '🇺🇸', true),
    ('XX', 'International', 'International', false, 'en', '🌍', true),
    ('GB', 'United Kingdom', 'United Kingdom', false, 'en', '🇬🇧', true)
ON CONFLICT (country_code) DO NOTHING;

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

UPDATE source_credibility SET reliability_tier = 'research'
WHERE source_name ILIKE '%Carbon Brief%' AND reliability_tier = 'public';
UPDATE source_credibility SET reliability_tier = 'scientific'
WHERE source_name ILIKE '%European Environment Agency%' AND reliability_tier = 'public';
UPDATE source_credibility SET reliability_tier = 'scientific'
WHERE source_name ILIKE '%EEA%' AND reliability_tier = 'public';

-- ============================================================================
-- CLEANUP: Delete broken Helsinki fact-checks
-- ============================================================================

DELETE FROM fact_checks WHERE claim_id IN
  (SELECT claim_id FROM claims WHERE article_id = 'e34ad0c5-58c2-4b04-9d0e-d4dc1dcba77a');
DELETE FROM claims WHERE article_id = 'e34ad0c5-58c2-4b04-9d0e-d4dc1dcba77a';
UPDATE articles SET claims_status = 'pending', claims_count = 0, verified_claims_count = 0
  WHERE article_id = 'e34ad0c5-58c2-4b04-9d0e-d4dc1dcba77a';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'All 12 migrations applied successfully.';
END $$;

COMMIT;
