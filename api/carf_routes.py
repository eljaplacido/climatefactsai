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
