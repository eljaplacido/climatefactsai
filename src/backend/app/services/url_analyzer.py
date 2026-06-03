"""
URL Analyzer Service

Orchestrates the complete URL analysis workflow:
1. URL validation and sanitization
2. Content scraping
3. Claim extraction
4. Fact-checking via orchestration service
5. Credibility scoring
"""

import hashlib
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse
from uuid import uuid4

from shared.database import get_postgres
from shared.logger import setup_logging
from services.ingestion_service.src.scraper import NewsScraperPool
from services.ingestion_service.src.claim_extractor import ClaimExtractor

logger = setup_logging("url-analyzer")


class URLValidationError(Exception):
    """Raised when URL validation fails."""
    pass


class URLAnalyzer:
    """
    Service for analyzing user-submitted URLs for fact-checking.

    This service integrates with the existing scraper and claim extractor
    to provide on-demand analysis of news articles.
    """

    def __init__(self):
        """Initialize URL analyzer with dependencies."""
        self.scraper = NewsScraperPool(logger=logger)
        self.claim_extractor = ClaimExtractor(logger=logger)
        self.db = get_postgres()

    def validate_url(self, url: str) -> str:
        """
        Validate and sanitize URL.

        Args:
            url: URL to validate

        Returns:
            Sanitized URL

        Raises:
            URLValidationError: If URL is invalid or blocked
        """
        # Max length check
        if len(url) > 2048:
            raise URLValidationError("URL exceeds maximum length of 2048 characters")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            raise URLValidationError("Invalid URL format")

        # Must have valid scheme
        if parsed.scheme not in ['http', 'https']:
            raise URLValidationError("URL must use http or https protocol")

        # Must have valid hostname
        if not parsed.netloc:
            raise URLValidationError("URL must have a valid hostname")

        # Block dangerous protocols
        dangerous_schemes = ['file', 'javascript', 'data', 'vbscript']
        if parsed.scheme.lower() in dangerous_schemes:
            raise URLValidationError(f"Protocol '{parsed.scheme}' is not allowed")

        # Block localhost and private IPs
        hostname = parsed.netloc.split(':')[0].lower()
        if hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
            raise URLValidationError("Cannot analyze localhost URLs")

        # Block private IP ranges (basic check)
        if hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
            raise URLValidationError("Cannot analyze private network URLs")

        return url

    def generate_url_hash(self, url: str) -> str:
        """
        Generate SHA-256 hash of URL for deduplication.

        Args:
            url: URL to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def check_existing_analysis(self, url_hash: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if this URL has been analyzed recently by this user.

        Args:
            url_hash: SHA-256 hash of the URL
            user_id: User ID

        Returns:
            Existing analysis dict or None
        """
        query = """
            SELECT
                analysis_id, status, completed_at,
                overall_credibility, reliability_score
            FROM url_analyses
            WHERE url_hash = :url_hash AND user_id = :user_id
            AND created_at > NOW() - INTERVAL '24 hours'
            AND status IN ('completed', 'processing', 'pending')
            ORDER BY created_at DESC
            LIMIT 1
        """

        results = self.db.execute_query(query, {"url_hash": url_hash, "user_id": user_id})

        if results:
            return dict(results[0])

        return None

    def create_analysis_record(
        self,
        user_id: str,
        url: str,
        url_hash: str,
        priority: str = "normal"
    ) -> str:
        """
        Create initial analysis record in database.

        Args:
            user_id: User ID
            url: Submitted URL
            url_hash: SHA-256 hash of URL
            priority: Analysis priority

        Returns:
            Analysis ID (UUID)
        """
        analysis_id = str(uuid4())

        query = """
            INSERT INTO url_analyses (
                analysis_id, user_id, submitted_url, url_hash,
                status, created_at, updated_at
            ) VALUES (:analysis_id, :user_id, :url, :url_hash, 'pending', NOW(), NOW())
        """

        self.db.execute_update(
            query,
            {"analysis_id": analysis_id, "user_id": user_id, "url": url, "url_hash": url_hash}
        )

        logger.info(f"Created analysis record: {analysis_id}", url=url, user_id=user_id)

        return analysis_id

    def scrape_article(self, url: str, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Scrape article content from URL.

        Args:
            url: URL to scrape
            analysis_id: Analysis ID for tracking

        Returns:
            Article data dict or None if scraping fails
        """
        try:
            # Update status
            self.db.execute_update(
                """
                UPDATE url_analyses
                SET status = 'processing',
                    processing_started_at = NOW(),
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {"analysis_id": analysis_id}
            )

            # Scrape using existing scraper
            article_data = self.scraper._fetch_article_content(url)

            if not article_data:
                raise Exception("Failed to extract article content")

            # Extract domain for source name
            parsed = urlparse(url)
            source_domain = parsed.netloc

            # Update analysis with scraped content
            self.db.execute_update(
                """
                UPDATE url_analyses
                SET source_name = :source_name,
                    source_domain = :source_domain,
                    title = :title,
                    extracted_text = :extracted_text,
                    language_code = :language_code,
                    published_date = :published_date,
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {
                    "source_name": article_data.get('source_name'),
                    "source_domain": source_domain,
                    "title": article_data.get('title'),
                    "extracted_text": article_data.get('extracted_text'),
                    "language_code": article_data.get('language', 'en'),
                    "published_date": article_data.get('published_date'),
                    "analysis_id": analysis_id,
                }
            )

            logger.info(f"Scraped article for analysis {analysis_id}", title=article_data.get('title'))

            return article_data

        except Exception as e:
            logger.error(f"Scraping failed for analysis {analysis_id}: {str(e)}")

            self.db.execute_update(
                """
                UPDATE url_analyses
                SET status = 'failed',
                    error_message = :error_message,
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {"error_message": str(e), "analysis_id": analysis_id}
            )

            return None

    def extract_claims(
        self,
        article_data: Dict[str, Any],
        analysis_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract verifiable claims from article text.

        Args:
            article_data: Article data from scraper
            analysis_id: Analysis ID

        Returns:
            List of extracted claims
        """
        try:
            text = article_data.get('extracted_text', '')

            if not text or len(text) < 100:
                logger.warning(f"Article text too short for claim extraction: {analysis_id}")
                return []

            # Extract claims using existing claim extractor
            claims = self.claim_extractor.extract_claims(text)

            # Store claims in analysis record
            self.db.execute_update(
                """
                UPDATE url_analyses
                SET extracted_claims = :claims::jsonb,
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {"claims": str(claims), "analysis_id": analysis_id}
            )

            logger.info(f"Extracted {len(claims)} claims for analysis {analysis_id}")

            return claims

        except Exception as e:
            logger.error(f"Claim extraction failed for analysis {analysis_id}: {str(e)}")
            return []

    def calculate_credibility(
        self,
        fact_checks: List[Dict[str, Any]]
    ) -> tuple[int, str]:
        """
        Calculate overall credibility score and level.

        Args:
            fact_checks: List of fact-check results

        Returns:
            Tuple of (reliability_score, overall_credibility)
        """
        if not fact_checks:
            return (50, "MEDIUM")  # Neutral for no fact checks

        # Verdict weights
        verdict_weights = {
            'verified': 1.0,
            'VERIFIED': 1.0,
            'partially_true': 0.6,
            'PARTIALLY_TRUE': 0.6,
            'unverified': 0.3,
            'UNVERIFIED': 0.3,
            'disputed': 0.0,
            'DISPUTED': 0.0,
            'FALSE': 0.0
        }

        total_score = 0.0
        total_weight = 0.0

        for fc in fact_checks:
            verdict = fc.get('verdict', fc.get('verification_status', 'unverified'))
            confidence = fc.get('confidence_score', 0.5)

            verdict_weight = verdict_weights.get(verdict, 0.5)

            total_score += verdict_weight * confidence
            total_weight += confidence

        if total_weight == 0:
            reliability_score = 50
        else:
            reliability_score = int((total_score / total_weight) * 100)

        # Determine credibility level via the single source of truth (seq-5):
        # this path used 75/45, which disagreed with the canonical 80/50
        # reliability_scorer for borderline scores (76 -> HIGH here, MEDIUM there).
        from shared.credibility_thresholds import level_for
        credibility_level = level_for(reliability_score)

        return (reliability_score, credibility_level)

    def finalize_analysis(
        self,
        analysis_id: str,
        fact_checks: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]]
    ):
        """
        Finalize analysis with fact-check results.

        Args:
            analysis_id: Analysis ID
            fact_checks: Fact-check results
            evidence: Supporting evidence
        """
        try:
            # Calculate credibility
            reliability_score, credibility_level = self.calculate_credibility(fact_checks)

            # Calculate processing time
            processing_time_query = """
                SELECT EXTRACT(EPOCH FROM (NOW() - processing_started_at)) * 1000 as processing_ms
                FROM url_analyses
                WHERE analysis_id = :analysis_id
            """

            time_result = self.db.execute_query(processing_time_query, {"analysis_id": analysis_id})
            processing_ms = int(time_result[0]['processing_ms']) if time_result else 0

            # Update analysis with final results
            self.db.execute_update(
                """
                UPDATE url_analyses
                SET status = 'completed',
                    completed_at = NOW(),
                    processing_time_ms = :processing_ms,
                    reliability_score = :reliability_score,
                    overall_credibility = :credibility_level,
                    fact_checks = :fact_checks::jsonb,
                    evidence = :evidence::jsonb,
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {
                    "processing_ms": processing_ms,
                    "reliability_score": reliability_score,
                    "credibility_level": credibility_level,
                    "fact_checks": str(fact_checks),
                    "evidence": str(evidence),
                    "analysis_id": analysis_id,
                }
            )

            logger.info(
                f"Analysis completed: {analysis_id}",
                reliability_score=reliability_score,
                credibility_level=credibility_level,
                processing_ms=processing_ms
            )

        except Exception as e:
            logger.error(f"Failed to finalize analysis {analysis_id}: {str(e)}")

            self.db.execute_update(
                """
                UPDATE url_analyses
                SET status = 'failed',
                    error_message = :error_message,
                    updated_at = NOW()
                WHERE analysis_id = :analysis_id
                """,
                {"error_message": str(e), "analysis_id": analysis_id}
            )

    def get_analysis_status(self, analysis_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an analysis.

        Args:
            analysis_id: Analysis ID
            user_id: User ID (for authorization)

        Returns:
            Analysis status dict or None
        """
        query = """
            SELECT
                analysis_id, user_id, submitted_url as url,
                status, title, source_name, source_domain,
                reliability_score, overall_credibility,
                extracted_claims, fact_checks, evidence,
                processing_started_at, completed_at, processing_time_ms,
                error_message, created_at, updated_at
            FROM url_analyses
            WHERE analysis_id = :analysis_id AND user_id = :user_id
        """

        results = self.db.execute_query(query, {"analysis_id": analysis_id, "user_id": user_id})

        if results:
            return dict(results[0])

        return None

    def cleanup(self):
        """Close connections and cleanup resources."""
        self.scraper.close()


# Singleton instance
_analyzer: Optional[URLAnalyzer] = None


def get_url_analyzer() -> URLAnalyzer:
    """Get or create URLAnalyzer singleton instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = URLAnalyzer()
    return _analyzer
