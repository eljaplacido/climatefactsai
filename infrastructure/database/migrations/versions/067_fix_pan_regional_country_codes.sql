-- Migration 067: fix country-code corruption from pan-regional feed codes (P0)
--
-- Root cause (2026-06-09 data-layer audit): eu_feeds_registry.py uses the
-- pan-regional markers XX-AF / XX-LA / XX-AS / XX-ME for multi-country feeds
-- (African Arguments, AllAfrica, Mongabay LATAM, The Third Pole, IRENA, …).
-- The articles.country_code column is CHAR(2), so these were SILENTLY
-- TRUNCATED to AF / LA / AS / ME — i.e. Afghanistan, Laos, American Samoa,
-- Montenegro — putting 161 "Afghanistan" / 119 "Botswana"-class artifacts on
-- the map. Going forward ingestion._normalize_country_code collapses non-ISO
-- codes to 'XX'; this migration re-stamps the already-corrupted rows.
--
-- Scoped to the 17 pan-regional feed source domains AND the four truncated
-- codes, so legitimate GNews country articles (e.g. real Afghanistan news on
-- a local outlet) are left untouched. Idempotent: after the first run the
-- rows are 'XX', so the country_code IN (...) predicate no longer matches.

UPDATE articles
SET country_code = 'XX',
    updated_at   = NOW()
WHERE country_code IN ('AF', 'AS', 'LA', 'ME')
  AND (
        url ILIKE '%africanarguments.org%'
     OR url ILIKE '%africaclimatesummit.org%'
     OR url ILIKE '%allafrica.com%'
     OR url ILIKE '%sdg.iisd.org%'
     OR url ILIKE '%uneca.org%'
     OR url ILIKE '%climatechangenews.com%'
     OR url ILIKE '%es.mongabay.com%'
     OR url ILIKE '%dialogochino.net%'
     OR url ILIKE '%plenglish.com%'
     OR url ILIKE '%cepal.org%'
     OR url ILIKE '%iadb.org%'
     OR url ILIKE '%climatetracker.org%'
     OR url ILIKE '%thethirdpole.net%'
     OR url ILIKE '%adb.org%'
     OR url ILIKE '%undp.org%'
     OR url ILIKE '%irena.org%'
     OR url ILIKE '%icarda.org%'
  );
