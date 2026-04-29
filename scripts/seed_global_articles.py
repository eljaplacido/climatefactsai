"""
Seed articles for ALL countries missing from the climate intelligence map.

Generates realistic climate-related articles for every country that currently
has 0 or very few articles in the database, ensuring full global coverage
for the map layers (article density, temperature anomaly, climate risk,
source diversity).

Run: DB_PORT=5433 python scripts/seed_global_articles.py
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
import random

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "climatenews")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

# ── All countries that need coverage ──────────────────────────────────────

COUNTRIES = {
    # Africa
    "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt", "ET": "Ethiopia",
    "GH": "Ghana", "TZ": "Tanzania", "UG": "Uganda", "RW": "Rwanda",
    "SN": "Senegal", "MA": "Morocco", "DZ": "Algeria", "TN": "Tunisia",
    "SD": "Sudan", "SS": "South Sudan", "CD": "DR Congo", "CM": "Cameroon",
    "AO": "Angola", "MZ": "Mozambique", "MW": "Malawi", "ZM": "Zambia",
    "ZW": "Zimbabwe", "BW": "Botswana", "NA": "Namibia", "MG": "Madagascar",
    "ML": "Mali", "BF": "Burkina Faso", "NE": "Niger", "TD": "Chad",
    "CI": "Ivory Coast", "SO": "Somalia", "ER": "Eritrea", "LY": "Libya",
    "ZA": "South Africa",
    # South America
    "VE": "Venezuela", "BO": "Bolivia", "PY": "Paraguay", "UY": "Uruguay",
    "GY": "Guyana", "SR": "Suriname", "EC": "Ecuador", "PE": "Peru",
    # Central America & Caribbean
    "GT": "Guatemala", "HN": "Honduras", "SV": "El Salvador",
    "NI": "Nicaragua", "CR": "Costa Rica", "PA": "Panama",
    "CU": "Cuba", "DO": "Dominican Republic", "HT": "Haiti",
    "JM": "Jamaica", "TT": "Trinidad and Tobago",
    # Middle East
    "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait",
    "BH": "Bahrain", "OM": "Oman", "YE": "Yemen",
    "IR": "Iran", "IQ": "Iraq", "JO": "Jordan", "LB": "Lebanon",
    "SY": "Syria", "PS": "Palestine",
    # Central Asia
    "KZ": "Kazakhstan", "UZ": "Uzbekistan", "TM": "Turkmenistan",
    "KG": "Kyrgyzstan", "TJ": "Tajikistan",
    # South & Southeast Asia
    "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka",
    "NP": "Nepal", "MM": "Myanmar", "TH": "Thailand", "VN": "Vietnam",
    "KH": "Cambodia", "LA": "Laos", "PH": "Philippines",
    "MY": "Malaysia", "ID": "Indonesia", "BN": "Brunei",
    # East Asia
    "MN": "Mongolia", "TW": "Taiwan",
    # Pacific
    "PG": "Papua New Guinea", "FJ": "Fiji", "WS": "Samoa",
    "TO": "Tonga", "VU": "Vanuatu", "SB": "Solomon Islands",
    # Other missing
    "GL": "Greenland", "AF": "Afghanistan",
    "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan",
    "MD": "Moldova", "BY": "Belarus",
    "MT": "Malta", "LU": "Luxembourg",
    "IS": "Iceland", "SE": "Sweden", "NO": "Norway",
    "DK": "Denmark", "CA": "Canada",
    # Ensure existing thin countries get more
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "MX": "Mexico", "BR": "Brazil",
    "AE": "United Arab Emirates", "IL": "Israel",
    "JP": "Japan", "KR": "South Korea", "AU": "Australia",
    "NZ": "New Zealand",
}

# ── Article templates per region/topic ────────────────────────────────────

CLIMATE_TOPICS = {
    "climate_science": [
        "{country} records highest temperature anomaly in {year} as global warming accelerates",
        "New climate study reveals {country}'s vulnerability to extreme weather events",
        "Scientists warn of unprecedented drought conditions affecting {country}",
        "Research shows accelerating glacier retreat impacts {country}'s water supply",
        "Climate projections for {country}: rising temperatures and shifting rainfall patterns",
        "{country}'s coastal regions face increased flood risk from sea level rise",
        "Ocean temperature changes threaten marine ecosystems off {country}'s coast",
    ],
    "green_transition": [
        "{country} announces ambitious renewable energy targets for 2030",
        "Solar power capacity in {country} grows by 40% as clean energy transition accelerates",
        "Wind energy investments surge in {country} amid global push for decarbonization",
        "{country} launches green hydrogen strategy to reduce industrial emissions",
        "Electric vehicle adoption in {country} reaches new milestone",
        "{country}'s green bond market expands as sustainable finance grows",
    ],
    "policy": [
        "{country} implements new carbon pricing mechanism to meet Paris Agreement goals",
        "Climate policy reform in {country}: new emissions standards take effect",
        "{country} joins coalition of nations pledging net-zero by 2050",
        "Government of {country} allocates record funding for climate adaptation",
        "{country} updates national climate action plan with stronger targets",
    ],
    "sustainability": [
        "Circular economy initiatives in {country} reduce waste by 25%",
        "{country}'s sustainable agriculture program shows promising results",
        "ESG reporting requirements tighten in {country} as investors demand transparency",
        "Biodiversity conservation efforts expand across {country}",
    ],
    "localized_forecast": [
        "Precipitation patterns shift in {country}: dry season extends by two weeks",
        "Heatwave warning issued for {country} as temperatures exceed historical averages",
        "{country} experiences record rainfall, flooding displaces communities",
        "Climate models predict increased cyclone intensity affecting {country}",
    ],
}

SOURCES_BY_REGION = {
    "africa": ["African Arguments", "Daily Maverick Environment", "Reuters Environment", "Climate Home News", "UN Climate News"],
    "south_america": ["Mongabay Latam", "InfoAmazonia", "Dialogo Chino", "Reuters Environment", "Climate Change News"],
    "central_america": ["Reuters Environment", "Climate Home News", "Earth.org", "Inside Climate News", "UN Climate News"],
    "middle_east": ["Reuters Environment", "Climate Home News", "China Dialogue", "Earth.org", "Al Jazeera English"],
    "central_asia": ["Reuters Environment", "Climate Home News", "Earth.org", "IPCC", "UN Climate News"],
    "south_asia": ["The Wire Science India", "Mongabay Asia", "Reuters Environment", "Climate Home News", "UN Climate News"],
    "southeast_asia": ["Mongabay Asia", "Eco-Business", "Reuters Environment", "Climate Home News", "China Dialogue"],
    "east_asia": ["China Dialogue", "Mongabay Asia", "Reuters Environment", "Nature Climate Change", "Climate Home News"],
    "pacific": ["Reuters Environment", "Climate Home News", "Earth.org", "ABC Environment Australia", "UN Climate News"],
    "europe": ["EurActiv Climate", "Carbon Brief", "Climate Home News", "The Guardian Climate", "Clean Energy Wire (DE)"],
    "north_america": ["Inside Climate News", "Grist", "NYT Climate", "Climate Central", "The Daily Climate"],
    "greenland": ["Reuters Environment", "Carbon Brief", "Nature Climate Change", "IPCC", "Climate Home News"],
}

COUNTRY_REGION = {
    "NG": "africa", "KE": "africa", "EG": "africa", "ET": "africa", "GH": "africa",
    "TZ": "africa", "UG": "africa", "RW": "africa", "SN": "africa", "MA": "africa",
    "DZ": "africa", "TN": "africa", "SD": "africa", "SS": "africa", "CD": "africa",
    "CM": "africa", "AO": "africa", "MZ": "africa", "MW": "africa", "ZM": "africa",
    "ZW": "africa", "BW": "africa", "NA": "africa", "MG": "africa", "ML": "africa",
    "BF": "africa", "NE": "africa", "TD": "africa", "CI": "africa", "SO": "africa",
    "ER": "africa", "LY": "africa", "ZA": "africa",
    "VE": "south_america", "BO": "south_america", "PY": "south_america",
    "UY": "south_america", "GY": "south_america", "SR": "south_america",
    "EC": "south_america", "PE": "south_america", "AR": "south_america",
    "CL": "south_america", "CO": "south_america", "BR": "south_america",
    "GT": "central_america", "HN": "central_america", "SV": "central_america",
    "NI": "central_america", "CR": "central_america", "PA": "central_america",
    "CU": "central_america", "DO": "central_america", "HT": "central_america",
    "JM": "central_america", "TT": "central_america", "MX": "central_america",
    "SA": "middle_east", "QA": "middle_east", "KW": "middle_east",
    "BH": "middle_east", "OM": "middle_east", "YE": "middle_east",
    "IR": "middle_east", "IQ": "middle_east", "JO": "middle_east",
    "LB": "middle_east", "SY": "middle_east", "PS": "middle_east",
    "AE": "middle_east", "IL": "middle_east",
    "KZ": "central_asia", "UZ": "central_asia", "TM": "central_asia",
    "KG": "central_asia", "TJ": "central_asia", "AF": "central_asia",
    "PK": "south_asia", "BD": "south_asia", "LK": "south_asia",
    "NP": "south_asia", "IN": "south_asia",
    "MM": "southeast_asia", "TH": "southeast_asia", "VN": "southeast_asia",
    "KH": "southeast_asia", "LA": "southeast_asia", "PH": "southeast_asia",
    "MY": "southeast_asia", "ID": "southeast_asia", "BN": "southeast_asia",
    "MN": "east_asia", "TW": "east_asia", "JP": "east_asia",
    "KR": "east_asia", "CN": "east_asia",
    "PG": "pacific", "FJ": "pacific", "WS": "pacific", "TO": "pacific",
    "VU": "pacific", "SB": "pacific", "AU": "pacific", "NZ": "pacific",
    "GL": "greenland", "IS": "europe",
    "SE": "europe", "NO": "europe", "DK": "europe", "CA": "north_america",
    "GE": "europe", "AM": "europe", "AZ": "europe", "MD": "europe",
    "BY": "europe", "MT": "europe", "LU": "europe",
}

CREDIBILITY_TIERS = ["HIGH", "MEDIUM", "HIGH", "HIGH", "MEDIUM"]  # weighted toward HIGH


def generate_articles(cc, country_name, existing_count):
    """Generate articles for a country. More for countries with 0, fewer for those with some."""
    target = max(0, 10 - existing_count)  # aim for at least 10 per country
    if target == 0:
        return []

    region = COUNTRY_REGION.get(cc, "africa")
    sources = SOURCES_BY_REGION.get(region, SOURCES_BY_REGION["africa"])
    articles = []

    for i in range(target):
        category = random.choice(list(CLIMATE_TOPICS.keys()))
        templates = CLIMATE_TOPICS[category]
        title_template = random.choice(templates)
        year = random.choice(["2024", "2025", "2026"])
        title = title_template.format(country=country_name, year=year)

        source = random.choice(sources)
        cred = random.choice(CREDIBILITY_TIERS)
        reliability = random.randint(45, 95)
        days_ago = random.randint(1, 180)
        pub_date = datetime.utcnow() - timedelta(days=days_ago)

        excerpt = (
            f"A comprehensive analysis of climate trends in {country_name} reveals "
            f"significant changes in temperature and precipitation patterns. "
            f"Experts from the national meteorological service and international "
            f"research institutions highlight the urgent need for adaptive strategies."
        )

        tags = []
        if category == "climate_science":
            tags = random.sample(["climate", "temperature", "drought", "flooding", "sea-level", "extreme-weather"], 3)
        elif category == "green_transition":
            tags = random.sample(["renewable-energy", "solar", "wind", "hydrogen", "electric-vehicles", "green-finance"], 3)
        elif category == "policy":
            tags = random.sample(["carbon-pricing", "net-zero", "paris-agreement", "climate-policy", "adaptation"], 3)
        elif category == "sustainability":
            tags = random.sample(["circular-economy", "biodiversity", "esg", "sustainable-agriculture"], 3)
        elif category == "localized_forecast":
            tags = random.sample(["precipitation", "heatwave", "cyclone", "forecast", "rainfall"], 3)

        articles.append({
            "article_id": str(uuid.uuid4()),
            "url": f"https://example.com/climate/{cc.lower()}/{uuid.uuid4().hex[:8]}",
            "title": title,
            "source_name": source,
            "country_code": cc,
            "content_category": category,
            "overall_credibility": cred,
            "reliability_score": reliability,
            "published_date": pub_date,
            "excerpt": excerpt,
            "extracted_text": f"{title}. {excerpt} This report examines the climate situation in {country_name} with data from {year}.",
            "language_code": "en",
            "tags": tags,
            "claims_status": "completed",
        })

    return articles


def main():
    print("=" * 70)
    print("  CliLens.AI — Seed Global Climate Articles")
    print("=" * 70)

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASS
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        print(f"Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Get existing article counts per country
    cur.execute("""
        SELECT country_code, count(*) as cnt
        FROM articles
        WHERE country_code IS NOT NULL
        GROUP BY country_code
    """)
    existing = {r["country_code"]: r["cnt"] for r in cur.fetchall()}
    print(f"\nExisting countries with articles: {len(existing)}")

    total_inserted = 0
    countries_seeded = 0

    for cc, name in sorted(COUNTRIES.items()):
        current = existing.get(cc, 0)
        articles = generate_articles(cc, name, current)
        if not articles:
            continue

        for art in articles:
            try:
                cur.execute("""
                    INSERT INTO articles (
                        article_id, url, title, source_name, country_code,
                        content_category, overall_credibility, reliability_score,
                        published_date, excerpt, extracted_text, language_code,
                        tags, claims_status
                    ) VALUES (
                        %(article_id)s, %(url)s, %(title)s, %(source_name)s, %(country_code)s,
                        %(content_category)s, %(overall_credibility)s, %(reliability_score)s,
                        %(published_date)s, %(excerpt)s, %(extracted_text)s, %(language_code)s,
                        %(tags)s, %(claims_status)s
                    )
                    ON CONFLICT (url) DO NOTHING
                """, art)
                total_inserted += 1
            except Exception as e:
                print(f"  WARN: {cc} insert error: {e}")

        countries_seeded += 1
        print(f"  {cc} ({name}): +{len(articles)} articles (was {current})")

    # Summary
    cur.execute("SELECT count(*) as total FROM articles")
    total = cur.fetchone()["total"]
    cur.execute("SELECT count(DISTINCT country_code) as countries FROM articles WHERE country_code IS NOT NULL")
    country_count = cur.fetchone()["countries"]

    print(f"\n{'=' * 70}")
    print(f"  Summary")
    print(f"{'=' * 70}")
    print(f"  Countries seeded:  {countries_seeded}")
    print(f"  Articles inserted: {total_inserted}")
    print(f"  Total articles:    {total}")
    print(f"  Countries covered: {country_count}")
    print(f"{'=' * 70}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
