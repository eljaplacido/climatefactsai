-- Migration 013: OAuth support + User activity tracking
-- Adds OAuth provider fields to users table and creates activity/bookmarks tables

-- OAuth support: add provider fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) DEFAULT 'local';
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_user_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_refresh_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_avatar_url TEXT;

-- Create index for OAuth lookups
CREATE INDEX IF NOT EXISTS idx_users_provider ON users(auth_provider, provider_user_id);

-- User activity / history tracking
CREATE TABLE IF NOT EXISTS user_activity (
    activity_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    activity_data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity(user_id, activity_type, created_at DESC);

-- Saved analyses / reports
CREATE TABLE IF NOT EXISTS saved_analyses (
    analysis_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_analyses_user ON saved_analyses(user_id, created_at DESC);

-- User bookmarks
CREATE TABLE IF NOT EXISTS user_bookmarks (
    bookmark_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(article_id) ON DELETE CASCADE,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user ON user_bookmarks(user_id, created_at DESC);
