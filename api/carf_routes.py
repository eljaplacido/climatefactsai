"""
CARF Integration Routes — Expose CARF reasoning fabric capabilities.

Provides endpoints for complexity classification, causal analysis,
counterfactual reasoning, and hallucination detection.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from shared.logger import setup_logging
from api.auth_routes import get_current_user, get_optional_user

logger = setup_logging("carf")
router = APIRouter(prefix="/api/carf", tags=["CARF Integration"])


class ComplexityRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10000)
    context: Optional[str] = None


class CausalClaimRequest(BaseModel):
    claim: str = Field(..., min_length=10, max_length=5000)
    evidence: List[str] = Field(default_factory=list)


class CounterfactualRequest(BaseModel):
    scenario: str = Field(..., min_length=10, max_length=5000)
    intervention: Optional[str] = None


class HallucinationCheckRequest(BaseModel):
    generated_text: str = Field(..., min_length=10, max_length=10000)
    source_texts: List[str] = Field(default_factory=list)


class ArticleAnalysisRequest(BaseModel):
    article_id: str


class AnalyzeClaimRequest(BaseModel):
    claim_text: str = Field(..., min_length=10, max_length=5000)
    evidence_texts: List[str] = Field(default_factory=list)
    context: Optional[str] = None


class FullHallucinationCheckRequest(BaseModel):
    generated_text: str = Field(..., min_length=10, max_length=10000)
    source_texts: List[str] = Field(default_factory=list)


@router.get("/status")
async def carf_status():
    """Check CARF service availability and capabilities."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    health = await carf.health_check()
    return {
        "configured": carf.available,
        "health": health,
        "capabilities": [
            "cynefin_classification",
            "causal_inference",
            "counterfactual_reasoning",
            "hallucination_detection",
            "eu_ai_compliance",
        ],
    }


@router.post("/classify")
async def classify_complexity(request: ComplexityRequest, user: dict = Depends(get_optional_user)):
    """Classify text complexity using Cynefin framework."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    result = await carf.classify_complexity(request.text, request.context)
    if not result:
        raise HTTPException(status_code=503, detail="Classification unavailable")
    return result


@router.post("/causal")
async def analyze_causal_claim(request: CausalClaimRequest, user: dict = Depends(get_optional_user)):
    """Run causal inference on a climate claim."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    result = await carf.analyze_causal_claim(request.claim, request.evidence)
    return result or {"status": "unavailable", "note": "CARF causal engine not reachable"}


@router.post("/counterfactual")
async def counterfactual_analysis(request: CounterfactualRequest, user: dict = Depends(get_current_user)):
    """Run counterfactual analysis on a climate scenario."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    result = await carf.counterfactual_analysis(request.scenario, request.intervention)
    return result or {"status": "unavailable"}


@router.post("/hallucination-check")
async def check_hallucination(request: HallucinationCheckRequest, user: dict = Depends(get_current_user)):
    """Check AI-generated text for hallucinations."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    result = await carf.check_hallucination(request.generated_text, request.source_texts)
    return result or {"status": "unavailable"}


@router.post("/article-analysis")
async def carf_article_analysis(request: ArticleAnalysisRequest, user: dict = Depends(get_current_user)):
    """Run CARF-enhanced analysis on an article."""
    from app.domains.intelligence.carf_integration import get_carf
    carf = get_carf()
    result = await carf.enhanced_article_analysis(request.article_id)
    if not result:
        raise HTTPException(status_code=404, detail="Article not found")
    return result


@router.post("/analyze-claim")
async def analyze_claim(request: AnalyzeClaimRequest, user: dict = Depends(get_optional_user)):
    """
    Analyze a causal claim with full CARF pipeline.

    Routes through Cynefin complexity classification, then applies the
    appropriate analysis depth — from simple lookup to full causal reasoning.
    Includes hallucination checks when evidence is provided.
    """
    from shared.database import get_postgres
    from app.domains.intelligence.cynefin_router import CynefinRouter
    from app.domains.intelligence.causal_claim_analyzer import CausalClaimAnalyzer
    from app.domains.intelligence.hallucination_detector import HallucinationDetector

    db = get_postgres()

    # Step 1: Cynefin complexity classification
    router_ctx = {"context": request.context} if request.context else None
    cynefin = CynefinRouter()
    classification = cynefin.classify(request.claim_text, context=router_ctx)

    # Step 2: Causal analysis
    analyzer = CausalClaimAnalyzer(db)
    causal_result = await analyzer.analyze(
        claim_text=request.claim_text,
        evidence=request.evidence_texts or None,
    )

    # Step 3: Hallucination check (if evidence provided)
    hallucination_result = None
    if request.evidence_texts:
        detector = HallucinationDetector(db)
        hallucination_result = await detector.check(
            generated_text=request.claim_text,
            source_texts=request.evidence_texts,
        )

    return {
        "domain": classification,
        "analysis": causal_result,
        "causal_assessment": {
            "is_causal": causal_result.get("is_causal", False),
            "confidence": causal_result.get("causal_confidence", 0.0),
            "cause": causal_result.get("cause_entity", ""),
            "effect": causal_result.get("effect_entity", ""),
        },
        "hallucination_check": hallucination_result,
        "confidence": causal_result.get("causal_confidence", 0.0),
    }


