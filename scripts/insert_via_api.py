#!/usr/bin/env python3
"""
Insert sample climate news articles via API
"""
import requests
import json
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000"

# Sample climate news articles
articles = [
    {
        "title": "Finland Leads EU in Renewable Energy Transition with 87% Clean Power",
        "url": "https://example.com/finland-renewable-energy-2025",
        "source_name": "Nordic Climate News",
        "country_code": "FI",
        "language": "en",
        "excerpt": "Finland has achieved remarkable milestone in renewable energy transition, reaching 87% clean energy in national grid...",
        "extracted_text": "Finland continues to lead the European Union's renewable energy transition, with latest data showing that 87% of the nation's electricity now comes from clean sources. The Nordic country's success story combines wind, solar, and hydroelectric power with innovative energy storage solutions.",
        "published_date": (datetime.now() - timedelta(days=1)).isoformat(),
        "fact_check_status": "verified"
    },
    {
        "title": "Sweden Invests €5 Billion in Carbon Capture Technology",
        "url": "https://example.com/sweden-carbon-capture-2025",
        "source_name": "Scandinavian Environmental Review",
        "country_code": "SE",
        "language": "en",
        "excerpt": "Swedish government announces massive €5 billion investment in carbon capture and storage facilities...",
        "extracted_text": "The Swedish government has announced a groundbreaking €5 billion investment program in carbon capture and storage (CCS) technology. This ambitious initiative aims to remove 10 million tons of CO2 annually by 2028, positioning Sweden as a global leader in negative emissions technology.",
        "published_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "fact_check_status": "pending"
    },
    {
        "title": "Denmark's Wind Energy Exports Reach Record €2.3 Billion",
        "url": "https://example.com/denmark-wind-exports-2025",
        "source_name": "Danish Energy Monitor",
        "country_code": "DK",
        "language": "en",
        "excerpt": "Denmark's wind energy sector exports hit record high of €2.3 billion in Q3 2025...",
        "extracted_text": "Denmark's offshore wind industry has achieved unprecedented export success, generating €2.3 billion in revenue during Q3 2025. The country's expertise in turbine manufacturing and offshore installation services continues to drive growth in international markets.",
        "published_date": (datetime.now() - timedelta(hours=12)).isoformat(),
        "fact_check_status": "verified"
    },
    {
        "title": "Norway Launches World's Largest Floating Solar Farm in Fjords",
        "url": "https://example.com/norway-floating-solar-2025",
        "source_name": "Nordic Innovation Today",
        "country_code": "NO",
        "language": "en",
        "excerpt": "Norway inaugurates revolutionary floating solar installation spanning 50 hectares in coastal fjords...",
        "extracted_text": "Norway has unveiled the world's largest floating solar farm, spanning 50 hectares across its scenic fjords. The innovative project combines Norway's abundant water resources with cutting-edge solar technology, generating enough electricity to power 15,000 homes while preserving valuable land for other uses.",
        "published_date": (datetime.now() - timedelta(hours=6)).isoformat(),
        "fact_check_status": "verified"
    },
    {
        "title": "Estonia Pioneers AI-Driven Smart Grid for 100% Renewable Integration",
        "url": "https://example.com/estonia-smart-grid-2025",
        "source_name": "Baltic Tech Review",
        "country_code": "EE",
        "language": "en",
        "excerpt": "Estonia deploys revolutionary AI-powered smart grid capable of managing 100% renewable energy sources...",
        "extracted_text": "Estonia has become the first Baltic nation to deploy a fully AI-driven smart grid system capable of managing 100% renewable energy integration. The system uses machine learning to predict energy demand and optimize distribution from wind, solar, and biomass sources in real-time.",
        "published_date": (datetime.now() - timedelta(hours=3)).isoformat(),
        "fact_check_status": "pending"
    }
]

def insert_article(article_data):
    """Insert article via API"""
    try:
        # First check if API is responding
        health = requests.get(f"{API_BASE}/health", timeout=5)
        if health.status_code != 200:
            print(f"❌ API health check failed: {health.status_code}")
            return False

        # Try to insert article directly to database via API
        # Since we don't have a direct article creation endpoint,
        # let's use the database connection from the API
        print(f"✓ API is healthy")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to API: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("CliLens.AI - Sample Article Insertion".center(80))
    print("="*80 + "\n")

    # Check API health
    print("[INFO] Checking API health...")
    if not insert_article(None):
        print("\n❌ API is not responding. Please ensure services are running:")
        print("   docker-compose up -d")
        return

    print("\n[INFO] API is healthy! Now inserting sample articles...\n")

    # Since direct API insertion isn't available, let's create SQL file
    print("[INFO] Creating SQL file for manual insertion...")

    sql_statements = []
    for idx, article in enumerate(articles, 1):
        article_id = f"sample-{idx:03d}"
        sql = f"""
INSERT INTO articles (
    article_id, url, title, source_name, country_code,
    language, excerpt, extracted_text, published_date,
    fact_check_status, created_at, updated_at
) VALUES (
    '{article_id}',
    '{article['url']}',
    '{article['title'].replace("'", "''")}',
    '{article['source_name']}',
    '{article['country_code']}',
    '{article['language']}',
    '{article['excerpt'].replace("'", "''")}',
    '{article['extracted_text'].replace("'", "''")}',
    '{article['published_date']}',
    '{article['fact_check_status']}',
    NOW(),
    NOW()
) ON CONFLICT (article_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();
"""
        sql_statements.append(sql)
        print(f"  [{idx}/5] Generated SQL for: {article['title'][:60]}...")

    # Write SQL file
    sql_file = "insert_sample_articles.sql"
    with open(sql_file, 'w', encoding='utf-8') as f:
        f.write("-- CliLens.AI Sample Climate News Articles\n")
        f.write("-- Generated: " + datetime.now().isoformat() + "\n\n")
        f.write("BEGIN;\n\n")
        f.write('\n'.join(sql_statements))
        f.write("\n\nCOMMIT;\n")

    print(f"\n✓ Created {sql_file}")
    print("\n[INFO] To insert articles into database, run:")
    print(f"   docker exec -i climatenews-postgres psql -U postgres -d climatenews < {sql_file}")
    print("\nOr manually:")
    print(f"   cat {sql_file} | docker exec -i climatenews-postgres psql -U postgres -d climatenews")

    print("\n" + "="*80)
    print("[SUCCESS] SQL file ready for insertion!".center(80))
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
