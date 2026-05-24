"""
URL Analysis Routes - Premium Feature

Allows users to submit custom URLs for fact-checking analysis.
This service fetches content, extracts claims, and runs verification.

NO KAFKA DEPENDENCY - Works synchronously with database polling.
"""

import hashlib
import os
import re
from typing import List, Optional
from datetime import datetime, timezone
from uuid import uuid4, UUID
from urllib.parse import urlparse
import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl, Field, validator

from api.auth_routes import get_current_user, get_optional_user
from api.rate_limiter import UsageTracker, check_premium_feature

# Import from src/backend/shared (correct path)
import sys
from pathlib import Path

# Add src/backend to path
SRC_BACKEND = Path(__file__).resolve().parents[1] / "src" / "backend"
if str(SRC_BACKEND) not in sys.path:
    sys.path.insert(0, str(SRC_BACKEND))

from shared.database import get_postgres
from shared.logger import setup_logging

# Import intelligence service components
from app.domains.intelligence.services import ClaimExtractor

logger = setup_logging("url-analysis-api")
router = APIRouter(prefix="/api/analyze-url", tags=["URL Analysis"])

ANONYMOUS_UUID = "00000000-0000-0000-0000-000000000000"
ANONYMOUS_URL_ANALYSIS_EMAIL = os.getenv(
    "ANONYMOUS_URL_ANALYSIS_EMAIL",
    "anonymous-url-analysis@climatenews.local",
)


def _read_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read bounded integer from env; fallback to sane defaults on bad values."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            f"Invalid integer for {name}: {raw!r}. Falling back to {default}."
        )
        return default

    if value < minimum:
        logger.warning(
            f"{name}={value} below minimum {minimum}. Using {minimum}."
        )
        return minimum

    if value > maximum:
        logger.warning(
            f"{name}={value} above maximum {maximum}. Using {maximum}."
        )
        return maximum

    return value


def _coerce_utc_naive_datetime(value: object) -> Optional[datetime]:
    """Normalize DB datetime payloads to naive UTC datetimes."""
    if value is None:
        return None

    dt_value: Optional[datetime] = None
    if isinstance(value, datetime):
        dt_value = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt_value = datetime.fromisoformat(raw)
        except ValueError:
            return None

    if dt_value is None:
        return None

    if dt_value.tzinfo is not None:
        return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
    return dt_value


def _timeout_stale_processing_analysis(db, analysis_id: str, row: dict) -> dict:
    """
    Fail stale URL analyses stuck in pending/processing for too long.

    This prevents indefinite spinner states when the background task crashes or
    does not complete.
    """
    current_status = str(row.get("status") or "").lower()
    if current_status not in {"pending", "processing"}:
        return row

    timeout_minutes = _read_int_env(
        name="URL_ANALYSIS_PROCESSING_TIMEOUT_MIN",
        default=20,
        minimum=1,
        maximum=24 * 60,
    )

    reference_dt = _coerce_utc_naive_datetime(row.get("processing_started_at"))
    if reference_dt is None:
        reference_dt = _coerce_utc_naive_datetime(row.get("created_at"))

    if reference_dt is None:
        return row

    now_utc = datetime.utcnow()
    elapsed_ms = int((now_utc - reference_dt).total_seconds() * 1000)
    if elapsed_ms < timeout_minutes * 60 * 1000:
        return row

    timeout_message = (
        "URL analysis timed out before completion. "
        "Please retry with a shorter or more accessible URL."
    )

    try:
        db.execute_update(
            """
            UPDATE url_analyses
            SET status = 'failed',
                error_message = COALESCE(error_message, :error),
                completed_at = COALESCE(completed_at, NOW()),
                processing_time_ms = COALESCE(processing_time_ms, :elapsed_ms),
                updated_at = NOW()
            WHERE analysis_id = :analysis_id
              AND status IN ('pending', 'processing')
            """,
            {
                "analysis_id": analysis_id,
                "error": timeout_message,
                "elapsed_ms": max(elapsed_ms, 0),
            },
        )
    except Exception as exc:
        logger.warning(f"Failed to persist URL analysis timeout state for {analysis_id}: {exc}")

    updated_row = dict(row)
    updated_row["status"] = "failed"
    if not updated_row.get("error_message"):
        updated_row["error_message"] = timeout_message
    if not updated_row.get("completed_at"):
        updated_row["completed_at"] = now_utc
    if not updated_row.get("processing_time_ms"):
        updated_row["processing_time_ms"] = max(elapsed_ms, 0)

    logger.warning(
        "URL analysis marked failed after timeout",
        analysis_id=analysis_id,
        timeout_minutes=timeout_minutes,
    )
    return updated_row


def _ensure_anonymous_user_id(db) -> Optional[str]:
    """Best-effort ensure a synthetic anonymous user exists for FK-based schemas."""
    try:
        existing = db.execute_query(
            "SELECT user_id FROM users WHERE email = :email LIMIT 1",
            {"email": ANONYMOUS_URL_ANALYSIS_EMAIL},
        )
        if existing and existing[0].get("user_id"):
            return str(existing[0]["user_id"])
    except Exception as exc:
        logger.warning(f"Could not look up anonymous user: {exc}")

    try:
        from api.auth_utils import PasswordHasher, TokenGenerator

        password_hash = PasswordHasher.hash_password(TokenGenerator.generate_verification_token())
        created = db.execute_query(
            """
            INSERT INTO users (email, password_hash)
            VALUES (:email, :password_hash)
            ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
            RETURNING user_id
            """,
            {
                "email": ANONYMOUS_URL_ANALYSIS_EMAIL,
                "password_hash": password_hash,
            },
        )
        if created and created[0].get("user_id"):
            return str(created[0]["user_id"])
    except Exception as exc:
        logger.warning(f"Could not create anonymous user: {exc}")

    try:
        existing = db.execute_query(
            "SELECT user_id FROM users WHERE email = :email LIMIT 1",
            {"email": ANONYMOUS_URL_ANALYSIS_EMAIL},
        )
        if existing and existing[0].get("user_id"):
            return str(existing[0]["user_id"])
    except Exception:
        pass

    return None


def _insert_url_analysis_record(
    db,
    analysis_id: str,
    user_id: str,
    url: str,
    url_hash: str,
    source_domain: str,
) -> str:
    """
    Insert into url_analyses with schema-compatibility fallbacks.

    Handles both variants seen in production:
    - `priority` column present / absent
    - `user_id` freely writable / FK-constrained to `users.user_id`
    """

    def _attempt_insert(candidate_user_id: str) -> bool:
        common_params = {
            "analysis_id": analysis_id,
            "user_id": candidate_user_id,
            "url": url,
            "url_hash": url_hash,
            "domain": source_domain,
        }

        with_priority = """
            INSERT INTO url_analyses (
                analysis_id, user_id, submitted_url, url_hash, source_domain,
                status, priority, created_at, updated_at
            ) VALUES (
                :analysis_id, :user_id, :url, :url_hash, :domain,
                'pending', 'normal', NOW(), NOW()
            )
        """

        without_priority = """
            INSERT INTO url_analyses (
                analysis_id, user_id, submitted_url, url_hash, source_domain,
                status, created_at, updated_at
            ) VALUES (
                :analysis_id, :user_id, :url, :url_hash, :domain,
                'pending', NOW(), NOW()
            )
        """

        try:
            db.execute_update(with_priority, common_params)
            return True
        except Exception as first_err:
            try:
                db.execute_update(without_priority, common_params)
                logger.warning(
                    f"Fell back to url_analyses insert without priority column: {first_err}"
                )
                return True
            except Exception:
                return False

    if _attempt_insert(user_id):
        return user_id

    if user_id == ANONYMOUS_UUID:
        fk_compatible_user_id = _ensure_anonymous_user_id(db)
        if fk_compatible_user_id and fk_compatible_user_id != user_id:
            if _attempt_insert(fk_compatible_user_id):
                logger.info(
                    "URL analysis anonymous user fallback succeeded",
                    fallback_user_id=fk_compatible_user_id,
                )
                return fk_compatible_user_id

    raise RuntimeError("Failed to insert URL analysis record in compatible schema mode")


def _normalize_claim_text_for_dedupe(claim_text: Optional[str]) -> str:
    if not claim_text:
        return ""
    normalized = re.sub(r"\s+", " ", claim_text.strip().lower())
    normalized = re.sub(r"[^a-z0-9\s%.,:/\-]", "", normalized)
    compact = normalized.replace(" ", "")
    return compact[:600]


