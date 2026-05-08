"""
URL Analysis Routes - Premium Feature

Allows users to submit custom URLs for fact-checking analysis.
This service fetches content, extracts claims, and runs verification.

NO KAFKA DEPENDENCY - Works synchronously with database polling.
"""

import hashlib
import re
from typing import List, Optional
from datetime import datetime
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

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AnalyzeURLRequest(BaseModel):
    """Request to analyze a custom URL"""
    url: HttpUrl = Field(..., description="URL to analyze (HTTPS only)")

    @validator('url')
    def validate_url(cls, v):
        """Validate URL format and security"""
        url_str = str(v)

        # Must be HTTPS
        if not url_str.startswith('https://'):
            raise ValueError('Only HTTPS URLs are allowed for security reasons')

        # Max length check
        if len(url_str) > 2048:
            raise ValueError('URL exceeds maximum length of 2048 characters')

        # Parse and validate domain
        parsed = urlparse(url_str)

        # Block non-HTTP(S) schemes
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('Only HTTP and HTTPS URLs are supported')

        hostname = (parsed.hostname or '').lower().strip('[]')

        # Reject localhost and known internal hostnames
        blocked_hosts = {'localhost', '127.0.0.1', '0.0.0.0', '::1', '',
                         'metadata.google.internal', 'metadata.goog'}
        if hostname in blocked_hosts:
            raise ValueError('Cannot analyze localhost or internal URLs')

        # Block dangerous TLDs
        blocked_tlds = ('.internal', '.local', '.localhost')
        for tld in blocked_tlds:
            if hostname.endswith(tld):
                raise ValueError(f'Cannot analyze URLs with {tld} TLD')

        # Use ipaddress module for comprehensive private/reserved IP detection
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                raise ValueError('Cannot analyze private, reserved, or internal IP addresses')
        except ValueError as ve:
            # Not an IP address — it's a hostname
            # Re-raise if this was our own validation error from above
            if 'Cannot analyze' in str(ve):
                raise

            # DNS rebinding protection: resolve hostname and check resolved IP
            import socket
            try:
                resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
                for family, socktype, proto, canonname, sockaddr in resolved_ips:
                    resolved_ip = ipaddress.ip_address(sockaddr[0])
                    if resolved_ip.is_private or resolved_ip.is_reserved or resolved_ip.is_loopback or resolved_ip.is_link_local:
                        raise ValueError(
                            f'DNS rebinding detected: {hostname} resolves to private IP {sockaddr[0]}'
                        )
            except socket.gaierror:
                raise ValueError(f'Cannot resolve hostname: {hostname}')

        return v


class URLAnalysisJobResponse(BaseModel):
    """Response when URL analysis is submitted"""
    job_id: str
    status: str  # "processing", "completed", "failed"
    estimated_time: int = 30  # seconds


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

    # Claims (as JSON array)
    extracted_claims: List[dict] = Field(default_factory=list)
    fact_checks: List[dict] = Field(default_factory=list)

    # Metadata
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None


# =============================================================================
# URL CONTENT FETCHING SERVICE
# =============================================================================

