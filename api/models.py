"""
API data models used by the FastAPI layer.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Country(BaseModel):
    """Country metadata returned to the frontend selector."""

    country_code: str
    country_name: str
    country_name_native: Optional[str] = None
    flag_emoji: Optional[str] = None
    language_code: Optional[str] = None
    is_eu_member: bool = False
    articles_count: int = Field(default=0, ge=0)


class DecomposedConfidence(BaseModel):
    """Multi-factor confidence breakdown (CARF-inspired)."""

    model_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_breadth: float = Field(default=0.0, ge=0.0, le=1.0)
    cross_reference_score: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    overall: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidenceChainLink(BaseModel):
    """Single link in an evidence chain."""

    step_number: int = 0
    description: str = ""
    source: str = ""
    source_url: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supports_claim: Optional[bool] = None


class FactCheck(BaseModel):
    """Fact-check payload for a claim."""

    verification_status: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    justification: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    climatecheck_hazard_type: Optional[str] = None
    climatecheck_risk_score: Optional[float] = None
    verified_date: Optional[datetime] = None
    decomposed_confidence: Optional[DecomposedConfidence] = None
    evidence_chain: Optional[List[EvidenceChainLink]] = None


class ClaimDetail(BaseModel):
    """Detailed information about a verified claim."""

    claim_id: str
    claim_text: str
    claim_context: Optional[str] = None
    claim_type: Optional[str] = None
    claim_category: Optional[str] = None
    fact_check: Optional[FactCheck] = None


class Article(BaseModel):
    """Article summary used on listing views."""

    article_id: str
    title: str
    url: str
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    source_name: str
    source_credibility_score: Optional[int] = Field(default=None, ge=0, le=100)
    excerpt: Optional[str] = None
    claim_count: int = Field(default=0, ge=0)
    verified_claim_count: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)
    content_relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reliability_score: Optional[int] = Field(default=None, ge=0, le=100)
    overall_credibility: Optional[str] = None
    created_at: datetime
    country_code: Optional[str] = None
    claims_status: Optional[str] = None
    claims_error_message: Optional[str] = None
    claims_processed_at: Optional[datetime] = None
    claims_by_category: Optional[Dict[str, int]] = None
    content_category: Optional[str] = None


class ArticleDetail(Article):
    """Full article response including claims and fact checks."""

    full_text: Optional[str] = None
    language_code: Optional[str] = None
    claims: List[ClaimDetail] = Field(default_factory=list)
    claims_available: bool = False
    decomposed_confidence: Optional[DecomposedConfidence] = None
    reliability_breakdown: Optional[Dict[str, Any]] = None
    insight_summary: Optional[str] = None


class DashboardStats(BaseModel):
    """Aggregate numbers shown on the dashboard."""

    total_articles: int = 0
    articles_today: int = 0
    total_fact_checks: int = 0
    verified_claims: int = 0
    average_confidence: float = 0.0
    last_updated: Optional[datetime] = None


class WorkflowStatus(BaseModel):
    """State of a workflow execution."""

    task_id: str
    status: str
    current_stage: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriggerWorkflowRequest(BaseModel):
    """Request body for manual workflow triggers."""

    task_id: Optional[str] = None
    country: Optional[str] = Field(default="FI", description="ISO country code", max_length=2)
    max_articles: Optional[int] = Field(default=5, ge=1, le=50)
    article_ids: Optional[List[str]] = Field(default=None, description="Optional list of article IDs")


class TriggerWorkflowResponse(BaseModel):
    """Response returned after starting a workflow."""

    task_id: str
    status: str
    message: str
    celery_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Feedback payload submitted from the UI."""

    feedback_type: str = Field(pattern=r"^(USEFUL|NOT_USEFUL|FLAGGED)$")
    reliability_score: Optional[int] = Field(default=None, ge=0, le=100)
    comment: Optional[str] = Field(default=None, max_length=2000)
    submitted_by: Optional[str] = Field(default=None, max_length=100)


class FeedbackResponse(BaseModel):
    """Response returned after storing feedback."""

    feedback_id: str
    article_id: str
    feedback_type: str
    reliability_score: Optional[int] = None
    comment: Optional[str] = None
    submitted_at: datetime


class FeedbackSummary(BaseModel):
    """Aggregated feedback counts for an article."""

    article_id: str
    total_feedback: int
    useful: int
    not_useful: int
    flagged: int
    average_reliability: Optional[float] = None


class TagStat(BaseModel):
    """Tag usage statistics."""

    tag: str
    article_count: int


