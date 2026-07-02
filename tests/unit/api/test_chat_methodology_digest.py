"""ML-07 regression: the chat must not confabulate how scores/layers work.

Live, the assistant described the map's Climate Risk layer as a
"hazard/sensitivity/adaptive-capacity composite (GDP, disaster records)" when it
is a single IPCC AR6 SSP2-4.5 projected-2050-warming number. The fix injects a
machine-generated methodology digest (sourced from the live warming-risk
constants) into the VOLATILE user block and adds a static methodology-honesty
instruction to the cached system prefix.

These tests pin: (a) the digest content, (b) that the digest DATA stays out of
the cache-eligible system prefix, and (c) a confabulation guard that flags a
Climate-Risk explanation invoking vulnerability/sensitivity/adaptive-capacity/GDP.
"""

from __future__ import annotations

from api.chat_routes import (
    _chat_system_prompt,
    _methodology_digest,
    flag_climate_risk_confabulation,
)


class TestMethodologyDigest:
    def test_digest_states_climate_risk_is_projected_warming(self):
        d = _methodology_digest().lower()
        assert "climate risk" in d
        # Sourced from the live warming-risk constants — can't drift from code.
        from api.map.services import (
            WARMING_RISK_SCENARIO,
            WARMING_RISK_HORIZON_YEAR,
        )
        assert WARMING_RISK_SCENARIO.lower() in d
        assert str(WARMING_RISK_HORIZON_YEAR) in d

    def test_digest_disclaims_the_wrong_factors(self):
        d = _methodology_digest().lower()
        # The wrong factors are named ONLY to negate them, and the digest says so.
        assert "not" in d
        for wrong in ("vulnerability", "gdp", "article volume"):
            assert wrong in d

    def test_digest_covers_scores_and_tiers(self):
        d = _methodology_digest().lower()
        assert "reliability score" in d
        assert "credibility tier" in d
        assert "t1" in d and "t2" in d

    def test_digest_is_cached_singleton(self):
        assert _methodology_digest() is _methodology_digest()


class TestSystemPromptMethodologyInstruction:
    def test_system_prompt_carries_methodology_honesty(self):
        s = _chat_system_prompt().lower()
        assert "methodology" in s
        assert "climate risk" in s
        assert "open_methodology_section" in s

    def test_digest_body_stays_out_of_cached_prefix(self):
        # The always-current digest DATA must live in the volatile user block so
        # the cached system prefix stays byte-frozen (Headroom CacheAligner).
        s = _chat_system_prompt()
        assert _methodology_digest() not in s
        # A digest-only token (a layer the instruction never names) must be absent.
        assert "Köppen" not in s
        assert "ND-GAIN" not in s

    def test_system_prompt_has_no_volatile_markers(self):
        s = _chat_system_prompt()
        for marker in (
            "PLATFORM SNAPSHOT",
            "CURRENT VIEW",
            "USER QUESTION",
            "RELEVANT ARTICLES FROM DATABASE",
        ):
            assert marker not in s


class TestClimateRiskConfabulationGuard:
    def test_flags_a_confabulated_climate_risk_explanation(self):
        bad = (
            "The Climate Risk score is a composite of hazard, sensitivity, and "
            "adaptive capacity, weighted by GDP and historical disaster records."
        )
        flags = flag_climate_risk_confabulation(bad)
        assert "sensitivity" in flags
        assert "adaptive capacity" in flags
        assert "gdp" in flags

    def test_passes_a_correct_climate_risk_explanation(self):
        good = (
            "The Climate Risk layer is IPCC AR6 SSP2-4.5 projected warming at 2050, "
            "scaled 1.5C to 0 and 5.0C to 10. It is not a vulnerability or GDP composite."
        )
        assert flag_climate_risk_confabulation(good) == []

    def test_ignores_text_not_about_climate_risk(self):
        other = "The Adaptation Gap uses ND-GAIN vulnerability and readiness sub-scores."
        assert flag_climate_risk_confabulation(other) == []

    def test_empty_answer_is_not_flagged(self):
        assert flag_climate_risk_confabulation("") == []
