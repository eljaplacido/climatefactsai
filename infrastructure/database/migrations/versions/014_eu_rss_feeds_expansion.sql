-- Migration 014: EU-specific RSS feed expansion
-- Date: 2026-03-11
-- Adds 20+ European climate news sources across major EU member states

-- Nordic / Scandinavian climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('YLE News Climate (FI)', 'https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET&concepts=18-35354', 'yle.fi', 'FI', 'europe', 'public'),
    ('Svenska Dagbladet Klimat (SE)', 'https://www.svd.se/feed/rss/klimat', 'svd.se', 'SE', 'europe', 'public'),
    ('DR Klima (DK)', 'https://www.dr.dk/nyheder/service/feeds/klima', 'dr.dk', 'DK', 'europe', 'public'),
    ('NRK Klima (NO)', 'https://www.nrk.no/emne/klima/rss', 'nrk.no', 'NO', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- German-speaking climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Tagesschau Klima (DE)', 'https://www.tagesschau.de/xml/rss2_topthemen/', 'tagesschau.de', 'DE', 'europe', 'public'),
    ('Spiegel Wissenschaft (DE)', 'https://www.spiegel.de/wissenschaft/index.rss', 'spiegel.de', 'DE', 'europe', 'public'),
    ('Der Standard Klimawandel (AT)', 'https://www.derstandard.at/rss/klimawandel', 'derstandard.at', 'AT', 'europe', 'public'),
    ('Clean Energy Wire (DE)', 'https://www.cleanenergywire.org/rss.xml', 'cleanenergywire.org', 'DE', 'europe', 'research')
ON CONFLICT (feed_name) DO NOTHING;

-- French-speaking climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Le Monde Planete (FR)', 'https://www.lemonde.fr/planete/rss_full.xml', 'lemonde.fr', 'FR', 'europe', 'public'),
    ('Reporterre (FR)', 'https://reporterre.net/spip.php?page=backend', 'reporterre.net', 'FR', 'europe', 'research'),
    ('Novethic Climat (FR)', 'https://www.novethic.fr/feed', 'novethic.fr', 'FR', 'europe', 'research')
ON CONFLICT (feed_name) DO NOTHING;

-- Dutch / Benelux climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('NOS Klimaat (NL)', 'https://feeds.nos.nl/nosnieuwsklimaat', 'nos.nl', 'NL', 'europe', 'public'),
    ('De Correspondent Klimaat (NL)', 'https://decorrespondent.nl/feed', 'decorrespondent.nl', 'NL', 'europe', 'research')
ON CONFLICT (feed_name) DO NOTHING;

-- Southern European climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('El Pais Clima (ES)', 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/clima-y-medio-ambiente/portada', 'elpais.com', 'ES', 'europe', 'public'),
    ('La Repubblica Ambiente (IT)', 'https://www.repubblica.it/rss/ambiente/rss2.0.xml', 'repubblica.it', 'IT', 'europe', 'public'),
    ('Publico Ambiente (PT)', 'https://feeds.feedburner.com/PublicoAmbiente', 'publico.pt', 'PT', 'europe', 'public'),
    ('Kathimerini Environment (GR)', 'https://www.ekathimerini.com/rss/news/environment', 'ekathimerini.com', 'GR', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Eastern European climate feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('Gazeta Wyborcza Klimat (PL)', 'https://wyborcza.pl/rss/klimat', 'wyborcza.pl', 'PL', 'europe', 'public'),
    ('Denik Referendum Klima (CZ)', 'https://denikreferendum.cz/rss/klima', 'denikreferendum.cz', 'CZ', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;

-- Pan-European / EU institutional feeds
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('EEA News (EU)', 'https://www.eea.europa.eu/api/rss', 'eea.europa.eu', 'XX', 'europe', 'scientific'),
    ('Euractiv Energy & Environment', 'https://www.euractiv.com/sections/energy-environment/feed/', 'euractiv.com', 'XX', 'europe', 'research'),
    ('EurActiv Climate', 'https://www.euractiv.com/sections/climate-environment/feed/', 'euractiv.com', 'XX', 'europe', 'research'),
    ('Copernicus Climate Service', 'https://climate.copernicus.eu/rss.xml', 'climate.copernicus.eu', 'XX', 'europe', 'scientific'),
    ('ECMWF News', 'https://www.ecmwf.int/en/rss', 'ecmwf.int', 'XX', 'europe', 'scientific')
ON CONFLICT (feed_name) DO NOTHING;

-- Irish / UK extension
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier) VALUES
    ('RTE Environment (IE)', 'https://www.rte.ie/news/rss/environment.xml', 'rte.ie', 'IE', 'europe', 'public'),
    ('BBC Climate (GB)', 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml', 'bbc.co.uk', 'GB', 'europe', 'public')
ON CONFLICT (feed_name) DO NOTHING;
