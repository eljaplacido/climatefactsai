-- CliLens.AI Sample Climate News Articles
-- Generated: 2025-10-28

BEGIN;

INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    'sample-001',
    'https://example.com/finland-renewable-energy-2025',
    'Finland Leads EU in Renewable Energy Transition with 87% Clean Power',
    'Nordic Climate News',
    'FI',
    'en',
    'Finland has achieved remarkable milestone in renewable energy transition, reaching 87% clean energy in national grid...',
    'Finland continues to lead the European Union''s renewable energy transition, with latest data showing that 87% of the nation''s electricity now comes from clean sources. The Nordic country''s success story combines wind, solar, and hydroelectric power with innovative energy storage solutions.',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    'verified',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();

INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    'sample-002',
    'https://example.com/sweden-carbon-capture-2025',
    'Sweden Invests €5 Billion in Carbon Capture Technology',
    'Scandinavian Environmental Review',
    'SE',
    'en',
    'Swedish government announces massive €5 billion investment in carbon capture and storage facilities...',
    'The Swedish government has announced a groundbreaking €5 billion investment program in carbon capture and storage (CCS) technology. This ambitious initiative aims to remove 10 million tons of CO2 annually by 2028, positioning Sweden as a global leader in negative emissions technology.',
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    'pending',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();

INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    'sample-003',
    'https://example.com/denmark-wind-exports-2025',
    'Denmark''s Wind Energy Exports Reach Record €2.3 Billion',
    'Danish Energy Monitor',
    'DK',
    'en',
    'Denmark''s wind energy sector exports hit record high of €2.3 billion in Q3 2025...',
    'Denmark''s offshore wind industry has achieved unprecedented export success, generating €2.3 billion in revenue during Q3 2025. The country''s expertise in turbine manufacturing and offshore installation services continues to drive growth in international markets.',
    CURRENT_TIMESTAMP - INTERVAL '12 hours',
    'verified',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();

INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    'sample-004',
    'https://example.com/norway-floating-solar-2025',
    'Norway Launches World''s Largest Floating Solar Farm in Fjords',
    'Nordic Innovation Today',
    'NO',
    'en',
    'Norway inaugurates revolutionary floating solar installation spanning 50 hectares in coastal fjords...',
    'Norway has unveiled the world''s largest floating solar farm, spanning 50 hectares across its scenic fjords. The innovative project combines Norway''s abundant water resources with cutting-edge solar technology, generating enough electricity to power 15,000 homes while preserving valuable land for other uses.',
    CURRENT_TIMESTAMP - INTERVAL '6 hours',
    'verified',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();

INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    'sample-005',
    'https://example.com/estonia-smart-grid-2025',
    'Estonia Pioneers AI-Driven Smart Grid for 100% Renewable Integration',
    'Baltic Tech Review',
    'EE',
    'en',
    'Estonia deploys revolutionary AI-powered smart grid capable of managing 100% renewable energy sources...',
    'Estonia has become the first Baltic nation to deploy a fully AI-driven smart grid system capable of managing 100% renewable energy integration. The system uses machine learning to predict energy demand and optimize distribution from wind, solar, and biomass sources in real-time.',
    CURRENT_TIMESTAMP - INTERVAL '3 hours',
    'pending',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();

COMMIT;

-- Verify insertion
SELECT COUNT(*) as article_count FROM articles WHERE article_id LIKE 'sample-%';
SELECT article_id, title, country_code, fact_check_status FROM articles WHERE article_id LIKE 'sample-%' ORDER BY published_date DESC;
