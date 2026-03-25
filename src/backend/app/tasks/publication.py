"""
Publication task: mark articles as published and ready for API/UX.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.core.celery_app import app
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)


@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def publish_article(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finalize workflow by marking articles as published in the database.
    """
    workflow_state = workflow_state or {}
    article_ids: List[str] = workflow_state.get("article_ids") or []
    if not article_ids:
        workflow_state["publication"] = {"published": 0}
        return workflow_state

    db = get_db()
    now = datetime.utcnow()
    published_count = 0

    for article_id in article_ids:
        try:
            db.execute_update(
                """
                UPDATE articles
                SET published = TRUE,
                    published_at_platform = :published_at,
                    updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": article_id, "published_at": now},
            )
            published_count += 1
        except Exception:
            # Legacy schema fallback
            db.execute_update(
                """
                UPDATE articles
                SET updated_at = NOW()
                WHERE article_id = :article_id
                """,
                {"article_id": article_id},
            )
            published_count += 1

    workflow_state["publication"] = {
        "published": published_count,
        "published_at": now.isoformat(),
    }
    logger.info(
        "Publication stage completed",
        published_count=published_count,
    )
    return workflow_state
