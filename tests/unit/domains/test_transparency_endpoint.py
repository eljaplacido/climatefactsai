"""ML-05 (2026-07-01) — per-article Transparency Report must reflect REAL
claim_provenance instead of fabricating provenance.

The old endpoint hard-coded, for EVERY article: model "Claude 3.5 Sonnet /
DeepSeek", a fixed 5-source evidence list, and a "Bayesian posterior with
source prior" — even for an article with 0 claims that consulted none of those
sources and was enriched by a different model. These tests pin the honest
behaviour: methodology is driven by real provenance rows, un-run steps are
marked "not run for this article", the reliability breakdown surfaces the three
REAL headline components (source .50 / claims .30 / relevance .20), and no
fabricated model / evidence source / "Bayesian" language survives.
"""

from __future__ import annotations

import json

import pytest

from app.domains.intelligence.transparency import get_article_transparency


class _TransparencyFakeDB:
    """Routes the handful of queries `get_article_transparency` runs to
    caller-supplied fixtures, so the endpoint can be exercised without a DB."""

    def __init__(self, article_row, provenance_rows=None, claim_rows=None, fc_counts=None):
        self.article_row = article_row
        self.provenance_rows = provenance_rows or []
        self.claim_rows = claim_rows or []
        self.fc_counts = fc_counts or {
            "verified_count": 0,
            "false_count": 0,
            "misleading_count": 0,
            "adjudicated_count": 0,
        }

    def execute_query(self, query, params=None):
        q = " ".join(query.split()).lower()
        if "from claim_provenance" in q:
            return [dict(r) for r in self.provenance_rows]
        if "from claims c" in q and "count(*) filter" in q:
            return [dict(self.fc_counts)]
        if "from claims c" in q:  # detailed claims (evidence chains)
            return [dict(r) for r in self.claim_rows]
        if "from articles a" in q and "left join source_credibility" in q:
            return [dict(self.article_row)]
        # source_profiles, source_credibility_tiers (3-axis), anything else.
        return []


def _article_row(**overrides):
    row = {
        "article_id": "art-xyz",
        "title": "Some climate article",
        "source_name": "Example News",
        "reliability_score": 42,
        "overall_credibility": "LOW",
        "content_relevance_score": 0.5,
        "source_credibility_score": 60,
        "claims_count": 0,
        "article_decomposed_confidence": None,
        "source_profile_id": None,
        "source_score": 0,
        "factual_score": 0,
        "transparency_score": 0,
        "reliability_tier": "public",
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_transparency_zero_claims_no_fabricated_provenance():
    db = _TransparencyFakeDB(_article_row())
    resp = await get_article_transparency("art-xyz", db=db)

    method_blob = json.dumps(resp.methodology)
    # No fabricated model / invented evidence-source list / "Bayesian" language.
    assert "Claude 3.5" not in method_blob
    assert "Bayesian" not in method_blob
    assert "NASA GISS" not in method_blob  # one of the 5 fabricated sources

    # Steps that did not run for this article are marked honestly.
    assert resp.methodology["claim_extraction"]["method"] == "Not run for this article"
    assert resp.methodology["verdict_adjudication"]["method"] == "Not run for this article"

    # Real reliability-scoring step present, described as a weighted sum.
    assert "reliability_scoring" in resp.methodology
    assert "weighted sum" in resp.methodology["reliability_scoring"]["method"].lower()

    # Reliability breakdown = the 3 REAL headline components, NOT CARF factors
    # (model_confidence / cross_reference_score / temporal_relevance).
    assert set(resp.reliability_breakdown.keys()) == {
        "source_credibility",
        "verified_claims",
        "content_relevance",
    }
    # Weights reconcile with the documented source .50 / claims .30 / relevance .20.
    assert resp.reliability_breakdown["source_credibility"]["weight"] == 0.50
    assert resp.reliability_breakdown["verified_claims"]["weight"] == 0.30
    assert resp.reliability_breakdown["content_relevance"]["weight"] == 0.20
    # 0 claims => the verified-claims factor scores 0 (no invented evidence).
    assert resp.reliability_breakdown["verified_claims"]["score"] == 0.0

    # No claims are listed for a 0-claim article.
    assert resp.claims == []


@pytest.mark.asyncio
async def test_transparency_methodology_reflects_real_provenance_model():
    prov = [
        {
            "extraction_method": "article_ingestion_enrichment",
            "model_name": "qwen2.5:7b-instruct/local-gx10",
            "prompt_name": "claim_extraction",
            "prompt_version": "v1.2",
            "prompt_fingerprint": "abcdef0123456789",
            "retrieval_strategy": None,
            "created_at": "2026-06-30T00:00:00",
        }
    ]
    db = _TransparencyFakeDB(
        _article_row(claims_count=3),
        provenance_rows=prov,
        fc_counts={
            "verified_count": 2,
            "false_count": 0,
            "misleading_count": 0,
            "adjudicated_count": 3,
        },
    )
    resp = await get_article_transparency("art-xyz", db=db)

    ce = resp.methodology["claim_extraction"]
    # Real enrichment model surfaced, not the fabricated Claude/DeepSeek label.
    assert ce["model"] == "qwen2.5:7b-instruct/local-gx10"
    assert "claim_extraction" in ce["description"]  # real prompt name surfaced
    assert "Claude 3.5" not in json.dumps(resp.methodology)

    # Verdict adjudication ran (3 claims fact-checked) — not marked "not run".
    assert resp.methodology["verdict_adjudication"]["method"] != "Not run for this article"
