-- =============================================================================
-- 024_indicator_sync_logs.sql — Audit log for indicator-adapter sync runs
-- =============================================================================
-- Phase 3 wave 5: when Cloud Scheduler / cron triggers
-- POST /api/scheduler/indicators/sync, the resulting SyncResult lands
-- here. Ops can inspect freshness ("when did Climate TRACE last sync?")
-- and failure patterns (skipped_count, errors).
--
-- Retention: keep indefinitely. The rows are small (one per sync run);
-- a daily sync produces ~365 rows per adapter per year — trivial.
-- =============================================================================

CREATE TABLE IF NOT EXISTS indicator_sync_logs (
    id              BIGSERIAL PRIMARY KEY,
    source_name     VARCHAR(64) NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    duration_seconds DOUBLE PRECISION,
    fetched_count   INTEGER NOT NULL DEFAULT 0,
    upserted_count  INTEGER NOT NULL DEFAULT 0,
    skipped_count   INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    -- First 5 errors (or so) preserved verbatim for triage.
    errors          JSONB,
    triggered_by    VARCHAR(64) NOT NULL DEFAULT 'scheduler',
        -- 'scheduler' | 'manual' | 'startup' | 'admin_console'
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_sync_logs_source_recency
    ON indicator_sync_logs(source_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_indicator_sync_logs_started_at
    ON indicator_sync_logs(started_at DESC);

COMMENT ON TABLE indicator_sync_logs IS
    'One row per indicator-adapter sync run (Climate TRACE, OWID, CAT, …). '
    'Read by ops dashboards + freshness SLO alerts.';
