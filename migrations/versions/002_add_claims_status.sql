-- Migration: Add claims_status tracking for articles
-- Date: 2025-12-18
-- Phase: Claims Processing Enhancement
-- Reference: docs/CURRENT_STATE.md lines 206-224

-- ============================================================================
-- ENUM TYPE FOR CLAIMS STATUS
-- ============================================================================

CREATE TYPE claims_status_enum AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed'
);

COMMENT ON TYPE claims_status_enum IS 'Tracks the status of claims extraction and verification process';

-- ============================================================================
-- ADD CLAIMS_STATUS COLUMN TO ARTICLES TABLE
-- ============================================================================

-- Add claims_status column to existing articles table
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS claims_status VARCHAR(50) DEFAULT 'pending';

COMMENT ON COLUMN articles.claims_status IS 'Status of claims extraction: pending, processing, completed, failed';

-- Add claims_error_message for failed cases
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS claims_error_message TEXT;

COMMENT ON COLUMN articles.claims_error_message IS 'Error message if claims extraction failed';

-- Add claims_processed_at timestamp
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS claims_processed_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN articles.claims_processed_at IS 'Timestamp when claims extraction was completed or failed';

-- ============================================================================
-- CREATE INDEX FOR EFFICIENT FILTERING
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_articles_claims_status
ON articles(claims_status);

COMMENT ON INDEX idx_articles_claims_status IS 'Index for filtering articles by claims processing status';

-- Create composite index for common queries (status + count)
CREATE INDEX IF NOT EXISTS idx_articles_claims_status_count
ON articles(claims_status, claims_count);

COMMENT ON INDEX idx_articles_claims_status_count IS 'Index for queries filtering by status and checking claim counts';

-- ============================================================================
-- UPDATE EXISTING ARTICLES
-- ============================================================================

-- Set status based on existing data
UPDATE articles
SET claims_status = CASE
    WHEN claims_count > 0 THEN 'completed'
    WHEN claims_count = 0 AND created_at < NOW() - INTERVAL '1 hour' THEN 'pending'
    ELSE 'pending'
END
WHERE claims_status IS NULL;

-- ============================================================================
-- ADD HELPER FUNCTION
-- ============================================================================

-- Function to compute claims_available status
CREATE OR REPLACE FUNCTION article_has_claims_available(
    p_claims_status VARCHAR(50),
    p_claims_count INTEGER
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN p_claims_status = 'completed' AND p_claims_count > 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION article_has_claims_available IS 'Determines if an article has successfully extracted claims available';

-- ============================================================================
-- CREATE VIEW FOR ARTICLES WITH CLAIMS STATUS
-- ============================================================================

CREATE OR REPLACE VIEW articles_claims_status_view AS
SELECT
    a.article_id,
    a.title,
    a.url,
    a.claims_status,
    a.claims_count,
    a.verified_claims_count,
    a.claims_error_message,
    a.claims_processed_at,
    article_has_claims_available(a.claims_status, a.claims_count) as claims_available,
    CASE
        WHEN a.claims_status = 'completed' THEN '✓ Completed'
        WHEN a.claims_status = 'processing' THEN '⏳ Processing'
        WHEN a.claims_status = 'failed' THEN '✗ Failed'
        ELSE '⏸ Pending'
    END as status_display,
    a.created_at,
    a.updated_at
FROM articles a
ORDER BY a.created_at DESC;

COMMENT ON VIEW articles_claims_status_view IS 'View showing articles with computed claims availability status';

-- ============================================================================
-- MIGRATION VERIFICATION
-- ============================================================================

-- Verify column was added
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'articles'
        AND column_name = 'claims_status'
    ) THEN
        RAISE EXCEPTION 'Migration failed: claims_status column not found';
    END IF;

    RAISE NOTICE 'Migration completed successfully: claims_status tracking added';
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT (commented out, use if needed)
-- ============================================================================

/*
-- To rollback this migration:

DROP VIEW IF EXISTS articles_claims_status_view;
DROP FUNCTION IF EXISTS article_has_claims_available(VARCHAR, INTEGER);
DROP INDEX IF EXISTS idx_articles_claims_status_count;
DROP INDEX IF EXISTS idx_articles_claims_status;

ALTER TABLE articles DROP COLUMN IF EXISTS claims_processed_at;
ALTER TABLE articles DROP COLUMN IF EXISTS claims_error_message;
ALTER TABLE articles DROP COLUMN IF EXISTS claims_status;

DROP TYPE IF EXISTS claims_status_enum;
*/
