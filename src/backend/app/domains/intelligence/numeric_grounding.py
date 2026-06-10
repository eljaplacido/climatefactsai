"""Numeric grounding check — Phase 8 B4 MVP (2026-05-24).

Cheap, deterministic grounding check that asserts every numeric token in a
claim appears (within tolerance) in the supporting evidence. Designed as a
defence-in-depth layer alongside the multi-LLM verifier — a single LLM may
hallucinate "1.5°C" when the underlying study says "1.6°C"; this catches it.

Out of scope: full NER (entity grounding), unit conversion (kg → tonnes),
temporal reasoning ("by 2030" vs "from 2030"). Those are the next-step
upgrades. This MVP grounds raw numeric tokens with their immediate unit
suffix only.

Design intent:
  - Pure functions, no I/O, no LLM calls — runs in <1ms on real claims.
  - Verdict is a *partial* signal: 100% grounding does NOT mean the claim
    is correct (semantic mismatch is invisible here), but <100% means at
    least one number was invented or transcribed wrong.
  - Used by the chat-time verifier + URL analysis claim extractor; later
    by the corporate-claim analyzer once /api/companies grows numeric
    claims like "reduced emissions by 40%".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


# Number pattern:
#   - optional leading sign
#   - integer with optional thousand separators (1,234 or 1234)
#   - optional decimal (.56)
#   - optional scientific notation (e10, E-3)
# We use re.X for readability.
_NUMBER_RE = re.compile(
    r"""
    (?<![\w.])               # not preceded by word char or dot — avoids '4.5' inside 'a4.5b'
    (
        -?                   # optional negative
        \d{1,3}(?:,\d{3})+   # 1,234,567 form
        |
        -?\d+                # plain integer
    )
    (?:\.\d+)?               # optional decimal part
    (?:[eE][+-]?\d+)?        # optional scientific notation
    (?!\w)                   # not followed by word char (e.g. '4abc')
    """,
    re.VERBOSE,
)

# Unit pattern follows the number. Captures common climate units.
# Order matters: longer units first so "ppm" matches before "p".
_UNIT_PATTERNS = [
    # Temperature
    (re.compile(r"\s*°\s*C\b"), "°C"),
    (re.compile(r"\s*°\s*F\b"), "°F"),
    (re.compile(r"\s*degrees?\s+celsius\b", re.IGNORECASE), "°C"),
    (re.compile(r"\s*degrees?\s+fahrenheit\b", re.IGNORECASE), "°F"),
    # Concentration
    (re.compile(r"\s*ppm\b", re.IGNORECASE), "ppm"),
    (re.compile(r"\s*ppb\b", re.IGNORECASE), "ppb"),
    # Mass (CO2e units)
    (re.compile(r"\s*gigatonnes?\b", re.IGNORECASE), "Gt"),
    (re.compile(r"\s*gt\s*CO2e?\b", re.IGNORECASE), "GtCO2e"),
    (re.compile(r"\s*GtCO2e?\b"), "GtCO2e"),
    (re.compile(r"\s*megatonnes?\b", re.IGNORECASE), "Mt"),
    (re.compile(r"\s*MtCO2e?\b"), "MtCO2e"),
    (re.compile(r"\s*tonnes?\b", re.IGNORECASE), "t"),
    (re.compile(r"\s*kilotonnes?\b", re.IGNORECASE), "kt"),
    # Percentage
    (re.compile(r"\s*%"), "%"),
    (re.compile(r"\s*percent\b", re.IGNORECASE), "%"),
    (re.compile(r"\s*per\s*cent\b", re.IGNORECASE), "%"),
    # Energy / power
    (re.compile(r"\s*TWh\b"), "TWh"),
    (re.compile(r"\s*GWh\b"), "GWh"),
    (re.compile(r"\s*MWh\b"), "MWh"),
    (re.compile(r"\s*kWh\b"), "kWh"),
    (re.compile(r"\s*GW\b"), "GW"),
    (re.compile(r"\s*MW\b"), "MW"),
    # Sea level / distance
    (re.compile(r"\s*mm\b"), "mm"),
    (re.compile(r"\s*cm\b"), "cm"),
    (re.compile(r"\s*km\b"), "km"),
    (re.compile(r"\s*m\b"), "m"),
    # Money — captured because emission-reduction targets often paired with
    # investment numbers in the same sentence; lets us avoid grounding
    # "$5 billion" against "5 GtCO2e".
    (re.compile(r"\s*billion\s+dollars?\b", re.IGNORECASE), "USD-bn"),
    (re.compile(r"\s*million\s+dollars?\b", re.IGNORECASE), "USD-mn"),
    (re.compile(r"\s*billion\b", re.IGNORECASE), "bn"),
    (re.compile(r"\s*million\b", re.IGNORECASE), "mn"),
    # Year — context anchor only; never grounded numerically.
    (re.compile(r"(?<=\d)(?=\s|\.|,|$)"), None),  # bare number, no unit
]


@dataclass(frozen=True)
class NumericToken:
    """One number + unit pair extracted from text."""
    value: float
    unit: Optional[str]
    raw: str
    span: tuple[int, int]


def _detect_unit(text: str, after_index: int) -> tuple[Optional[str], int]:
    """Match a unit pattern starting at `after_index`. Returns (unit, end)."""
    for pat, label in _UNIT_PATTERNS:
        m = pat.match(text, after_index)
        if m:
            return label, m.end()
    return None, after_index


def extract_numbers(text: str) -> list[NumericToken]:
    """Extract every numeric token from `text` with its unit suffix.

    Returns tokens in source order. Duplicate values + units are NOT
    deduplicated — the caller decides whether identical tokens count as
    multiple groundings.
    """
    if not text:
        return []

    tokens: list[NumericToken] = []
    pos = 0
    while pos < len(text):
        m = _NUMBER_RE.search(text, pos)
        if not m:
            break
        raw = m.group(0)
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            pos = m.end()
            continue
        unit, end = _detect_unit(text, m.end())
        tokens.append(NumericToken(value=value, unit=unit, raw=raw, span=(m.start(), m.end())))
        pos = end if end > m.end() else m.end()

    return tokens


# ---------------------------------------------------------------------------
# Grounding check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundingResult:
    """Output of `check_numeric_grounding`.

    `grounding_score` is in [0, 1]. 1.0 = every claim-token had a matching
    evidence-token. 0.0 = none did. NaN-safe: when the claim has zero
    numeric tokens, score is 1.0 by convention (vacuously grounded — there
    is nothing to ground).
    """
    grounded: bool
    grounding_score: float
    grounded_tokens: tuple[NumericToken, ...]
    ungrounded_tokens: tuple[NumericToken, ...]
    claim_token_count: int


def _tokens_match(a: NumericToken, b: NumericToken, tolerance: float) -> bool:
    """Two tokens match when their units are compatible AND their values
    are within `tolerance` (relative, not absolute).

    Unit compatibility:
      - Both unitless → must match exactly
      - Both same unit → match by value
      - One unitless, one with unit → MATCH (claim "1.5" against evidence
        "1.5°C" is treated as grounded; the claim writer left the unit
        implicit). This is more permissive than strict grounding — we
        prioritise low false-positive rate over strict typing for MVP.
    """
    if a.unit and b.unit and a.unit != b.unit:
        return False
    # Tolerance is relative to the larger absolute value, with a small
    # floor so 0 doesn't break the division. Absolute fallback for tiny
    # numbers — anything <1e-6 is treated as equal-zero-ish.
    av, bv = a.value, b.value
    if abs(av) < 1e-6 and abs(bv) < 1e-6:
        return True
    denom = max(abs(av), abs(bv), 1e-6)
    return abs(av - bv) / denom <= tolerance


def check_numeric_grounding(
    claim: str,
    evidence: str,
    tolerance: float = 0.01,
) -> GroundingResult:
    """Check whether every numeric token in `claim` is grounded in `evidence`.

    Args:
        claim: The factual claim being verified.
        evidence: The supporting text (article body, disclosure context,
            citation excerpt) that should contain the same numbers.
        tolerance: Relative tolerance, default 1%. "1.5°C" matches "1.51°C".

    Returns:
        GroundingResult — see dataclass docstring for semantics.
    """
    claim_tokens = extract_numbers(claim)
    evidence_tokens = extract_numbers(evidence)

    if not claim_tokens:
        return GroundingResult(
            grounded=True,
            grounding_score=1.0,
            grounded_tokens=(),
            ungrounded_tokens=(),
            claim_token_count=0,
        )

    grounded: list[NumericToken] = []
    ungrounded: list[NumericToken] = []
    for ct in claim_tokens:
        if any(_tokens_match(ct, et, tolerance) for et in evidence_tokens):
            grounded.append(ct)
        else:
            ungrounded.append(ct)

    score = len(grounded) / len(claim_tokens)
    return GroundingResult(
        grounded=(score >= 1.0),
        grounding_score=score,
        grounded_tokens=tuple(grounded),
        ungrounded_tokens=tuple(ungrounded),
        claim_token_count=len(claim_tokens),
    )


def check_numeric_grounding_against_indicators(
    claim: str,
    indicators: Sequence[Tuple[float, Optional[str]]],
    tolerance: float = 0.05,
) -> GroundingResult:
    """Ground a claim's numbers against REAL measured values, not the prose.

    `indicators` is a sequence of ``(value, unit)`` pairs — e.g. the rows from
    ``country_indicators`` for a given country (emissions_tco2e_per_capita,
    renewable_share_electricity_percent, …). Matching semantics are identical
    to :func:`check_numeric_grounding` (unit-compatible AND within a relative
    tolerance, default 5%).

    This is the building block the Data-Layer audit (2026-06-10, item 5) asks
    for: grounding numerics against real data instead of the article's own
    text (which a model may have hallucinated and then "corroborated" against
    itself). It is only meaningful with a topical/country context that yields a
    RELEVANT indicator set — grounding arbitrary article numbers against every
    national indicator globally would match coincidentally and dilute the
    signal. It therefore belongs in the country-aware article-verification
    path; the URL-analysis path (which has no country context) keeps the
    source-text check.
    """
    claim_tokens = extract_numbers(claim)
    if not claim_tokens:
        return GroundingResult(
            grounded=True,
            grounding_score=1.0,
            grounded_tokens=(),
            ungrounded_tokens=(),
            claim_token_count=0,
        )

    evidence_tokens = [
        NumericToken(value=float(v), unit=u, raw=str(v), span=(0, 0))
        for (v, u) in indicators
        if v is not None
    ]

    grounded: list[NumericToken] = []
    ungrounded: list[NumericToken] = []
    for ct in claim_tokens:
        if any(_tokens_match(ct, et, tolerance) for et in evidence_tokens):
            grounded.append(ct)
        else:
            ungrounded.append(ct)

    score = len(grounded) / len(claim_tokens)
    return GroundingResult(
        grounded=(score >= 1.0),
        grounding_score=score,
        grounded_tokens=tuple(grounded),
        ungrounded_tokens=tuple(ungrounded),
        claim_token_count=len(claim_tokens),
    )


def grounding_score(claim: str, evidence: str, tolerance: float = 0.01) -> float:
    """Convenience: scalar grounding score in [0, 1]. See
    `check_numeric_grounding` for full semantics."""
    return check_numeric_grounding(claim, evidence, tolerance).grounding_score