@router.post("/hallucination-check-full")
async def hallucination_check_full(request: FullHallucinationCheckRequest, user: dict = Depends(get_optional_user)):
    """
    Full hallucination assessment against source texts.

    Checks entity overlap, statistic accuracy, and semantic grounding
    of generated text against provided source documents.
    """
    from shared.database import get_postgres
    from app.domains.intelligence.hallucination_detector import HallucinationDetector

    db = get_postgres()
    detector = HallucinationDetector(db)
    result = await detector.check(
        generated_text=request.generated_text,
        source_texts=request.source_texts,
    )
    return result


@router.get("/entity-graph/{article_id}")
async def get_entity_graph(article_id: str, user: dict = Depends(get_optional_user)):
    """
    Return the knowledge graph entities and relationships for a specific article.

    Returns entities extracted from the article, their relationships,
    and articles connected via shared entities.

    End2End audit + KG-Robustness-Audit-2026-05-27.md: the canonical
    `infrastructure/database/migrations/versions/` tree does not include
    the knowledge_graph schema (it lives only in the legacy `migrations/`
    path), so on production the JOINs below raise `relation
    "article_entities" does not exist`. Soft-fail to a 200 + empty graph
    so the frontend renders the "KG not populated for this article yet"
    empty state instead of a hard 500. The honest fix is mig 049 +
    spaCy NER worker — see the KG audit doc for the 3-phase sequencing.
    """
    from shared.database import get_postgres

    db = get_postgres()

    def _empty_graph(reason: str) -> dict:
        return {
            "article_id": article_id,
            "entities": [],
            "relationships": [],
            "connected_articles": [],
            "status": "kg_not_populated",
            "reason": reason,
            "next_steps_doc": (
                "docs/improvementplans/KG-Robustness-Audit-2026-05-27.md"
            ),
        }

    # Get entities for this article (soft-fail if the schema isn't deployed).
    try:
        entities = db.execute_query(
            """
            SELECT
                e.entity_id,
                e.entity_name,
                e.entity_type,
                e.description,
                e.article_count,
                ae.mention_count,
                ae.salience
            FROM article_entities ae
            JOIN entities e ON e.entity_id = ae.entity_id
            WHERE ae.article_id = :aid
            ORDER BY ae.salience DESC
            """,
            {"aid": article_id},
        )
    except Exception as exc:
        logger.debug(f"entity-graph schema missing for {article_id}: {exc}")
        return _empty_graph(
            "knowledge_graph schema not deployed (mig 013 legacy path only)"
        )
    if not entities:
        return _empty_graph("no entities extracted for this article yet")

    entity_ids = [str(e["entity_id"]) for e in entities]

    # Get relationships between these entities
    placeholders = ", ".join(f":eid{i}" for i in range(len(entity_ids)))
    eid_params = {f"eid{i}": eid for i, eid in enumerate(entity_ids)}

    relationships = db.execute_query(
        f"""
        SELECT
            er.relationship_id,
            e_src.entity_name AS source_entity,
            e_tgt.entity_name AS target_entity,
            er.relationship_type,
            er.strength,
            er.confidence,
            er.evidence_text
        FROM entity_relationships er
        JOIN entities e_src ON e_src.entity_id = er.source_entity_id
        JOIN entities e_tgt ON e_tgt.entity_id = er.target_entity_id
        WHERE er.source_entity_id IN ({placeholders})
           OR er.target_entity_id IN ({placeholders})
        ORDER BY er.confidence DESC
        LIMIT 50
        """,
        eid_params,
    )

    # Get connected articles (via shared entities, excluding current)
    connected = db.execute_query(
        f"""
        SELECT DISTINCT
            a.article_id,
            a.title,
            a.source_name,
            a.overall_credibility
        FROM article_entities ae2
        JOIN articles a ON a.article_id = ae2.article_id
        WHERE ae2.entity_id IN ({placeholders})
          AND ae2.article_id != :current_aid
        ORDER BY a.title
        LIMIT 20
        """,
        {**eid_params, "current_aid": article_id},
    )

    return {
        "article_id": article_id,
        "entities": [
            {
                "entity_id": str(e["entity_id"]),
                "name": e.get("entity_name", ""),
                "type": e.get("entity_type", ""),
                "description": e.get("description", ""),
                "article_count": e.get("article_count", 0),
                "mention_count": e.get("mention_count", 0),
                "salience": float(e.get("salience", 0)),
            }
            for e in entities
        ],
        "relationships": [
            {
                "relationship_id": str(r["relationship_id"]),
                "source_entity": r.get("source_entity", ""),
                "target_entity": r.get("target_entity", ""),
                "relationship_type": r.get("relationship_type", ""),
                "strength": float(r.get("strength", 0)),
                "confidence": float(r.get("confidence", 0)),
                "evidence_text": r.get("evidence_text", ""),
            }
            for r in (relationships or [])
        ],
        "connected_articles": [
            {
                "article_id": str(c["article_id"]),
                "title": c.get("title", ""),
                "source_name": c.get("source_name", ""),
                "credibility": c.get("overall_credibility", "UNKNOWN"),
            }
            for c in (connected or [])
        ],
    }
