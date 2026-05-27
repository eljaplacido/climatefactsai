"""Public platform-status endpoints.

Surfaces "what is the platform doing right now" so the user can verify
GX10 / Lane A / entity-extraction progress without an admin token. All
aggregate counts, no PII, safe to expose unauthenticated.

Born from a real bug pattern: the user kept asking "is GX10 actually
enriching anything?" and we had no public-readable answer — only the
admin/llm/breakers endpoint behind a scheduler-secret. This is the
honest, observable read.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("status")
router = APIRouter(prefix="/api/status", tags=["Platform Status"])


def _safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


@router.get("/gx10")
async def get_gx10_status() -> Dict[str, Any]:
    """Snapshot of GX10 / Lane A activity over the last 24 hours.

    Returns:
      * enrichments_24h: total articles whose `enriched_at` is < 24h ago
      * enrichments_24h_by_provider: split by `enrichment_metadata.llm_provider`
        — `local-gx10`, `deepseek`, `openai`, `anthropic`, `fallback`
      * latest_enriched: the most-recent article (title + provider + timestamp)
      * entities_24h: count of KG entities first seen in last 24h
      * article_entities_24h: count of (article, entity) links in last 24h
      * latest_entity: the most-recent entity extracted (name + type + time)
      * topic_feedback_off_topic: count of articles flagged off-topic
      * server_time: api-side now() for clock-drift sanity
    """
    db = get_postgres()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    out: Dict[str, Any] = {
        "server_time": now.isoformat(),
        "window_hours": 24,
    }

    # ---- 1. Article enrichments in the last 24h, split by provider --------
    try:
        rows = db.execute_query(
            """SELECT COALESCE(enrichment_metadata->>'llm_provider', 'unknown')
                       AS provider,
                       COUNT(*) AS n
                 FROM articles
                WHERE enriched_at IS NOT NULL
                  AND enriched_at > :since
                GROUP BY 1
                ORDER BY 2 DESC""",
            {"since": since},
        )
        by_provider = {r["provider"]: _safe_int(r["n"]) for r in (rows or [])}
        out["enrichments_24h"] = sum(by_provider.values())
        out["enrichments_24h_by_provider"] = by_provider
        # Convenience read for the user's question "is GX10 actually working?"
        # — sum any provider key that starts with "local-gx10" (covers comma-
        # separated chains like "local-gx10,deepseek" when fallback fires).
        out["enrichments_24h_local_gx10"] = sum(
            n for p, n in by_provider.items()
            if p and p.startswith("local-gx10")
        )
    except Exception as exc:
        logger.warning("status/gx10 enrichments query failed", error=str(exc))
        out["enrichments_24h"] = 0
        out["enrichments_24h_by_provider"] = {}
        out["enrichments_24h_local_gx10"] = 0

    # ---- 2. Latest enriched article ---------------------------------------
    try:
        rows = db.execute_query(
            """SELECT article_id::text AS article_id,
                      title,
                      enriched_at,
                      COALESCE(enrichment_metadata->>'llm_provider','unknown')
                        AS provider,
                      COALESCE(enrichment_metadata->>'llm_model','')
                        AS model
                 FROM articles
                WHERE enriched_at IS NOT NULL
                ORDER BY enriched_at DESC
                LIMIT 1""",
            {},
        )
        if rows:
            r = rows[0]
            out["latest_enriched"] = {
                "article_id": r["article_id"],
                "title": (r["title"] or "")[:160],
                "enriched_at": (
                    r["enriched_at"].isoformat()
                    if hasattr(r["enriched_at"], "isoformat")
                    else r["enriched_at"]
                ),
                "provider": r["provider"],
                "model": r["model"],
            }
        else:
            out["latest_enriched"] = None
    except Exception as exc:
        logger.warning("status/gx10 latest enriched failed", error=str(exc))
        out["latest_enriched"] = None

    # ---- 3. Entity extraction activity ------------------------------------
    try:
        rows = db.execute_query(
            """SELECT COUNT(*) AS n FROM entities
                WHERE first_seen_at > :since""",
            {"since": since},
        )
        out["entities_24h"] = _safe_int(rows[0]["n"]) if rows else 0
    except Exception as exc:
        logger.warning("status/gx10 entities count failed", error=str(exc))
        out["entities_24h"] = 0

    try:
        rows = db.execute_query(
            """SELECT COUNT(*) AS n FROM article_entities
                WHERE created_at > :since""",
            {"since": since},
        )
        out["article_entities_24h"] = _safe_int(rows[0]["n"]) if rows else 0
    except Exception as exc:
        logger.warning("status/gx10 article_entities failed", error=str(exc))
        out["article_entities_24h"] = 0

    try:
        rows = db.execute_query(
            """SELECT entity_name, entity_type::text AS entity_type,
                      first_seen_at
                 FROM entities
                ORDER BY first_seen_at DESC
                LIMIT 1""",
            {},
        )
        if rows:
            r = rows[0]
            out["latest_entity"] = {
                "name": r["entity_name"],
                "type": r["entity_type"],
                "first_seen_at": (
                    r["first_seen_at"].isoformat()
                    if hasattr(r["first_seen_at"], "isoformat")
                    else r["first_seen_at"]
                ),
            }
        else:
            out["latest_entity"] = None
    except Exception as exc:
        logger.warning("status/gx10 latest entity failed", error=str(exc))
        out["latest_entity"] = None

    # ---- 4. Topic-feedback (mig 050 + 055) signal -------------------------
    try:
        rows = db.execute_query(
            """SELECT COUNT(DISTINCT article_id) AS n
                 FROM topic_feedback
                WHERE verdict = 'off_topic'""",
            {},
        )
        out["topic_feedback_off_topic"] = _safe_int(rows[0]["n"]) if rows else 0
    except Exception as exc:
        logger.warning("status/gx10 topic feedback count failed", error=str(exc))
        out["topic_feedback_off_topic"] = 0

    # ---- 5. Pipeline-health heuristic -------------------------------------
    # "healthy" when GX10 produced > 0 enrichments in the last 24h.
    # "stalled" when nothing produced.
    # "degraded" when ONLY cloud fallbacks fired (GX10 likely offline).
    gx10_n = out["enrichments_24h_local_gx10"]
    total_n = out["enrichments_24h"]
    if gx10_n > 0:
        out["lane_a_health"] = "healthy"
    elif total_n > 0:
        out["lane_a_health"] = "degraded"  # fallback chain ran without GX10
    else:
        out["lane_a_health"] = "stalled"

    return out


@router.get("/summary")
async def get_platform_status_summary() -> Dict[str, Any]:
    """Compact top-level snapshot for the home page + chat-context badge.

    Designed for cheap polling — every field is a single aggregate query.
    Intentionally exposes only counts, not row data.
    """
    db = get_postgres()
    out: Dict[str, Any] = {}

    queries: List[tuple[str, str, dict]] = [
        ("articles_total", "SELECT COUNT(*) AS n FROM articles", {}),
        (
            "articles_enriched",
            "SELECT COUNT(*) AS n FROM articles WHERE enriched_at IS NOT NULL",
            {},
        ),
        ("companies_total", "SELECT COUNT(*) AS n FROM companies", {}),
        ("entities_total", "SELECT COUNT(*) AS n FROM entities", {}),
        (
            "url_analyses_total",
            "SELECT COUNT(*) AS n FROM url_analyses WHERE status = 'completed'",
            {},
        ),
        (
            "off_topic_flagged",
            "SELECT COUNT(DISTINCT article_id) AS n FROM topic_feedback "
            "WHERE verdict = 'off_topic'",
            {},
        ),
        (
            "rss_feeds_active",
            "SELECT COUNT(*) AS n FROM rss_feed_registry WHERE is_active = true",
            {},
        ),
    ]
    for key, sql, params in queries:
        try:
            rows = db.execute_query(sql, params)
            out[key] = _safe_int(rows[0]["n"]) if rows else 0
        except Exception as exc:
            logger.warning(
                "status/summary %s failed: %s", key, exc
            )
            out[key] = 0

    out["server_time"] = datetime.now(timezone.utc).isoformat()
    return out
