"""
Causal Claim Analyzer.

Detects causal language patterns in claims, extracts cause/effect entities,
queries the knowledge graph for supporting or contradicting evidence, and
uses LLM analysis to distinguish genuine causal relationships from mere
correlations.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)

# Causal language patterns (regex)
CAUSAL_PATTERNS = [
    r"\bcauses?\b",
    r"\bleads?\s+to\b",
    r"\bresults?\s+in\b",
    r"\bdue\s+to\b",
    r"\bbecause\s+of\b",
    r"\bdriven\s+by\b",
    r"\bcontributes?\s+to\b",
    r"\bresponsible\s+for\b",
    r"\btriggers?\b",
    r"\binduces?\b",
    r"\bproduces?\b",
    r"\bbrings?\s+about\b",
    r"\bgives?\s+rise\s+to\b",
    r"\battribut(?:ed|able)\s+to\b",
    r"\bas\s+a\s+result\s+of\b",
    r"\bconsequen(?:ce|tly)\b",
]

CAUSAL_ANALYSIS_SYSTEM = """You are a causal reasoning expert specializing in climate science.
Analyze the following claim and evidence to determine if the stated causal relationship is valid.

Return valid JSON:
{
  "is_causal": true/false,
  "causal_confidence": 0.0-1.0,
  "cause_entity": "the cause described",
  "effect_entity": "the effect described",
  "mechanism": "brief description of the causal mechanism if valid",
  "confounders": ["list of potential confounding variables"],
  "alternative_explanations": ["list of alternative explanations"],
  "assessment": "brief assessment paragraph"
}

Consider:
1. Is this truly causal or merely correlational?
2. What confounders could exist?
3. Is there a plausible mechanism?
4. What is the strength of evidence?

