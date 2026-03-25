"""
DeepEval evaluation tests for insight summary generation.

Tests that generated summaries are factually consistent with verification results.

Run with: pytest tests/evaluation/test_insight_generation_eval.py -m evaluation
"""

import pytest

pytestmark = [pytest.mark.evaluation, pytest.mark.slow]


def test_insight_factual_consistency(verdicts_golden_dataset, openai_api_key):
    """Test that insight summaries are factually consistent with verification data."""
    from deepeval import evaluate
    from deepeval.metrics import FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    metric = FaithfulnessMetric(threshold=0.6, model="gpt-4o-mini")

    test_cases = []
    for entry in verdicts_golden_dataset[:10]:
        insight = entry.get("expected_insight_summary")
        if not insight:
            continue

        # Build context from verification results
        claim_text = entry["claim_text"]
        verdict = entry.get("expected_verdict", {})
        evidence_texts = [e["content"] for e in entry.get("evidence", [])]

        context = [
            f"Claim: {claim_text}",
            f"Verdict: {verdict.get('verdict', 'unknown')}",
            f"Confidence: {verdict.get('confidence', 0.5):.0%}",
        ] + evidence_texts

        test_cases.append(
            LLMTestCase(
                input="Generate an insight summary for this fact-checked article.",
                actual_output=insight,
                retrieval_context=context,
            )
        )

    if not test_cases:
        pytest.skip("No insight summaries in golden dataset")

    results = evaluate(test_cases, [metric])
    passed = sum(1 for r in results.test_results if r.success)
    total = len(results.test_results)
    assert passed / total >= 0.5, f"Only {passed}/{total} insights passed consistency check"


def test_insight_contains_key_metrics(verdicts_golden_dataset):
    """Test that insight summaries mention key verification metrics."""
    tested = 0
    passed = 0

    metric_keywords = ["verified", "confidence", "claim", "evidence", "credib"]

    for entry in verdicts_golden_dataset:
        insight = entry.get("expected_insight_summary", "")
        if not insight:
            continue
        tested += 1
        insight_lower = insight.lower()
        matches = sum(1 for kw in metric_keywords if kw in insight_lower)
        if matches >= 2:
            passed += 1

    if tested == 0:
        pytest.skip("No insight summaries to test")

    rate = passed / tested
    assert rate >= 0.5, f"Only {rate:.0%} of insights mention key metrics"
