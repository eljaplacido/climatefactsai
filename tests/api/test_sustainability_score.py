"""Sustainability score formula tests (Phase 3 wave 3).

Pins every component of the formula:
- Normalisation curves at boundary values
- Composite computation with 1/2/3 components
- Weight redistribution when components are missing
- Confidence-band sizing by indicators_used count
- Edge cases (None values, non-numeric values, empty inputs)
- methodology_version + methodology_url surfaced

The formula is deliberately simple — these tests are the explicit
documentation of what "sustainability_score 73" means, so future formula
revisions can be reviewed against pinned expected values.
"""

from __future__ import annotations

import pytest

from app.domains.intelligence.sustainability_score import (
    COMPONENTS,
    METHODOLOGY_VERSION,
    METHODOLOGY_URL,
    compute_sustainability_score,
    confidence_band_for,
    normalize_cat_rating,
    normalize_emissions_per_capita,
    normalize_renewable_share,
)


# ---------------------------------------------------------------------------
# Normalisation curves
# ---------------------------------------------------------------------------

class TestNormalizeEmissionsPerCapita:
    """Linear 0–20 tCO2e → 100–0, clamped."""

    @pytest.mark.parametrize("tco2e,expected", [
        (0.0, 100.0),
        (5.0, 75.0),
        (10.0, 50.0),
        (14.0, 30.0),  # USA-ish
        (20.0, 0.0),
        # Clamping
        (25.0, 0.0),
        (100.0, 0.0),
        (-5.0, 100.0),
    ])
    def test_boundary_values(self, tco2e, expected):
        assert normalize_emissions_per_capita(tco2e) == pytest.approx(expected, rel=1e-6)

    def test_none_raises(self):
        with pytest.raises(ValueError):
            normalize_emissions_per_capita(None)  # type: ignore[arg-type]


class TestNormalizeRenewableShare:
    """Already 0–100; pass through with clamp."""

    @pytest.mark.parametrize("pct,expected", [
        (0.0, 0.0),
        (35.0, 35.0),
        (50.0, 50.0),
        (100.0, 100.0),
        (110.0, 100.0),
        (-10.0, 0.0),
    ])
    def test_boundary_values(self, pct, expected):
        assert normalize_renewable_share(pct) == pytest.approx(expected, rel=1e-6)


class TestNormalizeCatRating:
    """Already 0–100; pass through with clamp."""

    def test_clamp_high(self):
        assert normalize_cat_rating(150.0) == 100.0

    def test_clamp_low(self):
        assert normalize_cat_rating(-20.0) == 0.0

    def test_passthrough(self):
        assert normalize_cat_rating(65.0) == 65.0


# ---------------------------------------------------------------------------
# Confidence band table
# ---------------------------------------------------------------------------

class TestConfidenceBand:
    @pytest.mark.parametrize("n,expected_band", [
        (0, 50.0),
        (1, 25.0),
        (2, 15.0),
        (3, 10.0),
        (5, 10.0),
    ])
    def test_band_size(self, n, expected_band):
        assert confidence_band_for(n) == expected_band


# ---------------------------------------------------------------------------
# Component definitions sanity
# ---------------------------------------------------------------------------

class TestComponentDefinitions:
    def test_weights_sum_to_one(self):
        total = sum(c.weight for c in COMPONENTS)
        assert total == pytest.approx(1.0)

    def test_methodology_version_pinned(self):
        assert METHODOLOGY_VERSION == "sustainability_v2_2026_05"

    def test_methodology_url_set(self):
        assert METHODOLOGY_URL.startswith("http")


# ---------------------------------------------------------------------------
# compute_sustainability_score — happy paths
# ---------------------------------------------------------------------------

def _ind(value, *, year=2022, unit="tCO2e/person", source="owid", url="https://example.org/x"):
    """Build a real_indicators-style dict entry."""
    return {
        "value": value,
        "unit": unit,
        "year": year,
        "source_name": source,
        "source_url": url,
    }


