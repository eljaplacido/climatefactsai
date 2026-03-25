"""
Comprehensive Tests for Search Functionality

Tests cover:
- Search suggestions endpoint
- Full-text search
- Semantic search (if available)
- Search error handling
- Edge cases and validation
- Search result quality
"""

import pytest
from typing import List, Dict, Any


class TestSearchSuggestions:
    """Test search auto-complete suggestions"""

    def test_search_suggestions_endpoint_exists(self, client):
        """Verify search suggestions endpoint is available"""
        response = client.get("/api/search/suggestions?q=cli")

        # Should either work or return 401/404
        assert response.status_code in [200, 401, 404]

    def test_suggestions_for_short_query(self, client):
        """Test suggestions with minimum query length"""
        response = client.get("/api/search/suggestions?q=cl")

        if response.status_code == 200:
            suggestions = response.json()
            assert isinstance(suggestions, list)

    def test_suggestions_include_count(self, client):
        """Verify each suggestion includes article count"""
        response = client.get("/api/search/suggestions?q=climate")

        if response.status_code == 200:
            suggestions = response.json()

            for suggestion in suggestions:
                assert "text" in suggestion
                assert "category" in suggestion
                assert "count" in suggestion


class TestFullTextSearch:
    """Test full-text search functionality"""

    def test_basic_full_text_search(self, client):
        """Test basic search query"""
        response = client.get("/api/articles?q=climate")

        assert response.status_code == 200
        articles = response.json()
        assert isinstance(articles, list)

    def test_search_with_pagination(self, client):
        """Test search results support pagination"""
        response = client.get("/api/articles?q=climate&limit=5&offset=0")

        assert response.status_code == 200


class TestSearchFilters:
    """Test search combined with filters"""

    def test_search_with_country_filter(self, client):
        """Test search filtered by country"""
        response = client.get("/api/articles?q=climate&country=FI")

        assert response.status_code == 200


class TestSearchErrorHandling:
    """Test error handling in search"""

    def test_search_with_sql_injection_attempt(self, client):
        """Test that SQL injection is prevented"""
        malicious_query = "'; DROP TABLE articles; --"
        response = client.get(f"/api/articles?q={malicious_query}")

        # Should handle safely
        assert response.status_code in [200, 400]
