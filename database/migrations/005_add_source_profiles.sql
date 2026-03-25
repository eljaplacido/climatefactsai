-- Migration 005: Add source profiles table for reusable source trust metadata
-- Supports MVP Feature 5: Source trust metadata with historical reliability context

CREATE TABLE IF NOT EXISTS source_profiles (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(255) NOT NULL UNIQUE,
    source_domain VARCHAR(255) NOT NULL UNIQUE,

    -- Trust metrics
    credibility_score INT DEFAULT 50 CHECK (credibility_score >= 0 AND credibility_score <= 100),
    editorial_standards VARCHAR(50) DEFAULT 'unknown',    -- rigorous, moderate, low, unknown
    fact_check_record VARCHAR(50) DEFAULT 'unknown',      -- excellent, good, mixed, poor, unknown
    transparency_level VARCHAR(50) DEFAULT 'unknown',     -- high, moderate, low, unknown

    -- Historical stats (updated on each article ingestion)
    total_articles_analyzed INT DEFAULT 0,
    average_reliability_score FLOAT DEFAULT NULL,
    total_claims_verified INT DEFAULT 0,
    total_claims_disputed INT DEFAULT 0,
    false_claim_rate FLOAT DEFAULT 0.0,

    -- Source metadata
    source_type VARCHAR(50) DEFAULT 'news_outlet',        -- news_outlet, government_agency, research_institution, ngo, blog
    country_code VARCHAR(2) DEFAULT NULL,
    description TEXT DEFAULT NULL,
    website_url VARCHAR(2048) DEFAULT NULL,

    -- Timestamps
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_source_profiles_domain ON source_profiles(source_domain);
CREATE INDEX IF NOT EXISTS idx_source_profiles_name ON source_profiles(source_name);
CREATE INDEX IF NOT EXISTS idx_source_profiles_credibility ON source_profiles(credibility_score DESC);

-- Link articles to source profiles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_profile_id UUID REFERENCES source_profiles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_source_profile ON articles(source_profile_id);

COMMENT ON TABLE source_profiles IS 'Reusable source trust profiles with historical reliability tracking';
COMMENT ON COLUMN source_profiles.credibility_score IS 'Overall source credibility 0-100, updated as articles are analyzed';
COMMENT ON COLUMN source_profiles.false_claim_rate IS 'Fraction of claims from this source found to be false (0.0-1.0)';
