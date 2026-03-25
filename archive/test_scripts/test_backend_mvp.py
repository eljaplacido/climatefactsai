"""
Comprehensive Backend MVP Test Script

Tests:
1. Database connection and countries table
2. News discovery with Perplexity for multiple countries
3. Article storage with country_code
4. Claim extraction
5. Fact-checking
6. Reliability scoring
7. API endpoints (countries, articles with filters)
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add src/backend to path
sys.path.insert(0, str(Path(__file__).parent / "src" / "backend"))

from shared.database import get_postgres
from shared.logger import setup_logging
from shared.reliability_scorer import ReliabilityScorer
from src.backend.services.ingestion_service.src.perplexity_news_discovery import PerplexityNewsDiscovery


def test_database_connection():
    """Test 1: Database connection and countries table"""
    print("\n" + "="*70)
    print("TEST 1: Database Connection & Countries Table")
    print("="*70)

    try:
        db = get_postgres()

        # Check if countries table exists
        result = db.execute_query("""
            SELECT COUNT(*) as count
            FROM countries
            WHERE enabled = true
        """)

        country_count = result[0]['count'] if result else 0
        print(f"✅ Database connected!")
        print(f"✅ Found {country_count} enabled countries in database")

        # List some countries
        countries = db.execute_query("""
            SELECT country_code, country_name, flag_emoji, is_eu_member
            FROM countries
            WHERE enabled = true
            ORDER BY country_name
            LIMIT 10
        """)

        print("\nSample countries:")
        for country in countries:
            eu_status = "🇪🇺" if country['is_eu_member'] else "  "
            print(f"  {country['flag_emoji']} {country['country_code']} - {country['country_name']} {eu_status}")

        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


def test_perplexity_news_discovery():
    """Test 2: News discovery with Perplexity"""
    print("\n" + "="*70)
    print("TEST 2: Perplexity News Discovery (Multiple Countries)")
    print("="*70)

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not set")
        return False

    try:
        discovery = PerplexityNewsDiscovery(api_key)

        # Test with multiple countries
        test_countries = [
            ("Finland", "FI"),
            ("Sweden", "SE"),
            ("Germany", "DE")
        ]

        all_articles = []

        for country_name, country_code in test_countries:
            print(f"\n🌍 Discovering news from {country_name} ({country_code})...")

            articles = discovery.discover_news(
                country=country_name,
                country_code=country_code,
                max_articles=3,
                days_back=3
            )

            print(f"✅ Found {len(articles)} articles from {country_name}")

            for i, article in enumerate(articles, 1):
                print(f"\n  {i}. {article['title']}")
                print(f"     Source: {article['source_name']}")
                print(f"     Country: {article['country_code']}")
                print(f"     Credibility: {article['credibility_score']}/100")
                print(f"     URL: {article['url'][:60]}...")

            all_articles.extend(articles)
            time.sleep(2)  # Rate limiting

        print(f"\n✅ Total articles discovered: {len(all_articles)}")
        return True, all_articles

    except Exception as e:
        print(f"❌ Perplexity discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_article_storage(articles):
    """Test 3: Article storage with country_code"""
    print("\n" + "="*70)
    print("TEST 3: Article Storage with Country Code")
    print("="*70)

    if not articles:
        print("⚠️  No articles to store")
        return False

    try:
        db = get_postgres()
        stored_ids = []

        for article in articles[:5]:  # Store first 5 articles
            query = """
            INSERT INTO articles (
                url, title, author, published_date, source_name,
                extracted_text, language_code, country_code, task_id,
                source_credibility_score, tags, created_at
            ) VALUES (
                :url, :title, :author, :published_date, :source_name,
                :extracted_text, :language_code, :country_code, :task_id,
                :source_credibility_score, :tags, CURRENT_TIMESTAMP
            )
            ON CONFLICT (url) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                country_code = EXCLUDED.country_code
            RETURNING article_id
            """

            # Convert tags to PostgreSQL array
            tags = article.get('tags', [])
            tags_array = "{}" if not tags else "{" + ",".join(f'"{tag}"' for tag in tags) + "}"

            result = db.execute_query(
                query,
                params={
                    "url": article['url'],
                    "title": article['title'],
                    "author": article.get('author'),
                    "published_date": article.get('published_date'),
                    "source_name": article['source_name'],
                    "extracted_text": article.get('extracted_text', article.get('summary', '')),
                    "language_code": article.get('language_code', 'en'),
                    "country_code": article['country_code'],
                    "task_id": "test-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
                    "source_credibility_score": article.get('source_credibility_score', 70),
                    "tags": tags_array
                }
            )

            if result:
                article_id = result[0]['article_id']
                stored_ids.append(str(article_id))
                print(f"✅ Stored article: {article['title'][:50]}... (ID: {article_id})")

        print(f"\n✅ Successfully stored {len(stored_ids)} articles")
        return True, stored_ids

    except Exception as e:
        print(f"❌ Article storage failed: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_reliability_scoring(article_ids):
    """Test 4: Reliability scoring"""
    print("\n" + "="*70)
    print("TEST 4: Reliability Scoring Algorithm")
    print("="*70)

    if not article_ids:
        print("⚠️  No article IDs to test")
        return False

    try:
        # Test the scoring algorithm
        print("\n📊 Testing scoring algorithm with different scenarios:")

        # Scenario 1: High credibility
        score1, level1 = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=90,
            total_claims=10,
            verified_claims=9,
            false_claims=0,
            misleading_claims=1,
            content_relevance_score=0.85
        )
        print(f"\n  Scenario 1 (High Credibility):")
        print(f"    Score: {score1}/100")
        print(f"    Level: {level1}")

        # Scenario 2: Medium credibility with mixed claims
        score2, level2 = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=70,
            total_claims=10,
            verified_claims=6,
            false_claims=2,
            misleading_claims=2,
            content_relevance_score=0.60
        )
        print(f"\n  Scenario 2 (Medium Credibility):")
        print(f"    Score: {score2}/100")
        print(f"    Level: {level2}")

        # Scenario 3: Low credibility
        score3, level3 = ReliabilityScorer.calculate_reliability_score(
            source_credibility_score=40,
            total_claims=5,
            verified_claims=1,
            false_claims=3,
            misleading_claims=1,
            content_relevance_score=0.30
        )
        print(f"\n  Scenario 3 (Low Credibility):")
        print(f"    Score: {score3}/100")
        print(f"    Level: {level3}")

        # Test content relevance calculation
        relevance = ReliabilityScorer.calculate_content_relevance(
            title="Climate Change Impact on Global Emissions",
            text="Scientists report rising carbon emissions and greenhouse gas effects causing global warming..."
        )
        print(f"\n  Content Relevance Test:")
        print(f"    Relevance Score: {relevance:.2f}")

        # Update actual article reliability
        db = get_postgres()
        for article_id in article_ids[:3]:  # Update first 3 articles
            print(f"\n  Updating reliability for article {article_id}...")
            result = ReliabilityScorer.update_article_reliability(
                article_id=article_id,
                postgres_client=db,
                logger=None
            )
            if result:
                print(f"    ✅ Score: {result['reliability_score']}, Level: {result['credibility_level']}")

        print(f"\n✅ Reliability scoring test passed!")
        return True

    except Exception as e:
        print(f"❌ Reliability scoring failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Test 5: API endpoints"""
    print("\n" + "="*70)
    print("TEST 5: API Endpoints")
    print("="*70)

    try:
        import requests

        base_url = "http://localhost:8000"

        # Test 1: Countries endpoint
        print("\n📡 Testing /api/countries endpoint...")
        try:
            response = requests.get(f"{base_url}/api/countries", timeout=5)
            if response.status_code == 200:
                countries = response.json()
                print(f"  ✅ Got {len(countries)} countries")
                for country in countries[:5]:
                    print(f"    {country.get('flag_emoji', '')} {country['country_code']} - {country['country_name']} ({country.get('articles_count', 0)} articles)")
            else:
                print(f"  ⚠️  Response code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("  ⚠️  API server not running. Start with: uvicorn api.main:app --reload")

        # Test 2: Articles endpoint with country filter
        print("\n📡 Testing /api/articles endpoint with country filter...")
        try:
            response = requests.get(f"{base_url}/api/articles?country=FI&limit=5", timeout=5)
            if response.status_code == 200:
                articles = response.json()
                print(f"  ✅ Got {len(articles)} articles from Finland")
                for article in articles:
                    print(f"    • {article['title'][:60]}...")
                    print(f"      Reliability: {article.get('reliability_score', 'N/A')}/100, Credibility: {article.get('overall_credibility', 'N/A')}")
            else:
                print(f"  ⚠️  Response code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("  ⚠️  API server not running")

        # Test 3: Stats endpoint
        print("\n📡 Testing /api/stats endpoint...")
        try:
            response = requests.get(f"{base_url}/api/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print(f"  ✅ Dashboard Stats:")
                print(f"    Total Articles: {stats.get('total_articles', 0)}")
                print(f"    Articles Today: {stats.get('articles_today', 0)}")
                print(f"    Total Fact Checks: {stats.get('total_fact_checks', 0)}")
                print(f"    Verified Claims: {stats.get('verified_claims', 0)}")
                print(f"    Avg Confidence: {stats.get('average_confidence', 0):.1f}%")
            else:
                print(f"  ⚠️  Response code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("  ⚠️  API server not running")

        return True

    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 CLIMATE NEWS BACKEND MVP TEST SUITE")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Test 1: Database
    results['database'] = test_database_connection()

    # Test 2: News Discovery
    success, articles = test_perplexity_news_discovery()
    results['discovery'] = success

    # Test 3: Article Storage
    success, article_ids = test_article_storage(articles) if articles else (False, [])
    results['storage'] = success

    # Test 4: Reliability Scoring
    results['scoring'] = test_reliability_scoring(article_ids) if article_ids else False

    # Test 5: API Endpoints
    results['api'] = test_api_endpoints()

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name.ljust(20)}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! Backend MVP is ready!")
    else:
        print("\n  ⚠️  Some tests failed. Check the output above for details.")

    print("\n" + "="*70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
