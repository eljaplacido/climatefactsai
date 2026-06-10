"""Numeric grounding tests — Phase 8 B4 MVP (2026-05-24).

Pins the pure-function contract of `extract_numbers` and
`check_numeric_grounding`. These functions are a defence-in-depth layer
against single-LLM numeric hallucination — a regression here means a claim
like "1.5°C warming" silently grades as grounded when the evidence
actually said "1.6°C". That's exactly the failure mode the layer exists
to catch, so the tests are exhaustive.
"""

from __future__ import annotations

import math

import pytest

from app.domains.intelligence.numeric_grounding import (
    GroundingResult,
    NumericToken,
    check_numeric_grounding,
    check_numeric_grounding_against_indicators,
    extract_numbers,
    grounding_score,
)


# ---------------------------------------------------------------------------
# extract_numbers
# ---------------------------------------------------------------------------


class TestExtractNumbersBasics:
    def test_empty_string_returns_empty_list(self):
        assert extract_numbers("") == []

    def test_no_numbers_returns_empty_list(self):
        assert extract_numbers("The climate is changing.") == []

    def test_single_plain_integer(self):
        tokens = extract_numbers("There are 42 countries.")
        assert len(tokens) == 1
        assert tokens[0].value == 42.0
        assert tokens[0].unit is None
        assert tokens[0].raw == "42"

    def test_single_decimal(self):
        tokens = extract_numbers("Anomaly is 1.5 above baseline.")
        assert len(tokens) == 1
        assert tokens[0].value == 1.5
        # No explicit unit
        assert tokens[0].unit is None

    def test_negative_number(self):
        tokens = extract_numbers("Cooling of -2.3 observed.")
        assert len(tokens) == 1
        assert tokens[0].value == -2.3

    def test_thousand_separator(self):
        tokens = extract_numbers("Population grew to 1,234,567 last year.")
        assert len(tokens) == 1
        assert tokens[0].value == 1234567.0
        assert tokens[0].raw == "1,234,567"

    def test_multiple_numbers_in_order(self):
        tokens = extract_numbers("Reduced 40% by 2030 from 1990 levels.")
        # Three numbers: 40, 2030, 1990
        assert len(tokens) == 3
        assert tokens[0].value == 40.0
        assert tokens[0].unit == "%"
        assert tokens[1].value == 2030.0
        assert tokens[2].value == 1990.0


class TestExtractNumbersUnits:
    @pytest.mark.parametrize("text,expected_unit", [
        ("Warming of 1.5°C", "°C"),
        ("Warming of 1.5 °C", "°C"),
        ("1.5 degrees Celsius warming", "°C"),
        ("Concentration reached 420 ppm", "ppm"),
        ("Concentration reached 420 PPM", "ppm"),
        ("Emissions cut 40%", "%"),
        ("Emissions cut 40 percent", "%"),
        ("Emissions cut 40 per cent", "%"),
        ("Total of 51 GtCO2e", "GtCO2e"),
        ("Total of 51 gigatonnes", "Gt"),
        ("Total of 51 tonnes", "t"),
        ("Solar grew to 1500 TWh", "TWh"),
        ("Sea level rise of 23 mm", "mm"),
        ("Sea level rise of 4 cm", "cm"),
        ("Investment of $5 billion dollars", "USD-bn"),
        ("Plain 5 billion units", "bn"),
    ])
    def test_unit_detection(self, text, expected_unit):
        tokens = extract_numbers(text)
        assert len(tokens) >= 1
        assert tokens[0].unit == expected_unit

    def test_no_unit_for_bare_number(self):
        tokens = extract_numbers("There are 195 countries in the world.")
        assert tokens[0].unit is None


