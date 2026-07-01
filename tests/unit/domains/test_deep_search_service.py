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
    """Both per-side searches time out -> both sides report 0 sources ->
    the §3.1 fix kicks in: skip the LLM comparative (no evidence to
    compare) and emit the deterministic empty-empty explainer + guidance.

    Pre-2026-05-23 this test asserted the LLM comparative still ran on
    empty input. That was the bug the §3.1 fix targets — comparing two
    voids would produce a hallucinated comparison. New contract: empty
    coverage MUST surface the deterministic explainer."""
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
    # MUST NOT be called on the both-sides-empty path (post §3.1 fix).
    service._generate_comparison = AsyncMock(
        side_effect=AssertionError("LLM comparative must not run when both sides empty")
    )
    service._generate_comparison_structured = AsyncMock(
        side_effect=AssertionError("Structured LLM must not run when both sides empty")
    )
    # _suggest_scope_refinements is now invoked twice (one per side); stub it.
    service._suggest_scope_refinements = AsyncMock(return_value=["refine"])

    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SIDE_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("DEEP_SEARCH_COMPARE_SYNTHESIS_TIMEOUT_SECONDS", "2")

    result = await service.compare("topic a", "topic b", country="FI")

    assert result["query_a"] == "topic a"
    assert result["query_b"] == "topic b"
    assert result["result_a"]["query"] == "topic a"
    assert result["result_b"]["query"] == "topic b"
    assert result["result_a"]["internal_articles_count"] == 0
    assert result["result_b"]["internal_articles_count"] == 0
    # New behaviour: deterministic explainer, not LLM hallucination
    assert "could not find evidence" in result["comparative_analysis"].lower()
    assert result["comparative_analysis_structured"] is None
    assert result["guidance"]["status"] == "empty"
    assert result["low_confidence"] is True


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


# ---------------------------------------------------------------------------
# §3.1 (2026-05-23) — compare aggregate guidance + low-evidence fallback
# ---------------------------------------------------------------------------
# These tests pin the four branches of the new behaviour:
#   - both_sides_empty: deterministic explainer + unified chips + guidance=empty
#   - one_side_empty: low_confidence pill + guidance=asymmetric
#   - aggregate_weak: guidance=weak + single combined refinement
#   - strong_evidence: no guidance block
# ---------------------------------------------------------------------------


def _side_payload(query: str, internal: int, external: int) -> dict:
    """Build a per-side payload with the requested coverage shape."""
    citations = [
        {
            "type": "internal_article",
            "article_id": f"art-{i}",
            "title": f"Source {i}",
            "source_name": "Nature",
            "credibility": "HIGH",
        }
        for i in range(internal)
    ] + [
        {"type": "external_web", "source_url": f"https://example.com/{i}"}
        for i in range(external)
    ]
    return {
        "query": query,
        "answer": "stub answer",
        "citations": citations,
        "internal_articles_count": internal,
        "external_sources_count": external,
        "weather_context": None,
        "filters": {"country": "FI"},
        "methodology": {"queries_run": [], "synthesis_model": "anthropic"},
        "clarification_needed": None,
        "searched_at": datetime.utcnow().isoformat(),
    }


