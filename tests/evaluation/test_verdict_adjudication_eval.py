"""
DeepEval evaluation tests for the VerdictAdjudicator pipeline.

Tests verdict quality using:
- HallucinationMetric: Are verdicts grounded in provided evidence?
- Custom VerdictAccuracyMetric: Do verdicts match golden labels?

Run with: pytest tests/evaluation/test_verdict_adjudication_eval.py -m evaluation
"""

import pytest

pytestmark = [pytest.mark.evaluation, pytest.mark.slow]


def test_verdict_hallucination(verdicts_golden_dataset, openai_api_key):
    """Test that verdicts don't hallucinate beyond provided evidence."""
    from deepeval import evaluate
    from deepeval.metrics import HallucinationMetric
    from deepeval.test_case import LLMTestCase

    metric = HallucinationMetric(threshold=0.7, model="gpt-4o-mini")

    test_cases = []
    for entry in verdicts_golden_dataset[:15]:
        claim_text = entry["claim_text"]
        evidence_texts = [e["content"] for e in entry.get("evidence", [])]
        expected_verdict = entry.get("expected_verdict", {})
        justification = expected_verdict.get("justification", "")

        if not evidence_texts or not justification:
            continue

        test_cases.append(
            LLMTestCase(
                input=f"Verify this claim: {claim_text}",
                actual_output=justification,
                context=evidence_texts,
            )
        )

    if not test_cases:
        pytest.skip("No test cases generated from golden dataset")

    results = evaluate(test_cases, [metric])
    passed = sum(1 for r in results.test_results if r.success)
    total = len(results.test_results)
    assert passed / total >= 0.6, f"Only {passed}/{total} verdicts passed hallucination check"


def test_verdict_accuracy(verdicts_golden_dataset):
    """Test verdict classification accuracy against golden labels."""
    correct = 0
    total = 0

    verdict_map = {
        "verified": "verified",
        "true": "verified",
        "disputed": "disputed",
        "false": "disputed",
        "partially_true": "partially_true",
        "unverified": "unverified",
    }

    for entry in verdicts_golden_dataset:
        expected = entry.get("expected_verdict", {}).get("verdict")
        actual = entry.get("actual_verdict")
        if expected and actual:
            total += 1
            # Normalize both to common labels
            expected_norm = verdict_map.get(expected, expected)
            actual_norm = verdict_map.get(actual, actual)
            if expected_norm == actual_norm:
                correct += 1

    if total == 0:
        pytest.skip("No verdict pairs in golden dataset")

    accuracy = correct / total
    assert accuracy >= 0.5, f"Verdict accuracy {accuracy:.0%} below 50% threshold"


def test_confidence_calibration(verdicts_golden_dataset):
    """Test that confidence scores are reasonably calibrated."""
    high_conf_correct = 0
    high_conf_total = 0
    low_conf_incorrect = 0
    low_conf_total = 0

    for entry in verdicts_golden_dataset:
        expected = entry.get("expected_verdict", {}).get("verdict")
        actual = entry.get("actual_verdict")
        confidence = entry.get("actual_confidence", 0.5)

        if not expected or not actual:
            continue

        is_correct = expected == actual

        if confidence >= 0.8:
            high_conf_total += 1
            if is_correct:
                high_conf_correct += 1
        elif confidence <= 0.4:
            low_conf_total += 1
            if not is_correct:
                low_conf_incorrect += 1

    # High-confidence verdicts should be mostly correct
    if high_conf_total >= 3:
        rate = high_conf_correct / high_conf_total
        assert rate >= 0.6, f"High-confidence accuracy {rate:.0%} too low"
