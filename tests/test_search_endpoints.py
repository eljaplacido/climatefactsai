"""
Test Search Endpoints

Tests all search functionality including:
- Basic search (freemium)
- Semantic search (premium)
- Search suggestions
- Saved searches
"""

import requests
import json
from typing import Optional

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_URL = f"{API_BASE_URL}/api"


def print_test_header(test_name: str):
    """Print formatted test header"""
    print("\n" + "=" * 70)
    print(f"TEST: {test_name}")
    print("=" * 70)


def print_result(success: bool, message: str, data: Optional[dict] = None):
    """Print test result"""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")
    if data:
        print(f"   Data: {json.dumps(data, indent=2)[:200]}...")


def test_basic_search():
    """Test 1: Basic search endpoint (no auth required)"""
    print_test_header("Basic Search (Freemium)")

    try:
        # Test 1a: Simple search
        response = requests.get(f"{API_URL}/search/", params={"q": "climate"})
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Basic search successful - {len(data)} results",
                        {"first_result": data[0]["title"] if data else "No results"})
        else:
            print_result(False, f"Basic search failed: {response.text}")

        # Test 1b: Search with filters
        response = requests.get(f"{API_URL}/search/", params={
            "q": "climate",
            "country": "FI",
            "limit": 5
        })

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Filtered search successful - {len(data)} results")
        else:
            print_result(False, f"Filtered search failed: {response.text}")

        # Test 1c: Edge case - empty query
        response = requests.get(f"{API_URL}/search/", params={"q": ""})

        if response.status_code == 422:  # Validation error
            print_result(True, "Empty query validation works correctly")
        else:
            print_result(False, f"Empty query should return 422, got {response.status_code}")

    except Exception as e:
        print_result(False, f"Basic search test crashed: {str(e)}")


def test_search_suggestions():
    """Test 2: Search suggestions endpoint"""
    print_test_header("Search Suggestions")

    try:
        # Test tag suggestions
        response = requests.get(f"{API_URL}/search/suggestions", params={
            "q": "climate",
            "category": "tag",
            "limit": 5
        })

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Tag suggestions successful - {len(data)} suggestions",
                        {"suggestions": [s["text"] for s in data[:3]]})
        else:
            print_result(False, f"Tag suggestions failed: {response.text}")

        # Test country suggestions
        response = requests.get(f"{API_URL}/search/suggestions", params={
            "q": "F",
            "category": "country",
            "limit": 5
        })

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Country suggestions successful - {len(data)} suggestions")
        else:
            print_result(False, f"Country suggestions failed: {response.text}")

    except Exception as e:
        print_result(False, f"Suggestions test crashed: {str(e)}")


def test_semantic_search_without_auth():
    """Test 3: Semantic search requires authentication"""
    print_test_header("Semantic Search - No Auth")

    try:
        # Test GET method
        response = requests.get(f"{API_URL}/search/semantic", params={
            "query": "climate change",
            "limit": 5
        })

        if response.status_code == 401:
            print_result(True, "GET semantic search correctly requires auth")
        else:
            print_result(False, f"Expected 401, got {response.status_code}: {response.text}")

        # Test POST method
        response = requests.post(f"{API_URL}/search/semantic", json={
            "query": "renewable energy",
            "limit": 5
        })

        if response.status_code == 401:
            print_result(True, "POST semantic search correctly requires auth")
        else:
            print_result(False, f"Expected 401, got {response.status_code}")

    except Exception as e:
        print_result(False, f"Semantic search auth test crashed: {str(e)}")


def test_semantic_search_with_freemium():
    """Test 4: Semantic search with freemium account (should fail)"""
    print_test_header("Semantic Search - Freemium User")

    try:
        # First, register a test user
        register_response = requests.post(f"{API_URL}/auth/register", json={
            "email": "test_freemium@example.com",
            "password": "SecurePass123!",
            "full_name": "Test Freemium User"
        })

        if register_response.status_code in [200, 201]:
            token = register_response.json().get("access_token")
            print_result(True, "Freemium user registered successfully")

            # Try semantic search with freemium tier
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{API_URL}/search/semantic",
                                   params={"query": "climate"},
                                   headers=headers)

            if response.status_code == 403:
                print_result(True, "Freemium user correctly denied semantic search")
            else:
                print_result(False, f"Expected 403, got {response.status_code}: {response.text}")
        else:
            print_result(False, f"User registration failed: {register_response.text}")

    except Exception as e:
        print_result(False, f"Freemium test crashed: {str(e)}")


