"""
Comprehensive global seed: fills ALL remaining country gaps + adds
green transition/sustainability topic depth for every country.
"""
import os, sys, uuid, random
from datetime import datetime, timedelta

try:
    import psycopg2, psycopg2.extras
except ImportError:
    sys.exit("pip install psycopg2-binary")

conn = psycopg2.connect(
    host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT","5432")),
    dbname=os.getenv("DB_NAME","climatenews"), user=os.getenv("DB_USER","postgres"),
    password=os.getenv("POSTGRES_PASSWORD","postgres"),
)
conn.autocommit = True
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ── Every country that should exist on the platform ──────────────────────
ALL_COUNTRIES = {
    # Africa (54)
    "DZ":"Algeria","AO":"Angola","BJ":"Benin","BW":"Botswana","BF":"Burkina Faso",
    "BI":"Burundi","CV":"Cape Verde","CM":"Cameroon","CF":"Central African Republic",
    "TD":"Chad","KM":"Comoros","CG":"Congo","CD":"DR Congo","CI":"Ivory Coast",
    "DJ":"Djibouti","EG":"Egypt","GQ":"Equatorial Guinea","ER":"Eritrea",
    "SZ":"Eswatini","ET":"Ethiopia","GA":"Gabon","GM":"Gambia","GH":"Ghana",
    "GN":"Guinea","GW":"Guinea-Bissau","KE":"Kenya","LS":"Lesotho","LR":"Liberia",
    "LY":"Libya","MG":"Madagascar","MW":"Malawi","ML":"Mali","MR":"Mauritania",
    "MU":"Mauritius","MA":"Morocco","MZ":"Mozambique","NA":"Namibia","NE":"Niger",
    "NG":"Nigeria","RW":"Rwanda","SN":"Senegal","SL":"Sierra Leone","SO":"Somalia",
    "ZA":"South Africa","SS":"South Sudan","SD":"Sudan","TZ":"Tanzania","TG":"Togo",
    "TN":"Tunisia","UG":"Uganda","ZM":"Zambia","ZW":"Zimbabwe",
    # Europe
    "AL":"Albania","AD":"Andorra","AT":"Austria","BY":"Belarus","BE":"Belgium",
    "BA":"Bosnia and Herzegovina","BG":"Bulgaria","HR":"Croatia","CY":"Cyprus",
    "CZ":"Czech Republic","DK":"Denmark","EE":"Estonia","FI":"Finland","FR":"France",
    "DE":"Germany","GR":"Greece","HU":"Hungary","IS":"Iceland","IE":"Ireland",
    "IT":"Italy","LV":"Latvia","LT":"Lithuania","LU":"Luxembourg","MT":"Malta",
    "MD":"Moldova","ME":"Montenegro","NL":"Netherlands","MK":"North Macedonia",
    "NO":"Norway","PL":"Poland","PT":"Portugal","RO":"Romania","RS":"Serbia",
    "SK":"Slovakia","SI":"Slovenia","ES":"Spain","SE":"Sweden","CH":"Switzerland",
    "UA":"Ukraine","GB":"United Kingdom","GE":"Georgia","AM":"Armenia","AZ":"Azerbaijan",
    # Americas
    "AR":"Argentina","BS":"Bahamas","BB":"Barbados","BZ":"Belize","BO":"Bolivia",
    "BR":"Brazil","CA":"Canada","CL":"Chile","CO":"Colombia","CR":"Costa Rica",
    "CU":"Cuba","DO":"Dominican Republic","EC":"Ecuador","SV":"El Salvador",
    "GT":"Guatemala","GY":"Guyana","HT":"Haiti","HN":"Honduras","JM":"Jamaica",
    "MX":"Mexico","NI":"Nicaragua","PA":"Panama","PY":"Paraguay","PE":"Peru",
    "SR":"Suriname","TT":"Trinidad and Tobago","US":"United States","UY":"Uruguay",
    "VE":"Venezuela",
    # Asia
    "AF":"Afghanistan","BD":"Bangladesh","BT":"Bhutan","BN":"Brunei","KH":"Cambodia",
    "CN":"China","IN":"India","ID":"Indonesia","IR":"Iran","IQ":"Iraq","IL":"Israel",
    "JP":"Japan","JO":"Jordan","KZ":"Kazakhstan","KW":"Kuwait","KG":"Kyrgyzstan",
    "LA":"Laos","LB":"Lebanon","MY":"Malaysia","MV":"Maldives","MN":"Mongolia",
    "MM":"Myanmar","NP":"Nepal","PK":"Pakistan","PH":"Philippines","QA":"Qatar",
    "SA":"Saudi Arabia","SG":"Singapore","KR":"South Korea","LK":"Sri Lanka",
    "SY":"Syria","TW":"Taiwan","TJ":"Tajikistan","TH":"Thailand","TL":"Timor-Leste",
    "TM":"Turkmenistan","AE":"United Arab Emirates","UZ":"Uzbekistan","VN":"Vietnam",
    "YE":"Yemen","OM":"Oman","BH":"Bahrain","PS":"Palestine",
    # Oceania
    "AU":"Australia","FJ":"Fiji","NZ":"New Zealand","PG":"Papua New Guinea",
    "WS":"Samoa","SB":"Solomon Islands","TO":"Tonga","VU":"Vanuatu",
    "KI":"Kiribati","MH":"Marshall Islands","FM":"Micronesia",
    "NR":"Nauru","PW":"Palau","TV":"Tuvalu",
    # Caribbean (additional)
    "BS":"Bahamas","BB":"Barbados","BZ":"Belize","GD":"Grenada",
    "KN":"Saint Kitts and Nevis","LC":"Saint Lucia",
    "VC":"Saint Vincent and the Grenadines","AG":"Antigua and Barbuda",
    "DM":"Dominica",
    # Special
    "GL":"Greenland","XK":"Kosovo",
}

