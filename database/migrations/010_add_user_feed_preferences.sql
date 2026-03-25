-- Migration 010: Add user feed preferences for automatic feed updates
-- Phase 2A of CliLens.AI Consumer Release

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

-- Index for looking up user preferences
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_feed_preferences_user
    ON user_feed_preferences (user_id);

-- Index for scheduler queries
CREATE INDEX IF NOT EXISTS idx_user_feed_preferences_frequency
    ON user_feed_preferences (update_frequency, last_updated_at);

COMMENT ON TABLE user_feed_preferences IS
    'Per-user feed configuration for automatic climate news discovery';
COMMENT ON COLUMN user_feed_preferences.update_frequency IS
    'Update frequency: daily, twice_daily, four_times_daily, hourly';
COMMENT ON COLUMN user_feed_preferences.country_codes IS
    'Array of ISO 3166-1 alpha-2 country codes the user subscribes to';
