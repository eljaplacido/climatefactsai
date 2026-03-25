-- =============================================================================
-- 009: Saved queries, chat sessions, and user activity tables
-- Adds: user_saved_queries, chat_sessions, user_activity, user_bookmarks, saved_analyses
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < migrations/versions/009_add_saved_queries_and_chat.sql
-- =============================================================================

BEGIN;

-- =============================================================================
-- USER_SAVED_QUERIES — Recurring themed queries with scheduling
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_saved_queries (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    query_text TEXT NOT NULL,
    theme VARCHAR(100),
    country_codes TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{}',
    notification_interval VARCHAR(30) DEFAULT 'daily',
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_result_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_queries_user ON user_saved_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_queries_next_run ON user_saved_queries(next_run_at) WHERE is_active = true;

-- =============================================================================
-- CHAT_SESSIONS — General non-article-specific conversations
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    title VARCHAR(500),
    session_type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    sources_used TEXT[] DEFAULT '{}',
    article_ids TEXT[] DEFAULT '{}',
    confidence REAL DEFAULT 0.0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);

-- =============================================================================
-- USER_ACTIVITY — Flexible activity/event tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_activity (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    activity_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity(activity_type);

-- =============================================================================
-- USER_BOOKMARKS — Article bookmarks
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_bookmarks (
    bookmark_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    article_id UUID NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_bookmark UNIQUE (user_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user ON user_bookmarks(user_id);

-- =============================================================================
-- SAVED_ANALYSES — User-saved analysis reports
-- =============================================================================
CREATE TABLE IF NOT EXISTS saved_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    analysis_type VARCHAR(100) NOT NULL,
    content JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_analyses_user ON saved_analyses(user_id);

DO $$ BEGIN RAISE NOTICE 'Migration 009 applied successfully.'; END $$;

COMMIT;
