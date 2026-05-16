"""Multi-LLM cross-verification tests (Phase 5 wave 1).

Pins:
- Normalisation + Jaccard math at boundary values
- Single-LLM mode returns unverified claims (no penalty, agreement=None)
- Full agreement → agreement=1.0, no penalty
- Partial agreement → correct ratio, uncorroborated claims get penalty
- Zero agreement → all penalised, agreement=0.0
- Secondary timeout / error → fall back to single-LLM semantics with
  secondary_error captured
- Primary error propagates (we need primary claims to have output)
- Empty primary → empty output, agreement=None
- Accepts both ExtractedClaim instances and arbitrary dict/dataclass
  shapes via _to_extracted_claim
"""

from __future__ import annotations

import asyncio
from typing import Any, List

import pytest

from app.domains.intelligence.multi_llm_verifier import (
    CorroboratedClaim,
    CrossVerificationResult,
    ExtractedClaim,
    _jaccard_similarity,
    _normalise_text,
    _to_extracted_claim,
    verify_claims,
)


# ---------------------------------------------------------------------------
# Helpers: extractor factories
# ---------------------------------------------------------------------------

def _const_extractor(claims: List[Any]):
    """Build an extractor coroutine that always returns the given claims."""
    async def _fn(text: str, max_claims: int) -> List[Any]:
        return claims
    return _fn


def _slow_extractor(claims: List[Any], delay: float):
    async def _fn(text: str, max_claims: int) -> List[Any]:
        await asyncio.sleep(delay)
        return claims
    return _fn


def _failing_extractor(exc: Exception):
    async def _fn(text: str, max_claims: int) -> List[Any]:
        raise exc
    return _fn


# ---------------------------------------------------------------------------
# Normalisation + similarity
# ---------------------------------------------------------------------------

class TestNormaliseText:
    def test_lowercases_and_strips_punctuation(self):
        assert _normalise_text("Hello, World!") == "hello world"

    def test_preserves_numbers(self):
        assert _normalise_text("Solar grew 35% in 2022") == "solar grew 35 in 2022"

    def test_collapses_whitespace(self):
        assert _normalise_text("  foo \t bar\n") == "foo bar"

    def test_empty_returns_empty(self):
        assert _normalise_text("") == ""
        assert _normalise_text(None) == ""


class TestJaccardSimilarity:
    def test_identical_strings_yield_one(self):
        assert _jaccard_similarity("solar capacity grew 35%", "solar capacity grew 35%") == 1.0

    def test_disjoint_yields_zero(self):
        assert _jaccard_similarity("apples oranges", "cars trucks") == 0.0

    def test_both_empty_yields_one(self):
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty_yields_zero(self):
        assert _jaccard_similarity("solar", "") == 0.0
        assert _jaccard_similarity("", "wind") == 0.0

    def test_known_partial_overlap(self):
        # "solar grew 35" vs "solar grew 50":
        # tokens A = {solar, grew, 35}
        # tokens B = {solar, grew, 50}
        # |A ∩ B| = 2 (solar, grew); |A ∪ B| = 4 (solar, grew, 35, 50)
        # → 0.5
        sim = _jaccard_similarity("solar grew 35", "solar grew 50")
        assert sim == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# _to_extracted_claim
# ---------------------------------------------------------------------------

class TestToExtractedClaim:
    def test_passthrough_for_extracted_claim(self):
        c = ExtractedClaim(text="x", importance=0.5)
        assert _to_extracted_claim(c) is c

    def test_dict_with_claim_text_and_importance_score(self):
        d = {"claim_text": "Solar grew 35%", "importance_score": 0.8}
        c = _to_extracted_claim(d)
        assert c.text == "Solar grew 35%"
        assert c.importance == 0.8

    def test_dict_with_text_and_importance(self):
        d = {"text": "Wind grew 20%", "importance": 0.6}
        c = _to_extracted_claim(d)
        assert c.text == "Wind grew 20%"
        assert c.importance == 0.6

    def test_attribute_access_object(self):
        class _Obj:
            claim_text = "Battery deploy doubled"
            importance_score = 0.9
        c = _to_extracted_claim(_Obj())
        assert c.text == "Battery deploy doubled"
        assert c.importance == 0.9

    def test_non_numeric_importance_defaults_to_zero(self):
        d = {"text": "x", "importance": "high"}
        c = _to_extracted_claim(d)
        assert c.importance == 0.0


