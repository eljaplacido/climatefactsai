"""
Trust Domain Pydantic Schemas

API request/response models for trust domain.
Provides validation and serialization for publishers, articles, and moderation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class CredibilityRating(str, Enum):
    """Publisher credibility rating levels."""
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERIFIED = "VERIFIED"


class SummaryType(str, Enum):
    """How article summary was created."""
    AI_GENERATED = "AI_GENERATED"
    HUMAN_EDITED = "HUMAN_EDITED"
    HYBRID = "HYBRID"


class VerificationStatus(str, Enum):
    """Article verification status."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    DISPUTED = "DISPUTED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class VideoStatus(str, Enum):
    """Video rendering status."""
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HITLStatus(str, Enum):
    """Human-in-the-loop review status."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ModerationStatus(str, Enum):
    """Moderation queue status."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_EDIT = "REQUIRES_EDIT"


# ============================================================================
# PUBLISHER SCHEMAS
# ============================================================================

class NutritionLabel(BaseModel):
    """Publisher nutrition label structure."""
    fact_check_ratio: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Ratio of fact-checked articles"
    )
    bias_score: Optional[Dict[str, float]] = Field(
        None,
        description="Political bias distribution (left, center, right)"
    )
    verified_claims_count: Optional[int] = Field(None, ge=0)
    disputed_claims_count: Optional[int] = Field(None, ge=0)
    sources: Optional[List[str]] = Field(None, description="Primary sources cited")
    transparency_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class PublisherBase(BaseModel):
    """Base publisher fields."""
    domain: str = Field(..., max_length=255, description="Publisher domain")
    name: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    tdm_opt_out: bool = Field(default=False)
    trust_score: int = Field(default=50, ge=0, le=100)
    credibility_rating: CredibilityRating = CredibilityRating.UNKNOWN
    nutrition_label: Optional[NutritionLabel] = None


class PublisherCreate(PublisherBase):
    """Create new publisher."""
    pass


class PublisherUpdate(BaseModel):
    """Update existing publisher."""
    name: Optional[str] = None
    description: Optional[str] = None
    tdm_opt_out: Optional[bool] = None
    trust_score: Optional[int] = Field(None, ge=0, le=100)
    credibility_rating: Optional[CredibilityRating] = None
    nutrition_label: Optional[NutritionLabel] = None


class Publisher(PublisherBase):
    """Publisher response model."""
    id: int
    robots_txt_status: str
    compliance_last_checked: Optional[datetime] = None
    articles_published_count: int = 0
    articles_verified_count: int = 0
    articles_rejected_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_article_published: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# ARTICLE SCHEMAS
# ============================================================================

class ProvenanceData(BaseModel):
    """Article provenance structure."""
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary generation metadata"
    )
    hitl_review: Optional[Dict[str, Any]] = Field(
        None,
        description="HITL review details"
    )
    verification: Optional[Dict[str, Any]] = Field(
        None,
        description="Verification results"
    )


class ArticleBase(BaseModel):
    """Base article fields."""
    original_url: str = Field(..., max_length=2048)
    headline: str = Field(..., max_length=500)
    author: Optional[str] = Field(None, max_length=255)
    published_at: Optional[datetime] = None
    extracted_text: Optional[str] = None
    summary_text: Optional[str] = None
    summary_type: SummaryType = SummaryType.AI_GENERATED


class ArticleCreate(ArticleBase):
    """Create new article."""
    publisher_id: int
    compliance_check_passed: bool = False
    compliance_skip_reason: Optional[str] = None
    provenance: Optional[ProvenanceData] = None


class ArticleUpdate(BaseModel):
    """Update existing article."""
    headline: Optional[str] = None
    summary_text: Optional[str] = None
    summary_type: Optional[SummaryType] = None
    verification_status: Optional[VerificationStatus] = None
    trust_score_cache: Optional[int] = Field(None, ge=0, le=100)
    video_url: Optional[str] = None
    video_status: Optional[VideoStatus] = None
    hitl_status: Optional[HITLStatus] = None
    published: Optional[bool] = None
    provenance: Optional[ProvenanceData] = None


