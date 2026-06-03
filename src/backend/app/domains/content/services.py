"""
Content Domain Services

Business logic for article management, search, and credibility scoring.
"""

from typing import Optional
from uuid import UUID

from app.core.database import Database
from app.core.logging import get_logger
from .repository import ArticleRepository
from .models import Article, ArticleDetail, TagStat

logger = get_logger(__name__)


class ArticleNotFoundError(Exception):
    """Raised when an article is not found."""
    def __init__(self, article_id: UUID):
        self.article_id = article_id
        super().__init__(f"Article {article_id} not found")


class ArticleService:
    """
    Business logic for article operations.
    
    This service provides high-level operations for working with articles,
    delegating data access to the ArticleRepository.
    """
    
    def __init__(self, db: Database):
        self.repository = ArticleRepository(db)
        self.db = db
    
    def get_article(self, article_id: UUID) -> Article:
        """
        Get article by ID.
        
        Args:
            article_id: Article UUID
        
        Returns:
            Article model
        
        Raises:
            ArticleNotFoundError: If article doesn't exist
        """
        article = self.repository.get_by_id(article_id)
        if not article:
            raise ArticleNotFoundError(article_id)
        
        logger.info(f"Article retrieved: {article_id}")
        return article
    
    def get_article_detail(self, article_id: UUID) -> ArticleDetail:
        """
        Get article with full content and fact-checks.
        
        Args:
            article_id: Article UUID
        
        Returns:
            ArticleDetail with claims
        
        Raises:
            ArticleNotFoundError: If article doesn't exist
        """
        article = self.repository.get_detail(article_id)
        if not article:
            raise ArticleNotFoundError(article_id)
        
        logger.info(f"Article detail retrieved: {article_id}, claims={len(article.claims)}")
        return article
    
    def search_articles(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        credibility: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> list[Article]:
        """
        Search articles with filters.
        
        Args:
            query: Search query string
            country: Country code filter
            credibility: Credibility level filter
            tags: Tag filters
            limit: Max results (default 20, max 100)
            offset: Pagination offset
        
        Returns:
            List of articles matching criteria
        """
        # Enforce max limit
        limit = min(limit, 100)
        
        articles = self.repository.list_articles(
            query=query,
            country=country,
            credibility=credibility,
            tags=tags,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Article search completed: query={query}, country={country}, credibility={credibility}, results={len(articles)}")
        
        return articles
    
    def get_popular_tags(self, limit: int = 50) -> list[TagStat]:
        """
        Get most popular tags.
        
        Args:
            limit: Max tags to return
        
        Returns:
            List of TagStat models
        """
        return self.repository.get_tags(limit=limit)
    
    def get_platform_stats(self) -> dict:
        """
        Get platform-wide statistics.
        
        Returns:
            Dict with aggregate stats
        """
        return self.repository.get_stats()
    
    def calculate_credibility_score(self, article: ArticleDetail) -> float:
        """
        Calculate article credibility based on claim verdicts.
        
        Uses weighted average of claim confidence scores and verdicts.
        
        Args:
            article: ArticleDetail with claims
        
        Returns:
            Credibility score (0-1)
        """
        if not article.claims:
            # No claims verified yet
            return 0.5
        
        # Verdict weights
        verdict_weights = {
            'verified': 1.0,
            'partially_true': 0.6,
            'unverified': 0.3,
            'disputed': 0.0
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for claim in article.claims:
            if not claim.fact_check:
                continue
            
            # Get importance (default to 1.0 if not set)
            importance = claim.importance_score or 1.0
            
            # Get verdict weight
            verdict = claim.fact_check.verdict
            verdict_weight = verdict_weights.get(verdict, 0.5)
            
            # Get confidence
            confidence = claim.fact_check.confidence_score
            
            # Weighted contribution
            total_weighted_score += importance * confidence * verdict_weight
            total_weight += importance
        
        if total_weight == 0:
            return 0.5
        
        credibility = total_weighted_score / total_weight
        
        logger.debug(f"Credibility calculated: {article.article_id}, claims={len(article.claims)}, score={credibility}")
        
        return credibility
    
    def get_credibility_level(self, score: float) -> str:
        """
        Convert numeric credibility score to level.
        
        Args:
            score: Credibility score (0-1)
        
        Returns:
            'high', 'medium', or 'low'
        """
        # Single source of truth (seq-5): was 0.75/0.45, now the canonical
        # 0.80/0.50 so this label agrees with the URL + reliability scorers.
        from shared.credibility_thresholds import level_for_unit
        return level_for_unit(score).lower()

