-- Migration 014: Query subscriptions for scheduled/interval-based article queries

CREATE TABLE IF NOT EXISTS query_subscriptions (
    subscription_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}',
    frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
    notify_email BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_subs_user ON query_subscriptions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_query_subs_frequency ON query_subscriptions(frequency, is_active, last_run_at);
