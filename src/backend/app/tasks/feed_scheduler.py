"""
Feed Scheduler — Automatic per-user feed updates.

Celery task that queries user_feed_preferences, respects tier-based
frequency limits, and dispatches per-country discovery tasks.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.celery_app import app
from app.core.logging import get_logger
from shared.database import get_postgres

logger = get_logger(__name__)

# How often each frequency tier is allowed to update (in hours)
FREQUENCY_INTERVALS = {
    "daily": 24,
    "twice_daily": 12,
    "four_times_daily": 6,
    "hourly": 1,
}

# Map subscription tier → allowed update frequency
TIER_FREQUENCY = {
    "freemium": "daily",
    "basic": "twice_daily",
    "professional": "four_times_daily",
    "enterprise": "hourly",
}


def get_pending_feed_updates(tier_frequency: Optional[str] = None) -> list[dict]:
    """
    Query user feed preferences that are due for an update.

    Args:
        tier_frequency: If set, only fetch users with this frequency or slower.

    Returns:
        List of dicts with user_id, country_codes, keywords, update_frequency.
    """
    db = get_postgres()

    query = """
        SELECT
            ufp.user_id,
            ufp.country_codes,
            ufp.keywords,
            ufp.update_frequency,
            ufp.last_updated_at,
            u.subscription_tier
        FROM user_feed_preferences ufp
        JOIN users u ON u.user_id = ufp.user_id
        WHERE
            array_length(ufp.country_codes, 1) > 0
    """

    rows = db.execute_query(query) or []

    pending = []
    now = datetime.now(timezone.utc)

    for row in rows:
        freq = row.get("update_frequency", "daily")
        tier = row.get("subscription_tier", "freemium")

        # Enforce tier caps
        max_freq = TIER_FREQUENCY.get(tier, "daily")
        interval_hours = max(
            FREQUENCY_INTERVALS.get(freq, 24),
            FREQUENCY_INTERVALS.get(max_freq, 24),
        )

        last_updated = row.get("last_updated_at")
        if last_updated:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            # Ensure both datetimes are timezone-aware for comparison
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            if now - last_updated < timedelta(hours=interval_hours):
                continue  # Not yet due

        pending.append({
            "user_id": str(row["user_id"]),
            "country_codes": row.get("country_codes", []),
            "keywords": row.get("keywords", []),
            "update_frequency": freq,
            "subscription_tier": tier,
        })

    return pending


@app.task(name="app.tasks.feed_scheduler.update_user_feeds", bind=True, max_retries=2)
def update_user_feeds(self):
    """
    Celery beat task: iterate over pending user feeds and dispatch
    per-country discovery tasks. Deduplicates countries that have
    already been ingested within the frequency window.
    """
    try:
        pending = get_pending_feed_updates()
        logger.info(f"Feed scheduler: {len(pending)} users pending update")

        dispatched_countries: set[str] = set()
        db = get_postgres()

        for pref in pending:
            user_id = pref["user_id"]
            countries = pref.get("country_codes", [])
            keywords = pref.get("keywords", [])

            for cc in countries:
                cc = cc.upper().strip()
                if not cc:
                    continue

                # Dedup: skip if already dispatched in this run
                if cc in dispatched_countries:
                    continue
                dispatched_countries.add(cc)

                # Dispatch discovery task
                try:
                    from app.tasks.ingestion import discover_articles
                    discover_articles.delay(
                        country=cc,
                        max_articles=5,
                        keywords=keywords[:3] if keywords else None,
                    )
                    logger.info(f"Dispatched feed update for {cc} (user {user_id[:8]})")
                except Exception as e:
                    logger.warning(f"Failed to dispatch for {cc}: {e}")

            # Mark user feed as updated
            try:
                db.execute_update(
                    """UPDATE user_feed_preferences
                       SET last_updated_at = NOW(), updated_at = NOW()
                       WHERE user_id = :uid""",
                    {"uid": user_id},
                )
            except Exception as e:
                logger.warning(f"Failed to mark feed updated for {user_id}: {e}")

        return {"dispatched": len(dispatched_countries), "users_processed": len(pending)}

    except Exception as e:
        logger.error(f"Feed scheduler failed: {e}")
        raise self.retry(exc=e, countdown=300)