class TestComputeWithSingleComponent:
    def test_only_emissions(self):
        # USA-ish value at 14 tCO2e per capita.
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(14.0),
        })
        assert score is not None
        # 14 tCO2e → 30 normalised. Full weight goes to the only component.
        assert score.value == pytest.approx(30.0)
        assert score.indicators_used == 1
        assert score.indicators_available_in_formula == 5
        # Confidence band = ±25 for 1 indicator.
        assert score.confidence_band == 25.0
        assert score.confidence_low == pytest.approx(5.0)
        assert score.confidence_high == pytest.approx(55.0)
        # Only one component in the breakdown, with weight_applied == 1.0.
        assert len(score.components) == 1
        c = score.components[0]
        assert c.indicator_id == "emissions_tco2e_per_capita"
        assert c.weight_applied == pytest.approx(1.0)
        assert c.normalized_score == pytest.approx(30.0)
        assert c.raw_value == 14.0

    def test_only_renewable(self):
        score = compute_sustainability_score({
            "renewable_share_electricity_percent": _ind(85.0, unit="%"),
        })
        assert score is not None
        assert score.value == pytest.approx(85.0)
        assert score.indicators_used == 1
        assert score.confidence_band == 25.0
        assert score.confidence_low == pytest.approx(60.0)
        assert score.confidence_high == pytest.approx(100.0)  # clamped


class TestComputeWithTwoComponents:
    def test_emissions_and_renewable(self):
        # Germany-ish: 8 tCO2e/person, 46% renewable share.
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(8.0),
            "renewable_share_electricity_percent": _ind(46.0, unit="%"),
        })
        assert score is not None
        # emissions normalises to 60; renewable to 46.
        # Weights v2 (5 components): emissions=0.30, renewable=0.25.
        # Re-normalise across the two present: 0.30/0.55 and 0.25/0.55.
        # Composite = 60 * (0.30/0.55) + 46 * (0.25/0.55) = 32.73 + 20.91 = 53.64
        assert score.value == pytest.approx(53.64, abs=0.05)
        assert score.indicators_used == 2
        assert score.confidence_band == 15.0
        # confidence_low/high are derived as value ± band, so they shift with value.
        assert score.confidence_low == pytest.approx(38.64, abs=0.05)
        assert score.confidence_high == pytest.approx(68.64, abs=0.05)
        # Weights re-normalised: emissions=0.30/0.55, renewable=0.25/0.55.
        weights = {c.indicator_id: c.weight_applied for c in score.components}
        assert weights["emissions_tco2e_per_capita"] == pytest.approx(0.30 / 0.55)
        assert weights["renewable_share_electricity_percent"] == pytest.approx(0.25 / 0.55)

    def test_emissions_and_cat(self):
        # When CAT lands: 14 tCO2e (USA-ish) + CAT rating 30.
        # Weights v2 (5 components): emissions=0.30, cat=0.20.
        # Re-normalised across present-only components: 0.30/0.50 and 0.20/0.50.
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(14.0),
            "cat_overall_rating": _ind(30.0, unit="score (0–100)"),
        })
        assert score is not None
        # Both components normalise to 30, so composite stays 30 regardless of ratio.
        assert score.value == pytest.approx(30.0, abs=0.01)
        # Check the weight ratios.
        weights = {c.indicator_id: c.weight_applied for c in score.components}
        assert weights["emissions_tco2e_per_capita"] == pytest.approx(0.30 / 0.50)
        assert weights["cat_overall_rating"] == pytest.approx(0.20 / 0.50)


class TestComputeWithAllThreeComponents:
    def test_full_formula(self):
        # Hypothetical leading country: low emissions, high renewable, strong policy.
        # Weights v2 (5 components): 0.30, 0.25, 0.20, 0.15, 0.10 (sum 1.0).
        # Without ND-GAIN or NDC data, re-normalised across the three present components:
        # 0.30/0.75, 0.25/0.75, 0.20/0.75.
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(4.0),         # → 80
            "renewable_share_electricity_percent": _ind(70.0, unit="%"),
            "cat_overall_rating": _ind(75.0, unit="score (0–100)"),
        })
        assert score is not None
        # 80 * (0.30/0.75) + 70 * (0.25/0.75) + 75 * (0.20/0.75)
        # = 32.0 + 23.33 + 20.0 = 75.33
        assert score.value == pytest.approx(75.33, abs=0.05)
        assert score.indicators_used == 3
        assert score.confidence_band == 10.0  # tightest band (no year_spread in fixtures)

    def test_components_ordered_by_definition(self):
        """Components in output preserve the order of COMPONENTS definition."""
        score = compute_sustainability_score({
            "cat_overall_rating": _ind(50.0),
            "emissions_tco2e_per_capita": _ind(10.0),
            "renewable_share_electricity_percent": _ind(50.0),
        })
        assert score is not None
        order = [c.indicator_id for c in score.components]
        # COMPONENTS order is emissions, renewable, cat.
        assert order == [
            "emissions_tco2e_per_capita",
            "renewable_share_electricity_percent",
            "cat_overall_rating",
        ]