@pytest.mark.asyncio
async def test_compare_both_sides_empty_emits_deterministic_explainer_and_chips():
    """When both topics return 0 sources we MUST NOT invoke the LLM
    comparative synthesis (it would hallucinate a comparison). Instead we
    emit a deterministic explainer + the union of both sides' refinement
    chips + a guidance block with status='empty'."""
    service = DeepSearchService(_FakeDB())

    service.search = AsyncMock(side_effect=[
        _side_payload("Arctic ice melt acceleration", 0, 0),
        _side_payload("Antarctic ice shelf loss comparison", 0, 0),
    ])
    # If the LLM comparative was wrongly called, the test would fail —
    # because both_sides_empty path is supposed to skip it entirely.
    service._generate_comparison = AsyncMock(
        side_effect=AssertionError("LLM comparative MUST NOT run when both sides empty")
    )
    service._generate_comparison_structured = AsyncMock(
        side_effect=AssertionError("Structured comparative MUST NOT run when both sides empty")
    )
    service._suggest_scope_refinements = AsyncMock(side_effect=[
        ["Arctic sea-ice September minimum 2010-2024", "Arctic sea-ice extent vs 1981-2010 baseline"],
        ["Larsen C ice shelf mass balance 2015-2024", "Antarctic ice loss rates 2000-2024"],
    ])

    result = await service.compare(
        "Arctic ice melt acceleration",
        "Antarctic ice shelf loss comparison",
        country="FI",
    )

    # Guidance block surfaces status=empty with per-side counters at 0/0
    assert result["guidance"] is not None
    assert result["guidance"]["status"] == "empty"
    assert result["guidance"]["reason"] == "no_matching_evidence_either_side"
    assert result["guidance"]["per_side"] == {
        "a": {"internal": 0, "external": 0},
        "b": {"internal": 0, "external": 0},
    }

    # Deterministic explainer, not an LLM-synthesised comparison
    assert "could not find evidence" in result["comparative_analysis"].lower()
    assert result["comparative_analysis_structured"] is None

    # Unified chips drawn from both sides, deduped, capped at 6
    assert isinstance(result["clarification_needed"], list)
    assert len(result["clarification_needed"]) == 4
    assert "Arctic sea-ice September minimum 2010-2024" in result["clarification_needed"]
    assert "Larsen C ice shelf mass balance 2015-2024" in result["clarification_needed"]

    # Top-level low_confidence flag is set
    assert result["low_confidence"] is True


@pytest.mark.asyncio
async def test_compare_one_side_empty_emits_asymmetric_guidance_and_low_confidence():
    """When exactly one topic has 0 sources, the comparative MAY still run
    (LLM has something to talk about on one side) but it MUST be tagged as
    low_confidence and the guidance MUST flag the asymmetry explicitly."""
    service = DeepSearchService(_FakeDB())

    service.search = AsyncMock(side_effect=[
        _side_payload("Topic A with evidence", internal=4, external=2),
        _side_payload("Topic B empty", internal=0, external=0),
    ])
    service._generate_comparison = AsyncMock(return_value="A has 6 sources; B has none.")
    service._generate_comparison_structured = AsyncMock(return_value={
        "summary": "A vs B",
        "similarities": [],
        "differences": [],
        "evidence_strength": "asymmetric",
        "common_gaps": [],
    })

    result = await service.compare("Topic A with evidence", "Topic B empty")

    assert result["guidance"] is not None
    assert result["guidance"]["status"] == "asymmetric"
    assert result["guidance"]["reason"] == "one_side_empty"
    assert "Topic B" in result["guidance"]["message"]
    assert result["guidance"]["per_side"]["a"] == {"internal": 4, "external": 2}
    assert result["guidance"]["per_side"]["b"] == {"internal": 0, "external": 0}

    # Structured comparative was tagged with low_confidence + reason
    structured = result["comparative_analysis_structured"]
    assert structured is not None
    assert structured["low_confidence"] is True
    assert "Topic B" in structured["low_confidence_reason"]

    assert result["low_confidence"] is True


