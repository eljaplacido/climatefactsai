"""Unit tests for chat_routes._hydrate_view_context and _format_view_context_block.

These tests pin the contract between the chat surface and the rest of the
platform — when the frontend says "the user is looking at this article /
country / URL analysis", the backend must turn that hint into real grounded
state for the LLM prompt, and never fall back to fabricated data.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from api.chat_routes import (
    _format_view_context_block,
    _hydrate_view_context,
)


def _stub_db(rows_by_query):
    """Build a mock DB whose execute_query returns rows based on substring match."""
    db = MagicMock()

    def _route(query, params=None):
        for needle, rows in rows_by_query.items():
            if needle in query:
                return rows
        return []

    db.execute_query.side_effect = _route
    return db


class TestHydrateViewContext:
    def test_empty_view_returns_empty_dict(self):
        assert _hydrate_view_context(MagicMock(), None) == {}
        assert _hydrate_view_context(MagicMock(), {}) == {}
        assert _hydrate_view_context(MagicMock(), "not a dict") == {}

    def test_route_and_label_passthrough(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {
            "route": "/articles/abc/transparency",
            "label": "Some article",
        })
        assert out["route"] == "/articles/abc/transparency"
        assert out["label"] == "Some article"

    def test_route_truncated_to_120_chars(self):
        db = _stub_db({})
        long_route = "/very" * 50
        out = _hydrate_view_context(db, {"route": long_route})
        assert len(out["route"]) <= 120

    def test_article_lookup_populates_article_dict(self):
        now = datetime.utcnow()
        db = _stub_db({
            "FROM articles WHERE article_id": [{
                "article_id": "art-1",
                "title": "Drought in East Africa",
                "source_name": "Reuters",
                "country_code": "KE",
                "overall_credibility": "HIGH",
                "content_category": "climate_impacts",
                "claims_status": "completed",
                "insight_summary": "Severe drought across the Horn of Africa.",
                "body_preview": "The Horn of Africa is in its fifth consecutive failed rainy season.",
            }],
        })
        out = _hydrate_view_context(db, {"article_id": "art-1"})
        assert out["article"]["article_id"] == "art-1"
        assert out["article"]["title"] == "Drought in East Africa"
        assert out["article"]["source_name"] == "Reuters"
        assert out["article"]["credibility"] == "HIGH"
        assert "fifth consecutive failed rainy season" in out["article"]["body_preview"]

    def test_article_id_new_is_ignored(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {"article_id": "new"})
        assert "article" not in out
        # Should not have run any query
        db.execute_query.assert_not_called()

    def test_country_lookup_populates_stats(self):
        db = _stub_db({
            "country_code,\n                          COUNT(*)": [{
                "country_code": "FI",
                "article_count": 42,
                "source_count": 7,
                "high_cred_articles": 19,
                "latest_published": datetime(2026, 4, 1),
            }],
        })
        out = _hydrate_view_context(db, {"country": "fi"})
        assert out["country_code"] == "FI"
        assert out["country_stats"]["country_code"] == "FI"
        assert out["country_stats"]["article_count"] == 42
        assert out["country_stats"]["high_credibility_articles"] == 19

    def test_compare_countries_normalised_and_capped(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {
            "compare_countries": ["fi", "se", "no", "dk", "is", "EXTRA"],
        })
        assert out["compare_countries"] == ["FI", "SE", "NO", "DK"]

    def test_compare_countries_filters_invalid(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {
            "compare_countries": ["fi", "longlong", 123, None, "se"],
        })
        assert out["compare_countries"] == ["FI", "SE"]

    def test_url_analysis_lookup_populates_payload(self):
        db = _stub_db({
            "FROM url_analyses WHERE analysis_id": [{
                "analysis_id": "ua-9",
                "submitted_url": "https://example.com/article",
                "source_name": "Example",
                "source_domain": "example.com",
                "title": "Solar surges in 2026",
                "status": "completed",
                "reliability_score": 72,
                "overall_credibility": "MEDIUM",
                "extracted_claims": [
                    {"claim_text": "Solar capacity grew by 35% YoY", "claim_type": "stat"},
                    {"claim_text": "Battery costs dropped by 18%", "claim_type": "stat"},
                ],
            }],
        })
        out = _hydrate_view_context(db, {"analysis_id": "ua-9"})
        ua = out["url_analysis"]
        assert ua["analysis_id"] == "ua-9"
        assert ua["credibility"] == "MEDIUM"
        assert ua["reliability_score"] == 72
        assert len(ua["claims"]) == 2

    def test_url_analysis_handles_jsonb_string(self):
        db = _stub_db({
            "FROM url_analyses WHERE analysis_id": [{
                "analysis_id": "ua-9",
                "submitted_url": "https://example.com",
                "source_name": "Example",
                "source_domain": "example.com",
                "title": None,
                "status": "completed",
                "reliability_score": 50,
                "overall_credibility": "LOW",
                "extracted_claims": '[{"claim_text": "foo"}]',
            }],
        })
        out = _hydrate_view_context(db, {"analysis_id": "ua-9"})
        assert out["url_analysis"]["claims"][0]["claim_text"] == "foo"

    def test_deep_search_query_truncated(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {
            "deep_search_query": "x" * 500,
        })
        assert len(out["deep_search_query"]) == 300

    def test_deep_search_compare_round_trip(self):
        db = _stub_db({})
        out = _hydrate_view_context(db, {
            "deep_search_compare": {"query_a": "wind north", "query_b": "solar south"},
        })
        assert out["deep_search_compare"]["query_a"] == "wind north"
        assert out["deep_search_compare"]["query_b"] == "solar south"

    def test_lookup_failures_degrade_silently(self):
        db = MagicMock()
        db.execute_query.side_effect = RuntimeError("DB down")
        # Should not raise — chat must keep working without grounding
        out = _hydrate_view_context(db, {
            "article_id": "art-1",
            "country": "FI",
            "analysis_id": "ua-1",
            "source_id": "Reuters",
        })
        assert isinstance(out, dict)
        assert "country_code" in out  # country code is set before the lookup


class TestFormatViewContextBlock:
    def test_empty_view_returns_empty_string(self):
        assert _format_view_context_block({}) == ""

    def test_article_block_includes_credibility_and_excerpt(self):
        block = _format_view_context_block({
            "article": {
                "article_id": "art-1",
                "title": "Sea level rise",
                "source_name": "NOAA",
                "credibility": "HIGH",
                "country_code": "US",
                "body_preview": "Global mean sea level rose 2.1mm/yr.",
                "insight": "Accelerating trend",
            }
        })
        assert "Sea level rise" in block
        assert "credibility=HIGH" in block
        assert "Accelerating trend" in block
        assert "Global mean sea level" in block

    def test_country_stats_rendered(self):
        block = _format_view_context_block({
            "country_stats": {
                "country_code": "FI",
                "article_count": 42,
                "source_count": 7,
                "high_credibility_articles": 19,
            }
        })
        assert "FI" in block
        assert "42 articles" in block
        assert "19 HIGH-credibility" in block

    def test_url_analysis_block_includes_claims(self):
        block = _format_view_context_block({
            "url_analysis": {
                "analysis_id": "ua-1",
                "submitted_url": "https://example.com/x",
                "source_domain": "example.com",
                "title": "X article",
                "credibility": "MEDIUM",
                "reliability_score": 60,
                "status": "completed",
                "claims": [
                    {"claim_text": "Solar grew 35%"},
                    {"claim_text": "Wind grew 12%"},
                ],
            }
        })
        assert "URL analysis open" in block
        assert "credibility=MEDIUM" in block
        assert "Solar grew 35%" in block

    def test_compare_countries_listed(self):
        block = _format_view_context_block({
            "compare_countries": ["FI", "SE"],
        })
        assert "Comparing countries: FI, SE" in block

    def test_deep_search_compare_rendered(self):
        block = _format_view_context_block({
            "deep_search_compare": {"query_a": "wind", "query_b": "solar"},
        })
        assert "wind" in block
        assert "solar" in block

    def test_label_only_when_no_other_fields(self):
        # When no other fields, label is the only thing rendered
        block = _format_view_context_block({"label": "Some context"})
        assert "Some context" in block
        # When there are other fields, label is not rendered redundantly
        block_with_data = _format_view_context_block({
            "label": "Some context",
            "country_stats": {
                "country_code": "FI",
                "article_count": 1,
                "source_count": 1,
                "high_credibility_articles": 0,
            },
        })
        assert "Country focus" in block_with_data
