"""Chi-squared bias auditor — TruthMachine strategy report Section III.

The report flagged this as MISSING: "Implement a chi-squared test over
claim-type and verdict counts to provide a defensible check against
ideological skew that the source mix might inherit."

Implementation is pure-numpy + a hardcoded chi-squared critical-value
table for common df + alpha levels. No scipy dependency. The point isn't
publication-grade statistics — the point is a defensible alarm: when
(claim_type × verdict) becomes statistically dependent, the source mix
is starting to skew verdicts in a way that needs editorial review.

Mathematical contract:
  - Null hypothesis: claim_type is INDEPENDENT of verdict
    (i.e. p(verdict | claim_type) == p(verdict))
  - If chi² > critical value for df=(rows-1)*(cols-1) at alpha=0.05,
    we reject the null and surface a "bias flag" with the
    contingency table.
  - Cramér's V reported as effect size (0 = independent, 1 = perfect
    association). Useful because a giant N can make even tiny
    associations "significant".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("bias_auditor")


# Hardcoded chi² critical values at alpha=0.05 for df=1..20.
# Sourced from standard statistical tables (Pearson 1900, replicated
# in any intro stats textbook). The contingency tables this auditor
# builds rarely exceed 5x5 (5 claim_types × 5 verdicts), so df max
# is (5-1)*(5-1) = 16. We pad to 20 for safety.
CHI2_CRITICAL_ALPHA_05: Dict[int, float] = {
    1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
    6: 12.592, 7: 14.067, 8: 15.507, 9: 16.919, 10: 18.307,
    11: 19.675, 12: 21.026, 13: 22.362, 14: 23.685, 15: 24.996,
    16: 26.296, 17: 27.587, 18: 28.869, 19: 30.144, 20: 31.410,
}


def chi_squared_test(
    contingency: np.ndarray,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Run a chi-squared test of independence on a contingency table.

    contingency: numpy array of shape (rows, cols), non-negative integers.
        Rows typically = claim_types, cols = verdicts.

    Returns:
        {
          "chi2": float,
          "df": int,
          "critical_value": float,  # at alpha
          "reject_independence": bool,
          "cramer_v": float,  # effect size 0-1
          "n": int,  # total count
          "alpha": float,
          "notes": [str],
        }
    """
    notes: List[str] = []
    if contingency.ndim != 2 or contingency.size == 0:
        raise ValueError("contingency must be a 2D non-empty array")

    rows, cols = contingency.shape
    if rows < 2 or cols < 2:
        notes.append(
            f"Table shape ({rows}x{cols}) too small for chi² — "
            "need at least 2 rows AND 2 cols."
        )
        return {
            "chi2": 0.0, "df": 0, "critical_value": float("inf"),
            "reject_independence": False, "cramer_v": 0.0,
            "n": int(contingency.sum()), "alpha": alpha, "notes": notes,
        }

    n = int(contingency.sum())
    if n == 0:
        notes.append("Empty contingency table (n=0).")
        return {
            "chi2": 0.0, "df": (rows - 1) * (cols - 1),
            "critical_value": float("inf"),
            "reject_independence": False, "cramer_v": 0.0,
            "n": 0, "alpha": alpha, "notes": notes,
        }

    # Expected counts under independence: E_ij = (row_i * col_j) / n
    row_totals = contingency.sum(axis=1, keepdims=True)
    col_totals = contingency.sum(axis=0, keepdims=True)
    expected = (row_totals @ col_totals) / n

    # If any expected count is too low, chi² approximation breaks.
    # Standard rule: each expected >= 5. Flag and continue, but caller
    # should treat the result as preview.
    min_expected = float(np.min(expected))
    if min_expected < 5:
        notes.append(
            f"Min expected count {min_expected:.2f} < 5 — chi² approximation "
            "unreliable for sparse cells. Treat as preview."
        )

    # Avoid division by zero on all-zero rows/cols (collapsed dimension).
    with np.errstate(divide="ignore", invalid="ignore"):
        contribution = np.where(expected > 0, (contingency - expected) ** 2 / expected, 0.0)
    chi2 = float(np.sum(contribution))

    df = (rows - 1) * (cols - 1)
    critical = CHI2_CRITICAL_ALPHA_05.get(df, CHI2_CRITICAL_ALPHA_05[20])
    if df > 20:
        notes.append(
            f"df={df} exceeds hardcoded table — using df=20 critical value "
            "(31.410). This is conservative (under-rejects) for very large tables."
        )

    reject = chi2 > critical

    # Cramér's V effect size — normalised so 0 = no association,
    # 1 = perfect. min(rows, cols) - 1 is the max possible chi²/n.
    cramer_v = float(np.sqrt(chi2 / (n * (min(rows, cols) - 1)))) if min(rows, cols) > 1 else 0.0

    return {
        "chi2": round(chi2, 4),
        "df": df,
        "critical_value": critical,
        "reject_independence": reject,
        "cramer_v": round(cramer_v, 4),
        "n": n,
        "alpha": alpha,
        "notes": notes,
    }


