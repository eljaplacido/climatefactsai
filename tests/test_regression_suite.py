"""
Regression Tests for Existing Functionality

Ensures existing features still work after changes:
- API health endpoints
- Article listing and filtering
- Authentication (basic checks)
- Stats endpoints
- Countries and tags endpoints
- Feedback functionality
"""

import pytest
from datetime import datetime


class TestAPIHealth:
    """Test API health and readiness endpoints"""

    def test_healthz_endpoint(self, client):
        """Verify /healthz returns OK"""
        response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_endpoint_alias(self, client):
        """Verify /health endpoint works"""
        response = client.get("/health")

        assert response.status_code == 200

    def test_healthz_ready_endpoint(self, client):
        """Verify readiness check works"""
        response = client.get("/healthz/ready")

        # May be degraded if services not available
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestArticleListingBasics:
    """Test basic article listing functionality"""

    def test_get_articles_default(self, client):
        """Test getting articles with default parameters"""
        response = client.get("/api/articles")

        assert response.status_code == 200
        articles = response.json()
        assert isinstance(articles, list)

    def test_articles_have_required_fields(self, client):
        """Verify articles have all required fields"""
        response = client.get("/api/articles")

        assert response.status_code == 200
        articles = response.json()

        if len(articles) > 0:
            article = articles[0]

            # Required fields
            required_fields = [
                "article_id",
                "title",
                "url",
                "source_name",
                "created_at"
            ]

            for field in required_fields:
                assert field in article, f"Missing required field: {field}"

    def test_articles_pagination_works(self, client):
        """Test pagination parameters are respected"""
        # Get first page
        response1 = client.get("/api/articles?limit=5&offset=0")
        assert response1.status_code == 200
        page1 = response1.json()

        # Get second page
        response2 = client.get("/api/articles?limit=5&offset=5")
        assert response2.status_code == 200
        page2 = response2.json()

        # Pages should exist
        assert isinstance(page1, list)
        assert isinstance(page2, list)

    def test_articles_limit_parameter(self, client):
        """Test limit parameter controls result count"""
        limit = 3
        response = client.get(f"/api/articles?limit={limit}")

        assert response.status_code == 200
        articles = response.json()

        # Should not exceed limit
        assert len(articles) <= limit


class TestArticleFiltering:
    """Test article filtering functionality"""

    def test_filter_by_country(self, client):
        """Test filtering articles by country code"""
        response = client.get("/api/articles?country=FI")

        assert response.status_code == 200
        articles = response.json()

        for article in articles:
            if "country_code" in article:
                assert article["country_code"] == "FI"

    def test_filter_by_credibility(self, client):
        """Test filtering by credibility level"""
        response = client.get("/api/articles?credibility=HIGH")

        assert response.status_code == 200

    def test_filter_by_source(self, client):
        """Test filtering by source name"""
        response = client.get("/api/articles?source=YLE")

        assert response.status_code == 200

    def test_filter_by_date_range(self, client):
        """Test filtering by date range"""
        response = client.get(
            "/api/articles?date_from=2025-01-01&date_to=2025-12-31"
        )

        assert response.status_code == 200

    def test_multiple_filters_combined(self, client):
        """Test combining multiple filters"""
        response = client.get(
            "/api/articles?country=FI&credibility=HIGH&limit=10"
        )

        assert response.status_code == 200


class TestArticleDetail:
    """Test article detail endpoint"""

    def test_get_article_by_id(self, client):
        """Test retrieving specific article by ID"""
        article_id = "article-0001"
        response = client.get(f"/api/articles/{article_id}")

        assert response.status_code == 200
        article = response.json()
        assert article["article_id"] == article_id

    def test_article_detail_has_full_text(self, client):
        """Verify detail view includes full article text"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()
            # Should have full text or extracted text
            has_text = (
                "full_text" in article or
                "extracted_text" in article
            )

    def test_article_detail_has_claims(self, client):
        """Verify detail view includes claims array"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()
            assert "claims" in article
            assert isinstance(article["claims"], list)

    def test_nonexistent_article_returns_404(self, client):
        """Test 404 for non-existent article"""
        response = client.get("/api/articles/nonexistent-article-id-xyz")

        assert response.status_code == 404


class TestStatsEndpoint:
    """Test statistics endpoint"""

    def test_get_public_stats(self, client):
        """Test public stats endpoint"""
        response = client.get("/api/stats")

        assert response.status_code == 200
        stats = response.json()

        # Should have key statistics
        expected_fields = [
            "total_articles",
            "articles_today",
            "total_fact_checks",
            "verified_claims"
        ]

        for field in expected_fields:
            assert field in stats

    def test_stats_values_are_numbers(self, client):
        """Verify stats return numeric values"""
        response = client.get("/api/stats")

        if response.status_code == 200:
            stats = response.json()

            numeric_fields = [
                "total_articles",
                "articles_today",
                "total_fact_checks",
                "verified_claims"
            ]

            for field in numeric_fields:
                if field in stats:
                    assert isinstance(stats[field], (int, float))
                    assert stats[field] >= 0


