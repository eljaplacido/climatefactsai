-- Migration 010: User source registration for premium RSS feed management
-- Date: 2026-03-04
-- Phase: 1 - CliLens.AI Platform (User Source Registration)
--
-- Allows authenticated users to register custom RSS/Atom feed sources.
-- Source limits are enforced at the API layer by subscription tier:
--   freemium     → 0 (no custom sources)
--   standard     → 3
--   professional → 20
--   enterprise   → unlimited
--
-- The `approved` flag is reserved for future moderation workflows.
-- Sources are deduplicated per user via a UNIQUE(user_id, source_url) constraint.

-- ============================================================================
-- TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_source_registrations (
    registration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source_name VARCHAR(255) NOT NULL,
    source_url TEXT NOT NULL,
    feed_type VARCHAR(20) DEFAULT 'rss',
    reliability_tier VARCHAR(20) DEFAULT 'public',
    country_code CHAR(2),
    is_active BOOLEAN DEFAULT true,
    approved BOOLEAN DEFAULT false,
    last_fetched_at TIMESTAMPTZ,
    fetch_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source_url)
);

COMMENT ON TABLE user_source_registrations IS
    'User-registered custom RSS/Atom feed sources. '
    'Tier-gated: freemium=0, standard=3, professional=20, enterprise=unlimited.';

COMMENT ON COLUMN user_source_registrations.approved IS
    'Reserved for future admin moderation. Defaults to false; '
    'API currently allows all validated registrations regardless of this flag.';

COMMENT ON COLUMN user_source_registrations.feed_type IS
    'Feed format hint. Expected values: rss, atom. Default: rss.';

COMMENT ON COLUMN user_source_registrations.reliability_tier IS
    'Source reliability classification used in article filtering. '
    'Valid values: public, research, scientific.';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_user_sources_user_id
    ON user_source_registrations(user_id);

COMMENT ON INDEX idx_user_sources_user_id IS
    'Supports fast per-user source listing queries.';

CREATE INDEX IF NOT EXISTS idx_user_sources_active
    ON user_source_registrations(is_active, approved);

COMMENT ON INDEX idx_user_sources_active IS
    'Supports filtering active/approved sources for feed ingestion workers.';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'user_source_registrations'
    ) THEN
        RAISE EXCEPTION
            'Migration 010 failed: user_source_registrations table not found.';
    END IF;

    RAISE NOTICE
        'Migration 010 completed: user_source_registrations table created and indexed.';
END $$;

-- ============================================================================
-- ROLLBACK (commented out — run manually if needed)
-- ============================================================================

/*
DROP INDEX IF EXISTS idx_user_sources_active;
DROP INDEX IF EXISTS idx_user_sources_user_id;
DROP TABLE IF EXISTS user_source_registrations;
*/
