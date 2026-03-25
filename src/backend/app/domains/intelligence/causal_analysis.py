"""
Causal Analysis Service — CARF-inspired causal claim analysis.

Uses LLM to extract causal relationships from verified climate claims,
identifying cause-effect chains, mechanisms, and counterfactuals.
"""

import json
import os
from typing import Any, Dict, List, Optional

from app.core.database import Database, get_db
from app.core.logging import get_logger

try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None

logger = get_logger(__name__)


class CausalAnalysisService:
    """Extract and analyze causal relationships in climate claims."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = OpenAIClient(api_key=api_key, base_url=base_url) if api_key and OpenAIClient else None
        if not self.client:
            logger.warning("CausalAnalysisService: No DeepSeek API key — causal analysis unavailable")

    async def analyze_claim(
        self,
        claim_text: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
        article_context: str = "",
    ) -> Dict[str, Any]:
        """
        Perform causal analysis on a climate claim.

        Returns dict with: cause, effect, mechanism, confidence,
        counterfactual, causal_chain.
        """
        if not self.client:
            return {"error": "LLM client not configured"}

        evidence_text = ""
        if evidence:
            evidence_text = "\n".join(
                f"- {e.get('source', 'Unknown')}: {e.get('description', e.get('text', ''))}"
                for e in evidence[:5]
            )

        prompt = f"""You are a climate science analyst specializing in causal reasoning.

CLAIM: "{claim_text}"

ARTICLE CONTEXT: {article_context[:2000]}

SUPPORTING EVIDENCE:
{evidence_text or "No additional evidence provided."}

TASK: Analyze the causal relationships in this claim. Return ONLY valid JSON:

{{
  "cause": "The primary cause identified in the claim",
  "effect": "The primary effect or outcome",
  "mechanism": "The causal mechanism connecting cause to effect",
  "confidence": 0.75,
  "counterfactual": "What would happen if the cause were absent",
  "causal_chain": [
    "Step 1: Initial cause",
    "Step 2: Intermediate effect",
    "Step 3: Final outcome"
  ],
  "causal_type": "direct|indirect|correlational|spurious",
  "strength": "strong|moderate|weak"
}}

If the claim does not contain a causal relationship, set causal_type to "none" and confidence to 0."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.1,
            )
            text = response.choices[0].message.content.strip()

            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            result.setdefault("confidence", 0.5)
            result.setdefault("causal_type", "unknown")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Causal analysis JSON parse failed: {e}")
            return {"error": "Failed to parse causal analysis", "raw": text[:500]}
        except Exception as e:
            logger.error(f"Causal analysis failed: {e}")
            return {"error": str(e)}

    async def store_analysis(self, claim_id: str, analysis: Dict[str, Any]) -> bool:
        """Store causal analysis results on the fact_checks table."""
        try:
            self.db.execute_update(
                """UPDATE fact_checks
                   SET metadata = COALESCE(metadata, '{}'::jsonb) || :causal_data::jsonb,
                       updated_at = NOW()
                   WHERE claim_id = :claim_id""",
                {
                    "claim_id": claim_id,
                    "causal_data": json.dumps({"causal_analysis": analysis}),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store causal analysis for claim {claim_id}: {e}")
            return False
