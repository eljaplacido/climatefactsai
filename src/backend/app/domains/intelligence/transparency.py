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


# Provenance extraction_method slugs that correspond to the claim-extraction
# pipeline step (see app.domains.intelligence.provenance).
_EXTRACTION_METHODS = {
    "article_ingestion_enrichment",
    "url_analysis_claim_extraction",
    "claim_extraction",
}


def _prov_step_description(row: Dict[str, Any]) -> str:
    """Compact human-readable description of one provenance row's prompt +
    retrieval provenance, e.g. "prompt 'claim_extraction' v1.2; fingerprint
    ab12…; retrieval: none". Empty string if nothing recorded."""
    parts: List[str] = []
    pn = row.get("prompt_name")
    if pn:
        pv = row.get("prompt_version")
        parts.append(f"prompt '{pn}'" + (f" {pv}" if pv else ""))
    fp = row.get("prompt_fingerprint")
    if fp:
        parts.append(f"fingerprint {fp}")
    rs = row.get("retrieval_strategy")
    if rs:
        parts.append(f"retrieval: {rs}")
    return "; ".join(parts)


def _build_methodology_from_provenance(
    article_id: str,
    prov_rows: List[Dict[str, Any]],
    adjudicated_count: int,
) -> Dict[str, Any]:
    """Assemble the transparency methodology block from REAL provenance (ML-05).

    The previous implementation hard-coded, for EVERY article: model
    "Claude 3.5 Sonnet / DeepSeek", a fixed 5-source evidence list, and a
    "Bayesian posterior with source prior" — none of which reflected reality
    (real enrichment model is e.g. qwen2.5:7b-instruct/local-gx10; a 0-claim
    article consulted none of those sources; the score is a weighted sum, not a
    posterior). This version only describes pipeline steps that genuinely ran
    for THIS article and marks the rest "not run for this article".
    """
    from shared.reliability_scorer import ReliabilityScorer as _RS

    # Most-recent extraction provenance row for this article, if any.
    extraction_row: Optional[Dict[str, Any]] = None
    for r in prov_rows:
        if (r.get("extraction_method") or "") in _EXTRACTION_METHODS:
            extraction_row = r
            break

    methodology: Dict[str, Any] = {}

    if extraction_row is not None:
        desc = _prov_step_description(extraction_row)
        methodology["claim_extraction"] = {
            "method": "LLM atomic claim extraction",
            "model": extraction_row.get("model_name") or "not recorded",
            "description": (
                "Claims were extracted from this article by the enrichment "
                "pipeline. " + (desc + "." if desc else "")
            ).strip(),
        }
    else:
        methodology["claim_extraction"] = {
            "method": "Not run for this article",
            "description": (
                "No claim-extraction provenance was recorded for this article. "
                f"See the raw audit trail at /api/methodology/audit-trail/article/{article_id}."
            ),
        }

    # Reliability scoring — the REAL computation behind the headline score. The
    # previous stub mislabelled it a "Bayesian posterior with source prior"; it
    # is in fact a deterministic weighted sum. Weights are imported so this can
    # never drift from the live scorer.
    methodology["reliability_scoring"] = {
        "method": "Deterministic weighted sum",
        "description": (
            "The headline reliability score is a deterministic weighted sum of "
            "three normalised (0-1) factors: source_credibility×{s:.2f} + "
            "verified_claims×{c:.2f} + content_relevance×{r:.2f}. Full "
            "disclosure at /api/methodology/credibility-scales."
        ).format(
            s=_RS.WEIGHT_SOURCE_CREDIBILITY,
            c=_RS.WEIGHT_VERIFIED_CLAIMS,
            r=_RS.WEIGHT_CONTENT_RELEVANCE,
        ),
    }

    # Verdict adjudication — only claim it ran if claims were actually checked.
    if adjudicated_count > 0:
        methodology["verdict_adjudication"] = {
            "method": "Per-claim evidence adjudication",
            "description": (
                f"{adjudicated_count} claim(s) from this article were checked "
                "against retrieved evidence, producing per-claim verdicts and "
                "confidence scores (see the Evidence Chains section)."
            ),
        }
    else:
        methodology["verdict_adjudication"] = {
            "method": "Not run for this article",
            "description": (
                "No claims from this article have been fact-checked, so no "
                "verdict adjudication ran. Nothing is asserted here that the "
                "pipeline did not actually compute."
            ),
        }

    return methodology


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
                  a.source_credibility_score, a.claims_count,
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

    # --- 0. Real provenance + verdict counts (feed methodology + breakdown) ---
    # (ML-05) Read the article's ACTUAL claim_provenance rows so the methodology
    # reflects the model/prompt/retrieval that really ran, not a hard-coded stub.
    try:
        prov_rows = db.execute_query(
            """SELECT extraction_method, model_name, prompt_name, prompt_version,
                      prompt_fingerprint, retrieval_strategy, created_at
               FROM claim_provenance
               WHERE article_id = :aid
               ORDER BY created_at DESC""",
            {"aid": article_id},
        ) or []
    except Exception as exc:
        logger.warning(f"claim_provenance lookup failed for {article_id}: {exc}")
        prov_rows = []

    # Verdict / fact-check counts. These also feed the reconciled reliability
    # breakdown below so the displayed factors match the headline score.
    try:
        fc_rows = db.execute_query(
            """SELECT
                   COUNT(*) FILTER (WHERE fc.verification_status = 'VERIFIED') AS verified_count,
                   COUNT(*) FILTER (WHERE fc.verification_status = 'FALSE') AS false_count,
                   COUNT(*) FILTER (WHERE fc.verification_status = 'MISLEADING') AS misleading_count,
                   COUNT(fc.claim_id) AS adjudicated_count
               FROM claims c
               LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
               WHERE c.article_id = :aid""",
            {"aid": article_id},
        ) or []
    except Exception as exc:
        logger.warning(f"fact_check aggregate failed for {article_id}: {exc}")
        fc_rows = []
    fc = fc_rows[0] if fc_rows else {}
    verified_count = int(fc.get("verified_count") or 0)
    false_count = int(fc.get("false_count") or 0)
    misleading_count = int(fc.get("misleading_count") or 0)
    adjudicated_count = int(fc.get("adjudicated_count") or 0)

    # --- 1. Methodology (Record<string, MethodologyStep>) — from real provenance ---
    methodology = _build_methodology_from_provenance(
        article_id, prov_rows, adjudicated_count
    )

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

    # --- 4. Reliability breakdown — reconciled with the headline score (ML-05/06) ---
    # Built from the SAME components + weights that produce the article's
    # reliability_score (source .50 / claims .30 / relevance .20) via the shared
    # ReliabilityScorer.compute_components. The three weighted_scores sum to
    # reliability_score/100, so the breakdown reconciles with the headline number
    # and the documented formula — unlike the previous block, which displayed
    # CARF factors (model_confidence / cross_reference / temporal_relevance) that
    # matched neither the headline nor the formula and invented a 5th factor.
    from shared.reliability_scorer import ReliabilityScorer

    def _to_int(v) -> Optional[int]:
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None

    src_cred = _to_int(art.get("source_credibility_score"))
    if src_cred is None and art.get("source_score"):
        # Fall back to the joined source_credibility.overall_score (0-100).
        src_cred = _to_int(art.get("source_score"))

    rel_input = art.get("content_relevance_score")
    try:
        rel_input = float(rel_input) if rel_input is not None else None
    except (TypeError, ValueError):
        rel_input = None

    # Best-effort 3-axis source scores (mirrors update_article_reliability) so the
    # source component matches the stored headline as closely as possible.
    editorial_axis = factcheck_axis = transparency_axis = None
    try:
        from app.domains.trust.source_tier_service import get_source_3axis_scores
        axes = get_source_3axis_scores(db, art.get("source_name") or "", None)
        if axes:
            editorial_axis, factcheck_axis, transparency_axis = axes
    except Exception as exc:
        logger.debug(f"3-axis lookup failed for transparency {article_id}: {exc}")

    _components = ReliabilityScorer.compute_components(
        source_credibility_score=src_cred,
        total_claims=int(art.get("claims_count") or 0),
        verified_claims=verified_count,
        false_claims=false_count,
        misleading_claims=misleading_count,
        content_relevance_score=rel_input,
        editorial_score=editorial_axis,
        factcheck_score=factcheck_axis,
        transparency_score=transparency_axis,
    )
    reliability_breakdown = {
        key: {
            "label": comp["label"],
            "score": comp["score"],
            "weight": comp["weight"],
            "weighted_score": comp["weighted_score"],
        }
        for key, comp in _components.items()
        if key != "raw_total"
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