# ---------------------------------------------------------------------------
# compute_sustainability_score — edge cases
# ---------------------------------------------------------------------------

class TestComputeEdgeCases:
    def test_empty_input_returns_none(self):
        assert compute_sustainability_score({}) is None

    def test_no_matching_indicators_returns_none(self):
        # Indicator not in the formula's component list.
        assert compute_sustainability_score({
            "unrelated_made_up_indicator": _ind(60.0),
        }) is None

    def test_indicator_with_none_value_skipped(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(None),
            "renewable_share_electricity_percent": _ind(50.0),
        })
        assert score is not None
        # Only the renewable indicator contributes; weight 1.0.
        assert score.indicators_used == 1
        assert score.components[0].indicator_id == "renewable_share_electricity_percent"

    def test_indicator_with_non_numeric_value_skipped(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind("not-a-number"),
            "renewable_share_electricity_percent": _ind(50.0),
        })
        assert score is not None
        assert score.indicators_used == 1

    def test_extreme_emissions_clamped_at_zero(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(50.0),  # 2.5x worst case
        })
        assert score is not None
        assert score.value == 0.0
        assert score.confidence_low == 0.0  # clamped

    def test_perfect_score_clamped_at_hundred(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(0.0),
            "renewable_share_electricity_percent": _ind(100.0),
            "cat_overall_rating": _ind(100.0),
        })
        assert score is not None
        assert score.value == pytest.approx(100.0)
        assert score.confidence_high == 100.0  # clamped


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_as_dict_contains_methodology_disclosure(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(10.0),
        })
        assert score is not None
        out = score.as_dict()
        assert out["methodology_version"] == METHODOLOGY_VERSION
        assert out["methodology_url"] == METHODOLOGY_URL
        assert "formula_disclosure" in out
        assert "1 of 5 defined components" in out["formula_disclosure"]
        assert "sustainability_v2_2026_05" in out["formula_disclosure"]

    def test_component_contribution_includes_provenance(self):
        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _ind(
                12.0, year=2021, source="owid",
                url="https://example.org/co2-data.csv",
            ),
        })
        assert score is not None
        out = score.as_dict()
        c = out["components"][0]
        assert c["raw_value"] == 12.0
        assert c["year"] == 2021
        assert c["source_name"] == "owid"
        assert c["source_url"] == "https://example.org/co2-data.csv"
        assert c["unit"] == "tCO2e/person"


# ---------------------------------------------------------------------------
# Integration with the RealIndicatorValue Pydantic model
# (compute should also accept attribute-access objects, not just dicts)
# ---------------------------------------------------------------------------

class TestComputeWithPydanticLikeObjects:
    def test_accepts_objects_with_attribute_access(self):
        class _Obj:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        score = compute_sustainability_score({
            "emissions_tco2e_per_capita": _Obj(
                value=10.0, unit="tCO2e/person", year=2022,
                source_name="owid", source_url="https://x",
            ),
            "renewable_share_electricity_percent": _Obj(
                value=40.0, unit="%", year=2022,
                source_name="owid", source_url="https://y",
            ),
        })
        assert score is not None
        # 10 tCO2e → 50; 40% renewable → 40.
        # Weights v2 (5 components): emissions=0.30, renewable=0.25. Re-normalised
        # across the two present: 50 * (0.30/0.55) + 40 * (0.25/0.55) = 45.45.
        assert score.value == pytest.approx(45.45, abs=0.05)