async def fetch_url_content(url: str) -> dict:
    """
    Fetch article content from URL using BeautifulSoup for robust extraction.

    Handles JS-rendered sites (yle.fi, etc.) by extracting article content
    from semantic HTML tags (article, main, [role=main]).

    Returns dict with:
    - title: Article title
    - text: Extracted text content
    - source_name: Source name
    - source_domain: Domain name
    - language_code: Detected language (optional)
    - published_date: Publication date (optional)
    """
    MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB absolute limit

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=5),
            max_redirects=5
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

            # Check Content-Length header before downloading full body
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            # Enforce 10MB response size limit
            declared_length = response.headers.get("content-length")
            if declared_length and int(declared_length) > MAX_RESPONSE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Response too large ({int(declared_length)} bytes). Maximum allowed: {MAX_RESPONSE_SIZE} bytes (10MB)."
                )

            content_length = len(response.content)
            if content_length > MAX_RESPONSE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Response too large ({content_length} bytes). Maximum allowed: {MAX_RESPONSE_SIZE} bytes (10MB)."
                )

            if content_length > 500 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="Content size exceeds maximum allowed (500KB)"
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
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Could not extract enough text from this URL. "
                        "The site may use JavaScript rendering, require authentication, "
                        "or block automated access. Try a different URL."
                    )
                )

            text = article_text[:15000]

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
        raise HTTPException(
            status_code=503,
            detail="Timeout fetching URL. The server took too long to respond. Try again later."
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL {url}: {e.response.status_code}")
        status_explanations = {
            403: "Access denied — this site blocks automated access.",
            404: "Page not found — check the URL is correct.",
            451: "Content unavailable for legal reasons.",
            500: "The target server encountered an internal error.",
        }
        detail = status_explanations.get(
            e.response.status_code,
            f"Failed to fetch URL: HTTP {e.response.status_code}"
        )
        raise HTTPException(status_code=400, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL content: {str(e)}"
        )


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
        content = await fetch_url_content(url)

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

        try:
            claims = await extractor.decompose_claims(text, max_claims=10)
        except HTTPException as e:
            # Handle API errors (ANTHROPIC_API_KEY missing, rate limits, etc.)
            error_msg = f"Claim extraction failed: {e.detail}"
            logger.error(error_msg)

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
                    "error": error_msg,
                    "time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "analysis_id": analysis_id
                }
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

        # Step 7: Compute a preliminary credibility signal from the extraction stage.
        # Full verification (claim-level fact-checking) runs as a separate pipeline;
        # the reliability_score and overall_credibility here reflect the *quality of
        # the extracted text* (length, claim density, importance), not verification.
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
                extracted_claims = :claims::jsonb,
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

    except HTTPException as e:
        # Already handled and logged
        error_msg = e.detail
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
                "error": error_msg,
                "time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                "analysis_id": analysis_id
            }
        )
    except Exception as e:
        logger.error(f"Error processing URL analysis {analysis_id}: {e}", exc_info=True)

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
                "error": str(e),
                "time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                "analysis_id": analysis_id
            }
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
    # Use a fixed UUID for anonymous users
    ANONYMOUS_UUID = "00000000-0000-0000-0000-000000000000"
    user_id = ANONYMOUS_UUID
    user_tier = "freemium"
    if current_user and isinstance(current_user, dict):
        user_id = str(current_user.get("user_id", ANONYMOUS_UUID))
        user_tier = current_user.get("subscription_tier", "freemium") or "freemium"

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
        db.execute_update(
            """
            INSERT INTO url_analyses (
                analysis_id, user_id, submitted_url, url_hash, source_domain,
                status, priority, created_at, updated_at
            ) VALUES (
                :analysis_id, :user_id, :url, :url_hash, :domain,
                'pending', 'normal', NOW(), NOW()
            )
            """,
            {
                "analysis_id": analysis_id,
                "user_id": user_id,
                "url": url_str,
                "url_hash": url_hash,
                "domain": source_domain
            }
        )

        # Queue background processing
        background_tasks.add_task(
            process_url_analysis_sync,
            analysis_id=analysis_id,
            url=url_str,
            user_id=user_id
        )

        # Log usage
        try:
            UsageTracker.log_usage(
                user_id=user_id,
                usage_type="url_analysis",
                resource_id=analysis_id,
                resource_url=url_str
            )
        except Exception:
            pass

        logger.info(f"URL analysis submitted: {analysis_id} by user {user_id}")

        return URLAnalysisJobResponse(
            job_id=analysis_id,
            status="processing",
            estimated_time=30
        )

    except Exception as e:
        logger.error(f"Error creating URL analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit URL analysis")


@router.get("/{job_id}", response_model=URLAnalysisDetail)
async def get_analysis_result(
    job_id: str,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """
    Get the result of a URL analysis.

    Returns the complete analysis including extracted claims,
    credibility assessment, and processing status.
    """
    db = get_postgres()

    # Fetch analysis — allow access by job_id (no strict user filtering for anonymous)
    results = db.execute_query(
        """
        SELECT
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
        extracted_claims=extracted_claims,
        fact_checks=fact_checks,
        created_at=result["created_at"],
        processing_started_at=result.get("processing_started_at"),
        completed_at=result.get("completed_at"),
        processing_time_ms=result.get("processing_time_ms"),
        error_message=result.get("error_message")
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
