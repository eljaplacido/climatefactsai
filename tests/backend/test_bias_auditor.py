"""Chi-squared bias auditor — math + interpretation pin tests.

TruthMachine strategy report Section III: "Implement a chi-squared
test over claim-type and verdict counts to provide a defensible check
against ideological skew that the source mix might inherit."

These tests pin the math (against textbook examples) + the alarm
behaviour (only fires when independence is genuinely rejected at
alpha=0.05). No DB hit — uses the pure-function chi_squared_test
helper directly.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.domains.intelligence.bias_auditor import (
    chi_squared_test,
    CHI2_CRITICAL_ALPHA_05,
)


class TestChiSquaredMath:
    """Textbook examples — verify chi² + Cramér's V to 2 decimal places."""

    def test_independent_variables_no_rejection(self):
        """Perfectly independent 2x2: chi² ≈ 0, no rejection."""
        # 100 cells, perfectly uniform across both rows and columns
        table = np.array([[25, 25], [25, 25]])
        result = chi_squared_test(table)
        assert result["chi2"] == 0.0
        assert result["reject_independence"] is False
        assert result["cramer_v"] == 0.0

    def test_perfect_dependence_strong_rejection(self):
        """Perfectly dependent 2x2: large chi², Cramér's V close to 1."""
        # All weight on diagonal — type A always gets verdict X, type B always Y.
        table = np.array([[100, 0], [0, 100]])
        result = chi_squared_test(table)
        # Chi² = N * (V²) * (k-1) where V=1 for perfect dependence: 200 * 1 * 1 = 200
        assert result["chi2"] >= 100  # well above critical=3.841 for df=1
        assert result["reject_independence"] is True
        assert result["cramer_v"] > 0.9

    def test_known_2x2_textbook(self):
        """Pearson's classic smoking vs lung cancer example —
        scaled to our domain: claim_type=offset vs other; verdict=flagged vs not."""
        # 50 offset claims: 40 flagged, 10 not
        # 50 other claims: 10 flagged, 40 not
        table = np.array([[40, 10], [10, 40]])
        result = chi_squared_test(table)
        # Expected if independent: 25 each cell. Chi² per cell: (15²)/25 = 9.
        # Total = 4 * 9 = 36. df=1, critical=3.841. Reject hard.
        assert abs(result["chi2"] - 36.0) < 0.1
        assert result["reject_independence"] is True
        # Cramér's V = sqrt(36/100/1) = 0.6 → strong association
        assert abs(result["cramer_v"] - 0.6) < 0.01

    def test_critical_value_lookup(self):
        """Pin the hardcoded critical values against the Pearson 1900 table."""
        assert CHI2_CRITICAL_ALPHA_05[1] == 3.841
        assert CHI2_CRITICAL_ALPHA_05[4] == 9.488
        assert CHI2_CRITICAL_ALPHA_05[16] == 26.296


class TestEdgeCases:
    def test_empty_table(self):
        table = np.array([[0, 0], [0, 0]])
        result = chi_squared_test(table)
        assert result["n"] == 0
        assert result["reject_independence"] is False
        assert "Empty contingency table" in " ".join(result["notes"])

    def test_single_row_too_small(self):
        table = np.array([[10, 20, 30]])
        result = chi_squared_test(table)
        assert result["reject_independence"] is False
        # Should note the shape issue.
        assert any("shape" in n.lower() for n in result["notes"])

    def test_sparse_cells_flagged(self):
        """When expected counts are <5, chi² approximation is unreliable.
        The auditor MUST flag this so callers don't trust the verdict."""
        # 5-row table where one row has very few observations.
        table = np.array([
            [100, 100, 100],
            [1, 1, 1],
            [100, 100, 100],
        ])
        result = chi_squared_test(table)
        notes_text = " ".join(result["notes"]).lower()
        assert "min expected" in notes_text or "sparse" in notes_text

    def test_2d_shape_required(self):
        with pytest.raises(ValueError):
            chi_squared_test(np.array([1, 2, 3]))


class TestRealistic:
    """Realistic mid-size tables — confirm the test gives sensible answers."""

    def test_moderate_bias_correctly_flagged(self):
        # 4 claim types × 3 verdicts, mild but consistent bias on type 0.
        # All types have 100 claims, but type 0 gets 60% verified (vs 33% baseline).
        table = np.array([
            [60, 30, 10],  # type 0: skewed verified
            [30, 35, 35],
            [35, 30, 35],
            [30, 35, 35],
        ])
        result = chi_squared_test(table)
        assert result["reject_independence"] is True
        assert 0.1 < result["cramer_v"] < 0.5  # moderate effect

    def test_balanced_corpus_no_flag(self):
        # 4 claim types × 3 verdicts, balanced ~equally — should NOT reject.
        table = np.array([
            [40, 30, 30],
            [33, 34, 33],
            [35, 32, 33],
            [32, 34, 34],
        ])
        result = chi_squared_test(table)
        assert result["reject_independence"] is False
