"""
Cynefin Complexity Router.

Classifies queries into Cynefin framework domains (Clear, Complicated,
Complex, Chaotic) and recommends an appropriate analysis strategy. Uses
keyword scoring with optional LLM fallback for ambiguous cases.
"""

import re
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class CynefinRouter:
    """Routes queries through Cynefin framework for appropriate analysis depth."""

    CLEAR_KEYWORDS = [
        "what is", "when did", "how many", "define", "current temperature",
        "latest data", "who is", "where is", "list", "name of", "which country",
        "how much", "total", "average", "what year",
    ]

    COMPLICATED_KEYWORDS = [
        "how does", "what causes", "compare", "relationship between",
        "impact of", "explain", "difference between", "why does",
        "mechanism", "process", "analysis", "correlation", "effect of",
        "influence", "contribute to", "factors",
    ]

    COMPLEX_KEYWORDS = [
        "predict", "forecast", "scenario", "what if", "future", "trend",
        "model", "tipping point", "feedback loop", "systemic", "cascade",
        "long-term", "projection", "emerging", "evolving", "adaptation",
        "uncertainty", "transition",
    ]

    CHAOTIC_KEYWORDS = [
        "emergency", "crisis", "sudden", "unprecedented", "breaking",
        "urgent", "disaster", "catastrophic", "extreme event", "collapse",
        "immediate", "critical", "alert", "evacuate",
    ]

    # Domain-to-strategy mapping
    STRATEGY_MAP = {
        "clear": "direct_lookup",
        "complicated": "multi_source_analysis",
        "complex": "causal_analysis",
        "chaotic": "rapid_assessment",
    }

    STRATEGY_DESCRIPTIONS = {
        "direct_lookup": "Simple database query for factual answers.",
        "multi_source_analysis": "HybridRAG retrieval with evidence chain analysis.",
        "causal_analysis": "Full causal pipeline with counterfactual reasoning.",
        "rapid_assessment": "Quick summary with high uncertainty flags.",
    }

    def classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Classify query complexity using Cynefin framework.

        Args:
            query: The user's query text.
            context: Optional context dict (e.g., prior conversation, article data).

        Returns:
            Dict with: domain, confidence, recommended_strategy,
            strategy_description, reasoning.
        """
        query_lower = query.lower().strip()

        scores = {
            "clear": self._score_domain(query_lower, self.CLEAR_KEYWORDS),
            "complicated": self._score_domain(query_lower, self.COMPLICATED_KEYWORDS),
            "complex": self._score_domain(query_lower, self.COMPLEX_KEYWORDS),
            "chaotic": self._score_domain(query_lower, self.CHAOTIC_KEYWORDS),
        }

        # Apply contextual boosts
        if context:
            scores = self._apply_context_boosts(scores, context)

        total = sum(scores.values())
        if total == 0:
            # No keyword matches — try LLM classification
            llm_result = self._llm_classify(query)
            if llm_result:
                return llm_result
            # Default to complicated for non-trivial queries
            domain = "complicated"
            confidence = 0.3
            reasoning = "No strong keyword signals detected; defaulting to multi-source analysis."
        else:
            domain = max(scores, key=scores.get)
            confidence = round(scores[domain] / max(total, 1), 2)
            matched = self._get_matched_keywords(query_lower, domain)
            reasoning = f"Matched {domain} keywords: {', '.join(matched[:5])}"

        # Boost confidence if single domain dominates
        if confidence > 0.6:
            confidence = min(0.95, confidence + 0.1)

        strategy = self.STRATEGY_MAP[domain]

        return {
            "domain": domain,
            "confidence": confidence,
            "recommended_strategy": strategy,
            "strategy_description": self.STRATEGY_DESCRIPTIONS[strategy],
            "reasoning": reasoning,
            "scores": scores,
        }

    # ------------------------------------------------------------------
    # Keyword scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _score_domain(query_lower: str, keywords: list) -> float:
        """Score a query against a list of domain keywords."""
        score = 0.0
        for kw in keywords:
            if kw in query_lower:
                # Longer keyword phrases are weighted more
                weight = 1.0 + len(kw.split()) * 0.3
                score += weight
        return round(score, 2)

    def _get_matched_keywords(self, query_lower: str, domain: str) -> list:
        """Return the keywords that matched for a given domain."""
        keyword_map = {
            "clear": self.CLEAR_KEYWORDS,
            "complicated": self.COMPLICATED_KEYWORDS,
            "complex": self.COMPLEX_KEYWORDS,
            "chaotic": self.CHAOTIC_KEYWORDS,
        }
        keywords = keyword_map.get(domain, [])
        return [kw for kw in keywords if kw in query_lower]

    # ------------------------------------------------------------------
    # Context boosts
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_context_boosts(
        scores: Dict[str, float],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """Apply contextual boosts based on metadata."""
        # If query is about a specific article with high credibility, lean toward Clear
        if context.get("article_credibility") == "HIGH":
            scores["clear"] += 0.5

        # If the topic involves predictions or models
        if context.get("involves_predictions"):
            scores["complex"] += 1.0

        # If flagged as urgent/breaking
        if context.get("is_breaking"):
            scores["chaotic"] += 1.5

        return scores

    # ------------------------------------------------------------------
    # LLM fallback for ambiguous queries
    # ------------------------------------------------------------------

    def _llm_classify(self, query: str) -> Optional[Dict[str, Any]]:
        """Use LLM to classify ambiguous queries."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            prompt = (
                f'Classify this climate news query into one Cynefin domain.\n'
                f'Query: "{query}"\n\n'
                f'Domains:\n'
                f'- clear: Simple factual lookup\n'
                f'- complicated: Requires expert analysis of multiple factors\n'
                f'- complex: Involves emergence, predictions, tipping points\n'
                f'- chaotic: Crisis/emergency requiring rapid response\n\n'
                f'Respond with ONLY the domain name (one word): clear, complicated, complex, or chaotic'
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt="You classify queries. Respond with exactly one word.",
                max_tokens=10,
                temperature=0.0,
            )

            if response:
                domain = response.strip().lower().rstrip(".")
                if domain in self.STRATEGY_MAP:
                    strategy = self.STRATEGY_MAP[domain]
                    return {
                        "domain": domain,
                        "confidence": 0.6,
                        "recommended_strategy": strategy,
                        "strategy_description": self.STRATEGY_DESCRIPTIONS[strategy],
                        "reasoning": "Classified by LLM (ambiguous keywords).",
                        "scores": {},
                    }
        except Exception as e:
            logger.debug(f"LLM Cynefin classification failed: {e}")

        return None
