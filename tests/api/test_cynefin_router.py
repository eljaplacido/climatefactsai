"""CynefinRouter tests — keyword path + structured-JSON LLM path (T3 port).

Covers the 2026-05-16 port of the projectcarfcynepic classifier prompt and
the `carf_integration._fallback_classify` delegation to CynefinRouter.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Keyword scoring path
# ---------------------------------------------------------------------------

class TestKeywordClassification:
    """No LLM call — keyword matches produce a routable classification."""

    def test_clear_keyword_match(self):
        from app.domains.intelligence.cynefin_router import CynefinRouter

        router = CynefinRouter()
        result = router.classify("What is the current temperature in Helsinki?")
        assert result["domain"] == "clear"
        assert result["recommended_strategy"] == "direct_lookup"
        assert result["confidence"] > 0.0

    def test_complex_keyword_match(self):
        from app.domains.intelligence.cynefin_router import CynefinRouter

        router = CynefinRouter()
        result = router.classify(
            "Predict how the tipping point in Arctic ice will reshape "
            "feedback loops over the long-term"
        )
        assert result["domain"] == "complex"
        assert result["recommended_strategy"] == "causal_analysis"

    def test_chaotic_keyword_match(self):
        from app.domains.intelligence.cynefin_router import CynefinRouter

        router = CynefinRouter()
        result = router.classify("Emergency: catastrophic flooding hit immediately")
        assert result["domain"] == "chaotic"
        assert result["recommended_strategy"] == "rapid_assessment"


# ---------------------------------------------------------------------------
# Structured-JSON LLM path (the T3 port)
# ---------------------------------------------------------------------------

class TestStructuredLLMClassification:
    """When keyword scoring is empty, the LLM returns JSON with confidence+reasoning."""

    def test_llm_complex_with_confidence(self, monkeypatch):
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return (
                '{"domain": "complex", "confidence": 0.82, '
                '"reasoning": "Involves emergent multi-system effects."}'
            )

        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        # Query has no overlap with any keyword list — forces the LLM path.
        result = router.classify(
            "Intersection of monsoonal variability with grid resilience."
        )
        assert result["domain"] == "complex"
        assert result["confidence"] == 0.82
        assert "emergent" in result["reasoning"].lower()
        assert result["source"] == "llm_structured"

    def test_llm_disorder_maps_to_complicated_with_low_confidence(self, monkeypatch):
        """`disorder` is the LLM's "I don't know" — route safely to complicated but cap confidence."""
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return '{"domain": "disorder", "confidence": 0.9, "reasoning": "Ambiguous"}'

        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        result = router.classify("zxy abc")
        assert result["domain"] == "complicated"  # safe default routing
        assert result["raw_domain"] == "disorder"  # transparency
        # Confidence capped at 0.4 for disorder regardless of LLM-reported value.
        assert result["confidence"] <= 0.4

    def test_llm_strips_code_fences(self, monkeypatch):
        """Robust to ```json ... ``` wrappers some models add."""
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return (
                '```json\n'
                '{"domain": "clear", "confidence": 0.95, "reasoning": "Direct lookup."}\n'
                '```'
            )

        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        result = router.classify("xyz123")
        assert result["domain"] == "clear"
        assert result["confidence"] == 0.95

    def test_llm_invalid_json_falls_through_to_default(self, monkeypatch):
        """Non-JSON LLM output must not crash — falls back to default 'complicated' with low confidence."""
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return "I cannot classify this query, it's too vague."

        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        result = router.classify("abstract")
        # _llm_classify returns None → outer classify defaults.
        assert result["domain"] == "complicated"
        assert result["confidence"] <= 0.3
        # Source field not present on the default-fallback path.
        assert result.get("source") != "llm_structured"

    def test_llm_unknown_domain_is_rejected(self, monkeypatch):
        """LLM returning an invented domain name (`urgent-ish`) falls back rather than misroute."""
        from app.domains.intelligence import llm_client
        from app.domains.intelligence.cynefin_router import CynefinRouter

        def fake_chat(**kwargs):
            return '{"domain": "urgent-ish", "confidence": 0.7, "reasoning": "made up"}'

        monkeypatch.setattr(llm_client, "llm_chat", fake_chat)

        router = CynefinRouter()
        result = router.classify("blah blah")
        # _llm_classify returns None for unknown domain → default fallback.
        assert result["domain"] == "complicated"
        assert result.get("source") != "llm_structured"


# ---------------------------------------------------------------------------
# CARF fallback delegation
# ---------------------------------------------------------------------------

class TestCarfFallbackDelegation:
    """`carf_integration._fallback_classify` must delegate to CynefinRouter
    instead of the old 4-keyword heuristic."""

    @pytest.mark.asyncio
    async def test_fallback_uses_cynefin_router_not_keywords(self, monkeypatch):
        from app.domains.intelligence.carf_integration import CARFIntegration

        client = CARFIntegration()

        # Force `_request` to fail (CARF unreachable) so _fallback_classify runs.
        async def _fake_request(self_arg, endpoint, payload):
            return None

        monkeypatch.setattr(CARFIntegration, "_request", _fake_request)

        # Text with clear-domain keywords should route via CynefinRouter →
        # "clear" / "direct_lookup", not the old "sci>=3 → complicated".
        result = await client.classify_complexity(
            "What is the current temperature in Helsinki?"
        )
        assert result is not None
        assert result["domain"] == "clear"
        # New routing key from CynefinRouter, not "fallback_<domain>" prefix.
        assert result["routing"] == "direct_lookup"
        # Source indicates the new path.
        assert "cynefin_router" in result.get("source", "") or result.get("source") in (
            "keyword", "llm_structured"
        )
