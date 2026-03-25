"""
Automated fact-checking pipeline: discovers unverified articles and chains
them through claim extraction → verification → summary generation.

Runs on a Celery Beat schedule to continuously process new articles.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.celery_app import app
from app.core.database import get_db
from app.core.logging import get_logger
from app.domains.intelligence.services import VerificationService
from app.domains.content.source_profiles import SourceProfileService

logger = get_logger(__name__)


@app.task(bind=True, max_retries=2, rate_limit="3/m")
def auto_verify_pending_articles(
    self,
    batch_size: int = 10,
    country_code: Optional[str] = None,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Automated pipeline: find articles with claims_status='pending' or NULL
    and run the full verification chain on each.

    Steps per article:
      1. Mark claims_status = 'processing'
      2. Run VerificationService.verify_article()
      3. Update source profile claim stats
      4. Generate summary teaser + embedding
      5. Mark claims_status = 'completed' (or 'failed')

    Returns summary dict with counts and per-article results.
    """
    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"autoverify-{uuid4()}"
    db = get_db()

    logger.info(
        "auto_verify_pending_articles started",
        task_id=task_id,
        batch_size=batch_size,
        country_code=country_code,
    )

    # Find unverified articles
    country_filter = "AND country_code = :country_code" if country_code else ""
    query = f"""
        SELECT article_id, title, url, source_name
        FROM articles
        WHERE (claims_status IS NULL OR claims_status = 'pending')
          AND extracted_text IS NOT NULL
          AND LENGTH(COALESCE(extracted_text, '')) > 100
          {country_filter}
        ORDER BY created_at DESC
        LIMIT :batch_size
    """
    params: Dict[str, Any] = {"batch_size": batch_size}
    if country_code:
        params["country_code"] = country_code

    try:
        rows = db.execute_query(query, params)
    except Exception as exc:
        logger.error("Failed to query pending articles", error=str(exc))
        # Fallback: try without extracted_text filter
        fallback_query = f"""
            SELECT article_id, title, url, source_name
            FROM articles
            WHERE (claims_status IS NULL OR claims_status = 'pending')
              {country_filter}
            ORDER BY created_at DESC
            LIMIT :batch_size
        """
        rows = db.execute_query(fallback_query, params)

    if not rows:
        logger.info("No pending articles to verify", task_id=task_id)
        return {
            "task_id": task_id,
            "articles_found": 0,
            "verified": 0,
            "failed": 0,
            "completed_at": datetime.utcnow().isoformat(),
        }

    article_ids = [str(r["article_id"]) for r in rows]
    logger.info(
        "Found pending articles for verification",
        task_id=task_id,
        count=len(article_ids),
    )

    # Mark all as 'processing'
    for aid in article_ids:
        try:
            db.execute_update(
                """
                UPDATE articles
                SET claims_status = 'processing', updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": aid},
            )
        except Exception:
            pass

    # Run verification for each article
    service = VerificationService(db)
    results: List[Dict[str, Any]] = []
    verified_count = 0
    failed_count = 0

    for aid in article_ids:
        try:
            result = asyncio.run(service.verify_article(aid))
            verified_count += 1

            claims_count = len(result.claims) if hasattr(result, 'claims') else 0
            verdicts = result.verdicts if hasattr(result, 'verdicts') else []
            verified_claims = sum(
                1 for v in verdicts
                if hasattr(v, 'verification_status') and v.verification_status in ("verified", "true")
            )
            disputed_claims = sum(
                1 for v in verdicts
                if hasattr(v, 'verification_status') and v.verification_status in ("false", "disputed")
            )

            # Update source profile
            try:
                source_domain = None
                if hasattr(result, 'provenance') and result.provenance:
                    source_domain = result.provenance.get("source_domain")
                if source_domain:
                    sp_svc = SourceProfileService(db)
                    sp_svc.update_claim_stats(
                        source_domain, verified=verified_claims, disputed=disputed_claims
                    )
            except Exception as sp_exc:
                logger.warning("Source stats update failed", error=str(sp_exc))

            # Generate summary teaser
            try:
                _generate_teaser(db, aid)
            except Exception as t_exc:
                logger.warning("Teaser generation failed", article_id=aid, error=str(t_exc))

            # Generate embedding
            try:
                from app.domains.content.embedding_service import EmbeddingService
                emb_svc = EmbeddingService(db)
                asyncio.run(emb_svc.populate_embedding(aid))
            except Exception:
                pass

            # Mark completed
            db.execute_update(
                """
                UPDATE articles
                SET claims_status = 'completed',
                    claims_processed_at = NOW(),
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": aid},
            )

            results.append({
                "article_id": aid,
                "status": "completed",
                "claims_extracted": claims_count,
                "verified": verified_claims,
                "disputed": disputed_claims,
            })

            logger.info(
                "Article verified successfully",
                article_id=aid,
                claims=claims_count,
                verified=verified_claims,
                disputed=disputed_claims,
            )

        except Exception as exc:
            failed_count += 1
            error_msg = str(exc)[:500]

            db.execute_update(
                """
                UPDATE articles
                SET claims_status = 'failed',
                    claims_error_message = :error,
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": aid, "error": error_msg},
            )

            results.append({
                "article_id": aid,
                "status": "failed",
                "error": error_msg,
            })

            logger.error(
                "Article verification failed",
                article_id=aid,
                error=error_msg,
            )

    summary = {
        "task_id": task_id,
        "articles_found": len(article_ids),
        "verified": verified_count,
        "failed": failed_count,
        "results": results,
        "completed_at": datetime.utcnow().isoformat(),
    }

    logger.info(
        "auto_verify_pending_articles completed",
        task_id=task_id,
        verified=verified_count,
        failed=failed_count,
    )

    return summary


@app.task(bind=True, max_retries=1)
def retry_failed_verifications(
    self,
    max_retries_per_article: int = 2,
    batch_size: int = 5,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retry articles that previously failed verification.
    Only retries articles that have failed fewer than max_retries_per_article times.
    """
    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"retry-{uuid4()}"
    db = get_db()

    logger.info("retry_failed_verifications started", task_id=task_id)

    rows = db.execute_query(
        """
        SELECT article_id
        FROM articles
        WHERE claims_status = 'failed'
          AND (claims_error_message NOT LIKE '%%API%%credit%%' OR claims_error_message IS NULL)
        ORDER BY updated_at ASC
        LIMIT :batch_size
        """,
        {"batch_size": batch_size},
    )

    if not rows:
        return {"task_id": task_id, "retried": 0}

    # Reset to pending so auto_verify picks them up
    retried = 0
    for row in rows:
        aid = str(row["article_id"])
        try:
            db.execute_update(
                """
                UPDATE articles
                SET claims_status = 'pending',
                    claims_error_message = NULL,
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": aid},
            )
            retried += 1
        except Exception as exc:
            logger.warning("Failed to reset article for retry", article_id=aid, error=str(exc))

    # Trigger auto-verify for the reset articles
    if retried > 0:
        auto_verify_pending_articles.apply_async(
            kwargs={"batch_size": retried},
            countdown=10,
        )

    logger.info("retry_failed_verifications completed", task_id=task_id, retried=retried)
    return {"task_id": task_id, "retried": retried}


@app.task(bind=True, max_retries=1)
def pipeline_health_check(
    self,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Health check task that reports pipeline statistics.
    Useful for monitoring and alerting.
    """
    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"health-{uuid4()}"
    db = get_db()

    stats = db.execute_query(
        """
        SELECT
            COUNT(*) AS total_articles,
            COUNT(*) FILTER (WHERE claims_status = 'pending' OR claims_status IS NULL) AS pending,
            COUNT(*) FILTER (WHERE claims_status = 'processing') AS processing,
            COUNT(*) FILTER (WHERE claims_status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE claims_status = 'failed') AS failed,
            COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS ingested_today,
            COUNT(*) FILTER (WHERE DATE(claims_processed_at) = CURRENT_DATE) AS verified_today
        FROM articles
        """,
        {},
    )

    row = stats[0] if stats else {}

    health = {
        "task_id": task_id,
        "total_articles": row.get("total_articles", 0),
        "pending": row.get("pending", 0),
        "processing": row.get("processing", 0),
        "completed": row.get("completed", 0),
        "failed": row.get("failed", 0),
        "ingested_today": row.get("ingested_today", 0),
        "verified_today": row.get("verified_today", 0),
        "checked_at": datetime.utcnow().isoformat(),
    }

    logger.info("pipeline_health_check", **health)
    return health


def _generate_teaser(db, article_id: str) -> None:
    """Generate a non-substitutive teaser for the article."""
    rows = db.execute_query(
        """
        SELECT summary_text, excerpt, COALESCE(extracted_text, '') AS extracted_text
        FROM articles WHERE article_id = :article_id
        """,
        {"article_id": article_id},
    )
    if not rows:
        return

    row = rows[0]
    base_text = row.get("summary_text") or row.get("excerpt") or row.get("extracted_text") or ""
    teaser = base_text.strip()
    if len(teaser) > 320:
        teaser = teaser[:320].rsplit(" ", 1)[0]

    if teaser:
        db.execute_update(
            """
            UPDATE articles
            SET summary_text = COALESCE(summary_text, :teaser),
                updated_at = NOW()
            WHERE article_id = :article_id
            """,
            {"teaser": teaser, "article_id": article_id},
        )
