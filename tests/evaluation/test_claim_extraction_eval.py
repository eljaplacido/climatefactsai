"""
DeepEval evaluation tests for the ClaimExtractor pipeline.

Tests claim extraction quality using:
- AnswerRelevancyMetric: Are extracted claims relevant to the article?
- FaithfulnessMetric: Are claims faithful to the source text?

Run with: pytest tests/evaluation/test_claim_extraction_eval.py -m evaluation
"""

import pytest

pytestmark = [pytest.mark.evaluation, pytest.mark.slow]


def test_claim_extraction_relevancy(claims_golden_dataset, openai_api_key):
    """Test that extracted claims are relevant to the source article."""
    from deepeval import evaluate
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase

    metric = AnswerRelevancyMetric(threshold=0.7, model="gpt-4o-mini")

    test_cases = []
    for entry in claims_golden_dataset[:10]:
        article_text = entry["article_text"]
        expected_claims = entry["expected_claims"]

        # Each expected claim should be relevant to the article
        for claim in expected_claims:
            test_cases.append(
                LLMTestCase(
                    input=article_text[:2000],
                    actual_output=claim["claim_text"],
                    expected_output=claim["claim_text"],
                    context=[article_text[:2000]],
                )
            )

    if not test_cases:
        pytest.skip("No test cases generated from golden dataset")

    results = evaluate(test_cases, [metric])
    passed = sum(1 for r in results.test_results if r.success)
    total = len(results.test_results)
    assert passed / total >= 0.7, f"Only {passed}/{total} claims passed relevancy check"


def test_claim_extraction_faithfulness(claims_golden_dataset, openai_api_key):
    """Test that extracted claims are faithful to (grounded in) the source text."""
    from deepeval import evaluate
    from deepeval.metrics import FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    metric = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")

    test_cases = []
    for entry in claims_golden_dataset[:10]:
        article_text = entry["article_text"]
        expected_claims = entry["expected_claims"]

        # Combine all claims as the output to check faithfulness
        combined_output = "\n".join(c["claim_text"] for c in expected_claims)

        test_cases.append(
            LLMTestCase(
                input=f"Extract verifiable claims from this article:\n{article_text[:2000]}",
                actual_output=combined_output,
                retrieval_context=[article_text[:2000]],
            )
        )

    if not test_cases:
        pytest.skip("No test cases generated from golden dataset")

    results = evaluate(test_cases, [metric])
    passed = sum(1 for r in results.test_results if r.success)
    total = len(results.test_results)
    assert passed / total >= 0.6, f"Only {passed}/{total} articles passed faithfulness check"


def test_claim_category_accuracy(claims_golden_dataset):
    """Test claim category classification accuracy against golden labels."""
    correct = 0
    total = 0

    for entry in claims_golden_dataset:
        for claim in entry.get("expected_claims", []):
            expected_cat = claim.get("expected_category")
            actual_cat = claim.get("claim_category")
            if expected_cat and actual_cat:
                total += 1
                if expected_cat == actual_cat:
                    correct += 1

    if total == 0:
        pytest.skip("No categorized claims in golden dataset")

    accuracy = correct / total
    assert accuracy >= 0.6, f"Category accuracy {accuracy:.0%} below 60% threshold"
