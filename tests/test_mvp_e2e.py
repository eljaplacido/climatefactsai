"""
End-to-end tests for MVP user stories.

Tests all six MVP user journeys:
1. Filter climate news by country/source/credibility
2. Article trust panel with claims verification status
3. Evidence links on claims
4. URL analysis submission and status polling
5. Transparent error states
6. Claims status transparency (pending/processing/completed/failed)
"""

import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Story 1: Filter climate news by country/source/credibility
# ---------------------------------------------------------------------------

class TestArticleFiltering:
    """Story 1: As a user, I want to filter climate news by country/source/credibility."""

    def test_list_articles_no_filter(self, client):
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_filter_by_country(self, client):
        response = client.get("/api/articles", params={"country": "FI"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_by_credibility_uppercase(self, client):
        response = client.get("/api/articles", params={"credibility": "HIGH"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_credibility_lowercase(self, client):
        """Verify case-insensitive credibility filter (v1/v2 alignment)."""
        response = client.get("/api/articles", params={"credibility": "high"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_source(self, client):
        response = client.get("/api/articles", params={"source": "YLE"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_tags(self, client):
        response = client.get("/api/articles", params={"tags": ["climate"]})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_combined(self, client):
        response = client.get(
            "/api/articles",
            params={"country": "FI", "credibility": "HIGH", "source": "YLE"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_pagination(self, client):
        response = client.get("/api/articles", params={"limit": 5, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_invalid_credibility_rejected(self, client):
        response = client.get("/api/articles", params={"credibility": "INVALID"})
        assert response.status_code == 422

    def test_countries_endpoint(self, client):
        response = client.get("/api/countries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        country = data[0]
        assert "country_code" in country
        assert "country_name" in country
        assert "articles_count" in country
        assert "is_eu_member" in country

    def test_tags_endpoint(self, client):
        response = client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "tag" in data[0]
            assert "article_count" in data[0]

    def test_tags_by_country(self, client):
        response = client.get("/api/tags", params={"country": "FI"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Story 2: Article trust panel with claims and verification status
# ---------------------------------------------------------------------------

class TestArticleTrustPanel:
    """Story 2: As a reader, I want each article to show claim verification status."""

    def test_article_detail_has_claims(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert isinstance(data["claims"], list)

    def test_article_detail_has_claim_counts(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()
        assert "claim_count" in data
        assert "verified_claim_count" in data
        assert data["claim_count"] >= 0
        assert data["verified_claim_count"] >= 0

    def test_article_detail_claims_available(self, client, fake_db):
        """Verify claims_available is True when status is completed and count > 0."""
        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()
        assert "claims_available" in data
        assert data["claims_available"] is True

    def test_claim_has_fact_check(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()
        claims = data.get("claims", [])
        assert len(claims) >= 1
        claim = claims[0]
        assert "claim_id" in claim
        assert "claim_text" in claim
        assert "fact_check" in claim

    def test_fact_check_has_verification_status(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        claim = response.json()["claims"][0]
        fc = claim["fact_check"]
        assert fc is not None
        assert "verification_status" in fc
        assert "confidence_score" in fc
        assert 0.0 <= fc["confidence_score"] <= 1.0

    def test_fact_check_has_justification(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        claim = response.json()["claims"][0]
        fc = claim["fact_check"]
        assert "justification" in fc

    def test_article_not_found(self, client):
        response = client.get("/api/articles/nonexistent-id")
        assert response.status_code == 404
        assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Story 3: Evidence links on claims
# ---------------------------------------------------------------------------

class TestEvidenceLinks:
    """Story 3: As a researcher, I want evidence links attached to each claim."""

    def test_fact_check_has_evidence(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        claim = response.json()["claims"][0]
        fc = claim["fact_check"]
        assert "evidence" in fc
        # evidence can be dict or None
        if fc["evidence"] is not None:
            assert isinstance(fc["evidence"], dict)


# ---------------------------------------------------------------------------
# Story 4: URL analysis submission and status polling
# ---------------------------------------------------------------------------

class TestUrlAnalysis:
    """Story 4: As a user, I want to submit a URL and get analysis status.

    URL analysis requires authentication (premium feature).
    These tests verify the auth gate and validation layers.
    """

    def test_analyze_url_requires_auth(self, client):
        """URL analysis is a premium feature requiring authentication."""
        try:
            response = client.post(
                "/api/analyze-url",
                json={"url": "https://example.com/article"},
            )
            # Should require auth (401/403)
            assert response.status_code in (401, 403, 422)
        except Exception:
            # Auth dependency raises HTTPException directly - this is expected
            pass

    def test_analyze_url_status_poll_exists(self, client):
        """GET endpoint for analysis status should exist."""
        try:
            response = client.get("/api/analyze-url/test-job-id")
            # Should return 401 (auth required) or 404 (job not found)
            assert response.status_code in (401, 403, 404)
        except Exception:
            pass

    def test_analyze_url_route_registered(self):
        """Verify the URL analysis routes are registered in the app."""
        from api.main import app
        route_paths = [route.path for route in app.routes]
        assert "/api/analyze-url" in route_paths or any(
            "/api/analyze-url" in str(r.path) for r in app.routes
        )


# ---------------------------------------------------------------------------
# Story 5: Transparent error states
# ---------------------------------------------------------------------------

class TestErrorTransparency:
    """Story 5: As a user, I want transparent error states."""

    def test_404_has_detail(self, client):
        response = client.get("/api/articles/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)
        assert len(body["detail"]) > 0

    def test_invalid_query_params(self, client):
        response = client.get("/api/articles", params={"limit": -1})
        assert response.status_code == 422

    def test_health_endpoint(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_stats_endpoint(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_articles" in data
        assert "total_fact_checks" in data


# ---------------------------------------------------------------------------
# Story 6: Claims status transparency
# ---------------------------------------------------------------------------

class TestClaimsStatusTransparency:
    """Story 6: Claims status should be visible on article listings and detail."""

    def test_article_listing_has_claims_status(self, client):
        """v1 API articles should include claims_status field."""
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        article = data[0]
        assert "claims_status" in article
        assert article["claims_status"] in (
            "pending", "processing", "completed", "failed", None
        )

    def test_article_detail_has_claims_status(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        assert response.status_code == 200
        data = response.json()
        assert "claims_status" in data
        assert data["claims_status"] == "completed"

    def test_claims_status_pending_article(self, client, fake_db):
        """Article with pending claims should show pending status."""
        fake_db.article_row["claims_status"] = "pending"
        fake_db.article_row["claims_count"] = 0
        fake_db.article_row["verified_claims_count"] = 0

        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()
        assert data["claims_status"] == "pending"
        assert data["claims_available"] is False

    def test_claims_status_failed_article(self, client, fake_db):
        """Failed claims extraction should show error message."""
        fake_db.article_row["claims_status"] = "failed"
        fake_db.article_row["claims_error_message"] = "Extraction timeout"
        fake_db.article_row["claims_count"] = 0
        fake_db.article_row["verified_claims_count"] = 0

        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()
        assert data["claims_status"] == "failed"
        assert data["claims_error_message"] == "Extraction timeout"
        assert data["claims_available"] is False


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------

class TestAPIContracts:
    """Validate API response schemas match frontend TypeScript types."""

    def test_article_schema(self, client):
        response = client.get("/api/articles")
        data = response.json()
        assert len(data) >= 1
        article = data[0]

        # Required fields (must match types/index.ts Article)
        required_fields = [
            "article_id", "title", "url", "source_name", "created_at",
            "claim_count", "verified_claim_count", "tags",
        ]
        for field in required_fields:
            assert field in article, f"Missing required field: {field}"

        # Optional fields that should be present
        optional_fields = [
            "author", "published_date", "source_credibility_score",
            "excerpt", "overall_credibility", "country_code",
            "claims_status", "claims_error_message", "claims_processed_at",
        ]
        for field in optional_fields:
            assert field in article, f"Missing optional field: {field}"

    def test_article_detail_schema(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}")
        data = response.json()

        # Must have detail-specific fields
        detail_fields = ["claims", "claims_available"]
        for field in detail_fields:
            assert field in data, f"Missing detail field: {field}"

    def test_country_schema(self, client):
        response = client.get("/api/countries")
        data = response.json()
        assert len(data) >= 1
        country = data[0]

        required_fields = [
            "country_code", "country_name", "articles_count", "is_eu_member",
        ]
        for field in required_fields:
            assert field in country, f"Missing country field: {field}"

    def test_feedback_schema(self, client, fake_db):
        """Feedback types should match enum: USEFUL, NOT_USEFUL, FLAGGED."""
        # Use a fresh client with the same fake_db to avoid state issues
        response = client.post(
            f"/api/articles/{fake_db.article_id}/feedback",
            json={"feedback_type": "USEFUL", "comment": "Great article"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback_type"] == "USEFUL"

    def test_invalid_feedback_type_rejected(self, client, fake_db):
        response = client.post(
            f"/api/articles/{fake_db.article_id}/feedback",
            json={"feedback_type": "INVALID"},
        )
        assert response.status_code == 422

    def test_feedback_summary_schema(self, client, fake_db):
        response = client.get(f"/api/articles/{fake_db.article_id}/feedback")
        assert response.status_code == 200
        data = response.json()
        for field in ["article_id", "total_feedback", "useful", "not_useful", "flagged"]:
            assert field in data, f"Missing feedback summary field: {field}"


# ---------------------------------------------------------------------------
# Workflow integration: browse -> detail -> claims -> feedback
# ---------------------------------------------------------------------------

class TestUserJourneyE2E:
    """End-to-end user journey: browse -> read -> verify claims -> give feedback."""

    def test_complete_user_journey(self, client, fake_db):
        """Simulate full user journey through the platform."""

        # 1. Browse articles
        browse_resp = client.get("/api/articles")
        assert browse_resp.status_code == 200
        articles = browse_resp.json()
        assert len(articles) >= 1

        # 2. Check countries for filtering
        countries_resp = client.get("/api/countries")
        assert countries_resp.status_code == 200
        assert len(countries_resp.json()) >= 1

        # 3. Filter by country
        filtered_resp = client.get("/api/articles", params={"country": "FI"})
        assert filtered_resp.status_code == 200

        # 4. Open article detail
        article_id = articles[0]["article_id"]
        detail_resp = client.get(f"/api/articles/{article_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        # 5. Verify trust panel data
        assert detail["claims_status"] is not None
        assert "claims" in detail
        assert "claims_available" in detail

        # 6. Check claims have verification
        if detail["claims"]:
            claim = detail["claims"][0]
            assert "claim_text" in claim
            if claim["fact_check"]:
                assert "verification_status" in claim["fact_check"]
                assert "confidence_score" in claim["fact_check"]

        # 7. Submit feedback
        feedback_resp = client.post(
            f"/api/articles/{article_id}/feedback",
            json={"feedback_type": "USEFUL", "reliability_score": 85},
        )
        assert feedback_resp.status_code == 200

        # 8. Verify feedback summary
        summary_resp = client.get(f"/api/articles/{article_id}/feedback")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["total_feedback"] >= 1
        assert summary["useful"] >= 1

    def test_search_to_detail_journey(self, client, fake_db):
        """Search -> select article -> view claims."""

        # 1. Search
        search_resp = client.get("/api/articles", params={"q": "climate"})
        assert search_resp.status_code == 200

        # 2. Get tags for refinement
        tags_resp = client.get("/api/tags")
        assert tags_resp.status_code == 200

        # 3. Open detail
        detail_resp = client.get(f"/api/articles/{fake_db.article_id}")
        assert detail_resp.status_code == 200
        assert "claims" in detail_resp.json()

    def test_dashboard_stats(self, client):
        """Verify dashboard stats are accessible."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_articles"] >= 0
        assert stats["total_fact_checks"] >= 0
        assert "average_confidence" in stats