# ---------------------------------------------------------------------------
# verify_claims — single-LLM mode (no secondary)
# ---------------------------------------------------------------------------

class TestVerifyClaimsSingleLLM:
    @pytest.mark.asyncio
    async def test_no_secondary_returns_unverified_no_penalty(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar grew 35%", importance=0.8),
            ExtractedClaim(text="Wind grew 20%", importance=0.6),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="deepseek-chat",
            secondary_extractor=None,
        )
        assert result.secondary_model is None
        assert result.agreement_score is None
        assert result.secondary_error == "no_secondary_configured"
        assert result.primary_count == 2
        # No penalty when there's no comparator.
        for claim in result.primary_claims:
            assert claim.confidence == claim.importance
            assert claim.corroborated is False
            assert claim.similarity_to_best_match is None


# ---------------------------------------------------------------------------
# verify_claims — agreement scenarios
# ---------------------------------------------------------------------------

class TestVerifyClaimsAgreement:
    @pytest.mark.asyncio
    async def test_full_agreement(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.8),
            ExtractedClaim(text="Wind deployment doubled in 2022", importance=0.7),
        ])
        # Secondary phrasings overlap enough to clear Jaccard ≥ 0.5.
        secondary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.6),
            ExtractedClaim(text="Wind deployment doubled in 2022", importance=0.5),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="deepseek-chat",
            secondary_extractor=secondary,
            secondary_model="claude-sonnet-4-5",
        )
        assert result.agreement_score == 1.0
        assert result.corroborated_count == 2
        assert result.secondary_total_claims == 2
        for claim in result.primary_claims:
            assert claim.corroborated
            assert claim.confidence == claim.importance
            assert claim.similarity_to_best_match == 1.0

    @pytest.mark.asyncio
    async def test_zero_agreement_applies_penalty(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.8),
        ])
        secondary = _const_extractor([
            ExtractedClaim(text="Coal phase-out delayed by Germany", importance=0.7),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=secondary,
            secondary_model="B",
        )
        assert result.agreement_score == 0.0
        assert result.corroborated_count == 0
        # 0.8 importance × 0.7 penalty = 0.56.
        assert result.primary_claims[0].confidence == pytest.approx(0.56)
        assert result.primary_claims[0].corroborated is False
        assert result.primary_claims[0].matched_secondary_text is None

    @pytest.mark.asyncio
    async def test_partial_agreement(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.8),
            ExtractedClaim(text="Carbon prices fell 12% in Q3", importance=0.6),
        ])
        secondary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.7),
            # Doesn't match the carbon-prices claim.
            ExtractedClaim(text="Banking sector exit from coal speeds up", importance=0.5),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=secondary,
            secondary_model="B",
        )
        assert result.agreement_score == 0.5
        assert result.corroborated_count == 1

        # Order preserved: primary[0] corroborated, primary[1] not.
        assert result.primary_claims[0].corroborated is True
        assert result.primary_claims[0].confidence == 0.8
        assert result.primary_claims[1].corroborated is False
        assert result.primary_claims[1].confidence == pytest.approx(0.6 * 0.7)

    @pytest.mark.asyncio
    async def test_partial_overlap_below_threshold_not_corroborated(self):
        """A near-miss claim isn't corroborated when below similarity_threshold,
        but its similarity_to_best_match is still surfaced so callers can see
        why."""
        primary = _const_extractor([
            ExtractedClaim(text="Solar grew 35", importance=0.8),
        ])
        secondary = _const_extractor([
            # Primary tokens:  {solar, grew, 35}    (3)
            # Secondary tokens: {solar, grew, 50, mwh}    (4)
            # Intersection: {solar, grew}    (2)
            # Union: {solar, grew, 35, 50, mwh}    (5)
            # Jaccard = 2/5 = 0.4
            ExtractedClaim(text="Solar grew 50 mwh", importance=0.6),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=secondary,
            secondary_model="B",
            similarity_threshold=0.5,  # 0.4 is below this → not corroborated
        )
        assert result.agreement_score == 0.0
        assert result.primary_claims[0].corroborated is False
        # similarity_to_best_match still set so callers can see the near-miss.
        assert result.primary_claims[0].similarity_to_best_match == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# verify_claims — fault tolerance
# ---------------------------------------------------------------------------

class TestVerifyClaimsFaultTolerance:
    @pytest.mark.asyncio
    async def test_secondary_timeout_falls_back_to_single_llm(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar grew 35%", importance=0.8),
        ])
        slow = _slow_extractor([ExtractedClaim(text="anything", importance=0.5)], delay=1.0)

        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=slow,
            secondary_model="slow-B",
            secondary_timeout=0.05,  # forces timeout
        )
        assert result.agreement_score is None
        assert result.secondary_error is not None
        assert "timeout" in result.secondary_error
        # No penalty applied on timeout (absence of evidence isn't disagreement).
        for claim in result.primary_claims:
            assert claim.confidence == claim.importance

    @pytest.mark.asyncio
    async def test_secondary_error_falls_back_to_single_llm(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar grew 35%", importance=0.8),
        ])
        failing = _failing_extractor(RuntimeError("upstream 500"))

        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=failing,
            secondary_model="failing-B",
        )
        assert result.agreement_score is None
        assert result.secondary_error == "secondary_error:RuntimeError"
        for claim in result.primary_claims:
            assert claim.confidence == claim.importance

    @pytest.mark.asyncio
    async def test_primary_error_propagates(self):
        """If we can't even get primary claims, raise — caller needs to know."""
        primary = _failing_extractor(RuntimeError("primary down"))
        secondary = _const_extractor([])

        with pytest.raises(RuntimeError, match="primary down"):
            await verify_claims(
                text="any",
                max_claims=10,
                primary_extractor=primary,
                primary_model="A",
                secondary_extractor=secondary,
                secondary_model="B",
            )

    @pytest.mark.asyncio
    async def test_empty_primary_yields_empty_output(self):
        primary = _const_extractor([])
        secondary = _const_extractor([ExtractedClaim(text="x", importance=0.5)])

        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=secondary,
            secondary_model="B",
        )
        assert result.primary_count == 0
        # agreement_score is None when there's no primary to score against
        # (0/0 is undefined, not 1.0).
        assert result.agreement_score is None
        assert result.secondary_error is None  # secondary ran fine
        assert result.secondary_total_claims == 1


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestResultAsDict:
    @pytest.mark.asyncio
    async def test_as_dict_serialises_cleanly(self):
        primary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.8),
        ])
        secondary = _const_extractor([
            ExtractedClaim(text="Solar capacity grew 35% in 2022", importance=0.7),
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="deepseek-chat",
            secondary_extractor=secondary,
            secondary_model="claude-sonnet-4-5",
        )
        out = result.as_dict()
        assert out["primary_model"] == "deepseek-chat"
        assert out["secondary_model"] == "claude-sonnet-4-5"
        assert out["agreement_score"] == 1.0
        assert out["corroborated_count"] == 1
        assert out["primary_count"] == 1
        assert out["similarity_threshold"] == 0.5
        assert "claims" in out
        assert out["claims"][0]["corroborated"] is True
        assert out["claims"][0]["matched_secondary_text"] == "Solar capacity grew 35% in 2022"


# ---------------------------------------------------------------------------
# Integration with dict-shaped claims (e.g. AtomicClaim from services.py)
# ---------------------------------------------------------------------------

class TestVerifyAcceptsRawShapes:
    @pytest.mark.asyncio
    async def test_dicts_with_claim_text_field(self):
        # ClaimExtractor in this codebase yields objects with .claim_text +
        # .importance_score — verify_claims must normalise them.
        primary = _const_extractor([
            {"claim_text": "Solar grew 35%", "importance_score": 0.8},
            {"claim_text": "Wind doubled", "importance_score": 0.7},
        ])
        secondary = _const_extractor([
            {"claim_text": "Solar grew 35%", "importance_score": 0.6},
        ])
        result = await verify_claims(
            text="any",
            max_claims=10,
            primary_extractor=primary,
            primary_model="A",
            secondary_extractor=secondary,
            secondary_model="B",
        )
        assert result.primary_count == 2
        assert result.corroborated_count == 1
        assert result.primary_claims[0].text == "Solar grew 35%"
        assert result.primary_claims[0].importance == 0.8
