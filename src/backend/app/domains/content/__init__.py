"""
Content Domain

Manages verified climate articles, search, tagging, and user feedback.
"""

from .models import Article, ArticleDetail, Claim, FactCheck, FeedbackSummary
from .repository import ArticleRepository
from .services import ArticleService

__all__ = [
    "Article",
    "ArticleDetail",
    "Claim",
    "FactCheck",
    "FeedbackSummary",
    "ArticleRepository",
    "ArticleService",
]

