"""
Claims Status Manager

Centralized module for managing claims_status field transitions across the system.
This ensures consistent status updates throughout the claims extraction and verification workflow.

Usage:
    >>> from shared.claims_status_manager import ClaimsStatusManager
    >>>
    >>> manager = ClaimsStatusManager(postgres_client)
    >>>
    >>> # Start processing
    >>> manager.set_processing(article_id)
    >>>
    >>> # Mark as completed
    >>> manager.set_completed(article_id, claims_count=5)
    >>>
    >>> # Mark as failed
    >>> manager.set_failed(article_id, error_message="API timeout")
"""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import text

from .logger import LoggerMixin
from .database import PostgresClient


class ClaimsStatusManager(LoggerMixin):
    """
    Manages claims_status field transitions for articles.

    This class provides a centralized interface for updating the claims_status
    field and related metadata (error messages, timestamps, counts) in the database.

    Attributes:
        postgres (PostgresClient): PostgreSQL database client
    """

    # Valid status values
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(self, postgres: PostgresClient):
        """
        Initialize the ClaimsStatusManager.

        Args:
            postgres: PostgreSQL client instance
        """
        self.setup_logger("claims_status_manager")
        self.postgres = postgres

    def set_processing(self, article_id: UUID) -> bool:
        """
        Set article claims_status to 'processing'.

        Call this when claim extraction begins.

        Args:
            article_id: Article UUID

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.set_processing(article_id)
        """
        try:
            query = text("""
                UPDATE articles
                SET claims_status = :status,
                    updated_at = NOW()
                WHERE article_id = :article_id
            """)

            self.postgres.execute_update(
                str(query),
                {
                    "status": self.STATUS_PROCESSING,
                    "article_id": str(article_id)
                }
            )

            self.logger.info(
                "Article claims status set to processing",
                article_id=str(article_id)
            )
            return True

        except Exception as e:
            self.log_error(e, context={"article_id": str(article_id)})
            return False

    def set_completed(
        self,
        article_id: UUID,
        claims_count: int,
        verified_claims_count: int = 0
    ) -> bool:
        """
        Set article claims_status to 'completed'.

        Call this when claim extraction completes successfully.

        Args:
            article_id: Article UUID
            claims_count: Number of claims extracted
            verified_claims_count: Number of verified claims (optional)

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.set_completed(article_id, claims_count=5, verified_claims_count=3)
        """
        try:
            query = text("""
                UPDATE articles
                SET claims_status = :status,
                    claims_count = :claims_count,
                    verified_claims_count = :verified_count,
                    claims_processed_at = NOW(),
                    claims_error_message = NULL,
                    updated_at = NOW()
                WHERE article_id = :article_id
            """)

            self.postgres.execute_update(
                str(query),
                {
                    "status": self.STATUS_COMPLETED,
                    "claims_count": claims_count,
                    "verified_count": verified_claims_count,
                    "article_id": str(article_id)
                }
            )

            self.logger.info(
                "Article claims status set to completed",
                article_id=str(article_id),
                claims_count=claims_count,
                verified_claims_count=verified_claims_count
            )
            return True

        except Exception as e:
            self.log_error(e, context={
                "article_id": str(article_id),
                "claims_count": claims_count
            })
            return False

    def set_failed(
        self,
        article_id: UUID,
        error_message: str
    ) -> bool:
        """
        Set article claims_status to 'failed'.

        Call this when claim extraction fails.

        Args:
            article_id: Article UUID
            error_message: Error description

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.set_failed(article_id, "API timeout after 3 retries")
        """
        try:
            query = text("""
                UPDATE articles
                SET claims_status = :status,
                    claims_error_message = :error_message,
                    claims_processed_at = NOW(),
                    updated_at = NOW()
                WHERE article_id = :article_id
            """)

            self.postgres.execute_update(
                str(query),
                {
                    "status": self.STATUS_FAILED,
                    "error_message": error_message,
                    "article_id": str(article_id)
                }
            )

            self.logger.error(
                "Article claims status set to failed",
                article_id=str(article_id),
                error_message=error_message
            )
            return True

        except Exception as e:
            self.log_error(e, context={
                "article_id": str(article_id),
                "error_message": error_message
            })
            return False

    def set_pending(self, article_id: UUID) -> bool:
        """
        Set article claims_status to 'pending'.

        Call this to reset article to pending state (e.g., for retry).

        Args:
            article_id: Article UUID

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.set_pending(article_id)
        """
        try:
            query = text("""
                UPDATE articles
                SET claims_status = :status,
                    claims_error_message = NULL,
                    claims_processed_at = NULL,
                    updated_at = NOW()
                WHERE article_id = :article_id
            """)

            self.postgres.execute_update(
                str(query),
                {
                    "status": self.STATUS_PENDING,
                    "article_id": str(article_id)
                }
            )

            self.logger.info(
                "Article claims status reset to pending",
                article_id=str(article_id)
            )
            return True

        except Exception as e:
            self.log_error(e, context={"article_id": str(article_id)})
            return False

    def get_status(self, article_id: UUID) -> Optional[dict]:
        """
        Get current claims status for an article.

        Args:
            article_id: Article UUID

        Returns:
            Dictionary with status, error_message, and processed_at, or None if not found

        Example:
            >>> status = manager.get_status(article_id)
            >>> print(status["claims_status"])
        """
        try:
            query = """
                SELECT
                    claims_status,
                    claims_count,
                    verified_claims_count,
                    claims_error_message,
                    claims_processed_at
                FROM articles
                WHERE article_id = :article_id
            """

            results = self.postgres.execute_query(query, {"article_id": str(article_id)})

            if not results:
                return None

            return results[0]

        except Exception as e:
            self.log_error(e, context={"article_id": str(article_id)})
            return None

    def update_verification_counts(
        self,
        article_id: UUID,
        verified_claims_count: int
    ) -> bool:
        """
        Update verified_claims_count without changing status.

        Call this after fact-checking completes to update verification counts.

        Args:
            article_id: Article UUID
            verified_claims_count: Number of verified claims

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.update_verification_counts(article_id, verified_claims_count=3)
        """
        try:
            query = text("""
                UPDATE articles
                SET verified_claims_count = :verified_count,
                    updated_at = NOW()
                WHERE article_id = :article_id
            """)

            self.postgres.execute_update(
                str(query),
                {
                    "verified_count": verified_claims_count,
                    "article_id": str(article_id)
                }
            )

            self.logger.info(
                "Article verification counts updated",
                article_id=str(article_id),
                verified_claims_count=verified_claims_count
            )
            return True

        except Exception as e:
            self.log_error(e, context={
                "article_id": str(article_id),
                "verified_claims_count": verified_claims_count
            })
            return False

    def reset_stale_processing(
        self,
        stale_minutes: int = 120,
        limit: int = 200,
    ) -> int:
        """
        Reset stale 'processing' rows back to pending for retry.

        This prevents articles from staying indefinitely in processing when a
        worker crashes or a task is interrupted mid-flight.

        Args:
            stale_minutes: Consider rows stale after this many minutes
            limit: Maximum number of rows to reset per invocation

        Returns:
            Number of articles reset to pending
        """
        try:
            stale_minutes = max(1, int(stale_minutes))
            limit = max(1, min(int(limit), 5000))
        except (TypeError, ValueError):
            stale_minutes = 120
            limit = 200

        cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)

        try:
            stale_rows = self.postgres.execute_query(
                """
                SELECT article_id
                FROM articles
                WHERE claims_status = :processing_status
                  AND (
                        (updated_at IS NOT NULL AND updated_at < :cutoff)
                        OR (updated_at IS NULL AND created_at IS NOT NULL AND created_at < :cutoff)
                      )
                ORDER BY updated_at ASC
                LIMIT :limit
                """,
                {
                    "processing_status": self.STATUS_PROCESSING,
                    "cutoff": cutoff,
                    "limit": limit,
                },
            )

            if not stale_rows:
                return 0

            timeout_message = (
                f"Claim verification exceeded {stale_minutes} minutes and "
                "was reset to pending for retry."
            )

            recovered = 0
            for row in stale_rows:
                article_id = row.get("article_id") if isinstance(row, dict) else None
                if not article_id:
                    continue

                rows_updated = self.postgres.execute_update(
                    """
                    UPDATE articles
                    SET claims_status = :status,
                        claims_error_message = :error_message,
                        claims_processed_at = NULL,
                        updated_at = NOW()
                    WHERE article_id = :article_id
                      AND claims_status = :processing_status
                    """,
                    {
                        "status": self.STATUS_PENDING,
                        "error_message": timeout_message,
                        "article_id": str(article_id),
                        "processing_status": self.STATUS_PROCESSING,
                    },
                )
                if rows_updated:
                    recovered += 1

            if recovered:
                self.logger.warning(
                    "Reset stale processing articles",
                    recovered=recovered,
                    stale_minutes=stale_minutes,
                )

            return recovered

        except Exception as e:
            self.log_error(e, context={
                "stale_minutes": stale_minutes,
                "limit": limit,
            })
            return 0


def get_claims_status_manager() -> ClaimsStatusManager:
    """
    Get singleton instance of ClaimsStatusManager.

    Returns:
        ClaimsStatusManager instance

    Example:
        >>> from shared.claims_status_manager import get_claims_status_manager
        >>> manager = get_claims_status_manager()
        >>> manager.set_processing(article_id)
    """
    from .database import get_postgres

    postgres = get_postgres()
    return ClaimsStatusManager(postgres)


if __name__ == "__main__":
    # Test the claims status manager
    from uuid import uuid4

    manager = get_claims_status_manager()

    # Example usage
    test_article_id = uuid4()

    print("Setting status to processing...")
    manager.set_processing(test_article_id)

    print("Getting current status...")
    status = manager.get_status(test_article_id)
    print(f"Status: {status}")

    print("Setting status to completed...")
    manager.set_completed(test_article_id, claims_count=5, verified_claims_count=3)

    print("Final status:")
    status = manager.get_status(test_article_id)
    print(f"Status: {status}")
