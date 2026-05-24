-- Migration 032: AOI (Area of Interest) alert subscriptions
--
-- Phase 3 (2026-05-23) — implements MH5 from the competitive UX audit
-- (Global Forest Watch pattern). Authenticated users on Basic+ tier
-- can subscribe to threshold alerts for a country + variable +
-- comparison + value combination. A Celery beat task polls the
-- corresponding country_indicators rows hourly; when a threshold is
-- crossed, an email is dispatched and `last_fired_at` is updated to
-- prevent re-firing on the same crossing.
--
-- Schema design notes:
--   - country_code is the scoping primitive (no polygon AOI yet — that's
--     Phase 4 scope). Users pick a country from the existing 198-country
--     reference catalogue.
--   - variable is the indicator slug from country_indicators.indicator_id
--     (e.g. 'co2_emissions_per_capita', 'renewable_share_pct',
--     'temperature_anomaly_c').
--   - comparison: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' — matches the
--     subset our threshold-check logic supports.
--   - threshold: the numeric value the variable is compared against.
--   - delivery_channel: 'email' for v1; 'push' + 'slack' Phase 4.
--   - active: soft delete — flip to false rather than hard-delete so
--     historical fire records keep their FK target.
--   - last_fired_at: nullable; when present, the threshold-check loop
--     uses it to debounce re-firing (1 fire per crossing).
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS aoi_subscriptions (
    subscription_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    -- Scope
    country_code         CHAR(2) NOT NULL,
    variable             VARCHAR(64) NOT NULL,
    -- Threshold rule
    comparison           VARCHAR(4) NOT NULL,
    threshold            DOUBLE PRECISION NOT NULL,
    -- Delivery
    delivery_channel     VARCHAR(16) NOT NULL DEFAULT 'email',
    delivery_target      TEXT,             -- nullable; defaults to user.email
    -- Lifecycle
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    last_fired_at        TIMESTAMPTZ,
    last_observed_value  DOUBLE PRECISION,
    fire_count           INTEGER NOT NULL DEFAULT 0,
    label                VARCHAR(200),     -- human-readable name e.g. "Germany emissions over 8 t/cap"
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT aoi_comparison_valid CHECK (comparison IN ('gt','gte','lt','lte','eq')),
    CONSTRAINT aoi_delivery_channel_valid CHECK (delivery_channel IN ('email','push','slack'))
);

-- Fast lookup of a user's active subscriptions (dashboard list view).
CREATE INDEX IF NOT EXISTS idx_aoi_subscriptions_user_active
    ON aoi_subscriptions (user_id, active)
    WHERE active = TRUE;

-- The poll task scans all-active filtered by variable so it can batch
-- one indicator pull per variable, then loop the matching subscriptions.
CREATE INDEX IF NOT EXISTS idx_aoi_subscriptions_variable_active
    ON aoi_subscriptions (variable, active)
    WHERE active = TRUE;

COMMENT ON TABLE aoi_subscriptions IS
    'Area-of-Interest alert subscriptions (Phase 3 MH5). One row per user × country × variable × threshold.';
COMMENT ON COLUMN aoi_subscriptions.comparison IS
    'How the observed value is compared to threshold: gt|gte|lt|lte|eq.';
COMMENT ON COLUMN aoi_subscriptions.last_fired_at IS
    'When the threshold was last crossed and an alert was dispatched. NULL means never. Used to debounce re-firing on the same crossing.';
COMMENT ON COLUMN aoi_subscriptions.last_observed_value IS
    'Most recent observed value of `variable` for `country_code`. The poll task updates this on every check.';
