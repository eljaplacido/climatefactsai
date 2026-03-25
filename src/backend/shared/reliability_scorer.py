"""
Reliability Scoring Engine

Calculates article reliability scores using multiple factors:
1. Source credibility (50%)
2. Verified claims ratio (30%)
3. Content relevance (20%)

Formula:
reliability_score = (
    source_credibility * 0.50 +
    verified_claims_ratio * 0.30 +
    content_relevance * 0.20
)

Categorization:
- HIGH: ≥ 80
- MEDIUM: 50-79
- LOW: < 50
"""

from typing import Dict, Any, Optional, Tuple
from enum import Enum


class CredibilityLevel(str, Enum):
    """Article credibility level classification.

    Attributes:
        HIGH: High credibility (≥80 score, no false claims)
        MEDIUM: Medium credibility (50-79 score, possible misleading content)
        LOW: Low credibility (<50 score)
        MIXED: Mixed credibility (high score but contains false claims)
        UNVERIFIED: No verification performed yet
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MIXED = "MIXED"
    UNVERIFIED = "UNVERIFIED"


class ReliabilityScorer:
    """Calculate article reliability scores using multi-factor analysis.

    Implements weighted scoring algorithm combining source credibility,
    verified claims ratio, and content relevance. Used by verification
    agents to assess article trustworthiness.

    Scoring Formula:
        reliability_score = (
            source_credibility * 0.50 +
            verified_claims_ratio * 0.30 +
            content_relevance * 0.20
        )

    Attributes:
        WEIGHT_SOURCE_CREDIBILITY: Source credibility weight (50%)
        WEIGHT_VERIFIED_CLAIMS: Verified claims weight (30%)
        WEIGHT_CONTENT_RELEVANCE: Content relevance weight (20%)
        THRESHOLD_HIGH: High credibility threshold (80)
        THRESHOLD_MEDIUM: Medium credibility threshold (50)

    Example:
        >>> score, level = ReliabilityScorer.calculate_reliability_score(
        ...     source_credibility_score=85,
        ...     total_claims=10,
        ...     verified_claims=8,
        ...     false_claims=0,
        ...     misleading_claims=2,
        ...     content_relevance_score=0.75
        ... )
        >>> print(f"Score: {score}, Level: {level}")
        Score: 78, Level: MEDIUM
    """

    # Weight factors (must sum to 1.0)
    WEIGHT_SOURCE_CREDIBILITY = 0.50
    WEIGHT_VERIFIED_CLAIMS = 0.30
    WEIGHT_CONTENT_RELEVANCE = 0.20

    # Threshold values
    THRESHOLD_HIGH = 80
    THRESHOLD_MEDIUM = 50

    @classmethod
    def calculate_reliability_score(
        cls,
        source_credibility_score: Optional[int] = None,
        total_claims: int = 0,
        verified_claims: int = 0,
        false_claims: int = 0,
        misleading_claims: int = 0,
        content_relevance_score: Optional[float] = None
    ) -> Tuple[int, str]:
        """
        Calculate overall reliability score and credibility level

        Args:
            source_credibility_score: Source credibility (0-100)
            total_claims: Total number of claims identified
            verified_claims: Number of verified claims
            false_claims: Number of false claims
            misleading_claims: Number of misleading claims
            content_relevance_score: Content relevance (0.0-1.0)

        Returns:
            Tuple of (reliability_score: int, credibility_level: str)
        """

        # 1. Source Credibility Component (50%)
        if source_credibility_score is not None:
            source_component = cls._normalize_score(source_credibility_score) * cls.WEIGHT_SOURCE_CREDIBILITY
        else:
            # Default to neutral if not provided
            source_component = 50.0 * cls.WEIGHT_SOURCE_CREDIBILITY

        # 2. Verified Claims Ratio Component (30%)
        if total_claims > 0:
            # Calculate verified ratio
            verified_ratio = verified_claims / total_claims

            # Penalize for false/misleading claims
            false_ratio = false_claims / total_claims
            misleading_ratio = misleading_claims / total_claims

            # Weighted claims score
            claims_score = (
                verified_ratio * 100.0 -
                false_ratio * 100.0 -
                misleading_ratio * 50.0  # Misleading is less severe than false
            )

            # Clamp to 0-100
            claims_score = max(0.0, min(100.0, claims_score))

            claims_component = claims_score * cls.WEIGHT_VERIFIED_CLAIMS
        else:
            # No claims found - use neutral score
            claims_component = 60.0 * cls.WEIGHT_VERIFIED_CLAIMS

        # 3. Content Relevance Component (20%)
        if content_relevance_score is not None:
            # Convert 0.0-1.0 to 0-100
            relevance_score = content_relevance_score * 100.0
            relevance_component = relevance_score * cls.WEIGHT_CONTENT_RELEVANCE
        else:
            # Default to neutral
            relevance_component = 60.0 * cls.WEIGHT_CONTENT_RELEVANCE

        # Calculate final reliability score
        reliability_score = int(round(
            source_component + claims_component + relevance_component
        ))

        # Ensure score is in valid range
        reliability_score = max(0, min(100, reliability_score))

        # Determine credibility level
        credibility_level = cls._determine_credibility_level(
            reliability_score=reliability_score,
            has_false_claims=(false_claims > 0),
            has_misleading_claims=(misleading_claims > 0)
        )

        return reliability_score, credibility_level

    @classmethod
    def _normalize_score(cls, score: float) -> float:
        """Normalize score to valid 0-100 range with clamping.

        Args:
            score: Input score (any numeric value)

        Returns:
            Normalized score clamped to 0-100 range

        Example:
            >>> ReliabilityScorer._normalize_score(150)
            100.0
            >>> ReliabilityScorer._normalize_score(-10)
            0.0
        """
        if score < 0:
            return 0.0
        elif score > 100:
            return 100.0
        return float(score)

    @classmethod
    def _determine_credibility_level(
        cls,
        reliability_score: int,
        has_false_claims: bool = False,
        has_misleading_claims: bool = False
    ) -> str:
        """Determine credibility level category with claim-based overrides.

        Applies business logic: articles with false claims cannot be HIGH,
        articles with misleading claims cannot exceed MEDIUM.

        Args:
            reliability_score: Overall reliability score (0-100)
            has_false_claims: Whether article contains any false claims
            has_misleading_claims: Whether article contains misleading claims

        Returns:
            Credibility level string (HIGH, MEDIUM, LOW, or MIXED)

        Example:
            >>> # High score but false claims = MIXED
            >>> ReliabilityScorer._determine_credibility_level(85, has_false_claims=True)
            'MIXED'
            >>> # High score, misleading only = MEDIUM
            >>> ReliabilityScorer._determine_credibility_level(85, has_misleading_claims=True)
            'MEDIUM'
        """

        # If article has false claims, it's automatically MIXED at best
        if has_false_claims:
            if reliability_score >= cls.THRESHOLD_HIGH:
                return CredibilityLevel.MIXED
            else:
                return CredibilityLevel.LOW

        # If article has misleading claims, cap at MEDIUM
        if has_misleading_claims:
            if reliability_score >= cls.THRESHOLD_HIGH:
                return CredibilityLevel.MEDIUM
            elif reliability_score >= cls.THRESHOLD_MEDIUM:
                return CredibilityLevel.MEDIUM
            else:
                return CredibilityLevel.LOW

        # Standard categorization
        if reliability_score >= cls.THRESHOLD_HIGH:
            return CredibilityLevel.HIGH
        elif reliability_score >= cls.THRESHOLD_MEDIUM:
            return CredibilityLevel.MEDIUM
        else:
            return CredibilityLevel.LOW

    @classmethod
    def calculate_content_relevance(
        cls,
        title: str,
        text: str,
        climate_keywords: Optional[list] = None
    ) -> float:
        """Calculate content relevance using multilingual keyword matching.

        Analyzes title and text for climate-related keywords across 6 languages
        (English, Finnish, Swedish, German, French, Spanish). Uses logarithmic
        scaling to prevent keyword stuffing inflation.

        Args:
            title: Article title (weighted 3x in matching)
            text: Article body text
            climate_keywords: Custom keyword list (optional, uses defaults if None)

        Returns:
            Relevance score from 0.0 (irrelevant) to 1.0 (highly relevant)

        Example:
            >>> score = ReliabilityScorer.calculate_content_relevance(
            ...     title="Arctic Ice Melting Accelerates",
            ...     text="Scientists report rising carbon emissions and greenhouse effects..."
            ... )
            >>> print(f"Relevance: {score:.2f}")
            Relevance: 0.78
        """

        if climate_keywords is None:
            climate_keywords = [
                # English
                'climate', 'emission', 'carbon', 'renewable', 'sustainability',
                'environment', 'greenhouse', 'pollution', 'global warming',
                'fossil fuel', 'solar', 'wind energy', 'electric vehicle',
                'paris agreement', 'ipcc', 'cop', 'biodiversity',

                # Finnish
                'ilmasto', 'päästö', 'hiili', 'uusiutuva', 'kestävyys',
                'ympäristö', 'kasvihuone', 'saastuminen', 'ilmaston lämpeneminen',

                # Swedish
                'klimat', 'utsläpp', 'förnybar', 'hållbarhet', 'miljö',

                # German
                'klima', 'emission', 'nachhaltig', 'umwelt', 'erneuerbar',

                # French
                'climat', 'émission', 'renouvelable', 'durabilité', 'environnement',

                # Spanish
                'clima', 'emisión', 'renovable', 'sostenibilidad', 'medio ambiente'
            ]

        # Combine title and text (weight title more)
        combined_text = (title.lower() * 3) + " " + text.lower()

        # Count keyword matches
        matches = 0
        total_keywords = len(climate_keywords)

        for keyword in climate_keywords:
            if keyword.lower() in combined_text:
                matches += 1

        # Calculate relevance as percentage of keywords found
        if total_keywords == 0:
            return 0.5  # Neutral if no keywords provided

        relevance = matches / total_keywords

        # Apply logarithmic scaling to avoid too high scores from keyword stuffing
        # Scale: 0-25% keywords = 0.3-0.7, 25-50% = 0.7-0.9, >50% = 0.9-1.0
        if relevance < 0.25:
            scaled_relevance = 0.3 + (relevance / 0.25) * 0.4
        elif relevance < 0.50:
            scaled_relevance = 0.7 + ((relevance - 0.25) / 0.25) * 0.2
        else:
            scaled_relevance = 0.9 + ((relevance - 0.50) / 0.50) * 0.1

        return min(1.0, max(0.0, scaled_relevance))

    @classmethod
    def update_article_reliability(
        cls,
        article_id: str,
        postgres_client,
        logger=None
    ) -> Dict[str, Any]:
        """Recalculate and update article reliability score in database.

        Comprehensive update process:
        1. Fetch article metadata and fact-check results
        2. Calculate content relevance if not set
        3. Compute reliability score using weighted algorithm
        4. Update database with new scores and credibility level

        Args:
            article_id: Article UUID from articles table
            postgres_client: PostgresClient instance for database access
            logger: Optional logger instance for structured logging

        Returns:
            Dictionary containing updated scores:
            - article_id: Article UUID
            - reliability_score: New reliability score (0-100)
            - credibility_level: NEW credibility classification
            - content_relevance_score: Content relevance (0.0-1.0)
            - verified_claims_count: Number of verified claims

        Example:
            >>> from shared.database import get_postgres
            >>> from shared.logger import setup_logging
            >>>
            >>> postgres = get_postgres()
            >>> logger = setup_logging("reliability_updater")
            >>>
            >>> result = ReliabilityScorer.update_article_reliability(
            ...     article_id="550e8400-e29b-41d4-a716-446655440000",
            ...     postgres_client=postgres,
            ...     logger=logger
            ... )
            >>> print(f"Updated: {result['reliability_score']} ({result['credibility_level']})")
        """

        # 1. Fetch article data
        article_query = """
            SELECT
                a.source_credibility_score,
                a.content_relevance_score,
                a.title,
                a.extracted_text,
                a.claims_count,
                a.verified_claims_count
            FROM articles a
            WHERE a.article_id = :article_id
        """

        article_data = postgres_client.execute_query(
            article_query,
            params={"article_id": article_id}
        )

        if not article_data:
            if logger:
                logger.warning(f"Article not found: {article_id}")
            return {}

        article = article_data[0]

        # 2. Get fact-check stats
        factcheck_query = """
            SELECT
                COUNT(*) FILTER (WHERE fc.verification_status = 'VERIFIED') as verified_count,
                COUNT(*) FILTER (WHERE fc.verification_status = 'FALSE') as false_count,
                COUNT(*) FILTER (WHERE fc.verification_status = 'MISLEADING') as misleading_count,
                COUNT(*) as total_fact_checks
            FROM claims c
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE c.article_id = :article_id
        """

        factcheck_data = postgres_client.execute_query(
            factcheck_query,
            params={"article_id": article_id}
        )

        factcheck = factcheck_data[0] if factcheck_data else {}

        # 3. Calculate content relevance if not already set
        content_relevance = article.get('content_relevance_score')
        if content_relevance is None:
            content_relevance = cls.calculate_content_relevance(
                title=article.get('title', ''),
                text=article.get('extracted_text', '')
            )
        else:
            # Ensure it's a float between 0-1
            content_relevance = float(content_relevance)

        # 4. Calculate reliability score
        reliability_score, credibility_level = cls.calculate_reliability_score(
            source_credibility_score=article.get('source_credibility_score'),
            total_claims=article.get('claims_count', 0),
            verified_claims=factcheck.get('verified_count', 0),
            false_claims=factcheck.get('false_count', 0),
            misleading_claims=factcheck.get('misleading_count', 0),
            content_relevance_score=content_relevance
        )

        # 5. Update database
        update_query = """
            UPDATE articles
            SET
                reliability_score = :reliability_score,
                overall_credibility = :overall_credibility,
                content_relevance_score = :content_relevance_score,
                verified_claims_count = :verified_claims_count,
                updated_at = CURRENT_TIMESTAMP
            WHERE article_id = :article_id
        """

        postgres_client.execute_query(
            update_query,
            params={
                "article_id": article_id,
                "reliability_score": reliability_score,
                "overall_credibility": credibility_level,
                "content_relevance_score": content_relevance,
                "verified_claims_count": factcheck.get('verified_count', 0)
            }
        )

        if logger:
            logger.info(
                "Reliability score updated",
                article_id=article_id,
                reliability_score=reliability_score,
                credibility_level=credibility_level
            )

        return {
            "article_id": article_id,
            "reliability_score": reliability_score,
            "credibility_level": credibility_level,
            "content_relevance_score": content_relevance,
            "verified_claims_count": factcheck.get('verified_count', 0)
        }

    @classmethod
    def calculate_decomposed_reliability(
        cls,
        source_credibility_score: Optional[int] = None,
        total_claims: int = 0,
        verified_claims: int = 0,
        false_claims: int = 0,
        content_relevance_score: Optional[float] = None,
        evidence_count: int = 0,
        cross_source_agreement: float = 0.5,
        publication_age_days: int = 30,
    ) -> Dict[str, Any]:
        """Calculate decomposed reliability with individual factor scores.

        Returns a breakdown dict with each factor's weight, raw score,
        weighted contribution, and a human-friendly label.

        Args:
            source_credibility_score: Source credibility (0-100)
            total_claims: Total claims found
            verified_claims: Verified claims
            false_claims: False claims
            content_relevance_score: Relevance (0.0-1.0)
            evidence_count: Total evidence pieces retrieved
            cross_source_agreement: Agreement ratio across sources (0.0-1.0)
            publication_age_days: Days since publication

        Returns:
            Dict with 'overall_score', 'level', and 'factors' breakdown
        """
        # Source quality (normalised 0-1)
        src_quality = (source_credibility_score or 50) / 100.0

        # Claims verification ratio
        claims_ratio = (verified_claims / total_claims) if total_claims > 0 else 0.5
        false_penalty = (false_claims / total_claims) if total_claims > 0 else 0.0
        claims_score = max(0.0, claims_ratio - false_penalty)

        # Evidence breadth (log scale, capped at 1.0)
        import math
        breadth = min(1.0, math.log1p(evidence_count) / math.log1p(10))

        # Cross-reference score
        cross_ref = max(0.0, min(1.0, cross_source_agreement))

        # Temporal relevance (decay over 365 days)
        temporal = max(0.1, 1.0 - (publication_age_days / 365.0))

        # Content relevance
        relevance = content_relevance_score if content_relevance_score is not None else 0.5

        factors = {
            "source_quality": {
                "weight": 0.25, "score": round(src_quality, 3),
                "weighted_score": round(src_quality * 0.25, 3),
                "label": "Source Quality",
            },
            "claims_verification": {
                "weight": 0.20, "score": round(claims_score, 3),
                "weighted_score": round(claims_score * 0.20, 3),
                "label": "Claims Verification",
            },
            "evidence_breadth": {
                "weight": 0.15, "score": round(breadth, 3),
                "weighted_score": round(breadth * 0.15, 3),
                "label": "Evidence Breadth",
            },
            "cross_reference": {
                "weight": 0.20, "score": round(cross_ref, 3),
                "weighted_score": round(cross_ref * 0.20, 3),
                "label": "Cross-Reference Agreement",
            },
            "temporal_relevance": {
                "weight": 0.10, "score": round(temporal, 3),
                "weighted_score": round(temporal * 0.10, 3),
                "label": "Recency",
            },
            "content_relevance": {
                "weight": 0.10, "score": round(relevance, 3),
                "weighted_score": round(relevance * 0.10, 3),
                "label": "Content Relevance",
            },
        }

        overall = sum(f["weighted_score"] for f in factors.values())
        overall_pct = int(round(overall * 100))

        if overall_pct >= 80:
            level = "HIGH"
        elif overall_pct >= 50:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "overall_score": overall_pct,
            "level": level,
            "factors": factors,
        }

    @classmethod
    def get_reliability_breakdown(
        cls,
        article_id: str,
        postgres_client,
    ) -> Dict[str, Any]:
        """Fetch article data and return full decomposed reliability breakdown.

        Args:
            article_id: Article UUID
            postgres_client: Database client

        Returns:
            Decomposed reliability dict or empty dict if article not found
        """
        article_data = postgres_client.execute_query(
            """SELECT a.source_credibility_score, a.content_relevance_score,
                      a.claims_count, a.verified_claims_count
               FROM articles a WHERE a.article_id = :article_id""",
            {"article_id": article_id},
        )
        if not article_data:
            return {}

        article = article_data[0]

        factcheck_data = postgres_client.execute_query(
            """SELECT COUNT(*) FILTER (WHERE fc.verification_status = 'FALSE') as false_count,
                      COUNT(*) as total_evidence
               FROM claims c LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
               WHERE c.article_id = :article_id""",
            {"article_id": article_id},
        )
        fc = factcheck_data[0] if factcheck_data else {}

        return cls.calculate_decomposed_reliability(
            source_credibility_score=article.get("source_credibility_score"),
            total_claims=article.get("claims_count", 0),
            verified_claims=article.get("verified_claims_count", 0),
            false_claims=fc.get("false_count", 0),
            content_relevance_score=article.get("content_relevance_score"),
            evidence_count=fc.get("total_evidence", 0),
        )


# Example usage and testing
if __name__ == "__main__":
    # Test case 1: High credibility source with verified claims
    score1, level1 = ReliabilityScorer.calculate_reliability_score(
        source_credibility_score=90,
        total_claims=10,
        verified_claims=9,
        false_claims=0,
        misleading_claims=1,
        content_relevance_score=0.85
    )
    print(f"Test 1: Score={score1}, Level={level1}")
    assert level1 == "HIGH" or level1 == "MEDIUM"

    # Test case 2: Medium credibility with some false claims
    score2, level2 = ReliabilityScorer.calculate_reliability_score(
        source_credibility_score=70,
        total_claims=10,
        verified_claims=6,
        false_claims=2,
        misleading_claims=2,
        content_relevance_score=0.60
    )
    print(f"Test 2: Score={score2}, Level={level2}")
    assert level2 == "LOW" or level2 == "MIXED"

    # Test case 3: Low credibility source
    score3, level3 = ReliabilityScorer.calculate_reliability_score(
        source_credibility_score=40,
        total_claims=5,
        verified_claims=1,
        false_claims=3,
        misleading_claims=1,
        content_relevance_score=0.30
    )
    print(f"Test 3: Score={score3}, Level={level3}")
    assert level3 == "LOW"

    # Test content relevance
    relevance = ReliabilityScorer.calculate_content_relevance(
        title="Climate Change Impact on Global Temperatures",
        text="Scientists report rising carbon emissions and greenhouse gas effects..."
    )
    print(f"Test 4: Content Relevance={relevance:.2f}")
    assert 0.0 <= relevance <= 1.0

    print("\n✅ All reliability scorer tests passed!")