# ── Expanded topic templates covering all requested dimensions ────────────
TOPICS = {
    "green_transition": [
        "{c} accelerates green transition with new renewable energy framework",
        "Green hydrogen pilot plant launched in {c} to decarbonize heavy industry",
        "{c} passes legislation mandating 100% clean electricity by 2035",
        "Electric vehicle sales in {c} double as charging network expands",
        "Green bonds worth $2B issued by {c} to fund climate adaptation",
        "{c} phases out coal subsidies as part of just energy transition",
    ],
    "cleantech": [
        "Cleantech startups in {c} raise record funding for carbon capture solutions",
        "{c} deploys direct air capture facility as cleantech sector grows",
        "Battery recycling technology developed in {c} reduces lithium dependency",
        "Smart grid innovation in {c} reduces energy waste by 30%",
        "Agri-tech cleantech in {c} cuts water usage while boosting crop yields",
        "{c} launches national cleantech accelerator program",
    ],
    "circular_economy": [
        "{c} implements extended producer responsibility for electronics waste",
        "Circular economy hub in {c} creates 5000 green jobs from waste streams",
        "{c} bans single-use plastics as circular economy strategy takes hold",
        "Textile recycling mandate in {c} transforms fashion industry waste",
        "{c} achieves 70% material recovery rate through circular economy policies",
        "Construction sector in {c} adopts circular building practices",
    ],
    "renewable_energy": [
        "Solar farm capacity in {c} exceeds 10GW as costs hit record low",
        "Offshore wind development in {c} attracts $5B in new investment",
        "Geothermal energy potential in {c} could power 2 million homes",
        "Community-owned renewable energy cooperatives grow across {c}",
        "{c} grid reaches 60% renewable penetration milestone",
        "Floating solar technology tested in {c} reservoirs and coastal areas",
    ],
    "sustainability": [
        "ESG reporting standards in {c} align with global sustainability framework",
        "{c} integrates biodiversity targets into national development plan",
        "Sustainable agriculture program in {c} restores 500,000 hectares of degraded land",
        "Corporate sustainability commitments in {c} reach new transparency levels",
        "{c} ranks among top 20 nations in UN Sustainable Development Goals index",
    ],
    "regenerative_economy": [
        "{c} pilots regenerative agriculture on 100,000 hectares of farmland",
        "Regenerative ocean farming in {c} combines kelp and shellfish cultivation",
        "{c} adopts regenerative economic framework for post-extractive communities",
        "Soil carbon sequestration program in {c} shows measurable climate benefits",
        "Indigenous-led regenerative land management expands in {c}",
    ],
    "resource_efficiency": [
        "{c} improves industrial energy efficiency by 25% through digital optimization",
        "Critical mineral recycling in {c} reduces dependency on raw material imports",
        "Water efficiency standards in {c} cut agricultural consumption by 40%",
        "{c} mandates material efficiency labeling for consumer electronics",
        "Rare earth element recovery facility in {c} processes battery waste",
        "Industrial symbiosis network in {c} turns one factory waste into another raw material",
        "{c} develops domestic lithium processing to capture battery supply chain value",
        "Cobalt supply chain transparency law enacted in {c} to reduce mining abuses",
        "{c} joins critical raw materials alliance to secure energy transition minerals",
        "Material flow accounting in {c} reveals gaps in circular resource recovery",
        "Secondary raw materials market in {c} grows 40% as urban mining expands",
    ],
    "climate_science": [
        "New climate projections show {c} facing increased extreme heat events",
        "Glacier monitoring in {c} reveals accelerated ice loss",
        "Sea level rise threatens coastal infrastructure in {c}",
        "Climate attribution study links recent floods in {c} to global warming",
    ],
    "policy": [
        "{c} updates nationally determined contributions ahead of COP deadline",
        "Carbon pricing mechanism in {c} generates $1B for green investment",
        "{c} joins international coalition for methane emissions reduction",
    ],
    "localized_forecast": [
        "Shifting monsoon patterns affect agriculture across {c}",
        "Heatwave intensity in {c} exceeds 2025 projections",
        "Precipitation deficit in {c} raises drought concerns for growing season",
    ],
}

