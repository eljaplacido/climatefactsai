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


# Polish wave 2 hotfix (2026-05-26) — End2End audit found the
# reliability_scorer.calculate_reliability_score 3-axis params were
# silently ignored because none of the source_tier_service SELECTs
# projected editorial_score / factcheck_score / transparency_score
# from source_credibility_tiers. Mig 041 + 045 wrote them and fenced
# them never-null, but the data layer never propagated to the scorer.
# This helper closes the loop.

@lru_cache(maxsize=1024)
def _db_lookup_axes(
    db, domain: Optional[str], source_name: str
) -> Optional[Tuple[int, int, int]]:
    """Query 3-axis source scores (editorial, factcheck, transparency).

    Returns None when domain unknown or DB error — caller must treat
    None as 'fall back to legacy single-score path'.
    """
    if domain is None:
        return None
    try:
        rows = db.execute_query(
            """
            SELECT editorial_score, factcheck_score, transparency_score
            FROM source_credibility_tiers
            WHERE domain = :domain
            LIMIT 1
            """,
            {"domain": domain},
        )
        if rows:
            r = rows[0]
            ed = r.get("editorial_score")
            fc = r.get("factcheck_score")
            tr = r.get("transparency_score")
            if ed is None or fc is None or tr is None:
                return None
            return (int(ed), int(fc), int(tr))
        return None
    except Exception as exc:
        _logger.debug(f"source_tier 3-axis lookup failed ({domain}): {exc}")
        return None


def get_source_3axis_scores(
    db,
    source_name: str,
    domain: Optional[str] = None,
) -> Optional[Tuple[int, int, int]]:
    """Public helper: get (editorial, factcheck, transparency) for a source.

    Pairs with reliability_scorer.calculate_reliability_score's three
    new optional args. Caller passes the tuple's elements positionally
    or as kwargs; None on this side means scorer falls back to legacy.

    Domain extraction mirrors get_source_tier_prior. Cached via
    _db_lookup_axes LRU.
    """
    effective_domain = domain or _extract_domain(source_name)
    if effective_domain is None:
        return None
    return _db_lookup_axes(db, effective_domain, source_name)


# End2End audit gap (2026-05-27, Section II priority): articles.source_credibility_score
# was NULL or hardcoded 50 across the entire production corpus because no ingest
# path called the tier service. This helper closes the loop: given a source name
# or URL, return the 0-100 credibility score we'd stamp on a fresh article row.
# Maps the curated 79-tier table → tier band defaults.
_TIER_BASE_SCORE: Dict[str, int] = {
    "T1": 90,
    "T2": 75,
    "T3": 60,
    "unknown": 50,
    "retracted": 20,
}


def get_source_credibility_score(
    db,
    source_name: str,
    domain: Optional[str] = None,
) -> int:
    """Return the 0-100 source credibility score for a source name / URL.

    Looks the domain up in source_credibility_tiers (mig 027 + 041). Falls
    back to legacy LEGACY_KNOWN_VENUES (Nature/Science/Elsevier/...) → T1
    on miss, then to neutral 50. Always returns an int in [0, 100].

    Used by ingestion to stamp `articles.source_credibility_score` so the
    reliability scorer has real data to blend (the 0.5×source weighting
    was collapsing to 50 for every article before this helper).
    """
    bonus, tier = get_source_tier_prior(db, source_name, domain)
    base = _TIER_BASE_SCORE.get((tier or "unknown").lower(), 50)
    # The prior_bonus is additive (T1=30/T2=15/T3=5) but we already encode
    # the band in base; clamp the final score into [0, 100].
    return max(0, min(100, base))


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
    """Full profile for a domain (for /api/methodology/source-tiers).

    Polish wave 2 hotfix (2026-05-26): now projects the 3-axis scores
    (editorial / factcheck / transparency from mig 041/045) so the
    /methodology page surfaces them. Without this fix the JSON response
    omitted them entirely.
    """
    try:
        rows = db.execute_query(
            """
            SELECT source_name, domain, tier, prior_bonus, evidence_url,
                   classification, retracted_count, last_audited_at,
                   editorial_score, factcheck_score, transparency_score,
                   scoring_rubric_url, scoring_last_reviewed_at
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
                "editorial_score": int(r["editorial_score"]) if r.get("editorial_score") is not None else None,
                "factcheck_score": int(r["factcheck_score"]) if r.get("factcheck_score") is not None else None,
                "transparency_score": int(r["transparency_score"]) if r.get("transparency_score") is not None else None,
                "scoring_rubric_url": r.get("scoring_rubric_url"),
                "scoring_last_reviewed_at": str(r["scoring_last_reviewed_at"]) if r.get("scoring_last_reviewed_at") else None,
            }
        return None
    except Exception as exc:
        _logger.warning(f"get_source_tier_profile failed ({domain}): {exc}")
        return None


def list_all_source_tiers(db) -> list:
    """All tiered sources (for /api/methodology/source-tiers).

    Polish wave 2 hotfix (2026-05-26): now projects 3-axis scores.
    """
    try:
        rows = db.execute_query(
            """
            SELECT source_name, domain, tier, prior_bonus, evidence_url,
                   classification, retracted_count,
                   editorial_score, factcheck_score, transparency_score
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
                "editorial_score": int(r["editorial_score"]) if r.get("editorial_score") is not None else None,
                "factcheck_score": int(r["factcheck_score"]) if r.get("factcheck_score") is not None else None,
                "transparency_score": int(r["transparency_score"]) if r.get("transparency_score") is not None else None,
            }
            for r in (rows or [])
        ]
    except Exception as exc:
        _logger.warning(f"list_all_source_tiers failed: {exc}")
        return []
