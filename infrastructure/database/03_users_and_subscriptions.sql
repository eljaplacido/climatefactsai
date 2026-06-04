-- =============================================================================
-- USER MANAGEMENT AND SUBSCRIPTION SYSTEM
-- =============================================================================
-- This script creates tables for:
-- 1. Users (authentication and profile)
-- 2. Subscriptions (freemium/premium tiers)
-- 3. Usage tracking (rate limiting and analytics)
-- 4. User preferences (personalization)
-- 5. URL analyses (on-demand fact-checking)
-- =============================================================================

-- =============================================================================
-- USERS TABLE
-- Core user authentication and profile information
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- Profile
    full_name VARCHAR(255),
    avatar_url TEXT,

    -- Subscription
    subscription_tier VARCHAR(20) DEFAULT 'freemium', -- freemium, basic, professional, enterprise

    -- Account status
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP WITH TIME ZONE,

    -- Password reset
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP WITH TIME ZONE,

    -- Security
    last_login_at TIMESTAMP WITH TIME ZONE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_tier ON users(subscription_tier);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- =============================================================================
-- SUBSCRIPTIONS TABLE
-- Manages paid subscriptions with Stripe integration
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Subscription details
    tier VARCHAR(20) NOT NULL, -- freemium, basic, professional, enterprise
    status VARCHAR(20) DEFAULT 'active', -- active, cancelled, expired, trial, past_due

    -- Stripe integration
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    stripe_price_id VARCHAR(255),

    -- Billing cycle
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,

    -- Trial
    trial_starts_at TIMESTAMP WITH TIME ZONE,
    trial_ends_at TIMESTAMP WITH TIME ZONE,

    -- Cancellation
    cancel_at_period_end BOOLEAN DEFAULT false,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancellation_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period_end ON subscriptions(current_period_end);

-- =============================================================================
-- USER_USAGE TABLE
-- Tracks usage for rate limiting and analytics
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_usage (
    usage_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Usage type
    usage_type VARCHAR(50) NOT NULL, -- article_view, url_analysis, api_call, export, search

    -- Resource information
    resource_id VARCHAR(255), -- article_id, analysis_id, etc.
    resource_url TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- IP and user agent (for abuse detection)
    ip_address INET,
    user_agent TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_user_date ON user_usage(user_id, created_at DESC);
CREATE INDEX idx_usage_type ON user_usage(usage_type);
CREATE INDEX idx_usage_created_at ON user_usage(created_at DESC);

-- Composite index for daily usage queries
CREATE INDEX idx_usage_user_type_date ON user_usage(user_id, usage_type, DATE(created_at));

-- =============================================================================
-- USER_PREFERENCES TABLE
-- Stores user preferences and personalization settings
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,

    -- Content preferences
    preferred_countries TEXT[] DEFAULT '{}', -- Array of country codes
    notification_topics TEXT[] DEFAULT '{}', -- Climate topics for alerts
    preferred_sources TEXT[] DEFAULT '{}', -- Preferred news sources

    -- Notification settings
    email_notifications BOOLEAN DEFAULT true,
    daily_digest BOOLEAN DEFAULT false,
    weekly_summary BOOLEAN DEFAULT false,
    breaking_news_alerts BOOLEAN DEFAULT false,

    -- Saved searches (JSON array of search objects)
    saved_searches JSONB DEFAULT '[]'::jsonb,

    -- UI preferences
    theme VARCHAR(20) DEFAULT 'light', -- light, dark, auto
    language_code CHAR(2) DEFAULT 'en',
    articles_per_page INTEGER DEFAULT 20,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_preferences_user ON user_preferences(user_id);

-- =============================================================================
-- URL_ANALYSES TABLE
-- Stores on-demand URL fact-checking analyses
-- =============================================================================

CREATE TABLE IF NOT EXISTS url_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Submitted URL
    submitted_url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for deduplication

    -- Processing status
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed

    -- Source information
    source_name VARCHAR(255),
    source_domain VARCHAR(255),
    published_date TIMESTAMP WITH TIME ZONE,

    -- Content
    title TEXT,
    extracted_text TEXT,
    language_code CHAR(2),

    -- Analysis results
    source_credibility_score INTEGER CHECK (source_credibility_score >= 0 AND source_credibility_score <= 100),
    overall_credibility VARCHAR(20), -- HIGH, MEDIUM, LOW, MIXED
    reliability_score INTEGER CHECK (reliability_score >= 0 AND reliability_score <= 100),

    -- Extracted claims and fact checks (JSON arrays)
    extracted_claims JSONB DEFAULT '[]'::jsonb,
    fact_checks JSONB DEFAULT '[]'::jsonb,
    evidence JSONB DEFAULT '[]'::jsonb,

    -- Processing metadata
    processing_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,
    error_message TEXT,

    -- Cost tracking
    api_calls_made JSONB DEFAULT '{}'::jsonb,
    estimated_cost_usd DECIMAL(10, 6),

    -- Sharing
    is_public BOOLEAN DEFAULT false,
    share_token VARCHAR(255) UNIQUE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analyses_user ON url_analyses(user_id);
CREATE INDEX idx_analyses_status ON url_analyses(status);
CREATE INDEX idx_analyses_url_hash ON url_analyses(url_hash);
CREATE INDEX idx_analyses_created_at ON url_analyses(created_at DESC);
CREATE INDEX idx_analyses_share_token ON url_analyses(share_token) WHERE share_token IS NOT NULL;

-- =============================================================================
-- API_KEYS TABLE
-- For premium users who want programmatic access
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Key details
    key_hash VARCHAR(255) NOT NULL UNIQUE, -- Hashed API key
    key_prefix VARCHAR(20) NOT NULL, -- First few chars for identification (e.g., "clk_abc123...")
    name VARCHAR(100) NOT NULL, -- User-defined name for the key

    -- Permissions
    scopes TEXT[] DEFAULT '{read:articles}', -- Array of permission scopes

    -- Rate limiting
    rate_limit_per_hour INTEGER DEFAULT 100,
    rate_limit_per_day INTEGER DEFAULT 1000,

    -- Status
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- Expiration
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);

