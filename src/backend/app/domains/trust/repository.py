"""
Trust Domain Repositories

Provides thin SQL repositories over the trust-centric tables defined in
`docs/architecture/data-model-trust.md`. These helpers are intentionally
SQL-first (no heavy ORM dependency) so they can run inside the existing
Postgres client used by the modular monolith.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.database import Database
from app.core.logging import get_logger

logger = get_logger(__name__)


class PublisherRepository:
    """CRUD helpers for the `publishers` trust table."""

    def __init__(self, db: Database):
        self.db = db

    def get_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query(
            """
            SELECT
                id,
                domain,
                name,
                description,
                trust_score,
                credibility_rating,
                tdm_opt_out,
                robots_txt_status,
                compliance_last_checked,
                nutrition_label,
                articles_published_count,
                articles_verified_count,
                articles_rejected_count,
                created_at,
                updated_at,
                last_article_published
            FROM publishers
            WHERE domain = :domain
            """,
            {"domain": domain},
        )
        return rows[0] if rows else None

    def upsert_publisher(
        self,
        *,
        domain: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        trust_score: Optional[int] = None,
        credibility_rating: Optional[str] = None,
        tdm_opt_out: Optional[bool] = None,
        nutrition_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = self.db.execute_query(
            """
            INSERT INTO publishers (
                domain,
                name,
                description,
                trust_score,
                credibility_rating,
                nutrition_label,
                tdm_opt_out
            )
            VALUES (
                :domain,
                :name,
                :description,
                COALESCE(:trust_score, 50),
                COALESCE(:credibility_rating, 'UNKNOWN'),
                :nutrition_label,
                COALESCE(:tdm_opt_out, FALSE)
            )
            ON CONFLICT (domain) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                trust_score = COALESCE(EXCLUDED.trust_score, publishers.trust_score),
                credibility_rating = COALESCE(EXCLUDED.credibility_rating, publishers.credibility_rating),
                nutrition_label = COALESCE(EXCLUDED.nutrition_label, publishers.nutrition_label),
                tdm_opt_out = COALESCE(EXCLUDED.tdm_opt_out, publishers.tdm_opt_out),
                updated_at = NOW()
            RETURNING *
            """,
            {
                "domain": domain,
                "name": name,
                "description": description,
                "trust_score": trust_score,
                "credibility_rating": credibility_rating,
                "nutrition_label": nutrition_label,
                "tdm_opt_out": tdm_opt_out,
            },
        )
        return row[0]

    def record_compliance_result(
        self,
        *,
        domain: str,
        robots_status: str,
        tdm_opt_out: bool,
        last_checked: Optional[datetime] = None,
    ):
        self.db.execute_update(
            """
            UPDATE publishers
            SET
                robots_txt_status = :robots_status,
                tdm_opt_out = :tdm_opt_out,
                compliance_last_checked = :checked_at,
                updated_at = NOW()
            WHERE domain = :domain
            """,
            {
                "domain": domain,
                "robots_status": robots_status,
                "tdm_opt_out": tdm_opt_out,
                "checked_at": last_checked or datetime.utcnow(),
            },
        )


class TrustArticleRepository:
    """Helpers for the trust metadata stored on articles."""

    def __init__(self, db: Database):
        self.db = db

    def update_trust_metadata(
        self,
        article_id: str,
        *,
        trust_score: Optional[int] = None,
        provenance: Optional[Dict[str, Any]] = None,
        summary_type: Optional[str] = None,
        compliance_passed: Optional[bool] = None,
        compliance_reason: Optional[str] = None,
        hitl_status: Optional[str] = None,
        video_status: Optional[str] = None,
        video_url: Optional[str] = None,
    ):
        """Update trust + compliance metadata on an article row."""
        set_clauses = ["updated_at = NOW()"]
        params: Dict[str, Any] = {"article_id": article_id}

        def add_clause(field: str, column: str = None):
            col = column or field
            set_clauses.append(f"{col} = :{field}")

        if trust_score is not None:
            params["trust_score"] = trust_score
            add_clause("trust_score", "trust_score_cache")
        if provenance is not None:
            params["provenance"] = provenance
            add_clause("provenance")
        if summary_type is not None:
            params["summary_type"] = summary_type
            add_clause("summary_type")
        if compliance_passed is not None:
            params["compliance_passed"] = compliance_passed
            add_clause("compliance_passed", "compliance_check_passed")
        if compliance_reason is not None:
            params["compliance_reason"] = compliance_reason
            add_clause("compliance_reason", "compliance_skip_reason")
        if hitl_status is not None:
            params["hitl_status"] = hitl_status
            add_clause("hitl_status")
        if video_status is not None:
            params["video_status"] = video_status
            add_clause("video_status")
        if video_url is not None:
            params["video_url"] = video_url
            add_clause("video_url")
        if len(set_clauses) == 1:
            logger.debug("No trust metadata change for article %s", article_id)
            return

        query = f"""
            UPDATE articles
            SET {', '.join(set_clauses)}
            WHERE article_id = :article_id
        """
        self.db.execute_update(query, params)

    def fetch_trust_snapshot(self, article_id: str) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query(
            """
            SELECT
                article_id,
                trust_score_cache,
                provenance,
                summary_type,
                compliance_check_passed,
                compliance_skip_reason,
                hitl_status,
                video_status,
                video_url
            FROM articles
            WHERE article_id = :article_id
            """,
            {"article_id": article_id},
        )
        return rows[0] if rows else None


class ModerationQueueRepository:
    """Repository for HITL moderation queue entries."""

    def __init__(self, db: Database):
        self.db = db

    def enqueue(
        self,
        *,
        article_id: str,
        priority: int,
        status: str = "PENDING",
        assigned_to: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = self.db.execute_query(
            """
            INSERT INTO moderation_queue (
                article_id,
                status,
                priority,
                assigned_to,
                feedback
            )
            VALUES (
                :article_id,
                :status,
                :priority,
                :assigned_to,
                :feedback
            )
            RETURNING *
            """,
            {
                "article_id": article_id,
                "status": status,
                "priority": priority,
                "assigned_to": assigned_to,
                "feedback": feedback,
            },
        )
        return row[0]

    def update_status(
        self,
        queue_id: int,
        *,
        status: str,
        reviewer: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        edits: Optional[Dict[str, Any]] = None,
    ):
        self.db.execute_update(
            """
            UPDATE moderation_queue
            SET
                status = :status,
                reviewer = COALESCE(:reviewer, reviewer),
                rejection_reason = COALESCE(:rejection_reason, rejection_reason),
                edits = COALESCE(:edits, edits),
                reviewed_at = CASE
                    WHEN :status IN ('APPROVED','REJECTED') THEN NOW()
                    ELSE reviewed_at
                END,
                updated_at = NOW()
            WHERE id = :queue_id
            """,
            {
                "queue_id": queue_id,
                "status": status,
                "reviewer": reviewer,
                "rejection_reason": rejection_reason,
                "edits": edits,
            },
        )


class VideoJobRepository:
    """Repository for Remotion/Render job bookkeeping."""

    def __init__(self, db: Database):
        self.db = db

    def create_job(
        self,
        *,
        article_id: str,
        job_id: str,
        render_provider: str = "remotion",
        assets: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = self.db.execute_query(
            """
            INSERT INTO video_jobs (
                article_id,
                job_id,
                status,
                render_provider,
                assets
            )
            VALUES (
                :article_id,
                :job_id,
                'QUEUED',
                :render_provider,
                :assets
            )
            RETURNING *
            """,
            {
                "article_id": article_id,
                "job_id": job_id,
                "render_provider": render_provider,
                "assets": assets,
            },
        )
        return row[0]

    def update_status(
        self,
        *,
        job_id: str,
        status: str,
        output_url: Optional[str] = None,
        error_message: Optional[str] = None,
        cost_cents: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ):
        self.db.execute_update(
            """
            UPDATE video_jobs
            SET
                status = :status,
                output_url = COALESCE(:output_url, output_url),
                error_message = COALESCE(:error_message, error_message),
                cost_cents = COALESCE(:cost_cents, cost_cents),
                duration_ms = COALESCE(:duration_ms, duration_ms),
                updated_at = NOW(),
                completed_at = CASE
                    WHEN :status IN ('COMPLETED','FAILED','CANCELLED') THEN NOW()
                    ELSE completed_at
                END
            WHERE job_id = :job_id
            """,
            {
                "job_id": job_id,
                "status": status,
                "output_url": output_url,
                "error_message": error_message,
                "cost_cents": cost_cents,
                "duration_ms": duration_ms,
            },
        )
