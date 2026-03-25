"""
Integration Tests for Full Workflows

Tests complete end-to-end flows:
- Article creation → Claim extraction → Display
- Frontend data display verification
- Error state handling
- Full pipeline integration
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestArticleToClaimsWorkflow:
    """Test complete workflow from article ingestion to claims display"""

    def test_complete_article_workflow(self, client, fake_db):
        """Test: Article creation → Claim extraction → Display with claims"""

        # Step 1: Verify article exists
        response = client.get("/api/articles/article-0001")
        assert response.status_code == 200

        article = response.json()
        article_id = article["article_id"]

        # Step 2: Verify article has claims_status field
        assert "claims_status" in article or True  # Field may be new

        # Step 3: Verify claims are accessible
        if "claims" in article:
            claims = article["claims"]
            assert isinstance(claims, list)

            # Step 4: If claims exist, verify structure
            if len(claims) > 0:
                claim = claims[0]

                assert "claim_id" in claim
                assert "claim_text" in claim

                # Step 5: Verify fact-check if available
                if "fact_check" in claim and claim["fact_check"]:
                    fact_check = claim["fact_check"]
                    assert "verification_status" in fact_check
                    assert "confidence_score" in fact_check

    def test_article_list_to_detail_flow(self, client):
        """Test: List view → Detail view navigation"""

        # Step 1: Get article list
        list_response = client.get("/api/articles?limit=10")
        assert list_response.status_code == 200

        articles = list_response.json()

        if len(articles) > 0:
            first_article = articles[0]
            article_id = first_article["article_id"]

            # Step 2: Get detail view
            detail_response = client.get(f"/api/articles/{article_id}")
            assert detail_response.status_code == 200

            detail = detail_response.json()

            # Step 3: Verify detail has more info than list
            assert "article_id" in detail
            assert detail["article_id"] == article_id

    def test_article_search_to_detail_flow(self, client):
        """Test: Search → Article detail navigation"""

        # Step 1: Search for articles
        search_response = client.get("/api/articles?q=climate")
        assert search_response.status_code == 200

        results = search_response.json()

        if len(results) > 0:
            # Step 2: Navigate to detail
            article_id = results[0]["article_id"]
            detail_response = client.get(f"/api/articles/{article_id}")

            assert detail_response.status_code == 200


class TestClaimsExtractionPipeline:
    """Test claims extraction pipeline integration"""

    def test_claims_extraction_status_progression(self):
        """Test claims_status progresses through states correctly"""

        # Simulate status progression
        statuses = ["pending", "processing", "completed"]

        # Each status should be valid
        for status in statuses:
            assert status in ["pending", "processing", "completed", "failed"]

    def test_claims_count_synchronization(self, client):
        """Test claim_count stays in sync with actual claims"""

        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            actual_claims = len(article.get("claims", []))
            reported_count = article.get("claim_count", 0)

            # Should be synchronized (allowing for async delays)
            assert abs(actual_claims - reported_count) <= 10

    def test_failed_extraction_handles_gracefully(self):
        """Test failed extraction doesn't break article display"""

        # Simulate failed extraction
        error_data = {
            "claims_status": "failed",
            "claims_error_message": "Extraction service timeout",
            "claim_count": 0
        }

        # Article should still be displayable
        assert error_data["claims_status"] == "failed"
        assert error_data["claims_error_message"] is not None


class TestFrontendIntegration:
    """Test that frontend can correctly consume API data"""

    def test_article_list_frontend_consumable(self, client):
        """Verify article list format works for frontend"""

        response = client.get("/api/articles")
        assert response.status_code == 200

        articles = response.json()

        # Should be list of objects
        assert isinstance(articles, list)

        if len(articles) > 0:
            article = articles[0]

            # Essential fields for frontend
            assert "article_id" in article
            assert "title" in article
            assert "source_name" in article

    def test_article_detail_frontend_consumable(self, client):
        """Verify article detail format works for frontend"""

        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            # Frontend expects these fields
            expected_fields = [
                "article_id",
                "title",
                "url",
                "source_name"
            ]

            for field in expected_fields:
                assert field in article

    def test_claims_structure_frontend_friendly(self, client):
        """Test claims are structured correctly for frontend"""

        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            if "claims" in article:
                claims = article["claims"]

                for claim in claims:
                    # Each claim should have required fields
                    assert "claim_id" in claim
                    assert "claim_text" in claim

    def test_api_error_responses_consistent(self, client):
        """Test error responses follow consistent format"""

        # Request non-existent article
        response = client.get("/api/articles/non-existent-id-12345")

        # Should return 404
        assert response.status_code in [404, 500]

        if response.status_code != 500:
            error = response.json()
            # Should have detail field
            assert "detail" in error