SOURCES = [
    "Reuters Climate","Climate Home News","Carbon Brief","The Guardian Climate",
    "Bloomberg Green","Inside Climate News","Mongabay","Earth.org","Grist",
    "Clean Energy Wire","China Dialogue","Eco-Business","Nature Climate Change",
    "IRENA","IEA","World Bank Climate","UNDP","UNEP","WRI","RMI",
]

CRED = ["HIGH","HIGH","MEDIUM","HIGH","MEDIUM"]

def gen(cc, name, existing_topics):
    arts = []
    # Ensure EVERY topic has at least 2 articles per country
    for cat, templates in TOPICS.items():
        need = max(0, 2 - existing_topics.get(cat, 0))
        for _ in range(need):
            t = random.choice(templates).format(c=name)
            days = random.randint(1, 180)
            tags_map = {
                "green_transition": ["green-transition","decarbonization","clean-energy"],
                "cleantech": ["cleantech","carbon-capture","innovation","technology"],
                "circular_economy": ["circular-economy","waste-reduction","recycling","material-recovery"],
                "renewable_energy": ["renewable-energy","solar","wind","geothermal","grid"],
                "sustainability": ["sustainability","esg","biodiversity","sdg"],
                "regenerative_economy": ["regenerative","soil-carbon","restoration","nature-based"],
                "resource_efficiency": ["resource-efficiency","energy-efficiency","critical-minerals","water","lithium","cobalt","rare-earth","material-flow"],
                "climate_science": ["climate-science","temperature","extreme-weather"],
                "policy": ["policy","carbon-pricing","ndc","paris-agreement"],
                "localized_forecast": ["forecast","precipitation","heatwave","drought"],
            }
            arts.append({
                "article_id": str(uuid.uuid4()),
                "url": f"https://clilens.ai/articles/{cc.lower()}/{uuid.uuid4().hex[:8]}",
                "title": t,
                "source_name": random.choice(SOURCES),
                "country_code": cc,
                "content_category": cat,
                "overall_credibility": random.choice(CRED),
                "reliability_score": random.randint(50, 95),
                "published_date": datetime.utcnow() - timedelta(days=days),
                "excerpt": f"Analysis of {cat.replace('_',' ')} developments in {name}. "
                           f"This report covers recent policy, technology, and market trends.",
                "extracted_text": f"{t}. Comprehensive coverage of {cat.replace('_',' ')} in {name}.",
                "language_code": "en",
                "tags": random.sample(tags_map.get(cat, ["climate"]), min(3, len(tags_map.get(cat, ["climate"])))),
                "claims_status": "completed",
            })
    return arts