@pytest.mark.asyncio
async def test_compare_weak_aggregate_emits_weak_guidance_and_unified_refinements():
    """Aggregate evidence < 4 (but not 0+0): emit weak guidance and a
    SINGLE combined refinement call against the joint query, not per-side."""
    service = DeepSearchService(_FakeDB())

    service.search = AsyncMock(side_effect=[
        _side_payload("Topic A", internal=1, external=0),
        _side_payload("Topic B", internal=1, external=1),  # aggregate = 3
    ])
    service._generate_comparison = AsyncMock(return_value="comparative ok")
    service._generate_comparison_structured = AsyncMock(return_value={
        "summary": "tiny",
        "similarities": [],
        "differences": [],
        "evidence_strength": "weak",
        "common_gaps": [],
    })
    combined_refinement = AsyncMock(return_value=[
        "Constrain by country and year range",
        "Add domain-specific terms",
    ])
    service._suggest_scope_refinements = combined_refinement

    result = await service.compare("Topic A", "Topic B")

    assert result["guidance"] is not None
    assert result["guidance"]["status"] == "weak"
    assert result["guidance"]["reason"] == "low_aggregate_coverage"
    assert result["low_confidence"] is True

    # Exactly ONE refinement call against the combined "A vs B" query
    combined_refinement.assert_awaited_once()
    args, _kwargs = combined_refinement.call_args
    assert "Topic A vs Topic B" in args[0]

    # Chips came through and are not None
    assert isinstance(result["clarification_needed"], list)
    assert "Constrain by country and year range" in result["clarification_needed"]


# ---------------------------------------------------------------------------
# §3.3 (2026-05-23) — low-evidence routing + sentence-level grounding
# ---------------------------------------------------------------------------
# When `search()` retrieval returns < 3 total sources, it MUST route to the
# `deep_search_synthesis_low_evidence` prompt and return:
#   - the synthesised answer text under `answer`
#   - sentence_grounding[] with HIGH/MEDIUM/LOW/NONE level tags
#   - confidence_envelope with confidence="low" + reason
#   - methodology.prompts_used.synthesis pointing at the low-evidence prompt
# When retrieval is strong (>=3), the high-evidence prompt is used and
# sentence_grounding is None.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_routes_to_low_evidence_prompt_when_thin(monkeypatch):
    """Empty corpus + no external sources -> route to low-evidence prompt;
    response carries sentence_grounding[] and confidence envelope."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())
    service._search_internal_corpus = AsyncMock(return_value=[])
    service._search_perplexity = AsyncMock(return_value={"answer": "", "citations": []})

    low_eval_fixture = {
        "answer_markdown": "Tuvalu has limited corpus coverage.",
        "sentence_grounding": [
            {"text": "Tuvalu has limited corpus coverage.", "level": "HIGH", "reason": "platform-introspection"},
        ],
        "confidence": "low",
        "confidence_reason": "no_internal_sources",
        "suggested_refinements": [
            "Tuvalu sea-level rise 2020-2024",
            "Tuvalu adaptation funding pledges",
        ],
    }
    service._synthesize_low_evidence_answer = AsyncMock(return_value=low_eval_fixture)
    service._synthesize_answer = AsyncMock(
        side_effect=AssertionError("High-evidence prompt must NOT run when retrieval is thin"),
    )

    result = await service.search("climate in Tuvalu", country="TV")

    # Answer text comes from the low-evidence envelope
    assert result["answer"] == "Tuvalu has limited corpus coverage."
    # Sentence grounding is present
    assert result["sentence_grounding"] == low_eval_fixture["sentence_grounding"]
    # Confidence envelope set with low + reason
    assert result["confidence_envelope"] == {
        "confidence": "low",
        "reason": "no_internal_sources",
    }
    # Refinements merged into clarification_needed
    assert "Tuvalu sea-level rise 2020-2024" in (result["clarification_needed"] or [])
    # Methodology records the low-evidence prompt as the synthesis prompt
    synth_prompt = result["methodology"]["prompts_used"]["synthesis"]
    assert synth_prompt["name"] == "deep_search_synthesis_low_evidence"


@pytest.mark.asyncio
async def test_search_uses_high_evidence_prompt_when_sources_abundant(monkeypatch):
    """When retrieval returns >=3 sources, the legacy prompt path runs and
    sentence_grounding stays None."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())
    # 3 internal articles is enough to route to the standard path
    service._search_internal_corpus = AsyncMock(return_value=[
        {"article_id": f"a{i}", "title": f"T{i}", "source_name": "Nature", "excerpt": "..."}
        for i in range(3)
    ])
    service._search_perplexity = AsyncMock(return_value={"answer": "external", "citations": ["u"]})
    service._synthesize_answer = AsyncMock(return_value="standard synthesis text")
    service._synthesize_low_evidence_answer = AsyncMock(
        side_effect=AssertionError("Low-evidence prompt must NOT run on the abundant-evidence path"),
    )

    result = await service.search("renewable energy in Germany", country="DE")

    assert result["answer"] == "standard synthesis text"
    assert result["sentence_grounding"] is None
    assert result["confidence_envelope"] is None
    # Methodology points at the standard prompt
    synth_prompt = result["methodology"]["prompts_used"]["synthesis"]
    assert synth_prompt["name"] == "deep_search_synthesis"