class TestExtractNumbersEdgeCases:
    def test_does_not_extract_from_inside_word(self):
        """Avoid grabbing the '5' out of 'iPhone15'."""
        tokens = extract_numbers("Use the iPhone15 app.")
        # iPhone15 should NOT yield a token — '15' is preceded by a word char
        assert tokens == []

    def test_does_not_double_match_decimal_dot(self):
        tokens = extract_numbers("Reading: 3.14 and 2.71.")
        assert len(tokens) == 2
        assert tokens[0].value == 3.14
        assert tokens[1].value == 2.71

    def test_year_is_extracted_as_plain_number(self):
        tokens = extract_numbers("By 2050 we will...")
        assert len(tokens) == 1
        assert tokens[0].value == 2050.0
        assert tokens[0].unit is None

    def test_consecutive_numbers_separated_by_punct(self):
        tokens = extract_numbers("From 1.5°C to 2.0°C")
        assert len(tokens) == 2
        assert (tokens[0].value, tokens[0].unit) == (1.5, "°C")
        assert (tokens[1].value, tokens[1].unit) == (2.0, "°C")


# ---------------------------------------------------------------------------
# check_numeric_grounding
# ---------------------------------------------------------------------------


class TestGroundingExactMatch:
    def test_perfect_match_grounds(self):
        r = check_numeric_grounding(
            "Warming of 1.5°C by 2030",
            "The study reports 1.5°C of warming by 2030.",
        )
        assert r.grounded is True
        assert r.grounding_score == 1.0
        assert len(r.ungrounded_tokens) == 0

    def test_no_numbers_in_claim_is_vacuously_grounded(self):
        """A claim with no numbers can't be ungrounded by definition."""
        r = check_numeric_grounding(
            "Climate change is happening.",
            "Evidence with no numbers either.",
        )
        assert r.grounded is True
        assert r.grounding_score == 1.0
        assert r.claim_token_count == 0

    def test_empty_evidence_with_claim_numbers_fails(self):
        r = check_numeric_grounding("Warming of 1.5°C", "")
        assert r.grounded is False
        assert r.grounding_score == 0.0
        assert len(r.ungrounded_tokens) == 1


class TestGroundingTolerance:
    def test_within_default_tolerance_grounds(self):
        """Default 1% tolerance — 1.5°C matches 1.51°C."""
        r = check_numeric_grounding(
            "Warming of 1.5°C",
            "Study reports 1.51°C warming",
        )
        assert r.grounded is True

    def test_just_outside_default_tolerance_fails(self):
        """1.5 vs 1.6 is ~6.7% off → fails 1% tolerance."""
        r = check_numeric_grounding(
            "Warming of 1.5°C",
            "Study reports 1.6°C warming",
        )
        assert r.grounded is False
        assert r.grounding_score == 0.0

    def test_explicit_loose_tolerance_grounds_wider(self):
        """Caller can relax tolerance to 10% if they want approximate."""
        r = check_numeric_grounding(
            "Warming of 1.5°C",
            "Study reports 1.6°C warming",
            tolerance=0.10,
        )
        assert r.grounded is True


class TestGroundingPartialMatches:
    def test_two_of_three_grounded_is_partial(self):
        r = check_numeric_grounding(
            "Cut 40% by 2030 from 1990 levels",
            "Targets a 40% reduction from 1990, by some unspecified date.",
        )
        # Claim has 3 numbers (40, 2030, 1990)
        # Evidence covers 40 and 1990 but not 2030
        assert r.claim_token_count == 3
        assert r.grounding_score == pytest.approx(2 / 3, abs=1e-6)
        assert r.grounded is False
        assert any(t.value == 2030.0 for t in r.ungrounded_tokens)

    def test_grounded_and_ungrounded_lists_partition_claim_tokens(self):
        r = check_numeric_grounding(
            "Earth warmed 1.5°C while CO2 hit 420 ppm",
            "The 1.5°C figure is widely cited. Other concentrations vary.",
        )
        # 1.5 grounded, 420 not grounded
        assert len(r.grounded_tokens) + len(r.ungrounded_tokens) == r.claim_token_count
        grounded_values = {t.value for t in r.grounded_tokens}
        ungrounded_values = {t.value for t in r.ungrounded_tokens}
        assert grounded_values.isdisjoint(ungrounded_values)


