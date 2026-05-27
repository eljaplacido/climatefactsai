"""Unit tests for app.domains.content.sdg — Stage 6 / M7."""

from __future__ import annotations

import pytest

from app.domains.content.sdg import (
    SDG_GOALS,
    SDG_BY_ID,
    SDG_KEYWORDS,
    tag_text,
    tag_to_goal_ids,
)


class TestTaxonomy:
    def test_seventeen_goals_present(self):
        assert len(SDG_GOALS) == 17
        ids = {g["id"] for g in SDG_GOALS}
        assert ids == set(range(1, 18))

    def test_every_goal_has_keywords(self):
        for gid in range(1, 18):
            assert gid in SDG_KEYWORDS, f"SDG {gid} missing from SDG_KEYWORDS"
            assert len(SDG_KEYWORDS[gid]) > 0, f"SDG {gid} has empty keyword list"

    def test_climate_goal_is_13(self):
        assert SDG_BY_ID[13]["title"] == "Climate Action"


class TestTagger:
    def test_climate_text_tags_13(self):
        text = "The IPCC AR6 report highlights global warming and net-zero pathways."
        results = tag_text(text)
        ids = [r["goal_id"] for r in results]
        assert 13 in ids
        # SDG 13 should rank highly given multiple matches
        top = next(r for r in results if r["goal_id"] == 13)
        assert top["matched_count"] >= 3

    def test_energy_text_tags_7(self):
        text = "Solar and wind capacity grew, with battery storage scaling for off-grid villages."
        ids = tag_to_goal_ids(text)
        assert 7 in ids

    def test_water_text_tags_6(self):
        text = "Drought conditions in the river basin pushed the watershed below safe yield."
        ids = tag_to_goal_ids(text)
        assert 6 in ids

    def test_forest_text_tags_15(self):
        # Text emphasises forest/biodiversity — should tag SDG 15.
        # No explicit climate keywords (climate, carbon, emission, etc.)
        # so don't assert SDG 13 here; biodiversity ≠ guaranteed climate
        # by the tagger's keyword set.
        text = "Deforestation accelerated in the Amazon, threatening biodiversity and species conservation."
        ids = tag_to_goal_ids(text)
        assert 15 in ids

    def test_word_boundary_does_not_match_forestalia(self):
        """Substring 'deforest' must not match 'Forestalia' — same bug
        the Stage-1 review caught in the daemon selection gate."""
        text = "The Forestalia case involves Spanish government officials."
        ids = tag_to_goal_ids(text)
        # 'forest' bare word isn't a keyword, but 'deforest' is — and
        # it shouldn't substring-match 'Forestalia'.
        # So SDG 15 should NOT appear from this text alone.
        assert 15 not in ids or len(ids) == 0

    def test_empty_text_returns_nothing(self):
        assert tag_text("") == []
        assert tag_to_goal_ids("") == []

    def test_results_sorted_by_match_strength(self):
        text = (
            "Carbon emissions, renewable energy, solar, wind, geothermal, "
            "biomass, climate mitigation, net-zero, paris agreement, ipcc, cop30, "
            "loss and damage, carbon market, sbti"
        )
        results = tag_text(text)
        # Should be sorted by matched_count DESC
        counts = [r["matched_count"] for r in results]
        assert counts == sorted(counts, reverse=True)

    def test_multi_label_climate_and_forest(self):
        text = (
            "The Amazon rainforest absorbs 25% of global CO2 emissions. "
            "Deforestation in Brazil threatens climate goals."
        )
        ids = tag_to_goal_ids(text)
        assert 13 in ids and 15 in ids

    def test_min_match_count_filter(self):
        text = "Net zero climate action."  # several SDG-13 keywords
        ids_all = tag_to_goal_ids(text, min_match_count=1)
        ids_strict = tag_to_goal_ids(text, min_match_count=10)
        assert 13 in ids_all
        # No SDG has 10+ matches in 4 words
        assert ids_strict == []
