"""
Trust Domain Database Models

Implements trust-first data model with:
- Publisher trust scores and nutrition labels
- Article provenance and compliance tracking
- HITL moderation queue
- Video job tracking
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Numeric,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Database

Base = Database.Base


class Publisher(Base):
    """Publisher with trust scoring and TDM opt-out tracking.

    Stores publisher-level trust metrics, nutrition labels, and compliance data.
    Used for filtering and scoring articles during ingestion.
    """

    __tablename__ = "publishers"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Domain identifier (unique)
    domain = Column(String(255), unique=True, nullable=False, index=True)

    # Publisher metadata
    name = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # Compliance flags
    tdm_opt_out = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Text/Data Mining opt-out flag (robots.txt/noai)"
    )
    robots_txt_status = Column(
        String(50),
        default="unknown",
        comment="Last robots.txt check status"
    )
    compliance_last_checked = Column(DateTime, nullable=True)

    # Trust scoring
    trust_score = Column(
        Integer,
        default=50,
        nullable=False,
        index=True,
        comment="Trust score 0-100, default 50"
    )
    credibility_rating = Column(
        SQLEnum(
            "UNKNOWN", "LOW", "MEDIUM", "HIGH", "VERIFIED",
            name="credibility_rating_enum"
        ),
        default="UNKNOWN",
        nullable=False
    )

    # Nutrition label (JSONB for flexibility)
    nutrition_label = Column(
        JSONB,
        nullable=True,
        comment="Structured transparency data: fact-check ratio, bias scores, sources"
    )
    # Example structure:
    # {
    #   "fact_check_ratio": 0.85,
    #   "bias_score": {"left": 0.2, "center": 0.6, "right": 0.2},
    #   "verified_claims_count": 450,
    #   "disputed_claims_count": 12,
    #   "sources": ["Reuters", "AP"],
    #   "transparency_score": 0.9
    # }

    # Article statistics
    articles_published_count = Column(Integer, default=0)
    articles_verified_count = Column(Integer, default=0)
    articles_rejected_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    last_article_published = Column(DateTime, nullable=True)

    # Relationships
    articles = relationship("Article", back_populates="publisher", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_publisher_trust_score", "trust_score"),
        Index("idx_publisher_domain", "domain"),
        Index("idx_publisher_tdm_opt_out", "tdm_opt_out"),
    )

    def __repr__(self):
        return f"<Publisher {self.domain} (trust: {self.trust_score})>"


class Article(Base):
    """Article with trust metadata, provenance, and compliance tracking.

    Extends basic article model with:
    - Publisher trust relationship
    - Compliance check results
    - Summary provenance (AI vs human-edited)
    - HITL review status
    - Video rendering tracking
    """

    __tablename__ = "articles"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Publisher relationship
    publisher_id = Column(
        Integer,
        ForeignKey("publishers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Source article metadata
    original_url = Column(String(2048), unique=True, nullable=False, index=True)
    headline = Column(String(500), nullable=False)
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Content
    extracted_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    summary_type = Column(
        SQLEnum(
            "AI_GENERATED", "HUMAN_EDITED", "HYBRID",
            name="summary_type_enum"
        ),
        default="AI_GENERATED",
        nullable=False,
        comment="How summary was created"
    )

    # Compliance
    compliance_check_passed = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Passed robots.txt/noai checks"
    )
    compliance_skip_reason = Column(
        String(255),
        nullable=True,
        comment="Why article was skipped (if failed compliance)"
    )
    compliance_checked_at = Column(DateTime, nullable=True)

    # Provenance (JSONB for full audit trail)
    provenance = Column(
        JSONB,
        nullable=True,
        comment="Complete provenance: prompt version, model, HITL reviewer, decisions"
    )
    # Example structure:
    # {
    #   "summary": {
    #     "prompt_version": "v1.0",
    #     "model": "claude-3.5-sonnet",
    #     "temperature": 0.7,
    #     "created_at": "2025-12-12T10:00:00Z"
    #   },
    #   "hitl_review": {
    #     "reviewer": "user@example.com",
    #     "reviewed_at": "2025-12-12T10:30:00Z",
    #     "changes_made": ["Fixed typo", "Clarified claim"],
    #     "approval_reason": "Factually accurate"
    #   },
    #   "verification": {
    #     "claims_verified": 5,
    #     "sources_cited": ["NOAA", "ClimateCheck"],
    #     "confidence_scores": [0.95, 0.88, 0.92]
    #   }
    # }

    # Trust scoring (cached from publisher + article-level adjustments)
    trust_score_cache = Column(
        Integer,
        nullable=True,
        index=True,
        comment="Cached trust score for fast filtering"
    )
    verification_status = Column(
        SQLEnum(
            "PENDING", "VERIFIED", "UNVERIFIED", "DISPUTED", "REQUIRES_REVIEW",
            name="verification_status_enum"
        ),
        default="PENDING",
        nullable=False
    )

    # Video
    video_url = Column(String(2048), nullable=True)
    video_status = Column(
        SQLEnum(
            "NOT_STARTED", "QUEUED", "RENDERING", "COMPLETED", "FAILED",
            name="video_status_enum"
        ),
        default="NOT_STARTED",
        nullable=False
    )

    # HITL workflow
    hitl_status = Column(
        SQLEnum(
            "NOT_REQUIRED", "PENDING", "IN_REVIEW", "APPROVED", "REJECTED",
            name="hitl_status_enum"
        ),
        default="NOT_REQUIRED",
        nullable=False,
        index=True
    )
    hitl_assigned_to = Column(String(255), nullable=True)
    hitl_reviewed_at = Column(DateTime, nullable=True)

    # Publication
    published = Column(Boolean, default=False, nullable=False, index=True)
    published_at_platform = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    publisher = relationship("Publisher", back_populates="articles")
    moderation_reviews = relationship(
        "ModerationQueue",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    video_jobs = relationship(
        "VideoJob",
        back_populates="article",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_article_publisher_published", "publisher_id", "published_at"),
        Index("idx_article_trust_score", "trust_score_cache"),
        Index("idx_article_hitl_status", "hitl_status"),
        Index("idx_article_compliance", "compliance_check_passed"),
        Index("idx_article_published", "published", "published_at_platform"),
    )

    def __repr__(self):
        return f"<Article {self.id}: {self.headline[:50]}>"


class ModerationQueue(Base):
    """HITL moderation queue for human review of articles.

    Tracks articles requiring human review before publication.
    Stores reviewer decisions and feedback for audit trail.
    """

    __tablename__ = "moderation_queue"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Article relationship
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Review status
    status = Column(
        SQLEnum(
            "PENDING", "IN_REVIEW", "APPROVED", "REJECTED", "REQUIRES_EDIT",
            name="moderation_status_enum"
        ),
        default="PENDING",
        nullable=False,
        index=True
    )

    # Priority (higher = more urgent)
    priority = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Priority level for review queue ordering"
    )

    # Assignment
    assigned_to = Column(String(255), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)

    # Review
    reviewer = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Feedback
    feedback = Column(Text, nullable=True, comment="Reviewer feedback and notes")
    rejection_reason = Column(
        String(255),
        nullable=True,
        comment="Why article was rejected"
    )

    # Edits made (JSONB array)
    edits = Column(
        JSONB,
        nullable=True,
        comment="List of edits made by reviewer"
    )
    # Example:
    # [
    #   {"field": "headline", "original": "...", "edited": "...", "reason": "..."},
    #   {"field": "summary_text", "original": "...", "edited": "...", "reason": "..."}
    # ]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    article = relationship("Article", back_populates="moderation_reviews")

    # Indexes
    __table_args__ = (
        Index("idx_moderation_status_priority", "status", "priority"),
        Index("idx_moderation_assigned", "assigned_to", "status"),
    )

    def __repr__(self):
        return f"<ModerationQueue {self.id}: Article {self.article_id} ({self.status})>"


class VideoJob(Base):
    """Video rendering job tracking for Remotion pipeline.

    Tracks video generation jobs with cost, duration, and status.
    Links to article for video preview functionality.
    """

    __tablename__ = "video_jobs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Article relationship
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Job tracking
    job_id = Column(String(255), unique=True, nullable=True, index=True)
    status = Column(
        SQLEnum(
            "QUEUED", "RENDERING", "COMPLETED", "FAILED", "CANCELLED",
            name="video_job_status_enum"
        ),
        default="QUEUED",
        nullable=False,
        index=True
    )

    # Rendering provider
    render_provider = Column(
        String(50),
        default="remotion",
        nullable=False,
        comment="Video rendering provider (remotion, invideo, etc.)"
    )

    # Video metadata
    output_url = Column(String(2048), nullable=True)
    duration_ms = Column(Integer, nullable=True, comment="Video duration in milliseconds")
    resolution = Column(String(20), default="1920x1080")
    format = Column(String(10), default="mp4")

    # Cost tracking
    cost_cents = Column(
        Integer,
        nullable=True,
        comment="Rendering cost in cents (USD)"
    )
    render_time_seconds = Column(
        Integer,
        nullable=True,
        comment="Time taken to render"
    )

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Assets used (JSONB)
    assets = Column(
        JSONB,
        nullable=True,
        comment="TTS audio, Pexels videos, images used"
    )
    # Example:
    # {
    #   "tts_audio_url": "https://...",
    #   "pexels_videos": ["https://...", "https://..."],
    #   "pexels_images": ["https://..."]
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    article = relationship("Article", back_populates="video_jobs")

    # Indexes
    __table_args__ = (
        Index("idx_video_job_status", "status"),
        Index("idx_video_job_article", "article_id", "status"),
    )

    def __repr__(self):
        return f"<VideoJob {self.id}: Article {self.article_id} ({self.status})>"