@pytest.mark.asyncio
async def test_low_evidence_synthesis_parses_fenced_json_response(monkeypatch):
    """LLMs sometimes wrap JSON in ```json ... ``` fences. _synthesize_low_evidence_answer
    MUST strip the fence and parse the JSON, not return the raw fenced string."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())

    fake_llm_response = """Here's the JSON:
```json
{
  "answer_markdown": "Fenced answer.",
  "sentence_grounding": [{"text": "Fenced answer.", "level": "MEDIUM"}],
  "confidence": "low",
  "confidence_reason": "test",
  "suggested_refinements": ["one"]
}
```
"""

    # Stub the Claude call to return the fenced response
    class _FakeMessage:
        def __init__(self, text):
            self.content = [type("C", (), {"text": text})()]

    class _FakeAnthropic:
        def __init__(self, *args, **kwargs):
            class _M:
                def create(_self, **_kwargs):
                    return _FakeMessage(fake_llm_response)
            self.messages = _M()

    import sys
    sys.modules["anthropic"] = type("M", (), {"Anthropic": _FakeAnthropic})()

    result = await service._synthesize_low_evidence_answer(
        query="q",
        internal_articles=[],
        perplexity_answer="",
        weather_context=None,
    )

    assert result["answer_markdown"] == "Fenced answer."
    assert result["sentence_grounding"] == [{"text": "Fenced answer.", "level": "MEDIUM"}]
    assert result["confidence"] == "low"


@pytest.mark.asyncio
async def test_low_evidence_synthesis_falls_back_when_llm_returns_garbage(monkeypatch):
    """When the LLM returns prose that can't be parsed as JSON, the method
    MUST fall back to a synthetic envelope so the UI still gets something
    sane — never raise."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())

    class _FakeMessage:
        def __init__(self, text):
            self.content = [type("C", (), {"text": text})()]

    class _FakeAnthropic:
        def __init__(self, *args, **kwargs):
            class _M:
                def create(_self, **_kwargs):
                    return _FakeMessage("Sorry, I cannot respond in JSON today.")
            self.messages = _M()

    import sys
    sys.modules["anthropic"] = type("M", (), {"Anthropic": _FakeAnthropic})()

    result = await service._synthesize_low_evidence_answer(
        query="q",
        internal_articles=[],
        perplexity_answer="",
        weather_context=None,
    )

    # Garbage path still produces a usable envelope, never raises
    assert "answer_markdown" in result
    assert result["confidence"] == "low"
    assert result["confidence_reason"] == "llm_response_unparseable"
    # sentence_grounding is None when we can't parse — UI falls back to plain prose
    assert result["sentence_grounding"] is None


