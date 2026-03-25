-- Migration 007: Add article conversations table for Q&A feature
-- Stores conversation threads per article for the expandable Q&A component

CREATE TABLE IF NOT EXISTS article_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    user_id UUID,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    context_used TEXT[],
    model_used VARCHAR(100) DEFAULT 'claude-3-5-sonnet-20240620',
    confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_article ON article_conversations(article_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON article_conversations(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_created ON article_conversations(created_at DESC);

COMMENT ON TABLE article_conversations IS 'Stores Q&A conversations per article for the expandable analysis feature';