def _dedupe_claim_objects(claims: List) -> List:
    """Deduplicate claim objects by normalized claim text, keeping highest importance."""
    best_by_text = {}
    for claim in claims:
        key = _normalize_claim_text_for_dedupe(getattr(claim, "claim_text", ""))
        if not key:
            continue
        prev = best_by_text.get(key)
        if prev is None or (getattr(claim, "importance_score", 0) or 0) > (getattr(prev, "importance_score", 0) or 0):
            best_by_text[key] = claim
    return list(best_by_text.values())


async def _extract_claims_for_long_text(
    extractor: ClaimExtractor,
    text: str,
    max_total_claims: int,
) -> List:
    """
    Extract claims from long text by chunking and deduplicating.

    Defaults are tuned for long reports while keeping LLM token usage bounded.
    """
    chunk_chars = _read_int_env(
        name="URL_ANALYSIS_CLAIM_CHUNK_CHARS",
        default=12000,
        minimum=4000,
        maximum=40000,
    )
    overlap_chars = _read_int_env(
        name="URL_ANALYSIS_CLAIM_CHUNK_OVERLAP_CHARS",
        default=1000,
        minimum=0,
        maximum=5000,
    )
    max_chunks = _read_int_env(
        name="URL_ANALYSIS_MAX_CLAIM_CHUNKS",
        default=24,
        minimum=1,
        maximum=200,
    )
    per_chunk_claim_cap = _read_int_env(
        name="URL_ANALYSIS_MAX_CLAIMS_PER_CHUNK",
        default=8,
        minimum=1,
        maximum=25,
    )

    if overlap_chars >= chunk_chars:
        overlap_chars = max(0, chunk_chars // 5)

    text_len = len(text or "")
    if text_len <= chunk_chars:
        return await extractor.decompose_claims(text, max_claims=max_total_claims)

    step = max(1, chunk_chars - overlap_chars)
    all_chunks = []
    for start in range(0, text_len, step):
        end = min(text_len, start + chunk_chars)
        if end >= text_len:
            break

        chunk = (text[start:end] or "").strip()
        if len(chunk) >= 100:
            all_chunks.append(chunk)

    if not all_chunks:
        return []

    if len(all_chunks) <= max_chunks:
        chunks = all_chunks
    elif max_chunks == 1:
        chunks = [all_chunks[0]]
    else:
        last_idx = len(all_chunks) - 1
        selected_indices = {
            round(i * (last_idx / (max_chunks - 1)))
            for i in range(max_chunks)
        }
        chunks = [all_chunks[i] for i in sorted(selected_indices)]

    logger.info(
        "Running chunked claim extraction",
        text_length=text_len,
        chunk_count=len(chunks),
        all_chunk_count=len(all_chunks),
        chunk_chars=chunk_chars,
        overlap_chars=overlap_chars,
        max_total_claims=max_total_claims,
    )

    extracted = []
    for idx, chunk in enumerate(chunks, start=1):
        remaining = max_total_claims - len(extracted)
        if remaining <= 0:
            break

        chunk_claim_limit = min(per_chunk_claim_cap, remaining)
        try:
            chunk_claims = await extractor.decompose_claims(chunk, max_claims=chunk_claim_limit)
        except Exception as chunk_err:
            logger.warning(f"Chunk {idx}/{len(chunks)} claim extraction failed: {chunk_err}")
            continue

        if chunk_claims:
            extracted.extend(chunk_claims)

    deduped = _dedupe_claim_objects(extracted)
    deduped.sort(key=lambda c: getattr(c, "importance_score", 0) or 0, reverse=True)
    return deduped[:max_total_claims]

# =============================================================================
# SAFE-URL VALIDATION + REDIRECT-AWARE FETCH (SSRF hardening, S6)
# =============================================================================

def _validate_safe_url(url_str: str) -> None:
    """
    Raise ValueError if `url_str` resolves to anything we must not fetch.

    Called from two places:
    - AnalyzeURLRequest's Pydantic validator (initial submission)
    - _safe_fetch's manual redirect loop (every hop)

    Closes the DNS-rebinding / open-redirect gap where the initial host
    resolved to a public IP but a redirect target (or a TTL-1 DNS swap) points
    at 169.254.169.254, 10.x, or a metadata service.
    """
    import ipaddress
    import socket

    if not url_str:
        raise ValueError("Empty URL")

    if len(url_str) > 2048:
        raise ValueError("URL exceeds maximum length of 2048 characters")

    parsed = urlparse(url_str)

    # Only HTTPS at the top level — redirects from HTTPS may NOT downgrade
    # to HTTP (would otherwise leak the Authorization header etc.).
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed (redirect downgrade blocked)")

    hostname = (parsed.hostname or "").lower().strip("[]")

    blocked_hosts = {
        "localhost", "127.0.0.1", "0.0.0.0", "::1", "",
        "metadata.google.internal", "metadata.goog",
    }
    if hostname in blocked_hosts:
        raise ValueError("Cannot analyze localhost or internal URLs")

    blocked_tlds = (".internal", ".local", ".localhost")
    for tld in blocked_tlds:
        if hostname.endswith(tld):
            raise ValueError(f"Cannot analyze URLs with {tld} TLD")

    try:
        ip = ipaddress.ip_address(hostname)
        if (
            ip.is_private or ip.is_reserved or ip.is_loopback
            or ip.is_link_local or ip.is_multicast
        ):
            raise ValueError("Cannot analyze private, reserved, or internal IP addresses")
    except ValueError as ve:
        if "Cannot analyze" in str(ve):
            raise
        # Hostname (not literal IP) → DNS check.
        try:
            resolved_ips = socket.getaddrinfo(
                hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
            for family, socktype, proto, canonname, sockaddr in resolved_ips:
                resolved_ip = ipaddress.ip_address(sockaddr[0])
                if (
                    resolved_ip.is_private or resolved_ip.is_reserved
                    or resolved_ip.is_loopback or resolved_ip.is_link_local
                ):
                    raise ValueError(
                        f"DNS rebinding detected: {hostname} resolves to private IP {sockaddr[0]}"
                    )
        except socket.gaierror:
            raise ValueError(f"Cannot resolve hostname: {hostname}")


async def _safe_fetch(client, url: str, *, headers: dict, max_redirects: int = 5):
    """
    Fetch a URL with MANUAL redirect handling that re-validates each hop.

    httpx's `follow_redirects=True` will silently follow a 30x to any host,
    including private IPs after a DNS swap or an attacker-controlled open
    redirect. This loop re-runs `_validate_safe_url` on every Location, so
    a redirect to http://internal.example or 169.254.169.254 gets blocked.
    """
    from urllib.parse import urljoin as _urljoin

    current_url = url
    for _ in range(max_redirects + 1):
        resp = await client.get(current_url, headers=headers, follow_redirects=False)
        if 300 <= resp.status_code < 400:
            location = resp.headers.get("location")
            if not location:
                return resp  # 3xx without Location — surface as-is to caller
            next_url = _urljoin(current_url, location)
            try:
                _validate_safe_url(next_url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Redirect blocked: {e}")
            current_url = next_url
            continue
        return resp
    raise HTTPException(status_code=400, detail="Too many redirects (max 5)")


# =============================================================================
# JOB-ACCESS TOKEN (S7: defend against UUID-guessing on anonymous GETs)
# =============================================================================

def _job_token_secret() -> bytes:
    """Secret used to HMAC-sign per-analysis access tokens.

    Falls back to a deterministic dev secret only if JWT_SECRET_KEY is missing;
    in production JWT_SECRET_KEY is required at boot in api/auth_utils, so this
    fallback is effectively only hit by unit tests with no env wired up.
    """
    secret = os.getenv("JWT_SECRET_KEY", "") or "dev-job-token-fallback-not-for-prod"
    return secret.encode("utf-8")


def _generate_job_token(analysis_id: str) -> str:
    """HMAC-SHA256 token (32-hex prefix) bound to one analysis_id."""
    import hmac as _hmac
    msg = f"url_analysis_v1:{analysis_id}".encode("utf-8")
    return _hmac.new(_job_token_secret(), msg, hashlib.sha256).hexdigest()[:32]


def _verify_job_token(token: Optional[str], analysis_id: str) -> bool:
    """Constant-time check of a job-access token."""
    if not token:
        return False
    import hmac as _hmac
    return _hmac.compare_digest(token, _generate_job_token(analysis_id))


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AnalyzeURLRequest(BaseModel):
    """Request to analyze a custom URL"""
    url: HttpUrl = Field(..., description="URL to analyze (HTTPS only)")

    @validator('url')
    def validate_url(cls, v):
        """Validate URL format and security via the shared _validate_safe_url helper."""
        url_str = str(v)
        # _validate_safe_url raises ValueError — Pydantic re-raises as 422.
        _validate_safe_url(url_str)
        return v


class URLAnalysisJobResponse(BaseModel):
    """Response when URL analysis is submitted"""
    job_id: str
    status: str  # "processing", "completed", "failed"
    estimated_time: int = 30  # seconds
    # HMAC-signed token (S7). Anonymous users MUST pass it as ?token=... on
    # subsequent GET /api/analyze-url/{job_id} calls. Authenticated owners can
    # omit it. Without this gate, anyone who guessed a job UUID could read
    # another user's submitted URL + extracted text + claims.
    access_token: str


class URLAnalysisStatus(BaseModel):
    """Status of a URL analysis"""
    analysis_id: str
    submitted_url: str
    status: str  # pending, processing, completed, failed

    # Content
    title: Optional[str] = None
    source_name: Optional[str] = None
    source_domain: Optional[str] = None

    # Results
    claims_found: int = 0
    claims_verified: int = 0
    reliability_score: Optional[int] = None
    overall_credibility: Optional[str] = None

    # Metadata
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None


class URLAnalysisDetail(BaseModel):
    """Detailed URL analysis result with claims"""
    analysis_id: str
    submitted_url: str
    status: str

    # Source info
    source_name: Optional[str] = None
    source_domain: Optional[str] = None
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    language_code: Optional[str] = None
    published_date: Optional[datetime] = None

    # Analysis results
    reliability_score: Optional[int] = None
    overall_credibility: Optional[str] = None
    # Phase 5 wave 5 (2026-05-16): the platform applies the most-recent
    # Platt-scaled calibration to `reliability_score` when a fit exists
    # in `calibration_fits`. Returns None when no fit is available yet —
    # callers fall back to `reliability_score`.
    calibrated_reliability_score: Optional[float] = None

    # Claims (as JSON array)
    extracted_claims: List[dict] = Field(default_factory=list)
    fact_checks: List[dict] = Field(default_factory=list)

    # Metadata
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    # Structured failure surface (migration 031). Present when status == 'failed'
    # AND the failure was classified. Legacy rows + legacy error paths have
    # these as None and the frontend falls back to `error_message`.
    failure_reason: Optional[str] = None
    failure_detail: Optional[dict] = None


# =============================================================================
# URL CONTENT FETCHING SERVICE
# =============================================================================

# Structured failure reasons (migration 031). Each value MUST stay stable —
# the frontend keys off it to pick an icon, explanation, and remediation hint.
FAILURE_REASON_HTTP_FORBIDDEN = "http_forbidden"
FAILURE_REASON_HTTP_NOT_FOUND = "http_not_found"
FAILURE_REASON_HTTP_LEGAL_BLOCK = "http_legal_block"
FAILURE_REASON_HTTP_4XX_OTHER = "http_4xx_other"
FAILURE_REASON_HTTP_5XX = "http_5xx"
FAILURE_REASON_TIMEOUT = "timeout"
FAILURE_REASON_RESPONSE_TOO_LARGE = "response_too_large"
FAILURE_REASON_EXTRACTION_TOO_SHORT = "extraction_too_short"
FAILURE_REASON_PAYWALL_SUSPECTED = "paywall_suspected"
FAILURE_REASON_JS_RENDERED_SPA = "js_rendered_spa"
FAILURE_REASON_REDIRECT_BLOCKED = "redirect_blocked"
FAILURE_REASON_NETWORK_ERROR = "network_error"
FAILURE_REASON_VALIDATION_FAILED = "validation_failed"
FAILURE_REASON_CLAIM_EXTRACTION_FAILED = "claim_extraction_failed"
FAILURE_REASON_UNKNOWN = "unknown"


# Per-reason copy + remediation. Kept here so the backend stays the single
# source of truth for the failure surface; the frontend just renders the JSON.
_FAILURE_COPY: dict = {
    FAILURE_REASON_HTTP_FORBIDDEN: {
        "title": "Source blocked our reader",
        "message": (
            "The site returned HTTP 403, which usually means automated access is "
            "blocked (Cloudflare bot protection, anti-scraping rules, or robots.txt "
            "deny). The article likely exists but we cannot fetch it server-side."
        ),
        "remediation": (
            "Open the article in your browser, copy the visible text, and use the "
            "Research → Paste text mode at /research to analyze it. Professional "
            "tier will add a Playwright fallback for verified domains."
        ),
    },
    FAILURE_REASON_HTTP_NOT_FOUND: {
        "title": "Page not found",
        "message": (
            "The URL returned HTTP 404. The article may have moved, been deleted, "
            "or the link contains a typo."
        ),
        "remediation": (
            "Double-check the URL on the publisher's site. If the article was "
            "redirected, copy the new URL and resubmit."
        ),
    },
    FAILURE_REASON_HTTP_LEGAL_BLOCK: {
        "title": "Content blocked for legal reasons",
        "message": (
            "The source returned HTTP 451 — content unavailable in this jurisdiction "
            "for legal reasons (e.g. court-ordered takedown, GDPR / DMCA block)."
        ),
        "remediation": (
            "Try an archived copy via web.archive.org, or paste the text directly "
            "into /research if you have legitimate access."
        ),
    },
    FAILURE_REASON_HTTP_4XX_OTHER: {
        "title": "Source rejected our request",
        "message": (
            "The site returned a 4xx HTTP error. This usually indicates an "
            "authentication requirement, a malformed URL, or a deliberate block."
        ),
        "remediation": (
            "Verify the URL works in your browser. For login-walled content, "
            "paste the article text into /research instead."
        ),
    },
    FAILURE_REASON_HTTP_5XX: {
        "title": "Source server failed",
        "message": (
            "The publisher's server returned a 5xx error. This is a problem on "
            "their end, not ours — they may be down or rate-limiting."
        ),
        "remediation": "Wait a few minutes and try the same URL again.",
    },
    FAILURE_REASON_TIMEOUT: {
        "title": "Source took too long to respond",
        "message": (
            "We waited 45 seconds for the page to load and it did not respond. "
            "Either the site is slow today or it intentionally stalls non-browser "
            "clients."
        ),
        "remediation": (
            "Retry the URL; if it consistently times out, the site likely has "
            "anti-scraping latency walls. Paste the text into /research."
        ),
    },
    FAILURE_REASON_RESPONSE_TOO_LARGE: {
        "title": "Article exceeds size limit",
        "message": (
            "The fetched page was larger than the configured ceiling. We cap "
            "responses to keep extraction bounded; some PDFs or long-form reports "
            "exceed it."
        ),
        "remediation": (
            "Try the article's HTML version instead of a PDF, or submit a "
            "shorter URL pointing to just the article (not the homepage)."
        ),
    },
    FAILURE_REASON_EXTRACTION_TOO_SHORT: {
        "title": "Couldn't find article body",
        "message": (
            "We fetched the page but couldn't extract more than ~50 characters of "
            "readable text. The article body may be inside an image, video, or a "
            "deeply non-standard HTML structure."
        ),
        "remediation": (
            "Use /research → Paste text mode and paste the article body directly."
        ),
    },
    FAILURE_REASON_PAYWALL_SUSPECTED: {
        "title": "Paywall detected",
        "message": (
            "The page loaded but only returned a short stub with subscription / "
            "premium-content keywords. The full article is gated behind a paywall."
        ),
        "remediation": (
            "If you have a subscription, open the article in your browser and "
            "paste the text into /research. Otherwise try an open-access summary "
            "from the same publisher."
        ),
    },
    FAILURE_REASON_JS_RENDERED_SPA: {
        "title": "JavaScript-rendered page",
        "message": (
            "The site appears to render its article body via JavaScript after the "
            "initial HTML loads. Our server-side fetcher only sees the empty shell. "
            "We are planning a Playwright-rendered fallback for verified domains."
        ),
        "remediation": (
            "For now, paste the article text into /research. If this site is "
            "important to you, request Playwright support via /suggest-source."
        ),
    },
    FAILURE_REASON_REDIRECT_BLOCKED: {
        "title": "Redirect blocked for safety",
        "message": (
            "The URL tried to redirect to a private network address (DNS rebinding "
            "or open-redirect attempt). We block these to prevent the platform "
            "from being abused as an SSRF gadget."
        ),
        "remediation": (
            "Verify the URL is the publisher's real article URL, not a shortener "
            "or open-redirect link."
        ),
    },
    FAILURE_REASON_NETWORK_ERROR: {
        "title": "Network error reaching source",
        "message": (
            "We couldn't reach the source — DNS lookup failed, connection refused, "
            "or the TLS handshake didn't complete."
        ),
        "remediation": (
            "Check the URL is correct and reachable from a normal browser. "
            "Retry in a few minutes."
        ),
    },
    FAILURE_REASON_VALIDATION_FAILED: {
        "title": "URL failed safety validation",
        "message": (
            "The URL pointed at a private IP, localhost, or an unsupported scheme. "
            "We only accept public HTTPS URLs."
        ),
        "remediation": "Submit a public HTTPS URL.",
    },
    FAILURE_REASON_CLAIM_EXTRACTION_FAILED: {
        "title": "Claim extraction failed",
        "message": (
            "We fetched and parsed the article, but the LLM-based claim extractor "
            "encountered an error (provider outage, rate limit, or unparseable "
            "response)."
        ),
        "remediation": "Click Re-analyze, or try again in a few minutes.",
    },
    FAILURE_REASON_UNKNOWN: {
        "title": "Analysis failed",
        "message": "An unexpected error occurred while analyzing this URL.",
        "remediation": (
            "Try again. If the problem persists, use the chat helper to share "
            "details so we can debug it."
        ),
    },
}


class URLFetchException(Exception):
    """
    Typed fetch failure used by `fetch_url_content` so callers can persist
    a structured `failure_reason` + `failure_detail` payload on `url_analyses`
    (migration 031) instead of stuffing everything into the free-form
    `error_message` column.

    Backwards compat: this still walks like an Exception, so `except Exception`
    paths upstream continue to work — but the dedicated handler in
    `process_url_analysis_sync` reads `.reason` + `.detail()` and persists them.
    """

    def __init__(
        self,
        reason: str,
        message: Optional[str] = None,
        *,
        status_code: Optional[int] = None,
        extra: Optional[dict] = None,
    ):
        copy = _FAILURE_COPY.get(reason) or _FAILURE_COPY[FAILURE_REASON_UNKNOWN]
        self.reason = reason
        self.message = message or copy["message"]
        self.title = copy["title"]
        self.remediation = copy["remediation"]
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(self.message)

    def detail(self) -> dict:
        """Serialise to the shape we persist in `url_analyses.failure_detail`."""
        payload: dict = {
            "reason": self.reason,
            "title": self.title,
            "message": self.message,
            "remediation": self.remediation,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.extra:
            payload["extra"] = self.extra
        return payload


# Heuristic paywall keywords. Conservative on purpose — false positives here
# tell a real user "you have a paywall" when they don't, which is annoying.
_PAYWALL_KEYWORDS = (
    "subscribe to read",
    "subscribe to continue",
    "create a free account",
    "become a member",
    "subscriber-only",
    "this content is for subscribers",
    "to continue reading",
    "premium content",
    "members only",
    "paywall",
    "register to read",
    "log in to read",
)


def _classify_extraction_failure(
    html_content: str,
    extracted_text: str,
) -> str:
    """
    When extraction returned < 50 chars, decide whether it looks like a paywall,
    a JS-rendered SPA, or just a malformed page.

    Returns one of FAILURE_REASON_PAYWALL_SUSPECTED, FAILURE_REASON_JS_RENDERED_SPA,
    or FAILURE_REASON_EXTRACTION_TOO_SHORT.
    """
    html_lower = (html_content or "").lower()

    # Paywall heuristic — short body + paywall keywords in the surrounding HTML.
    for kw in _PAYWALL_KEYWORDS:
        if kw in html_lower:
            return FAILURE_REASON_PAYWALL_SUSPECTED

    # JS-rendered SPA heuristic — heavy script load relative to text content,
    # plus telltale framework markers in the HTML shell.
    script_count = html_lower.count("<script")
    spa_markers = (
        'id="__next"', 'id="root"', 'id="app"',
        'data-reactroot', 'ng-app', 'data-v-',
        '__nuxt', '__next_data__',
    )
    has_spa_marker = any(m in html_lower for m in spa_markers)
    if script_count >= 5 and has_spa_marker and len(html_content) > 5_000:
        return FAILURE_REASON_JS_RENDERED_SPA

    return FAILURE_REASON_EXTRACTION_TOO_SHORT


async def fetch_url_content(url: str) -> dict:
    """
    Fetch article content from URL using BeautifulSoup for robust extraction.

    Handles JS-rendered sites (yle.fi, etc.) by extracting article content
    from semantic HTML tags (article, main, [role=main]).

    Raises `URLFetchException` with a structured `reason` on failure so the
    caller can persist `failure_reason` + `failure_detail` (migration 031).
    Legacy `HTTPException` paths are preserved when this is invoked directly
    from a request handler.

    Returns dict with:
    - title: Article title
    - text: Extracted text content
    - source_name: Source name
    - source_domain: Domain name
    - language_code: Detected language (optional)
    - published_date: Publication date (optional)
    """
    max_response_size = _read_int_env(
        name="URL_ANALYSIS_MAX_RESPONSE_BYTES",
        default=50 * 1024 * 1024,  # 50MB default for long-form reports
        minimum=1 * 1024 * 1024,
        maximum=100 * 1024 * 1024,
    )
    max_extracted_text_chars = _read_int_env(
        name="URL_ANALYSIS_MAX_TEXT_CHARS",
        default=500_000,
        minimum=15_000,
        maximum=2_000_000,
    )

    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=False,  # Manual redirect handling via _safe_fetch (S6)
            limits=httpx.Limits(max_connections=5),
        ) as client:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,fi;q=0.8',
            }

            # Re-validate the target on every redirect hop (S6 DNS-rebinding fix).
            response = await _safe_fetch(client, url, headers=headers)
            response.raise_for_status()

            # Enforce bounded response size limit (configurable for long-form content)
            declared_length = response.headers.get("content-length")
            if declared_length:
                try:
                    declared_length_int = int(declared_length)
                except ValueError:
                    declared_length_int = None
                if declared_length_int and declared_length_int > max_response_size:
                    raise URLFetchException(
                        FAILURE_REASON_RESPONSE_TOO_LARGE,
                        extra={
                            "declared_length": declared_length_int,
                            "max_bytes": max_response_size,
                        },
                    )

            content_length = len(response.content)
            if content_length > max_response_size:
                raise URLFetchException(
                    FAILURE_REASON_RESPONSE_TOO_LARGE,
                    extra={"content_length": content_length, "max_bytes": max_response_size},
                )

            html_content = response.text
            parsed_url = urlparse(url)
            source_domain = parsed_url.netloc

            # Use BeautifulSoup for robust HTML parsing
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, 'lxml')

            # Extract title
            title = None
            # Try og:title first (most reliable for news sites)
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)

            # Extract published date
            published_date = None
            for meta_name in ['article:published_time', 'datePublished', 'date']:
                meta = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
                if meta and meta.get('content'):
                    published_date = meta['content']
                    break
            # Also check time tags
            if not published_date:
                time_tag = soup.find('time', attrs={'datetime': True})
                if time_tag:
                    published_date = time_tag['datetime']

            # Extract language
            lang = 'en'
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                lang = html_tag['lang'][:2].lower()

            # Remove non-content elements
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer',
                                       'aside', 'iframe', 'noscript', 'form',
                                       'button', 'input', 'select', 'textarea']):
                tag.decompose()

            # Try to find article content using semantic selectors
            article_text = ''
            # Priority order: article tag, main tag, role=main, specific classes
            content_selectors = [
                soup.find('article'),
                soup.find('main'),
                soup.find(attrs={'role': 'main'}),
                soup.find(class_=re.compile(r'article[_-]?(body|content|text)', re.I)),
                soup.find(class_=re.compile(r'(story|post|entry)[_-]?(body|content|text)', re.I)),
                soup.find(id=re.compile(r'article|content|story|main', re.I)),
            ]

            for container in content_selectors:
                if container:
                    # Extract text from paragraphs within the container
                    paragraphs = container.find_all('p')
                    if paragraphs:
                        article_text = '\n\n'.join(
                            p.get_text(strip=True) for p in paragraphs
                            if len(p.get_text(strip=True)) > 20
                        )
                    if not article_text:
                        article_text = container.get_text(separator='\n', strip=True)
                    if len(article_text) > 100:
                        break

            # Fallback: extract all paragraphs from body
            if len(article_text) < 100:
                body = soup.find('body')
                if body:
                    paragraphs = body.find_all('p')
                    article_text = '\n\n'.join(
                        p.get_text(strip=True) for p in paragraphs
                        if len(p.get_text(strip=True)) > 30
                    )

            # Final fallback: full body text
            if len(article_text) < 100:
                body = soup.find('body')
                if body:
                    article_text = body.get_text(separator='\n', strip=True)

            # Clean up
            article_text = re.sub(r'\n{3,}', '\n\n', article_text)
            article_text = re.sub(r' {2,}', ' ', article_text)

            if len(article_text.strip()) < 50:
                classified_reason = _classify_extraction_failure(
                    html_content=html_content,
                    extracted_text=article_text,
                )
                raise URLFetchException(
                    classified_reason,
                    extra={
                        "extracted_chars": len(article_text.strip()),
                        "html_bytes": len(html_content),
                    },
                )

            text = article_text[:max_extracted_text_chars]

            return {
                'title': title or 'Untitled',
                'text': text,
                'source_name': source_domain,
                'source_domain': source_domain,
                'language_code': lang,
                'published_date': published_date,
            }

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching URL: {url}")
        raise URLFetchException(FAILURE_REASON_TIMEOUT)
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        logger.error(f"HTTP error fetching URL {url}: {status}")
        if status == 403:
            reason = FAILURE_REASON_HTTP_FORBIDDEN
        elif status == 404:
            reason = FAILURE_REASON_HTTP_NOT_FOUND
        elif status == 451:
            reason = FAILURE_REASON_HTTP_LEGAL_BLOCK
        elif 400 <= status < 500:
            reason = FAILURE_REASON_HTTP_4XX_OTHER
        else:
            reason = FAILURE_REASON_HTTP_5XX
        raise URLFetchException(reason, status_code=status)
    except URLFetchException:
        raise
    except HTTPException as e:
        # `_safe_fetch` raises HTTPException(400) on redirect-blocked / DNS-rebind
        # attempts. Surface that as the structured REDIRECT_BLOCKED reason so the
        # frontend can show the SSRF-defence explainer rather than a raw 400.
        if e.status_code == 400 and "edirect" in str(e.detail or ""):
            raise URLFetchException(
                FAILURE_REASON_REDIRECT_BLOCKED,
                extra={"detail": str(e.detail)},
            )
        # Anything else: preserve the legacy HTTPException so the caller (if any)
        # still sees a properly-coded API response.
        raise
    except (httpx.ConnectError, httpx.NetworkError, httpx.ReadError) as e:
        logger.error(f"Network error fetching URL {url}: {e}")
        raise URLFetchException(
            FAILURE_REASON_NETWORK_ERROR,
            extra={"error_class": type(e).__name__, "detail": str(e)[:200]},
        )
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}", exc_info=True)
        raise URLFetchException(
            FAILURE_REASON_UNKNOWN,
            extra={"error_class": type(e).__name__, "detail": str(e)[:200]},
        )


