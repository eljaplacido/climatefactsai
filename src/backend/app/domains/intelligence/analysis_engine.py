"""
Analysis Engine

Agentic analysis orchestrator that classifies claims, routes them to appropriate
verification strategies, aggregates results, and generates human-readable insights.

Inspired by CARF's Cynefin-based routing and Guardian policy enforcement.
"""

import json
from typing import Optional
from uuid import UUID

from app.core.logging import get_logger
from app.core.database import Database
from .schemas import (
    ClaimCategory, VerificationResult,
)
from .claim_classifier import ClaimClassifier
from .services import VerificationService
from .llm_client import get_llm_client, llm_chat
from shared.reliability_scorer import ReliabilityScorer
from app.domains.content.article_generator import AnalysisArticleGenerator

logger = get_logger(__name__)


class AnalysisEngine:
    """
    High-level orchestrator that combines classification, verification,
    reliability scoring, and insight generation into a single pipeline.
    """

    def __init__(self, db: Database):
        self.db = db
        self.verification_service = VerificationService(db)
        self.classifier = ClaimClassifier()
        self.llm_client, self.llm_model = get_llm_client()
        self.article_generator = AnalysisArticleGenerator()

    async def full_analysis(self, article_id: UUID) -> dict:
        """
        Run full analysis pipeline:
        1. Verify article (extract claims, fetch evidence, adjudicate)
        2. Compute decomposed reliability
        3. Generate insight summary
        4. Return combined result

        Returns:
            Dict with verification_result, reliability_breakdown, insight_summary
        """
        # Step 1: Run verification pipeline
        result = await self.verification_service.verify_article(article_id)

        if result.status != "completed":
            return {
                "verification_result": result.dict(),
                "reliability_breakdown": {},
                "insight_summary": None,
            }

        # Step 2: Compute decomposed reliability
        breakdown = ReliabilityScorer.get_reliability_breakdown(
            article_id=str(article_id),
            postgres_client=self.db,
        )

        # Store breakdown in DB
        if breakdown:
            bd_json = json.dumps(breakdown).replace("'", "''")
            self.db.execute_update(
                f"""UPDATE articles
                    SET decomposed_confidence = '{bd_json}'::jsonb
                    WHERE article_id = '{str(article_id)}'""",
                {},
            )

        # Step 3: Generate insight summary
        insight = await self._generate_insight_summary(article_id, result, breakdown)

        if insight:
            insight_safe = insight.replace("'", "''")
            self.db.execute_update(
                f"""UPDATE articles
                    SET insight_summary = '{insight_safe}'
                    WHERE article_id = '{str(article_id)}'""",
                {},
            )

        # Step 4: Generate analysis article
        analysis_html = None
        try:
            # Fetch article text
            article_rows = self.db.execute_query(
                f"SELECT title, COALESCE(extracted_text, excerpt, '') as text FROM articles WHERE article_id = '{str(article_id)}'",
                {},
            )
            if article_rows:
                article_title = article_rows[0].get("title", "Unknown")
                article_text = article_rows[0].get("text", "")

                claims_data = [{"claim_text": c.claim_text, "claim_category": c.claim_category.value if hasattr(c.claim_category, 'value') else str(c.claim_category)} for c in (result.claims if hasattr(result, 'claims') else [])]
                verdicts_data = [v.dict() if hasattr(v, 'dict') else v for v in (result.verdicts if hasattr(result, 'verdicts') else [])]

                article_md = await self.article_generator.generate(
                    article_title=article_title,
                    article_text=article_text,
                    claims=claims_data,
                    verdicts=verdicts_data,
                    decomposed_confidence=breakdown.get("decomposed_confidence") if breakdown else None,
                    reliability_breakdown=breakdown.get("factors") if breakdown else None,
                )

                if article_md:
                    analysis_html = await self.article_generator.generate_html(article_md)
                    # Store in DB
                    safe_html = analysis_html.replace("'", "''")
                    self.db.execute_update(
                        f"""UPDATE articles
                            SET analysis_article_html = '{safe_html}',
                                analysis_article_generated_at = NOW()
                            WHERE article_id = '{str(article_id)}'""",
                        {},
                    )
        except Exception as e:
            logger.error(f"Analysis article generation failed: {e}")

        return {
            "verification_result": result.dict(),
            "reliability_breakdown": breakdown,
            "insight_summary": insight,
            "analysis_article_html": analysis_html,
        }

    async def get_article_insights(self, article_id: UUID) -> dict:
        """
        Retrieve pre-computed insights for an article.
        Returns cached data from DB without re-running analysis.
        """
        rows = self.db.execute_query(
            f"""SELECT
                    a.reliability_score,
                    a.overall_credibility,
                    a.decomposed_confidence,
                    a.insight_summary,
                    a.claims_count,
                    a.verified_claims_count
                FROM articles a
                WHERE a.article_id = '{str(article_id)}'""",
            {},
        )
        if not rows:
            return {}

        article = rows[0]

        # Get claims by category
        cat_rows = self.db.execute_query(
            f"""SELECT claim_category, COUNT(*) as cnt
                FROM claims
                WHERE article_id = '{str(article_id)}' AND claim_category IS NOT NULL
                GROUP BY claim_category""",
            {},
        )
        claims_by_category = {r["claim_category"]: r["cnt"] for r in cat_rows} if cat_rows else {}

        return {
            "article_id": str(article_id),
            "reliability_score": article.get("reliability_score"),
            "credibility_level": article.get("overall_credibility"),
            "decomposed_confidence": article.get("decomposed_confidence"),
            "insight_summary": article.get("insight_summary"),
            "claims_count": article.get("claims_count", 0),
            "verified_claims_count": article.get("verified_claims_count", 0),
            "claims_by_category": claims_by_category,
        }

    async def _generate_insight_summary(
        self,
        article_id: UUID,
        result: VerificationResult,
        breakdown: dict,
    ) -> Optional[str]:
        """Generate a human-readable insight summary using DeepSeek."""
        if not self.llm_client:
            logger.warning("No LLM client for insight generation (DEEPSEEK_API_KEY not set)")
            return None

        try:
            prompt = f"""You are a climate news analyst. Generate a concise, user-friendly
insight summary for an article that was fact-checked.

VERIFICATION RESULTS:
- Claims extracted: {result.claims_extracted}
- Verified: {result.claims_verified}
- Disputed: {result.claims_disputed}
- Unverified: {result.claims_unverified}
- Average confidence: {result.average_confidence:.0%}
- Credibility level: {result.credibility_level}
- Claims by category: {json.dumps(result.claims_by_category)}

RELIABILITY BREAKDOWN:
{json.dumps(breakdown.get('factors', {}), indent=2) if breakdown else 'Not available'}

Write a 2-3 sentence summary that:
1. States the overall credibility assessment
2. Highlights the strongest and weakest verification areas
3. Notes any concerns or caveats

Be factual, balanced, and avoid alarmist language. Write in plain English.
Return ONLY the summary text, no JSON or formatting."""

            return llm_chat(
                prompt,
                max_tokens=300,
                temperature=0.3,
                client=self.llm_client,
                model=self.llm_model,
            )

        except Exception as e:
            logger.error(f"Insight generation failed: {e}")
            return None

    async def analyze_text(self, text: str, max_claims: int = 15) -> dict:
        """
        Analyze raw text without storing to DB (for quick analysis).
        Extracts claims, classifies them, and returns structured result.
        """
        claims = await self.verification_service.extractor.decompose_claims(text, max_claims)

        classified = {}
        for claim in claims:
            cat = claim.claim_category.value if isinstance(claim.claim_category, ClaimCategory) else str(claim.claim_category)
            if cat not in classified:
                classified[cat] = []
            classified[cat].append({
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "importance_score": claim.importance_score,
                "claim_context": claim.claim_context,
            })

        return {
            "total_claims": len(claims),
            "claims_by_category": {k: len(v) for k, v in classified.items()},
            "claims": classified,
        }