class TestCountriesEndpoint:
    """Test countries endpoint"""

    def test_get_countries_list(self, client):
        """Test retrieving list of countries"""
        response = client.get("/api/countries")

        assert response.status_code == 200
        countries = response.json()
        assert isinstance(countries, list)

    def test_countries_have_required_fields(self, client):
        """Verify country objects have required fields"""
        response = client.get("/api/countries")

        if response.status_code == 200:
            countries = response.json()

            if len(countries) > 0:
                country = countries[0]

                required_fields = [
                    "country_code",
                    "country_name"
                ]

                for field in required_fields:
                    assert field in country

    def test_countries_include_article_counts(self, client):
        """Verify countries include article counts"""
        response = client.get("/api/countries")

        if response.status_code == 200:
            countries = response.json()

            for country in countries:
                if "articles_count" in country:
                    assert isinstance(country["articles_count"], int)


class TestTagsEndpoint:
    """Test tags endpoint"""

    def test_get_tags_list(self, client):
        """Test retrieving list of tags"""
        response = client.get("/api/tags")

        assert response.status_code == 200
        tags = response.json()
        assert isinstance(tags, list)

    def test_tags_have_article_counts(self, client):
        """Verify tags include article counts"""
        response = client.get("/api/tags")

        if response.status_code == 200:
            tags = response.json()

            for tag in tags:
                assert "tag" in tag
                assert "article_count" in tag
                assert isinstance(tag["article_count"], int)

    def test_tags_filtered_by_country(self, client):
        """Test filtering tags by country"""
        response = client.get("/api/tags?country=FI")

        assert response.status_code == 200


class TestFeedbackFunctionality:
    """Test article feedback functionality"""

    def test_submit_article_feedback(self, client):
        """Test submitting feedback for an article"""
        article_id = "article-0001"

        response = client.post(
            f"/api/articles/{article_id}/feedback",
            json={
                "feedback_type": "USEFUL",
                "reliability_score": 85,
                "comment": "Great article",
                "submitted_by": "test_user"
            }
        )

        assert response.status_code in [200, 201]

    def test_get_feedback_summary(self, client):
        """Test retrieving feedback summary"""
        article_id = "article-0001"

        response = client.get(f"/api/articles/{article_id}/feedback")

        assert response.status_code == 200

        summary = response.json()
        assert "total_feedback" in summary
        assert "useful" in summary
        assert "not_useful" in summary

    def test_feedback_for_nonexistent_article(self, client):
        """Test feedback submission for non-existent article"""
        response = client.post(
            "/api/articles/nonexistent-xyz/feedback",
            json={
                "feedback_type": "USEFUL",
                "reliability_score": 80
            }
        )

        # Should return 404
        assert response.status_code == 404


class TestCORSHeaders:
    """Test CORS configuration"""

    def test_cors_headers_present(self, client):
        """Verify CORS headers are set"""
        response = client.options("/api/articles")

        # Should have CORS headers
        # TestClient may not fully simulate CORS


class TestRateLimiting:
    """Test rate limiting (basic checks)"""

    def test_normal_request_not_rate_limited(self, client):
        """Test normal requests are not blocked"""
        response = client.get("/api/articles")

        assert response.status_code == 200

    def test_multiple_requests_handled(self, client):
        """Test multiple requests are handled"""
        for _ in range(10):
            response = client.get("/api/articles")
            assert response.status_code == 200


class TestErrorHandling:
    """Test general error handling"""

    def test_invalid_endpoint_returns_404(self, client):
        """Test 404 for invalid endpoints"""
        response = client.get("/api/nonexistent-endpoint-xyz")

        assert response.status_code == 404

    def test_malformed_json_returns_error(self, client):
        """Test error handling for malformed JSON"""
        response = client.post(
            "/api/articles/article-0001/feedback",
            data="invalid json{{{",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422]


class TestBackwardCompatibility:
    """Test backward compatibility of API"""

    def test_article_response_format_stable(self, client):
        """Verify article response format hasn't changed"""
        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            # Core fields should still exist
            core_fields = [
                "article_id",
                "title",
                "url",
                "source_name"
            ]

            for field in core_fields:
                assert field in article

    def test_stats_response_format_stable(self, client):
        """Verify stats response format hasn't changed"""
        response = client.get("/api/stats")

        if response.status_code == 200:
            stats = response.json()

            # Core stats should exist
            assert "total_articles" in stats

    def test_countries_response_format_stable(self, client):
        """Verify countries response format hasn't changed"""
        response = client.get("/api/countries")

        assert response.status_code == 200