# =============================================================================
# USER AUTHENTICATION MODELS
# =============================================================================

class UserRegister(BaseModel):
    """User registration request payload."""

    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    """User login request payload."""

    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # seconds


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request (forgot password)."""

    email: str = Field(..., max_length=255)


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation with token."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class EmailVerification(BaseModel):
    """Email verification request."""

    token: str


class PasswordChange(BaseModel):
    """Change password (for authenticated users)."""

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


# =============================================================================
# USER PROFILE MODELS
# =============================================================================

class UserProfile(BaseModel):
    """User profile information."""

    user_id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    subscription_tier: str = "freemium"
    email_verified: bool = False
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserProfileUpdate(BaseModel):
    """Update user profile."""

    full_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=2000)


class UserPreferences(BaseModel):
    """User preferences and settings."""

    preferred_countries: List[str] = Field(default_factory=list)
    notification_topics: List[str] = Field(default_factory=list)
    preferred_sources: List[str] = Field(default_factory=list)
    email_notifications: bool = True
    daily_digest: bool = False
    weekly_summary: bool = False
    breaking_news_alerts: bool = False
    theme: str = "light"
    language_code: str = "en"
    articles_per_page: int = 20


class SavedSearch(BaseModel):
    """Saved search query."""

    name: str = Field(..., max_length=100)
    filters: Dict[str, Any]
    created_at: datetime


# =============================================================================
# SUBSCRIPTION MODELS
# =============================================================================

class SubscriptionInfo(BaseModel):
    """User subscription details."""

    subscription_id: str
    tier: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_ends_at: Optional[datetime] = None


class SubscriptionCreate(BaseModel):
    """Create a new subscription."""

    tier: str = Field(..., pattern=r"^(basic|professional|enterprise)$")
    payment_method_id: str  # Stripe payment method ID


class SubscriptionCancel(BaseModel):
    """Cancel subscription request."""

    cancellation_reason: Optional[str] = Field(None, max_length=500)
    cancel_immediately: bool = False  # If False, cancel at period end


# =============================================================================
# USAGE TRACKING MODELS
# =============================================================================

class UsageStats(BaseModel):
    """User usage statistics."""

    articles_viewed_today: int = 0
    articles_viewed_this_month: int = 0
    url_analyses_this_month: int = 0
    api_calls_today: int = 0
    api_calls_this_month: int = 0

    # Limits based on tier
    article_limit_daily: Optional[int] = None
    url_analysis_limit_monthly: Optional[int] = None
    api_call_limit_daily: Optional[int] = None


# =============================================================================
# URL ANALYSIS MODELS
# =============================================================================

class URLAnalysisRequest(BaseModel):
    """Request to analyze a URL."""

    url: str = Field(..., max_length=2000)


class URLAnalysisResponse(BaseModel):
    """URL analysis result."""

    analysis_id: str
    status: str
    submitted_url: str
    created_at: datetime


class URLAnalysisDetail(BaseModel):
    """Detailed URL analysis result."""

    analysis_id: str
    submitted_url: str
    status: str

    # Source info
    source_name: Optional[str] = None
    source_domain: Optional[str] = None
    published_date: Optional[datetime] = None

    # Content
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    language_code: Optional[str] = None

    # Analysis results
    source_credibility_score: Optional[int] = None
    overall_credibility: Optional[str] = None
    reliability_score: Optional[int] = None

    # Claims and fact checks
    extracted_claims: List[Dict[str, Any]] = Field(default_factory=list)
    fact_checks: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)

    # Processing
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None

    # Sharing
    is_public: bool = False
    share_token: Optional[str] = None

    created_at: datetime


# =============================================================================
# API KEY MODELS
# =============================================================================

class APIKeyCreate(BaseModel):
    """Create a new API key."""

    name: str = Field(..., max_length=100)
    scopes: List[str] = Field(default=["read:articles"])
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    """API key creation response (includes plain key - shown only once)."""

    key_id: str
    api_key: str  # Full plain key (shown only on creation)
    key_prefix: str
    name: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None


class APIKeyInfo(BaseModel):
    """API key information (without the plain key)."""

    key_id: str
    key_prefix: str
    name: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


# =============================================================================
# NOTIFICATION MODELS
# =============================================================================

class Notification(BaseModel):
    """User notification."""

    notification_id: str
    type: str
    title: str
    message: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_url: Optional[str] = None
    is_read: bool = False
    priority: str = "normal"
    created_at: datetime


class NotificationMarkRead(BaseModel):
    """Mark notifications as read."""

    notification_ids: List[str]
