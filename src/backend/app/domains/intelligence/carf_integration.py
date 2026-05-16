"""
CARF Integration Service — Bridges CliLens.AI with Project CARF's
Complexity-Adaptive & Context-Aware Reasoning Fabric.

CARF provides:
1. Cynefin complexity classification for climate articles
2. Causal inference for claim verification (1,138x vs raw LLM)
3. Counterfactual reasoning (Pearl's 3-level hierarchy)
4. Hallucination detection for AI-generated content
5. Policy compliance checking (EU AI Act)

Integration is via HTTP proxy to CARF's FastAPI backend.
Falls back gracefully when CARF is unavailable.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

CARF_BASE_URL = os.getenv("CARF_API_URL", "http://localhost:8000")
CARF_API_KEY = os.getenv("CARF_API_KEY", "")
CARF_TIMEOUT = int(os.getenv("CARF_TIMEOUT", "30"))


class CARFIntegration:
    """Client for CARF reasoning fabric integration."""

    def __init__(self):
        self.base_url = CARF_BASE_URL
        self.api_key = CARF_API_KEY
        self.timeout = CARF_TIMEOUT

    @property
    def available(self) -> bool:
        return bool(self.base_url)

    async def _request(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.available:
            return None

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}{endpoint}", json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"CARF request to {endpoint} returned {resp.status_code}")
                return None
        except httpx.ConnectError:
            logger.debug("CARF service not reachable")
            return None
        except Exception as e:
            logger.warning(f"CARF request failed: {e}")
            return None

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "details": resp.json()}
        except Exception:
            pass
        return {"status": "unavailable"}

    async def classify_complexity(self, text: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Classify article/claim complexity using Cynefin framework."""
        result = await self._request("/query", {
            "hypothesis": text[:3000], "context": context or "climate_news_analysis", "mode": "classify_only",
        })
        if not result:
            return self._fallback_classify(text)

        return {
            "domain": result.get("cynefin_domain", "disorder"),
            "confidence": result.get("classification_confidence", 0.5),
            "routing": result.get("routing_recommendation", ""),
            "source": "carf",
        }

    def _fallback_classify(self, text: str) -> Dict[str, Any]:
        """Local fallback when CARF service is unreachable.

        Pre-2026-05-16 this was a 4-keyword heuristic that would label any
        text with three "study" mentions as 'complicated' regardless of
        substance — the audit (T3) flagged it as misleading methodology
        because the transparency endpoint advertised "Bayesian + Guardian-
        lite" while this stub ran in production.

        Now delegates to CynefinRouter, which has keyword scoring + a
        structured-JSON LLM classifier (the LLM prompt itself was ported
        from projectcarfcynepic). Still local-only — no HTTP — so CARF
        service deployment can wait.
        """
        try:
            from app.domains.intelligence.cynefin_router import CynefinRouter

            router = CynefinRouter()
            result = router.classify(text)
            return {
                "domain": result["domain"],
                "confidence": result["confidence"],
                "routing": result["recommended_strategy"],
                "source": result.get("source", "cynefin_router_local"),
                "reasoning": result.get("reasoning"),
            }
        except Exception as e:
            logger.warning(f"CynefinRouter fallback failed: {e}")
            return {
                "domain": "disorder",
                "confidence": 0.2,
                "routing": "fallback_disorder",
                "source": "error",
            }

    async def analyze_causal_claim(self, claim: str, evidence: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Run causal inference on a climate claim using CARF's DoWhy/EconML engine."""
        result = await self._request("/query", {
            "hypothesis": claim, "context": "causal_verification",
            "evidence": evidence or [], "analysis_type": "causal",
        })
        if not result:
            return {"status": "carf_unavailable", "causal_analysis": None,
                    "note": "CARF causal engine not available. Using LLM-only analysis."}

        return {
            "status": "completed", "causal_effect": result.get("causal_effect"),
            "confidence": result.get("confidence"), "methodology": result.get("methodology"),
            "counterfactual": result.get("counterfactual_result"),
            "provenance": result.get("provenance_chain"), "source": "carf_causal_engine",
        }

    async def counterfactual_analysis(self, scenario: str, intervention: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Run counterfactual analysis using Pearl's three-level causal hierarchy."""
        result = await self._request("/query", {
            "hypothesis": scenario, "intervention": intervention,
            "context": "counterfactual_analysis", "analysis_type": "counterfactual",
        })
        if not result:
            return None

        return {
            "scenario": scenario, "intervention": intervention,
            "causal_level": result.get("causal_level", "unknown"),
            "counterfactual_outcome": result.get("counterfactual_result"),
            "confidence": result.get("confidence"), "explanation": result.get("explanation"),
            "source": "carf_counterfactual_engine",
        }

    async def check_hallucination(self, generated_text: str, source_texts: List[str]) -> Optional[Dict[str, Any]]:
        """Check AI-generated text for hallucinations using H-Neuron sentinel."""
        result = await self._request("/query", {
            "hypothesis": generated_text, "evidence": source_texts[:5],
            "context": "hallucination_detection", "analysis_type": "grounding_check",
        })
        if not result:
            return None

        return {
            "hallucination_risk": result.get("hallucination_risk", 0.5),
            "grounded": result.get("is_grounded", True),
            "flagged_segments": result.get("flagged_segments", []),
            "confidence": result.get("confidence"), "source": "carf_h_neuron",
        }

    async def check_eu_ai_compliance(self, analysis_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check analysis output against EU AI Act requirements."""
        result = await self._request("/query", {
            "hypothesis": str(analysis_output)[:5000],
            "context": "eu_ai_act_compliance", "analysis_type": "compliance",
        })
        if not result:
            return {"compliant": True, "note": "CARF compliance check unavailable", "source": "fallback"}

        return {
            "compliant": result.get("is_compliant", True), "violations": result.get("violations", []),
            "audit_trail": result.get("audit_trail"),
            "articles_checked": ["Art. 9", "Art. 12", "Art. 13", "Art. 14"], "source": "carf_guardian",
        }

    async def enhanced_article_analysis(self, article_id: str, db=None) -> Optional[Dict[str, Any]]:
        """Run CARF-enhanced analysis on an article."""
        if db is None:
            from app.core.database import get_db
            db = get_db()

        rows = db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') as text, country_code
               FROM articles WHERE article_id = :id""",
            {"id": article_id},
        )
        if not rows:
            return None

        article = rows[0]
        full_text = f"{article['title']} {article.get('text', '')} {article.get('excerpt', '')}".strip()

        classification, causal, compliance = await asyncio.gather(
            self.classify_complexity(full_text),
            self.analyze_causal_claim(full_text),
            self.check_eu_ai_compliance({"article": full_text[:2000]}),
            return_exceptions=True,
        )

        if isinstance(classification, Exception):
            classification = self._fallback_classify(full_text)
        if isinstance(causal, Exception):
            causal = None
        if isinstance(compliance, Exception):
            compliance = None

        health = await self.health_check()
        return {
            "article_id": article_id,
            "carf_available": health.get("status") == "healthy",
            "complexity_classification": classification,
            "causal_analysis": causal,
            "compliance_check": compliance,
        }


_carf_client: Optional[CARFIntegration] = None


def get_carf() -> CARFIntegration:
    global _carf_client
    if _carf_client is None:
        _carf_client = CARFIntegration()
    return _carf_client
