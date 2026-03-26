-- =============================================================================
-- 011: Enriched article content columns
-- Adds AI-enriched excerpt, climate context summary, and enrichment metadata
-- to the articles table for richer card displays and agentic insights.
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < migrations/versions/011_enriched_content.sql
-- =============================================================================

BEGIN;

INSERT INTO schema_migrations (version, description)
VALUES (11, '011_enriched_content.sql - article enrichment columns')
ON CONFLICT (version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 1. Add enrichment columns to articles
-- ---------------------------------------------------------------------------

-- Full-paragraph AI-generated excerpt with insights (replaces short excerpt)
ALTER TABLE articles ADD COLUMN IF NOT EXISTS enriched_excerpt TEXT;

-- Localized climate/weather context matching the article's geography and topic
ALTER TABLE articles ADD COLUMN IF NOT EXISTS climate_context_summary TEXT;

-- Flexible metadata: model version, token count, enrichment source, etc.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS enrichment_metadata JSONB DEFAULT '{}';

-- Timestamp tracking when enrichment was last performed
ALTER TABLE articles ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 2. Indexes
-- ---------------------------------------------------------------------------

-- Partial index for tracking enrichment progress (find un-enriched articles)
CREATE INDEX IF NOT EXISTS idx_articles_enriched_at
    ON articles (enriched_at)
    WHERE enriched_at IS NOT NULL;

-- GIN index on enrichment metadata for querying by model/source
CREATE INDEX IF NOT EXISTS idx_articles_enrichment_metadata
    ON articles USING GIN (enrichment_metadata);

-- ---------------------------------------------------------------------------
-- 3. Comments
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN articles.enriched_excerpt
    IS 'AI-generated full-paragraph excerpt with climate insights and context';

COMMENT ON COLUMN articles.climate_context_summary
    IS 'Localized weather/climate context matching article geography and topic';

COMMENT ON COLUMN articles.enrichment_metadata
    IS 'JSONB: model_version, token_count, enrichment_source, processing_time_ms';

COMMENT ON COLUMN articles.enriched_at
    IS 'Timestamp of last enrichment run; NULL means not yet enriched';

DO $$ BEGIN RAISE NOTICE 'Migration 011 applied successfully — enriched content columns added.'; END $$;

COMMIT;