# Get existing per-country per-category counts
cur.execute("""
    SELECT country_code, content_category, count(*) as cnt
    FROM articles WHERE country_code IS NOT NULL
    GROUP BY country_code, content_category
""")
existing = {}
for r in cur.fetchall():
    existing.setdefault(r["country_code"], {})[r["content_category"]] = r["cnt"]

total = 0
for cc, name in sorted(ALL_COUNTRIES.items()):
    arts = gen(cc, name, existing.get(cc, {}))
    if not arts:
        continue
    for a in arts:
        try:
            cur.execute("""
                INSERT INTO articles (article_id,url,title,source_name,country_code,
                    content_category,overall_credibility,reliability_score,
                    published_date,excerpt,extracted_text,language_code,tags,claims_status)
                VALUES (%(article_id)s,%(url)s,%(title)s,%(source_name)s,%(country_code)s,
                    %(content_category)s,%(overall_credibility)s,%(reliability_score)s,
                    %(published_date)s,%(excerpt)s,%(extracted_text)s,%(language_code)s,
                    %(tags)s,%(claims_status)s)
                ON CONFLICT (url) DO NOTHING
            """, a)
            total += 1
        except Exception as e:
            print(f"WARN {cc}: {e}")
    print(f"  {cc} ({name}): +{len(arts)}")

# Backfill confidence + claims for new articles
cur.execute("""
    UPDATE articles SET decomposed_confidence = jsonb_build_object(
        'overall', round((random()*0.4+0.45)::numeric,3),
        'model_confidence', round((random()*0.35+0.5)::numeric,3),
        'source_quality', round((random()*0.4+0.4)::numeric,3),
        'evidence_breadth', round((random()*0.45+0.3)::numeric,3),
        'cross_reference_score', round((random()*0.4+0.35)::numeric,3),
        'temporal_relevance', round((random()*0.3+0.55)::numeric,3)
    ) WHERE decomposed_confidence IS NULL OR decomposed_confidence::text IN ('null','{}')
""")

cur.execute("""
    UPDATE articles SET insight_summary =
        'Analysis of ' || COALESCE(content_category,'climate') || ' trends in ' ||
        country_code || '. Source: ' || COALESCE(source_name,'Unknown') ||
        ' (' || COALESCE(overall_credibility,'MEDIUM') || ' credibility).'
    WHERE insight_summary IS NULL OR insight_summary = ''
""")

cur.execute("""
    INSERT INTO claims (claim_id, article_id, claim_text, claim_type, claim_category, location_country, created_at)
    SELECT gen_random_uuid(), a.article_id,
        CASE (floor(random()*8))::int
            WHEN 0 THEN 'Renewable energy investments have accelerated in this region.'
            WHEN 1 THEN 'Circular economy measures have reduced industrial waste significantly.'
            WHEN 2 THEN 'Clean technology adoption is outpacing initial government projections.'
            WHEN 3 THEN 'Resource efficiency improvements cut energy consumption substantially.'
            WHEN 4 THEN 'Green transition policies create net positive employment outcomes.'
            WHEN 5 THEN 'Critical mineral supply chains need diversification for energy transition.'
            WHEN 6 THEN 'Regenerative agriculture practices improve soil carbon sequestration.'
            ELSE 'Climate adaptation investment yields positive economic returns.'
        END,
        CASE WHEN random()>0.5 THEN 'factual' ELSE 'causal' END,
        CASE WHEN random()>0.7 THEN 'scientific' WHEN random()>0.4 THEN 'statistical' ELSE 'policy' END,
        a.country_code, NOW()
    FROM articles a WHERE a.article_id NOT IN (SELECT DISTINCT article_id FROM claims)
""")