@pytest.mark.asyncio
async def test_low_evidence_synthesis_no_llm_returns_synthetic_envelope(monkeypatch):
    """When neither Claude nor DeepSeek is configured, the method returns a
    synthetic envelope explaining the LLM gap rather than raising."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    service = DeepSearchService(_FakeDB())

    result = await service._synthesize_low_evidence_answer(
        query="climate in Tuvalu",
        internal_articles=[],
        perplexity_answer="",
        weather_context=None,
    )

    assert "Tuvalu" in result["answer_markdown"]
    assert result["confidence"] == "low"
    assert result["confidence_reason"] == "no_llm_available_and_no_retrieved_evidence"
    # Synthetic envelope ships pre-built sentence_grounding so the UI still
    # renders the calibrated view (introspective sentences are HIGH grounded).
    assert isinstance(result["sentence_grounding"], list)
    assert len(result["sentence_grounding"]) >= 2
    assert all(s["level"] == "HIGH" for s in result["sentence_grounding"])


@pytest.mark.asyncio
async def test_compare_strong_evidence_emits_no_guidance():
    """When both sides have substantial evidence (aggregate >= 4), no
    guidance block is emitted and low_confidence is False."""
    service = DeepSearchService(_FakeDB())

    service.search = AsyncMock(side_effect=[
        _side_payload("Topic A", internal=5, external=3),
        _side_payload("Topic B", internal=4, external=2),
    ])
    service._generate_comparison = AsyncMock(return_value="strong comparative")
    service._generate_comparison_structured = AsyncMock(return_value={
        "summary": "robust",
        "similarities": ["a"],
        "differences": ["b"],
        "evidence_strength": "high",
        "common_gaps": [],
    })

    result = await service.compare("Topic A", "Topic B")

    assert result["guidance"] is None
    assert result["low_confidence"] is False
    assert result["clarification_needed"] in (None, [])
    # Structured comparative did NOT get a low_confidence tag
    assert "low_confidence" not in result["comparative_analysis_structured"] or \
        result["comparative_analysis_structured"].get("low_confidence") is not True


# ---------------------------------------------------------------------------
# ML-04 (2026-07-01) — zero-evidence deep-search must be honest, and the
# hallucination grounding check MUST run on the empty-source path (it used to
# be skipped there by an `if source_texts:` guard — the most hallucination-
# prone path went out unchecked with hallucination_check=null).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_evidence_search_is_honest_and_grounding_check_runs(monkeypatch):
    """A zero-evidence query (0 internal, 0 external, no LLM configured) must:
      * surface an explicit insufficient-evidence signal in the answer,
      * NOT emit a confident fabricated factual claim, and
      * carry a NON-NULL hallucination_check in methodology (proving the
        grounding check ran even though there were no source texts)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    # Keep the LLM grounding sub-check hermetic + offline.
    from app.domains.intelligence import llm_client
    monkeypatch.setattr(llm_client, "llm_chat", lambda **kwargs: "", raising=False)

    service = DeepSearchService(_FakeDB())
    service._search_internal_corpus = AsyncMock(return_value=[])
    service._search_perplexity = AsyncMock(return_value={"answer": "", "citations": []})
    service._suggest_scope_refinements = AsyncMock(return_value=["refine 1", "refine 2"])

    result = await service.search("obscure query with no corpus coverage", country="TV")

    answer = (result["answer"] or "").lower()
    # Insufficient-evidence signal present.
    assert (
        "do not currently have verified evidence" in answer
        or "insufficient" in answer
        or "could not find" in answer
    )
    # No confident numeric/unit fabrication (the live bug surfaced "~21-24 cm").
    assert " cm" not in answer and "°c" not in answer

    # The grounding check RAN on the empty-source path: real, non-null verdict.
    hcheck = result["methodology"]["hallucination_check"]
    assert hcheck is not None
    assert "hallucination_risk" in hcheck

    # Methodology distinguishes an unconfigured/failed layer from a clean miss.
    layers = {q["layer"]: q for q in result["methodology"]["queries_run"]}
    assert layers["perplexity_external"]["status"] in {
        "skipped_unconfigured", "skipped_platform_only", "error", "ok"
    }


