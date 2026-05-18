"""Sustainability score formula — Phase 3 wave 3.

Replaces the article-count `coverage_index` (which measured platform coverage,
not real-world sustainability) with a defensible composite over the indicators
populated by Phase 3 adapters (Climate TRACE, OWID, and eventually CAT, IRENA,
UNFCCC NDC, World Bank CCKP).

Every choice in this module is deliberately surfaced — weights are explicit
constants, normalisations are testable functions, missing components are
handled by transparent re-weighting (not silent zero-substitution), and the
output structure includes a `components` breakdown so users can see WHY a
score landed where it did.

# Methodology v1 (2026-05-16)

A country's sustainability_score is the weighted sum of normalised component
scores, each on a 0–100 scale where higher = more sustainable:

| Component                            | Weight | Direction | Source(s)                |
|--------------------------------------|--------|-----------|--------------------------|
| Per-capita emissions (inverted)      |  0.40  | lower=better | OWID, Global Carbon Project |
| Renewable share of electricity       |  0.40  | higher=better | OWID, IEA, Ember         |
| Climate Action Tracker policy rating |  0.20  | higher=better | CAT (adapter pending)    |

When a component's underlying indicator hasn't been synced yet for a country,
its weight is removed from the denominator and the remaining components are
re-normalised. The output's `indicators_used` and `confidence_band` reflect
this:

  * 1 component  → confidence_band = ±25 (low confidence)
  * 2 components → confidence_band = ±15 (medium)
  * 3+ components → confidence_band = ±10 (high)

The methodology_version string ("sustainability_v1_2026_05") is pinned to
every score. Future formula changes increment this so historical scores
remain reproducible.

# Why this is more defensible than coverage_index

  * **Reliability**: primary-source values vs article-count proxy.
  * **Transparency**: weights + normalisations in source, not buried in
    a black-box model.
  * **Traceability**: each ComponentContribution carries source_name + year
    + raw_value; you can trace the displayed 0–100 back to the upstream
    integer-precision number.
  * **Calibration**: confidence_band sizes with information available.
  * **Robustness**: missing data is explicit (indicators_used count)
    rather than imputed; clamping at the boundaries prevents overflow.

The formula will evolve as more adapters land. Each iteration bumps
METHODOLOGY_VERSION; the API exposes the version on every response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

_logger = logging.getLogger("sustainability_score")


# Pinned to every output. Bump on formula changes; old persisted scores can
# then be displayed with their original methodology label.
METHODOLOGY_VERSION = "sustainability_v1_2026_05"

# Methodology disclosure URL. Should point to a user-readable doc when one
# exists; today routes to the project's CHANGELOG / repository.
METHODOLOGY_URL = (
    "https://github.com/eljaplacido/climatenews/blob/main/"
    "docs/methodology/SUSTAINABILITY_SCORE.md"
)


# ---------------------------------------------------------------------------
# Normalisation functions — each maps a raw indicator value to a 0–100 score
# where higher = more sustainable. All clamp to [0, 100].
# ---------------------------------------------------------------------------

def normalize_emissions_per_capita(tco2e_per_person: float) -> float:
    """Map per-capita emissions (tCO2e/person) → 0–100 (lower emissions = higher).

    Linear scale: 0 tCO2e → 100, 20 tCO2e → 0, clamped.

    Reference distribution (for sanity-checking — World Bank / OWID 2022):
      * Qatar, Kuwait, UAE: 20–30 tCO2e per capita
      * USA: ~14 tCO2e
      * Germany, Japan: 8–9 tCO2e
      * China: ~7 tCO2e
      * World average: ~4.5 tCO2e
      * India: ~1.9 tCO2e
      * Most least-developed countries: <1 tCO2e

    20 tCO2e per capita is chosen as the "0 score" threshold because it
    represents emissions clearly incompatible with the 1.5 °C carbon budget.
    """
    if tco2e_per_person is None:
        raise ValueError("normalize_emissions_per_capita requires a number")
    score = 100.0 * (1.0 - (float(tco2e_per_person) / 20.0))
    return max(0.0, min(100.0, score))


def normalize_renewable_share(percent: float) -> float:
    """Renewable share of electricity is already 0–100; pass-through with clamp."""
    if percent is None:
        raise ValueError("normalize_renewable_share requires a number")
    return max(0.0, min(100.0, float(percent)))


def normalize_cat_rating(rating: float) -> float:
    """Climate Action Tracker rating is already normalised 0–100; pass-through with clamp."""
    if rating is None:
        raise ValueError("normalize_cat_rating requires a number")
    return max(0.0, min(100.0, float(rating)))


def normalize_nd_gain_index(score_0_to_100: float) -> float:
    """ND-GAIN composite adaptation index is already 0–100; pass-through with clamp.

    Notre Dame Global Adaptation Initiative scores combine vulnerability
    (lower is better) and readiness (higher is better), normalised to a
    0–100 composite where higher = more climate-resilient.
    """
    if score_0_to_100 is None:
        raise ValueError("normalize_nd_gain_index requires a number")
    return max(0.0, min(100.0, float(score_0_to_100)))


# ---------------------------------------------------------------------------
# Component definitions — the formula's wired structure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ComponentDefinition:
    """One ingredient of the composite score."""
    indicator_id: str
    weight: float          # 0–1; weights across all defined components sum to 1
    normalizer: Any        # Callable[[float], float] producing a 0–100 score
    description: str       # Human-readable disclosure for the methodology drawer


# Order matters for the components list output: highest-weight first.
# 2026-05-18 — ND-GAIN added as the adaptation dimension. The adapter wrote
# `nd_gain_index` into country_indicators but no formula consumed it, so the
# composite score ignored climate-resilience information for every country.
COMPONENTS: List[ComponentDefinition] = [
    ComponentDefinition(
        indicator_id="emissions_tco2e_per_capita",
        weight=0.35,
        normalizer=normalize_emissions_per_capita,
        description=(
            "Per-capita greenhouse-gas emissions (CO₂-equivalent, 100-year "
            "GWP), inverted so lower emissions yield a higher score. "
            "Calibrated against the 1.5 °C carbon budget — 20 tCO₂e/person "
            "= score 0; 0 tCO₂e/person = score 100."
        ),
    ),
    ComponentDefinition(
        indicator_id="renewable_share_electricity_percent",
        weight=0.30,
        normalizer=normalize_renewable_share,
        description=(
            "Share of electricity generated from renewable sources "
            "(solar + wind + hydro + geothermal + bioenergy). Used "
            "directly as the 0–100 score."
        ),
    ),
    ComponentDefinition(
        indicator_id="cat_overall_rating",
        weight=0.20,
        normalizer=normalize_cat_rating,
        description=(
            "Climate Action Tracker composite policy-ambition rating, "
            "normalised 0–100. 100 = aligned with 1.5 °C."
        ),
    ),
    ComponentDefinition(
        indicator_id="nd_gain_index",
        weight=0.15,
        normalizer=normalize_nd_gain_index,
        description=(
            "Notre Dame Global Adaptation Initiative composite — vulnerability "
            "and readiness combined to 0–100. Higher = more climate-resilient. "
            "Captures the adaptation dimension that the emissions/renewable/CAT "
            "components don't reach (mitigation policy ≠ resilience)."
        ),
    ),
]

assert abs(sum(c.weight for c in COMPONENTS) - 1.0) < 1e-9, (
    "Component weights must sum to exactly 1.0"
)


# Confidence band by indicators_used. Wider band when fewer indicators contributed.
def confidence_band_for(indicators_used: int) -> float:
    if indicators_used <= 0:
        return 50.0   # essentially uninformative
    if indicators_used == 1:
        return 25.0
    if indicators_used == 2:
        return 15.0
    return 10.0  # 3+ components


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------

@dataclass
class ComponentContribution:
    indicator_id: str
    normalized_score: float           # 0–100 after normalization
    weight_applied: float             # effective weight after redistribution
    raw_value: float
    unit: Optional[str]
    year: int
    source_name: str
    source_url: Optional[str]


@dataclass
class SustainabilityScore:
    value: float                                # 0–100 composite
    confidence_low: float                       # value - band, clamped to [0, 100]
    confidence_high: float                      # value + band, clamped to [0, 100]
    confidence_band: float                      # half-width of the band
    methodology_version: str
    methodology_url: str
    indicators_used: int
    indicators_available_in_formula: int
    components: List[ComponentContribution]     # one per contributing indicator
    formula_disclosure: str                     # human-readable summary

    def as_dict(self) -> Dict[str, Any]:
        return {
            "value": round(self.value, 2),
            "confidence_low": round(self.confidence_low, 2),
            "confidence_high": round(self.confidence_high, 2),
            "confidence_band": round(self.confidence_band, 2),
            "methodology_version": self.methodology_version,
            "methodology_url": self.methodology_url,
            "indicators_used": self.indicators_used,
            "indicators_available_in_formula": self.indicators_available_in_formula,
            "components": [
                {
                    "indicator_id": c.indicator_id,
                    "normalized_score": round(c.normalized_score, 2),
                    "weight_applied": round(c.weight_applied, 4),
                    "raw_value": c.raw_value,
                    "unit": c.unit,
                    "year": c.year,
                    "source_name": c.source_name,
                    "source_url": c.source_url,
                }
                for c in self.components
            ],
            "formula_disclosure": self.formula_disclosure,
        }


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def compute_sustainability_score(
    real_indicators: Dict[str, Any],
) -> Optional[SustainabilityScore]:
    """Compute the composite score for one country.

    `real_indicators` is expected to be a dict keyed by indicator_id, with
    values that have `.value`, `.unit`, `.year`, `.source_name`, `.source_url`
    attributes (the green_transition_routes.RealIndicatorValue Pydantic model
    matches this shape; raw dicts also work for unit tests).

    Returns None when no defined component has a usable raw value — callers
    should treat absence as "real-data scoring not yet available for this
    country, fall back to coverage_index".
    """
    contributing: List[Tuple[ComponentDefinition, Any, float]] = []  # (defn, indicator_obj, normalized)

    for comp in COMPONENTS:
        indicator = real_indicators.get(comp.indicator_id)
        if indicator is None:
            continue
        raw = _attr_or_item(indicator, "value")
        if raw is None:
            continue
        try:
            normalized = comp.normalizer(float(raw))
        except (TypeError, ValueError):
            _logger.debug(
                "Skipping component %s: raw value %r is not numeric",
                comp.indicator_id, raw,
            )
            continue
        contributing.append((comp, indicator, normalized))

    if not contributing:
        return None

    # Re-normalise weights over the contributing subset so they sum to 1.
    total_defined_weight = sum(c[0].weight for c in contributing)
    if total_defined_weight <= 0:
        return None

    components_out: List[ComponentContribution] = []
    weighted_total = 0.0
    for comp, indicator, normalized in contributing:
        effective_weight = comp.weight / total_defined_weight
        weighted_total += normalized * effective_weight
        components_out.append(
            ComponentContribution(
                indicator_id=comp.indicator_id,
                normalized_score=normalized,
                weight_applied=effective_weight,
                raw_value=float(_attr_or_item(indicator, "value")),
                unit=_attr_or_item(indicator, "unit"),
                year=int(_attr_or_item(indicator, "year") or 0),
                source_name=str(_attr_or_item(indicator, "source_name") or "unknown"),
                source_url=_attr_or_item(indicator, "source_url"),
            )
        )

    band = confidence_band_for(len(contributing))
    confidence_low = max(0.0, weighted_total - band)
    confidence_high = min(100.0, weighted_total + band)

    return SustainabilityScore(
        value=weighted_total,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        confidence_band=band,
        methodology_version=METHODOLOGY_VERSION,
        methodology_url=METHODOLOGY_URL,
        indicators_used=len(contributing),
        indicators_available_in_formula=len(COMPONENTS),
        components=components_out,
        formula_disclosure=_disclosure_for(components_out, total_defined_weight),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attr_or_item(obj: Any, key: str) -> Any:
    """Return obj.key if it's an attribute, else obj[key] if subscriptable, else None.

    Lets the same compute function consume both Pydantic models (attribute
    access) and dicts (subscript) — convenient for testing.
    """
    if obj is None:
        return None
    try:
        return getattr(obj, key)
    except AttributeError:
        pass
    try:
        return obj[key]
    except (TypeError, KeyError):
        return None


def _disclosure_for(
    components: List[ComponentContribution],
    total_defined_weight: float,
) -> str:
    """Render a one-paragraph disclosure of how this score was assembled."""
    if not components:
        return (
            "No real primary-source indicators were available for this "
            "country; the sustainability_score field is null."
        )

    used = ", ".join(
        f"{c.indicator_id} ({c.source_name}, {c.year}, weight {c.weight_applied:.0%})"
        for c in components
    )
    return (
        f"Composite score over {len(components)} of {len(COMPONENTS)} "
        f"defined components: {used}. Weights of unavailable components "
        f"were redistributed proportionally across the available set. "
        f"Methodology: {METHODOLOGY_VERSION}. "
        f"See {METHODOLOGY_URL} for the full formula and references."
    )
