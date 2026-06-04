-- Migration 065: source-health canary columns on rss_feed_registry (seq-9)
--
-- The ingestion path already writes fetch_error_count + last_fetched_at, but
-- nothing ever ACTED on a rising error count (dead feeds were polled forever)
-- and there was no per-feed liveness reporting. The source-health canary
-- (app/domains/content/source_health.py) probes each feed, records the result
-- here, and auto-disables a feed once fetch_error_count crosses the threshold.
--
-- All additive + nullable + IF NOT EXISTS => bulletproof, one transaction
-- (see run_migrations.py). No backfill: the first canary run populates them.

ALTER TABLE rss_feed_registry
    ADD COLUMN IF NOT EXISTS last_success_at  TIMESTAMPTZ,   -- last time the feed parsed with >=1 entry
    ADD COLUMN IF NOT EXISTS last_item_count  INTEGER,        -- entries seen on the last successful probe
    ADD COLUMN IF NOT EXISTS last_http_status INTEGER,        -- HTTP status of the last probe
    ADD COLUMN IF NOT EXISTS last_check_error TEXT;           -- error string of the last failed probe (NULL when healthy)

-- The canary reads is_active + fetch_error_count to decide auto-disable; the
-- existing idx_rss_feed_active covers the active filter. A small partial index
-- on the unhealthy tail keeps the /source-health report query cheap.
CREATE INDEX IF NOT EXISTS idx_rss_feed_unhealthy
    ON rss_feed_registry (fetch_error_count)
 WHERE fetch_error_count > 0;
