"""
Editorial Gate — CARF-inspired Guardian pattern for content quality control.

Applies rule-based logic to determine whether an article should be published,
held for review, or escalated for manual inspection, based on reliability signals.
"""

from typing import Any, Dict, Optional, Tuple
from app.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Content-Scope Charter (F1) — topical relevance gate
# =============================================================================
# The platform ingests from a mix of feeds; general-news feeds leak off-topic
# stories (e.g. a bus-accident report) that don't belong on a climate platform.
# classify_climate_relevance is a CONSERVATIVE keyword gate: an item is
# in-scope if it shows ANY climate / sustainability / energy-transition signal.
# It rejects only items with ZERO signal, so legitimate climate coverage is
# never dropped (false-negatives matter far more than false-positives here).
# The matched terms are returned so the decision is reviewer-traceable.

_CLIMATE_TERMS_STRONG = (
    "climate change", "global warming", "greenhouse gas", "carbon emission",
    "carbon dioxide", "co2", "net zero", "net-zero", "decarboni",
    "renewable energy", "solar power", "wind power", "wind energy",
    "fossil fuel", "energy transition", "paris agreement", "ipcc",
    "sea level rise", "carbon neutral", "carbon footprint", "emissions",
    "sustainability", "sustainable", "biodiversity", "deforestation",
    "cop28", "cop29", "cop30", "unfccc", "climate", "cleantech",
    "clean energy", "green transition", "esg", "csrd", "sbti",
    "carbon market", "carbon credit", "climate risk", "climate policy",
)

_CLIMATE_TERMS_WEAK = (
    "drought", "wildfire", "flood", "heatwave", "heat wave", "hurricane",
    "cyclone", "typhoon", "glacier", "permafrost", "coral", "ecosystem",
    "pollution", "recycling", "electric vehicle", "battery",
    "hydrogen", "methane", "rainforest", "conservation", "biofuel",
    "solar", "wind farm", "warming", "temperature anomaly",
    "extreme weather", "adaptation", "mitigation", "resilience",
)


def classify_climate_relevance(title: str, body: str) -> Tuple[bool, float, str]:
    """Decide whether an article is in scope for the climate platform (F1).

    Pure function (no DB/LLM) so it is directly unit-testable. Returns
    (is_relevant, score 0-1, human-readable reason). Conservative: rejects
    only items with NO climate signal at all.
    """
    text = f"{title or ''} {body or ''}".lower()
    if not text.strip():
        return False, 0.0, "empty content"

    strong_hits = sorted({t for t in _CLIMATE_TERMS_STRONG if t in text})
    weak_hits = sorted({t for t in _CLIMATE_TERMS_WEAK if t in text})

    if strong_hits:
        score = min(1.0, 0.6 + 0.1 * len(strong_hits))
        return True, score, f"climate-relevant (matched: {', '.join(strong_hits[:5])})"
    if len(weak_hits) >= 2:
        return True, 0.5, f"climate-adjacent (matched: {', '.join(weak_hits[:5])})"
    if len(weak_hits) == 1:
        # One weak signal is ambiguous — let it through but flag for review
        # rather than dropping potential coverage.
        return True, 0.35, f"weak signal ({weak_hits[0]}); review recommended"
    return False, 0.0, "no climate/sustainability/energy-transition signal detected"


class EditorialDecision:
    """Represents the editorial gate's decision."""
    PUBLISH = "PUBLISH"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"


class EditorialGate:
    """
    Rule engine for editorial quality control.

    Decision criteria:
    - PUBLISH: reliability_score >= 60, no disputed claims, high-tier source
    - HOLD: reliability_score 30-59, or some disputed claims
    - ESCALATE: reliability_score < 30, or majority disputed, or low source tier
    """

    def evaluate(
        self,
        reliability_score: Optional[float] = None,
        claims_count: int = 0,
        disputed_claims: int = 0,
        source_tier: str = "public",
        confidence: Optional[float] = None,
        content_type: str = "news_article",
    ) -> Dict[str, Any]:
        """
        Evaluate an article through the editorial gate.

        Returns dict with:
            - decision: PUBLISH | HOLD | ESCALATE
            - reason: human-readable explanation
            - auto_publishable: bool
            - requires_review: bool
            - risk_factors: list of identified risks
        """
        risk_factors = []
        score = reliability_score or 0

        # Risk factor analysis
        if score < 30:
            risk_factors.append("Very low reliability score")
        elif score < 50:
            risk_factors.append("Below-average reliability score")

        if claims_count > 0:
            disputed_ratio = disputed_claims / claims_count
            if disputed_ratio > 0.5:
                risk_factors.append(f"Majority of claims disputed ({disputed_claims}/{claims_count})")
            elif disputed_ratio > 0.25:
                risk_factors.append(f"Significant disputed claims ({disputed_claims}/{claims_count})")

        if source_tier not in ("research", "scientific"):
            if score < 50:
                risk_factors.append("Public-tier source with low reliability")

        if confidence is not None and confidence < 0.4:
            risk_factors.append("Low verification confidence")

        if content_type == "preprint":
            risk_factors.append("Preprint — not peer-reviewed")

        # Decision logic
        decision = EditorialDecision.PUBLISH
        reason = "All quality checks passed"

        # ESCALATE conditions
        if score < 30:
            decision = EditorialDecision.ESCALATE
            reason = "Reliability score below threshold (< 30)"
        elif claims_count > 0 and disputed_claims / claims_count > 0.5:
            decision = EditorialDecision.ESCALATE
            reason = "Majority of claims are disputed"
        elif len(risk_factors) >= 3:
            decision = EditorialDecision.ESCALATE
            reason = f"Multiple risk factors identified ({len(risk_factors)})"

        # HOLD conditions (only if not already ESCALATE)
        elif score < 60:
            decision = EditorialDecision.HOLD
            reason = "Reliability score below publish threshold (< 60)"
        elif claims_count > 0 and disputed_claims / claims_count > 0.25:
            decision = EditorialDecision.HOLD
            reason = "Significant proportion of disputed claims"
        elif confidence is not None and confidence < 0.5:
            decision = EditorialDecision.HOLD
            reason = "Low verification confidence"
        elif content_type == "preprint":
            decision = EditorialDecision.HOLD
            reason = "Preprint requires additional verification"

        return {
            "decision": decision,
            "reason": reason,
            "auto_publishable": decision == EditorialDecision.PUBLISH,
            "requires_review": decision != EditorialDecision.PUBLISH,
            "risk_factors": risk_factors,
            "reliability_score": score,
            "source_tier": source_tier,
        }