Return ONLY the JSON object.
"""


class CausalClaimAnalyzer:
    """Analyze causal claims with evidence from the knowledge graph and LLM reasoning."""

    def __init__(self, db: Database):
        self.db = db

    async def analyze(
        self,
        claim_text: str,
        evidence: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a causal claim.

        Args:
            claim_text: The claim to analyze (e.g., "CO2 emissions cause warming").
            evidence: Optional list of supporting evidence texts.

        Returns:
            Dict with causal assessment details.
        """
        # Step 1: Detect causal language
        causal_matches = self._detect_causal_language(claim_text)
        has_causal_language = len(causal_matches) > 0

        # Step 2: Extract cause/effect from claim
        cause_effect = self._extract_cause_effect(claim_text)

        # Step 3: Query knowledge graph for related evidence
        graph_support, graph_contra = self._query_graph_evidence(
            cause_effect.get("cause", ""),
            cause_effect.get("effect", ""),
        )

        # Step 4: LLM causal analysis
        all_evidence = list(evidence or [])
        for item in graph_support:
            all_evidence.append(f"[SUPPORTING] {item}")
        for item in graph_contra:
            all_evidence.append(f"[CONTRADICTING] {item}")

        llm_result = await self._llm_analyze(claim_text, all_evidence)

        # Merge results
        result = {
            "claim_text": claim_text,
            "has_causal_language": has_causal_language,
            "causal_patterns_found": causal_matches,
            "is_causal": llm_result.get("is_causal", has_causal_language),
            "causal_confidence": llm_result.get("causal_confidence", 0.5 if has_causal_language else 0.2),
            "cause_entity": llm_result.get("cause_entity", cause_effect.get("cause", "")),
            "effect_entity": llm_result.get("effect_entity", cause_effect.get("effect", "")),
            "mechanism": llm_result.get("mechanism", ""),
            "confounders": llm_result.get("confounders", []),
            "alternative_explanations": llm_result.get("alternative_explanations", []),
            "supporting_evidence": graph_support,
            "contradicting_evidence": graph_contra,
            "assessment": llm_result.get("assessment", ""),
        }

        logger.info(
            "Causal claim analyzed",
            is_causal=result["is_causal"],
            confidence=result["causal_confidence"],
            patterns=len(causal_matches),
        )
        return result

    # ------------------------------------------------------------------
    # Causal language detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_causal_language(text: str) -> List[str]:
        """Find causal language patterns in the text."""
        text_lower = text.lower()
        matches = []
        for pattern in CAUSAL_PATTERNS:
            found = re.findall(pattern, text_lower)
            matches.extend(found)
        return matches

    @staticmethod
    def _extract_cause_effect(claim: str) -> Dict[str, str]:
        """
        Simple heuristic extraction of cause and effect from a claim.

        Looks for patterns like "X causes Y", "Y due to X", etc.
        """
        claim_lower = claim.lower()

        # "X causes/leads to/results in Y"
        for sep in ["causes", "leads to", "results in", "triggers", "produces", "contributes to"]:
            if sep in claim_lower:
                parts = claim_lower.split(sep, 1)
                if len(parts) == 2:
                    return {"cause": parts[0].strip(), "effect": parts[1].strip()}

        # "Y due to/because of/driven by X"
        for sep in ["due to", "because of", "driven by", "attributed to", "as a result of"]:
            if sep in claim_lower:
                parts = claim_lower.split(sep, 1)
                if len(parts) == 2:
                    return {"cause": parts[1].strip(), "effect": parts[0].strip()}

        return {"cause": "", "effect": ""}

    # ------------------------------------------------------------------
    # Knowledge graph evidence
    # ------------------------------------------------------------------

    def _query_graph_evidence(
        self,
        cause: str,
        effect: str,
    ) -> tuple:
        """
        Query the knowledge graph for supporting and contradicting relationships.

        Returns (supporting_evidence_list, contradicting_evidence_list).
        """
        supporting: List[str] = []
        contradicting: List[str] = []

        if not cause and not effect:
            return supporting, contradicting

        try:
            # Find entities matching cause and effect
            search_terms = []
            params: Dict[str, Any] = {}
            if cause:
                search_terms.append("e.entity_name ILIKE :cause_term")
                cause_words = [w for w in cause.split() if len(w) > 3]
                params["cause_term"] = f"%{cause_words[0]}%" if cause_words else f"%{cause}%"
            if effect:
                search_terms.append("e.entity_name ILIKE :effect_term")
                effect_words = [w for w in effect.split() if len(w) > 3]
                params["effect_term"] = f"%{effect_words[0]}%" if effect_words else f"%{effect}%"

            if not search_terms:
                return supporting, contradicting

            # Find relevant relationships
            rows = self.db.execute_query(
                f"""
                SELECT
                    e_src.entity_name AS source_name,
                    e_tgt.entity_name AS target_name,
                    er.relationship_type,
                    er.evidence_text,
                    er.confidence,
                    er.strength
                FROM entity_relationships er
                JOIN entities e_src ON e_src.entity_id = er.source_entity_id
                JOIN entities e_tgt ON e_tgt.entity_id = er.target_entity_id
                WHERE ({" OR ".join(search_terms.copy()).replace('e.entity_name', 'e_src.entity_name')})
                   OR ({" OR ".join(search_terms.copy()).replace('e.entity_name', 'e_tgt.entity_name')})
                ORDER BY er.confidence DESC
                LIMIT 20
                """,
                params,
            )

            for r in (rows or []):
                rel_type = r.get("relationship_type", "")
                evidence = r.get("evidence_text", "")
                src = r.get("source_name", "")
                tgt = r.get("target_name", "")
                summary = f"{src} {rel_type} {tgt}: {evidence}"

                if rel_type in ("CAUSES", "AFFECTS", "MITIGATES"):
                    supporting.append(summary)
                elif rel_type in ("OPPOSES",):
                    contradicting.append(summary)
                else:
                    supporting.append(summary)

        except Exception as e:
            logger.debug(f"Graph evidence query failed: {e}")

        return supporting, contradicting

    # ------------------------------------------------------------------
    # LLM causal analysis
    # ------------------------------------------------------------------

    async def _llm_analyze(
        self,
        claim: str,
        evidence: List[str],
    ) -> Dict[str, Any]:
        """Use LLM to assess causal validity."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            evidence_text = "\n".join(f"- {e}" for e in evidence[:10]) if evidence else "No external evidence provided."

            prompt = (
                f'Claim: "{claim}"\n\n'
                f"Evidence:\n{evidence_text}\n\n"
                "Analyze the causal relationship."
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt=CAUSAL_ANALYSIS_SYSTEM,
                max_tokens=1000,
                temperature=0.1,
            )

            if not response:
                return {}

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            return json.loads(cleaned)

        except json.JSONDecodeError as e:
            logger.warning(f"Causal analysis JSON parse failed: {e}")
            return {}
        except Exception as e:
            logger.warning(f"LLM causal analysis failed: {e}")
            return {}
