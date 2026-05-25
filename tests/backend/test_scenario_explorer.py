"""Scenario explorer — interpolation math + disclaimer pinning (deferred #14).

The whole-pipeline ScenarioExploreResponse is route-level glue tested
in CI; here we pin the pure-function _interpolate logic that drives
the math, plus the disclaimer text that's the user-facing trust
contract ("interpolation, not simulation").
"""

from __future__ import annotations

import pytest

from api.scenario_routes import (
    _interpolate,
    ScenarioBracket,
    _DISCLAIMER,
    _METHODOLOGY,
)


def _bracket(scenario: str, t: float) -> ScenarioBracket:
    return ScenarioBracket(scenario=scenario, temp_anomaly_c=t)


# ---------------------------------------------------------------------------
# Disclaimer + methodology — these are the user-facing trust contract.
# Any rewording must come with a deliberate ADR.
# ---------------------------------------------------------------------------


class TestDisclaimer:
    def test_disclaimer_explicitly_says_not_simulation(self):
        text = _DISCLAIMER.lower()
        assert "interpolation" in text
        assert "not simulation" in text
        assert "tipping" in text  # warns about non-linear feedbacks

    def test_methodology_calls_out_ipcc_ar6(self):
        text = _METHODOLOGY.lower()
        assert "ipcc ar6" in text
        assert "linear interpolation" in text
        assert "do not run a climate model" in text


# ---------------------------------------------------------------------------
# _interpolate — exact / lerp / extrapolation branches.
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_exact_match_returns_that_bracket(self):
        brackets = [
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP2-4.5", 2.7),
            _bracket("SSP3-7.0", 4.4),
        ]
        anomaly, method, returned = _interpolate(2.7, brackets)
        assert method == "exact"
        assert anomaly == 2.7
        assert len(returned) == 1
        assert returned[0].scenario == "SSP2-4.5"

    def test_exact_match_within_tolerance(self):
        """0.01°C tolerance — guards against float-equality flakiness."""
        brackets = [_bracket("SSP2-4.5", 2.70)]
        anomaly, method, returned = _interpolate(2.705, brackets)
        assert method == "exact"


class TestInterpolation:
    def test_target_between_two_ssps_lerps(self):
        brackets = [
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP2-4.5", 2.7),
            _bracket("SSP3-7.0", 4.4),
        ]
        anomaly, method, returned = _interpolate(2.0, brackets)
        assert method == "interpolated"
        # Returns the target itself (the lerp value IS what was asked for).
        assert anomaly == 2.0
        # Returns the two bracketing scenarios sorted ascending.
        assert [b.scenario for b in returned] == ["SSP1-2.6", "SSP2-4.5"]

    def test_target_in_upper_bracket(self):
        brackets = [
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP2-4.5", 2.7),
            _bracket("SSP3-7.0", 4.4),
        ]
        anomaly, method, returned = _interpolate(3.5, brackets)
        assert method == "interpolated"
        assert anomaly == 3.5
        assert [b.scenario for b in returned] == ["SSP2-4.5", "SSP3-7.0"]


class TestExtrapolation:
    def test_target_below_lowest_clamps(self):
        brackets = [
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP2-4.5", 2.7),
        ]
        anomaly, method, returned = _interpolate(0.8, brackets)
        assert method == "extrapolated_below"
        # Clamps to the lowest available, doesn't invent.
        assert anomaly == 1.5
        assert len(returned) == 1
        assert returned[0].scenario == "SSP1-2.6"

    def test_target_above_highest_clamps(self):
        brackets = [
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP3-7.0", 4.4),
        ]
        anomaly, method, returned = _interpolate(6.0, brackets)
        assert method == "extrapolated_above"
        assert anomaly == 4.4
        assert returned[0].scenario == "SSP3-7.0"


class TestEdgeCases:
    def test_single_bracket_only(self):
        """Some countries have only one SSP scenario populated."""
        brackets = [_bracket("SSP2-4.5", 2.7)]
        # Exact match works.
        anomaly, method, _ = _interpolate(2.7, brackets)
        assert method == "exact"
        # Below clamps.
        anomaly, method, _ = _interpolate(1.0, brackets)
        assert method == "extrapolated_below"
        assert anomaly == 2.7
        # Above clamps.
        anomaly, method, _ = _interpolate(5.0, brackets)
        assert method == "extrapolated_above"
        assert anomaly == 2.7

    def test_unsorted_brackets_still_work(self):
        """The function sorts internally — caller doesn't need to."""
        brackets = [
            _bracket("SSP3-7.0", 4.4),
            _bracket("SSP1-2.6", 1.5),
            _bracket("SSP2-4.5", 2.7),
        ]
        _, method, returned = _interpolate(2.0, brackets)
        assert method == "interpolated"
        assert [b.scenario for b in returned] == ["SSP1-2.6", "SSP2-4.5"]