async def _resolve_academic_repository_url(url: str) -> Optional[str]:
    """Resolve repository landing pages (URN/Theseus/DSpace) to a direct PDF URL.

    This improves success rate for pages that are metadata wrappers instead of
    article-like HTML bodies.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await _safe_fetch(
                client,
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            if not resp.is_success:
                return None

            content_type = (resp.headers.get("content-type") or "").lower()
            if "pdf" in content_type:
                return url

            html = resp.text or ""
            soup = BeautifulSoup(html, "lxml")

            # Most reliable in repositories
            meta_pdf = soup.find("meta", attrs={"name": "citation_pdf_url"})
            if meta_pdf and meta_pdf.get("content"):
                return urljoin(str(resp.url), str(meta_pdf["content"]).strip())

            # Common repository file links
            candidates: list[str] = []
            for a in soup.find_all("a", href=True):
                href = str(a.get("href") or "")
                if not href:
                    continue
                lowered = href.lower()
                if ".pdf" in lowered or "/bitstream/" in lowered or "/retrieve/" in lowered:
                    candidates.append(urljoin(str(resp.url), href))

            if candidates:
                # Prefer explicit PDFs first.
                candidates.sort(key=lambda x: (".pdf" not in x.lower(), len(x)))
                return candidates[0]
    except Exception as exc:
        logger.warning(f"Academic URL resolution failed for {url}: {exc}")

    return None


# =============================================================================
# URL → CORPUS MIRROR (migration 016)
# =============================================================================

async def _mirror_url_analysis_to_corpus(
    db,
    analysis_id: str,
    url: str,
    title: str,
    source_name: Optional[str],
    text: str,
    language_code: str,
    claims_list: list,
    reliability_score: Optional[int],
    overall_credibility: Optional[str],
) -> None:
    """
    Mirror an analyzed URL's article + extracted claims into the canonical
    `articles` and `claims` tables so the URL flow's output participates in
    deep-search, hybrid RAG, and transparency cross-references.

    - Upserts into `articles` keyed on URL (UNIQUE).  Marks is_user_submitted=TRUE
      and stores the back-reference to the originating url_analyses row.
    - Inserts each extracted claim into `claims` with source_kind='url_analysis'
      and the LLM-provided importance_score.
    - Best-effort kicks off embedding population so the new article is
      discoverable through pgvector similarity search.

    All failures are caught and logged as warnings — URL analysis must succeed
    even if mirroring fails (e.g. on FK violation, missing migration, or the
    embedding service being offline).

    Args:
        db: Postgres client (from get_postgres()).
        analysis_id: url_analyses.analysis_id (UUID str) to back-reference.
        url: The submitted URL (must equal articles.url uniqueness key).
        title: Extracted article title.
        source_name: Domain / source name (used for articles.source_name).
        text: Extracted article body.
        language_code: 2-char language code.
        claims_list: Iterable of AtomicClaim-shaped objects with attributes
            claim_text, claim_type, importance_score, claim_context.
        reliability_score: Preliminary 0-100 score from extraction stage.
        overall_credibility: 'LOW' | 'MEDIUM' | 'HIGH' from extraction stage.
    """
    try:
        excerpt = (text or "")[:500]

        rows = db.execute_query(
            """
            INSERT INTO articles (
                url, title, source_name, extracted_text, excerpt,
                language_code, reliability_score, overall_credibility,
                is_user_submitted, url_analysis_id, discovered_at
            ) VALUES (
                :url, :title, :source_name, :text, :excerpt,
                :language_code, :reliability, :credibility,
                TRUE, :analysis_id, NOW()
            )
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                extracted_text = EXCLUDED.extracted_text,
                excerpt = EXCLUDED.excerpt,
                reliability_score = EXCLUDED.reliability_score,
                overall_credibility = EXCLUDED.overall_credibility,
                url_analysis_id = EXCLUDED.url_analysis_id,
                is_user_submitted = TRUE
            RETURNING article_id
            """,
            {
                "url": url,
                "title": title,
                "source_name": source_name,
                "text": text,
                "excerpt": excerpt,
                "language_code": language_code,
                "reliability": reliability_score,
                "credibility": overall_credibility,
                "analysis_id": analysis_id,
            },
        )

        if not rows:
            logger.warning(
                f"[mirror] articles upsert returned no row for analysis {analysis_id}; "
                "skipping claim mirror"
            )
            return

        article_id = rows[0].get("article_id")
        if article_id is None:
            logger.warning(
                f"[mirror] articles upsert returned row without article_id for {analysis_id}"
            )
            return

        article_id_str = str(article_id)

        # Mirror each claim into the canonical claims table
        for claim in claims_list or []:
            try:
                db.execute_update(
                    """
                    INSERT INTO claims (
                        article_id, claim_text, claim_context, claim_type,
                        importance_score, source_kind, identified_at
                    ) VALUES (
                        :article_id, :claim_text, :claim_context, :claim_type,
                        :importance_score, 'url_analysis', NOW()
                    )
                    """,
                    {
                        "article_id": article_id_str,
                        "claim_text": getattr(claim, "claim_text", None),
                        "claim_context": getattr(claim, "claim_context", None),
                        "claim_type": getattr(claim, "claim_type", "factual"),
                        "importance_score": getattr(claim, "importance_score", None),
                    },
                )
            except Exception as claim_err:
                logger.warning(
                    f"[mirror] failed to insert claim for article {article_id_str}: {claim_err}"
                )

        logger.info(
            f"[mirror] mirrored URL analysis {analysis_id} -> article {article_id_str} "
            f"with {len(claims_list or [])} claim(s)"
        )

        # Best-effort embedding population so the article is RAG-discoverable.
        try:
            from app.domains.content.embedding_service import EmbeddingService
            await EmbeddingService(db).populate_embedding(article_id_str)
        except Exception as emb_err:
            logger.warning(
                f"[mirror] embedding population skipped for {article_id_str}: {emb_err}"
            )

    except Exception as e:
        logger.warning(
            f"[mirror] failed to mirror URL analysis {analysis_id} into corpus: {e}",
            exc_info=True,
        )


# =============================================================================
# BACKGROUND PROCESSING
# =============================================================================

def _persist_structured_failure(
    db,
    analysis_id: str,
    start_time: datetime,
    exc: "URLFetchException",
) -> None:
    """
    Write a structured failure row to `url_analyses`.

    Sets:
    - status = 'failed'
    - error_message (legacy free-form, kept for backward-compat readers)
    - failure_reason  (migration 031 — enum-shaped string)
    - failure_detail  (migration 031 — JSONB with title/message/remediation/extra)
    - processing_time_ms

    Best-effort: if the migration hasn't run yet (older clusters), falls
    back to the legacy single-column write so the analysis still completes.
    """
    import json

    elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    detail_payload = exc.detail()
    detail_json = json.dumps(detail_payload)

    try:
        db.execute_update(
            """
            UPDATE url_analyses
            SET status = 'failed',
                error_message = :error,
                failure_reason = :reason,
                failure_detail = CAST(:detail AS jsonb),
                completed_at = NOW(),
                processing_time_ms = :time_ms,
                updated_at = NOW()
            WHERE analysis_id = :analysis_id
            """,
            {
                "error": exc.message,
                "reason": exc.reason,
                "detail": detail_json,
                "time_ms": elapsed_ms,
                "analysis_id": analysis_id,
            },
        )
        return
    except Exception as schema_err:
        # Migration 031 not applied yet — fall back to the legacy single-column
        # write so the row still moves to 'failed'. Frontend just sees the
        # legacy error_message text in this case (no icon/remediation surface).
        logger.warning(
            f"Structured failure write fell back to legacy schema for {analysis_id}: {schema_err}"
        )

    db.execute_update(
        """
        UPDATE url_analyses
        SET status = 'failed',
            error_message = :error,
            completed_at = NOW(),
            processing_time_ms = :time_ms,
            updated_at = NOW()
        WHERE analysis_id = :analysis_id
        """,
        {
            "error": exc.message,
            "time_ms": elapsed_ms,
            "analysis_id": analysis_id,
        },
    )


async def process_url_analysis_sync(analysis_id: str, url: str, user_id: str):
    """
    Synchronous processing of URL analysis (NO KAFKA).

    Steps:
    1. Update status to 'processing'
    2. Fetch content from URL
    3. Extract metadata (title, author, etc.)
    4. Store in url_analyses table
    5. Extract claims using IntelligenceService
    6. Store claims and fact-checks
    7. Calculate credibility scores
    8. Update status to 'completed' or 'failed'
    """
    db = get_postgres()
    start_time = datetime.utcnow()

    try:
        # Step 1: Update status to processing
        db.execute_update(
            """
            UPDATE url_analyses
            SET status = 'processing',
                processing_started_at = NOW(),
                updated_at = NOW()
            WHERE analysis_id = :analysis_id
            """,
            {"analysis_id": analysis_id}
        )

        logger.info(f"Processing URL analysis {analysis_id}: {url}")

        # Step 2: Fetch content from URL
        try:
            content = await fetch_url_content(url)
        except (URLFetchException, HTTPException) as fetch_err:
            # Repository landing pages (Theseus/URN/DSpace) often hold only
            # metadata and link out to the actual PDF. Auto-resolve and retry.
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            is_academic_repo = any(
                marker in host or marker in url.lower()
                for marker in [
                    "theseus.fi",
                    "urn.fi",
                    "handle/",
                    "dspace",
                    "helda.",
                    "aaltodoc.",
                    "jultika.",
                    "trepo.",
                    "lutpub.",
                ]
            )

            if not is_academic_repo:
                raise

            resolved_pdf = await _resolve_academic_repository_url(url)
            if not resolved_pdf:
                raise

            logger.info(
                "Resolved academic repository page to direct PDF",
                original_url=url,
                resolved_pdf=resolved_pdf,
            )
            content = await fetch_url_content(resolved_pdf)

        # Step 3: Extract metadata
        title = content['title']
        text = content['text']
        source_name = content['source_name']
        source_domain = content['source_domain']
        language_code = content.get('language_code', 'en')

        # Step 4: Update url_analyses with extracted content
        db.execute_update(
            """
            UPDATE url_analyses
            SET title = :title,
                source_name = :source_name,
                source_domain = :source_domain,
                extracted_text = :text,
                language_code = :language_code,
                updated_at = NOW()
            WHERE analysis_id = :analysis_id
            """,
            {
                "title": title,
                "source_name": source_name,
                "source_domain": source_domain,
                "text": text,
                "language_code": language_code,
                "analysis_id": analysis_id
            }
        )

        # Step 5: Extract claims using IntelligenceService
        extractor = ClaimExtractor()
        max_total_claims = _read_int_env(
            name="URL_ANALYSIS_MAX_CLAIMS_TOTAL",
            default=60,
            minimum=5,
            maximum=300,
        )

        try:
            claims = await _extract_claims_for_long_text(
                extractor=extractor,
                text=text,
                max_total_claims=max_total_claims,
            )
        except HTTPException as e:
            # Handle API errors (ANTHROPIC_API_KEY missing, rate limits, etc.)
            error_msg = f"Claim extraction failed: {e.detail}"
            logger.error(error_msg)

            claim_exc = URLFetchException(
                FAILURE_REASON_CLAIM_EXTRACTION_FAILED,
                message=error_msg,
                status_code=getattr(e, "status_code", None),
                extra={"detail": str(e.detail)},
            )
            _persist_structured_failure(
                db=db,
                analysis_id=analysis_id,
                start_time=start_time,
                exc=claim_exc,
            )
            return

        # Step 6: Store claims in JSONB
        claims_json = [
            {
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "importance_score": claim.importance_score,
                "claim_context": claim.claim_context
            }
            for claim in claims
        ]

        import json
        claims_json_str = json.dumps(claims_json)

        # Step 7: Compute an EXTRACTION-QUALITY signal — NOT a verified credibility
        # score. This score is decided purely by text length and claim density, with
        # no source-reputation lookup, no cross-corpus corroboration, and no
        # verification of any individual claim. A 1500-char propaganda blog with
        # 5 confident claims would get HIGH here. The field is named
        # `overall_credibility` for DB-schema continuity, but the methodology drawer
        # surfaces this as `extraction_quality` with a caveat. Sprint 2 will wire
        # the real fact-check pipeline (EvidenceOrchestrator + source_credibility
        # join) before the label "credibility" is honest.
        claims_count = len(claims)
        text_len = len(text or "")

        if text_len < 400 or claims_count == 0:
            reliability_score = 25
            overall_credibility = "LOW"
        elif text_len < 1500 or claims_count < 3:
            reliability_score = 45
            overall_credibility = "MEDIUM"
        else:
            avg_importance = (
                sum(getattr(c, "importance_score", 0) or 0 for c in claims) / max(claims_count, 1)
            )
            if avg_importance >= 0.6 and claims_count >= 5:
                reliability_score = 70
                overall_credibility = "HIGH"
            else:
                reliability_score = 55
                overall_credibility = "MEDIUM"

        # Step 8: Update with results
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        db.execute_update(
            """
            UPDATE url_analyses
            SET status = 'completed',
                extracted_claims = CAST(:claims AS jsonb),
                reliability_score = :reliability,
                overall_credibility = :credibility,
                completed_at = NOW(),
                processing_time_ms = :time_ms,
                updated_at = NOW()
            WHERE analysis_id = :analysis_id
            """,
            {
                "claims": claims_json_str,
                "reliability": reliability_score,
                "credibility": overall_credibility,
                "time_ms": processing_time_ms,
                "analysis_id": analysis_id
            }
        )

        logger.info(
            f"URL analysis {analysis_id} completed successfully: "
            f"{claims_count} claims extracted in {processing_time_ms}ms"
        )

        # Step 8.3: Hallucination grounding check on extracted claims (Phase 6 wave 2).
        # Runs the existing HallucinationDetector.check with the joined claim
        # texts as `generated` and the article body as the source. The local
        # entity-overlap + statistic-verification subchecks run regardless of
        # LLM availability; the LLM-grounding sub-check degrades to risk=0.5
        # gracefully when no LLM key is set. Captures hallucination_score for
        # the provenance row's existing column (migration 021).
        hallucination_score: Optional[float] = None
        hallucination_flags: list = []
        try:
            if claims and text:
                from app.domains.intelligence.hallucination_detector import (
                    HallucinationDetector,
                )
                detector = HallucinationDetector(db)
                joined_claims = " ".join(
                    (getattr(c, "claim_text", "") or "") for c in claims
                ).strip()
                if joined_claims:
                    h_result = await detector.check(
                        generated_text=joined_claims,
                        source_texts=[text[:20000]],  # cap to keep the LLM cost bounded
                    )
                    hallucination_score = h_result.get("hallucination_risk")
                    hallucination_flags = h_result.get("flagged_segments", []) or []
        except Exception as _h_exc:
            logger.warning(
                "Hallucination grounding check failed for %s: %s",
                analysis_id, _h_exc,
            )

        # Step 8.4: Multi-LLM cross-verification (Phase 5 wave 3).
        # Opt-in via env: CLILENS_MULTI_LLM_VERIFY=1 + ANTHROPIC_API_KEY.
        # When enabled, runs Anthropic Claude as a SECONDARY extractor on
        # the same article and reports agreement_score in the provenance
        # raw_metadata. Disagreement → independently-corroborated claims
        # are flagged downstream. Best-effort: any failure logs + skips
        # (never blocks the URL analysis from completing).
        multi_llm_meta: dict = {}
        if os.getenv("CLILENS_MULTI_LLM_VERIFY") == "1":
            try:
                from app.domains.intelligence.anthropic_claim_extractor import (
                    AnthropicClaimExtractor,
                )
                from app.domains.intelligence.multi_llm_verifier import verify_claims

                secondary = AnthropicClaimExtractor()
                if secondary.available:
                    # Primary passthrough: we already extracted; just hand the
                    # existing list to verify_claims so it doesn't re-run the LLM.
                    _primary_claims = claims

                    async def _primary_passthrough(_t, _n):
                        return _primary_claims

                    async def _secondary_call(t, n):
                        return await secondary.decompose_claims(t, n)

                    verification = await verify_claims(
                        text=text[:4000],
                        max_claims=max(claims_count, 1),
                        primary_extractor=_primary_passthrough,
                        primary_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                        secondary_extractor=_secondary_call,
                        secondary_model=secondary.model,
                    )
                    multi_llm_meta = {
                        "enabled": True,
                        "agreement_score": verification.agreement_score,
                        "primary_model": verification.primary_model,
                        "secondary_model": verification.secondary_model,
                        "primary_count": verification.primary_count,
                        "corroborated_count": verification.corroborated_count,
                        "secondary_total_claims": verification.secondary_total_claims,
                        "secondary_error": verification.secondary_error,
                        "similarity_threshold": verification.similarity_threshold,
                    }
                    logger.info(
                        "Multi-LLM verification for %s: "
                        "agreement=%s corroborated=%s/%s",
                        analysis_id,
                        verification.agreement_score,
                        verification.corroborated_count,
                        verification.primary_count,
                    )
                else:
                    multi_llm_meta = {
                        "enabled": True,
                        "skipped_reason": "anthropic_unavailable",
                    }
            except Exception as _verify_exc:
                logger.warning(
                    "Multi-LLM verification failed for %s: %s",
                    analysis_id, _verify_exc,
                )
                multi_llm_meta = {
                    "enabled": True,
                    "skipped_reason": f"verifier_error:{type(_verify_exc).__name__}",
                }

        # Step 8.5: Record per-extraction provenance (Phase 4 wave 3).
        # Best-effort — never fails the URL analysis.
        try:
            from app.domains.intelligence.provenance import (
                EXTRACTION_URL_ANALYSIS,
                ProvenanceRecord,
                record_provenance,
            )
            # Model name is the env-configured extraction LLM. When we register
            # the claim-extraction prompt in the prompts.PROMPTS registry
            # (future wave), prompt_name/version/fingerprint will also populate.
            _model_name = (
                os.getenv("DEEPSEEK_MODEL")
                or os.getenv("ANTHROPIC_MODEL")
                or "unknown"
            )
            _raw_meta = {
                "claim_count": claims_count,
                "text_length": text_len,
                "language_code": language_code,
                "overall_credibility": overall_credibility,
                "processing_time_ms": processing_time_ms,
            }
            if multi_llm_meta:
                _raw_meta["multi_llm_verification"] = multi_llm_meta
            # Phase 6 wave 2: include the hallucination flagged segments
            # (the score itself goes in the dedicated column) so auditors
            # can see WHICH spans of the synthesised claims were flagged.
            if hallucination_flags:
                _raw_meta["hallucination_flagged_segments"] = hallucination_flags

            record_provenance(db, ProvenanceRecord(
                extraction_method=EXTRACTION_URL_ANALYSIS,
                url_analysis_id=str(analysis_id),
                model_name=_model_name,
                retrieval_strategy="user_submitted_url",
                # Normalise reliability_score (0–100) to confidence (0–1) so it
                # aggregates with other confidence signals across the platform.
                confidence=(
                    float(reliability_score) / 100.0
                    if reliability_score is not None else None
                ),
                hallucination_score=hallucination_score,
                raw_metadata=_raw_meta,
            ))
        except Exception as _prov_exc:
            logger.warning(
                f"record_provenance failed for URL analysis {analysis_id}: {_prov_exc}"
            )

        # Step 9: Mirror into canonical articles + claims tables so the URL
        # flow contributes to deep-search / hybrid RAG / transparency views.
        # Best-effort — mirror failures must NOT fail the URL analysis.
        await _mirror_url_analysis_to_corpus(
            db=db,
            analysis_id=analysis_id,
            url=url,
            title=title,
            source_name=source_name,
            text=text,
            language_code=language_code,
            claims_list=claims,
            reliability_score=reliability_score,
            overall_credibility=overall_credibility,
        )

    except URLFetchException as e:
        # Structured-failure path (migration 031). The frontend reads
        # `failure_reason` + `failure_detail` to show a typed explanation
        # instead of a free-form "Analysis failed" string.
        logger.warning(
            f"URL analysis {analysis_id} failed with structured reason: {e.reason}",
            reason=e.reason,
            status_code=e.status_code,
        )
        _persist_structured_failure(
            db=db,
            analysis_id=analysis_id,
            start_time=start_time,
            exc=e,
        )
    except HTTPException as e:
        # Legacy HTTPException path — wrap as unknown so the row still gets
        # a structured failure_reason. The original detail is preserved in
        # failure_detail.extra so we don't lose diagnostics.
        wrapped = URLFetchException(
            FAILURE_REASON_UNKNOWN,
            message=str(e.detail or "Unknown error"),
            status_code=getattr(e, "status_code", None),
            extra={"http_exception_detail": str(e.detail)},
        )
        _persist_structured_failure(
            db=db,
            analysis_id=analysis_id,
            start_time=start_time,
            exc=wrapped,
        )
    except Exception as e:
        logger.error(f"Error processing URL analysis {analysis_id}: {e}", exc_info=True)
        wrapped = URLFetchException(
            FAILURE_REASON_UNKNOWN,
            message=str(e)[:500],
            extra={"error_class": type(e).__name__},
        )
        _persist_structured_failure(
            db=db,
            analysis_id=analysis_id,
            start_time=start_time,
            exc=wrapped,
        )


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("", response_model=URLAnalysisJobResponse)
async def submit_url_analysis(
    request: AnalyzeURLRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """
    Submit a URL for fact-checking analysis.

    All users get basic access (3 analyses/month).
    Premium tiers get higher limits.
    """
    user_id = ANONYMOUS_UUID
    user_tier = "anonymous"
    if current_user and isinstance(current_user, dict):
        user_id = str(current_user.get("user_id", ANONYMOUS_UUID))
        user_tier = str(current_user.get("subscription_tier", "freemium"))

    # Phase 1A (2026-05-23) — quota gate: enforce the 3/3/2 freemium ladder
    # BEFORE doing the work. Raises HTTP 429 with structured envelope so the
    # client can render the upgrade modal with exact remaining/reset info.
    from api.quota_service import QuotaService
    QuotaService.check_and_raise(
        user_id=None if user_id == ANONYMOUS_UUID else user_id,
        tier=user_tier,
        quota_key="url_analysis",
    )

    # Create analysis record
    db = get_postgres()
    analysis_id = str(uuid4())
    url_str = str(request.url)

    # Generate URL hash for deduplication
    url_hash = hashlib.sha256(url_str.encode()).hexdigest()

    # Extract domain
    parsed_url = urlparse(url_str)
    source_domain = parsed_url.netloc

    try:
        stored_user_id = _insert_url_analysis_record(
            db=db,
            analysis_id=analysis_id,
            user_id=user_id,
            url=url_str,
            url_hash=url_hash,
            source_domain=source_domain,
        )

        # Queue background processing
        background_tasks.add_task(
            process_url_analysis_sync,
            analysis_id=analysis_id,
            url=url_str,
            user_id=stored_user_id,
        )

        # Log usage
        try:
            UsageTracker.log_usage(
                user_id=stored_user_id,
                usage_type="url_analysis",
                resource_id=analysis_id,
                resource_url=url_str
            )
        except Exception:
            pass

        logger.info(f"URL analysis submitted: {analysis_id} by user {stored_user_id}")

        return URLAnalysisJobResponse(
            job_id=analysis_id,
            status="processing",
            estimated_time=30,
            access_token=_generate_job_token(analysis_id),
        )

    except Exception as e:
        logger.error(f"Error creating URL analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit URL analysis")


@router.get("/{job_id}", response_model=URLAnalysisDetail)
async def get_analysis_result(
    job_id: str,
    token: Optional[str] = Query(
        None,
        description=(
            "HMAC access token returned by POST. Required for anonymous reads; "
            "authenticated owners can omit it."
        ),
    ),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Get the result of a URL analysis.

    Authorization (S7):
    - Authenticated user whose user_id matches `url_analyses.user_id`: allowed.
    - Anyone presenting the correct signed access_token via `?token=...`: allowed.
    - Everyone else: 403.

    This blocks the pre-2026-05-16 attack where any anonymous client could
    GET another user's submission by guessing/listing the analysis UUID.
    """
    db = get_postgres()

    # Phase 0 (2026-05-23): include failure_reason + failure_detail (migration 031)
    # via best-effort fetch. Clusters that have not run the migration yet still
    # work — the second SELECT (legacy column set) is the safe fallback.
    try:
        results = db.execute_query(
            """
            SELECT
                user_id,
                analysis_id,
                submitted_url,
                status,
                title,
                source_name,
                source_domain,
                extracted_text,
                language_code,
                published_date,
                reliability_score,
                overall_credibility,
                extracted_claims,
                fact_checks,
                created_at,
                processing_started_at,
                completed_at,
                processing_time_ms,
                error_message,
                failure_reason,
                failure_detail
            FROM url_analyses
            WHERE analysis_id = :analysis_id
            """,
            {
                "analysis_id": job_id,
            }
        )
    except Exception as schema_err:
        logger.warning(
            f"Legacy url_analyses schema (no migration 031); falling back. {schema_err}"
        )
        results = db.execute_query(
            """
            SELECT
                user_id,
                analysis_id,
                submitted_url,
                status,
                title,
                source_name,
                source_domain,
                extracted_text,
                language_code,
                published_date,
                reliability_score,
                overall_credibility,
                extracted_claims,
                fact_checks,
                created_at,
                processing_started_at,
                completed_at,
                processing_time_ms,
                error_message
            FROM url_analyses
            WHERE analysis_id = :analysis_id
            """,
            {
                "analysis_id": job_id,
            }
        )

    if not results:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found or you don't have access"
        )

    result = results[0]
    result = _timeout_stale_processing_analysis(db, job_id, result)

    # --- Authorization gate ---
    is_owner = False
    if current_user and isinstance(current_user, dict):
        cu_uid = str(current_user.get("user_id", "") or "")
        row_uid = str(result.get("user_id", "") or "")
        if cu_uid and cu_uid == row_uid and cu_uid != ANONYMOUS_UUID:
            is_owner = True

    if not is_owner and not _verify_job_token(token, job_id):
        # Same response shape as 404 to avoid leaking which UUIDs exist.
        raise HTTPException(
            status_code=403,
            detail=(
                "Access denied. Pass ?token=... from the POST response, or sign "
                "in as the submitting user."
            ),
        )

    # Parse JSONB fields
    import json
    extracted_claims = result.get("extracted_claims")
    if isinstance(extracted_claims, str):
        try:
            extracted_claims = json.loads(extracted_claims)
        except:
            extracted_claims = []
    elif extracted_claims is None:
        extracted_claims = []

    fact_checks = result.get("fact_checks")
    if isinstance(fact_checks, str):
        try:
            fact_checks = json.loads(fact_checks)
        except:
            fact_checks = []
    elif fact_checks is None:
        fact_checks = []

    # Phase 5 wave 5: apply the most-recent Platt-scaled calibration when
    # available. Returns None if no fit exists — callers fall back to raw.
    calibrated_reliability_score: Optional[float] = None
    try:
        from app.domains.intelligence.calibration_store import (
            apply_latest_to_reliability,
        )
        calibrated_reliability_score = apply_latest_to_reliability(
            db, result.get("reliability_score"),
        )
    except Exception as _calib_exc:
        logger.debug(
            "Calibration application failed (non-fatal) for %s: %s",
            job_id, _calib_exc,
        )

    # Structured failure (migration 031). failure_detail may be returned as
    # a dict (psycopg2 JSONB) or as a JSON string depending on the driver;
    # normalise to a dict for the response.
    failure_reason = result.get("failure_reason")
    failure_detail_raw = result.get("failure_detail")
    failure_detail: Optional[dict] = None
    if isinstance(failure_detail_raw, dict):
        failure_detail = failure_detail_raw
    elif isinstance(failure_detail_raw, str):
        try:
            failure_detail = json.loads(failure_detail_raw)
        except Exception:
            failure_detail = None

    return URLAnalysisDetail(
        analysis_id=str(result["analysis_id"]),
        submitted_url=result["submitted_url"],
        status=result["status"],
        title=result.get("title"),
        source_name=result.get("source_name"),
        source_domain=result.get("source_domain"),
        extracted_text=result.get("extracted_text"),
        language_code=result.get("language_code"),
        published_date=result.get("published_date"),
        reliability_score=result.get("reliability_score"),
        overall_credibility=result.get("overall_credibility"),
        calibrated_reliability_score=calibrated_reliability_score,
        extracted_claims=extracted_claims,
        fact_checks=fact_checks,
        created_at=result["created_at"],
        processing_started_at=result.get("processing_started_at"),
        completed_at=result.get("completed_at"),
        processing_time_ms=result.get("processing_time_ms"),
        error_message=result.get("error_message"),
        failure_reason=failure_reason,
        failure_detail=failure_detail,
    )


@router.get("/stats/usage")
async def get_url_analysis_usage(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current month's URL analysis usage statistics.

    Returns:
    - Analyses used this month
    - Monthly limit
    - Remaining analyses
    - Current subscription tier
    """
    db = get_postgres()

    # Get tier limits
    tier_limits = {
        "freemium": 0,
        "basic": 5,
        "professional": 20,
        "enterprise": -1  # unlimited
    }

    limit = tier_limits.get(current_user["subscription_tier"], 0)

    # Count this month's usage
    results = db.execute_query(
        """
        SELECT COUNT(*) as used
        FROM url_analyses
        WHERE user_id = :user_id
          AND created_at >= DATE_TRUNC('month', NOW())
        """,
        {"user_id": str(current_user["user_id"])}
    )

    used = results[0]["used"] if results else 0
    remaining = limit - used if limit != -1 else -1

    return {
        "tier": current_user["subscription_tier"],
        "limit": limit if limit != -1 else "unlimited",
        "used": used,
        "remaining": remaining if remaining != -1 else "unlimited",
        "period": "monthly"
    }
