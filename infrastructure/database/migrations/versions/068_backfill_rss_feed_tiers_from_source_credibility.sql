-- Migration 068: backfill rss_feed_registry.reliability_tier from source_credibility_tiers (seq-9)
--
-- The RSS feed registry has a reliability_tier column that defaults to 'public'.
-- Meanwhile, source_credibility_tiers has been populated with T1/T2/T3 ratings for 60+
-- sources (migrations 027, 033, 058, 060, 066). The ingestion scheduler
-- (scheduled_scientific_feed_ingestion, celery_app.py) filters on
-- rss_feed_registry.reliability_tier, so all 50 displayed sources currently
-- show 'public' — including IPCC, NASA, and other T1 sources.
--
-- This migration cross-references source_domain against source_credibility_tiers
-- and stamps the correct tier. Domains without tier data remain 'public'.
-- Idempotent — re-running overwrites existing tiers with the same value.

DO $$
DECLARE
    r record;
    tier_ranked text;
BEGIN
    FOR r IN
        SELECT feed_id, source_domain, reliability_tier
        FROM rss_feed_registry
        WHERE source_domain IS NOT NULL
    LOOP
        -- source_credibility_tiers uses domain patterns; extract the domain root
        -- e.g. "www.bbc.com" → "bbc.com"
        SELECT sct.tier INTO tier_ranked
        FROM source_credibility_tiers sct
        WHERE r.source_domain ILIKE ('%' || sct.domain || '%')
           OR sct.domain ILIKE ('%' || r.source_domain || '%')
        ORDER BY CASE sct.tier
            WHEN 'T1' THEN 1
            WHEN 'T2' THEN 2
            WHEN 'T3' THEN 3
            WHEN 'unknown' THEN 4
            ELSE 5
        END
        LIMIT 1;

        IF tier_ranked IS NOT NULL AND tier_ranked != r.reliability_tier THEN
            UPDATE rss_feed_registry
            SET reliability_tier = tier_ranked
            WHERE feed_id = r.feed_id;

            RAISE NOTICE 'Backfilled %: % → % (domain: %)',
                r.feed_id, r.reliability_tier, tier_ranked, r.source_domain;
        END IF;
    END LOOP;
END $$;

-- Report: what tiers look like after backfill
DO $$
DECLARE
    tier_summary record;
BEGIN
    RAISE NOTICE '--- Post-migration tier summary ---';
    FOR tier_summary IN
        SELECT reliability_tier, COUNT(*) as cnt
        FROM rss_feed_registry
        WHERE is_active = true
        GROUP BY reliability_tier
        ORDER BY reliability_tier
    LOOP
        RAISE NOTICE '  %: %', tier_summary.reliability_tier, tier_summary.cnt;
    END LOOP;
END $$;