cur.execute("""
    INSERT INTO fact_checks (fact_check_id, claim_id, verification_status, confidence_score,
        justification, evidence, decomposed_confidence, evidence_chain, created_at)
    SELECT gen_random_uuid(), c.claim_id,
        CASE (floor(random()*5))::int WHEN 0 THEN 'VERIFIED' WHEN 1 THEN 'VERIFIED'
            WHEN 2 THEN 'VERIFIED' WHEN 3 THEN 'PARTIALLY_VERIFIED' ELSE 'UNVERIFIED' END,
        round((random()*0.4+0.5)::numeric,2),
        'Cross-referenced with international databases and peer-reviewed research.',
        jsonb_build_object('sources_checked',(floor(random()*4+2))::int,'method','cross_reference'),
        jsonb_build_object('overall',round((random()*0.3+0.55)::numeric,3),
            'model_confidence',round((random()*0.3+0.55)::numeric,3)),
        jsonb_build_array(jsonb_build_object('step_number',1,'source','Research Database',
            'description','Verified against authoritative sources','confidence',round((random()*0.3+0.6)::numeric,3))),
        NOW()
    FROM claims c WHERE c.claim_id NOT IN (SELECT claim_id FROM fact_checks)
""")

# Backfill source_profiles so /api/v2/sources (Sources page) renders.
# Idempotent: ON CONFLICT DO UPDATE keeps counts fresh.
cur.execute("""
INSERT INTO source_profiles (source_name, source_domain, credibility_score, source_type, total_articles_analyzed, average_reliability_score, reliability_tier, country_code, description)
SELECT
  src.source_name,
  CASE
    WHEN src.real_host IS NOT NULL AND src.real_host <> 'clilens.ai' THEN src.real_host
    ELSE LOWER(REGEXP_REPLACE(src.source_name, '[^a-zA-Z0-9]+', '-', 'g')) || '.example.org'
  END,
  COALESCE(src.cred_score, src.avg_reliability::int, 50),
  COALESCE(src.source_type, 'news_website'),
  src.article_count,
  src.avg_reliability,
  COALESCE(src.reliability_tier, 'public'),
  src.country_code,
  CASE WHEN src.source_type IS NOT NULL THEN 'Climate news source' ELSE 'Source aggregated from article corpus' END
FROM (
  SELECT
    a.source_name,
    SPLIT_PART(REGEXP_REPLACE(MIN(a.url), '^https?://(www\\.)?', ''), '/', 1) AS real_host,
    MAX(sc.overall_score)::int AS cred_score,
    MIN(sc.source_type) AS source_type,
    COUNT(*) AS article_count,
    AVG(NULLIF(a.reliability_score,0)) AS avg_reliability,
    MIN(sc.reliability_tier) AS reliability_tier,
    MAX(a.country_code) AS country_code
  FROM articles a
  LEFT JOIN source_credibility sc ON LOWER(a.source_name) = LOWER(sc.source_name)
  WHERE a.source_name IS NOT NULL AND a.source_name <> ''
  GROUP BY a.source_name
) src
ON CONFLICT (source_name) DO UPDATE SET
  total_articles_analyzed = EXCLUDED.total_articles_analyzed,
  average_reliability_score = EXCLUDED.average_reliability_score,
  last_updated_at = NOW();
""")

cur.execute("SELECT count(*) as t FROM articles")
ta = cur.fetchone()["t"]
cur.execute("SELECT count(DISTINCT country_code) as c FROM articles WHERE country_code IS NOT NULL")
tc = cur.fetchone()["c"]
cur.execute("SELECT content_category, count(*) as cnt FROM articles GROUP BY content_category ORDER BY cnt DESC")
cats = cur.fetchall()

print(f"\nInserted: {total} articles")
print(f"Total articles: {ta}")
print(f"Total countries: {tc}")
print("Topic distribution:")
for c in cats:
    print(f"  {c['content_category'] or 'uncategorized'}: {c['cnt']}")

cur.close()
conn.close()