-- =============================================================================
-- NOTIFICATIONS TABLE
-- Stores user notifications (alerts, digests, etc.)
-- =============================================================================

CREATE TABLE IF NOT EXISTS notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Notification details
    type VARCHAR(50) NOT NULL, -- breaking_news, daily_digest, weekly_summary, account_update
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Related resource
    resource_type VARCHAR(50), -- article, analysis, subscription
    resource_id VARCHAR(255),
    resource_url TEXT,

    -- Delivery status
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,

    sent_via_email BOOLEAN DEFAULT false,
    email_sent_at TIMESTAMP WITH TIME ZONE,

    -- Priority
    priority VARCHAR(20) DEFAULT 'normal', -- low, normal, high, urgent

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = false;
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- =============================================================================
-- PAYMENT_HISTORY TABLE
-- Tracks payment transactions for auditing
-- =============================================================================

CREATE TABLE IF NOT EXISTS payment_history (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(subscription_id) ON DELETE SET NULL,

    -- Payment details
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    stripe_invoice_id VARCHAR(255),

    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',

    -- Status
    status VARCHAR(20) NOT NULL, -- succeeded, failed, pending, refunded

    -- Description
    description TEXT,

    -- Stripe hosted invoice link (surfaced by /api/subscription/history)
    invoice_url TEXT,

    -- Timestamps
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_user ON payment_history(user_id);
CREATE INDEX idx_payments_subscription ON payment_history(subscription_id);
CREATE INDEX idx_payments_status ON payment_history(status);
CREATE INDEX idx_payments_created_at ON payment_history(created_at DESC);

-- =============================================================================
-- HELPER VIEWS
-- Useful views for common queries
-- =============================================================================

-- View: Active subscriptions with user info
CREATE OR REPLACE VIEW active_subscriptions_view AS
SELECT
    u.user_id,
    u.email,
    u.full_name,
    u.subscription_tier,
    s.subscription_id,
    s.status,
    s.current_period_start,
    s.current_period_end,
    s.cancel_at_period_end,
    s.stripe_subscription_id
FROM users u
LEFT JOIN subscriptions s ON u.user_id = s.user_id
WHERE s.status IN ('active', 'trialing')
ORDER BY s.current_period_end ASC;

-- View: Daily usage summary per user
CREATE OR REPLACE VIEW daily_usage_summary AS
SELECT
    user_id,
    DATE(created_at) as usage_date,
    usage_type,
    COUNT(*) as usage_count
FROM user_usage
GROUP BY user_id, DATE(created_at), usage_type
ORDER BY usage_date DESC, user_id;

-- View: User analytics with subscription info
CREATE OR REPLACE VIEW user_analytics AS
SELECT
    u.user_id,
    u.email,
    u.full_name,
    u.subscription_tier,
    u.created_at as user_since,
    u.last_login_at,
    s.status as subscription_status,
    COUNT(DISTINCT uu.usage_id) FILTER (WHERE uu.usage_type = 'article_view' AND uu.created_at >= CURRENT_DATE - INTERVAL '30 days') as articles_viewed_30d,
    COUNT(DISTINCT ua.analysis_id) FILTER (WHERE ua.created_at >= CURRENT_DATE - INTERVAL '30 days') as analyses_30d,
    COUNT(DISTINCT n.notification_id) FILTER (WHERE n.is_read = false) as unread_notifications
FROM users u
LEFT JOIN subscriptions s ON u.user_id = s.user_id AND s.status = 'active'
LEFT JOIN user_usage uu ON u.user_id = uu.user_id
LEFT JOIN url_analyses ua ON u.user_id = ua.user_id
LEFT JOIN notifications n ON u.user_id = n.user_id
GROUP BY u.user_id, s.status;

-- =============================================================================
-- TRIGGER FUNCTIONS
-- Automatic updates and validations
-- =============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_url_analyses_updated_at
    BEFORE UPDATE ON url_analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Sync subscription tier to users table
CREATE OR REPLACE FUNCTION sync_subscription_tier()
RETURNS TRIGGER AS $$
BEGIN
    -- Update user's subscription_tier based on active subscription
    IF NEW.status = 'active' THEN
        UPDATE users
        SET subscription_tier = NEW.tier
        WHERE user_id = NEW.user_id;
    ELSIF NEW.status IN ('cancelled', 'expired') THEN
        UPDATE users
        SET subscription_tier = 'freemium'
        WHERE user_id = NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_subscription_tier_trigger
    AFTER INSERT OR UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION sync_subscription_tier();

-- =============================================================================
-- SEED DATA
-- Default freemium subscriptions and demo users
-- =============================================================================

-- Create default freemium subscription tiers (for reference)
-- These will be managed through Stripe in production

-- Example: Create test user (password: "TestPassword123!")
-- Password hash generated with bcrypt
-- In production, this should be done through the registration API
/*
INSERT INTO users (email, password_hash, full_name, email_verified, subscription_tier)
VALUES
    ('demo@clilens.ai', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5aeC8x8yD8kD2', 'Demo User', true, 'freemium')
ON CONFLICT (email) DO NOTHING;

-- Create preferences for demo user
INSERT INTO user_preferences (user_id, preferred_countries)
SELECT user_id, ARRAY['FI', 'SE', 'NO', 'DK', 'DE']
FROM users WHERE email = 'demo@clilens.ai'
ON CONFLICT (user_id) DO NOTHING;
*/

COMMIT;

-- =============================================================================
-- USAGE LIMIT CONSTRAINTS (Stored as constants)
-- =============================================================================

-- Freemium: 5 articles/day, 0 URL analyses/month
-- Basic: 50 articles/day, 5 URL analyses/month
-- Professional: Unlimited articles, 20 URL analyses/month
-- Enterprise: Unlimited everything

-- These limits will be enforced in the application layer (FastAPI middleware)