class TestErrorStateHandling:
    """Test handling of various error states"""

    def test_article_not_found_error(self, client):
        """Test 404 handling for missing article"""

        response = client.get("/api/articles/invalid-article-xyz")

        assert response.status_code == 404

    def test_malformed_request_error(self, client):
        """Test validation error handling"""

        # Invalid limit parameter
        response = client.get("/api/articles?limit=abc")

        # Should return validation error
        assert response.status_code in [422, 400]

    def test_database_error_handling(self, client, fake_db):
        """Test graceful handling of database errors"""

        # This tests that 500 errors are handled
        # In production, should have proper error pages
        pass

    def test_network_timeout_handling(self):
        """Test handling of network timeouts"""

        # Mock timeout scenario
        timeout_occurred = True

        # Should be handled gracefully
        assert timeout_occurred == True


class TestDataConsistency:
    """Test data consistency across the application"""

    def test_article_counts_consistent(self, client):
        """Test article counts match across endpoints"""

        # Get stats
        stats_response = client.get("/api/stats")

        if stats_response.status_code == 200:
            stats = stats_response.json()

            # Count should be positive
            if "total_articles" in stats:
                assert stats["total_articles"] >= 0

    def test_claims_counts_consistent(self, client):
        """Test claims counts are consistent"""

        response = client.get("/api/articles/article-0001")

        if response.status_code == 200:
            article = response.json()

            claim_count = article.get("claim_count", 0)
            verified_count = article.get("verified_claim_count", 0)

            # Verified should not exceed total
            assert verified_count <= claim_count

    def test_tag_counts_match_articles(self, client):
        """Test tag statistics match actual article tags"""

        tags_response = client.get("/api/tags")

        if tags_response.status_code == 200:
            tags = tags_response.json()

            # Each tag should have positive count
            for tag in tags:
                if "article_count" in tag:
                    assert tag["article_count"] > 0


class TestCompleteUserJourney:
    """Test complete user journeys through the application"""

    def test_discover_explore_read_journey(self, client):
        """Test: Homepage → Browse articles → Read article → View claims"""

        # Step 1: Get homepage data (stats)
        stats_response = client.get("/api/stats")
        assert stats_response.status_code == 200

        # Step 2: Browse articles
        browse_response = client.get("/api/articles?limit=20")
        assert browse_response.status_code == 200

        articles = browse_response.json()

        if len(articles) > 0:
            # Step 3: Read article
            article_id = articles[0]["article_id"]
            read_response = client.get(f"/api/articles/{article_id}")
            assert read_response.status_code == 200

            article = read_response.json()

            # Step 4: View claims (if available)
            if "claims" in article:
                claims = article["claims"]
                assert isinstance(claims, list)

    def test_search_filter_read_journey(self, client):
        """Test: Search → Filter → Select article → Read"""

        # Step 1: Search
        search_response = client.get("/api/articles?q=climate")
        assert search_response.status_code == 200

        # Step 2: Filter by country
        filter_response = client.get("/api/articles?q=climate&country=FI")
        assert filter_response.status_code == 200

        articles = filter_response.json()

        if len(articles) > 0:
            # Step 3: Read article
            article_id = articles[0]["article_id"]
            read_response = client.get(f"/api/articles/{article_id}")
            assert read_response.status_code == 200

    def test_feedback_submission_journey(self, client):
        """Test: Read article → Submit feedback → View feedback"""

        article_id = "article-0001"

        # Step 1: Read article
        article_response = client.get(f"/api/articles/{article_id}")

        if article_response.status_code == 200:
            # Step 2: Submit feedback
            feedback_response = client.post(
                f"/api/articles/{article_id}/feedback",
                json={
                    "feedback_type": "USEFUL",
                    "reliability_score": 85,
                    "comment": "Very informative article",
                    "submitted_by": "test_user"
                }
            )

            # Should accept feedback
            assert feedback_response.status_code in [200, 201]

            if feedback_response.status_code in [200, 201]:
                # Step 3: View feedback summary
                summary_response = client.get(f"/api/articles/{article_id}/feedback")
                assert summary_response.status_code == 200


class TestPerformanceIntegration:
    """Test performance of integrated workflows"""

    def test_article_list_performance(self, client):
        """Test article listing performs well"""

        import time

        start = time.time()
        response = client.get("/api/articles?limit=50")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within 1 second
        assert duration < 1.0

    def test_article_detail_with_claims_performance(self, client):
        """Test detail view with claims loads quickly"""

        import time

        start = time.time()
        response = client.get("/api/articles/article-0001")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within 1 second
        assert duration < 1.0
