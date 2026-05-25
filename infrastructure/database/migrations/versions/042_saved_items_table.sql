-- Migration 042: generalised saved_items table — Phase 10 (2026-05-25).
-- Per user feedback: "save not only articles, but analysis results,
-- their different my feed settings". The existing user_bookmarks
-- table only handles articles. This adds a polymorphic saved_items
-- table for everything else, with item_type discriminating the
-- underlying entity:
--
--   item_type='article'      → item_id = articles.article_id
--   item_type='analysis'     → item_id = url_analyses.analysis_id
--   item_type='claim'        → item_id = claims.claim_id
--   item_type='search'       → item_ref = arbitrary search-URL string
--   item_type='company'      → item_id = companies.company_id
--   item_type='feed_setting' → item_ref = JSON-encoded preferences
--   item_type='deep_search'  → item_ref = full deep-search query payload
--   item_type='country'      → item_ref = ISO 2-char country code
--
-- We use item_ref (TEXT) for non-UUID references and item_id (UUID)
-- for FK-able references. Exactly one must be non-null per row.
--
-- Existing user_bookmarks stays untouched for backward compat. A
-- future migration can DROP it after the frontend fully migrates.

CREATE TABLE IF NOT EXISTS saved_items (
    saved_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    item_type       VARCHAR(32) NOT NULL CHECK (item_type IN (
        'article', 'analysis', 'claim', 'search', 'company',
        'feed_setting', 'deep_search', 'country'
    )),
    item_id         UUID,         -- when the target has a UUID PK
    item_ref        TEXT,         -- when the target is a search URL / JSON / 2-char code
    label           VARCHAR(255), -- user-supplied label/title
    notes           TEXT,
    folder          VARCHAR(64) DEFAULT 'default',
    payload         JSONB,        -- arbitrary user-attached state (filters, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,

    -- Exactly one of (item_id, item_ref) must be populated.
    CONSTRAINT saved_items_target_xor CHECK (
        (item_id IS NOT NULL AND item_ref IS NULL)
        OR (item_id IS NULL AND item_ref IS NOT NULL)
    ),
    -- Same (user, type, target) twice = upsert, not duplicate.
    CONSTRAINT uq_saved_items_target UNIQUE (user_id, item_type, item_id, item_ref)
);

CREATE INDEX IF NOT EXISTS idx_saved_items_user_type
    ON saved_items (user_id, item_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_saved_items_user_folder
    ON saved_items (user_id, folder, created_at DESC);

COMMENT ON TABLE saved_items IS
'Polymorphic save bucket — articles, analyses, claims, searches,
 companies, feed settings, deep-search queries, countries.
 Phase 10 (2026-05-25). user_bookmarks stays for backward compat
 until the frontend fully migrates here.';


-- Mirror the existing user_bookmarks rows into saved_items so users
-- don't lose any saved articles when the frontend migrates.
INSERT INTO saved_items (
    saved_id, user_id, item_type, item_id, label, notes, folder, created_at
)
SELECT uuid_generate_v4(), b.user_id, 'article', b.article_id,
       (SELECT title FROM articles a WHERE a.article_id = b.article_id),
       b.notes, COALESCE(b.folder, 'default'), b.bookmarked_at
FROM user_bookmarks b
WHERE NOT EXISTS (
    SELECT 1 FROM saved_items s
    WHERE s.user_id = b.user_id
      AND s.item_type = 'article'
      AND s.item_id = b.article_id
);

DO $$
DECLARE
    n_saved INTEGER;
    n_bookmarks INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_saved FROM saved_items;
    SELECT COUNT(*) INTO n_bookmarks FROM user_bookmarks;
    RAISE NOTICE 'Migration 042: saved_items has % rows, user_bookmarks has %',
        n_saved, n_bookmarks;
END
$$;
