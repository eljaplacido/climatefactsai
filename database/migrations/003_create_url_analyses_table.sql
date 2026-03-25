-- Migration 003: Create url_analyses table for user-submitted URL analysis
-- Date: 2025-12-20
-- Purpose: Support POST /api/analyze-url endpoint for on-demand fact-checking

CREATE TABLE IF NOT EXISTS url_analyses (
    -- Primary identifiers
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),  -- Optional (nullable for non-authenticated requests)

    -- URL information
    submitted_url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for deduplication
    source_domain VARCHAR(255),

    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    priority VARCHAR(20) DEFAULT 'normal',  -- normal, high

    -- Content extraction
    title TEXT,
    source_name VARCHAR(255),
    extracted_text TEXT,
    language_code VARCHAR(10),
    published_date TIMESTAMPTZ,

    -- Analysis results
    extracted_claims JSONB,  -- List of claims extracted
    fact_checks JSONB,       -- Fact-check results
    evidence JSONB,          -- Supporting evidence

    -- Credibility assessment
    reliability_score INTEGER,  -- 0-100 score
    overall_credibility VARCHAR(20),  -- HIGH, MEDIUM, LOW

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_time_ms INTEGER,  -- Total processing time in milliseconds

    -- Error handling
    error_message TEXT,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT valid_priority CHECK (priority IN ('normal', 'high')),
    CONSTRAINT valid_credibility CHECK (overall_credibility IS NULL OR overall_credibility IN ('HIGH', 'MEDIUM', 'LOW'))
);

-- Indexes for performance
CREATE INDEX idx_url_analyses_user_id ON url_analyses(user_id);
CREATE INDEX idx_url_analyses_status ON url_analyses(status);
CREATE INDEX idx_url_analyses_url_hash ON url_analyses(url_hash);
CREATE INDEX idx_url_analyses_created_at ON url_analyses(created_at DESC);

-- Composite index for user history queries
CREATE INDEX idx_url_analyses_user_created ON url_analyses(user_id, created_at DESC);

-- Comments
COMMENT ON TABLE url_analyses IS 'Tracks user-submitted URLs for on-demand fact-checking analysis';
COMMENT ON COLUMN url_analyses.url_hash IS 'SHA-256 hash of URL for deduplication (prevents analyzing same URL repeatedly)';
COMMENT ON COLUMN url_analyses.status IS 'Current state: pending (queued), processing (in progress), completed (done), failed (error)';
COMMENT ON COLUMN url_analyses.extracted_claims IS 'JSON array of claims extracted from article text';
COMMENT ON COLUMN url_analyses.fact_checks IS 'JSON array of fact-check results with verdicts and confidence scores';
COMMENT ON COLUMN url_analyses.evidence IS 'JSON object containing supporting evidence from external sources (ClimateCheck, NOAA, NASA)';
COMMENT ON COLUMN url_analyses.processing_time_ms IS 'Total time taken for analysis in milliseconds (for performance monitoring)';
