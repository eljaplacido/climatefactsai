"""
API Article Routes - Test Suite

Tests article listing, filtering, detail view, and feedback operations.
"""

import pytest
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
except Exception:
    pytest.skip(
        "API module could not be imported (missing DB or dependencies)",
        allow_module_level=True,
    )


class TestArticleListing:
    """Test article listing endpoint"""
    
    def test_list_articles_basic(self):
        """Should list articles with default parameters"""
        response = client.get("/api/articles")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Default limit is 20
        assert len(data) <= 20
    
    def test_list_articles_with_limit(self):
        """Should respect limit parameter"""
        response = client.get("/api/articles?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5
    
    def test_list_articles_with_offset(self):
        """Should support pagination with offset"""
        # Get first page
        response1 = client.get("/api/articles?limit=5&offset=0")
        page1 = response1.json()
        
        # Get second page
        response2 = client.get("/api/articles?limit=5&offset=5")
        page2 = response2.json()
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Pages should be different (assuming > 5 articles)
        if len(page1) == 5 and len(page2) > 0:
            assert page1[0]["article_id"] != page2[0]["article_id"]
    
    def test_list_articles_limit_bounds(self):
        """Should enforce limit boundaries (1-100)"""
        # Limit too low
        response = client.get("/api/articles?limit=0")
        assert response.status_code == 422
        
        # Limit too high
        response = client.get("/api/articles?limit=101")
        assert response.status_code == 422
        
        # Valid limits
        response = client.get("/api/articles?limit=1")
        assert response.status_code == 200
        
        response = client.get("/api/articles?limit=100")
        assert response.status_code == 200


class TestArticleFiltering:
    """Test article filtering parameters"""
    
    def test_filter_by_country(self):
        """Should filter articles by country code"""
        response = client.get("/api/articles?country=FI")
        
        assert response.status_code == 200
        data = response.json()
        
        # All articles should be from Finland
        for article in data:
            assert article.get("country_code") == "FI"
    
    def test_filter_by_credibility(self):
        """Should filter articles by credibility level"""
        response = client.get("/api/articles?credibility=HIGH")
        
        assert response.status_code == 200
        data = response.json()
        
        # All articles should have HIGH credibility
        for article in data:
            assert article.get("overall_credibility") == "HIGH"
    
    def test_filter_by_source(self):
        """Should filter articles by source name"""
        response = client.get("/api/articles?source=YLE")
        
        assert response.status_code == 200
        data = response.json()
        
        # All articles should be from YLE
        for article in data:
            assert article.get("source_name") == "YLE"
    
    def test_filter_by_date_range(self):
        """Should filter articles by date range"""
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        response = client.get(
            f"/api/articles?date_from={week_ago}&date_to={today}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All articles should be within date range
        for article in data:
            pub_date = datetime.fromisoformat(
                article.get("published_date", article["created_at"])
            ).date()
            assert week_ago <= pub_date <= today
    
    def test_filter_by_tags(self):
        """Should filter articles by tags"""
        response = client.get("/api/articles?tags=climate&tags=policy")
        
        assert response.status_code == 200
        data = response.json()
        
        # Articles should have at least one of the specified tags
        for article in data:
            tags = article.get("tags", [])
            assert "climate" in tags or "policy" in tags
    
    def test_multiple_filters_combined(self):
        """Should support multiple filters simultaneously"""
        response = client.get(
            "/api/articles?country=FI&credibility=HIGH&limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All articles should match all filters
        for article in data:
            assert article.get("country_code") == "FI"
            assert article.get("overall_credibility") == "HIGH"
        
        assert len(data) <= 10


class TestArticleDetail:
    """Test article detail endpoint"""
    
    def test_get_article_detail(self):
        """Should retrieve article with full details"""
        # First, get an article ID from listing
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available for testing")
        
        article_id = articles[0]["article_id"]
        
        # Get article detail
        response = client.get(f"/api/articles/{article_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check article structure
        assert data["article_id"] == article_id
        assert "title" in data
        assert "url" in data
        assert "source_name" in data
        assert "full_text" in data
        assert "claims" in data
        assert isinstance(data["claims"], list)
    
    def test_get_article_with_claims(self):
        """Should include claims and fact-checks"""
        # Get article detail
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        response = client.get(f"/api/articles/{article_id}")
        data = response.json()
        
        # Check claims structure
        if len(data["claims"]) > 0:
            claim = data["claims"][0]
            assert "claim_id" in claim
            assert "claim_text" in claim
            
            # Check fact-check if exists
            if claim.get("fact_check"):
                fc = claim["fact_check"]
                assert "verification_status" in fc
                assert "confidence_score" in fc
    
    def test_get_nonexistent_article(self):
        """Should return 404 for nonexistent article"""
        response = client.get("/api/articles/nonexistent-id-12345")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_article_response_structure(self):
        """Should return article with correct structure"""
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        response = client.get(f"/api/articles/{article_id}")
        data = response.json()
        
        # Required fields
        required_fields = [
            "article_id", "title", "url", "source_name",
            "created_at", "claims"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestArticleFeedback:
    """Test article feedback operations"""
    
    def test_submit_feedback(self):
        """Should submit feedback for article"""
        # Get an article
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        
        # Submit feedback
        response = client.post(
            f"/api/articles/{article_id}/feedback",
            json={
                "feedback_type": "USEFUL",
                "reliability_score": 85,
                "comment": "Great article, very informative!",
                "submitted_by": "test_user"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "feedback_id" in data
        assert data["article_id"] == article_id
        assert data["feedback_type"] == "USEFUL"
        assert data["reliability_score"] == 85
    
    def test_submit_feedback_without_comment(self):
        """Should allow feedback without comment"""
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        
        response = client.post(
            f"/api/articles/{article_id}/feedback",
            json={
                "feedback_type": "USEFUL"
            }
        )
        
        assert response.status_code == 200
    
    def test_feedback_invalid_type(self):
        """Should reject invalid feedback type"""
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        
        response = client.post(
            f"/api/articles/{article_id}/feedback",
            json={
                "feedback_type": "INVALID_TYPE"
            }
        )
        
        assert response.status_code == 422
    
    def test_get_feedback_summary(self):
        """Should retrieve feedback summary for article"""
        list_response = client.get("/api/articles?limit=1")
        articles = list_response.json()
        
        if len(articles) == 0:
            pytest.skip("No articles available")
        
        article_id = articles[0]["article_id"]
        
        # Get feedback summary
        response = client.get(f"/api/articles/{article_id}/feedback")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "article_id" in data
        assert "total_feedback" in data
        assert "useful" in data
        assert "not_useful" in data
        assert "flagged" in data


class TestCountries:
    """Test countries endpoint"""
    
    def test_list_countries(self):
        """Should list all enabled countries"""
        response = client.get("/api/countries")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0  # Should have at least some countries
        
        # Check country structure
        if len(data) > 0:
            country = data[0]
            assert "country_code" in country
            assert "country_name" in country
            assert "flag_emoji" in country
            assert "articles_count" in country
    
    def test_countries_have_article_counts(self):
        """Countries should include article counts"""
        response = client.get("/api/countries")
        data = response.json()
        
        for country in data:
            assert "articles_count" in country
            assert isinstance(country["articles_count"], int)
            assert country["articles_count"] >= 0


class TestTags:
    """Test tags endpoint"""
    
    def test_list_tags(self):
        """Should list popular tags"""
        response = client.get("/api/tags")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Check tag structure
        if len(data) > 0:
            tag = data[0]
            assert "tag" in tag
            assert "article_count" in tag
            assert isinstance(tag["article_count"], int)
    
    def test_tags_filtered_by_country(self):
        """Should filter tags by country"""
        response = client.get("/api/tags?country=FI")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_tags_sorted_by_frequency(self):
        """Tags should be sorted by article count"""
        response = client.get("/api/tags")
        data = response.json()
        
        if len(data) > 1:
            # Check descending order
            for i in range(len(data) - 1):
                assert data[i]["article_count"] >= data[i + 1]["article_count"]


class TestStats:
    """Test statistics endpoint"""
    
    def test_get_stats(self):
        """Should retrieve dashboard statistics"""
        response = client.get("/api/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check stat fields
        required_fields = [
            "total_articles",
            "articles_today",
            "total_fact_checks",
            "verified_claims",
            "average_confidence"
        ]
        
        for field in required_fields:
            assert field in data
            assert isinstance(data[field], (int, float))
    
    def test_stats_values_reasonable(self):
        """Stats should have reasonable values"""
        response = client.get("/api/stats")
        data = response.json()
        
        # All counts should be non-negative
        assert data["total_articles"] >= 0
        assert data["articles_today"] >= 0
        assert data["total_fact_checks"] >= 0
        assert data["verified_claims"] >= 0
        
        # Confidence should be percentage (0-100)
        assert 0 <= data["average_confidence"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

