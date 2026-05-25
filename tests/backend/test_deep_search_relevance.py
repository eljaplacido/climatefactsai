"""Deep-search relevance guardrails — Slovenian-noise bug repro (2026-05-25).

User reported: asking Deep Search to compare "India extreme heat 2025
trends" vs "India heatwaves 2015-2020" returned three articles from a
Slovenian news outlet covering celebrity news, government dietary
guidelines, and political statements. All three had zero topical
relevance to India or heatwaves.

Root cause: `_search_internal_corpus` had NO minimum cosine-similarity
threshold and the downstream `_filter_results_by_query_relevance` gate
accepted articles at `overlap >= 0.1 OR rel_score >= 0.2` — permissive
enough to let stop-word matches survive. These tests pin both fences.
"""

from __future__ import annotations

import pytest

from app.domains.intelligence.deep_search_service import DeepSearchService


# ---------------------------------------------------------------------------
# Threshold constants exposed for callers + sanity-checked by tests.
# ---------------------------------------------------------------------------


class TestThresholdConstants:
    def test_min_semantic_similarity_is_strict_enough(self):
        # Cosine similarity is in [0,1] for our normalised embeddings.
        # Below 0.55 the top-k returns are essentially random for our corpus.
        assert DeepSearchService.MIN_SEMANTIC_SIMILARITY >= 0.55
        assert DeepSearchService.MIN_SEMANTIC_SIMILARITY <= 0.85

    def test_min_fts_rank_is_set(self):
        assert DeepSearchService.MIN_FTS_RANK > 0
        assert DeepSearchService.MIN_FTS_RANK < 1.0


# ---------------------------------------------------------------------------
# _filter_results_by_query_relevance — the in-Python guardrail.
# ---------------------------------------------------------------------------


def _art(title: str, excerpt: str = "", category: str = "", rel: float = 0.0):
    return {
        "title": title,
        "excerpt": excerpt,
        "content_category": category,
        "relevance_score": rel,
    }


class TestQueryRelevanceGuardrail:
    """Replays the Slovenian-celebrity bug and pins the new thresholds."""

    def test_slovenian_celebrity_article_rejected_for_india_query(self):
        """The bug repro: 'Konec ljubezni med Majo Šuput in Šimetom Elezom'
        (Slovenian celebrity break-up news) MUST NOT survive a query
        about Indian heatwaves regardless of how it ranked numerically."""
        results = [
            _art(
                title="Konec ljubezni med Majo Šuput in Šimetom Elezom",
                excerpt="Slovenian celebrity break-up coverage with no climate content.",
                category="entertainment",
                rel=0.18,  # would have passed old `rel_score >= 0.2` if bumped slightly
            ),
        ]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "India extreme heat 2025 trends", results
        )
        assert kept == [], (
            "Slovenian celebrity article must NOT survive an India heatwave "
            "query — this is the exact trust bug the user reported"
        )

    def test_lexical_only_match_below_threshold_rejected(self):
        """Old gate accepted overlap >= 0.1 (1 of 10 terms). New gate
        requires >= 0.25 (~1 of 4) OR strong semantic. 1 marginal term
        out of a 5-term query (0.2 overlap) should now be REJECTED."""
        results = [
            # Query has 5 terms; this article only contains "2025" — 0.2 overlap.
            _art(
                title="Politics in 2025 — Slovenian elections",
                excerpt="Domestic politics coverage.",
                rel=0.1,
            ),
        ]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "India extreme heat 2025 trends", results
        )
        assert kept == [], (
            f"Article with overlap=0.2 (below 0.25) and rel=0.1 (below 0.5) "
            f"must be rejected; got {kept}"
        )

    def test_strong_lexical_match_survives(self):
        """An article that has most query terms in its title clearly belongs."""
        results = [
            _art(
                title="India 2025 heatwave: extreme heat records broken in Delhi",
                excerpt="Reuters analysis of unprecedented temperature trends.",
                rel=0.62,
            ),
        ]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "India extreme heat 2025 trends", results
        )
        assert len(kept) == 1
        assert "India 2025 heatwave" in kept[0]["title"]

    def test_high_semantic_rescues_low_lexical_overlap(self):
        """Synonym-heavy articles ('warming' instead of 'heat', 'Bharat'
        instead of 'India') may have weak lexical overlap but strong
        embedding similarity. They should survive via the rescue branch."""
        results = [
            _art(
                title="Bharat sweltering: record temperatures grip subcontinent",
                excerpt="Mercury soars across northern plains amid climate warming.",
                rel=0.72,  # strong semantic match
            ),
        ]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "India extreme heat 2025 trends", results
        )
        assert len(kept) == 1, "Strong semantic similarity must rescue synonym-heavy match"

    def test_empty_query_terms_returns_unchanged(self):
        """Edge case: all-stopword query returns the input unchanged
        rather than dropping everything."""
        results = [_art(title="Whatever", rel=0.05)]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "the and for", results  # all stopwords
        )
        assert kept == results

    def test_mixed_batch_keeps_only_relevant(self):
        """Realistic mixed-result scenario: 2 relevant + 3 noise."""
        results = [
            _art(  # Strong match — KEEP
                title="India heat dome 2025: scientists warn of new records",
                rel=0.71,
            ),
            _art(  # Weak match (only '2025') — REJECT
                title="Slovenia 2025 budget passes parliament",
                rel=0.11,
            ),
            _art(  # Strong semantic, lexical synonyms — KEEP
                title="Subcontinent swelters under record warming",
                rel=0.66,
            ),
            _art(  # Pure noise — REJECT
                title="Celebrity gossip column from Ljubljana",
                rel=0.04,
            ),
            _art(  # Weak match in excerpt only — REJECT
                title="Auto sales report",
                excerpt="Heat-related delays in shipping",
                rel=0.18,
            ),
        ]
        kept = DeepSearchService._filter_results_by_query_relevance(
            "India extreme heat 2025 trends", results
        )
        titles = [a["title"] for a in kept]
        assert "India heat dome 2025: scientists warn of new records" in titles
        assert "Subcontinent swelters under record warming" in titles
        assert len(kept) == 2, f"Expected 2 kept, got {len(kept)}: {titles}"
