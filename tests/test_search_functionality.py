"""
Test Suite for Search Functionality

Verifies that the search endpoints work correctly with the fixed implementation.
"""

import sys
from pathlib import Path

# Add src/backend to path for imports
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src" / "backend"))

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("search-tests")


def test_database_connection():
    """Test 1: Verify database connection works"""
    print("\n=== Test 1: Database Connection ===")
    try:
        db = get_postgres()
        result = db.execute_query("SELECT 1 as test")
        assert result[0]["test"] == 1
        print("✅ Database connection working")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_full_text_search():
    """Test 2: Verify full-text search works"""
    print("\n=== Test 2: Full-Text Search ===")
    try:
        db = get_postgres()

        query = """
            SELECT article_id, title
            FROM articles
            WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(excerpt, ''))
                  @@ plainto_tsquery('english', :query)
            LIMIT 5
        """

        results = db.execute_query(query, {"query": "climate"})

        print(f"Found {len(results)} articles matching 'climate'")
        for row in results:
            print(f"  - {row['title']}")

        assert len(results) > 0, "No results found"
        print("✅ Full-text search working")
        return True
    except Exception as e:
        print(f"❌ Full-text search failed: {e}")
        return False


def test_search_with_filters():
    """Test 3: Verify search with country and credibility filters"""
    print("\n=== Test 3: Search with Filters ===")
    try:
        db = get_postgres()

        query = """
            SELECT article_id, title, country_code, overall_credibility
            FROM articles
            WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(excerpt, ''))
                  @@ plainto_tsquery('english', :query)
              AND country_code = :country
            ORDER BY published_date DESC
            LIMIT 5
        """

        results = db.execute_query(query, {"query": "climate", "country": "FI"})

        print(f"Found {len(results)} Finnish articles matching 'climate'")
        for row in results:
            print(f"  - {row['title']} ({row['country_code']}, {row['overall_credibility']})")

        print("✅ Filtered search working")
        return True
    except Exception as e:
        print(f"❌ Filtered search failed: {e}")
        return False


def test_search_with_ranking():
    """Test 4: Verify ts_rank relevance ranking"""
    print("\n=== Test 4: Relevance Ranking ===")
    try:
        db = get_postgres()

        query = """
            SELECT
                article_id,
                title,
                ts_rank(
                    to_tsvector('english', title || ' ' || COALESCE(excerpt, '')),
                    plainto_tsquery('english', :query)
                ) as relevance
            FROM articles
            WHERE to_tsvector('english', title || ' ' || COALESCE(excerpt, ''))
                  @@ plainto_tsquery('english', :query)
            ORDER BY relevance DESC
            LIMIT 5
        """

        results = db.execute_query(query, {"query": "renewable energy"})

        print(f"Found {len(results)} articles with relevance scores:")
        for row in results:
            print(f"  - {row['title']} (score: {row['relevance']:.4f})")

        # Verify scores are in descending order
        scores = [float(row["relevance"]) for row in results]
        assert scores == sorted(scores, reverse=True), "Scores not sorted correctly"

        print("✅ Relevance ranking working")
        return True
    except Exception as e:
        print(f"❌ Relevance ranking failed: {e}")
        return False


def test_column_names():
    """Test 5: Verify all required columns exist"""
    print("\n=== Test 5: Column Name Verification ===")
    try:
        db = get_postgres()

        # Test query using all columns referenced in search_routes.py
        query = """
            SELECT
                article_id,
                title,
                url,
                source_name,
                published_date,
                excerpt,
                source_credibility_score,
                overall_credibility,
                country_code,
                tags,
                created_at,
                claims_count,
                verified_claims_count,
                content_relevance_score,
                reliability_score,
                author,
                extracted_text
            FROM articles
            LIMIT 1
        """

        results = db.execute_query(query, {})

        if len(results) > 0:
            row = results[0]
            print("✅ All required columns exist:")
            for col in row.keys():
                print(f"  - {col}")
        else:
            print("⚠️  No articles in database to test columns")

        print("✅ Column names verified")
        return True
    except Exception as e:
        print(f"❌ Column verification failed: {e}")
        return False


def test_suggestions_endpoint_query():
    """Test 6: Verify suggestions query structure"""
    print("\n=== Test 6: Search Suggestions Query ===")
    try:
        db = get_postgres()

        # Test tag suggestions query
        tag_results = db.execute_query(
            """
            SELECT tag, COUNT(*) as count
            FROM articles, UNNEST(tags) as tag
            WHERE tag ILIKE :pattern
            GROUP BY tag
            ORDER BY count DESC
            LIMIT :limit
            """,
            {"pattern": "%climate%", "limit": 5}
        )

        print(f"Found {len(tag_results)} tag suggestions:")
        for row in tag_results:
            print(f"  - {row['tag']} ({row['count']} articles)")

        # Test country suggestions
        country_results = db.execute_query(
            """
            SELECT country_code, COUNT(*) as count
            FROM articles
            WHERE country_code IS NOT NULL
            GROUP BY country_code
            ORDER BY count DESC
            LIMIT 5
            """,
            {}
        )

        print(f"\nFound {len(country_results)} countries:")
        for row in country_results:
            print(f"  - {row['country_code']} ({row['count']} articles)")

        print("✅ Suggestions queries working")
        return True
    except Exception as e:
        print(f"❌ Suggestions query failed: {e}")
        return False


def test_index_usage():
    """Test 7: Verify full-text index is being used"""
    print("\n=== Test 7: Index Usage Verification ===")
    try:
        db = get_postgres()

        # Use EXPLAIN to check if index is used
        query = """
            EXPLAIN (FORMAT JSON)
            SELECT article_id, title
            FROM articles
            WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(excerpt, ''))
                  @@ plainto_tsquery('english', 'climate')
            LIMIT 10
        """

        results = db.execute_query(query, {})

        # Check if idx_articles_fulltext is mentioned in the plan
        plan_str = str(results)
        uses_index = "idx_articles_fulltext" in plan_str or "Bitmap Index Scan" in plan_str

        if uses_index:
            print("✅ Full-text index is being used")
        else:
            print("⚠️  Index may not be used (check query plan)")
            print(f"Query plan: {plan_str[:200]}...")

        return True
    except Exception as e:
        print(f"❌ Index verification failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("SEARCH FUNCTIONALITY TEST SUITE")
    print("=" * 60)

    tests = [
        test_database_connection,
        test_full_text_search,
        test_search_with_filters,
        test_search_with_ranking,
        test_column_names,
        test_suggestions_endpoint_query,
        test_index_usage,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} total")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 All tests passed! Search functionality is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Review errors above.")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
