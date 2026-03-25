"""
Editorial Gate — CARF-inspired Guardian pattern for content quality control.

Applies rule-based logic to determine whether an article should be published,
held for review, or escalated for manual inspection, based on reliability signals.
"""

from typing import Any, Dict, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


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
                risk_factors.append(f"Public-tier source with low reliability")

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
