"""
Transparency API — CARF-inspired score explanation endpoint.

Provides detailed methodology breakdown, evidence chains, confidence
intervals, and source reliability context for Professional-tier users.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v2/articles", tags=["Transparency"])


class TransparencyResponse(BaseModel):
    """Full transparency breakdown matching frontend TransparencyData interface."""
    article_id: str
    title: str
    methodology: Dict[str, Any]
    reliability_breakdown: Dict[str, Any]
    decomposed_confidence: Optional[Dict[str, Any]] = None
    claims: List[Dict[str, Any]]
    source_profile: Dict[str, Any]
    causal_analysis: Optional[Dict[str, Any]] = None


def _parse_jsonb(value) -> Any:
    """Parse JSONB that may arrive as str or already-decoded."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


@router.get("/{article_id}/transparency", response_model=TransparencyResponse)
async def get_article_transparency(
    article_id: str,
    db=Depends(get_db),
):
    """
    Get full transparency breakdown for an article.

    Returns methodology, reliability breakdown, decomposed confidence,
    claims with evidence chains, source profile, and causal analysis.
    """
    # Get article base data + source credibility
    article_rows = db.execute_query(
        """SELECT a.article_id, a.title, a.source_name, a.reliability_score,
                  a.overall_credibility, a.content_relevance_score,
                  a.decomposed_confidence AS article_decomposed_confidence,
                  a.source_profile_id,
                  COALESCE(sc.overall_score, 0) as source_score,
                  COALESCE(sc.factual_reporting_score, 0) as factual_score,
                  COALESCE(sc.transparency_score, 0) as transparency_score,
                  COALESCE(sc.reliability_tier, 'public') as reliability_tier
           FROM articles a
           LEFT JOIN source_credibility sc ON LOWER(a.source_name) = LOWER(sc.source_name)
           WHERE a.article_id = :aid""",
        {"aid": article_id},
    )

    if not article_rows:
        raise HTTPException(status_code=404, detail="Article not found")

    art = article_rows[0]

    # --- 1. Methodology (Record<string, MethodologyStep>) ---
    methodology = {
        "claim_extraction": {
            "method": "LLM-based atomic decomposition",
            "model": "Claude 3.5 Sonnet / DeepSeek",
            "description": "Articles are decomposed into atomic, verifiable claims using structured prompting with claim categorisation (scientific, statistical, policy, anecdotal, predictive).",
        },
        "evidence_retrieval": {
            "method": "Multi-source evidence aggregation",
            "sources": ["Google Fact Check", "Climate Watch", "NASA GISS", "Open-Meteo", "Perplexity"],
            "description": "Each claim is cross-referenced against multiple authoritative climate data sources to gather supporting and contradicting evidence.",
        },
        "verdict_adjudication": {
            "method": "Bayesian posterior with source prior",
            "model": "Claude 3.5 Sonnet / DeepSeek",
            "description": "Evidence is weighed against claims using LLM reasoning with Guardian-lite policy checks, producing decomposed confidence scores and final verdicts.",
        },
    }

    # --- 2. Claims with evidence chains ---
    claim_rows = db.execute_query(
        """SELECT c.claim_id, c.claim_text, c.claim_type, c.claim_category,
                  fc.verification_status, fc.confidence_score,
                  fc.justification, fc.evidence, fc.evidence_chain,
                  fc.decomposed_confidence
           FROM claims c
           LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
           WHERE c.article_id = :aid
           ORDER BY c.created_at""",
        {"aid": article_id},
    )

    claims = []
    causal_analyses = {}
    for row in (claim_rows or []):
        # Parse evidence_chain JSONB
        ec_raw = _parse_jsonb(row.get("evidence_chain"))
        evidence_chain_links = []
        if isinstance(ec_raw, list):
            for i, link in enumerate(ec_raw):
                if isinstance(link, dict):
                    evidence_chain_links.append({
                        "step_number": link.get("step_number", i + 1),
                        "description": link.get("description") or link.get("finding", ""),
                        "source": link.get("source", "Unknown"),
                        "source_url": link.get("source_url", ""),
                        "retrieval_method": link.get("retrieval_method"),
                        "relevance_explanation": link.get("relevance_explanation"),
                        "confidence": link.get("confidence", 0),
                        "supports_claim": link.get("supports_claim", True),
                    })

        claims.append({
            "claim_text": row.get("claim_text", ""),
            "verdict": row.get("verification_status", "unverified"),
            "confidence_score": float(row.get("confidence_score") or 0),
            "evidence_chain": evidence_chain_links,
            "justification": row.get("justification", ""),
        })

        # Extract causal analysis if present
        if isinstance(ec_raw, dict) and ec_raw.get("causal_analysis"):
            causal = ec_raw["causal_analysis"]
            causal["claim_id"] = str(row.get("claim_id", ""))
            causal_analyses[str(row.get("claim_id", ""))] = causal

    # --- 3. Article-level decomposed confidence ---
    article_dc = _parse_jsonb(art.get("article_decomposed_confidence"))
    if not article_dc and claim_rows:
        # Compute aggregate from per-claim decomposed confidence
        all_dc = []
        for row in claim_rows:
            dc = _parse_jsonb(row.get("decomposed_confidence"))
            if isinstance(dc, dict) and dc.get("overall"):
                all_dc.append(dc)
        if all_dc:
            n = len(all_dc)
            article_dc = {
                "model_confidence": sum(d.get("model_confidence", 0) for d in all_dc) / n,
                "source_quality": sum(d.get("source_quality", 0) for d in all_dc) / n,
                "evidence_breadth": sum(d.get("evidence_breadth", 0) for d in all_dc) / n,
                "cross_reference_score": sum(d.get("cross_reference_score", 0) for d in all_dc) / n,
                "temporal_relevance": sum(d.get("temporal_relevance", 0) for d in all_dc) / n,
                "overall": sum(d.get("overall", 0) for d in all_dc) / n,
            }

    # --- 4. Reliability breakdown (from decomposed confidence factors) ---
    reliability_breakdown = {}
    if article_dc and isinstance(article_dc, dict):
        factor_config = [
            ("model_confidence", "AI Model Confidence", 0.20),
            ("source_quality", "Source Quality", 0.30),
            ("evidence_breadth", "Evidence Breadth", 0.20),
            ("cross_reference_score", "Cross-Reference Score", 0.15),
            ("temporal_relevance", "Temporal Relevance", 0.15),
        ]
        for key, label, weight in factor_config:
            score = article_dc.get(key, 0)
            reliability_breakdown[key] = {
                "label": label,
                "score": score,
                "weight": weight,
                "weighted_score": round(score * weight, 4),
            }
    else:
        # Fallback: build from source credibility scores
        source_score = art.get("source_score", 0) / 100.0
        factual_score = art.get("factual_score", 0) / 100.0
        transparency_val = art.get("transparency_score", 0) / 100.0
        reliability_breakdown = {
            "source_credibility": {
                "label": "Source Credibility",
                "score": source_score,
                "weight": 0.40,
                "weighted_score": round(source_score * 0.40, 4),
            },
            "factual_reporting": {
                "label": "Factual Reporting",
                "score": factual_score,
                "weight": 0.35,
                "weighted_score": round(factual_score * 0.35, 4),
            },
            "transparency": {
                "label": "Transparency",
                "score": transparency_val,
                "weight": 0.25,
                "weighted_score": round(transparency_val * 0.25, 4),
            },
        }

    # --- 5. Source profile ---
    source_profile = {
        "source_name": art.get("source_name", "Unknown"),
        "credibility_score": (art.get("source_score", 0)) / 100.0,
        "reliability_tier": art.get("reliability_tier", "public"),
        "editorial_standards": "unknown",
    }

    # Try to get richer data from source_profiles table
    if art.get("source_profile_id"):
        sp_rows = db.execute_query(
            """SELECT source_name, credibility_score, editorial_standards, transparency_level
               FROM source_profiles WHERE source_id = :sid""",
            {"sid": str(art["source_profile_id"])},
        )
        if sp_rows:
            sp = sp_rows[0]
            source_profile = {
                "source_name": sp.get("source_name", art.get("source_name", "Unknown")),
                "credibility_score": (sp.get("credibility_score", 0)) / 100.0,
                "reliability_tier": art.get("reliability_tier", "public"),
                "editorial_standards": sp.get("editorial_standards", "unknown"),
            }
    else:
        # Fallback: try matching by source name
        sp_rows = db.execute_query(
            """SELECT source_name, credibility_score, editorial_standards, transparency_level
               FROM source_profiles WHERE LOWER(source_name) = LOWER(:sname)""",
            {"sname": art.get("source_name", "")},
        )
        if sp_rows:
            sp = sp_rows[0]
            source_profile = {
                "source_name": sp.get("source_name", art.get("source_name", "Unknown")),
                "credibility_score": (sp.get("credibility_score", 0)) / 100.0,
                "reliability_tier": art.get("reliability_tier", "public"),
                "editorial_standards": sp.get("editorial_standards", "unknown"),
            }

    return TransparencyResponse(
        article_id=article_id,
        title=art.get("title", "Untitled"),
        methodology=methodology,
        reliability_breakdown=reliability_breakdown,
        decomposed_confidence=article_dc,
        claims=claims,
        source_profile=source_profile,
        causal_analysis=causal_analyses or None,
    )
