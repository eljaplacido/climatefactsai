-- Migration 009: Add content category and enhanced analysis fields to articles
-- Phase 1B of CliLens.AI Consumer Release

-- Add content_category column for article categorisation
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS content_category VARCHAR(50);

-- Add executive_brief for article card previews
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS executive_brief TEXT;

-- Add analysis_article_generated_at timestamp
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS analysis_article_generated_at TIMESTAMPTZ;

-- Index for filtering by category
CREATE INDEX IF NOT EXISTS idx_articles_content_category
    ON articles (content_category)
    WHERE content_category IS NOT NULL;

-- Composite index for category + country filtering
CREATE INDEX IF NOT EXISTS idx_articles_category_country
    ON articles (content_category, country_code)
    WHERE content_category IS NOT NULL;

-- Comment on new columns
COMMENT ON COLUMN articles.content_category IS
    'Content category: climate_science, sustainability, circular_economy, green_transition, localized_forecast, policy';
COMMENT ON COLUMN articles.executive_brief IS
    '2-3 sentence executive brief for card previews';
COMMENT ON COLUMN articles.analysis_article_generated_at IS
    'Timestamp of when the analysis article was last generated';
