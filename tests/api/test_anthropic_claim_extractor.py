"""AnthropicClaimExtractor tests (Phase 5 wave 2).

Pins:
- Returns [] when no key / no client (no exception)
- Returns [] when text is too short
- Parses well-formed JSON output
- Tolerates ```json``` fence wrappers
- Tolerates prose preambles before the JSON array
- Returns [] on malformed JSON, no exception
- Skips claim_dicts missing claim_text
- Clamps importance_score to [0, 1]
- Falls back to ClaimClassifier on unknown claim_category
- Uses the version-pinned `claim_extraction` prompt
- model name and extraction_model field are populated
"""

from __future__ import annotations

import json
import os
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from app.domains.intelligence.anthropic_claim_extractor import (
    AnthropicClaimExtractor,
)
from app.domains.intelligence.schemas import ClaimCategory


# ---------------------------------------------------------------------------
# Helpers — fake Anthropic SDK client
# ---------------------------------------------------------------------------

class _FakeBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [_FakeBlock(text)]


class _FakeAnthropic:
    """Mimics the small slice of anthropic.Anthropic we use."""
    def __init__(self, response_text: str, *, raise_exc: Exception = None):
        self._response_text = response_text
        self._raise_exc = raise_exc
        self.last_call = None

    @property
    def messages(self):
        return self

    def create(self, *, model: str, max_tokens: int, temperature: float, messages):
        self.last_call = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if self._raise_exc:
            raise self._raise_exc
        return _FakeMessage(self._response_text)


# Sample well-formed JSON output the model might return.
_GOOD_JSON = json.dumps([
    {
        "claim_text": "Global average temperature rose 1.2°C above pre-industrial in 2022",
        "claim_type": "factual",
        "claim_category": "statistical",
        "importance_score": 0.9,
        "claim_context": "WMO report.",
    },
    {
        "claim_text": "EU adopted Fit-for-55 package",
        "claim_type": "factual",
        "claim_category": "policy",
        "importance_score": 0.7,
        "claim_context": "EU summit summary.",
    },
])


# ---------------------------------------------------------------------------
# Availability / short-text guards
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_no_key_no_injected_client_returns_unavailable(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        extractor = AnthropicClaimExtractor()
        assert extractor.available is False

    def test_injected_client_makes_available(self):
        extractor = AnthropicClaimExtractor(
            client=_FakeAnthropic(_GOOD_JSON),
        )
        assert extractor.available is True

    @pytest.mark.asyncio
    async def test_unavailable_returns_empty_list_no_exception(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        extractor = AnthropicClaimExtractor()
        assert await extractor.decompose_claims("x" * 200) == []

    @pytest.mark.asyncio
    async def test_short_text_returns_empty(self):
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(_GOOD_JSON))
        # < 100 chars
        assert await extractor.decompose_claims("Solar grew.") == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_parses_well_formed_json(self):
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(_GOOD_JSON))
        claims = await extractor.decompose_claims("x" * 200)
        assert len(claims) == 2
        assert claims[0].claim_text.startswith("Global average temperature")
        assert claims[0].claim_category == ClaimCategory.STATISTICAL
        assert claims[1].claim_category == ClaimCategory.POLICY

    @pytest.mark.asyncio
    async def test_records_extraction_model_with_anthropic_prefix(self):
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(_GOOD_JSON))
        claims = await extractor.decompose_claims("x" * 200)
        for c in claims:
            assert c.extraction_model.startswith("anthropic:")

    @pytest.mark.asyncio
    async def test_max_claims_limit_respected(self):
        # 5 claims in the JSON but caller asks for 2.
        # AtomicClaim's Pydantic schema requires claim_text >= 10 chars,
        # so use realistic-length placeholder claims.
        many = json.dumps([
            {"claim_text": f"Climate datapoint number {i} was recorded in 2022",
             "claim_type": "factual",
             "claim_category": "statistical", "importance_score": 0.5}
            for i in range(5)
        ])
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(many))
        claims = await extractor.decompose_claims("x" * 200, max_claims=2)
        assert len(claims) == 2

    @pytest.mark.asyncio
    async def test_uses_versioned_prompt(self):
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(_GOOD_JSON))
        await extractor.decompose_claims("ArticleBody " * 50)
        # The fake client recorded the call; verify the prompt came from the
        # registry by checking it includes the canonical instructions.
        last = extractor._injected_client.last_call
        user_content = last["messages"][0]["content"]
        assert "atomic, verifiable claims" in user_content
        assert "Return ONLY a valid JSON array" in user_content


