"""
Processing tasks: verification + summary alignment (Phase 2/3 of migration).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from app.core.celery_app import app
from app.core.database import get_db
from app.core.logging import get_logger
from app.domains.intelligence.services import VerificationService
from app.domains.content.source_profiles import SourceProfileService
from app.domains.trust import TrustService

logger = get_logger(__name__)


@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def verify_claims(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify claims for each article via the Intelligence domain service.
    """
    workflow_state = workflow_state or {}
    article_ids: List[str] = workflow_state.get("article_ids") or []
    if not article_ids:
        logger.warning("verify_claims invoked with no article_ids")
        workflow_state["verification_results"] = []
        return workflow_state

    db = get_db()
    service = VerificationService(db)
    verification_results: List[Dict[str, Any]] = []

    for article_id in article_ids:
        try:
            result = asyncio.run(service.verify_article(article_id))
            verification_results.append(result.model_dump())
            logger.info("Article verified", article_id=str(article_id))

            # Update source profile claim stats
            try:
                source_domain = result.provenance.get("source_domain") if result.provenance else None
                if source_domain:
                    sp_svc = SourceProfileService(db)
                    verified = sum(1 for v in result.verdicts if v.verification_status in ("verified", "true"))
                    disputed = sum(1 for v in result.verdicts if v.verification_status in ("false", "disputed"))
                    sp_svc.update_claim_stats(source_domain, verified=verified, disputed=disputed)
            except Exception as sp_exc:
                logger.warning("Source claim stats update failed", error=str(sp_exc))
        except Exception as exc:  # noqa: BLE001 - log and continue
            logger.error(
                "Verification failed",
                article_id=str(article_id),
                error=str(exc),
            )

    workflow_state["verification_results"] = verification_results
    return workflow_state


@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def create_summary(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce non-substitutive summaries and mark summary type.
    """
    workflow_state = workflow_state or {}
    article_ids: List[str] = workflow_state.get("article_ids") or []
    if not article_ids:
        workflow_state["summary_task"] = {"updated": 0}
        return workflow_state

    db = get_db()
    trust_service = TrustService(db)

    def _select_article(article_id: str):
        rows = db.execute_query(
            """
            SELECT article_id, title, summary_text, excerpt, COALESCE(extracted_text, '') AS extracted_text
            FROM articles
            WHERE article_id = :article_id
            """,
            {"article_id": article_id},
        )
        return rows[0] if rows else None

    updated = 0
    for article_id in article_ids:
        row = _select_article(article_id)
        if not row:
            continue

        base_text = row.get("summary_text") or row.get("excerpt") or row.get("extracted_text") or ""
        teaser = base_text.strip()
        if len(teaser) > 320:
            teaser = teaser[:320].rsplit(" ", 1)[0]

        params = {
            "article_id": article_id,
            "summary_text": teaser or "Climate summary unavailable; refer to source.",
        }

        try:
            db.execute_update(
                """
                UPDATE articles
                SET summary_text = COALESCE(summary_text, :summary_text),
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                params,
            )
        except Exception:
            db.execute_update(
                """
                UPDATE articles
                SET excerpt = COALESCE(excerpt, :summary_text),
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                params,
            )

        trust_service.update_article_trust(
            article_id=article_id,
            summary_type="AI_GENERATED",
        )
        updated += 1

        # Generate embedding for similarity search
        try:
            from app.domains.content.embedding_service import EmbeddingService
            emb_svc = EmbeddingService(db)
            asyncio.run(emb_svc.populate_embedding(article_id))
        except Exception as emb_exc:
            logger.warning("Embedding generation failed", article_id=article_id, error=str(emb_exc))

    # Generate analysis article if verification results exist
    verification_results = workflow_state.get("verification_results", [])
    if verification_results:
        try:
            from app.domains.content.article_generator import AnalysisArticleGenerator
            generator = AnalysisArticleGenerator()

            for vr in verification_results:
                art_id = vr.get("article_id")
                if not art_id:
                    continue

                row = _select_article(str(art_id))
                if not row:
                    continue

                claims_data = vr.get("claims", [])
                verdicts_data = vr.get("verdicts", [])

                if claims_data or verdicts_data:
                    try:
                        article_md = asyncio.run(generator.generate(
                            article_title=row.get("title", "Unknown") if isinstance(row, dict) else "Unknown",
                            article_text=row.get("extracted_text", ""),
                            claims=claims_data if isinstance(claims_data, list) else [],
                            verdicts=verdicts_data if isinstance(verdicts_data, list) else [],
                        ))
                        if article_md:
                            analysis_html = asyncio.run(generator.generate_html(article_md))
                            db.execute_update(
                                """UPDATE articles
                                   SET analysis_article_html = :html,
                                       analysis_article_generated_at = NOW()
                                   WHERE article_id = :article_id""",
                                {"html": analysis_html, "article_id": str(art_id)},
                            )
                            logger.info("Generated analysis article", article_id=str(art_id))
                    except Exception as gen_exc:
                        logger.warning("Article generation failed", article_id=str(art_id), error=str(gen_exc))
        except ImportError:
            logger.warning("AnalysisArticleGenerator not available")

    workflow_state["summary_task"] = {"updated": updated}
    return workflow_state