@pytest.mark.asyncio
async def test_detector_allow_empty_sources_flags_fabricated_statistic(monkeypatch):
    """With allow_empty_sources=True the grounding check runs against an EMPTY
    source set: a fabricated statistic is flagged and the verdict is real —
    not the all-clear _empty_result the default (guarded) path returns."""
    from unittest.mock import MagicMock

    from app.domains.intelligence import llm_client
    from app.domains.intelligence.hallucination_detector import HallucinationDetector

    monkeypatch.setattr(llm_client, "llm_chat", lambda **kwargs: "", raising=False)

    det = HallucinationDetector(db=MagicMock())

    # Default preserves the historical all-clear contract on empty sources.
    default_out = await det.check("Sea level rose 21 cm since 1900.", [])
    assert default_out["hallucination_risk"] == 0.0
    assert default_out["checks_performed"] == []

    # Opt-in: the fabricated statistic is graded against the empty source set.
    out = await det.check(
        "Sea level rose 21 cm since 1900.", [], allow_empty_sources=True
    )
    assert out["checks_performed"]  # non-empty: checks actually ran
    assert out["statistic_accuracy"] < 1.0  # "21" not found in (empty) sources
    assert out["flagged_segments"]  # the unsupported statistic was flagged


# ---------------------------------------------------------------------------
# ML-02 (2026-07-01) — methodology honesty. The bge-m3 query embedder is
# unreachable in prod (GX10 tunnel down), so the vector layer usually
# contributes nothing. The methodology must NOT hardcode "bge-m3"/"fts+semantic"
# — it may only claim semantic ran when the vector layer actually produced rows.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_methodology_reports_fts_only_when_semantic_absent(monkeypatch):
    """Internal corpus returns FTS-layer rows (embedding unavailable / semantic
    empty): methodology reports FTS-only, embedding_model is null, and it does
    NOT claim bge-m3/semantic ran."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())
    service._search_internal_corpus = AsyncMock(return_value=[
        {
            "article_id": f"a{i}", "title": f"T{i}", "source_name": "Nature",
            "excerpt": "renewable capacity grew", "retrieval_layer": "fts",
            "relevance_score": 0.5,
        }
        for i in range(3)
    ])
    service._search_perplexity = AsyncMock(return_value={"answer": "", "citations": []})
    service._synthesize_answer = AsyncMock(return_value="synthesis text")

    result = await service.search(
        "renewable energy", country="DE",
        include_hallucination_check=False, include_refinements=False,
    )
    m = result["methodology"]
    assert m["semantic_retrieval_used"] is False
    assert m["embedding_model"] is None
    assert "semantic" not in m["retrieval_strategy"]
    assert "fts" in m["retrieval_strategy"]
    internal_q = next(q for q in m["queries_run"] if q["layer"] == "internal_corpus")
    assert internal_q.get("retrieval_mode") == "fts"


@pytest.mark.asyncio
async def test_methodology_reports_bge_m3_only_when_semantic_contributed(monkeypatch):
    """When the vector layer genuinely produced rows, the methodology may name
    bge-m3 / semantic — the honest positive case."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    service = DeepSearchService(_FakeDB())
    service._search_internal_corpus = AsyncMock(return_value=[
        {
            "article_id": f"a{i}", "title": f"T{i}", "source_name": "Nature",
            "excerpt": "renewable capacity grew", "retrieval_layer": "semantic",
            "relevance_score": 0.82,
        }
        for i in range(3)
    ])
    service._search_perplexity = AsyncMock(return_value={"answer": "", "citations": []})
    service._synthesize_answer = AsyncMock(return_value="synthesis text")

    result = await service.search(
        "renewable energy", country="DE",
        include_hallucination_check=False, include_refinements=False,
    )
    m = result["methodology"]
    assert m["semantic_retrieval_used"] is True
    assert m["embedding_model"] == "bge-m3"
    assert "semantic" in m["retrieval_strategy"]
    internal_q = next(q for q in m["queries_run"] if q["layer"] == "internal_corpus")
    assert internal_q.get("retrieval_mode") == "semantic"
