-- Migration: Add trust schema (publishers, articles with trust/provenance)
-- Date: 2025-12-12
-- Phase: 2 - Compliance & Trust

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE credibility_rating_enum AS ENUM (
    'UNKNOWN',
    'LOW',
    'MEDIUM',
    'HIGH',
    'VERIFIED'
);

CREATE TYPE summary_type_enum AS ENUM (
    'AI_GENERATED',
    'HUMAN_EDITED',
    'HYBRID'
);

CREATE TYPE verification_status_enum AS ENUM (
    'PENDING',
    'VERIFIED',
    'UNVERIFIED',
    'DISPUTED',
    'REQUIRES_REVIEW'
);

CREATE TYPE video_status_enum AS ENUM (
    'NOT_STARTED',
    'QUEUED',
    'RENDERING',
    'COMPLETED',
    'FAILED'
);

CREATE TYPE hitl_status_enum AS ENUM (
    'NOT_REQUIRED',
    'PENDING',
    'IN_REVIEW',
    'APPROVED',
    'REJECTED'
);

CREATE TYPE moderation_status_enum AS ENUM (
    'PENDING',
    'IN_REVIEW',
    'APPROVED',
    'REJECTED',
    'REQUIRES_EDIT'
);

CREATE TYPE video_job_status_enum AS ENUM (
    'QUEUED',
    'RENDERING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

-- ============================================================================
-- PUBLISHERS TABLE
-- ============================================================================

CREATE TABLE publishers (
    id SERIAL PRIMARY KEY,

    -- Domain identifier
    domain VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(500),
    description TEXT,

    -- Compliance
    tdm_opt_out BOOLEAN DEFAULT FALSE NOT NULL,
    robots_txt_status VARCHAR(50) DEFAULT 'unknown',
    compliance_last_checked TIMESTAMP,

    -- Trust scoring
    trust_score INTEGER DEFAULT 50 NOT NULL CHECK (trust_score >= 0 AND trust_score <= 100),
    credibility_rating credibility_rating_enum DEFAULT 'UNKNOWN' NOT NULL,

    -- Nutrition label (JSONB)
    nutrition_label JSONB,

    -- Statistics
    articles_published_count INTEGER DEFAULT 0,
    articles_verified_count INTEGER DEFAULT 0,
    articles_rejected_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    last_article_published TIMESTAMP
);

COMMENT ON TABLE publishers IS 'Publisher trust scores and compliance tracking';
COMMENT ON COLUMN publishers.tdm_opt_out IS 'Text/Data Mining opt-out (robots.txt/noai)';
COMMENT ON COLUMN publishers.trust_score IS 'Trust score 0-100, default 50';
COMMENT ON COLUMN publishers.nutrition_label IS 'Structured transparency data';

-- Indexes
CREATE INDEX idx_publisher_domain ON publishers(domain);
CREATE INDEX idx_publisher_trust_score ON publishers(trust_score);
CREATE INDEX idx_publisher_tdm_opt_out ON publishers(tdm_opt_out);

-- ============================================================================
-- ARTICLES TABLE — Trust columns added to existing articles table
-- ============================================================================
-- NOTE: The articles table is created in init.sql (UUID-based primary key).
-- This migration adds trust/compliance columns to the existing table instead
-- of creating a duplicate table definition.
-- ============================================================================

ALTER TABLE articles ADD COLUMN IF NOT EXISTS summary_text TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS compliance_check_passed BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS compliance_skip_reason VARCHAR(255);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS compliance_checked_at TIMESTAMP;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS provenance JSONB;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS trust_score_cache INTEGER CHECK (trust_score_cache >= 0 AND trust_score_cache <= 100);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS video_url VARCHAR(2048);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS hitl_status VARCHAR(20) DEFAULT 'NOT_REQUIRED';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS hitl_assigned_to VARCHAR(255);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS hitl_reviewed_at TIMESTAMP;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS published BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_at_platform TIMESTAMP;

-- Indexes (IF NOT EXISTS to avoid errors on re-run)
CREATE INDEX IF NOT EXISTS idx_article_trust_score ON articles(trust_score_cache);
CREATE INDEX IF NOT EXISTS idx_article_hitl_status ON articles(hitl_status);
CREATE INDEX IF NOT EXISTS idx_article_compliance ON articles(compliance_check_passed);
CREATE INDEX IF NOT EXISTS idx_article_published ON articles(published, published_at_platform);

-- ============================================================================
-- MODERATION QUEUE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS moderation_queue (
    id SERIAL PRIMARY KEY,

    -- Article relationship (UUID FK matching init.sql articles table)
    article_id UUID REFERENCES articles(article_id) ON DELETE CASCADE,

    -- Status
    status moderation_status_enum DEFAULT 'PENDING' NOT NULL,
    priority INTEGER DEFAULT 0 NOT NULL,

    -- Assignment
    assigned_to VARCHAR(255),
    assigned_at TIMESTAMP,

    -- Review
    reviewer VARCHAR(255),
    reviewed_at TIMESTAMP,

    -- Feedback
    feedback TEXT,
    rejection_reason VARCHAR(255),

    -- Edits (JSONB array)
    edits JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE moderation_queue IS 'HITL moderation queue for human review';
COMMENT ON COLUMN moderation_queue.priority IS 'Higher = more urgent';
COMMENT ON COLUMN moderation_queue.edits IS 'List of edits made by reviewer';

-- Indexes
CREATE INDEX idx_moderation_article_id ON moderation_queue(article_id);
CREATE INDEX idx_moderation_status_priority ON moderation_queue(status, priority);
CREATE INDEX idx_moderation_assigned ON moderation_queue(assigned_to, status);

-- ============================================================================
-- VIDEO JOBS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS video_jobs (
    id SERIAL PRIMARY KEY,

    -- Article relationship (UUID FK matching init.sql articles table)
    article_id UUID REFERENCES articles(article_id) ON DELETE CASCADE,

    -- Job tracking
    job_id VARCHAR(255) UNIQUE,
    status video_job_status_enum DEFAULT 'QUEUED' NOT NULL,

    -- Rendering
    render_provider VARCHAR(50) DEFAULT 'remotion' NOT NULL,

    -- Metadata
    output_url VARCHAR(2048),
    duration_ms INTEGER,
    resolution VARCHAR(20) DEFAULT '1920x1080',
    format VARCHAR(10) DEFAULT 'mp4',

    -- Cost tracking
    cost_cents INTEGER,
    render_time_seconds INTEGER,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Assets (JSONB)
    assets JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE video_jobs IS 'Video rendering job tracking';
COMMENT ON COLUMN video_jobs.render_provider IS 'Video rendering provider (remotion, etc.)';
COMMENT ON COLUMN video_jobs.cost_cents IS 'Rendering cost in cents (USD)';
COMMENT ON COLUMN video_jobs.assets IS 'TTS audio, Pexels assets used';

-- Indexes
CREATE INDEX idx_video_job_article_id ON video_jobs(article_id);
CREATE INDEX idx_video_job_id ON video_jobs(job_id);
CREATE INDEX idx_video_job_status ON video_jobs(status);
CREATE INDEX idx_video_job_article_status ON video_jobs(article_id, status);

-- ============================================================================
-- TRIGGERS (auto-update updated_at)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_publishers_updated_at BEFORE UPDATE ON publishers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_articles_updated_at BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_moderation_queue_updated_at BEFORE UPDATE ON moderation_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_jobs_updated_at BEFORE UPDATE ON video_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SAMPLE DATA (for development)
-- ============================================================================

-- Sample publishers
INSERT INTO publishers (domain, name, trust_score, credibility_rating, tdm_opt_out, nutrition_label)
VALUES
    ('bbc.com', 'BBC News', 90, 'HIGH', FALSE, '{"fact_check_ratio": 0.95, "transparency_score": 0.9}'),
    ('reuters.com', 'Reuters', 95, 'VERIFIED', FALSE, '{"fact_check_ratio": 0.98, "transparency_score": 0.95}'),
    ('apnews.com', 'Associated Press', 92, 'HIGH', FALSE, '{"fact_check_ratio": 0.96, "transparency_score": 0.92}');

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO climatenews_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO climatenews_app;
