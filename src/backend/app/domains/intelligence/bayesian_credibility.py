"""
Bayesian Credibility Enhancement — CARF-inspired scoring.

Uses Bayesian updating to refine article reliability scores based on
source credibility priors and verification evidence.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import Database, get_db
from app.core.logging import get_logger

logger = get_logger(__name__)


class BayesianCredibilityService:
    """Enhanced credibility scoring using Bayesian updating."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    @staticmethod
    def compute_research_prior(
        has_doi: bool = False,
        venue: Optional[str] = None,
        content_type: str = "news_article",
    ) -> float:
        """
        Compute a Bayesian prior for research content.

        DOI presence: +20 points
        Known venue (Nature, Science, etc.): +30 points
        Preprint: base 40 points
        News article: base 50 points
        Research report: base 60 points
        Policy document: base 55 points

        Args:
            has_doi: Whether the article/document has a DOI identifier.
            venue: Publication venue name, if known.
            content_type: One of "news_article", "research_report",
                          "preprint", or "policy_document".

        Returns:
            Prior credibility score in range [0, 100].
        """
        KNOWN_VENUES = {
            "Nature", "Science", "Elsevier", "Springer",
            "Wiley", "PLOS", "Frontiers", "Copernicus",
        }

        if content_type == "preprint":
            base = 40.0
        elif content_type == "research_report":
            base = 60.0
        elif content_type == "policy_document":
            base = 55.0
        else:
            base = 50.0

        if has_doi:
            base += 20.0
        if venue and venue in KNOWN_VENUES:
            base += 30.0

        return min(base, 100.0)

    def compute_posterior(
        self,
        prior_score: float,
        evidence_scores: List[float],
        prior_weight: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Compute Bayesian posterior credibility score.

        Args:
            prior_score: Source credibility score (0-100), used as prior.
            evidence_scores: List of verification evidence scores (0-1 each).
            prior_weight: Weight given to the prior vs evidence.

        Returns:
            Dict with posterior score, confidence interval, and breakdown.
        """
        if not evidence_scores:
            return {
                "posterior_score": prior_score,
                "confidence_interval": [max(0, prior_score - 15), min(100, prior_score + 15)],
                "evidence_count": 0,
                "prior_score": prior_score,
                "methodology": "prior_only",
            }

        # Normalize prior to 0-1
        prior = prior_score / 100.0

        # Compute likelihood from evidence (geometric mean)
        evidence_mean = sum(evidence_scores) / len(evidence_scores)
        evidence_weight = 1.0 - prior_weight

        # Weighted combination (simplified Bayesian update)
        posterior = (prior * prior_weight) + (evidence_mean * evidence_weight)

        # Confidence interval based on evidence variance and count
        n = len(evidence_scores)
        if n > 1:
            variance = sum((s - evidence_mean) ** 2 for s in evidence_scores) / (n - 1)
            std_err = math.sqrt(variance / n)
            # 95% CI approximation
            margin = 1.96 * std_err * 100
        else:
            margin = 20.0  # Wide interval for single evidence

        posterior_pct = round(posterior * 100, 1)
        lower = max(0, round(posterior_pct - margin, 1))
        upper = min(100, round(posterior_pct + margin, 1))

        return {
            "posterior_score": posterior_pct,
            "confidence_interval": [lower, upper],
            "evidence_count": n,
            "prior_score": prior_score,
            "evidence_mean": round(evidence_mean * 100, 1),
            "methodology": "bayesian_update",
        }

    async def update_article_credibility(
        self, article_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Recompute article reliability using Bayesian update.

        Pulls source credibility as prior, verification results as evidence,
        computes posterior, and updates articles.reliability_score.
        """
        try:
            # Get article source info
            rows = self.db.execute_query(
                """SELECT a.article_id, a.source_name, a.reliability_score,
                          COALESCE(sc.overall_score, 50) as source_score
                   FROM articles a
                   LEFT JOIN source_credibility sc
                     ON LOWER(a.source_name) = LOWER(sc.source_name)
                   WHERE a.article_id = :aid""",
                {"aid": article_id},
            )
            if not rows:
                return None

            source_score = rows[0].get("source_score", 50)

            # Get verification results as evidence scores
            verdict_rows = self.db.execute_query(
                """SELECT confidence_score
                   FROM fact_checks
                   WHERE article_id = :aid
                     AND confidence_score IS NOT NULL""",
                {"aid": article_id},
            )
            evidence = [
                float(r["confidence_score"]) / 100.0
                for r in (verdict_rows or [])
                if r.get("confidence_score") is not None
            ]

            result = self.compute_posterior(float(source_score), evidence)

            # Update article with new score
            self.db.execute_update(
                """UPDATE articles
                   SET reliability_score = :score, updated_at = NOW()
                   WHERE article_id = :aid""",
                {"score": int(result["posterior_score"]), "aid": article_id},
            )

            return result

        except Exception as e:
            logger.error(f"Bayesian update failed for article {article_id}: {e}")
            return None
