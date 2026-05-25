-- Migration 046: articles.source_url_status + last-checked timestamp.
--
-- Slice 5a (2026-05-25). Honest-Gap-Audit v2 item 7: many article
-- source_url links return 404 / paywalled / removed pages — but the
-- platform never re-checks URLs after first ingest, so dead links
-- accumulate forever and the "Source" link in article detail becomes
-- unreliable.
--
-- These columns let a periodic admin job (POST /api/admin/link-check
-- + Cloud Scheduler) tag URLs with their HTTP status and last-checked
-- timestamp. The article page can then render an "Original link
-- unavailable" affordance when status is 'broken' instead of sending
-- the user to a 404.
--
-- Status taxonomy (recorded by the admin endpoint):
--   ok        — last HEAD returned 2xx
--   broken    — last HEAD returned 4xx/5xx, network error, or DNS failure
--   redirect  — last HEAD returned 3xx and target unresolved
--   pending   — never checked yet (default)
--
-- This migration is purely additive — no data mutation, no FK
-- constraints, no index that could violate. Idempotent.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS source_url_status     VARCHAR(16),
    ADD COLUMN IF NOT EXISTS source_url_checked_at TIMESTAMPTZ;

-- Index for the periodic-check selector — "give me the N articles
-- that need re-checking" runs ORDER BY source_url_checked_at NULLS
-- FIRST LIMIT N. We can't use a time-based partial predicate
-- (NOW() isn't IMMUTABLE, Postgres rejects 42P17), so the predicate
-- only filters on source_url being set — the query layer handles
-- the "stale > 7d" filter at SELECT time. The btree still gives
-- O(log N) for the NULLS-FIRST ordering, which is what we need.
CREATE INDEX IF NOT EXISTS idx_articles_link_check_due
    ON articles (source_url_checked_at NULLS FIRST)
    WHERE source_url IS NOT NULL;

COMMENT ON COLUMN articles.source_url_status IS
'Result of the most recent HEAD probe of source_url. NULL = never checked. '
'See Slice 5a (Honest-Gap-Audit v2 item 7).';
COMMENT ON COLUMN articles.source_url_checked_at IS
'Timestamp of the most recent HEAD probe of source_url.';
