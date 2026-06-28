-- Migration 069: allow 'company_comparison' as a saved_items item_type.
--
-- The /companies/compare page saves comparisons with item_type='company_comparison'
-- (companies/compare/page.tsx) and the saved_items route accepts it, but the
-- mig-042 CHECK constraint only listed 8 types and omitted this one — so every
-- "save comparison" 500'd on a CHECK violation. Widen the allowed set.
--
-- Drops the existing item_type CHECK by discovering its (auto-generated) name
-- rather than hard-coding it, then re-adds a named, widened constraint.

DO $$
DECLARE
    cname text;
BEGIN
    SELECT conname INTO cname
    FROM pg_constraint
    WHERE conrelid = 'saved_items'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%item_type%IN%';
    IF cname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE saved_items DROP CONSTRAINT %I', cname);
    END IF;
END
$$;

ALTER TABLE saved_items ADD CONSTRAINT saved_items_item_type_check CHECK (
    item_type IN (
        'article', 'analysis', 'claim', 'search', 'company',
        'feed_setting', 'deep_search', 'country', 'company_comparison'
    )
);
