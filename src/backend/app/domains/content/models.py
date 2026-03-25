"""
Content Domain Models

Pydantic models representing articles, claims, and fact-checks.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class Article(BaseModel):
    """
    Article summary model for listing views.
    """
    model_config = ConfigDict(from_attributes=True)

    article_id: UUID = Field(..., description="Unique article identifier")
    title: str = Field(..., min_length=1, max_length=1000)
    url: str = Field(..., description="Source URL")
    source_name: str = Field(..., description="Publisher name")
    author: Optional[str] = None
    published_date: Optional[datetime] = None

    # Content
    excerpt: Optional[str] = Field(None, max_length=500)

    # Credibility
    reliability_score: Optional[int] = Field(None, ge=0, le=100, description="Overall reliability 0-100")
    overall_credibility: Optional[str] = Field(None, description="high, medium, low")
    source_credibility_score: Optional[int] = Field(None, ge=0, le=100)

    # Classification
    country_code: Optional[str] = Field(None, max_length=2)
    language_code: Optional[str] = Field(None, max_length=5)
    tags: list[str] = Field(default_factory=list)

    # Metrics
    claim_count: int = Field(default=0, ge=0)
    verified_claim_count: int = Field(default=0, ge=0)

    # Claims processing status
    claims_status: Optional[str] = Field(
        default="pending",
        description="Status of claims extraction: pending, processing, completed, failed"
    )
    claims_error_message: Optional[str] = Field(
        default=None,
        description="Error message if claims extraction failed"
    )
    claims_processed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when claims extraction was completed or failed"
    )

    # Trust & compliance metadata required by refactor docs
    cta_url: Optional[str] = Field(
        default=None,
        description="CTA link directing readers to the original publisher"
    )
    summary_type: Optional[str] = Field(
        default=None,
        description="AI_GENERATED, HUMAN_EDITED, or HYBRID"
    )
    video_url: Optional[str] = None
    video_status: Optional[str] = None
    hitl_status: Optional[str] = None
    compliance_flags: Optional[Dict[str, Any]] = None
    trust_score: Optional[int] = Field(default=None, ge=0, le=100)
    publisher_trust_score: Optional[int] = Field(default=None, ge=0, le=100)
    nutrition_label: Optional[Dict[str, Any]] = None

    # Content category
    content_category: Optional[str] = Field(
        default=None,
        description="Content category: climate_science, sustainability, circular_economy, green_transition, localized_forecast, policy"
    )
    executive_brief: Optional[str] = Field(
        default=None,
        description="2-3 sentence executive brief for article card previews"
    )

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None


class Claim(BaseModel):
    """
    Extracted claim from an article.
    """
    model_config = ConfigDict(from_attributes=True)

    claim_id: UUID
    article_id: UUID
    claim_text: str = Field(..., min_length=1)
    claim_type: Optional[str] = Field(None, description="factual, opinion, prediction")
    claim_context: Optional[str] = None
    claim_category: Optional[str] = Field(None, description="scientific_causal, statistical, policy, anecdotal, predictive")
    importance_score: Optional[float] = Field(None, ge=0, le=1)

    # Metadata
    extracted_at: datetime
    extraction_model: Optional[str] = None


class Evidence(BaseModel):
    """
    Evidence for a claim.
    """
    source: str
    source_url: str
    source_reliability: Optional[str] = None
    content_excerpt: str
    relevance_score: Optional[float] = Field(None, ge=0, le=1)
    supports_claim: Optional[bool] = None
    retrieved_at: Optional[datetime] = None


class FactCheck(BaseModel):
    """
    Fact-check verdict for a claim.
    """
    model_config = ConfigDict(from_attributes=True)
    
    fact_check_id: UUID
    claim_id: UUID
    
    # Verdict
    verdict: str = Field(..., description="verified, disputed, partially_true, unverified")
    verification_status: Optional[str] = Field(None, description="Alias for verdict for frontend compatibility")
    confidence_score: float = Field(..., ge=0, le=1)
    justification: Optional[str] = None
    
    # Evidence
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    # Decomposed confidence and evidence chain (CARF-inspired)
    decomposed_confidence: Optional[Dict[str, Any]] = Field(None, description="Multi-factor confidence breakdown")
    evidence_chain: list[Dict[str, Any]] = Field(default_factory=list, description="Evidence chain links")

    # Metadata
    verified_at: datetime
    verified_date: Optional[datetime] = Field(None, description="Alias for verified_at for frontend compatibility")
    verification_model: Optional[str] = None
    verification_method: Optional[str] = Field(None, description="automated, human_reviewed")
    
    def model_post_init(self, __context):
        """Set aliases from main fields if not provided."""
        if self.verification_status is None:
            object.__setattr__(self, 'verification_status', self.verdict)
        if self.verified_date is None:
            object.__setattr__(self, 'verified_date', self.verified_at)


class ClaimWithFactCheck(Claim):
    """
    Claim with its fact-check result.
    """
    fact_check: Optional[FactCheck] = None


class ArticleDetail(Article):
    """
    Full article with claims and fact-checks.
    """
    extracted_text: str = Field(default="", description="Full article content")
    full_text: Optional[str] = Field(None, description="Alias for extracted_text for frontend compatibility")
    claims: list[ClaimWithFactCheck] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None
    claims_available: bool = Field(
        default=False,
        description="Computed field: true if claims_status is completed and claims_count > 0"
    )
    analysis_article_html: Optional[str] = Field(
        default=None,
        description="Full HTML analysis article generated from verification results"
    )
    analysis_article_generated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of when analysis article was last generated"
    )
    # CARF-inspired decomposed confidence
    decomposed_confidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Article-level decomposed confidence scores"
    )
    reliability_breakdown: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Reliability breakdown with factor weights and scores"
    )
    insight_summary: Optional[str] = Field(
        default=None,
        description="AI-generated summary of verification findings"
    )

    def model_post_init(self, __context):
        """Set full_text from extracted_text and compute claims_available."""
        if self.full_text is None:
            object.__setattr__(self, 'full_text', self.extracted_text)

        # Compute claims_available based on status and count
        claims_available = (
            self.claims_status == 'completed' and
            self.claim_count > 0
        )
        object.__setattr__(self, 'claims_available', claims_available)


class FeedbackSummary(BaseModel):
    """
    Aggregated feedback for an article.
    """
    article_id: UUID
    total_feedback: int = 0
    useful: int = 0
    not_useful: int = 0
    flagged: int = 0
    average_reliability: Optional[float] = None


class TagStat(BaseModel):
    """
    Tag usage statistics.
    """
    tag: str
    article_count: int

