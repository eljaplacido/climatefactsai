"""
Intelligence Domain Schemas

Data models for claim extraction, verification, and decomposed confidence scoring.
Adapted from CARF's epistemic awareness patterns for climate news verification.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class ClaimCategory(str, Enum):
    """Classification of claim types for routing to appropriate verification strategies."""
    SCIENTIFIC_CAUSAL = "scientific_causal"   # Cause-effect claims (e.g., "CO2 causes warming")
    STATISTICAL = "statistical"               # Numeric data claims (e.g., "emissions rose 3%")
    POLICY = "policy"                         # Claims about regulations/agreements
    ANECDOTAL = "anecdotal"                   # Individual observations/events
    PREDICTIVE = "predictive"                 # Future projections/forecasts


class DecomposedConfidence(BaseModel):
    """
    Multi-factor confidence breakdown for transparent credibility scoring.

    Inspired by CARF's ReliabilityFactor model - instead of a single opaque score,
    each factor is independently assessed so users can see WHY a score is what it is.
    """
    model_config = ConfigDict(from_attributes=True)

    model_confidence: float = Field(default=0.5, ge=0.0, le=1.0,
        description="LLM's self-reported confidence in extraction/adjudication")
    source_quality: float = Field(default=0.5, ge=0.0, le=1.0,
        description="Quality/authority of evidence sources used")
    evidence_breadth: float = Field(default=0.5, ge=0.0, le=1.0,
        description="Number and diversity of independent evidence pieces")
    cross_reference_score: float = Field(default=0.5, ge=0.0, le=1.0,
        description="Agreement across multiple independent sources")
    temporal_relevance: float = Field(default=0.5, ge=0.0, le=1.0,
        description="How recent/current the evidence is")
    overall: float = Field(default=0.5, ge=0.0, le=1.0,
        description="Weighted aggregate score")

    @classmethod
    def compute_overall(cls, **factors) -> float:
        """Compute weighted overall from individual factors."""
        weights = {
            "model_confidence": 0.20,
            "source_quality": 0.25,
            "evidence_breadth": 0.20,
            "cross_reference_score": 0.25,
            "temporal_relevance": 0.10,
        }
        total = sum(factors.get(k, 0.5) * w for k, w in weights.items())
        return round(min(1.0, max(0.0, total)), 3)

    @classmethod
    def from_flat_confidence(cls, confidence: float) -> "DecomposedConfidence":
        """Create decomposed confidence from a single flat score (backward compat)."""
        return cls(
            model_confidence=confidence,
            source_quality=confidence,
            evidence_breadth=confidence * 0.8,
            cross_reference_score=confidence * 0.7,
            temporal_relevance=confidence * 0.9,
            overall=confidence,
        )


class EvidenceChainLink(BaseModel):
    """A single step in the evidence chain from claim to verdict."""
    model_config = ConfigDict(from_attributes=True)

    step_number: int = Field(..., description="Order in the chain (1-based)")
    description: str = Field(..., description="What this step established")
    source: str = Field(..., description="Source name")
    source_url: str = Field(default="", description="Link to source")
    retrieval_method: str = Field(default="unknown", description="Which API/tool retrieved this evidence")
    relevance_explanation: str = Field(default="", description="Why this evidence matters for the claim")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supports_claim: Optional[bool] = Field(None, description="True=supports, False=contradicts, None=neutral")


class AtomicClaim(BaseModel):
    """
    An atomic, verifiable claim extracted from an article.

    Atomic means:
    - Self-contained (understandable without context)
    - Singular (one factual assertion)
    - Specific (includes concrete details)
    - Verifiable (can be checked against evidence)
    """
    model_config = ConfigDict(from_attributes=True)

    claim_text: str = Field(..., min_length=10, max_length=1000, description="The claim statement")
    claim_type: str = Field(default="factual", description="factual, opinion, prediction")
    claim_category: ClaimCategory = Field(default=ClaimCategory.STATISTICAL,
        description="Classification for verification routing")
    claim_context: Optional[str] = Field(None, description="Surrounding sentences for context")
    importance_score: float = Field(default=1.0, ge=0.0, le=1.0, description="How central to the article (0-1)")
    extracted_from: Optional[str] = Field(None, description="Source paragraph or section")

    # Metadata (set during extraction)
    extraction_model: Optional[str] = Field(None, description="Model used (e.g., claude-3-5-sonnet)")
    extraction_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class Evidence(BaseModel):
    """
    Supporting or contradicting evidence for a claim.
    """
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(..., description="Evidence source name")
    source_url: str = Field(..., description="Evidence URL")
    source_reliability: str = Field(default="medium", description="high, medium, low")
    content_excerpt: str = Field(..., min_length=10, description="Relevant quote from source")
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="How relevant to claim")
    supports_claim: Optional[bool] = Field(None, description="True=supports, False=contradicts, None=neutral")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    # Tool/API used to retrieve
    retrieval_method: Optional[str] = Field(None, description="google_factcheck, climate_watch, nasa, claude_knowledge")


class Verdict(BaseModel):
    """
    Fact-check verdict for a claim with decomposed confidence.
    """
    model_config = ConfigDict(from_attributes=True)

    verdict: str = Field(..., description="verified, disputed, partially_true, unverified")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in verdict (0-1)")
    justification: str = Field(..., min_length=20, description="Human-readable explanation")
    evidence_summary: str = Field(..., description="Key evidence cited")

    # Evidence used
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)

    # Decomposed confidence (CARF-inspired)
    decomposed_confidence: Optional[DecomposedConfidence] = Field(None,
        description="Multi-factor confidence breakdown")
    evidence_chain: list[EvidenceChainLink] = Field(default_factory=list,
        description="Step-by-step evidence chain from claim to verdict")
    claim_category: Optional[str] = Field(None,
        description="Classification of the claim this verdict applies to")

    # Metadata
    model_used: str = Field(..., description="LLM model used for adjudication")
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    verification_method: str = Field(default="automated", description="automated, human_reviewed, rapid")


class VerificationResult(BaseModel):
    """
    Complete verification result for an article.

    Contains aggregate scores with decomposed confidence breakdown.
    """
    article_id: UUID
    claims_extracted: int = 0
    claims_verified: int = 0
    claims_disputed: int = 0
    claims_unverified: int = 0

    # Aggregate scores
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    article_credibility: float = Field(default=0.0, ge=0.0, le=1.0)
    credibility_level: str = Field(default="medium", description="high, medium, low")

    # Decomposed confidence (article-level aggregate)
    decomposed_confidence: Optional[DecomposedConfidence] = None
    claims_by_category: dict[str, int] = Field(default_factory=dict,
        description="Count of claims per category")
    insight_summary: Optional[str] = Field(None,
        description="AI-generated summary of key findings")

    # Processing metadata
    processing_started_at: datetime
    processing_completed_at: Optional[datetime] = None
    total_processing_time_seconds: Optional[float] = None

    # Provenance
    provenance: dict = Field(default_factory=dict,
        description="Models, APIs, timestamps used")

    # Status
    status: str = Field(default="in_progress", description="in_progress, completed, failed")
    error_message: Optional[str] = None


class ReliabilityBreakdown(BaseModel):
    """Breakdown of reliability scoring factors for frontend display."""
    factors: dict[str, dict] = Field(default_factory=dict,
        description="factor_name -> {weight, score, weighted_score, label}")


class ClaimExtractionRequest(BaseModel):
    """
    Request to extract claims from text.
    """
    text: str = Field(..., min_length=100, description="Article text to analyze")
    max_claims: int = Field(default=20, ge=1, le=50, description="Max claims to extract")
    language: str = Field(default="en", description="Text language code")


class VerificationRequest(BaseModel):
    """
    Request to verify an article.
    """
    article_id: UUID
    priority: str = Field(default="normal", description="normal, high, urgent")
    verification_method: str = Field(default="automated", description="automated, human_reviewed, rapid")


class ClimateEpistemicState(BaseModel):
    """
    Unified intelligence state for a climate article (CARF EpistemicState pattern).

    Bundles all intelligence signals from the verification pipeline into a single
    object that flows through: ClaimExtractor → EvidenceOrchestrator →
    BayesianCredibility → EditorialGate.
    """
    article_id: str
    content_type: str = "news_article"

    # Claim extraction
    claims: list = Field(default_factory=list)
    claims_count: int = 0
    claims_by_category: dict = Field(default_factory=dict)

    # Evidence
    evidence_chain: list = Field(default_factory=list)
    evidence_sources_used: list = Field(default_factory=list)
    rag_matches: int = 0

    # Verification
    verdicts: list = Field(default_factory=list)
    verified_claims_count: int = 0
    disputed_claims_count: int = 0

    # Credibility
    reliability_score: Optional[float] = None
    overall_credibility: Optional[str] = None
    decomposed_confidence: Optional[DecomposedConfidence] = None
    bayesian_posterior: Optional[float] = None

    # Research-specific
    doi: Optional[str] = None
    publication_venue: Optional[str] = None
    research_prior: Optional[float] = None

    # Weather validation
    weather_validated: bool = False
    weather_verdict: Optional[str] = None
    weather_deviation_pct: Optional[float] = None

    # Editorial gate
    editorial_decision: Optional[str] = None
    editorial_reason: Optional[str] = None
    risk_factors: list = Field(default_factory=list)

    # Pipeline metadata
    pipeline_version: str = "2.0.0"
    processed_at: Optional[str] = None
    processing_time_ms: Optional[int] = None
