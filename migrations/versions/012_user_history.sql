-- =============================================================================
-- 012: User history tables — reading history, bookmarks, search history
-- Enables personalized dashboards, "continue reading", and search analytics.
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < migrations/versions/012_user_history.sql
-- =============================================================================

BEGIN;

INSERT INTO schema_migrations (version, description)
VALUES (12, '012_user_history.sql - reading history, bookmarks, search history')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- READING_HISTORY — tracks every article read per user per day
-- =============================================================================
CREATE TABLE IF NOT EXISTS reading_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_duration_seconds INT,                -- time spent reading (client-reported)
    scroll_depth_pct INT CHECK (scroll_depth_pct >= 0 AND scroll_depth_pct <= 100),

    -- One row per user+article+calendar-day to avoid duplicate spam
    CONSTRAINT uq_reading_history_user_article_day
        UNIQUE (user_id, article_id, (read_at::date))
);

-- Fast lookups: "recent reads for user X" ordered by time
CREATE INDEX IF NOT EXISTS idx_reading_history_user_time
    ON reading_history (user_id, read_at DESC);

-- Analytics: which articles are read most?
CREATE INDEX IF NOT EXISTS idx_reading_history_article
    ON reading_history (article_id, read_at DESC);

-- =============================================================================
-- BOOKMARKS — saved articles with optional folders and notes
-- Extends the simpler user_bookmarks from migration 009 with folder support.
-- Uses a different table name to avoid conflicts.
-- =============================================================================
CREATE TABLE IF NOT EXISTS bookmarks (
    bookmark_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    folder VARCHAR(100) NOT NULL DEFAULT 'default',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_bookmarks_user_article UNIQUE (user_id, article_id)
);

-- "Show me all bookmarks in folder X for user Y"
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_folder
    ON bookmarks (user_id, folder, created_at DESC);

-- =============================================================================
-- SEARCH_HISTORY — logged queries for autocomplete and analytics
-- =============================================================================
CREATE TABLE IF NOT EXISTS search_history (
    search_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    filters JSONB DEFAULT '{}'::jsonb,         -- country, date range, category, etc.
    result_count INT,                          -- how many hits were returned
    searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- "Recent searches for user X" — powers autocomplete & search suggestions
CREATE INDEX IF NOT EXISTS idx_search_history_user_time
    ON search_history (user_id, searched_at DESC);

-- Analytics: most popular queries across all users
CREATE INDEX IF NOT EXISTS idx_search_history_query
    ON search_history USING GIN (to_tsvector('english', query));

DO $$ BEGIN RAISE NOTICE 'Migration 012 applied successfully — user history tables created.'; END $$;

COMMIT;
