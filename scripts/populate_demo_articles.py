"""
Populate database with demo climate articles for UI testing.
Run this script to see articles immediately in the web interface.
"""

import psycopg2
from datetime import datetime, timedelta
import random

# Database connection
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "climatenews"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")

# Sample articles
DEMO_ARTICLES = [
    {
        "title": "Arctic Sea Ice Hits Record Low in 2024",
        "url": "https://example.com/arctic-ice-2024",
        "source": "Nature Climate Change",
        "author": "Dr. Jane Smith",
        "excerpt": "New satellite data reveals unprecedented decline in Arctic sea ice extent, raising concerns about accelerated climate feedback loops.",
        "full_text": "Scientists have observed a dramatic reduction in Arctic sea ice coverage during the 2024 summer season...",
        "credibility_score": 0.92,
        "credibility_level": "high",
        "country": "US",
        "tags": ["arctic", "sea-ice", "climate-feedback"],
    },
    {
        "title": "EU Announces €50 Billion Climate Adaptation Fund",
        "url": "https://example.com/eu-climate-fund-2024",
        "source": "European Commission",
        "author": "Policy Team",
        "excerpt": "The European Union has committed €50 billion over five years to help member states adapt to climate change impacts.",
        "full_text": "In a landmark decision, the European Commission approved a comprehensive climate adaptation package...",
        "credibility_score": 0.95,
        "credibility_level": "high",
        "country": "BE",
        "tags": ["eu-policy", "climate-finance", "adaptation"],
    },
    {
        "title": "New Solar Technology Achieves 40% Efficiency",
        "url": "https://example.com/solar-breakthrough-2024",
        "source": "MIT Technology Review",
        "author": "Tech Reporter",
        "excerpt": "Researchers at Stanford University have developed a new multi-junction solar cell with record-breaking efficiency.",
        "full_text": "A team of materials scientists has achieved a significant breakthrough in photovoltaic technology...",
        "credibility_score": 0.88,
        "credibility_level": "high",
        "country": "US",
        "tags": ["renewable-energy", "solar-power", "technology"],
    },
    {
        "title": "Global CO2 Emissions Plateau in 2024",
        "url": "https://example.com/emissions-plateau-2024",
        "source": "International Energy Agency",
        "author": "IEA Analysis Team",
        "excerpt": "For the first time in decades, global carbon dioxide emissions have stopped growing, according to IEA data.",
        "full_text": "The International Energy Agency reports that global CO2 emissions from energy remained flat in 2024...",
        "credibility_score": 0.90,
        "credibility_level": "high",
        "country": "FR",
        "tags": ["emissions", "iea", "global-climate"],
    },
    {
        "title": "Amazon Rainforest Deforestation Rate Drops 30%",
        "url": "https://example.com/amazon-deforestation-2024",
        "source": "Brazil National Institute for Space Research",
        "author": "Environmental Team",
        "excerpt": "Satellite monitoring shows significant reduction in Amazon deforestation following new conservation policies.",
        "full_text": "Brazil's latest satellite data indicates a 30% decrease in Amazon rainforest deforestation...",
        "credibility_score": 0.86,
        "credibility_level": "high",
        "country": "BR",
        "tags": ["deforestation", "amazon", "conservation"],
    },
    {
        "title": "Climate Adaptation Costs Underestimated by 50%, Study Finds",
        "url": "https://example.com/adaptation-costs-2024",
        "source": "Nature Sustainability",
        "author": "Dr. Maria Garcia",
        "excerpt": "New research suggests that the costs of adapting to climate change have been significantly underestimated by policymakers.",
        "full_text": "A comprehensive study published in Nature Sustainability reveals that adaptation costs are 50% higher than previously estimated...",
        "credibility_score": 0.84,
        "credibility_level": "high",
        "country": "UK",
        "tags": ["adaptation", "climate-finance", "policy"],
    },
    {
        "title": "Ocean Heat Content Reaches New High in 2024",
        "url": "https://example.com/ocean-heat-2024",
        "source": "NOAA Climate.gov",
        "author": "Climate Science Team",
        "excerpt": "The world's oceans absorbed more heat in 2024 than any year on record, according to NOAA measurements.",
        "full_text": "Data from the National Oceanic and Atmospheric Administration shows that ocean heat content reached unprecedented levels...",
        "credibility_score": 0.93,
        "credibility_level": "high",
        "country": "US",
        "tags": ["ocean-warming", "noaa", "climate-indicators"],
    },
    {
        "title": "Green Hydrogen Production Costs Fall Below $2/kg",
        "url": "https://example.com/hydrogen-costs-2024",
        "source": "Bloomberg New Energy Finance",
        "author": "Energy Markets Team",
        "excerpt": "Falling renewable energy prices and improved electrolyzer efficiency are driving down green hydrogen costs.",
        "full_text": "The cost of producing green hydrogen has fallen below the critical $2 per kilogram threshold in several regions...",
        "credibility_score": 0.82,
        "credibility_level": "high",
        "country": "DE",
        "tags": ["hydrogen", "renewable-energy", "energy-transition"],
    },
]


def populate_articles():
    """Insert demo articles into the database."""
    conn = None
    cursor = None
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cursor = conn.cursor()
        
        print(f"Connected to database: {DB_NAME}")
        
        # Clear existing demo articles (optional)
        cursor.execute("DELETE FROM articles WHERE url LIKE 'https://example.com/%'")
        print(f"Cleared {cursor.rowcount} existing demo articles")
        
        # Ensure countries exist (with required language_code)
        cursor.execute("""
            INSERT INTO countries (country_code, country_name, language_code) VALUES
            ('US', 'United States', 'en'),
            ('BE', 'Belgium', 'en'),
            ('FR', 'France', 'fr'),
            ('BR', 'Brazil', 'pt'),
            ('UK', 'United Kingdom', 'en'),
            ('DE', 'Germany', 'de')
            ON CONFLICT (country_code) DO NOTHING
        """)
        
        # Insert articles
        inserted = 0
        for i, article in enumerate(DEMO_ARTICLES):
            # Generate published date (random within last 30 days)
            published_at = datetime.now() - timedelta(days=random.randint(1, 30))
            
            cursor.execute("""
                INSERT INTO articles (
                    title, url, source_name, author, published_date,
                    extracted_text, excerpt,
                    reliability_score, overall_credibility,
                    country_code, tags,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING article_id
            """, (
                article["title"],
                article["url"],
                article["source"],
                article["author"],
                published_at,
                article["full_text"],
                article["excerpt"],
                int(article["credibility_score"] * 100),  # Convert to 0-100 integer
                article["credibility_level"],
                article["country"],
                article["tags"],
            ))
            
            article_id = cursor.fetchone()[0]
            inserted += 1
            print(f"  [{i+1}/{len(DEMO_ARTICLES)}] Inserted: {article['title']} (ID: {article_id})")
        
        # Commit transaction
        conn.commit()
        print(f"\n[OK] Successfully inserted {inserted} demo articles!")
        print(f"\nYou can now view them at: http://localhost:5300")
        
        # Close connection
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"[X] Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"[X] Error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("CliLens.AI - Demo Article Populator")
    print("=" * 60)
    print()
    populate_articles()