# ---------------------------------------------------------------------------
# JSON parse tolerance
# ---------------------------------------------------------------------------

class TestParseTolerance:
    @pytest.mark.asyncio
    async def test_handles_json_code_fence(self):
        fenced = f"```json\n{_GOOD_JSON}\n```"
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(fenced))
        claims = await extractor.decompose_claims("x" * 200)
        assert len(claims) == 2

    @pytest.mark.asyncio
    async def test_handles_prose_preamble(self):
        prose = f"Here are the extracted claims:\n\n{_GOOD_JSON}"
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(prose))
        claims = await extractor.decompose_claims("x" * 200)
        assert len(claims) == 2

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty_no_exception(self):
        extractor = AnthropicClaimExtractor(
            client=_FakeAnthropic("Not JSON at all — sorry!"),
        )
        claims = await extractor.decompose_claims("x" * 200)
        assert claims == []

    @pytest.mark.asyncio
    async def test_non_list_root_returns_empty(self):
        extractor = AnthropicClaimExtractor(
            client=_FakeAnthropic('{"claims": [{"claim_text": "x"}]}'),
        )
        claims = await extractor.decompose_claims("x" * 200)
        assert claims == []

    @pytest.mark.asyncio
    async def test_skips_dicts_missing_claim_text(self):
        partial = json.dumps([
            {"claim_text": "Valid claim with enough length for the schema",
             "claim_type": "factual",
             "claim_category": "statistical", "importance_score": 0.5},
            {"claim_type": "factual"},  # missing claim_text
            {"claim_text": ""},          # empty claim_text
        ])
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(partial))
        claims = await extractor.decompose_claims("x" * 200)
        assert len(claims) == 1
        assert claims[0].claim_text.startswith("Valid claim")


# ---------------------------------------------------------------------------
# Category fallback + importance clamp
# ---------------------------------------------------------------------------

class TestCategoryAndImportance:
    @pytest.mark.asyncio
    async def test_unknown_category_falls_back_to_classifier(self):
        payload = json.dumps([
            {"claim_text": "Solar capacity grew 35% in 2022",
             "claim_type": "factual",
             "claim_category": "made_up_category",  # invalid
             "importance_score": 0.8},
        ])
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(payload))
        claims = await extractor.decompose_claims("x" * 200)
        # ClaimClassifier picks a valid ClaimCategory based on the text.
        assert claims[0].claim_category in set(ClaimCategory)

    @pytest.mark.asyncio
    async def test_importance_clamped_to_unit_interval(self):
        # claim_text must be >=10 chars per AtomicClaim schema.
        payload = json.dumps([
            {"claim_text": "Above one importance value passed", "importance_score": 5.0},
            {"claim_text": "Below zero importance value passed", "importance_score": -2.0},
            {"claim_text": "Non numeric importance value passed", "importance_score": "high"},
        ])
        extractor = AnthropicClaimExtractor(client=_FakeAnthropic(payload))
        claims = await extractor.decompose_claims("x" * 200)
        assert len(claims) == 3
        assert claims[0].importance_score == 1.0
        assert claims[1].importance_score == 0.0
        # Non-numeric falls through to the documented default 0.9.
        assert claims[2].importance_score == 0.9


# ---------------------------------------------------------------------------
# API error propagation (so multi-LLM verifier sees it)
# ---------------------------------------------------------------------------

class TestApiErrorPropagation:
    @pytest.mark.asyncio
    async def test_api_failure_propagates(self):
        extractor = AnthropicClaimExtractor(
            client=_FakeAnthropic("", raise_exc=RuntimeError("Anthropic 500")),
        )
        with pytest.raises(RuntimeError, match="Anthropic 500"):
            await extractor.decompose_claims("x" * 200)