def test_search_performance():
    """Test 5: Search performance and response times"""
    print_test_header("Search Performance")

    try:
        import time

        # Test basic search performance
        start = time.time()
        response = requests.get(f"{API_URL}/search/", params={
            "q": "climate change renewable energy",
            "limit": 20
        })
        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Basic search completed in {duration:.2f}s - {len(data)} results")

            if duration < 1.0:
                print_result(True, "Search performance is good (<1s)")
            else:
                print_result(False, f"Search is slow ({duration:.2f}s)")
        else:
            print_result(False, f"Performance test failed: {response.status_code}")

    except Exception as e:
        print_result(False, f"Performance test crashed: {str(e)}")


def test_search_ranking():
    """Test 6: Search result ranking"""
    print_test_header("Search Result Ranking")

    try:
        # Search for specific terms
        response = requests.get(f"{API_URL}/search/", params={
            "q": "renewable energy",
            "limit": 10
        })

        if response.status_code == 200:
            data = response.json()

            # Check that results are relevant
            if len(data) > 0:
                print_result(True, f"Retrieved {len(data)} results")
                print(f"   Top result: {data[0]['title']}")

                # Check that results contain the search terms
                relevant_count = sum(1 for article in data
                                   if "renewable" in article["title"].lower() or
                                      "energy" in article["title"].lower() or
                                      ("excerpt" in article and article["excerpt"] and
                                       ("renewable" in article["excerpt"].lower() or
                                        "energy" in article["excerpt"].lower())))

                relevance_ratio = relevant_count / len(data)
                print_result(True, f"Relevance: {relevance_ratio*100:.1f}% of results contain search terms")
            else:
                print_result(False, "No results returned")
        else:
            print_result(False, f"Ranking test failed: {response.status_code}")

    except Exception as e:
        print_result(False, f"Ranking test crashed: {str(e)}")


def test_search_edge_cases():
    """Test 7: Edge cases and error handling"""
    print_test_header("Edge Cases")

    try:
        # Test 7a: Very long query
        long_query = "climate " * 100
        response = requests.get(f"{API_URL}/search/", params={"q": long_query})

        if response.status_code == 422:
            print_result(True, "Long query rejected correctly")
        else:
            print_result(False, f"Long query should return 422, got {response.status_code}")

        # Test 7b: Special characters
        response = requests.get(f"{API_URL}/search/", params={"q": "climate & energy | renewable"})

        if response.status_code == 200:
            print_result(True, "Special characters handled correctly")
        else:
            print_result(False, f"Special chars failed: {response.status_code}")

        # Test 7c: Invalid country code
        response = requests.get(f"{API_URL}/search/", params={
            "q": "climate",
            "country": "INVALID"
        })

        # Should either work (no results) or return 422
        if response.status_code in [200, 422]:
            print_result(True, f"Invalid country handled (status {response.status_code})")
        else:
            print_result(False, f"Unexpected status for invalid country: {response.status_code}")

    except Exception as e:
        print_result(False, f"Edge cases test crashed: {str(e)}")


def run_all_tests():
    """Run all search endpoint tests"""
    print("\n" + "=" * 70)
    print("SEARCH ENDPOINTS TEST SUITE")
    print("=" * 70)
    print(f"API Base URL: {API_BASE_URL}")

    # Check if API is running
    try:
        health = requests.get(f"{API_BASE_URL}/health")
        if health.status_code == 200:
            print("✅ API is running and healthy")
        else:
            print("⚠️  API health check returned non-200 status")
    except Exception as e:
        print(f"❌ Cannot connect to API at {API_BASE_URL}")
        print(f"   Error: {str(e)}")
        return

    # Run all tests
    test_basic_search()
    test_search_suggestions()
    test_semantic_search_without_auth()
    # test_semantic_search_with_freemium()  # Disabled - requires user creation
    test_search_performance()
    test_search_ranking()
    test_search_edge_cases()

    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETED")
    print("=" * 70)
    print("\nNote: Semantic search with auth tests disabled (requires user management)")


if __name__ == "__main__":
    run_all_tests()
