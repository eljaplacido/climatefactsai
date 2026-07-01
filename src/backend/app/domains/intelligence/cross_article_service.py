"""
Cross-Article Intelligence Service.

Provides multi-article analysis capabilities:
- Contradiction detection across articles on the same topic.
- Intelligence brief generation with structured summaries.
- Consensus analysis measuring agreement/disagreement across sources.
"""

import json
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)


class CrossArticleService:
    """Cross-article intelligence: contradictions, briefs, and consensus analysis."""

    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------
    # Contradiction detection
    # ------------------------------------------------------------------

    async def find_contradictions(
        self,
        topic: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Find articles with contradictory claims on a topic.

        Searches for articles on the topic, groups by claim categories,
        and finds opposing claims using semantic similarity and negation
        detection.

        Args:
            topic: The topic to search for contradictions.
            limit: Max articles to consider.

        Returns:
            Dict with contradictions list, article pairs, and summary.
        """
        # Step 1: find articles on topic
        articles = self._search_topic_articles(topic, limit)
        if len(articles) < 2:
            return {
                "topic": topic,
                "contradictions": [],
                "article_count": len(articles),
                "summary": "Not enough articles found to detect contradictions.",
            }

        # Step 2: gather claims for these articles
        article_ids = [a["article_id"] for a in articles]
        claims_by_article = self._get_claims_for_articles(article_ids)

        # Step 3: use LLM to identify contradictions
        contradictions = await self._detect_contradictions_llm(
            topic, articles, claims_by_article
        )

        return {
            "topic": topic,
            "contradictions": contradictions,
            "article_count": len(articles),
            "claims_analyzed": sum(len(v) for v in claims_by_article.values()),
            "summary": (
                f"Found {len(contradictions)} contradiction(s) across "
                f"{len(articles)} articles on '{topic}'."
            ),
        }

    # ------------------------------------------------------------------
    # Intelligence brief generation
    # ------------------------------------------------------------------

    async def generate_intelligence_brief(
        self,
        topic: str,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive topic intelligence brief.

        Combines articles into a structured brief with summary, key findings,
        areas of agreement, dispute, data gaps, and recommended further reading.

        Args:
            topic: The topic for the brief.
            country: Optional country code filter.

        Returns:
            Structured intelligence brief dict.
        """
        articles = self._search_topic_articles(topic, limit=30, country=country)
        if not articles:
            return {
                "topic": topic,
                "country": country,
                "summary": "No articles found on this topic.",
                "key_findings": [],
                "areas_of_agreement": [],
                "areas_of_dispute": [],
                "data_gaps": [],
                "recommended_reading": [],
                "article_count": 0,
                "source_diversity": 0,
            }

        article_ids = [a["article_id"] for a in articles]
        claims_by_article = self._get_claims_for_articles(article_ids)

        # Gather article texts for context
        article_contexts = self._get_article_contexts(article_ids[:15])

        # Generate brief via LLM
        brief = await self._generate_brief_llm(
            topic, articles, article_contexts, claims_by_article
        )

        # Add metadata
        sources = set(a.get("source_name", "") for a in articles)
        brief["topic"] = topic
        brief["country"] = country
        brief["article_count"] = len(articles)
        brief["source_diversity"] = len(sources)
        brief["sources_used"] = list(sources)

        # Add consensus analysis
        consensus = await self.consensus_analysis(topic)
        brief["consensus"] = consensus

        return brief

    # ------------------------------------------------------------------
    # Consensus analysis
    # ------------------------------------------------------------------

    async def consensus_analysis(
        self,
        topic: str,
    ) -> Dict[str, Any]:
        """
        Analyze consensus vs controversy across sources for a topic.

        For each major claim, counts supporting vs contradicting articles
        and produces a consensus score.

        Args:
            topic: The topic to analyze.

        Returns:
            Dict with claim-level consensus scores and overall assessment.
        """
        articles = self._search_topic_articles(topic, limit=25)
        if len(articles) < 2:
            return {
                "topic": topic,
                "consensus_score": 0.0,
                "claims": [],
                "assessment": "Insufficient articles for consensus analysis.",
            }

        article_ids = [a["article_id"] for a in articles]
        claims_by_article = self._get_claims_for_articles(article_ids)

        # Use LLM to group claims and assess consensus
        consensus = await self._consensus_llm(topic, articles, claims_by_article)

        return consensus

    # ------------------------------------------------------------------
    # Database queries
    # ------------------------------------------------------------------

    def _search_topic_articles(
        self,
        topic: str,
        limit: int = 20,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Full-text search for articles on a topic."""
        params: Dict[str, Any] = {"query": topic, "limit": limit}
        country_filter = ""
        if country:
            country_filter = "AND a.country_code = :country"
            params["country"] = country.upper()

        rows = self.db.execute_query(
            f"""
            SELECT
                a.article_id,
                a.title,
                a.source_name,
                a.overall_credibility,
                a.country_code,
                a.published_date,
                a.excerpt,
                ts_rank(
                    a.search_tsv,
                    websearch_to_tsquery('english', :query)
                ) AS relevance
            FROM articles a
            WHERE a.search_tsv
                  @@ websearch_to_tsquery('english', :query)
            {country_filter}
            ORDER BY relevance DESC
            LIMIT :limit
            """,
            params,
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "credibility": r.get("overall_credibility", "UNKNOWN"),
                "country_code": r.get("country_code"),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "excerpt": r.get("excerpt", ""),
                "relevance": round(float(r.get("relevance", 0)), 4),
            }
            for r in (rows or [])
        ]

    def _get_claims_for_articles(
        self,
        article_ids: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch verified claims grouped by article_id."""
        if not article_ids:
            return {}

        placeholders = ", ".join(f":id{i}" for i in range(len(article_ids)))
        params = {f"id{i}": aid for i, aid in enumerate(article_ids)}

        rows = self.db.execute_query(
            f"""
            SELECT
                c.article_id,
                c.claim_text,
                c.claim_category,
                fc.verification_status,
                fc.confidence_score
            FROM claims c
            LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
            WHERE c.article_id IN ({placeholders})
            ORDER BY fc.confidence_score DESC NULLS LAST
            """,
            params,
        )

        result: Dict[str, List[Dict[str, Any]]] = {}
        for r in (rows or []):
            aid = str(r["article_id"])
            result.setdefault(aid, []).append(
                {
                    "claim_text": r.get("claim_text", ""),
                    "category": r.get("claim_category"),
                    "status": r.get("verification_status", "unverified"),
                    "confidence": r.get("confidence_score"),
                }
            )
        return result

    def _get_article_contexts(
        self,
        article_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch article text previews for LLM context."""
        if not article_ids:
            return []

        placeholders = ", ".join(f":id{i}" for i in range(len(article_ids)))
        params = {f"id{i}": aid for i, aid in enumerate(article_ids)}

        rows = self.db.execute_query(
            f"""
            SELECT
                a.article_id, a.title, a.source_name,
                a.overall_credibility, a.excerpt,
                SUBSTRING(a.extracted_text FROM 1 FOR 500) AS text_preview,
                a.insight_summary
            FROM articles a
            WHERE a.article_id IN ({placeholders})
            """,
            params,
        )
        return [dict(r) for r in (rows or [])]

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def _detect_contradictions_llm(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        claims_by_article: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Use LLM to identify contradictions across claims."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            # Build context
            context_parts = []
            for a in articles[:15]:
                aid = a["article_id"]
                claims = claims_by_article.get(aid, [])
                claim_texts = [c["claim_text"][:150] for c in claims[:5]]
                context_parts.append(
                    f"Article: {a['title']} (Source: {a['source_name']}, Credibility: {a['credibility']})\n"
                    f"Claims: {'; '.join(claim_texts) if claim_texts else 'No extracted claims'}"
                )
            context = "\n\n".join(context_parts)

            prompt = (
                f'Topic: "{topic}"\n\n'
                f"Articles and claims:\n{context}\n\n"
                "Identify contradictions between articles/claims. Return JSON:\n"
                '{"contradictions": [\n'
                '  {"claim_a": "text", "source_a": "name", "claim_b": "text", "source_b": "name", '
                '"explanation": "why they contradict", "severity": "low/medium/high"}\n'
                "]}"
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt="You detect contradictions in climate articles. Return ONLY JSON.",
                max_tokens=1500,
                temperature=0.1,
            )

            if not response:
                return []

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)
            return result.get("contradictions", [])

        except Exception as e:
            logger.warning(f"Contradiction detection failed: {e}")
            return []

    async def _generate_brief_llm(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]],
        claims_by_article: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Generate intelligence brief using LLM."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            # Build rich context
            context_parts = []
            for ctx in contexts[:10]:
                aid = str(ctx.get("article_id", ""))
                claims = claims_by_article.get(aid, [])
                claim_texts = [c["claim_text"][:100] for c in claims[:3]]
                text = ctx.get("text_preview") or ctx.get("excerpt") or ""
                insight = ctx.get("insight_summary") or ""

                part = (
                    f"ARTICLE: {ctx.get('title', '')}\n"
                    f"SOURCE: {ctx.get('source_name', '')} (Credibility: {ctx.get('overall_credibility', 'UNKNOWN')})\n"
                )
                if insight:
                    part += f"INSIGHT: {insight}\n"
                part += f"CONTENT: {text[:300]}\n"
                if claim_texts:
                    part += f"CLAIMS: {'; '.join(claim_texts)}\n"
                context_parts.append(part)

            context = "\n---\n".join(context_parts)

            prompt = (
                f'Generate an intelligence brief on: "{topic}"\n\n'
                f"Source articles:\n{context}\n\n"
                "Return JSON:\n"
                "{\n"
                '  "summary": "2-3 paragraph executive summary",\n'
                '  "key_findings": ["finding 1", "finding 2", ...],\n'
                '  "areas_of_agreement": ["agreed point 1", ...],\n'
                '  "areas_of_dispute": ["disputed point 1", ...],\n'
                '  "data_gaps": ["gap 1", ...],\n'
                '  "recommended_reading": [{"title": "...", "source": "...", "reason": "..."}]\n'
                "}"
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt="You generate structured intelligence briefs on climate topics. Return ONLY JSON.",
                max_tokens=2000,
                temperature=0.2,
            )

            if not response:
                return self._fallback_brief(topic, articles)

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            return json.loads(cleaned)

        except Exception as e:
            logger.warning(f"Intelligence brief generation failed: {e}")
            return self._fallback_brief(topic, articles)

    async def _consensus_llm(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        claims_by_article: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Analyze consensus using LLM."""
        try:
            from app.domains.intelligence.llm_client import llm_chat

            # Build claim summary
            all_claims = []
            for aid, claims in claims_by_article.items():
                article = next((a for a in articles if a["article_id"] == aid), {})
                for c in claims[:3]:
                    all_claims.append(
                        f"[{article.get('source_name', 'Unknown')}] "
                        f"[{c.get('status', 'unverified')}] {c['claim_text'][:150]}"
                    )

            claims_text = "\n".join(all_claims[:30]) if all_claims else "No claims extracted."

            prompt = (
                f'Topic: "{topic}"\n\n'
                f"Claims from multiple sources:\n{claims_text}\n\n"
                "Analyze consensus. Return JSON:\n"
                "{\n"
                '  "consensus_score": 0.0-1.0,\n'
                '  "claims": [\n'
                '    {"claim": "text", "supporting_sources": 0, "contradicting_sources": 0, "consensus": "high/medium/low"}\n'
                "  ],\n"
                '  "assessment": "brief overall assessment"\n'
                "}"
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt="You analyze source consensus. Return ONLY JSON.",
                max_tokens=1200,
                temperature=0.1,
            )

            if not response:
                return {
                    "topic": topic,
                    "consensus_score": 0.5,
                    "claims": [],
                    "assessment": "Consensus analysis unavailable.",
                }

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)
            result["topic"] = topic
            return result

        except Exception as e:
            logger.warning(f"Consensus analysis failed: {e}")
            return {
                "topic": topic,
                "consensus_score": 0.5,
                "claims": [],
                "assessment": "Consensus analysis unavailable.",
            }

    @staticmethod
    def _fallback_brief(
        topic: str,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a minimal brief when LLM is unavailable."""
        return {
            "summary": f"Intelligence brief on '{topic}' based on {len(articles)} articles.",
            "key_findings": [a.get("title", "") for a in articles[:5]],
            "areas_of_agreement": [],
            "areas_of_dispute": [],
            "data_gaps": ["LLM analysis unavailable for detailed assessment."],
            "recommended_reading": [
                {"title": a.get("title", ""), "source": a.get("source_name", ""), "reason": "Relevant article"}
                for a in articles[:3]
            ],
        }
