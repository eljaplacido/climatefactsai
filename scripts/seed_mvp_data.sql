-- MVP Demo Data: Articles, Claims, Fact-Checks
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < scripts/seed_mvp_data.sql

BEGIN;

-- ============================================================
-- SOURCE PROFILES (insert first, no FK dependencies)
-- ============================================================

INSERT INTO source_profiles (source_id, source_name, source_domain, credibility_score, editorial_standards, fact_check_record, transparency_level, total_articles_analyzed, average_reliability_score, total_claims_verified, total_claims_disputed, false_claim_rate, source_type, country_code, description, website_url) VALUES
('a0000000-0000-4000-8000-000000000001', 'NASA', 'climate.nasa.gov', 96, 'rigorous', 'excellent', 'high', 145, 95.2, 420, 8, 0.019, 'government_agency', NULL, 'National Aeronautics and Space Administration climate research division', 'https://climate.nasa.gov'),
('a0000000-0000-4000-8000-000000000002', 'NOAA', 'noaa.gov', 94, 'rigorous', 'excellent', 'high', 120, 93.8, 380, 12, 0.031, 'government_agency', NULL, 'National Oceanic and Atmospheric Administration', 'https://www.noaa.gov'),
('a0000000-0000-4000-8000-000000000003', 'IPCC', 'ipcc.ch', 97, 'rigorous', 'excellent', 'high', 85, 96.5, 290, 5, 0.017, 'research_institution', NULL, 'Intergovernmental Panel on Climate Change', 'https://www.ipcc.ch'),
('a0000000-0000-4000-8000-000000000004', 'European Commission', 'ec.europa.eu', 88, 'rigorous', 'good', 'high', 95, 88.4, 210, 18, 0.079, 'government_agency', NULL, 'EU executive body responsible for climate policy', 'https://ec.europa.eu'),
('a0000000-0000-4000-8000-000000000005', 'International Energy Agency', 'iea.org', 90, 'rigorous', 'excellent', 'high', 110, 90.1, 340, 15, 0.042, 'research_institution', NULL, 'International energy policy advisor', 'https://www.iea.org'),
('a0000000-0000-4000-8000-000000000006', 'Nature', 'nature.com', 95, 'rigorous', 'excellent', 'high', 200, 94.5, 580, 10, 0.017, 'research_institution', NULL, 'Premier scientific journal with peer-reviewed climate research', 'https://www.nature.com'),
('a0000000-0000-4000-8000-000000000007', 'Norwegian Road Federation', 'ofv.no', 85, 'moderate', 'good', 'moderate', 30, 86.2, 65, 5, 0.071, 'ngo', 'NO', 'Norwegian automotive industry association with transport statistics', 'https://ofv.no'),
('a0000000-0000-4000-8000-000000000008', 'SEAI', 'seai.ie', 82, 'moderate', 'good', 'high', 25, 83.5, 48, 3, 0.059, 'government_agency', 'IE', 'Sustainable Energy Authority of Ireland', 'https://www.seai.ie'),
('a0000000-0000-4000-8000-000000000009', 'Polish Climate Monitor', 'polishclimatemonitor.pl', 55, 'low', 'mixed', 'low', 15, 58.2, 20, 12, 0.375, 'blog', 'PL', 'Independent Polish climate reporting outlet', NULL),
('a0000000-0000-4000-8000-000000000010', 'YLE', 'yle.fi', 80, 'moderate', 'good', 'high', 65, 81.3, 140, 10, 0.067, 'news_outlet', 'FI', 'Finnish Broadcasting Company - public broadcaster', 'https://yle.fi')
ON CONFLICT (source_id) DO NOTHING;

-- ============================================================
-- SAMPLE ARTICLES (12 articles across EU countries)
-- ============================================================

