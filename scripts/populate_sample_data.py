#!/usr/bin/env python3
"""
Populate CliLens.AI database with sample climate news articles for UI testing
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'climatenews',
    'user': 'postgres',
    'password': os.getenv("POSTGRES_PASSWORD", "")
}

# Sample climate news articles
SAMPLE_ARTICLES = [
    {
        'title': 'Finland Announces New Climate Action Plan for 2030',
        'url': 'https://yle.fi/climate/finland-climate-action-2030',
        'author': 'Mika Virtanen',
        'source_name': 'Yle',
        'country_code': 'FI',
        'excerpt': 'Finland unveils ambitious plan to cut emissions by 60% by 2030, including major investments in renewable energy and carbon capture technology.',
        'extracted_text': 'Finland has announced a comprehensive climate action plan aimed at reducing greenhouse gas emissions by 60% by 2030. The plan includes significant investments in wind and solar energy, forest conservation, and carbon capture technologies. Prime Minister stated that Finland aims to be carbon neutral by 2035, five years ahead of the EU target.',
        'language_code': 'fi',
        'reliability_score': 92,
        'overall_credibility': 'HIGH',
        'tags': ['policy', 'renewable-energy', 'emissions'],
        'source_credibility_score': 92
    },
    {
        'title': 'Swedish Solar Energy Production Hits Record Levels',
        'url': 'https://svt.se/climate/sweden-solar-record-2025',
        'author': 'Anna Bergström',
        'source_name': 'SVT',
        'country_code': 'SE',
        'excerpt': 'Sweden has reached a new milestone with solar energy producing 15% of total electricity demand during summer months.',
        'extracted_text': 'Swedish solar energy production reached unprecedented levels this summer, contributing 15% to the national electricity grid during peak months. The increase is attributed to new solar farms in southern Sweden and government incentives for residential solar installations. Energy experts predict this trend will continue as costs decrease.',
        'language_code': 'sv',
        'reliability_score': 88,
        'overall_credibility': 'HIGH',
        'tags': ['renewable-energy', 'solar', 'energy-production'],
        'source_credibility_score': 88
    },
    {
        'title': 'Denmark Leads Europe in Wind Energy Adoption',
        'url': 'https://dr.dk/climate/denmark-wind-leadership-2025',
        'author': 'Lars Nielsen',
        'source_name': 'DR',
        'country_code': 'DK',
        'excerpt': 'Denmark now generates over 80% of its electricity from wind power, setting a global benchmark for renewable energy transition.',
        'extracted_text': 'Denmark has achieved a remarkable milestone, with wind energy now accounting for more than 80% of the country electricity production. The success is driven by extensive offshore wind farms in the North Sea and Baltic Sea. Danish technology companies are exporting their expertise globally, particularly to emerging markets.',
        'language_code': 'da',
        'reliability_score': 95,
        'overall_credibility': 'HIGH',
        'tags': ['renewable-energy', 'wind-power', 'energy-transition'],
        'source_credibility_score': 90
    },
    {
        'title': 'Germany Invests €50 Billion in Green Hydrogen Infrastructure',
        'url': 'https://dw.com/climate/germany-hydrogen-investment',
        'author': 'Thomas Schmidt',
        'source_name': 'Deutsche Welle',
        'country_code': 'DE',
        'excerpt': 'Germany announces massive investment in green hydrogen production and distribution network to decarbonize heavy industry.',
        'extracted_text': 'The German government has approved a €50 billion investment package for green hydrogen infrastructure over the next decade. The initiative aims to produce hydrogen using renewable electricity, replacing fossil fuels in steel, cement, and chemical industries. Germany plans to become a global leader in hydrogen technology and export expertise.',
        'language_code': 'de',
        'reliability_score': 90,
        'overall_credibility': 'HIGH',
        'tags': ['hydrogen', 'industrial-decarbonization', 'investment'],
        'source_credibility_score': 88
    },
    {
        'title': 'France Expands Nuclear Fleet to Support Net-Zero Goals',
        'url': 'https://france24.com/climate/france-nuclear-expansion',
        'author': 'Marie Dubois',
        'source_name': 'France 24',
        'country_code': 'FR',
        'excerpt': 'France announces construction of six new nuclear reactors to ensure stable, low-carbon electricity supply.',
        'extracted_text': 'France has confirmed plans to build six new-generation nuclear reactors as part of its strategy to achieve net-zero emissions by 2050. President Macron emphasized that nuclear energy, combined with renewables, will provide reliable baseload power while reducing carbon emissions. The first reactor is expected to be operational by 2035.',
        'language_code': 'fr',
        'reliability_score': 85,
        'overall_credibility': 'HIGH',
        'tags': ['nuclear-energy', 'energy-policy', 'net-zero'],
        'source_credibility_score': 85
    },
    {
        'title': 'Norway Electric Vehicle Sales Reach 95% Market Share',
        'url': 'https://nrk.no/climate/norway-ev-adoption-2025',
        'author': 'Kari Johansen',
        'source_name': 'NRK',
        'country_code': 'NO',
        'excerpt': 'Norway achieves world-leading electric vehicle adoption with 95% of new car sales being fully electric.',
        'extracted_text': 'Norway has reached an unprecedented 95% market share for electric vehicles in new car sales, far exceeding any other country. The achievement is attributed to generous tax incentives, extensive charging infrastructure, and high public awareness of climate issues. Norway aims for 100% electric vehicle sales by 2025.',
        'language_code': 'no',
        'reliability_score': 93,
        'overall_credibility': 'HIGH',
        'tags': ['electric-vehicles', 'transportation', 'climate-action'],
        'source_credibility_score': 92
    },
    {
        'title': 'Spanish Renewable Energy Capacity Doubles in Three Years',
        'url': 'https://elpais.com/climate/spain-renewables-growth',
        'author': 'Carlos Martínez',
        'source_name': 'El País',
        'country_code': 'ES',
        'excerpt': 'Spain renewable energy capacity has doubled since 2022, with solar and wind leading the growth.',
        'extracted_text': 'Spain has successfully doubled its renewable energy capacity over the past three years, now generating over 60% of electricity from renewable sources. The expansion includes large-scale solar farms in Andalusia and new wind installations in Galicia. The government aims for 75% renewable electricity by 2030.',
        'language_code': 'es',
        'reliability_score': 87,
        'overall_credibility': 'HIGH',
        'tags': ['renewable-energy', 'solar', 'wind-power'],
        'source_credibility_score': 85
    },
    {
        'title': 'Poland Begins Coal Phase-Out with First Mine Closures',
        'url': 'https://tvn24.pl/climate/poland-coal-phaseout-begins',
        'author': 'Piotr Kowalski',
        'source_name': 'TVN24',
        'country_code': 'PL',
        'excerpt': 'Poland announces closure of three coal mines as part of its transition to cleaner energy sources.',
        'extracted_text': 'Poland has taken a significant step in its energy transition by announcing the closure of three coal mines over the next two years. The decision marks a historic shift for the country, which has heavily relied on coal for decades. Workers will be retrained for jobs in renewable energy sectors, and affected regions will receive economic support.',
        'language_code': 'pl',
        'reliability_score': 80,
        'overall_credibility': 'MEDIUM',
        'tags': ['coal-phaseout', 'energy-transition', 'just-transition'],
        'source_credibility_score': 78
    },
    {
        'title': 'Dutch Farmers Adopt Regenerative Agriculture at Scale',
        'url': 'https://nos.nl/climate/netherlands-regenerative-farming',
        'author': 'Jan de Vries',
        'source_name': 'NOS',
        'country_code': 'NL',
        'excerpt': 'Netherlands farmers increasingly adopting regenerative practices that sequester carbon while improving soil health.',
        'extracted_text': 'A growing number of Dutch farmers are transitioning to regenerative agriculture practices that focus on soil health, biodiversity, and carbon sequestration. These methods include crop rotation, cover cropping, and reduced tillage. Studies show these farms can sequester up to 2 tons of CO2 per hectare annually while maintaining productivity.',
        'language_code': 'nl',
        'reliability_score': 84,
        'overall_credibility': 'HIGH',
        'tags': ['agriculture', 'carbon-sequestration', 'regenerative-farming'],
        'source_credibility_score': 82
    },
    {
        'title': 'Italy Launches Mediterranean Solar Alliance',
        'url': 'https://ansa.it/climate/italy-mediterranean-solar',
        'author': 'Giuseppe Rossi',
        'source_name': 'ANSA',
        'country_code': 'IT',
        'excerpt': 'Italy coordinates new alliance of Mediterranean countries to develop large-scale solar energy projects.',
        'extracted_text': 'Italy has launched the Mediterranean Solar Alliance, bringing together countries around the Mediterranean Sea to collaborate on solar energy development. The initiative aims to leverage the regions abundant sunshine to produce clean electricity and green hydrogen. Projects will include both domestic installations and potential undersea cables to Northern Europe.',
        'language_code': 'it',
        'reliability_score': 82,
        'overall_credibility': 'MEDIUM',
        'tags': ['solar', 'international-cooperation', 'energy-infrastructure'],
        'source_credibility_score': 80
    }
]

def create_sample_articles():
    """Insert sample articles into the database"""
    conn = None
    try:
        # Connect to database
        print(f"Connecting to database at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Clear existing sample data (optional)
        print("Clearing any existing sample data...")
        cursor.execute("DELETE FROM article_feedback;")
        cursor.execute("DELETE FROM fact_checks;")
        cursor.execute("DELETE FROM claims;")
        cursor.execute("DELETE FROM articles;")

        # Insert articles
        print(f"\nInserting {len(SAMPLE_ARTICLES)} sample articles...")

        article_values = []
        for article in SAMPLE_ARTICLES:
            article_id = str(uuid.uuid4())
            published_date = datetime.now() - timedelta(days=int(uuid.uuid4().int % 30))

            article_values.append((
                article_id,
                article['url'],
                article['title'],
                article.get('author'),
                published_date,
                article['source_name'],
                article['extracted_text'],
                article['excerpt'],
                article['language_code'],
                article['tags'],
                article.get('country_code'),
                article.get('source_credibility_score'),
                0.85,  # content_relevance_score
                article['reliability_score'],
                article['overall_credibility'],
                0,  # claims_count
                0   # verified_claims_count
            ))

            print(f"  ✓ {article['country_code']}: {article['title'][:60]}...")

        insert_query = """
            INSERT INTO articles (
                article_id, url, title, author, published_date, source_name,
                extracted_text, excerpt, language_code, tags, country_code,
                source_credibility_score, content_relevance_score, reliability_score,
                overall_credibility, claims_count, verified_claims_count
            ) VALUES %s
        """

        execute_values(cursor, insert_query, article_values)

        # Insert sample claims for first article
        print("\nInserting sample claims and fact-checks...")

        # Get first article ID
        cursor.execute("SELECT article_id FROM articles LIMIT 1")
        first_article_id = cursor.fetchone()[0]

        sample_claims = [
            {
                'claim_text': 'Finland aims to reduce emissions by 60% by 2030',
                'claim_context': 'Government climate action plan announcement',
                'entities': ['Finland', '60%', '2030']
            },
            {
                'claim_text': 'Finland plans to be carbon neutral by 2035',
                'claim_context': 'Five years ahead of EU target',
                'entities': ['Finland', 'carbon neutral', '2035', 'EU']
            }
        ]

        for idx, claim in enumerate(sample_claims):
            claim_id = str(uuid.uuid4())

            # Insert claim
            cursor.execute("""
                INSERT INTO claims (
                    claim_id, article_id, claim_text, claim_context, entities
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                claim_id,
                first_article_id,
                claim['claim_text'],
                claim['claim_context'],
                claim['entities']
            ))

            # Insert fact-check
            cursor.execute("""
                INSERT INTO fact_checks (
                    fact_check_id, claim_id, verification_status, confidence_score,
                    justification, evidence_sources, verified_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                claim_id,
                'VERIFIED',
                0.95,
                'Verified through official government sources and press releases. The Finnish Climate Change Act amendment confirms these targets.',
                ['https://valtioneuvosto.fi/climate-policy', 'https://ym.fi/en/climate-change-act'],
                datetime.now()
            ))

            print(f"  ✓ Claim {idx+1}: {claim['claim_text'][:50]}... [VERIFIED]")

        # Update claims count
        cursor.execute("""
            UPDATE articles SET claims_count = 2, verified_claims_count = 2
            WHERE article_id = %s
        """, (first_article_id,))

        # Commit changes
        conn.commit()

        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM articles")
        article_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM claims")
        claim_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM fact_checks")
        fact_check_count = cursor.fetchone()[0]

        print(f"\n✅ Success! Database populated with:")
        print(f"   • {article_count} articles")
        print(f"   • {claim_count} claims")
        print(f"   • {fact_check_count} fact-checks")

        print(f"\n🌍 Articles by country:")
        cursor.execute("""
            SELECT country_code, COUNT(*) as count
            FROM articles
            GROUP BY country_code
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            cursor.execute("""
                SELECT country_name, flag_emoji FROM countries WHERE country_code = %s
            """, (row[0],))
            country_info = cursor.fetchone()
            if country_info:
                print(f"   {country_info[1]} {country_info[0]}: {row[1]} article(s)")

        print(f"\n📊 Credibility distribution:")
        cursor.execute("""
            SELECT overall_credibility, COUNT(*) as count
            FROM articles
            GROUP BY overall_credibility
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            print(f"   • {row[0]}: {row[1]} article(s)")

        print(f"\n🎯 Next steps:")
        print(f"   1. View articles in API: http://localhost:8000/api/articles")
        print(f"   2. Check stats: http://localhost:8000/api/stats")
        print(f"   3. Open frontend: http://localhost:3000")
        print(f"   4. Filter by country: http://localhost:3000/?country=FI")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            cursor.close()
            conn.close()
            print(f"\n🔌 Database connection closed.")

if __name__ == "__main__":
    print("=" * 80)
    print("  CliLens.AI - Sample Data Population Script".center(80))
    print("=" * 80)
    print()

    success = create_sample_articles()

    if success:
        print("\n✅ All done! Your frontend should now display articles.")
        sys.exit(0)
    else:
        print("\n❌ Failed to populate database. Check errors above.")
        sys.exit(1)
