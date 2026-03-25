-- Global Climate News Seed Data: 70+ articles across 6 continents
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < scripts/seed_global_data.sql
-- Includes: articles, claims, fact_checks with full reliability/transparency data

BEGIN;

-- ============================================================
-- ADDITIONAL SOURCE PROFILES (global sources)
-- ============================================================

INSERT INTO source_profiles (source_id, source_name, source_domain, credibility_score, editorial_standards, fact_check_record, transparency_level, total_articles_analyzed, average_reliability_score, total_claims_verified, total_claims_disputed, false_claim_rate, source_type, country_code, description, website_url) VALUES
-- North America
('a0000000-0000-4000-8000-000000000011', 'NRDC', 'nrdc.org', 88, 'rigorous', 'good', 'high', 90, 87.5, 200, 14, 0.065, 'ngo', 'US', 'Natural Resources Defense Council', 'https://www.nrdc.org'),
('a0000000-0000-4000-8000-000000000012', 'Environment and Climate Change Canada', 'canada.ca', 91, 'rigorous', 'excellent', 'high', 75, 90.2, 180, 8, 0.043, 'government_agency', 'CA', 'Canadian federal department for environment', 'https://www.canada.ca/en/environment-climate-change.html'),
('a0000000-0000-4000-8000-000000000013', 'SEMARNAT', 'gob.mx/semarnat', 78, 'moderate', 'good', 'moderate', 40, 77.8, 85, 10, 0.105, 'government_agency', 'MX', 'Mexican Ministry of Environment', 'https://www.gob.mx/semarnat'),
-- Latin America
('a0000000-0000-4000-8000-000000000014', 'INPE Brazil', 'inpe.br', 90, 'rigorous', 'excellent', 'high', 85, 89.5, 220, 9, 0.039, 'research_institution', 'BR', 'Brazilian National Institute for Space Research', 'https://www.gov.br/inpe'),
('a0000000-0000-4000-8000-000000000015', 'CEPAL', 'cepal.org', 86, 'rigorous', 'good', 'high', 55, 85.8, 140, 11, 0.073, 'research_institution', NULL, 'UN Economic Commission for Latin America', 'https://www.cepal.org'),
('a0000000-0000-4000-8000-000000000016', 'La Nacion Argentina', 'lanacion.com.ar', 72, 'moderate', 'good', 'moderate', 50, 73.2, 100, 15, 0.130, 'news_outlet', 'AR', 'Argentine daily newspaper', 'https://www.lanacion.com.ar'),
-- Africa
('a0000000-0000-4000-8000-000000000017', 'African Climate Foundation', 'africanclimatefoundation.org', 84, 'rigorous', 'good', 'high', 60, 83.7, 130, 8, 0.058, 'ngo', 'ZA', 'Pan-African climate research foundation', 'https://africanclimatefoundation.org'),
('a0000000-0000-4000-8000-000000000018', 'UNEP Africa', 'unep.org/regions/africa', 92, 'rigorous', 'excellent', 'high', 95, 91.5, 260, 7, 0.026, 'research_institution', NULL, 'UN Environment Programme Africa office', 'https://www.unep.org/regions/africa'),
('a0000000-0000-4000-8000-000000000019', 'Climate Home News', 'climatechangenews.com', 80, 'moderate', 'good', 'high', 100, 79.8, 180, 18, 0.091, 'news_outlet', 'GB', 'Independent climate journalism outlet', 'https://www.climatechangenews.com'),
-- Asia
('a0000000-0000-4000-8000-000000000020', 'China Meteorological Administration', 'cma.gov.cn', 85, 'rigorous', 'good', 'moderate', 70, 84.5, 160, 12, 0.070, 'government_agency', 'CN', 'Chinese national weather service', 'https://www.cma.gov.cn'),
('a0000000-0000-4000-8000-000000000021', 'TERI India', 'teriin.org', 83, 'rigorous', 'good', 'high', 65, 82.9, 150, 10, 0.063, 'research_institution', 'IN', 'The Energy and Resources Institute', 'https://www.teriin.org'),
('a0000000-0000-4000-8000-000000000022', 'Japan Meteorological Agency', 'jma.go.jp', 93, 'rigorous', 'excellent', 'high', 80, 92.1, 200, 6, 0.029, 'government_agency', 'JP', 'Japanese national weather and climate service', 'https://www.jma.go.jp'),
('a0000000-0000-4000-8000-000000000023', 'The Jakarta Post', 'thejakartapost.com', 70, 'moderate', 'mixed', 'moderate', 45, 71.2, 80, 14, 0.149, 'news_outlet', 'ID', 'Leading English-language daily in Indonesia', 'https://www.thejakartapost.com'),
-- Middle East / Oceania
('a0000000-0000-4000-8000-000000000024', 'CSIRO Australia', 'csiro.au', 94, 'rigorous', 'excellent', 'high', 110, 93.2, 300, 8, 0.026, 'research_institution', 'AU', 'Commonwealth Scientific and Industrial Research Organisation', 'https://www.csiro.au'),
('a0000000-0000-4000-8000-000000000025', 'Masdar UAE', 'masdar.ae', 76, 'moderate', 'good', 'moderate', 35, 76.5, 65, 8, 0.110, 'research_institution', 'AE', 'Abu Dhabi Future Energy Company', 'https://masdar.ae'),
('a0000000-0000-4000-8000-000000000026', 'NIWA New Zealand', 'niwa.co.nz', 91, 'rigorous', 'excellent', 'high', 70, 90.8, 170, 5, 0.029, 'research_institution', 'NZ', 'National Institute of Water and Atmospheric Research', 'https://niwa.co.nz')
ON CONFLICT (source_id) DO NOTHING;


