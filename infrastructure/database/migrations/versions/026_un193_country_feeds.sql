-- Migration 026: UN-193 country coverage to 95% via Google News RSS feeds
--
-- Adds Google News country-and-language-scoped climate feeds for the
-- 116 UN-193 members not yet in rss_feed_registry as of 2026-05-18.
-- Google News aggregates from local publishers; resulting article rows
-- carry the underlying publisher in feedparser's source attribution.
-- Reliability tier is 'public' (aggregator); downstream source_credibility
-- scoring is applied per individual publisher when the article is parsed.
--
-- Idempotent: ON CONFLICT DO NOTHING respects existing rows.
-- Phase 8 (2026-05-24) fix: pre-add source_type column for cloud DBs that
-- were created from migration 012 only (which didn't include it).

ALTER TABLE rss_feed_registry
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'news_outlet';

INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Algeria', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=DZ&ceid=DZ:ar', 'news.google.com', 'DZ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Angola', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=pt&gl=AO&ceid=AO:pt', 'news.google.com', 'AO', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Benin', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=BJ&ceid=BJ:fr', 'news.google.com', 'BJ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Botswana', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BW&ceid=BW:en', 'news.google.com', 'BW', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Burkina Faso', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=BF&ceid=BF:fr', 'news.google.com', 'BF', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Burundi', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=BI&ceid=BI:fr', 'news.google.com', 'BI', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cabo Verde', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=pt&gl=CV&ceid=CV:pt', 'news.google.com', 'CV', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cameroon', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=CM&ceid=CM:fr', 'news.google.com', 'CM', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Central African Republic', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=CF&ceid=CF:fr', 'news.google.com', 'CF', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Chad', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=TD&ceid=TD:fr', 'news.google.com', 'TD', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Comoros', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=KM&ceid=KM:fr', 'news.google.com', 'KM', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Congo', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=CG&ceid=CG:fr', 'news.google.com', 'CG', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Democratic Republic of the Congo', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=CD&ceid=CD:fr', 'news.google.com', 'CD', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cote d''Ivoire', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=CI&ceid=CI:fr', 'news.google.com', 'CI', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Djibouti', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=DJ&ceid=DJ:fr', 'news.google.com', 'DJ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Equatorial Guinea', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=GQ&ceid=GQ:es', 'news.google.com', 'GQ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Eritrea', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=ER&ceid=ER:en', 'news.google.com', 'ER', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Eswatini', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SZ&ceid=SZ:en', 'news.google.com', 'SZ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Gabon', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=GA&ceid=GA:fr', 'news.google.com', 'GA', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Gambia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=GM&ceid=GM:en', 'news.google.com', 'GM', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Guinea', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=GN&ceid=GN:fr', 'news.google.com', 'GN', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Guinea-Bissau', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=pt&gl=GW&ceid=GW:pt', 'news.google.com', 'GW', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Lesotho', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LS&ceid=LS:en', 'news.google.com', 'LS', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Liberia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LR&ceid=LR:en', 'news.google.com', 'LR', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Libya', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=LY&ceid=LY:ar', 'news.google.com', 'LY', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Madagascar', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=MG&ceid=MG:fr', 'news.google.com', 'MG', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Malawi', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MW&ceid=MW:en', 'news.google.com', 'MW', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Mali', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=ML&ceid=ML:fr', 'news.google.com', 'ML', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Mauritania', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=MR&ceid=MR:ar', 'news.google.com', 'MR', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Mauritius', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MU&ceid=MU:en', 'news.google.com', 'MU', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Mozambique', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=pt&gl=MZ&ceid=MZ:pt', 'news.google.com', 'MZ', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Namibia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=NA&ceid=NA:en', 'news.google.com', 'NA', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Niger', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=NE&ceid=NE:fr', 'news.google.com', 'NE', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Rwanda', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=RW&ceid=RW:en', 'news.google.com', 'RW', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Sao Tome and Principe', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=pt&gl=ST&ceid=ST:pt', 'news.google.com', 'ST', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Seychelles', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SC&ceid=SC:en', 'news.google.com', 'SC', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Sierra Leone', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SL&ceid=SL:en', 'news.google.com', 'SL', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Somalia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SO&ceid=SO:en', 'news.google.com', 'SO', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - South Sudan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SS&ceid=SS:en', 'news.google.com', 'SS', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Sudan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=SD&ceid=SD:ar', 'news.google.com', 'SD', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Togo', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=TG&ceid=TG:fr', 'news.google.com', 'TG', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Tunisia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=TN&ceid=TN:ar', 'news.google.com', 'TN', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Uganda', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=UG&ceid=UG:en', 'news.google.com', 'UG', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Zambia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=ZM&ceid=ZM:en', 'news.google.com', 'ZM', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Zimbabwe', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=ZW&ceid=ZW:en', 'news.google.com', 'ZW', 'africa', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Afghanistan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=AF&ceid=AF:en', 'news.google.com', 'AF', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Armenia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=AM&ceid=AM:en', 'news.google.com', 'AM', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Azerbaijan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=AZ&ceid=AZ:en', 'news.google.com', 'AZ', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Bhutan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BT&ceid=BT:en', 'news.google.com', 'BT', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Brunei', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BN&ceid=BN:en', 'news.google.com', 'BN', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cambodia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=KH&ceid=KH:en', 'news.google.com', 'KH', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cyprus', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=CY&ceid=CY:en', 'news.google.com', 'CY', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Georgia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=GE&ceid=GE:en', 'news.google.com', 'GE', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Israel', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=IL&ceid=IL:en', 'news.google.com', 'IL', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Kyrgyzstan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=KG&ceid=KG:en', 'news.google.com', 'KG', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Laos', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LA&ceid=LA:en', 'news.google.com', 'LA', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Malaysia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MY&ceid=MY:en', 'news.google.com', 'MY', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Maldives', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MV&ceid=MV:en', 'news.google.com', 'MV', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Mongolia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MN&ceid=MN:en', 'news.google.com', 'MN', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - North Korea', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=KP&ceid=KP:en', 'news.google.com', 'KP', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Syria', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=ar&gl=SY&ceid=SY:ar', 'news.google.com', 'SY', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Tajikistan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TJ&ceid=TJ:en', 'news.google.com', 'TJ', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Timor-Leste', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TL&ceid=TL:en', 'news.google.com', 'TL', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Turkey', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TR&ceid=TR:en', 'news.google.com', 'TR', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Turkmenistan', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TM&ceid=TM:en', 'news.google.com', 'TM', 'asia', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Albania', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=AL&ceid=AL:en', 'news.google.com', 'AL', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Andorra', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=AD&ceid=AD:es', 'news.google.com', 'AD', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Belarus', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BY&ceid=BY:en', 'news.google.com', 'BY', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Belgium', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BE&ceid=BE:en', 'news.google.com', 'BE', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Bosnia and Herzegovina', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BA&ceid=BA:en', 'news.google.com', 'BA', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Estonia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=EE&ceid=EE:en', 'news.google.com', 'EE', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Latvia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LV&ceid=LV:en', 'news.google.com', 'LV', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Liechtenstein', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=de&gl=LI&ceid=LI:de', 'news.google.com', 'LI', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Lithuania', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LT&ceid=LT:en', 'news.google.com', 'LT', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Luxembourg', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LU&ceid=LU:en', 'news.google.com', 'LU', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Malta', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MT&ceid=MT:en', 'news.google.com', 'MT', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Moldova', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MD&ceid=MD:en', 'news.google.com', 'MD', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Monaco', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=MC&ceid=MC:fr', 'news.google.com', 'MC', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Montenegro', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=ME&ceid=ME:en', 'news.google.com', 'ME', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - North Macedonia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MK&ceid=MK:en', 'news.google.com', 'MK', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Russia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=RU&ceid=RU:en', 'news.google.com', 'RU', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - San Marino', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=it&gl=SM&ceid=SM:it', 'news.google.com', 'SM', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Serbia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=RS&ceid=RS:en', 'news.google.com', 'RS', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Ukraine', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=UA&ceid=UA:en', 'news.google.com', 'UA', 'europe', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Antigua and Barbuda', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=AG&ceid=AG:en', 'news.google.com', 'AG', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Bahamas', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BS&ceid=BS:en', 'news.google.com', 'BS', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Barbados', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BB&ceid=BB:en', 'news.google.com', 'BB', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Belize', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=BZ&ceid=BZ:en', 'news.google.com', 'BZ', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Cuba', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=CU&ceid=CU:es', 'news.google.com', 'CU', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Dominica', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=DM&ceid=DM:en', 'news.google.com', 'DM', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Dominican Republic', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=DO&ceid=DO:es', 'news.google.com', 'DO', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - El Salvador', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=SV&ceid=SV:es', 'news.google.com', 'SV', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Grenada', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=GD&ceid=GD:en', 'news.google.com', 'GD', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Guatemala', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=GT&ceid=GT:es', 'news.google.com', 'GT', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Guyana', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=GY&ceid=GY:en', 'news.google.com', 'GY', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Haiti', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=fr&gl=HT&ceid=HT:fr', 'news.google.com', 'HT', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Honduras', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=HN&ceid=HN:es', 'news.google.com', 'HN', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Jamaica', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=JM&ceid=JM:en', 'news.google.com', 'JM', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Nicaragua', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=NI&ceid=NI:es', 'news.google.com', 'NI', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Panama', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=PA&ceid=PA:es', 'news.google.com', 'PA', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Paraguay', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=PY&ceid=PY:es', 'news.google.com', 'PY', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Saint Kitts and Nevis', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=KN&ceid=KN:en', 'news.google.com', 'KN', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Saint Lucia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=LC&ceid=LC:en', 'news.google.com', 'LC', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Saint Vincent and the Grenadines', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=VC&ceid=VC:en', 'news.google.com', 'VC', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Suriname', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SR&ceid=SR:en', 'news.google.com', 'SR', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Trinidad and Tobago', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TT&ceid=TT:en', 'news.google.com', 'TT', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Uruguay', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=es&gl=UY&ceid=UY:es', 'news.google.com', 'UY', 'americas', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Kiribati', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=KI&ceid=KI:en', 'news.google.com', 'KI', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Marshall Islands', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=MH&ceid=MH:en', 'news.google.com', 'MH', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Micronesia', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=FM&ceid=FM:en', 'news.google.com', 'FM', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Nauru', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=NR&ceid=NR:en', 'news.google.com', 'NR', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Palau', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=PW&ceid=PW:en', 'news.google.com', 'PW', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Solomon Islands', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=SB&ceid=SB:en', 'news.google.com', 'SB', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Tonga', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TO&ceid=TO:en', 'news.google.com', 'TO', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Tuvalu', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=TV&ceid=TV:en', 'news.google.com', 'TV', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;
INSERT INTO rss_feed_registry (feed_name, feed_url, source_domain, country_code, region, reliability_tier, is_active, is_system_feed, source_type)
  VALUES ('Google News Climate - Vanuatu', 'https://news.google.com/rss/search?q=climate+OR+sustainability+OR+%22green+transition%22&hl=en&gl=VU&ceid=VU:en', 'news.google.com', 'VU', 'oceania', 'public', TRUE, TRUE, 'news_outlet')
  ON CONFLICT DO NOTHING;

-- Coverage tally after insert:
-- SELECT COUNT(DISTINCT country_code) FROM rss_feed_registry WHERE is_active = TRUE;
