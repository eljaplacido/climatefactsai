"""Source-health canary — seq-9 (2026-06-04).

Probes every RSS feed in `rss_feed_registry`, records HTTP status + entry count
+ last-success, and AUTO-DISABLES a feed once its consecutive-error count crosses
a threshold. The ingestion path already increments `fetch_error_count` on a bad
poll, but nothing ever acted on it — so a publisher that went dark (DNS death,
404, paywall, malformed XML) stayed in the active rotation forever, silently
dragging coverage down with zero observability. There were ZERO source-liveness
tests; this module + its tests are the safety net that gates coverage expansion.

Design:
  * `check_feed_liveness(url)` is the only network call (httpx GET + feedparser
    parse of the bytes). It is injected into `run_source_health_canary` so the
    canary logic is unit-tested without touching the network.
  * `run_source_health_canary(db, checker=...)` walks the registry, updates each
    row, auto-disables dead feeds, and returns a structured summary.

The threshold is deliberately > 1: a single transient blip (timeout, 503) must
NOT disable a feed. DEAD_FEED_THRESHOLD consecutive failures is the signal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

_logger = logging.getLogger("source_health")

# Consecutive failed probes before a feed is auto-disabled (is_active=false).
# A healthy poll resets the counter to 0, so this means "N in a row".
DEAD_FEED_THRESHOLD = 5

# Per-feed probe timeout (seconds). Kept tight so one hung publisher can't stall
# the whole canary run.
PROBE_TIMEOUT = 15.0

_USER_AGENT = (
    "Climatefacts-SourceHealthCanary/1.0 "
    "(+https://climatefacts.ai; feed liveness probe)"
)


@dataclass
class LivenessResult:
    """Outcome of a single feed probe."""
    ok: bool
    http_status: Optional[int] = None
    item_count: int = 0
    error: Optional[str] = None


def check_feed_liveness(url: str, timeout: float = PROBE_TIMEOUT) -> LivenessResult:
    """Probe a single feed URL. Healthy == HTTP 2xx/3xx AND >=1 parseable entry.

    Network + parsing imports are local so this module imports cleanly (and the
    canary logic stays unit-testable with an injected checker) even if httpx /
    feedparser aren't present in a given environment.
    """
    try:
        import httpx
    except Exception as exc:  # pragma: no cover - dependency guard
        return LivenessResult(ok=False, error=f"httpx unavailable: {exc}")

    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
    except Exception as exc:
        return LivenessResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])

    status = resp.status_code
    if status >= 400:
        return LivenessResult(ok=False, http_status=status, error=f"HTTP {status}")

    try:
        import feedparser
        parsed = feedparser.parse(resp.content)
        item_count = len(getattr(parsed, "entries", []) or [])
    except Exception as exc:
        return LivenessResult(ok=False, http_status=status, error=f"parse error: {exc}"[:300])

    if item_count == 0:
        return LivenessResult(
            ok=False,
            http_status=status,
            item_count=0,
            error="no entries (empty or unparseable feed)",
        )

    return LivenessResult(ok=True, http_status=status, item_count=item_count)


def run_source_health_canary(
    db,
    checker: Callable[[str], LivenessResult] = check_feed_liveness,
    threshold: int = DEAD_FEED_THRESHOLD,
    include_inactive: bool = False,
) -> Dict[str, Any]:
    """Probe every (active) feed, update its health row, auto-disable dead ones.

    Args:
        db: postgres client exposing execute_query / execute_update.
        checker: feed-liveness probe (injected for tests).
        threshold: consecutive failures before auto-disable.
        include_inactive: also re-probe already-disabled feeds (lets a revived
            feed be reported, though it stays disabled until a human re-enables).

    Returns a summary dict: counts + the feeds that were auto-disabled this run.
    """
    where = "" if include_inactive else "WHERE is_active = true"
    try:
        rows = db.execute_query(
            f"""
            SELECT feed_id, feed_name, feed_url, is_active, fetch_error_count
            FROM rss_feed_registry
            {where}
            ORDER BY feed_name
            """,
            {},
        )
    except Exception as exc:
        _logger.error(f"source_health: registry read failed: {exc}")
        return {"status": "error", "error": str(exc)[:300], "checked": 0}

    rows = rows or []
    checked = healthy = failed = 0
    newly_disabled: List[Dict[str, Any]] = []

    for row in rows:
        feed_id = row["feed_id"]
        feed_name = row.get("feed_name") or str(feed_id)
        feed_url = row.get("feed_url") or ""
        prior_errors = int(row.get("fetch_error_count") or 0)
        was_active = bool(row.get("is_active"))

        result = checker(feed_url)
        checked += 1

        try:
            if result.ok:
                healthy += 1
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           last_success_at = NOW(),
                           last_http_status = :status,
                           last_item_count = :count,
                           last_check_error = NULL,
                           fetch_error_count = 0
                     WHERE feed_id = :feed_id
                    """,
                    {
                        "status": result.http_status,
                        "count": result.item_count,
                        "feed_id": feed_id,
                    },
                )
            else:
                failed += 1
                new_errors = prior_errors + 1
                will_disable = was_active and new_errors >= threshold
                # Single write: increment the counter and flip is_active off the
                # moment the post-increment count crosses the threshold. Using
                # the DB's current value avoids a read/modify/write race.
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           last_http_status = :status,
                           last_check_error = :error,
                           fetch_error_count = fetch_error_count + 1,
                           is_active = CASE
                               WHEN fetch_error_count + 1 >= :threshold THEN false
                               ELSE is_active
                           END
                     WHERE feed_id = :feed_id
                    """,
                    {
                        "status": result.http_status,
                        "error": result.error,
                        "threshold": threshold,
                        "feed_id": feed_id,
                    },
                )
                if will_disable:
                    newly_disabled.append({
                        "feed_id": str(feed_id),
                        "feed_name": feed_name,
                        "feed_url": feed_url,
                        "consecutive_errors": new_errors,
                        "last_error": result.error,
                    })
                    _logger.warning(
                        f"source_health: auto-disabled dead feed '{feed_name}' "
                        f"after {new_errors} consecutive failures: {result.error}"
                    )
        except Exception as exc:
            _logger.warning(
                f"source_health: failed to update row for '{feed_name}': {exc}"
            )

    summary = {
        "status": "ok",
        "checked": checked,
        "healthy": healthy,
        "failed": failed,
        "auto_disabled": len(newly_disabled),
        "disabled_feeds": newly_disabled,
        "threshold": threshold,
    }
    _logger.info(f"source_health canary complete: {summary}")
    return summary
