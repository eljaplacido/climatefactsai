"""
Source credibility tier lookup — replaces the 8-publisher KNOWN_VENUES hardcode.

Reads from `source_credibility_tiers` (migration 027) seeded with
Scimago JR, RetractionWatch, and IFCN data. Falls back to the legacy
hardcoded set when the table doesn't exist yet.

All lookups are LRU-cached for the lifetime of the process; the cache
is invalidated via the `refresh-source-tiers` Celery beat task.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urlparse

_logger = logging.getLogger("source_tier_service")

LEGACY_KNOWN_VENUES = {
    "Nature", "Science", "Elsevier", "Springer",
    "Wiley", "PLOS", "Frontiers", "Copernicus",
}

LEGACY_TIER_BONUS = 30


def _extract_domain(source_name_or_url: str) -> Optional[str]:
    """Best-effort domain extraction from a source name or URL."""
    s = source_name_or_url.strip().lower()
    if s.startswith(("http://", "https://")):
        parsed = urlparse(s)
        domain = parsed.netloc or parsed.hostname
        if domain:
            domain = re.sub(r"^www\.", "", domain)
            return domain
        return None
    if "/" in s:
        return None
    return s


@lru_cache(maxsize=1024)
def _db_lookup(db, domain: Optional[str], source_name: str) -> Optional[Tuple[int, str]]:
    """Query source_credibility_tiers, returns (prior_bonus, tier) or None."""
    if domain is None:
        return None
    try:
        rows = db.execute_query(
            """
            SELECT prior_bonus, tier
            FROM source_credibility_tiers
            WHERE domain = :domain
            LIMIT 1
            """,
            {"domain": domain},
        )
        if rows:
            return (int(rows[0]["prior_bonus"] or 0), str(rows[0].get("tier") or "unknown"))
        return None
    except Exception as exc:
        _logger.debug(f"source_tier DB lookup failed ({domain}): {exc}")
        return None


def get_source_tier_prior(
    db,
    source_name: str,
    domain: Optional[str] = None,
) -> Tuple[int, str]:
    """Return (prior_bonus, tier_label) for a source.

    Priority:
      1. DB lookup on domain (if available)
      2. DB lookup on domain extracted from source_name
      3. Legacy hardcoded KNOWN_VENUES fallback
      4. Default (0, 'unknown')

    Args:
        db: Database connection.
        source_name: Source name or URL.
        domain: Explicit domain override.

    Returns:
        (prior_bonus, tier_label) — bonus is the additive credibility
        boost (T1=30, T2=15, T3=5, unknown=0, retracted=-30).
    """
    effective_domain = domain or _extract_domain(source_name)

    if effective_domain:
        result = _db_lookup(db, effective_domain, source_name)
        if result is not None:
            return result

    if source_name and source_name in LEGACY_KNOWN_VENUES:
        _logger.debug(
            "source_tier: legacy fallback for %s (migration 027 not yet seeded?)",
            source_name,
        )
        return (LEGACY_TIER_BONUS, "T1")

    return (0, "unknown")


def clear_tier_cache() -> None:
    """Invalidate the LRU cache (called by refresh-source-tiers beat task)."""
    _db_lookup.cache_clear()
    _logger.info("source_tier_service cache cleared")


def get_source_tier_profile(db, domain: str) -> Optional[dict]:
    """Full profile for a domain (for /api/methodology/source-tiers)."""
    try:
        rows = db.execute_query(
            """
            SELECT source_name, domain, tier, prior_bonus, evidence_url,
                   classification, retracted_count, last_audited_at
            FROM source_credibility_tiers
            WHERE domain = :domain
            LIMIT 1
            """,
            {"domain": domain},
        )
        if rows:
            r = rows[0]
            return {
                "source_name": r.get("source_name"),
                "domain": r.get("domain"),
                "tier": r.get("tier"),
                "prior_bonus": int(r.get("prior_bonus") or 0),
                "evidence_url": r.get("evidence_url"),
                "classification": r.get("classification"),
                "retracted_count": int(r.get("retracted_count") or 0),
                "last_audited_at": str(r.get("last_audited_at")) if r.get("last_audited_at") else None,
            }
        return None
    except Exception as exc:
        _logger.warning(f"get_source_tier_profile failed ({domain}): {exc}")
        return None


def list_all_source_tiers(db) -> list:
    """All tiered sources (for /api/methodology/source-tiers)."""
    try:
        rows = db.execute_query(
            """
            SELECT source_name, domain, tier, prior_bonus, evidence_url,
                   classification, retracted_count
            FROM source_credibility_tiers
            ORDER BY tier, source_name
            """,
            {},
        )
        return [
            {
                "source_name": r.get("source_name"),
                "domain": r.get("domain"),
                "tier": r.get("tier"),
                "prior_bonus": int(r.get("prior_bonus") or 0),
                "evidence_url": r.get("evidence_url"),
                "classification": r.get("classification"),
                "retracted_count": int(r.get("retracted_count") or 0),
            }
            for r in (rows or [])
        ]
    except Exception as exc:
        _logger.warning(f"list_all_source_tiers failed: {exc}")
        return []
