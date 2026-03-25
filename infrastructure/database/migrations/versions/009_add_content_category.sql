-- Migration 009: Add content_category column to articles table
-- Date: 2026-03-04
-- Phase: 0 - CliLens.AI Platform (Category Filter)
--
-- Adds a content_category column used by the feed filter UI to narrow articles
-- to a single thematic domain. The backfill assigns categories based on keyword
-- matching against the article headline. NULL is allowed so that rows added
-- before the application layer starts populating the column remain queryable
-- without artificial category assignment until they are re-processed.
--
-- Valid categories:
--   climate_science    (default / fallback)
--   sustainability
--   circular_economy
--   green_transition
--   localized_forecast
--   policy

-- ============================================================================
-- ADD COLUMN
-- ============================================================================

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS content_category VARCHAR(50) DEFAULT NULL;

COMMENT ON COLUMN articles.content_category IS
    'Thematic category used for feed filtering. '
    'Valid values: climate_science, sustainability, circular_economy, '
    'green_transition, localized_forecast, policy. NULL = uncategorised.';

-- ============================================================================
-- INDEX
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_articles_content_category
    ON articles(content_category);

COMMENT ON INDEX idx_articles_content_category IS
    'Supports fast WHERE content_category = $1 feed-filter queries.';

-- ============================================================================
-- BACKFILL EXISTING ROWS
--
-- Priority order (first match wins, evaluated top-to-bottom via CASE WHEN):
--   1. policy           — regulatory / geopolitical keywords
--   2. circular_economy — waste / recycling keywords
--   3. localized_forecast — weather event keywords
--   4. green_transition — energy-transition keywords
--   5. sustainability   — ESG / SDG / biodiversity keywords
--   6. climate_science  — default / fallback
--
-- The LOWER() normalisation makes all comparisons case-insensitive.
-- Matches against title, excerpt, and tags array (cast to text).
-- ============================================================================

UPDATE articles
SET content_category = CASE

    -- 1. Policy
    WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(tags::text, '')) SIMILAR TO
         '%(policy|regulation|legislation|cop[[:space:][:digit:]]|treaty|carbon tax|emissions trading)%'
        THEN 'policy'

    -- 2. Circular economy
    WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(tags::text, '')) SIMILAR TO
         '%(circular|recycling|recycled|recycle|waste)%'
        THEN 'circular_economy'

    -- 3. Localised forecast / weather events
    WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(tags::text, '')) SIMILAR TO
         '%(forecast|weather|heatwave|heat wave|storm|flood|flooding|flooded|drought|wildfire)%'
        THEN 'localized_forecast'

    -- 4. Green transition / energy
    WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(tags::text, '')) SIMILAR TO
         '%(transition|renewable|solar|wind power|electric vehicle| ev |hydrogen|net zero|decarboni)%'
        THEN 'green_transition'

    -- 5. Sustainability
    WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(excerpt, '') || ' ' || COALESCE(tags::text, '')) SIMILAR TO
         '%(sustainable|sustainability|esg|sdg|biodiversity|ecosystem)%'
        THEN 'sustainability'

    -- 6. Default fallback
    ELSE 'climate_science'

END
WHERE content_category IS NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name  = 'articles'
          AND column_name = 'content_category'
    ) THEN
        RAISE EXCEPTION
            'Migration 009 failed: content_category column not found in articles table.';
    END IF;

    RAISE NOTICE
        'Migration 009 completed: content_category added, indexed, and backfilled.';
END $$;

-- ============================================================================
-- ROLLBACK (commented out — run manually if needed)
-- ============================================================================

/*
DROP INDEX IF EXISTS idx_articles_content_category;
ALTER TABLE articles DROP COLUMN IF EXISTS content_category;
*/