class TestGroundingUnitDiscipline:
    def test_same_value_different_unit_does_not_ground(self):
        """Catches "5 GtCO2e" vs "5%" — same number, wrong unit, wrong claim."""
        r = check_numeric_grounding(
            "Emissions of 5 GtCO2e",
            "Reductions of 5%",
        )
        assert r.grounded is False

    def test_unitless_claim_grounds_against_unitful_evidence(self):
        """Permissive MVP behaviour — claim "1.5" grounds against
        evidence "1.5°C". This is the conservative default; we err on
        the side of false negatives over false positives at the
        grounding-check layer."""
        r = check_numeric_grounding(
            "The figure is 1.5",
            "Warming of 1.5°C observed",
        )
        assert r.grounded is True


class TestGroundingScoreHelper:
    def test_scalar_helper_returns_same_score(self):
        assert grounding_score("40%", "40% reduction reported") == 1.0
        assert grounding_score("60%", "40% reduction reported") == 0.0

    def test_scalar_helper_no_numbers_is_one(self):
        assert grounding_score("text only", "text only") == 1.0


class TestGroundingAgainstIndicators:
    """Audit item 5: ground a claim's numbers against REAL measured values
    (country_indicators rows), not the article's own prose."""

    def test_number_matching_a_real_indicator_is_grounded(self):
        # Claim cites 4.2 tCO2e; the country's real per-capita figure is 4.21.
        r = check_numeric_grounding_against_indicators(
            "Per-capita emissions are 4.2 tCO2e",
            indicators=[(4.21, "tCO2e"), (62.0, "%")],
        )
        assert r.grounded is True
        assert r.grounding_score == 1.0

    def test_number_absent_from_indicators_is_ungrounded(self):
        # 99 matches no real indicator -> ungrounded.
        r = check_numeric_grounding_against_indicators(
            "Emissions are 99 tCO2e",
            indicators=[(4.2, "tCO2e"), (62.0, "%")],
        )
        assert r.grounded is False
        assert r.grounding_score == 0.0
        assert r.claim_token_count == 1

    def test_unit_discipline(self):
        # 62 with no unit matches the 62% indicator (claim left unit implicit),
        # but a 62 GtCO2e claim must NOT match a 62% indicator.
        assert check_numeric_grounding_against_indicators(
            "renewables reached 62", indicators=[(62.0, "%")],
        ).grounded is True
        assert check_numeric_grounding_against_indicators(
            "62 GtCO2e", indicators=[(62.0, "%")],
        ).grounded is False

    def test_no_numbers_is_vacuously_grounded(self):
        r = check_numeric_grounding_against_indicators(
            "Emissions are falling", indicators=[(4.2, "tCO2e")],
        )
        assert r.grounded is True
        assert r.claim_token_count == 0

    def test_empty_indicators_ungrounds_numeric_claim(self):
        r = check_numeric_grounding_against_indicators(
            "Emissions are 4.2 tCO2e", indicators=[],
        )
        assert r.grounded is False


class TestGroundingResultShape:
    def test_returns_grounding_result_dataclass(self):
        r = check_numeric_grounding("1.5°C", "1.5°C")
        assert isinstance(r, GroundingResult)
        assert r.grounded is True
        assert isinstance(r.grounded_tokens, tuple)
        assert isinstance(r.ungrounded_tokens, tuple)

    def test_grounding_score_is_finite(self):
        r = check_numeric_grounding(
            "Multiple 5 numbers 10 here 15 and 20 too",
            "Only 5 and 10 are in evidence",
        )
        assert math.isfinite(r.grounding_score)
        assert 0.0 <= r.grounding_score <= 1.0