class Article(ArticleBase):
    """Article response model."""
    id: int
    publisher_id: int
    ingested_at: datetime
    compliance_check_passed: bool
    compliance_skip_reason: Optional[str] = None
    compliance_checked_at: Optional[datetime] = None
    provenance: Optional[ProvenanceData] = None
    trust_score_cache: Optional[int] = None
    verification_status: VerificationStatus
    video_url: Optional[str] = None
    video_status: VideoStatus
    hitl_status: HITLStatus
    hitl_assigned_to: Optional[str] = None
    hitl_reviewed_at: Optional[datetime] = None
    published: bool
    published_at_platform: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Related data
    publisher: Optional[Publisher] = None

    class Config:
        from_attributes = True


class ArticleWithTrust(Article):
    """Article with enhanced trust metadata for API v2."""

    # Trust scoring
    trust_badge: str = Field(
        ...,
        description="Trust badge level: gold, silver, bronze, unverified"
    )
    nutrition_label: Optional[NutritionLabel] = Field(
        None,
        description="Inherited from publisher"
    )

    # Compliance flags
    compliance_flags: Dict[str, bool] = Field(
        ...,
        description="robots_txt_ok, noai_ok, tdm_ok"
    )

    # Source CTA
    source_url: str = Field(..., description="Original article URL")
    source_domain: str = Field(..., description="Publisher domain")

    # HITL transparency
    human_reviewed: bool = Field(
        ...,
        description="Was this reviewed by a human?"
    )
    review_status: str = Field(..., description="HITL status for transparency")


# ============================================================================
# MODERATION SCHEMAS
# ============================================================================

class ModerationEdit(BaseModel):
    """Single edit made during moderation."""
    field: str
    original: str
    edited: str
    reason: str


class ModerationQueueBase(BaseModel):
    """Base moderation queue fields."""
    article_id: int
    status: ModerationStatus = ModerationStatus.PENDING
    priority: int = Field(default=0, description="Higher = more urgent")
    feedback: Optional[str] = None
    rejection_reason: Optional[str] = None


class ModerationQueueCreate(ModerationQueueBase):
    """Create moderation queue entry."""
    pass


class ModerationQueueUpdate(BaseModel):
    """Update moderation queue entry."""
    status: Optional[ModerationStatus] = None
    assigned_to: Optional[str] = None
    feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    edits: Optional[List[ModerationEdit]] = None


class ModerationQueue(ModerationQueueBase):
    """Moderation queue response model."""
    id: int
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    edits: Optional[List[ModerationEdit]] = None
    created_at: datetime
    updated_at: datetime

    # Related data
    article: Optional[Article] = None

    class Config:
        from_attributes = True


# ============================================================================
# VIDEO JOB SCHEMAS
# ============================================================================

class VideoAssets(BaseModel):
    """Video rendering assets."""
    tts_audio_url: Optional[str] = None
    pexels_videos: Optional[List[str]] = None
    pexels_images: Optional[List[str]] = None


class VideoJobBase(BaseModel):
    """Base video job fields."""
    article_id: int
    render_provider: str = "remotion"
    resolution: str = "1920x1080"
    format: str = "mp4"


class VideoJobCreate(VideoJobBase):
    """Create video job."""
    pass


class VideoJobUpdate(BaseModel):
    """Update video job."""
    status: Optional[VideoStatus] = None
    output_url: Optional[str] = None
    duration_ms: Optional[int] = None
    cost_cents: Optional[int] = None
    render_time_seconds: Optional[int] = None
    error_message: Optional[str] = None
    assets: Optional[VideoAssets] = None


class VideoJob(VideoJobBase):
    """Video job response model."""
    id: int
    job_id: Optional[str] = None
    status: VideoStatus
    output_url: Optional[str] = None
    duration_ms: Optional[int] = None
    cost_cents: Optional[int] = None
    render_time_seconds: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int
    assets: Optional[VideoAssets] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# LIST RESPONSES
# ============================================================================

class PublisherList(BaseModel):
    """Paginated publisher list."""
    publishers: List[Publisher]
    total: int
    page: int
    page_size: int


class ArticleList(BaseModel):
    """Paginated article list."""
    articles: List[Article]
    total: int
    page: int
    page_size: int


class ModerationQueueList(BaseModel):
    """Paginated moderation queue."""
    items: List[ModerationQueue]
    total: int
    page: int
    page_size: int
