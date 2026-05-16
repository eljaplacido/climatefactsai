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
        db: Any = None,
        deep_search_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classify query complexity using Cynefin framework.

        Args:
            query: The user's query text.
            context: Optional context dict (e.g., prior conversation, article data).
            db: Optional Postgres client. When provided AND the LLM path
                fires, records a provenance row to `claim_provenance`
                (Phase 4 wave 4) so the audit trail captures the
                classification.
            deep_search_session_id: When set, this classification's
                provenance row joins the deep-search session's other
                rows. The audit-trail endpoint groups by this id.

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
                # Phase 4 wave 4: record provenance for the LLM path so
                # auditors can trace classification → session → prompt.
                self._maybe_record_provenance(
                    llm_result, db, deep_search_session_id, query,
                )
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
    # Provenance recording (Phase 4 wave 4)
    # ------------------------------------------------------------------

    def _maybe_record_provenance(
        self,
        llm_result: Dict[str, Any],
        db: Any,
        deep_search_session_id: Optional[str],
        query: str,
    ) -> None:
        """Best-effort: log one provenance row when we have a DB + the LLM path fired."""
        if db is None:
            return
        try:
            import uuid as _uuid
            from app.domains.intelligence.provenance import (
                EXTRACTION_CYNEFIN,
                ProvenanceRecord,
                record_provenance,
            )

            prompt_block = llm_result.get("prompt") or {}
            record_provenance(db, ProvenanceRecord(
                extraction_method=EXTRACTION_CYNEFIN,
                cynefin_classification_id=str(_uuid.uuid4()),
                deep_search_session_id=deep_search_session_id,
                model_name="llm_via_llm_client",  # llm_client resolves which provider
                prompt_name=prompt_block.get("name"),
                prompt_version=prompt_block.get("version"),
                prompt_fingerprint=prompt_block.get("fingerprint"),
                confidence=llm_result.get("confidence"),
                raw_metadata={
                    "query": query[:500],
                    "domain": llm_result.get("domain"),
                    "raw_domain": llm_result.get("raw_domain"),
                    "recommended_strategy": llm_result.get("recommended_strategy"),
                    "reasoning": llm_result.get("reasoning"),
                },
            ))
        except Exception as exc:
            logger.debug(f"Cynefin record_provenance failed (non-fatal): {exc}")

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
        """Classify an ambiguous query via an LLM with structured-JSON output.

        Prompt adapted from `projectcarfcynepic/config/prompts.yaml#router`
        (eljaplacido/projectcarfcynepic — BSL 1.1, both repos same owner so
        self-permission is fine; track in docs/licenses if the port grows).
        Returns confidence + reasoning grounded in the LLM's actual judgement
        rather than the pre-fix flat 0.6 with a templated "Classified by LLM"
        string (the audit flagged that as a calibration lie).
        """
        try:
            from app.domains.intelligence.llm_client import llm_chat
            from app.domains.intelligence.prompts import get_prompt

            # Phase 4 wave 1: resolve prompt + system from the central registry
            # so the cynefin classifier is versioned/fingerprinted alongside
            # every other LLM call.
            tmpl = get_prompt("cynefin_classifier")
            user_prompt = tmpl.format(query=query)

            response = llm_chat(
                prompt=user_prompt,
                system_prompt=tmpl.system,
                max_tokens=tmpl.max_tokens or 200,
                temperature=tmpl.temperature if tmpl.temperature is not None else 0.0,
            )

            if not response:
                return None

            # Tolerant JSON parse — strip code fences if the model added them.
            import json as _json
            import re as _re

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = _re.sub(
                    r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=_re.DOTALL
                ).strip()

            try:
                parsed = _json.loads(cleaned)
            except (ValueError, TypeError):
                logger.debug(f"LLM Cynefin returned non-JSON: {response!r}")
                return None

            if not isinstance(parsed, dict):
                return None

            raw_domain = str(parsed.get("domain", "")).strip().lower()
            if raw_domain not in self.STRATEGY_MAP and raw_domain != "disorder":
                return None

            # "disorder" → safe default routing (complicated) with capped
            # confidence so callers can flag for clarification.
            effective_domain = "complicated" if raw_domain == "disorder" else raw_domain
            strategy = self.STRATEGY_MAP[effective_domain]

            try:
                confidence = float(parsed.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))
            if raw_domain == "disorder":
                confidence = min(confidence, 0.4)

            reasoning = str(parsed.get("reasoning", "")).strip() or "Classified by LLM."

            return {
                "domain": effective_domain,
                "confidence": round(confidence, 2),
                "recommended_strategy": strategy,
                "strategy_description": self.STRATEGY_DESCRIPTIONS[strategy],
                "reasoning": reasoning,
                "scores": {},
                "source": "llm_structured",
                "raw_domain": raw_domain,  # preserve "disorder" for transparency
                # Phase 4 wave 1: record which versioned prompt produced this.
                "prompt": tmpl.as_audit_dict(),
            }
        except Exception as e:
            logger.debug(f"LLM Cynefin classification failed: {e}")

        return None
