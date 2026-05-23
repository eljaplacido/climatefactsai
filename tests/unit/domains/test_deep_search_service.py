from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.domains.intelligence.deep_search_service import DeepSearchService


class _FakeDB:
    def execute_query(self, query, params=None):
        return []


@pytest.mark.asyncio
async def test_compare_degrades_when_side_times_out(monkeypatch):
    service = DeepSearchService(_FakeDB())

    async def _slow_search(*args, **kwargs):
        await asyncio.sleep(0.2)
        return {
            "query": "unused",
            "answer": "unused",
            "citations": [],
            "internal_articles_count": 1,
            "external_sources_count": 0,
            "weather_context": None,
            "filters": {},
            "searched_at": datetime.utcnow().isoformat(),
        }

    service.search = AsyncMock(side_effect=_slow_search)
    service._generate_comparison = AsyncMock(return_value="comparison")
    service._generate_comparison_structured = AsyncMock(return_value=None)

    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SIDE_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SYNTHESIS_TIMEOUT_SECONDS", "2")

    result = await service.compare("topic a", "topic b", country="FI")

    assert result["query_a"] == "topic a"
    assert result["query_b"] == "topic b"
    assert result["result_a"]["query"] == "topic a"
    assert result["result_b"]["query"] == "topic b"
    assert result["result_a"]["internal_articles_count"] == 0
    assert result["result_b"]["internal_articles_count"] == 0
    assert result["comparative_analysis"] == "comparison"


@pytest.mark.asyncio
async def test_compare_degrades_when_comparison_generation_times_out(monkeypatch):
    service = DeepSearchService(_FakeDB())

    side_payload = {
        "query": "topic",
        "answer": "side answer",
        "citations": [],
        "internal_articles_count": 2,
        "external_sources_count": 1,
        "weather_context": None,
        "filters": {"country": "FI"},
        "searched_at": datetime.utcnow().isoformat(),
    }
    service.search = AsyncMock(return_value=side_payload)

    async def _slow_compare(*args, **kwargs):
        await asyncio.sleep(0.2)
        return "late-comparison"

    service._generate_comparison = AsyncMock(side_effect=_slow_compare)
    service._generate_comparison_structured = AsyncMock(return_value={
        "summary": "ok",
        "similarities": ["a"],
        "differences": ["b"],
        "evidence_strength": "balanced",
        "common_gaps": [],
    })

    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SIDE_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SYNTHESIS_TIMEOUT_SECONDS", "0.01")

    result = await service.compare("topic a", "topic b", country="FI")

    assert "could not be generated" in result["comparative_analysis"].lower()
    assert result["comparative_analysis_structured"]["summary"] == "ok"
    assert result["result_a"]["internal_articles_count"] == 2
    assert result["result_b"]["internal_articles_count"] == 2