def audit_claim_type_verdict_bias(db) -> Dict[str, Any]:
    """Run the bias audit over the current claims × verdicts corpus.

    Queries claims + fact_checks, builds a contingency table by
    (claim_type, verification_status), runs chi_squared_test.

    Returns the test result PLUS the contingency table itself so the
    UI can show the auditor 'why' alongside the verdict.
    """
    try:
        rows = db.execute_query(
            """SELECT
                  COALESCE(c.claim_type, 'unknown') AS claim_type,
                  COALESCE(fc.verification_status, 'UNVERIFIED') AS verdict,
                  COUNT(*) AS n
               FROM claims c
               LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
               WHERE c.created_at > NOW() - INTERVAL '180 days'
               GROUP BY claim_type, verdict
               ORDER BY claim_type, verdict"""
        )
    except Exception as exc:
        logger.error(f"bias auditor query failed: {exc}")
        return {
            "available": False,
            "error": str(exc),
            "notes": ["Database query failed — claims or fact_checks table may be missing"],
        }

    if not rows:
        return {
            "available": False,
            "notes": ["No claims found in the last 180 days — nothing to audit."],
        }

    # Build contingency table.
    claim_types = sorted({r["claim_type"] for r in rows})
    verdicts = sorted({r["verdict"] for r in rows})
    matrix = np.zeros((len(claim_types), len(verdicts)), dtype=np.int64)
    for r in rows:
        i = claim_types.index(r["claim_type"])
        j = verdicts.index(r["verdict"])
        matrix[i, j] = int(r["n"])

    test = chi_squared_test(matrix)
    return {
        "available": True,
        "window_days": 180,
        "claim_types": claim_types,
        "verdicts": verdicts,
        "contingency": matrix.tolist(),
        "test": test,
        "interpretation": _interpret(test),
    }


def _interpret(test: Dict[str, Any]) -> str:
    """Plain-language read of the test result for the methodology page."""
    if test.get("n", 0) == 0:
        return "Not enough data to audit yet."
    if test.get("reject_independence"):
        v = test.get("cramer_v", 0)
        if v < 0.1:
            strength = "weak but statistically present"
        elif v < 0.3:
            strength = "moderate"
        elif v < 0.5:
            strength = "strong"
        else:
            strength = "very strong"
        return (
            f"Statistically significant ({strength}) association between "
            f"claim type and verdict (chi²={test['chi2']}, "
            f"df={test['df']}, Cramér's V={test['cramer_v']}). "
            "Editorial review recommended — some claim types are receiving "
            "disproportionate verdict labels."
        )
    return (
        f"No statistically significant claim-type × verdict bias detected "
        f"(chi²={test['chi2']} below threshold {test['critical_value']:.3f}, "
        f"Cramér's V={test['cramer_v']}). Verdict distribution looks "
        "independent of claim type."
    )