-- ============================================================
-- NORTH AMERICA ARTICLES (12 articles: US, CA, MX)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('40000000-0000-4000-8000-000000000001',
 'US Wildfire Season 2025: Record Acreage Burned in Western States',
 'https://nrdc.org/stories/wildfire-season-2025', 'Michael Torres', NOW() - INTERVAL '3 days',
 'NRDC', 88, 'Over 8.5 million acres burned in western US during 2025 fire season, exceeding 2020 records.',
 'The 2025 wildfire season has been the most destructive on record for the western United States. Over 8.5 million acres have burned across California, Oregon, Washington, and Montana. Climate scientists attribute the severity to prolonged drought conditions and above-average temperatures.',
 ARRAY['climate', 'wildfire', 'adaptation', 'temperature'], 0.91, 88, 'HIGH', 'US', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000011'),

('40000000-0000-4000-8000-000000000002',
 'Canadian Arctic Ice Loss Reaches Critical Threshold',
 'https://canada.ca/arctic-ice-2025', 'Dr. Jean-Pierre Bouchard', NOW() - INTERVAL '4 days',
 'Environment and Climate Change Canada', 91, 'Northwest Passage now ice-free for 4 consecutive months, the longest period ever recorded.',
 'Environment and Climate Change Canada reports that the Northwest Passage remained ice-free for four consecutive months in 2025, breaking the previous record of 2.5 months set in 2020. The finding has major implications for Arctic shipping routes and indigenous communities.',
 ARRAY['climate', 'arctic', 'sea-ice', 'temperature'], 0.93, 91, 'HIGH', 'CA', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000012'),

('40000000-0000-4000-8000-000000000003',
 'Mexico Water Crisis: Climate Change Amplifies Drought in Central Regions',
 'https://gob.mx/semarnat/drought-crisis-2025', 'Carmen Juarez', NOW() - INTERVAL '2 days',
 'SEMARNAT', 78, 'Central Mexico faces worst drought in 50 years; 30 million people affected by water rationing.',
 'The Mexican Ministry of Environment declared a water emergency in 12 central states as reservoirs fell to 25% capacity. Climate models indicate the drought is consistent with warming-driven changes to the North American monsoon pattern.',
 ARRAY['climate', 'adaptation', 'water-stress', 'temperature'], 0.82, 78, 'MEDIUM', 'MX', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000013'),

('40000000-0000-4000-8000-000000000004',
 'US Inflation Reduction Act: $370 Billion Clean Energy Investment Progress Report',
 'https://nrdc.org/ira-progress-2025', 'Sarah Williams', NOW() - INTERVAL '5 days',
 'NRDC', 85, 'IRA has catalyzed $280 billion in private clean energy investments since 2022.',
 'A comprehensive review of the Inflation Reduction Act shows that the landmark climate legislation has driven $280 billion in private sector clean energy investments. Over 300,000 new clean energy jobs have been created across 44 states.',
 ARRAY['climate', 'clean-energy', 'environmental-policy', 'energy-transition'], 0.88, 85, 'HIGH', 'US', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000011'),

('40000000-0000-4000-8000-000000000005',
 'British Columbia Glacier Retreat Accelerates: 60% Volume Loss Since 1985',
 'https://canada.ca/bc-glaciers-2025', 'Dr. Amanda Reed', NOW() - INTERVAL '6 days',
 'Environment and Climate Change Canada', 92, 'British Columbia glaciers have lost 60% of their volume in 40 years.',
 'New satellite and ground-based measurements show that British Columbia glaciers have lost approximately 60% of their total ice volume since 1985. The rate of loss has tripled in the last decade compared to the 1990s.',
 ARRAY['climate', 'arctic', 'sea-ice', 'temperature'], 0.90, 92, 'HIGH', 'CA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000012'),

('40000000-0000-4000-8000-000000000006',
 'US Coastal Flooding: 2025 Sees Record High-Tide Flooding Events',
 'https://noaa.gov/coastal-flooding-2025', 'Dr. Robert Chen', NOW() - INTERVAL '1 day',
 'NOAA', 93, 'US East Coast experienced 120 high-tide flooding events in 2025, triple the 2000 average.',
 'NOAA data shows US East Coast communities experienced 120 high-tide flooding events in 2025, compared to an average of 40 per year in 2000. Sea level rise of 3.2mm per year is the primary driver.',
 ARRAY['climate', 'ocean', 'adaptation', 'sea-level'], 0.94, 93, 'HIGH', 'US', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000002'),

('40000000-0000-4000-8000-000000000007',
 'Mexico Mangrove Restoration: Blue Carbon Success Story',
 'https://gob.mx/semarnat/mangrove-restoration', 'Dr. Luis Mendoza', NOW() - INTERVAL '7 days',
 'SEMARNAT', 80, 'Mexico has restored 50,000 hectares of mangroves, sequestering 2.5 million tons of CO2.',
 'Mexicos national mangrove restoration program has successfully rehabilitated 50,000 hectares of coastal wetlands. Blue carbon measurements confirm 2.5 million tons of CO2 sequestered since the program began in 2020.',
 ARRAY['climate', 'conservation', 'emissions', 'biodiversity'], 0.83, 80, 'HIGH', 'MX', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000013'),

('40000000-0000-4000-8000-000000000008',
 'Canada Carbon Tax Impact: Emissions Down 8% Since Implementation',
 'https://canada.ca/carbon-tax-review-2025', 'Prof. David Wong', NOW() - INTERVAL '3 days',
 'Environment and Climate Change Canada', 89, 'Canadian carbon pricing has reduced national emissions by 8% since 2019.',
 'An independent review of Canadas carbon pricing mechanism shows national greenhouse gas emissions have decreased by 8% since the policy was implemented in 2019, while GDP grew by 7% over the same period.',
 ARRAY['climate', 'environmental-policy', 'emissions', 'energy-transition'], 0.87, 89, 'HIGH', 'CA', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000012'),

('40000000-0000-4000-8000-000000000009',
 'US Solar Industry Reaches 200 GW Installed Capacity Milestone',
 'https://iea.org/reports/us-solar-2025', 'Jennifer Liu', NOW() - INTERVAL '2 days',
 'International Energy Agency', 90, 'US solar capacity surpasses 200 GW, generating 15% of national electricity.',
 'The International Energy Agency reports that US installed solar capacity has exceeded 200 GW, now generating approximately 15% of the nations electricity. Texas, California, and Florida lead in new installations.',
 ARRAY['climate', 'renewable-energy', 'clean-energy', 'energy-transition'], 0.92, 90, 'HIGH', 'US', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('40000000-0000-4000-8000-000000000010',
 'Great Lakes Water Temperatures Hit Record Highs',
 'https://noaa.gov/great-lakes-warming-2025', 'Dr. Michelle Park', NOW() - INTERVAL '5 days',
 'NOAA', 91, 'Great Lakes surface temperatures averaged 2.3C above normal in summer 2025.',
 'NOAA monitoring data shows Great Lakes surface temperatures averaged 2.3C above the 1991-2020 normal during summer 2025. Lake Erie reached 27.8C, the highest temperature ever recorded. Harmful algal blooms increased by 40%.',
 ARRAY['climate', 'temperature', 'water-stress', 'biodiversity'], 0.90, 91, 'HIGH', 'US', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000002'),

('40000000-0000-4000-8000-000000000011',
 'Mexican Wind Power Expansion Targets 35 GW by 2030',
 'https://iea.org/reports/mexico-wind-2025', 'Carlos Rivera', NOW() - INTERVAL '4 days',
 'International Energy Agency', 86, 'Mexico aims to triple wind power capacity from 12 GW to 35 GW by 2030.',
 'Mexico has announced ambitious plans to expand wind power capacity from 12 GW to 35 GW by 2030. The Isthmus of Tehuantepec wind corridor alone is expected to contribute 15 GW of new capacity.',
 ARRAY['climate', 'renewable-energy', 'wind-power', 'energy-transition'], 0.85, 86, 'HIGH', 'MX', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('40000000-0000-4000-8000-000000000012',
 'Alaskan Permafrost Communities Face Relocation: 31 Villages at Risk',
 'https://nrdc.org/alaska-permafrost-communities', 'Dr. Nathan Brooks', NOW() - INTERVAL '8 days',
 'NRDC', 84, '31 Alaskan villages face imminent relocation as permafrost thaw destabilizes infrastructure.',
 'The US Army Corps of Engineers has identified 31 Alaskan villages requiring relocation within the next decade due to permafrost thaw undermining buildings and infrastructure. Estimated relocation costs exceed $5 billion.',
 ARRAY['climate', 'permafrost', 'adaptation', 'arctic'], 0.86, 84, 'HIGH', 'US', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000011')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- LATIN AMERICA ARTICLES (11 articles: BR, AR, CO, CL, PE, EC)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('41000000-0000-4000-8000-000000000001',
 'Amazon Deforestation Falls 45% Under New Brazilian Policy',
 'https://inpe.br/amazon-deforestation-2025', 'Dr. Paulo Costa', NOW() - INTERVAL '2 days',
 'INPE Brazil', 90, 'Amazon deforestation dropped 45% in 2024-2025 compared to the previous period.',
 'INPE satellite data confirms Amazon deforestation decreased by 45% between August 2024 and July 2025 compared to the same period one year earlier. The decline is attributed to strengthened enforcement and indigenous territory protections.',
 ARRAY['climate', 'deforestation', 'conservation', 'biodiversity'], 0.93, 90, 'HIGH', 'BR', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000014'),

('41000000-0000-4000-8000-000000000002',
 'Argentine Patagonia Glaciers Losing 3 Cubic km of Ice Per Year',
 'https://lanacion.com.ar/patagonia-glaciers-2025', 'Maria Fernandez', NOW() - INTERVAL '3 days',
 'La Nacion Argentina', 72, 'Patagonian glaciers are losing ice at 3 cubic km annually, double the 2000 rate.',
 'Research by Argentine and Chilean scientists shows Patagonian glaciers are losing approximately 3 cubic km of ice per year, double the rate measured in 2000. The Perito Moreno glacier is one of the few still advancing.',
 ARRAY['climate', 'arctic', 'sea-ice', 'temperature'], 0.75, 72, 'MEDIUM', 'AR', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000016'),

('41000000-0000-4000-8000-000000000003',
 'Colombia Announces 30% Renewable Energy Target by 2030',
 'https://cepal.org/colombia-renewables-2025', 'Ana Martinez', NOW() - INTERVAL '4 days',
 'CEPAL', 86, 'Colombia commits to generating 30% of electricity from non-hydro renewables by 2030.',
 'Colombia has announced an ambitious renewable energy target, committing to 30% of electricity from non-hydro renewable sources by 2030. The La Guajira wind farm complex alone will add 2.5 GW of capacity.',
 ARRAY['climate', 'renewable-energy', 'energy-transition', 'environmental-policy'], 0.85, 86, 'HIGH', 'CO', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015'),

('41000000-0000-4000-8000-000000000004',
 'Chile Leads Latin America in Green Hydrogen Production',
 'https://cepal.org/chile-hydrogen-2025', 'Dr. Sebastian Vidal', NOW() - INTERVAL '5 days',
 'CEPAL', 88, 'Chile produces 40% of Latin Americas green hydrogen, targeting export leadership.',
 'Chile has emerged as Latin Americas green hydrogen leader, producing 40% of the regions output. The Atacama Desert offers unmatched solar irradiance for electrolysis, with production costs reaching $2.50/kg.',
 ARRAY['climate', 'clean-energy', 'hydrogen', 'energy-transition'], 0.87, 88, 'HIGH', 'CL', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015'),

('41000000-0000-4000-8000-000000000005',
 'Peru Andes Glacial Melt Threatens Lima Water Supply',
 'https://cepal.org/peru-glacial-melt-2025', 'Dr. Ricardo Flores', NOW() - INTERVAL '1 day',
 'CEPAL', 84, 'Andean glaciers supplying Lima have lost 55% of volume since 1970; water crisis looms.',
 'Andean glaciers that supply water to Lima and other Peruvian cities have lost 55% of their volume since 1970. With 10 million people dependent on glacial meltwater, Peru faces an existential water security challenge.',
 ARRAY['climate', 'water-stress', 'adaptation', 'temperature'], 0.86, 84, 'HIGH', 'PE', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015'),

('41000000-0000-4000-8000-000000000006',
 'Brazilian Cerrado Emissions Now Exceed Amazon: New Satellite Data',
 'https://inpe.br/cerrado-emissions-2025', 'Dr. Lucia Santos', NOW() - INTERVAL '6 days',
 'INPE Brazil', 92, 'Cerrado savanna deforestation now produces more CO2 than the Amazon basin.',
 'INPE satellite analysis reveals that deforestation of Brazils Cerrado savanna now produces more carbon emissions than Amazon deforestation. Soy and cattle expansion have cleared 48% of the original Cerrado biome.',
 ARRAY['climate', 'deforestation', 'emissions', 'biodiversity'], 0.91, 92, 'HIGH', 'BR', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000014'),

('41000000-0000-4000-8000-000000000007',
 'Ecuador Galapagos Marine Reserve: Ocean Warming Threatens Unique Ecosystem',
 'https://cepal.org/galapagos-warming-2025', 'Dr. Isabella Moreno', NOW() - INTERVAL '2 days',
 'CEPAL', 82, 'Galapagos waters have warmed 1.5C above historical average, threatening endemic species.',
 'Ocean temperatures around the Galapagos Islands have risen 1.5C above the 1961-1990 average. Marine iguanas, penguins, and coral reefs face severe stress from the warming waters.',
 ARRAY['climate', 'ocean', 'biodiversity', 'conservation'], 0.84, 82, 'HIGH', 'EC', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015'),

('41000000-0000-4000-8000-000000000008',
 'Argentina Wind Energy Boom: Patagonia Could Power South America',
 'https://lanacion.com.ar/patagonia-wind-2025', 'Diego Ramirez', NOW() - INTERVAL '7 days',
 'La Nacion Argentina', 74, 'Patagonian wind potential estimated at 500 GW, enough to power the continent.',
 'Studies by Argentine energy researchers estimate Patagonias wind power potential at 500 GW. The region already hosts 5 GW of installed capacity and is attracting international investment for green hydrogen production.',
 ARRAY['climate', 'renewable-energy', 'wind-power', 'energy-transition'], 0.76, 74, 'MEDIUM', 'AR', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000016'),

('41000000-0000-4000-8000-000000000009',
 'Brazil Amazon Carbon Credits: Market Integrity Under Scrutiny',
 'https://climatechangenews.com/brazil-carbon-credits', 'Helena Andrade', NOW() - INTERVAL '8 days',
 'Climate Home News', 68, 'Investigation finds 40% of Amazon REDD+ credits may not represent real emission reductions.',
 'An investigation into Amazon REDD+ carbon credit projects found that approximately 40% of credits issued may not represent genuine emission reductions. Questions about baseline methodology and additionality persist.',
 ARRAY['climate', 'emissions', 'deforestation', 'environmental-policy'], 0.70, 68, 'MEDIUM', 'BR', 4, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('41000000-0000-4000-8000-000000000010',
 'Chilean Lithium Mining and Climate: The Green Transition Paradox',
 'https://cepal.org/chile-lithium-2025', 'Prof. Andrea Rojas', NOW() - INTERVAL '3 days',
 'CEPAL', 80, 'Lithium extraction in Atacama uses 65% of regional water supply amid severe drought.',
 'Chiles lithium mining boom, essential for global battery production, consumes 65% of available water in the Atacama Desert region during a period of unprecedented drought. The tension between green transition minerals and local environmental impact is growing.',
 ARRAY['climate', 'sustainability', 'water-stress', 'energy-transition'], 0.81, 80, 'HIGH', 'CL', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015'),

('41000000-0000-4000-8000-000000000011',
 'Colombia Coffee Belt Shifts Upward: Climate Change Reshapes Agriculture',
 'https://cepal.org/colombia-coffee-2025', 'Juan Carlos Perez', NOW() - INTERVAL '4 days',
 'CEPAL', 83, 'Optimal coffee growing altitude has shifted 200m higher in 20 years due to warming.',
 'The optimal altitude for Arabica coffee cultivation in Colombia has shifted approximately 200 meters higher over the past two decades. Farmers at traditional altitudes report 30% yield declines due to heat stress and changing rainfall patterns.',
 ARRAY['climate', 'adaptation', 'temperature', 'biodiversity'], 0.82, 83, 'HIGH', 'CO', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000015')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- AFRICA ARTICLES (12 articles: KE, NG, ZA, GH, TZ, ET, EG, MA, SN)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('42000000-0000-4000-8000-000000000001',
 'Kenya Geothermal Energy Reaches 1 GW: Leading Africas Clean Power',
 'https://africanclimatefoundation.org/kenya-geothermal', 'Dr. Wanjiru Kamau', NOW() - INTERVAL '2 days',
 'African Climate Foundation', 84, 'Kenya now generates 1 GW of geothermal power, supplying 45% of national electricity.',
 'Kenyas geothermal capacity has reached 1 GW, making it the largest geothermal producer in Africa and 7th globally. The Olkaria complex in the Rift Valley supplies 45% of national electricity demand at competitive rates.',
 ARRAY['climate', 'renewable-energy', 'clean-energy', 'energy-transition'], 0.86, 84, 'HIGH', 'KE', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000017'),

('42000000-0000-4000-8000-000000000002',
 'Nigeria Flooding Crisis: 2.5 Million Displaced in 2025',
 'https://unep.org/regions/africa/nigeria-floods', 'Adebayo Okonkwo', NOW() - INTERVAL '3 days',
 'UNEP Africa', 92, 'Unprecedented flooding in Nigeria displaces 2.5 million and destroys 500,000 hectares of farmland.',
 'UNEP reports that Nigeria experienced its worst flooding in recorded history in 2025. Over 2.5 million people were displaced and 500,000 hectares of farmland destroyed. Climate change has intensified rainfall in the Niger-Benue basin by 20%.',
 ARRAY['climate', 'adaptation', 'water-stress', 'climate-indicators'], 0.93, 92, 'HIGH', 'NG', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('42000000-0000-4000-8000-000000000003',
 'South Africa Just Energy Transition: $8.5 Billion Coal Phase-Out Progress',
 'https://africanclimatefoundation.org/sa-jet', 'Dr. Thabo Mokoena', NOW() - INTERVAL '1 day',
 'African Climate Foundation', 82, 'South Africas coal phase-out partnership has mobilized $8.5 billion for green transition.',
 'South Africas Just Energy Transition Partnership has mobilized $8.5 billion in international financing to support the transition away from coal. Three coal-fired power stations are scheduled for decommissioning by 2027.',
 ARRAY['climate', 'energy-transition', 'environmental-policy', 'clean-energy'], 0.84, 82, 'HIGH', 'ZA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000017'),

('42000000-0000-4000-8000-000000000004',
 'Ghana Cocoa Industry Under Threat from Rising Temperatures',
 'https://unep.org/regions/africa/ghana-cocoa', 'Kwame Asante', NOW() - INTERVAL '4 days',
 'UNEP Africa', 88, 'Ghanas cocoa production declined 25% as growing zones shift due to warming.',
 'Ghana, the worlds second-largest cocoa producer, has seen a 25% production decline over five years. Rising temperatures and erratic rainfall have made traditional cocoa-growing regions unsuitable, pushing cultivation into forest reserves.',
 ARRAY['climate', 'adaptation', 'deforestation', 'temperature'], 0.87, 88, 'HIGH', 'GH', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('42000000-0000-4000-8000-000000000005',
 'Tanzania Coral Reefs: 70% Bleaching in 2025 Marine Heat Wave',
 'https://unep.org/regions/africa/tanzania-coral', 'Dr. Amina Mwakasege', NOW() - INTERVAL '5 days',
 'UNEP Africa', 90, 'Indian Ocean heat wave causes 70% bleaching in Tanzanian coral reef systems.',
 'A marine heat wave in the western Indian Ocean has caused 70% bleaching across Tanzanian coral reef systems. Sea surface temperatures reached 2.5C above normal for eight consecutive weeks, the longest thermal stress event recorded in the region.',
 ARRAY['climate', 'ocean', 'biodiversity', 'temperature'], 0.89, 90, 'HIGH', 'TZ', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('42000000-0000-4000-8000-000000000006',
 'Ethiopian Highlands Reforestation: 5 Billion Trees Planted',
 'https://climatechangenews.com/ethiopia-reforestation', 'Yohannes Gebre', NOW() - INTERVAL '6 days',
 'Climate Home News', 76, 'Ethiopias Green Legacy Initiative has planted 5 billion seedlings since 2019.',
 'Ethiopias ambitious Green Legacy Initiative claims to have planted 5 billion tree seedlings since 2019. While the planting numbers are impressive, survival rates vary between 50-70% depending on the region and species.',
 ARRAY['climate', 'conservation', 'deforestation', 'bioeconomy'], 0.78, 76, 'MEDIUM', 'ET', 3, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('42000000-0000-4000-8000-000000000007',
 'Egypt Renewable Energy Revolution: 42% Target by 2030',
 'https://iea.org/reports/egypt-renewables-2025', 'Dr. Fatma Hassan', NOW() - INTERVAL '2 days',
 'International Energy Agency', 87, 'Egypt targets 42% renewable electricity by 2030 with massive Benban solar complex.',
 'Egypt is rapidly expanding its renewable energy capacity, targeting 42% of electricity from renewables by 2030. The Benban Solar Park, one of the worlds largest, now produces 1.65 GW. New wind farms along the Red Sea coast add 3 GW.',
 ARRAY['climate', 'renewable-energy', 'solar', 'energy-transition'], 0.88, 87, 'HIGH', 'EG', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('42000000-0000-4000-8000-000000000008',
 'Morocco Leads Africa in Climate Adaptation: Fog Water Harvesting at Scale',
 'https://unep.org/regions/africa/morocco-fog', 'Fatima Zahra Benali', NOW() - INTERVAL '7 days',
 'UNEP Africa', 85, 'Moroccos fog water harvesting systems now supply 15,000 people in arid regions.',
 'Morocco has scaled its innovative fog water harvesting technology to supply clean water to 15,000 people in the Anti-Atlas mountains. The nets capture moisture from Atlantic fog, producing 600 liters per net per day.',
 ARRAY['climate', 'adaptation', 'water-stress', 'sustainability'], 0.84, 85, 'HIGH', 'MA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('42000000-0000-4000-8000-000000000009',
 'Senegal Great Green Wall: Progress and Challenges',
 'https://africanclimatefoundation.org/senegal-ggw', 'Mamadou Diallo', NOW() - INTERVAL '3 days',
 'African Climate Foundation', 80, 'Senegals section of the Great Green Wall is 35% complete, restoring 2.8M hectares.',
 'Senegals segment of the pan-African Great Green Wall initiative is approximately 35% complete, with 2.8 million hectares of degraded land restored. The project has improved food security for 400,000 households but faces ongoing funding challenges.',
 ARRAY['climate', 'conservation', 'adaptation', 'bioeconomy'], 0.82, 80, 'HIGH', 'SN', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000017'),

('42000000-0000-4000-8000-000000000010',
 'South African Drought: Cape Town Dam Levels at 40%',
 'https://climatechangenews.com/cape-town-drought-2025', 'Nandi Zulu', NOW() - INTERVAL '4 days',
 'Climate Home News', 78, 'Cape Town dam levels fall to 40% as Western Cape faces third consecutive dry winter.',
 'Cape Town faces renewed water stress as dam levels drop to 40% capacity following three consecutive below-average rainfall winters. Climate projections suggest the Western Cape will receive 20-30% less rainfall by 2050.',
 ARRAY['climate', 'water-stress', 'adaptation', 'climate-indicators'], 0.80, 78, 'MEDIUM', 'ZA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('42000000-0000-4000-8000-000000000011',
 'Kenya Maasai Mara: Wildlife Migration Patterns Shift Due to Climate',
 'https://unep.org/regions/africa/kenya-wildlife', 'Dr. Grace Otieno', NOW() - INTERVAL '5 days',
 'UNEP Africa', 86, 'Great Migration timing has shifted 3 weeks earlier as rainfall patterns change.',
 'The famous wildebeest migration through the Maasai Mara has shifted its timing by approximately three weeks earlier over the past decade. Changing rainfall patterns linked to Indian Ocean warming are altering grass growth cycles across the Serengeti ecosystem.',
 ARRAY['climate', 'biodiversity', 'adaptation', 'temperature'], 0.85, 86, 'HIGH', 'KE', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('42000000-0000-4000-8000-000000000012',
 'Nigeria Solar Mini-Grids: Powering 5 Million Off-Grid Residents',
 'https://africanclimatefoundation.org/nigeria-solar', 'Chidinma Eze', NOW() - INTERVAL '1 day',
 'African Climate Foundation', 81, 'Nigerias solar mini-grid program now serves 5 million off-grid residents.',
 'Nigerias Solar Naija program has deployed over 10,000 solar mini-grids powering 5 million previously off-grid residents. The decentralized approach has proven more cost-effective than grid extension in rural areas.',
 ARRAY['climate', 'renewable-energy', 'solar', 'energy-transition'], 0.83, 81, 'HIGH', 'NG', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000017')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- ASIA ARTICLES (12 articles: CN, IN, JP, KR, ID, TH, BD, PH, AU, NZ)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('43000000-0000-4000-8000-000000000001',
 'China Installs Record 300 GW of Solar in 2024',
 'https://iea.org/reports/china-solar-2025', 'Dr. Wei Zhang', NOW() - INTERVAL '2 days',
 'International Energy Agency', 92, 'China installed a record 300 GW of solar capacity in 2024, more than the rest of the world combined.',
 'The IEA reports China installed approximately 300 GW of new solar capacity in 2024, exceeding the combined additions of all other countries. Chinas total solar capacity now exceeds 1,000 GW.',
 ARRAY['climate', 'renewable-energy', 'solar', 'energy-transition'], 0.94, 92, 'HIGH', 'CN', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('43000000-0000-4000-8000-000000000002',
 'India Heat Wave 2025: 52C Recorded in Rajasthan',
 'https://teriin.org/india-heatwave-2025', 'Dr. Priya Sharma', NOW() - INTERVAL '1 day',
 'TERI India', 83, '52C recorded in Rajasthan; over 1,200 heat-related deaths across northern India.',
 'India recorded its highest-ever temperature of 52C in Phalodi, Rajasthan during the 2025 heat wave. Over 1,200 heat-related deaths were reported across northern India. Cooling demand surge caused rolling power blackouts in Delhi.',
 ARRAY['climate', 'temperature', 'adaptation', 'climate-indicators'], 0.85, 83, 'HIGH', 'IN', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000021'),

('43000000-0000-4000-8000-000000000003',
 'Japan Hydrogen Economy: World First Commercial Hydrogen Supply Chain',
 'https://jma.go.jp/en/hydrogen-2025', 'Dr. Takeshi Yamamoto', NOW() - INTERVAL '3 days',
 'Japan Meteorological Agency', 90, 'Japan launches worlds first commercial liquefied hydrogen supply chain from Australia.',
 'Japan has launched the worlds first commercial-scale liquefied hydrogen supply chain, importing green hydrogen produced from Australian solar energy. The Kobe terminal can receive 1,250 cubic meters of liquefied hydrogen per shipment.',
 ARRAY['climate', 'clean-energy', 'hydrogen', 'energy-transition'], 0.89, 90, 'HIGH', 'JP', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000022'),

('43000000-0000-4000-8000-000000000004',
 'South Korea Commits to Net Zero by 2050: New Climate Law',
 'https://climatechangenews.com/south-korea-net-zero', 'Park Sung-min', NOW() - INTERVAL '4 days',
 'Climate Home News', 79, 'South Korea passes climate neutrality law requiring 40% emission cuts by 2030.',
 'South Korea has passed a comprehensive climate neutrality law mandating a 40% reduction in greenhouse gas emissions by 2030 and net zero by 2050. The law includes carbon pricing reform and a $50 billion green technology investment fund.',
 ARRAY['climate', 'environmental-policy', 'emissions', 'energy-transition'], 0.80, 79, 'MEDIUM', 'KR', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('43000000-0000-4000-8000-000000000005',
 'Indonesia Peatland Fires: Carbon Emissions Spike Despite Moratorium',
 'https://thejakartapost.com/peatland-fires-2025', 'Rina Wahyuni', NOW() - INTERVAL '2 days',
 'The Jakarta Post', 70, 'Indonesian peatland fires released 500 million tons of CO2 in 2025 despite fire moratorium.',
 'Despite a government moratorium on peatland clearing, Indonesia experienced widespread peatland fires in 2025 releasing an estimated 500 million tons of CO2. El Nino conditions exacerbated drought in Kalimantan and Sumatra.',
 ARRAY['climate', 'emissions', 'deforestation', 'wildfire'], 0.72, 70, 'MEDIUM', 'ID', 3, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000023'),

('43000000-0000-4000-8000-000000000006',
 'Thailand Bangkok Sinking: Sea Level Rise Compounds Subsidence',
 'https://climatechangenews.com/bangkok-sinking-2025', 'Somsak Prachaya', NOW() - INTERVAL '5 days',
 'Climate Home News', 77, 'Bangkok sinking at 2cm per year while sea levels rise; 40% of city below sea level by 2030.',
 'Bangkok is sinking at approximately 2cm per year due to groundwater extraction, while sea levels in the Gulf of Thailand rise by 4mm annually. Models project 40% of the city will be below sea level by 2030.',
 ARRAY['climate', 'ocean', 'adaptation', 'sea-level'], 0.79, 77, 'MEDIUM', 'TH', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('43000000-0000-4000-8000-000000000007',
 'Bangladesh Climate Migration: 13 Million May Relocate by 2050',
 'https://climatechangenews.com/bangladesh-migration', 'Dr. Farida Rahman', NOW() - INTERVAL '6 days',
 'Climate Home News', 81, 'World Bank projects 13 million Bangladeshis may become internal climate migrants by 2050.',
 'The World Bank projects that up to 13 million Bangladeshis could become internal climate migrants by 2050 due to sea level rise, flooding, and salinity intrusion. Dhaka already absorbs 400,000 climate migrants annually.',
 ARRAY['climate', 'adaptation', 'ocean', 'sea-level'], 0.83, 81, 'HIGH', 'BD', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('43000000-0000-4000-8000-000000000008',
 'Philippines Super Typhoon Season: 5 Category 5 Storms in 2025',
 'https://climatechangenews.com/philippines-typhoons-2025', 'Maria Santos', NOW() - INTERVAL '3 days',
 'Climate Home News', 78, 'Philippines hit by 5 Category 5 typhoons in 2025, most in recorded history.',
 'The Philippines experienced five Category 5 super typhoons in the 2025 season, the most in recorded history. Warmer sea surface temperatures in the western Pacific, 1.8C above normal, fueled the intensification.',
 ARRAY['climate', 'climate-indicators', 'adaptation', 'temperature'], 0.80, 78, 'MEDIUM', 'PH', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('43000000-0000-4000-8000-000000000009',
 'Australia Great Barrier Reef: Sixth Mass Bleaching Event',
 'https://csiro.au/great-barrier-reef-2025', 'Dr. James Cook', NOW() - INTERVAL '1 day',
 'CSIRO Australia', 94, 'Great Barrier Reef experiences sixth mass bleaching event; 90% of reef surveyed shows bleaching.',
 'CSIRO aerial surveys confirm the Great Barrier Reef has experienced its sixth mass bleaching event. 90% of 1,036 reefs surveyed showed signs of bleaching. Sea temperatures reached 2C above the March average across the Coral Sea.',
 ARRAY['climate', 'ocean', 'biodiversity', 'temperature'], 0.95, 94, 'HIGH', 'AU', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000024'),

('43000000-0000-4000-8000-000000000010',
 'New Zealand Glacier Monitoring: Fox and Franz Josef Retreat Accelerates',
 'https://niwa.co.nz/glaciers-2025', 'Dr. Sarah Thompson', NOW() - INTERVAL '4 days',
 'NIWA New Zealand', 91, 'Fox and Franz Josef glaciers have retreated 800m in the last 5 years.',
 'NIWA long-term monitoring shows that New Zealands iconic Fox and Franz Josef glaciers have retreated 800 meters in the last five years. Both glaciers have lost 30% of their length since 1990.',
 ARRAY['climate', 'arctic', 'temperature', 'climate-indicators'], 0.90, 91, 'HIGH', 'NZ', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000026'),

('43000000-0000-4000-8000-000000000011',
 'China Yangtze River Drought: Lowest Water Levels in 150 Years',
 'https://cma.gov.cn/yangtze-drought-2025', 'Li Wei', NOW() - INTERVAL '7 days',
 'China Meteorological Administration', 85, 'Yangtze River water levels hit 150-year low, affecting 400 million people.',
 'The China Meteorological Administration reports that water levels in sections of the Yangtze River have fallen to their lowest point in 150 years of record-keeping. The drought affects water supply, agriculture, and hydroelectric generation for 400 million people.',
 ARRAY['climate', 'water-stress', 'adaptation', 'temperature'], 0.86, 85, 'HIGH', 'CN', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000020'),

('43000000-0000-4000-8000-000000000012',
 'India Solar Rooftop Revolution: 100 GW Target Achieved',
 'https://teriin.org/india-solar-rooftop-2025', 'Arun Patel', NOW() - INTERVAL '2 days',
 'TERI India', 84, 'India reaches 100 GW of rooftop solar capacity, powering 50 million homes.',
 'India has achieved its ambitious target of 100 GW rooftop solar capacity ahead of schedule. The program, subsidized through the PM Surya Ghar scheme, now powers approximately 50 million homes with clean energy.',
 ARRAY['climate', 'renewable-energy', 'solar', 'energy-transition'], 0.86, 84, 'HIGH', 'IN', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000021')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- MIDDLE EAST ARTICLES (10 articles: AE, SA, IL, JO, QA, KW, IR)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('44000000-0000-4000-8000-000000000001',
 'UAE IRENA Hub: Renewable Energy Capacity Doubled in 3 Years',
 'https://masdar.ae/uae-renewables-2025', 'Dr. Ahmed Al-Rashid', NOW() - INTERVAL '2 days',
 'Masdar UAE', 76, 'UAE has doubled its renewable energy capacity from 3 GW to 6 GW in three years.',
 'The UAE has doubled its installed renewable energy capacity from 3 GW to 6 GW between 2022 and 2025. The Al Dhafra Solar PV project alone contributes 2 GW, making it one of the worlds largest single-site solar plants.',
 ARRAY['climate', 'renewable-energy', 'solar', 'energy-transition'], 0.78, 76, 'MEDIUM', 'AE', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000025'),

('44000000-0000-4000-8000-000000000002',
 'Saudi Arabia NEOM Green Hydrogen: $8.4 Billion Project on Track',
 'https://iea.org/reports/saudi-neom-hydrogen', 'Dr. Khalid bin Nasser', NOW() - INTERVAL '3 days',
 'International Energy Agency', 88, 'NEOMs green hydrogen plant will produce 600 tons of hydrogen daily by 2026.',
 'Saudi Arabias NEOM Green Hydrogen Company is on track to begin production in 2026. The $8.4 billion facility will produce 600 tons of green hydrogen daily using 4 GW of wind and solar power.',
 ARRAY['climate', 'clean-energy', 'hydrogen', 'energy-transition'], 0.87, 88, 'HIGH', 'SA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('44000000-0000-4000-8000-000000000003',
 'Israel Dead Sea Shrinking: Water Level Drops 1 Meter Per Year',
 'https://nature.com/dead-sea-2025', 'Dr. Yael Cohen', NOW() - INTERVAL '4 days',
 'Nature', 92, 'Dead Sea surface level dropping 1m annually; could disappear entirely by 2100.',
 'A comprehensive study in Nature documents that the Dead Sea surface level is declining by approximately 1 meter per year. The combination of climate change reducing inflows and industrial mineral extraction threatens the lakes complete disappearance by 2100.',
 ARRAY['climate', 'water-stress', 'adaptation', 'climate-indicators'], 0.91, 92, 'HIGH', 'IL', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000006'),

('44000000-0000-4000-8000-000000000004',
 'Jordan Water Desalination: Red Sea-Dead Sea Project Advances',
 'https://climatechangenews.com/jordan-desalination', 'Rami Khoury', NOW() - INTERVAL '5 days',
 'Climate Home News', 75, 'Jordans Aqaba desalination plant will produce 300 million cubic meters annually.',
 'Jordans Red Sea-Dead Sea desalination project has broken ground, with the Aqaba plant expected to produce 300 million cubic meters of freshwater annually. The project addresses Jordans status as the worlds second most water-scarce country.',
 ARRAY['climate', 'water-stress', 'adaptation', 'sustainability'], 0.77, 75, 'MEDIUM', 'JO', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('44000000-0000-4000-8000-000000000005',
 'Qatar Sustainable World Cup Legacy: Carbon-Neutral Stadium Technology',
 'https://climatechangenews.com/qatar-stadiums-2025', 'Hassan Al-Thani', NOW() - INTERVAL '6 days',
 'Climate Home News', 72, 'Qatars World Cup stadiums now operate as carbon-neutral community venues.',
 'Qatars FIFA World Cup stadiums have been converted into carbon-neutral community venues using solar cooling technology. The innovative district cooling systems reduce energy consumption by 40% compared to conventional air conditioning.',
 ARRAY['climate', 'sustainability', 'clean-energy', 'adaptation'], 0.74, 72, 'MEDIUM', 'QA', 3, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('44000000-0000-4000-8000-000000000006',
 'Kuwait Extreme Heat: 54C Record Raises Habitability Concerns',
 'https://climatechangenews.com/kuwait-heat-2025', 'Fatima Al-Salem', NOW() - INTERVAL '1 day',
 'Climate Home News', 80, 'Kuwait records 54C, among the highest temperatures ever reliably measured on Earth.',
 'Kuwait recorded a temperature of 54C in Mitribah, among the highest temperatures ever reliably measured on Earth. Climate models project that parts of the Persian Gulf region may become uninhabitable for outdoor work during summer months by 2050.',
 ARRAY['climate', 'temperature', 'adaptation', 'climate-indicators'], 0.82, 80, 'HIGH', 'KW', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('44000000-0000-4000-8000-000000000007',
 'Iran Lake Urmia Recovery: Water Volume Up 40% After Restoration',
 'https://unep.org/iran-urmia-2025', 'Dr. Mehdi Hosseini', NOW() - INTERVAL '7 days',
 'UNEP Africa', 84, 'Lake Urmias water volume has increased 40% following a decade-long restoration effort.',
 'UNEP reports that Irans Lake Urmia, once on the brink of disappearing, has seen a 40% increase in water volume following a decade of restoration efforts including upstream water management and reduced agricultural extraction.',
 ARRAY['climate', 'water-stress', 'conservation', 'adaptation'], 0.83, 84, 'HIGH', 'IR', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000018'),

('44000000-0000-4000-8000-000000000008',
 'UAE Cloud Seeding Program: 256 Missions in 2025',
 'https://masdar.ae/cloud-seeding-2025', 'Sara Al-Mansoori', NOW() - INTERVAL '3 days',
 'Masdar UAE', 68, 'UAE conducted 256 cloud seeding operations in 2025, claiming 15% rainfall increase.',
 'The UAE National Center of Meteorology conducted 256 cloud seeding operations in the first half of 2025, claiming a 15% increase in rainfall. Independent verification of cloud seeding effectiveness remains contested in climate science.',
 ARRAY['climate', 'adaptation', 'water-stress', 'technology'], 0.70, 68, 'MEDIUM', 'AE', 3, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000025'),

('44000000-0000-4000-8000-000000000009',
 'Saudi Arabia Mangrove Planting: 100 Million Trees Coastal Defense',
 'https://climatechangenews.com/saudi-mangroves', 'Omar Al-Faisal', NOW() - INTERVAL '4 days',
 'Climate Home News', 74, 'Saudi Arabia plants 100 million mangrove trees along Red Sea coast for natural defense.',
 'Saudi Arabia has begun an ambitious program to plant 100 million mangrove trees along the Red Sea coast. The mangroves serve as natural coastal defenses, carbon sinks, and marine nurseries in line with the Saudi Green Initiative.',
 ARRAY['climate', 'conservation', 'adaptation', 'biodiversity'], 0.76, 74, 'MEDIUM', 'SA', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000019'),

('44000000-0000-4000-8000-000000000010',
 'Israel Solar Innovation: Perovskite Cells Reach 33% Efficiency',
 'https://nature.com/israel-perovskite-2025', 'Dr. David Levy', NOW() - INTERVAL '2 days',
 'Nature', 93, 'Israeli researchers achieve 33% efficiency in tandem perovskite-silicon solar cells.',
 'Researchers at the Weizmann Institute have achieved a world-record 33% efficiency in tandem perovskite-silicon solar cells. The breakthrough could reduce solar electricity costs by 30% when commercialized.',
 ARRAY['climate', 'renewable-energy', 'solar', 'clean-energy'], 0.92, 93, 'HIGH', 'IL', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000006')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- ADDITIONAL EUROPE ARTICLES (to ensure 10+ with full data)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id) VALUES

('45000000-0000-4000-8000-000000000001',
 'Spain Desertification: 75% of Territory at Risk',
 'https://nature.com/spain-desertification-2025', 'Dr. Miguel Gonzalez', NOW() - INTERVAL '2 days',
 'Nature', 89, '75% of Spain faces desertification risk as temperatures rise and rainfall declines.',
 'A comprehensive study shows 75% of Spanish territory is at risk of desertification. Southeastern Spain has already seen a 20% decline in annual rainfall since 1990. The Segura and Jucar river basins face critical water stress.',
 ARRAY['climate', 'water-stress', 'temperature', 'adaptation'], 0.88, 89, 'HIGH', 'ES', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000006'),

('45000000-0000-4000-8000-000000000002',
 'Denmark Offshore Wind: North Sea Energy Island Construction Begins',
 'https://iea.org/reports/denmark-energy-island', 'Lars Andersen', NOW() - INTERVAL '3 days',
 'International Energy Agency', 91, 'Denmark begins construction of worlds first artificial energy island in the North Sea.',
 'Denmark has commenced construction of the worlds first artificial energy island in the North Sea. The island will serve as a hub for 10 GW of offshore wind capacity, enough to power 10 million European households.',
 ARRAY['climate', 'renewable-energy', 'wind-power', 'energy-transition'], 0.90, 91, 'HIGH', 'DK', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('45000000-0000-4000-8000-000000000003',
 'Swiss Alps Glacier Monitoring: 10% Volume Lost in 2 Years',
 'https://nature.com/swiss-alps-glaciers', 'Prof. Hans Mueller', NOW() - INTERVAL '4 days',
 'Nature', 94, 'Swiss glaciers lost 10% of remaining volume in 2023-2024 alone.',
 'The Swiss Academy of Sciences reports that Swiss glaciers lost an extraordinary 10% of their remaining volume in just two years (2023-2024). The rate of loss is unprecedented in the 150-year measurement record.',
 ARRAY['climate', 'arctic', 'temperature', 'climate-indicators'], 0.93, 94, 'HIGH', 'CH', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000006')

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- CLAIMS FOR ALL NEW ARTICLES (representative sample, 3 per article)
-- Using continent-based ID ranges for organization
-- ============================================================

-- North America claims
INSERT INTO claims (claim_id, article_id, claim_text, claim_context, claim_type, claim_category, location_country, created_at) VALUES
-- US Wildfire
('50000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001', '8.5 million acres burned in western US during 2025 fire season', 'NIFC fire statistics comparison', 'statistical', 'statistical', 'US', NOW()),
('50000000-0000-4000-8000-000000000002', '40000000-0000-4000-8000-000000000001', 'Climate change has doubled the area burned by wildfires since 1990', 'Climate attribution studies', 'scientific_causal', 'scientific_causal', 'US', NOW()),
('50000000-0000-4000-8000-000000000003', '40000000-0000-4000-8000-000000000001', 'Drought conditions were the most severe in 1200 years', 'Paleoclimate reconstructions', 'statistical', 'statistical', 'US', NOW()),
-- Canada Arctic
('50000000-0000-4000-8000-000000000004', '40000000-0000-4000-8000-000000000002', 'Northwest Passage ice-free for 4 consecutive months', 'Canadian Ice Service monitoring', 'statistical', 'statistical', 'CA', NOW()),
('50000000-0000-4000-8000-000000000005', '40000000-0000-4000-8000-000000000002', 'Arctic shipping routes could cut Europe-Asia transit by 40%', 'Maritime transport analysis', 'predictive', 'predictive', 'CA', NOW()),
('50000000-0000-4000-8000-000000000006', '40000000-0000-4000-8000-000000000002', 'September Arctic sea ice has declined 13% per decade since 1979', 'NSIDC satellite records', 'statistical', 'statistical', 'CA', NOW()),
-- Mexico Water
('50000000-0000-4000-8000-000000000007', '40000000-0000-4000-8000-000000000003', '30 million people affected by water rationing in central Mexico', 'CONAGUA water authority reports', 'statistical', 'statistical', 'MX', NOW()),
('50000000-0000-4000-8000-000000000008', '40000000-0000-4000-8000-000000000003', 'Reservoirs at 25% capacity, worst in 50 years', 'CONAGUA dam level monitoring', 'statistical', 'statistical', 'MX', NOW()),
('50000000-0000-4000-8000-000000000009', '40000000-0000-4000-8000-000000000003', 'North American monsoon pattern shifting due to warming', 'Climate model projections', 'scientific_causal', 'scientific_causal', 'MX', NOW()),
-- US IRA
('50000000-0000-4000-8000-000000000010', '40000000-0000-4000-8000-000000000004', 'IRA catalyzed $280 billion in private clean energy investment', 'Treasury Department analysis', 'statistical', 'statistical', 'US', NOW()),
('50000000-0000-4000-8000-000000000011', '40000000-0000-4000-8000-000000000004', '300,000 new clean energy jobs created across 44 states', 'DOE employment tracking', 'statistical', 'statistical', 'US', NOW()),
('50000000-0000-4000-8000-000000000012', '40000000-0000-4000-8000-000000000004', 'US emissions reduced 5% since IRA passage', 'EPA greenhouse gas inventory', 'statistical', 'statistical', 'US', NOW()),

-- Latin America claims
('51000000-0000-4000-8000-000000000001', '41000000-0000-4000-8000-000000000001', 'Amazon deforestation dropped 45% year-over-year', 'INPE PRODES satellite monitoring', 'statistical', 'statistical', 'BR', NOW()),
('51000000-0000-4000-8000-000000000002', '41000000-0000-4000-8000-000000000001', 'Indigenous territory protections reduced deforestation by 60% in protected areas', 'FUNAI land demarcation data', 'statistical', 'statistical', 'BR', NOW()),
('51000000-0000-4000-8000-000000000003', '41000000-0000-4000-8000-000000000001', 'Amazon still emits more carbon than it absorbs in degraded areas', 'Nature study on Amazon carbon balance', 'scientific_causal', 'scientific_causal', 'BR', NOW()),
('51000000-0000-4000-8000-000000000004', '41000000-0000-4000-8000-000000000003', 'Colombia targets 30% non-hydro renewable electricity by 2030', 'Colombian energy ministry policy', 'policy', 'policy', 'CO', NOW()),
('51000000-0000-4000-8000-000000000005', '41000000-0000-4000-8000-000000000004', 'Chile produces 40% of Latin Americas green hydrogen', 'IEA regional hydrogen tracker', 'statistical', 'statistical', 'CL', NOW()),
('51000000-0000-4000-8000-000000000006', '41000000-0000-4000-8000-000000000005', 'Andean glaciers lost 55% of volume since 1970', 'INAIGEM glacier inventory', 'statistical', 'statistical', 'PE', NOW()),
('51000000-0000-4000-8000-000000000007', '41000000-0000-4000-8000-000000000006', 'Cerrado deforestation emissions now exceed Amazon', 'INPE DETER monitoring', 'statistical', 'statistical', 'BR', NOW()),
('51000000-0000-4000-8000-000000000008', '41000000-0000-4000-8000-000000000007', 'Galapagos waters warmed 1.5C above historical average', 'Charles Darwin Foundation monitoring', 'statistical', 'statistical', 'EC', NOW()),

-- Africa claims
('52000000-0000-4000-8000-000000000001', '42000000-0000-4000-8000-000000000001', 'Kenya generates 1 GW of geothermal power, 45% of national electricity', 'KenGen operational data', 'statistical', 'statistical', 'KE', NOW()),
('52000000-0000-4000-8000-000000000002', '42000000-0000-4000-8000-000000000002', '2.5 million displaced by flooding in Nigeria in 2025', 'NEMA disaster assessment', 'statistical', 'statistical', 'NG', NOW()),
('52000000-0000-4000-8000-000000000003', '42000000-0000-4000-8000-000000000002', 'Climate change intensified Niger-Benue basin rainfall by 20%', 'Attribution study by World Weather Attribution', 'scientific_causal', 'scientific_causal', 'NG', NOW()),
('52000000-0000-4000-8000-000000000004', '42000000-0000-4000-8000-000000000003', 'South Africa mobilized $8.5 billion for coal phase-out', 'JET Partnership financial tracking', 'statistical', 'statistical', 'ZA', NOW()),
('52000000-0000-4000-8000-000000000005', '42000000-0000-4000-8000-000000000004', 'Ghana cocoa production declined 25% in five years', 'COCOBOD production statistics', 'statistical', 'statistical', 'GH', NOW()),
('52000000-0000-4000-8000-000000000006', '42000000-0000-4000-8000-000000000005', '70% coral bleaching in Tanzanian reef systems', 'TCMP marine survey 2025', 'statistical', 'statistical', 'TZ', NOW()),
('52000000-0000-4000-8000-000000000007', '42000000-0000-4000-8000-000000000007', 'Egypt Benban Solar Park produces 1.65 GW', 'NREA operational data', 'statistical', 'statistical', 'EG', NOW()),
('52000000-0000-4000-8000-000000000008', '42000000-0000-4000-8000-000000000009', 'Senegals Great Green Wall section 35% complete', 'ANGMV progress report', 'statistical', 'statistical', 'SN', NOW()),

-- Asia claims
('53000000-0000-4000-8000-000000000001', '43000000-0000-4000-8000-000000000001', 'China installed 300 GW of solar capacity in 2024', 'NEA installation statistics', 'statistical', 'statistical', 'CN', NOW()),
('53000000-0000-4000-8000-000000000002', '43000000-0000-4000-8000-000000000002', '52C recorded in Rajasthan, highest ever in India', 'IMD verified temperature records', 'statistical', 'statistical', 'IN', NOW()),
('53000000-0000-4000-8000-000000000003', '43000000-0000-4000-8000-000000000002', 'Over 1,200 heat-related deaths across northern India', 'State health department reports', 'statistical', 'statistical', 'IN', NOW()),
('53000000-0000-4000-8000-000000000004', '43000000-0000-4000-8000-000000000003', 'Japan launches worlds first commercial liquefied hydrogen supply chain', 'METI energy reports', 'statistical', 'statistical', 'JP', NOW()),
('53000000-0000-4000-8000-000000000005', '43000000-0000-4000-8000-000000000005', 'Indonesian peatland fires released 500 million tons of CO2 in 2025', 'BMKG emission estimates', 'statistical', 'statistical', 'ID', NOW()),
('53000000-0000-4000-8000-000000000006', '43000000-0000-4000-8000-000000000009', '90% of Great Barrier Reef shows bleaching signs', 'AIMS aerial survey data', 'statistical', 'statistical', 'AU', NOW()),
('53000000-0000-4000-8000-000000000007', '43000000-0000-4000-8000-000000000010', 'Fox and Franz Josef glaciers retreated 800m in 5 years', 'NIWA End of Summer Snowline Survey', 'statistical', 'statistical', 'NZ', NOW()),
('53000000-0000-4000-8000-000000000008', '43000000-0000-4000-8000-000000000012', 'India reaches 100 GW rooftop solar capacity', 'MNRE capacity tracker', 'statistical', 'statistical', 'IN', NOW()),

-- Middle East claims
('54000000-0000-4000-8000-000000000001', '44000000-0000-4000-8000-000000000001', 'UAE doubled renewable capacity from 3 GW to 6 GW in three years', 'IRENA capacity statistics', 'statistical', 'statistical', 'AE', NOW()),
('54000000-0000-4000-8000-000000000002', '44000000-0000-4000-8000-000000000002', 'NEOM will produce 600 tons of green hydrogen daily by 2026', 'NEOM project prospectus', 'predictive', 'predictive', 'SA', NOW()),
('54000000-0000-4000-8000-000000000003', '44000000-0000-4000-8000-000000000003', 'Dead Sea level dropping 1 meter per year', 'Israel Geological Survey monitoring', 'statistical', 'statistical', 'IL', NOW()),
('54000000-0000-4000-8000-000000000004', '44000000-0000-4000-8000-000000000006', '54C recorded in Kuwait, among highest ever reliably measured', 'WMO verified records', 'statistical', 'statistical', 'KW', NOW()),
('54000000-0000-4000-8000-000000000005', '44000000-0000-4000-8000-000000000007', 'Lake Urmia water volume increased 40% after restoration', 'UNEP restoration assessment', 'statistical', 'statistical', 'IR', NOW()),
('54000000-0000-4000-8000-000000000006', '44000000-0000-4000-8000-000000000010', 'Perovskite-silicon tandem cells reach 33% efficiency', 'Weizmann Institute peer-reviewed results', 'statistical', 'statistical', 'IL', NOW()),

-- Additional Europe claims
('55000000-0000-4000-8000-000000000001', '45000000-0000-4000-8000-000000000001', '75% of Spanish territory at risk of desertification', 'CSIC desertification study', 'statistical', 'statistical', 'ES', NOW()),
('55000000-0000-4000-8000-000000000002', '45000000-0000-4000-8000-000000000002', 'Denmark energy island will host 10 GW offshore wind', 'Danish Energy Agency plans', 'predictive', 'predictive', 'DK', NOW()),
('55000000-0000-4000-8000-000000000003', '45000000-0000-4000-8000-000000000003', 'Swiss glaciers lost 10% of remaining volume in 2 years', 'GLAMOS measurement network', 'statistical', 'statistical', 'CH', NOW())

ON CONFLICT (claim_id) DO NOTHING;


-- ============================================================
-- FACT CHECKS FOR NEW CLAIMS (representative sample)
-- ============================================================

INSERT INTO fact_checks (fact_check_id, claim_id, verification_status, confidence_score, justification, evidence, verified_at, decomposed_confidence, evidence_chain) VALUES

-- North America
('60000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'VERIFIED', 0.92,
 'NIFC data confirms 8.3 million acres burned, consistent with 8.5M reported figure within measurement uncertainty.',
 '{"sources": ["NIFC", "NASA FIRMS"], "exact_figure": "8.3M acres"}', NOW(),
 '{"model_confidence": 0.93, "source_quality": 0.95, "evidence_breadth": 0.90, "cross_reference_score": 0.91, "temporal_relevance": 0.90, "overall": 0.92}',
 '[{"step_number": 1, "description": "NIFC confirmed 8.3M acres, within 3% of reported 8.5M", "source": "NIFC", "source_url": "https://www.nifc.gov/fire-information/statistics", "confidence": 0.94, "supports_claim": true}]'),

('60000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000004', 'VERIFIED', 0.95,
 'Canadian Ice Service confirms 4 consecutive ice-free months in Northwest Passage, longest recorded.',
 '{"sources": ["Canadian Ice Service", "NSIDC"]}', NOW(),
 '{"model_confidence": 0.96, "source_quality": 0.97, "evidence_breadth": 0.93, "cross_reference_score": 0.94, "temporal_relevance": 0.92, "overall": 0.95}',
 '[{"step_number": 1, "description": "4-month ice-free period confirmed by Canadian Ice Service satellite monitoring", "source": "Canadian Ice Service", "source_url": "https://ice-glaces.ec.gc.ca/", "confidence": 0.96, "supports_claim": true}]'),

('60000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000007', 'VERIFIED', 0.85,
 'CONAGUA confirms approximately 28 million affected; 30M is a reasonable rounded estimate.',
 '{"sources": ["CONAGUA", "CENAPRED"]}', NOW(),
 '{"model_confidence": 0.86, "source_quality": 0.88, "evidence_breadth": 0.82, "cross_reference_score": 0.84, "temporal_relevance": 0.85, "overall": 0.85}',
 '[{"step_number": 1, "description": "CONAGUA reports 28M affected, consistent with 30M estimate", "source": "CONAGUA", "source_url": "https://www.gob.mx/conagua", "confidence": 0.87, "supports_claim": true}]'),

('60000000-0000-4000-8000-000000000004', '50000000-0000-4000-8000-000000000010', 'VERIFIED', 0.91,
 'Treasury Department confirms $278B in tracked clean energy investment since IRA passage.',
 '{"sources": ["US Treasury", "Clean Investment Monitor"]}', NOW(),
 '{"model_confidence": 0.92, "source_quality": 0.94, "evidence_breadth": 0.89, "cross_reference_score": 0.90, "temporal_relevance": 0.88, "overall": 0.91}',
 '[{"step_number": 1, "description": "$278B confirmed, $280B is reasonable rounded figure", "source": "US Treasury", "source_url": "https://home.treasury.gov/", "confidence": 0.93, "supports_claim": true}]'),

-- Latin America
('61000000-0000-4000-8000-000000000001', '51000000-0000-4000-8000-000000000001', 'VERIFIED', 0.94,
 'INPE PRODES data confirms 44.7% reduction in Amazon deforestation year-over-year.',
 '{"sources": ["INPE PRODES", "Global Forest Watch"], "exact_figure": "44.7%"}', NOW(),
 '{"model_confidence": 0.95, "source_quality": 0.97, "evidence_breadth": 0.92, "cross_reference_score": 0.93, "temporal_relevance": 0.91, "overall": 0.94}',
 '[{"step_number": 1, "description": "44.7% deforestation reduction confirmed by PRODES satellite system", "source": "INPE PRODES", "source_url": "http://www.obt.inpe.br/OBT/assuntos/programas/amazonia/prodes", "confidence": 0.96, "supports_claim": true}]'),

('61000000-0000-4000-8000-000000000002', '51000000-0000-4000-8000-000000000005', 'VERIFIED', 0.88,
 'IEA hydrogen tracker confirms Chile produces 38-42% of Latin American green hydrogen output.',
 '{"sources": ["IEA", "Chilean Ministry of Energy"]}', NOW(),
 '{"model_confidence": 0.89, "source_quality": 0.92, "evidence_breadth": 0.85, "cross_reference_score": 0.87, "temporal_relevance": 0.88, "overall": 0.88}',
 '[{"step_number": 1, "description": "38-42% range confirmed, 40% is within bounds", "source": "IEA", "source_url": "https://www.iea.org/", "confidence": 0.90, "supports_claim": true}]'),

('61000000-0000-4000-8000-000000000003', '51000000-0000-4000-8000-000000000006', 'VERIFIED', 0.90,
 'INAIGEM glacier inventory confirms 53-57% volume loss since 1970, consistent with 55% claim.',
 '{"sources": ["INAIGEM", "WGMS"]}', NOW(),
 '{"model_confidence": 0.91, "source_quality": 0.93, "evidence_breadth": 0.88, "cross_reference_score": 0.89, "temporal_relevance": 0.87, "overall": 0.90}',
 '[{"step_number": 1, "description": "53-57% volume loss confirmed by glacier inventory", "source": "INAIGEM", "source_url": "https://www.gob.pe/inaigem", "confidence": 0.92, "supports_claim": true}]'),

-- Africa
('62000000-0000-4000-8000-000000000001', '52000000-0000-4000-8000-000000000001', 'VERIFIED', 0.93,
 'KenGen reports 985 MW operational geothermal capacity, rounded to 1 GW. 44.8% of national electricity.',
 '{"sources": ["KenGen", "EPRA Kenya"]}', NOW(),
 '{"model_confidence": 0.94, "source_quality": 0.96, "evidence_breadth": 0.91, "cross_reference_score": 0.92, "temporal_relevance": 0.90, "overall": 0.93}',
 '[{"step_number": 1, "description": "985 MW geothermal capacity confirmed, 44.8% of electricity", "source": "KenGen", "source_url": "https://www.kengen.co.ke/", "confidence": 0.95, "supports_claim": true}]'),

('62000000-0000-4000-8000-000000000002', '52000000-0000-4000-8000-000000000002', 'VERIFIED', 0.89,
 'NEMA confirmed 2.4 million displaced, consistent with 2.5M report within assessment uncertainty.',
 '{"sources": ["NEMA Nigeria", "OCHA"]}', NOW(),
 '{"model_confidence": 0.90, "source_quality": 0.92, "evidence_breadth": 0.87, "cross_reference_score": 0.88, "temporal_relevance": 0.88, "overall": 0.89}',
 '[{"step_number": 1, "description": "2.4M displaced confirmed by NEMA, 2.5M within uncertainty", "source": "NEMA Nigeria", "source_url": "https://nema.gov.ng/", "confidence": 0.91, "supports_claim": true}]'),

('62000000-0000-4000-8000-000000000003', '52000000-0000-4000-8000-000000000006', 'VERIFIED', 0.91,
 'TCMP marine surveys confirm 68-72% bleaching across surveyed reef systems.',
 '{"sources": ["TCMP", "WCS Tanzania"]}', NOW(),
 '{"model_confidence": 0.92, "source_quality": 0.94, "evidence_breadth": 0.89, "cross_reference_score": 0.90, "temporal_relevance": 0.89, "overall": 0.91}',
 '[{"step_number": 1, "description": "68-72% bleaching confirmed, 70% is midpoint of range", "source": "TCMP", "source_url": "https://www.tanzaniamarineconservation.org/", "confidence": 0.93, "supports_claim": true}]'),

-- Asia
('63000000-0000-4000-8000-000000000001', '53000000-0000-4000-8000-000000000001', 'VERIFIED', 0.94,
 'NEA data confirms 293 GW installed in 2024, reported as ~300 GW.',
 '{"sources": ["NEA China", "IEA PVPS"]}', NOW(),
 '{"model_confidence": 0.95, "source_quality": 0.96, "evidence_breadth": 0.92, "cross_reference_score": 0.93, "temporal_relevance": 0.91, "overall": 0.94}',
 '[{"step_number": 1, "description": "293 GW confirmed by NEA, 300 GW is reasonable rounding", "source": "NEA China", "source_url": "http://www.nea.gov.cn/", "confidence": 0.96, "supports_claim": true}]'),

('63000000-0000-4000-8000-000000000002', '53000000-0000-4000-8000-000000000002', 'VERIFIED', 0.87,
 'IMD confirmed 52.3C at Phalodi but accuracy debated by some international meteorologists.',
 '{"sources": ["IMD", "WMO"], "caveat": "measurement accuracy under review"}', NOW(),
 '{"model_confidence": 0.88, "source_quality": 0.90, "evidence_breadth": 0.84, "cross_reference_score": 0.86, "temporal_relevance": 0.87, "overall": 0.87}',
 '[{"step_number": 1, "description": "52.3C recorded by IMD at Phalodi, WMO review pending", "source": "IMD", "source_url": "https://mausam.imd.gov.in/", "confidence": 0.89, "supports_claim": true}]'),

('63000000-0000-4000-8000-000000000003', '53000000-0000-4000-8000-000000000006', 'VERIFIED', 0.96,
 'AIMS aerial surveys confirm 89-91% bleaching across 1,036 reefs surveyed.',
 '{"sources": ["AIMS", "GBRMPA"]}', NOW(),
 '{"model_confidence": 0.97, "source_quality": 0.98, "evidence_breadth": 0.95, "cross_reference_score": 0.96, "temporal_relevance": 0.93, "overall": 0.96}',
 '[{"step_number": 1, "description": "89-91% bleaching confirmed across 1,036 surveyed reefs", "source": "AIMS", "source_url": "https://www.aims.gov.au/", "confidence": 0.97, "supports_claim": true}]'),

('63000000-0000-4000-8000-000000000004', '53000000-0000-4000-8000-000000000007', 'VERIFIED', 0.93,
 'NIWA survey confirms 790m retreat for Fox and 815m for Franz Josef over 5 years.',
 '{"sources": ["NIWA", "Victoria University of Wellington"]}', NOW(),
 '{"model_confidence": 0.94, "source_quality": 0.95, "evidence_breadth": 0.91, "cross_reference_score": 0.92, "temporal_relevance": 0.91, "overall": 0.93}',
 '[{"step_number": 1, "description": "790-815m retreat confirmed, 800m is average of both glaciers", "source": "NIWA", "source_url": "https://niwa.co.nz/", "confidence": 0.95, "supports_claim": true}]'),

-- Middle East
('64000000-0000-4000-8000-000000000001', '54000000-0000-4000-8000-000000000001', 'VERIFIED', 0.86,
 'IRENA statistics confirm UAE capacity increase from 2.8 GW to 5.8 GW, reported as 3 to 6 GW.',
 '{"sources": ["IRENA", "UAE MOEI"]}', NOW(),
 '{"model_confidence": 0.87, "source_quality": 0.90, "evidence_breadth": 0.83, "cross_reference_score": 0.85, "temporal_relevance": 0.85, "overall": 0.86}',
 '[{"step_number": 1, "description": "2.8 to 5.8 GW confirmed, 3 to 6 GW is rounded", "source": "IRENA", "source_url": "https://www.irena.org/", "confidence": 0.88, "supports_claim": true}]'),

('64000000-0000-4000-8000-000000000002', '54000000-0000-4000-8000-000000000003', 'VERIFIED', 0.94,
 'Israel Geological Survey confirms 0.98-1.05m annual decline in Dead Sea level since 2010.',
 '{"sources": ["Israel Geological Survey", "Nature Geoscience"]}', NOW(),
 '{"model_confidence": 0.95, "source_quality": 0.96, "evidence_breadth": 0.92, "cross_reference_score": 0.93, "temporal_relevance": 0.91, "overall": 0.94}',
 '[{"step_number": 1, "description": "0.98-1.05m annual decline confirmed, 1m is midpoint", "source": "Israel Geological Survey", "source_url": "https://www.gov.il/en/departments/geological_survey", "confidence": 0.96, "supports_claim": true}]'),

('64000000-0000-4000-8000-000000000003', '54000000-0000-4000-8000-000000000004', 'VERIFIED', 0.90,
 'WMO confirmed 53.9C measurement at Mitribah, pending final review for 54C.',
 '{"sources": ["WMO", "Kuwait Met Department"]}', NOW(),
 '{"model_confidence": 0.91, "source_quality": 0.93, "evidence_breadth": 0.88, "cross_reference_score": 0.89, "temporal_relevance": 0.88, "overall": 0.90}',
 '[{"step_number": 1, "description": "53.9C confirmed, 54C within measurement uncertainty", "source": "WMO", "source_url": "https://wmo.int/", "confidence": 0.92, "supports_claim": true}]'),

('64000000-0000-4000-8000-000000000004', '54000000-0000-4000-8000-000000000006', 'VERIFIED', 0.95,
 'Weizmann Institute peer-reviewed results confirm 33.2% efficiency in certified testing.',
 '{"sources": ["Weizmann Institute", "Nature Energy"]}', NOW(),
 '{"model_confidence": 0.96, "source_quality": 0.98, "evidence_breadth": 0.93, "cross_reference_score": 0.94, "temporal_relevance": 0.93, "overall": 0.95}',
 '[{"step_number": 1, "description": "33.2% efficiency confirmed by NREL certified testing", "source": "Weizmann Institute", "source_url": "https://www.weizmann.ac.il/", "confidence": 0.97, "supports_claim": true}]'),

-- Additional Europe
('65000000-0000-4000-8000-000000000001', '55000000-0000-4000-8000-000000000001', 'VERIFIED', 0.91,
 'CSIC study confirms 74.8% of Spanish territory at desertification risk, consistent with 75%.',
 '{"sources": ["CSIC", "UNCCD"]}', NOW(),
 '{"model_confidence": 0.92, "source_quality": 0.94, "evidence_breadth": 0.89, "cross_reference_score": 0.90, "temporal_relevance": 0.89, "overall": 0.91}',
 '[{"step_number": 1, "description": "74.8% desertification risk confirmed by CSIC assessment", "source": "CSIC", "source_url": "https://www.csic.es/", "confidence": 0.93, "supports_claim": true}]'),

('65000000-0000-4000-8000-000000000002', '55000000-0000-4000-8000-000000000003', 'VERIFIED', 0.96,
 'GLAMOS confirms 9.8% volume loss in 2023-2024, consistent with 10% report.',
 '{"sources": ["GLAMOS", "ETH Zurich"]}', NOW(),
 '{"model_confidence": 0.97, "source_quality": 0.98, "evidence_breadth": 0.95, "cross_reference_score": 0.96, "temporal_relevance": 0.94, "overall": 0.96}',
 '[{"step_number": 1, "description": "9.8% volume loss confirmed by GLAMOS measurement network", "source": "GLAMOS", "source_url": "https://glamos.ch/", "confidence": 0.97, "supports_claim": true}]')

ON CONFLICT (fact_check_id) DO NOTHING;


-- ============================================================
-- UPDATE ARTICLE COUNTS (sync claims_count with actual claims)
-- ============================================================

UPDATE articles a SET
  claims_count = (SELECT COUNT(*) FROM claims c WHERE c.article_id = a.article_id),
  verified_claims_count = (
    SELECT COUNT(*) FROM claims c
    JOIN fact_checks fc ON fc.claim_id = c.claim_id
    WHERE c.article_id = a.article_id AND fc.verification_status IN ('VERIFIED', 'PARTIALLY_VERIFIED')
  )
WHERE a.article_id IN (
  SELECT DISTINCT article_id FROM claims
  WHERE claim_id LIKE '5%' OR claim_id LIKE '51%' OR claim_id LIKE '52%'
     OR claim_id LIKE '53%' OR claim_id LIKE '54%' OR claim_id LIKE '55%'
);

COMMIT;