INSERT INTO articles (article_id, title, url, author, published_date, source_name, source_credibility_score, excerpt, extracted_text, tags, content_relevance_score, reliability_score, overall_credibility, country_code, claims_count, verified_claims_count, claims_status, language_code, source_profile_id)
VALUES
('10000000-0000-4000-8000-000000000001',
 'Arctic Permafrost Thawing Accelerates: New Data Shows 150 Billion Tons of Carbon at Risk',
 'https://climate.nasa.gov/news/arctic-permafrost-2025', 'Dr. Sarah Chen', NOW() - INTERVAL '2 days',
 'NASA', 95, 'Recent satellite data reveals Arctic permafrost is thawing at unprecedented rates, potentially releasing massive amounts of methane and CO2.',
 'Recent satellite data from NASA reveals that Arctic permafrost is thawing at unprecedented rates. The analysis covers a 15-year period showing accelerating degradation patterns in Siberian and Canadian permafrost zones. An estimated 150 billion tons of carbon could be released if current trends continue.',
 ARRAY['climate', 'arctic', 'emissions', 'permafrost'], 0.96, 95, 'HIGH', 'FI', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000001'),

('10000000-0000-4000-8000-000000000002',
 'EU Green Deal Progress Report: Finland Leads Nordic Clean Energy Transition',
 'https://ec.europa.eu/green-deal/nordic-progress-2025', 'Anna Virtanen', NOW() - INTERVAL '1 day',
 'European Commission', 92, 'Finland ranks first among Nordic countries in implementing EU Green Deal targets, with 52% renewable energy share.',
 'The European Commission 2025 progress report highlights remarkable achievements in clean energy transition. With a 52% share of renewable energy in total consumption, Finland has surpassed its 2030 targets ahead of schedule. The report praises forest-based bioenergy and wind power investments.',
 ARRAY['climate', 'green-deal', 'sustainability', 'eu-policy'], 0.94, 92, 'HIGH', 'FI', 5, 4, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000004'),

('10000000-0000-4000-8000-000000000003',
 'Baltic Sea Acidification Threatens Marine Ecosystems',
 'https://noaa.gov/baltic-sea-ph-2025', 'Prof. Erik Lindstrom', NOW() - INTERVAL '3 days',
 'NOAA', 90, 'New research indicates Baltic Sea pH levels have dropped to levels not seen in centuries.',
 'NOAA and Finnish Meteorological Institute joint study shows alarming ocean acidification trends in the Baltic Sea. pH levels have decreased by 0.1 units since pre-industrial times, threatening shellfish populations and marine biodiversity.',
 ARRAY['climate', 'ocean', 'biodiversity', 'sea-ice'], 0.91, 90, 'HIGH', 'FI', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000002'),

('10000000-0000-4000-8000-000000000004',
 'Germany Achieves Record Renewable Energy Output in Q1 2025',
 'https://iea.org/reports/germany-renewables-2025', 'Klaus Weber', NOW() - INTERVAL '4 days',
 'International Energy Agency', 88, 'Germany generated 55% of electricity from renewable sources in Q1 2025.',
 'Germany has set a new record for renewable energy generation, with wind and solar contributing 55% of total electricity output during Q1 2025. This represents a 12% increase from the same period last year.',
 ARRAY['climate', 'renewable-energy', 'energy-transition', 'clean-energy'], 0.89, 88, 'HIGH', 'DE', 4, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000005'),

('10000000-0000-4000-8000-000000000005',
 'Swedish Forest Carbon Sink Declining Faster Than Expected',
 'https://nature.com/swedish-forests-carbon-2025', 'Dr. Lars Eriksson', NOW() - INTERVAL '5 days',
 'Nature', 85, 'Swedish boreal forests are losing carbon sequestration capacity due to increased logging and warming.',
 'A comprehensive study published in Nature reveals that Swedish boreal forests, once considered a reliable carbon sink, are losing their capacity to absorb CO2 at an accelerating rate. The study cites a 23% decrease in net carbon uptake since 2015.',
 ARRAY['climate', 'deforestation', 'conservation', 'bioeconomy'], 0.87, 85, 'HIGH', 'SE', 3, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000006'),

('10000000-0000-4000-8000-000000000006',
 'Norwegian EV Market Share Hits 92% in January 2025',
 'https://ofv.no/statistics/2025', 'Kristin Hagen', NOW() - INTERVAL '6 days',
 'Norwegian Road Federation', 94, 'Norway continues to lead global EV adoption with 92% of new car sales being fully electric.',
 'Norway has reached a new milestone in electric vehicle adoption. In January 2025, 92% of all new car registrations were fully electric vehicles, up from 82% in 2024.',
 ARRAY['climate', 'energy-transition', 'clean-energy', 'environmental-policy'], 0.93, 94, 'HIGH', 'NO', 3, 3, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000007'),

('10000000-0000-4000-8000-000000000007',
 'Mixed Claims About Carbon Capture in Poland Coal Regions',
 'https://polishclimatemonitor.pl/poland-ccs-mixed', 'Jan Kowalski', NOW() - INTERVAL '7 days',
 'Polish Climate Monitor', 60, 'Industry claims about CCS effectiveness in Polish coal regions face scrutiny from researchers.',
 'Industry-backed reports claim carbon capture and storage technology could extend the economic life of Polish coal mines while reducing emissions by 90%. Independent researchers dispute these figures, citing much lower real-world capture rates.',
 ARRAY['climate', 'emissions', 'environmental-policy'], 0.55, 60, 'MEDIUM', 'PL', 4, 1, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000009'),

('10000000-0000-4000-8000-000000000008',
 'Irish Wind Energy Sets New Production Record',
 'https://seai.ie/wind-energy-record-2025', 'Siobhan Murphy', NOW() - INTERVAL '8 days',
 'SEAI', 82, 'Ireland wind turbines generated enough electricity for 4.2 million homes during Storm Eowyn.',
 'The Sustainable Energy Authority of Ireland reports that during Storm Eowyn, wind turbines generated a record-breaking 5.4 GW of electricity, enough to power 4.2 million homes simultaneously.',
 ARRAY['climate', 'renewable-energy', 'clean-energy'], 0.84, 82, 'HIGH', 'IE', 2, 2, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000008'),

('10000000-0000-4000-8000-000000000009',
 'Mediterranean Heat Waves Expected to Double by 2050',
 'https://ipcc.ch/reports/mediterranean-heat-2025', 'Dr. Maria Rossi', NOW() - INTERVAL '3 days',
 'IPCC', 96, 'IPCC projects Mediterranean heat wave frequency will double within 25 years under current emission trajectories.',
 'The IPCC Sixth Assessment Working Group III has released new projections showing that Mediterranean countries will experience heat waves at twice the current frequency by 2050 unless emissions peak before 2030.',
 ARRAY['climate', 'climate-indicators', 'adaptation', 'global-climate'], 0.95, 96, 'HIGH', 'IT', 5, 4, 'completed', 'en',
 'a0000000-0000-4000-8000-000000000003'),

('10000000-0000-4000-8000-000000000010',
 'Dutch Flood Defenses Being Raised After New Sea Level Projections',
 'https://rijkswaterstaat.nl/sea-level-2025', 'Willem de Jong', NOW() - INTERVAL '2 days',
 'Rijkswaterstaat', 87, 'Netherlands to invest EUR 25 billion in raising coastal defenses based on revised sea level projections.',
 'The Dutch government announced a EUR 25 billion investment program to raise coastal flood defenses after KNMI revised its sea level rise projections upward by 15cm for 2100.',
 ARRAY['climate', 'adaptation', 'ocean', 'eu-policy'], 0.88, 87, 'HIGH', 'NL', 3, 2, 'completed', 'en',
 NULL),

('10000000-0000-4000-8000-000000000011',
 'New Analysis: French Nuclear Power and Climate Goals',
 'https://lemonde.fr/france-nuclear-climate', 'Pierre Dupont', NOW() - INTERVAL '1 hour',
 'Le Monde', 78, 'Analysis of how French nuclear energy strategy aligns with EU climate targets is underway.',
 'French energy policy and its nuclear fleet role in meeting Paris Agreement targets is being analyzed by multiple independent research groups.',
 ARRAY['climate', 'clean-energy', 'eu-policy'], 0.75, 78, 'MEDIUM', 'FR', 0, 0, 'processing', 'en',
 NULL),

('10000000-0000-4000-8000-000000000012',
 'Estonian Peatland Restoration Project Shows Promise',
 'https://envir.ee/estonia-peatlands', 'Kristjan Tamm', NOW() - INTERVAL '30 minutes',
 'Estonian Environment Agency', 70, 'Early results from the largest peatland restoration initiative in Estonia.',
 'Estonia has launched an ambitious peatland restoration project covering 15000 hectares. Early monitoring data suggests successful rewetting of degraded bog areas.',
 ARRAY['climate', 'conservation', 'bioeconomy'], 0.72, 70, 'MEDIUM', 'EE', 0, 0, 'pending', 'en',
 NULL)

ON CONFLICT (article_id) DO NOTHING;


-- ============================================================
-- CLAIMS (21 claims across articles)
-- ============================================================

INSERT INTO claims (claim_id, article_id, claim_text, claim_context, claim_type, claim_category, created_at) VALUES
-- Article 1: Arctic Permafrost
('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'Arctic permafrost is thawing at unprecedented rates', 'NASA satellite data analysis 2010-2025', 'scientific_causal', 'scientific_causal', NOW()),
('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', '150 billion tons of carbon could be released from thawing permafrost', 'Carbon stock estimates from IPCC AR6', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', 'Methane release from permafrost could accelerate warming by 0.3C by 2100', 'Climate feedback modeling', 'predictive', 'predictive', NOW()),
('20000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000001', 'Permafrost degradation in Siberia has increased by 40% since 2010', 'Satellite time-series analysis', 'statistical', 'statistical', NOW()),

-- Article 2: EU Green Deal Finland
('20000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000002', 'Finland has achieved 52% renewable energy share in total consumption', 'European Commission progress report 2025', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000006', '10000000-0000-4000-8000-000000000002', 'Finland has surpassed its 2030 EU renewable energy targets', 'Comparison with RED III directive targets', 'policy', 'policy', NOW()),
('20000000-0000-4000-8000-000000000007', '10000000-0000-4000-8000-000000000002', 'Forest-based bioenergy accounts for 28% of Finnish renewable mix', 'Finnish energy statistics', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000008', '10000000-0000-4000-8000-000000000002', 'Nordic cooperation reduced regional emissions by 15% since 2020', 'Nordic Council report', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000009', '10000000-0000-4000-8000-000000000002', 'Wind power capacity in Finland doubled between 2022 and 2025', 'Fingrid grid data', 'statistical', 'statistical', NOW()),

-- Article 3: Baltic Sea
('20000000-0000-4000-8000-000000000010', '10000000-0000-4000-8000-000000000003', 'Baltic Sea pH has decreased by 0.1 units since pre-industrial times', 'NOAA/FMI joint study', 'scientific_causal', 'scientific_causal', NOW()),
('20000000-0000-4000-8000-000000000011', '10000000-0000-4000-8000-000000000003', 'Shellfish populations in the Baltic have declined by 30% in 10 years', 'Marine biodiversity survey data', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000012', '10000000-0000-4000-8000-000000000003', 'Ocean acidification in the Baltic is accelerating faster than global average', 'Comparison with global ocean monitoring', 'scientific_causal', 'scientific_causal', NOW()),

-- Article 4: Germany renewables
('20000000-0000-4000-8000-000000000013', '10000000-0000-4000-8000-000000000004', 'Germany generated 55% of electricity from renewables in Q1 2025', 'German federal energy statistics', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000014', '10000000-0000-4000-8000-000000000004', 'Renewable output increased 12% year-over-year', 'Quarterly energy data comparison', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000015', '10000000-0000-4000-8000-000000000004', 'Solar capacity additions in Germany reached 14 GW in 2024', 'European solar energy association', 'statistical', 'statistical', NOW()),
('20000000-0000-4000-8000-000000000016', '10000000-0000-4000-8000-000000000004', 'Offshore wind in the North Sea contributed 18% of renewable generation', 'Grid operator data', 'statistical', 'statistical', NOW()),

-- Article 9: Mediterranean heat
('20000000-0000-4000-8000-000000000017', '10000000-0000-4000-8000-000000000009', 'Mediterranean heat wave frequency will double by 2050', 'IPCC WG III projections', 'predictive', 'predictive', NOW()),
('20000000-0000-4000-8000-000000000018', '10000000-0000-4000-8000-000000000009', 'Emissions must peak before 2030 to limit heat wave increase', 'IPCC scenario analysis', 'policy', 'policy', NOW()),
('20000000-0000-4000-8000-000000000019', '10000000-0000-4000-8000-000000000009', 'Southern Europe could see 50+ days above 40C annually by 2050', 'Regional climate modeling', 'predictive', 'predictive', NOW()),
('20000000-0000-4000-8000-000000000020', '10000000-0000-4000-8000-000000000009', 'Agricultural losses from heat stress could reach EUR 20 billion annually', 'Economic impact modeling', 'predictive', 'predictive', NOW()),
('20000000-0000-4000-8000-000000000021', '10000000-0000-4000-8000-000000000009', '2024 was already the hottest year on record for the Mediterranean basin', 'WMO climate monitoring', 'statistical', 'statistical', NOW())

ON CONFLICT (claim_id) DO NOTHING;


-- ============================================================
-- FACT CHECKS (17 fact checks)
-- ============================================================

INSERT INTO fact_checks (fact_check_id, claim_id, verification_status, confidence_score, justification, evidence, verified_at, decomposed_confidence, evidence_chain) VALUES
-- Arctic permafrost claims
('30000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'VERIFIED', 0.94,
 'Confirmed by multiple independent satellite datasets from NASA, ESA, and JAXA. Consistent with IPCC AR6 findings.',
 '{"sources": ["NASA ICESat-2", "ESA Sentinel-1", "IPCC AR6 WGI Ch4"], "methodology": "multi-sensor satellite analysis"}',
 NOW(),
 '{"model_confidence": 0.95, "source_quality": 0.97, "evidence_breadth": 0.92, "cross_reference_score": 0.93, "temporal_relevance": 0.90, "overall": 0.94}',
 '[{"step_number": 1, "description": "Confirmed accelerating thaw rates via satellite altimetry", "source": "NASA ICESat-2", "source_url": "https://icesat-2.gsfc.nasa.gov/", "confidence": 0.96, "supports_claim": true}, {"step_number": 2, "description": "Corroborating ground deformation data from SAR imagery", "source": "ESA Sentinel-1", "source_url": "https://sentinel.esa.int/web/sentinel/missions/sentinel-1", "confidence": 0.93, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 'VERIFIED', 0.87,
 'Consistent with IPCC AR6 range of 120-200 billion tons. The 150 billion figure falls within the central estimate.',
 '{"sources": ["IPCC AR6", "Nature Geoscience 2024"], "range": "120-200 Gt"}',
 NOW(),
 '{"model_confidence": 0.88, "source_quality": 0.95, "evidence_breadth": 0.85, "cross_reference_score": 0.86, "temporal_relevance": 0.82, "overall": 0.87}',
 '[{"step_number": 1, "description": "Central estimate 150 Gt within 120-200 Gt range", "source": "IPCC AR6", "source_url": "https://www.ipcc.ch/report/ar6/wg1/", "confidence": 0.90, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000003', '20000000-0000-4000-8000-000000000003', 'PARTIALLY_VERIFIED', 0.72,
 'The 0.3C figure is within model ranges but represents a high-end estimate. Median models suggest 0.15-0.25C.',
 '{"sources": ["CMIP6 models", "Nature Climate Change 2023"], "uncertainty": "high"}',
 NOW(),
 '{"model_confidence": 0.70, "source_quality": 0.85, "evidence_breadth": 0.68, "cross_reference_score": 0.72, "temporal_relevance": 0.75, "overall": 0.72}',
 '[{"step_number": 1, "description": "Median estimate 0.15-0.25C, upper bound includes 0.3C", "source": "CMIP6 Earth System Models", "source_url": "https://esgf-node.llnl.gov/projects/cmip6/", "confidence": 0.72, "supports_claim": false}]'),

-- EU Green Deal Finland claims
('30000000-0000-4000-8000-000000000004', '20000000-0000-4000-8000-000000000005', 'VERIFIED', 0.96,
 'Confirmed by Eurostat energy statistics. Finland reported 51.8% renewable share, rounded to 52%.',
 '{"sources": ["Eurostat", "Statistics Finland"], "exact_figure": "51.8%"}',
 NOW(),
 '{"model_confidence": 0.97, "source_quality": 0.98, "evidence_breadth": 0.95, "cross_reference_score": 0.96, "temporal_relevance": 0.94, "overall": 0.96}',
 '[{"step_number": 1, "description": "51.8% renewable share confirmed in official energy statistics", "source": "Eurostat", "source_url": "https://ec.europa.eu/eurostat/web/energy/overview", "confidence": 0.98, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000005', '20000000-0000-4000-8000-000000000006', 'VERIFIED', 0.91,
 'Finland exceeded its binding 2030 RED III target of 42.5% renewables.',
 '{"sources": ["RED III Directive", "EC Progress Report 2025"]}',
 NOW(),
 '{"model_confidence": 0.92, "source_quality": 0.95, "evidence_breadth": 0.88, "cross_reference_score": 0.90, "temporal_relevance": 0.91, "overall": 0.91}',
 '[{"step_number": 1, "description": "RED III binding target 42.5%, Finland achieved 51.8%", "source": "RED III Directive", "source_url": "https://energy.ec.europa.eu/topics/renewable-energy/renewable-energy-directive-targets-and-rules_en", "confidence": 0.95, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000006', '20000000-0000-4000-8000-000000000007', 'VERIFIED', 0.89,
 'Finnish Energy Authority data confirms 28.3% bioenergy share.',
 '{"sources": ["Finnish Energy Authority", "Bioenergia ry"]}',
 NOW(),
 '{"model_confidence": 0.90, "source_quality": 0.92, "evidence_breadth": 0.86, "cross_reference_score": 0.88, "temporal_relevance": 0.89, "overall": 0.89}',
 '[{"step_number": 1, "description": "28.3% bioenergy share confirmed in national energy data", "source": "Finnish Energy Authority", "source_url": "https://energiavirasto.fi/en/frontpage", "confidence": 0.92, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000007', '20000000-0000-4000-8000-000000000008', 'PARTIALLY_VERIFIED', 0.75,
 'Nordic cooperation contributed to emission reductions but the 15% figure is difficult to attribute solely to cooperation vs national policies.',
 '{"sources": ["Nordic Council", "national GHG inventories"], "caveat": "attribution uncertainty"}',
 NOW(),
 '{"model_confidence": 0.73, "source_quality": 0.82, "evidence_breadth": 0.70, "cross_reference_score": 0.76, "temporal_relevance": 0.78, "overall": 0.75}',
 '[{"step_number": 1, "description": "15% emission reduction claimed but attribution to cooperation vs national policies unclear", "source": "Nordic Council of Ministers", "source_url": "https://www.norden.org/en", "confidence": 0.75, "supports_claim": false}]'),

-- Baltic Sea claims
('30000000-0000-4000-8000-000000000008', '20000000-0000-4000-8000-000000000010', 'VERIFIED', 0.92,
 'Confirmed by long-term monitoring data from NOAA buoys and FMI coastal stations.',
 '{"sources": ["NOAA", "FMI", "SMHI"], "measurement_period": "1990-2025"}',
 NOW(),
 '{"model_confidence": 0.93, "source_quality": 0.96, "evidence_breadth": 0.90, "cross_reference_score": 0.91, "temporal_relevance": 0.88, "overall": 0.92}',
 '[{"step_number": 1, "description": "0.1 pH unit decrease confirmed by long-term buoy monitoring", "source": "NOAA Ocean Acidification Program", "source_url": "https://oceanacidification.noaa.gov/", "confidence": 0.94, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000009', '20000000-0000-4000-8000-000000000011', 'VERIFIED', 0.84,
 'HELCOM biodiversity assessments show 28-33% decline depending on species group.',
 '{"sources": ["HELCOM", "Baltic Sea Environment Proceedings"], "range": "28-33%"}',
 NOW(),
 '{"model_confidence": 0.85, "source_quality": 0.90, "evidence_breadth": 0.82, "cross_reference_score": 0.83, "temporal_relevance": 0.80, "overall": 0.84}',
 '[{"step_number": 1, "description": "28-33% shellfish population decline confirmed across species groups", "source": "HELCOM", "source_url": "https://helcom.fi/", "confidence": 0.88, "supports_claim": true}]'),

-- Germany renewable claims
('30000000-0000-4000-8000-000000000010', '20000000-0000-4000-8000-000000000013', 'VERIFIED', 0.95,
 'Federal Network Agency (Bundesnetzagentur) data confirms 54.8% renewable share in Q1 2025.',
 '{"sources": ["Bundesnetzagentur", "Fraunhofer ISE"], "exact_figure": "54.8%"}',
 NOW(),
 '{"model_confidence": 0.96, "source_quality": 0.97, "evidence_breadth": 0.93, "cross_reference_score": 0.94, "temporal_relevance": 0.92, "overall": 0.95}',
 '[{"step_number": 1, "description": "54.8% renewable share confirmed, reported as ~55% in article", "source": "Bundesnetzagentur", "source_url": "https://www.bundesnetzagentur.de/EN/Home/home_node.html", "confidence": 0.97, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000011', '20000000-0000-4000-8000-000000000014', 'VERIFIED', 0.90,
 'Year-over-year comparison shows 11.7% increase, consistent with the reported 12%.',
 '{"sources": ["Bundesnetzagentur quarterly reports"]}',
 NOW(),
 '{"model_confidence": 0.91, "source_quality": 0.94, "evidence_breadth": 0.87, "cross_reference_score": 0.89, "temporal_relevance": 0.90, "overall": 0.90}',
 '[{"step_number": 1, "description": "11.7% year-over-year increase confirmed, consistent with reported 12%", "source": "Bundesnetzagentur", "source_url": "https://www.bundesnetzagentur.de/EN/Home/home_node.html", "confidence": 0.93, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000012', '20000000-0000-4000-8000-000000000015', 'VERIFIED', 0.88,
 'BSW Solar data shows 13.8 GW additions, rounded to 14 GW in report.',
 '{"sources": ["BSW Solar", "Bundesnetzagentur"]}',
 NOW(),
 '{"model_confidence": 0.89, "source_quality": 0.92, "evidence_breadth": 0.85, "cross_reference_score": 0.87, "temporal_relevance": 0.88, "overall": 0.88}',
 '[{"step_number": 1, "description": "13.8 GW solar capacity additions confirmed, rounded to 14 GW", "source": "BSW Solar", "source_url": "https://www.solarwirtschaft.de/en/", "confidence": 0.91, "supports_claim": true}]'),

-- Mediterranean heat claims
('30000000-0000-4000-8000-000000000013', '20000000-0000-4000-8000-000000000017', 'VERIFIED', 0.93,
 'IPCC WG III Chapter 12 projects 1.5-2.5x increase under SSP2-4.5. Doubling is consistent with mid-range scenario.',
 '{"sources": ["IPCC AR6 WGIII", "Copernicus C3S"], "scenario": "SSP2-4.5"}',
 NOW(),
 '{"model_confidence": 0.94, "source_quality": 0.97, "evidence_breadth": 0.91, "cross_reference_score": 0.92, "temporal_relevance": 0.89, "overall": 0.93}',
 '[{"step_number": 1, "description": "1.5-2.5x heat wave frequency increase projected under SSP2-4.5 scenario", "source": "IPCC AR6 WG III", "source_url": "https://www.ipcc.ch/report/ar6/wg3/", "confidence": 0.95, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000014', '20000000-0000-4000-8000-000000000018', 'VERIFIED', 0.91,
 'Consistent with IPCC synthesis report finding that emissions must peak before 2025-2030 for 1.5C pathway.',
 '{"sources": ["IPCC Synthesis Report", "UNEP Emissions Gap Report 2024"]}',
 NOW(),
 '{"model_confidence": 0.92, "source_quality": 0.96, "evidence_breadth": 0.89, "cross_reference_score": 0.90, "temporal_relevance": 0.88, "overall": 0.91}',
 '[{"step_number": 1, "description": "Emissions must peak before 2030 for 1.5C pathway confirmed", "source": "IPCC Synthesis Report", "source_url": "https://www.ipcc.ch/report/ar6/syr/", "confidence": 0.94, "supports_claim": true}]'),

('30000000-0000-4000-8000-000000000015', '20000000-0000-4000-8000-000000000019', 'PARTIALLY_VERIFIED', 0.68,
 'Regional models vary. 50+ days above 40C is at the upper end of projections for southern Spain/Italy.',
 '{"sources": ["EURO-CORDEX", "MedCLIVAR"], "uncertainty": "moderate-high"}',
 NOW(),
 '{"model_confidence": 0.65, "source_quality": 0.80, "evidence_breadth": 0.62, "cross_reference_score": 0.70, "temporal_relevance": 0.72, "overall": 0.68}',
 '[{"step_number": 1, "description": "50+ days above 40C is upper range of regional climate model projections", "source": "EURO-CORDEX", "source_url": "https://www.euro-cordex.net/", "confidence": 0.68, "supports_claim": false}]'),

('30000000-0000-4000-8000-000000000016', '20000000-0000-4000-8000-000000000020', 'UNVERIFIED', 0.45,
 'The EUR 20 billion figure lacks clear sourcing. JRC estimates range EUR 8-15 billion depending on adaptation.',
 '{"sources": ["JRC PESETA IV"], "issue": "figure not independently confirmed at stated level"}',
 NOW(),
 '{"model_confidence": 0.40, "source_quality": 0.50, "evidence_breadth": 0.35, "cross_reference_score": 0.48, "temporal_relevance": 0.55, "overall": 0.45}',
 '[{"step_number": 1, "description": "JRC PESETA IV estimates EUR 8-15B agricultural losses, not EUR 20B as claimed", "source": "JRC PESETA IV", "source_url": "https://joint-research-centre.ec.europa.eu/peseta-projects_en", "confidence": 0.45, "supports_claim": false}]'),

('30000000-0000-4000-8000-000000000017', '20000000-0000-4000-8000-000000000021', 'VERIFIED', 0.97,
 'WMO and Copernicus Climate Change Service confirm 2024 as hottest Mediterranean year on record.',
 '{"sources": ["WMO", "C3S", "Berkeley Earth"]}',
 NOW(),
 '{"model_confidence": 0.98, "source_quality": 0.99, "evidence_breadth": 0.96, "cross_reference_score": 0.97, "temporal_relevance": 0.95, "overall": 0.97}',
 '[{"step_number": 1, "description": "2024 confirmed as hottest Mediterranean year on record by multiple agencies", "source": "WMO", "source_url": "https://wmo.int/", "confidence": 0.98, "supports_claim": true}]')

ON CONFLICT (fact_check_id) DO NOTHING;

COMMIT;
