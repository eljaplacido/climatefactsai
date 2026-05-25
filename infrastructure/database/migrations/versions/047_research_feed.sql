-- @notolerate
-- Migration 047: research feed — subscriptions + discovered items.
--
-- Deferred audit item #13 (2026-05-25). User asked for "a research
-- analysis feed exactly like the news feed, but just of research and
-- user could choose area, topic to follow about etc." Two new tables:
--
--   research_subscriptions — per-user "follow this topic" rows
--     (user_id, topic, keywords[]). One row per (user, topic).
--     last_polled_at + is_active drive the CrossRef poller.
--
--   research_feed_items — papers discovered by the poller
--     (subscription_id, doi, title, ...). One row per (subscription,
--     doi). Cascade-deleted with the subscription. discovered_at lets
--     the feed UI sort newest-first.
--
-- Both tables idempotent (CREATE IF NOT EXISTS). No data mutation.

CREATE TABLE IF NOT EXISTS research_subscriptions (
    subscription_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    topic              VARCHAR(200) NOT NULL,
    keywords           TEXT[] DEFAULT '{}',
    notification_email BOOLEAN DEFAULT FALSE,
    is_active          BOOLEAN DEFAULT TRUE,
    last_polled_at     TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ,

    CONSTRAINT uq_research_subscription UNIQUE (user_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_research_subs_user_active
    ON research_subscriptions (user_id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_research_subs_poll_due
    ON research_subscriptions (last_polled_at NULLS FIRST)
    WHERE is_active = TRUE;


CREATE TABLE IF NOT EXISTS research_feed_items (
    item_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id  UUID NOT NULL REFERENCES research_subscriptions(subscription_id)
                     ON DELETE CASCADE,
    doi              VARCHAR(255),
    title            TEXT NOT NULL,
    authors          TEXT[] DEFAULT '{}',
    abstract         TEXT,
    journal          VARCHAR(500),
    published_date   DATE,
    crossref_url     TEXT,
    source           VARCHAR(32) DEFAULT 'crossref'
                     CHECK (source IN ('crossref', 'openalex', 'manual')),
    discovered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- A paper appears at most once per subscription. NULL DOI rows
    -- (preprints without DOI) are deduplicated by trimmed-lowercased
    -- title via the partial index below — never by NULL = NULL.
    CONSTRAINT uq_research_feed_doi UNIQUE (subscription_id, doi)
);

CREATE INDEX IF NOT EXISTS idx_research_feed_subscription_time
    ON research_feed_items (subscription_id, discovered_at DESC);

-- Partial unique index for NULL-DOI dedup (preprints, working papers).
-- LOWER(TRIM(...)) handles superficial title-case variation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_research_feed_title_when_null_doi
    ON research_feed_items (subscription_id, LOWER(TRIM(title)))
    WHERE doi IS NULL;


COMMENT ON TABLE research_subscriptions IS
'User-configured "follow this research topic" subscriptions. Polled
periodically against CrossRef (and OpenAlex when configured). See
api/research_feed_routes.py and feedback_migration_tolerate_errors.';

COMMENT ON TABLE research_feed_items IS
'Papers discovered by the research-feed poller per subscription. One
row per (subscription, DOI) — same paper across multiple subs is
fine. Cascade-deletes with the subscription.';

DO $$
DECLARE
    n_subs INTEGER;
    n_items INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_subs FROM research_subscriptions;
    SELECT COUNT(*) INTO n_items FROM research_feed_items;
    RAISE NOTICE 'Migration 047: research_subscriptions has % rows, '
        'research_feed_items has %', n_subs, n_items;
END
$$;
