"""ML-03 — ingestion quality gate.

The single choke-point that keeps boilerplate / interstitial / thin bodies out
of the corpus BEFORE a row is inserted and, critically, before any paid LLM
enrichment / embedding / claim-verification spend.

Root cause it defends against: the Google-News RSS feeds hand out
``news.google.com/rss/articles/<opaque>`` *redirector* links. Fetching one
returns HTTP 200 whose body is Google's cookie-consent interstitial ("If you
choose to 'Accept all' … 'Reject all' … g.co/privacytools"), not the article.
1,433 such rows reached production, 906 were enriched, 858 embedded, 786 given
claim verdicts — broken data served with full credibility.

The gate rejects an article when ANY of these holds:
  * the body is a known consent-wall / interstitial signature;
  * the body's md5 matches a known-boilerplate hash (the observed consent wall
    is one exact 835-char body repeated 1,433×, md5 94a38797…);
  * the cleaned body has fewer than ``min_body_chars`` real characters;
  * the title is empty;
  * the URL is empty or an unresolved redirector (e.g. a Google-News
    ``/rss/articles/`` link that was never resolved to a publisher URL).

Rejected inputs are routed to the ``article_ingest_quarantine`` table (see
migration 073) via :func:`quarantine_article` so every drop is auditable rather
than silently lost.

Pure + dependency-light on purpose: :func:`check_article_quality` does no I/O so
it is trivially unit-testable; the DB write lives in :func:`quarantine_article`.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

# Minimum count of real characters a body must carry to be worth ingesting.
# Env-overridable for backfills / experiments. The observed poison is either the
# 835-char consent wall (caught by signature/md5) or a 45-208 char "Headline -
# Publisher" stub (caught here).
DEFAULT_MIN_BODY_CHARS = int(os.getenv("INGEST_MIN_BODY_CHARS", "250"))

# md5 hexdigests of bodies known to be boilerplate. Seeded with the Google
# cookie-consent interstitial that was ingested 1,433× (one identical 835-char
# body). This is the "seen-N+-times / known-boilerplate hash" list: when a body
# hash is observed to recur as boilerplate it gets added here so the exact bytes
# are rejected outright even if the textual signature ever changes.
KNOWN_BOILERPLATE_MD5S: Set[str] = {
    "94a38797a13f417b263c9c7c78c93f08",  # Google News cookie-consent wall (ML-03)
}

# Redirector hosts whose article links are NOT canonical publisher URLs. A row
# must never be stored pointing at one of these — the real article lives behind
# a redirect the ingester could not resolve, so the fetched body is the
# redirector's own interstitial, not journalism.
_REDIRECTOR_HOSTS = ("news.google.com",)


@dataclass(frozen=True)
class GateResult:
    """Outcome of :func:`check_article_quality`.

    ``ok``       — True when the article may be ingested.
    ``category`` — machine-stable bucket for quarantine/audit grouping.
    ``reason``   — human-readable detail for logs / the quarantine row.
    """

    ok: bool
    category: str  # 'ok'|'consent_wall'|'boilerplate_md5'|'thin_body'|'missing_title'|'redirector_url'
    reason: str


def body_md5(body: Optional[str]) -> str:
    """Stable md5 hexdigest of a body (empty string for None)."""
    return hashlib.md5((body or "").encode("utf-8", "replace")).hexdigest()


def is_redirector_url(url: Optional[str]) -> bool:
    """True when ``url`` is a known redirector, not a canonical article URL.

    Matches Google-News ``/rss/articles/…`` and ``/articles/…`` redirector
    links (the source of the ML-03 consent-wall poison). A publisher URL that a
    resolver has already substituted in passes this check.
    """
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    host = (p.netloc or "").lower()
    if not any(host == h or host.endswith("." + h) for h in _REDIRECTOR_HOSTS):
        return False
    path = (p.path or "").lower()
    return "/rss/articles/" in path or path.startswith("/articles/") or "/read/" in path


def is_consent_wall(body: Optional[str]) -> bool:
    """True when ``body`` is a cookie-consent / interstitial wall, not an article.

    Conservative: keys on Google-specific markers (``g.co/privacytools``, the
    "Non-personalized content" copy) or the paired Accept-all/Reject-all cookie
    prompt, so a genuine article that merely mentions "accept" or "cookies" is
    not mis-flagged.
    """
    if not body:
        return False
    b = body.lower()
    if "g.co/privacytools" in b:
        return True
    if "before you continue to google" in b:
        return True
    if "non-personalized content is influenced" in b:
        return True
    if "accept all" in b and "reject all" in b and (
        "cookies" in b or "non-personalized" in b or "privacy" in b
    ):
        return True
    return False


def check_article_quality(
    *,
    title: Optional[str],
    url: Optional[str],
    body: Optional[str],
    source_name: Optional[str] = None,
    min_body_chars: Optional[int] = None,
    known_md5s: Optional[Set[str]] = None,
) -> GateResult:
    """Decide whether an article may be ingested.

    ``body`` should be the cleaned body that would actually be stored in
    ``articles.extracted_text``. Pure function — no I/O.
    """
    min_chars = DEFAULT_MIN_BODY_CHARS if min_body_chars is None else min_body_chars
    md5s = KNOWN_BOILERPLATE_MD5S if known_md5s is None else known_md5s

    clean_title = (title or "").strip()
    if not clean_title:
        return GateResult(False, "missing_title", "empty or missing title")

    if not url or not url.strip():
        return GateResult(False, "redirector_url", "empty or missing URL")
    if is_redirector_url(url):
        return GateResult(
            False,
            "redirector_url",
            f"unresolved redirector URL (not a canonical publisher URL): {url[:120]}",
        )

    clean_body = (body or "").strip()

    if is_consent_wall(clean_body):
        return GateResult(
            False, "consent_wall", "body is a cookie-consent / interstitial wall"
        )

    if body_md5(clean_body) in md5s:
        return GateResult(
            False, "boilerplate_md5", "body md5 matches a known-boilerplate hash"
        )

    if len(clean_body) < min_chars:
        return GateResult(
            False,
            "thin_body",
            f"body has {len(clean_body)} real chars (< {min_chars} minimum)",
        )

    return GateResult(True, "ok", "passed ingestion quality gate")


def quarantine_article(
    db,
    *,
    url: Optional[str],
    title: Optional[str],
    source_name: Optional[str],
    reason: str,
    category: str,
    raw_input: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a rejected article in ``article_ingest_quarantine`` (best-effort).

    Never raises — a quarantine-write failure must not abort the ingest loop.
    ``raw_input`` is serialised to JSON with a str fallback so datetimes and
    other non-JSON values don't break the write.
    """
    try:
        raw_json = json.dumps(raw_input or {}, default=str)[:20000]
    except Exception:
        raw_json = "{}"
    try:
        db.execute_update(
            """
            INSERT INTO article_ingest_quarantine
                (url, title, source_name, body_md5, reason, category, raw_input, created_at)
            VALUES
                (:url, :title, :source_name, :body_md5, :reason, :category,
                 CAST(:raw_input AS JSONB), NOW())
            """,
            {
                "url": (url or "")[:2000] or None,
                "title": (title or "")[:1000] or None,
                "source_name": (source_name or "")[:255] or None,
                "body_md5": body_md5(
                    (raw_input or {}).get("extracted_text")
                    or (raw_input or {}).get("content")
                    or (raw_input or {}).get("summary")
                    or ""
                ),
                "reason": reason[:1000],
                "category": category[:40],
                "raw_input": raw_json,
            },
        )
    except Exception as exc:  # pragma: no cover - audit write must never block ingest
        logger.warning("ML-03 quarantine write failed", url=url, error=str(exc))


__all__ = [
    "GateResult",
    "check_article_quality",
    "quarantine_article",
    "is_consent_wall",
    "is_redirector_url",
    "body_md5",
    "KNOWN_BOILERPLATE_MD5S",
    "DEFAULT_MIN_BODY_CHARS",
]
