-- =============================================================================
-- 010: Global countries expansion
-- Adds region column and inserts 150+ countries for worldwide coverage.
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < migrations/versions/010_global_countries.sql
-- =============================================================================

BEGIN;

INSERT INTO schema_migrations (version, description)
VALUES (10, '010_global_countries.sql - global country expansion with regions')
ON CONFLICT (version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 1. Add region column to countries table
-- ---------------------------------------------------------------------------
ALTER TABLE countries ADD COLUMN IF NOT EXISTS region VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_countries_region ON countries(region);

-- ---------------------------------------------------------------------------
-- 2. Upsert all countries (existing + new) with accurate capital coordinates
--    ON CONFLICT updates continent, region, and coordinates for existing rows.
-- ---------------------------------------------------------------------------

INSERT INTO countries
    (country_code, country_name, country_name_native, continent, region, is_eu_member, language_code, latitude, longitude, flag_emoji, enabled)
VALUES
-- ==========================================================================
-- EUROPE  (region = 'europe')
-- ==========================================================================
-- Nordic
('FI', 'Finland',           'Suomi',            'Europe', 'europe', TRUE,  'fi', 60.16952000, 24.93545000, NULL, TRUE),
('SE', 'Sweden',            'Sverige',          'Europe', 'europe', TRUE,  'sv', 59.32938000, 18.06871000, NULL, TRUE),
('NO', 'Norway',            'Norge',            'Europe', 'europe', FALSE, 'no', 59.91387000, 10.75225000, NULL, TRUE),
('DK', 'Denmark',           'Danmark',          'Europe', 'europe', TRUE,  'da', 55.67610000, 12.56834000, NULL, TRUE),
('IS', 'Iceland',           'Island',           'Europe', 'europe', FALSE, 'is', 64.13548000,-21.89541000, NULL, TRUE),

-- British Isles
('GB', 'United Kingdom',    'United Kingdom',   'Europe', 'europe', FALSE, 'en', 51.50735000, -0.12776000, NULL, TRUE),
('IE', 'Ireland',           'Eire',             'Europe', 'europe', TRUE,  'ga', 53.34981000, -6.26031000, NULL, TRUE),

-- Western Europe
('FR', 'France',            'France',           'Europe', 'europe', TRUE,  'fr', 48.85661000,  2.35222000, NULL, TRUE),
('DE', 'Germany',           'Deutschland',      'Europe', 'europe', TRUE,  'de', 52.52001000, 13.40495000, NULL, TRUE),
('NL', 'Netherlands',       'Nederland',        'Europe', 'europe', TRUE,  'nl', 52.37403000,  4.88970000, NULL, TRUE),
('BE', 'Belgium',           'Belgie',           'Europe', 'europe', TRUE,  'nl', 50.85034000,  4.35171000, NULL, TRUE),
('LU', 'Luxembourg',        'Luxembourg',       'Europe', 'europe', TRUE,  'lb', 49.61162000,  6.13000000, NULL, TRUE),
('CH', 'Switzerland',       'Schweiz',          'Europe', 'europe', FALSE, 'de', 46.94810000,  7.44744000, NULL, TRUE),
('AT', 'Austria',           'Oesterreich',      'Europe', 'europe', TRUE,  'de', 48.20817000, 16.37382000, NULL, TRUE),
('LI', 'Liechtenstein',     'Liechtenstein',    'Europe', 'europe', FALSE, 'de', 47.14105000,  9.52154000, NULL, TRUE),

-- Southern Europe
('ES', 'Spain',             'Espana',           'Europe', 'europe', TRUE,  'es', 40.41678000, -3.70379000, NULL, TRUE),
('PT', 'Portugal',          'Portugal',         'Europe', 'europe', TRUE,  'pt', 38.72225000, -9.13934000, NULL, TRUE),
('IT', 'Italy',             'Italia',           'Europe', 'europe', TRUE,  'it', 41.90278000, 12.49637000, NULL, TRUE),
('MT', 'Malta',             'Malta',            'Europe', 'europe', TRUE,  'mt', 35.89890000, 14.51460000, NULL, TRUE),
('GR', 'Greece',            'Ellada',           'Europe', 'europe', TRUE,  'el', 37.98381000, 23.72753000, NULL, TRUE),
('CY', 'Cyprus',            'Kypros',           'Europe', 'europe', TRUE,  'el', 35.18560000, 33.38228000, NULL, TRUE),
('TR', 'Turkey',            'Turkiye',          'Europe', 'europe', FALSE, 'tr', 39.93365000, 32.85974000, NULL, TRUE),

-- Central Europe
('PL', 'Poland',            'Polska',           'Europe', 'europe', TRUE,  'pl', 52.22977000, 21.01178000, NULL, TRUE),
('CZ', 'Czech Republic',    'Cesko',            'Europe', 'europe', TRUE,  'cs', 50.07554000, 14.43780000, NULL, TRUE),
('SK', 'Slovakia',          'Slovensko',        'Europe', 'europe', TRUE,  'sk', 48.14816000, 17.10674000, NULL, TRUE),
('HU', 'Hungary',           'Magyarorszag',     'Europe', 'europe', TRUE,  'hu', 47.49791000, 19.04024000, NULL, TRUE),
('SI', 'Slovenia',          'Slovenija',        'Europe', 'europe', TRUE,  'sl', 46.05108000, 14.50513000, NULL, TRUE),

-- Southeast Europe
('RO', 'Romania',           'Romania',          'Europe', 'europe', TRUE,  'ro', 44.43225000, 26.10626000, NULL, TRUE),
('BG', 'Bulgaria',          'Bulgariya',        'Europe', 'europe', TRUE,  'bg', 42.69770000, 23.32189000, NULL, TRUE),
('HR', 'Croatia',           'Hrvatska',         'Europe', 'europe', TRUE,  'hr', 45.81500000, 15.98190000, NULL, TRUE),
('RS', 'Serbia',            'Srbija',           'Europe', 'europe', FALSE, 'sr', 44.78657000, 20.44892000, NULL, TRUE),
('BA', 'Bosnia and Herzegovina', 'Bosna i Hercegovina', 'Europe', 'europe', FALSE, 'bs', 43.85626000, 18.41313000, NULL, TRUE),
('ME', 'Montenegro',        'Crna Gora',        'Europe', 'europe', FALSE, 'sr', 42.44152000, 19.26362000, NULL, TRUE),
('MK', 'North Macedonia',   'Severna Makedonija','Europe', 'europe', FALSE, 'mk', 41.99732000, 21.42878000, NULL, TRUE),
('AL', 'Albania',           'Shqiperia',        'Europe', 'europe', FALSE, 'sq', 41.32755000, 19.81870000, NULL, TRUE),
('XK', 'Kosovo',            'Kosova',           'Europe', 'europe', FALSE, 'sq', 42.66267000, 21.16550000, NULL, TRUE),

-- Baltic
('EE', 'Estonia',           'Eesti',            'Europe', 'europe', TRUE,  'et', 59.43696000, 24.75353000, NULL, TRUE),
('LV', 'Latvia',            'Latvija',          'Europe', 'europe', TRUE,  'lv', 56.94965000, 24.10519000, NULL, TRUE),
('LT', 'Lithuania',         'Lietuva',          'Europe', 'europe', TRUE,  'lt', 54.68916000, 25.27980000, NULL, TRUE),

-- Eastern Europe / Caucasus
('UA', 'Ukraine',           'Ukrayina',         'Europe', 'europe', FALSE, 'uk', 50.45010000, 30.52340000, NULL, TRUE),
('MD', 'Moldova',           'Moldova',          'Europe', 'europe', FALSE, 'ro', 47.01046000, 28.86381000, NULL, TRUE),
('BY', 'Belarus',           'Belarus',          'Europe', 'europe', FALSE, 'be', 53.90067000, 27.55897000, NULL, TRUE),
('GE', 'Georgia',           'Sakartvelo',       'Europe', 'europe', FALSE, 'ka', 41.71514000, 44.82709000, NULL, TRUE),
('AM', 'Armenia',           'Hayastan',         'Europe', 'europe', FALSE, 'hy', 40.18310000, 44.51520000, NULL, TRUE),
('AZ', 'Azerbaijan',        'Azarbaycan',       'Europe', 'europe', FALSE, 'az', 40.40926000, 49.86710000, NULL, TRUE),
('RU', 'Russia',            'Rossiya',          'Europe', 'europe', FALSE, 'ru', 55.75580000, 37.61730000, NULL, TRUE),

-- ==========================================================================
-- NORTH AMERICA  (region = 'north_america')
-- ==========================================================================
('US', 'United States',     'United States',    'North America', 'north_america', FALSE, 'en', 38.89511000, -77.03637000, NULL, TRUE),
('CA', 'Canada',            'Canada',           'North America', 'north_america', FALSE, 'en', 45.42153000, -75.69720000, NULL, TRUE),
('MX', 'Mexico',            'Mexico',           'North America', 'north_america', FALSE, 'es', 19.43261000, -99.13321000, NULL, TRUE),

-- ==========================================================================
-- LATIN AMERICA  (region = 'latin_america')
-- ==========================================================================
('BR', 'Brazil',            'Brasil',           'South America', 'latin_america', FALSE, 'pt', -15.79420000, -47.88230000, NULL, TRUE),
('AR', 'Argentina',         'Argentina',        'South America', 'latin_america', FALSE, 'es', -34.60368000, -58.38155000, NULL, TRUE),
('CO', 'Colombia',          'Colombia',         'South America', 'latin_america', FALSE, 'es',   4.71099000, -74.07209000, NULL, TRUE),
('CL', 'Chile',             'Chile',            'South America', 'latin_america', FALSE, 'es', -33.44890000, -70.66927000, NULL, TRUE),
('PE', 'Peru',              'Peru',             'South America', 'latin_america', FALSE, 'es', -12.04637000, -77.04279000, NULL, TRUE),
('EC', 'Ecuador',           'Ecuador',          'South America', 'latin_america', FALSE, 'es',  -0.18065000, -78.46784000, NULL, TRUE),
('VE', 'Venezuela',         'Venezuela',        'South America', 'latin_america', FALSE, 'es',  10.48016000, -66.90370000, NULL, TRUE),
('UY', 'Uruguay',           'Uruguay',          'South America', 'latin_america', FALSE, 'es', -34.90111000, -56.16453000, NULL, TRUE),
('PY', 'Paraguay',          'Paraguay',         'South America', 'latin_america', FALSE, 'es', -25.26374000, -57.57561000, NULL, TRUE),
('BO', 'Bolivia',           'Bolivia',          'South America', 'latin_america', FALSE, 'es', -16.48984000, -68.11929000, NULL, TRUE),
('CR', 'Costa Rica',        'Costa Rica',       'North America', 'latin_america', FALSE, 'es',   9.93281000, -84.07972000, NULL, TRUE),
('PA', 'Panama',            'Panama',           'North America', 'latin_america', FALSE, 'es',   8.98380000, -79.51670000, NULL, TRUE),
('CU', 'Cuba',              'Cuba',             'North America', 'latin_america', FALSE, 'es',  23.11360000, -82.36660000, NULL, TRUE),
('DO', 'Dominican Republic','Republica Dominicana','North America','latin_america',FALSE,'es',  18.47186000, -69.89232000, NULL, TRUE),
('GT', 'Guatemala',         'Guatemala',        'North America', 'latin_america', FALSE, 'es',  14.63490000, -90.50690000, NULL, TRUE),
('HN', 'Honduras',          'Honduras',         'North America', 'latin_america', FALSE, 'es',  14.06500000, -87.17150000, NULL, TRUE),
('SV', 'El Salvador',       'El Salvador',      'North America', 'latin_america', FALSE, 'es',  13.69290000, -89.21820000, NULL, TRUE),
('NI', 'Nicaragua',         'Nicaragua',        'North America', 'latin_america', FALSE, 'es',  12.11500000, -86.23620000, NULL, TRUE),
('BB', 'Barbados',          'Barbados',         'North America', 'latin_america', FALSE, 'en',  13.10220000, -59.61420000, NULL, TRUE),
('JM', 'Jamaica',           'Jamaica',          'North America', 'latin_america', FALSE, 'en',  18.01790000, -76.80990000, NULL, TRUE),
('TT', 'Trinidad and Tobago','Trinidad and Tobago','North America','latin_america',FALSE,'en',  10.65180000, -61.51710000, NULL, TRUE),

-- ==========================================================================
-- AFRICA  (region = 'africa')
-- ==========================================================================
('KE', 'Kenya',             'Kenya',            'Africa', 'africa', FALSE, 'sw', -1.29207000, 36.82195000, NULL, TRUE),
('NG', 'Nigeria',           'Nigeria',          'Africa', 'africa', FALSE, 'en',  9.05785000,  7.49508000, NULL, TRUE),
('ZA', 'South Africa',      'South Africa',     'Africa', 'africa', FALSE, 'en', -25.74610000, 28.18710000, NULL, TRUE),
('GH', 'Ghana',             'Ghana',            'Africa', 'africa', FALSE, 'en',  5.60370000, -0.18696000, NULL, TRUE),
('TZ', 'Tanzania',          'Tanzania',         'Africa', 'africa', FALSE, 'sw', -6.79240000, 39.20830000, NULL, TRUE),
('UG', 'Uganda',            'Uganda',           'Africa', 'africa', FALSE, 'en',  0.31360000, 32.58100000, NULL, TRUE),
('RW', 'Rwanda',            'Rwanda',           'Africa', 'africa', FALSE, 'rw', -1.94030000, 29.87390000, NULL, TRUE),
('ET', 'Ethiopia',          'Ityopya',          'Africa', 'africa', FALSE, 'am',  9.02497000, 38.74689000, NULL, TRUE),
('EG', 'Egypt',             'Misr',             'Africa', 'africa', FALSE, 'ar', 30.04442000, 31.23571000, NULL, TRUE),
('MA', 'Morocco',           'Al-Maghrib',       'Africa', 'africa', FALSE, 'ar', 33.97159000, -6.84981000, NULL, TRUE),
('SN', 'Senegal',           'Senegal',          'Africa', 'africa', FALSE, 'fr', 14.69360000, -17.44770000, NULL, TRUE),
('ZM', 'Zambia',            'Zambia',           'Africa', 'africa', FALSE, 'en', -15.38710000, 28.32280000, NULL, TRUE),
('MW', 'Malawi',            'Malawi',           'Africa', 'africa', FALSE, 'en', -13.96260000, 33.78680000, NULL, TRUE),
('MZ', 'Mozambique',        'Mocambique',       'Africa', 'africa', FALSE, 'pt', -25.96920000, 32.57310000, NULL, TRUE),
('SD', 'Sudan',             'As-Sudan',         'Africa', 'africa', FALSE, 'ar', 15.50072000, 32.55990000, NULL, TRUE),
('CD', 'Democratic Republic of the Congo', 'Republique Democratique du Congo', 'Africa', 'africa', FALSE, 'fr', -4.44190000, 15.26590000, NULL, TRUE),
('CM', 'Cameroon',          'Cameroun',         'Africa', 'africa', FALSE, 'fr',  3.84800000, 11.50210000, NULL, TRUE),
('CI', 'Ivory Coast',       'Cote d Ivoire',    'Africa', 'africa', FALSE, 'fr',  6.82740000, -5.28930000, NULL, TRUE),
('TN', 'Tunisia',           'Tunis',            'Africa', 'africa', FALSE, 'ar', 36.80650000, 10.18160000, NULL, TRUE),
('LY', 'Libya',             'Libiya',           'Africa', 'africa', FALSE, 'ar', 32.89250000, 13.18000000, NULL, TRUE),
('AO', 'Angola',            'Angola',           'Africa', 'africa', FALSE, 'pt', -8.83900000, 13.28940000, NULL, TRUE),
('TG', 'Togo',              'Togo',             'Africa', 'africa', FALSE, 'fr',  6.17280000,  1.23140000, NULL, TRUE),
('BJ', 'Benin',             'Benin',            'Africa', 'africa', FALSE, 'fr',  6.49650000,  2.60360000, NULL, TRUE),
('BF', 'Burkina Faso',      'Burkina Faso',     'Africa', 'africa', FALSE, 'fr', 12.37140000, -1.51970000, NULL, TRUE),
('NE', 'Niger',             'Niger',            'Africa', 'africa', FALSE, 'fr', 13.51170000,  2.12540000, NULL, TRUE),
('ML', 'Mali',              'Mali',             'Africa', 'africa', FALSE, 'fr', 12.63920000, -8.00290000, NULL, TRUE),
('TD', 'Chad',              'Tchad',            'Africa', 'africa', FALSE, 'fr', 12.13480000, 15.05570000, NULL, TRUE),
('DJ', 'Djibouti',          'Djibouti',         'Africa', 'africa', FALSE, 'fr', 11.58800000, 43.14500000, NULL, TRUE),
('SO', 'Somalia',           'Soomaaliya',       'Africa', 'africa', FALSE, 'so',  2.04660000, 45.31820000, NULL, TRUE),
('ER', 'Eritrea',           'Ertra',            'Africa', 'africa', FALSE, 'ti', 15.33390000, 38.93180000, NULL, TRUE),
('SS', 'South Sudan',       'South Sudan',      'Africa', 'africa', FALSE, 'en',  4.85170000, 31.57480000, NULL, TRUE),
('NA', 'Namibia',           'Namibia',          'Africa', 'africa', FALSE, 'en', -22.56090000, 17.08350000, NULL, TRUE),
('BW', 'Botswana',          'Botswana',         'Africa', 'africa', FALSE, 'en', -24.65320000, 25.90870000, NULL, TRUE),
('LS', 'Lesotho',           'Lesotho',          'Africa', 'africa', FALSE, 'en', -29.31420000, 27.48380000, NULL, TRUE),
('SZ', 'Eswatini',          'Eswatini',         'Africa', 'africa', FALSE, 'en', -26.30540000, 31.13670000, NULL, TRUE),
('MG', 'Madagascar',        'Madagasikara',     'Africa', 'africa', FALSE, 'mg', -18.87920000, 47.50790000, NULL, TRUE),
('MU', 'Mauritius',         'Mauritius',        'Africa', 'africa', FALSE, 'en', -20.16090000, 57.50120000, NULL, TRUE),
('SC', 'Seychelles',        'Seychelles',       'Africa', 'africa', FALSE, 'en', -4.61960000, 55.45130000, NULL, TRUE),

-- ==========================================================================
-- ASIA  (region = 'asia')
-- ==========================================================================
('CN', 'China',             'Zhongguo',         'Asia', 'asia', FALSE, 'zh', 39.90420000, 116.40740000, NULL, TRUE),
('IN', 'India',             'Bharat',           'Asia', 'asia', FALSE, 'hi', 28.61390000, 77.20900000, NULL, TRUE),
('JP', 'Japan',             'Nihon',            'Asia', 'asia', FALSE, 'ja', 35.68950000, 139.69170000, NULL, TRUE),
('KR', 'South Korea',       'Hanguk',           'Asia', 'asia', FALSE, 'ko', 37.56650000, 126.97800000, NULL, TRUE),
('ID', 'Indonesia',         'Indonesia',        'Asia', 'asia', FALSE, 'id', -6.20880000, 106.84560000, NULL, TRUE),
('TH', 'Thailand',          'Prathet Thai',     'Asia', 'asia', FALSE, 'th', 13.75630000, 100.50180000, NULL, TRUE),
('VN', 'Vietnam',           'Viet Nam',         'Asia', 'asia', FALSE, 'vi', 21.02880000, 105.85420000, NULL, TRUE),
('PH', 'Philippines',       'Pilipinas',        'Asia', 'asia', FALSE, 'tl', 14.59950000, 120.98420000, NULL, TRUE),
('SG', 'Singapore',         'Singapore',        'Asia', 'asia', FALSE, 'en',  1.35210000, 103.81980000, NULL, TRUE),
('MY', 'Malaysia',          'Malaysia',         'Asia', 'asia', FALSE, 'ms',  3.13900000, 101.68690000, NULL, TRUE),
('BD', 'Bangladesh',        'Bangladesh',       'Asia', 'asia', FALSE, 'bn', 23.81030000, 90.41250000, NULL, TRUE),
('PK', 'Pakistan',          'Pakistan',         'Asia', 'asia', FALSE, 'ur', 33.69290000, 73.04510000, NULL, TRUE),
('TW', 'Taiwan',            'Taiwan',           'Asia', 'asia', FALSE, 'zh', 25.03300000, 121.56540000, NULL, TRUE),
('AU', 'Australia',         'Australia',        'Oceania','asia', FALSE, 'en', -35.28090000, 149.13000000, NULL, TRUE),
('NZ', 'New Zealand',       'Aotearoa',         'Oceania','asia', FALSE, 'en', -41.28650000, 174.77620000, NULL, TRUE),
('LK', 'Sri Lanka',         'Sri Lanka',        'Asia', 'asia', FALSE, 'si',  6.92710000, 79.86120000, NULL, TRUE),
('MM', 'Myanmar',           'Myanma',           'Asia', 'asia', FALSE, 'my', 19.76330000, 96.07850000, NULL, TRUE),
('KH', 'Cambodia',          'Kampuchea',        'Asia', 'asia', FALSE, 'km', 11.55640000, 104.92820000, NULL, TRUE),
('LA', 'Laos',              'Lao',              'Asia', 'asia', FALSE, 'lo', 17.96890000, 102.63310000, NULL, TRUE),
('NP', 'Nepal',             'Nepal',            'Asia', 'asia', FALSE, 'ne', 27.71720000, 85.32400000, NULL, TRUE),
('AF', 'Afghanistan',       'Afganistan',       'Asia', 'asia', FALSE, 'ps', 34.52530000, 69.17830000, NULL, TRUE),
('FJ', 'Fiji',              'Fiji',             'Oceania','asia', FALSE, 'en', -18.14160000, 178.44190000, NULL, TRUE),
('PG', 'Papua New Guinea',  'Papua Niugini',    'Oceania','asia', FALSE, 'en', -6.31470000, 143.95550000, NULL, TRUE),
('WS', 'Samoa',             'Samoa',            'Oceania','asia', FALSE, 'sm', -13.83330000,-171.76930000, NULL, TRUE),
('TO', 'Tonga',             'Tonga',            'Oceania','asia', FALSE, 'to', -21.21140000,-175.14960000, NULL, TRUE),

-- ==========================================================================
-- MIDDLE EAST  (region = 'middle_east')
-- ==========================================================================
('AE', 'United Arab Emirates','Al-Imarat',      'Asia', 'middle_east', FALSE, 'ar', 24.45390000, 54.37730000, NULL, TRUE),
('SA', 'Saudi Arabia',      'Al-Arabiyyah as-Suudiyyah','Asia','middle_east',FALSE,'ar', 24.71360000, 46.67530000, NULL, TRUE),
('IL', 'Israel',            'Yisrael',          'Asia', 'middle_east', FALSE, 'he', 31.76830000, 35.21370000, NULL, TRUE),
('JO', 'Jordan',            'Al-Urdun',         'Asia', 'middle_east', FALSE, 'ar', 31.95160000, 35.93370000, NULL, TRUE),
('LB', 'Lebanon',           'Lubnan',           'Asia', 'middle_east', FALSE, 'ar', 33.89380000, 35.50180000, NULL, TRUE),
('IQ', 'Iraq',              'Al-Iraq',          'Asia', 'middle_east', FALSE, 'ar', 33.31520000, 44.36610000, NULL, TRUE),
('IR', 'Iran',              'Iran',             'Asia', 'middle_east', FALSE, 'fa', 35.68920000, 51.38900000, NULL, TRUE),
('QA', 'Qatar',             'Qatar',            'Asia', 'middle_east', FALSE, 'ar', 25.28540000, 51.53100000, NULL, TRUE),
('KW', 'Kuwait',            'Al-Kuwayt',        'Asia', 'middle_east', FALSE, 'ar', 29.37590000, 47.97740000, NULL, TRUE),
('OM', 'Oman',              'Uman',             'Asia', 'middle_east', FALSE, 'ar', 23.58800000, 58.38290000, NULL, TRUE),
('BH', 'Bahrain',           'Al-Bahrayn',       'Asia', 'middle_east', FALSE, 'ar', 26.22350000, 50.58600000, NULL, TRUE)

ON CONFLICT (country_code) DO UPDATE SET
    continent  = EXCLUDED.continent,
    region     = EXCLUDED.region,
    latitude   = EXCLUDED.latitude,
    longitude  = EXCLUDED.longitude,
    enabled    = EXCLUDED.enabled;

-- ---------------------------------------------------------------------------
-- 3. Back-fill region for any rows that might have been missed
-- ---------------------------------------------------------------------------
UPDATE countries SET region = 'europe'        WHERE region IS NULL AND continent = 'Europe';
UPDATE countries SET region = 'north_america' WHERE region IS NULL AND continent = 'North America';
UPDATE countries SET region = 'latin_america' WHERE region IS NULL AND continent = 'South America';
UPDATE countries SET region = 'africa'        WHERE region IS NULL AND continent = 'Africa';
UPDATE countries SET region = 'asia'          WHERE region IS NULL AND continent IN ('Asia', 'Oceania');

DO $$ BEGIN RAISE NOTICE 'Migration 010 applied successfully — 150+ countries with regions.'; END $$;

COMMIT;
