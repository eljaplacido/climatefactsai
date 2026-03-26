"""
RAG Evidence Retriever — queries the article corpus for similar verified claims.

Uses HybridRAGService (pgvector semantic + full-text + knowledge graph) with
Reciprocal Rank Fusion to find previously verified articles with similar claims,
providing internal cross-reference evidence.
"""

import os
from typing import Optional

from app.core.logging import get_logger
from app.core.database import get_db
from .schemas import Evidence

logger = get_logger(__name__)


class RAGEvidenceRetriever:
    """
    Retrieves evidence from the internal article corpus using hybrid multi-strategy
    search (pgvector semantic, PostgreSQL FTS, knowledge graph) fused with RRF.

    Falls back to direct pgvector search when the hybrid service is unavailable.
    """

    SIMILARITY_THRESHOLD = 0.5
    MAX_RESULTS = 15

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """
        Search for similar verified articles using HybridRAGService.

        Falls back gracefully if embeddings are not populated or services unavailable.
        """
        evidence = []

        try:
            db = get_db()

            # Use HybridRAGService for multi-strategy retrieval
            from app.domains.intelligence.hybrid_rag_service import HybridRAGService

            hybrid = HybridRAGService(db)
            filters = {}
            if country_code:
                filters["country_code"] = country_code

            results = await hybrid.retrieve(
                query=claim,
                limit=self.MAX_RESULTS,
                filters=filters,
            )

            for item in results:
                similarity = float(item.get("rrf_score", item.get("similarity_score", 0)))
                if similarity < self.SIMILARITY_THRESHOLD and not item.get("retrieval_sources"):
                    continue

                credibility = item.get("credibility", "UNKNOWN")
                title = item.get("title", "")
                source_name = item.get("source_name", "Unknown")
                retrieval_sources = item.get("retrieval_sources", [])

                # Determine if similar article supports or contradicts
                supports = None
                if credibility == "HIGH":
                    supports = True
                elif credibility == "LOW":
                    supports = False

                strategy_label = ", ".join(retrieval_sources) if retrieval_sources else "hybrid"

                evidence.append(Evidence(
                    source=f"CliLens Corpus ({source_name})",
                    source_url="",
                    source_reliability="high" if credibility == "HIGH" else "medium",
                    content_excerpt=(
                        f"Similar article: \"{title}\". "
                        f"Credibility: {credibility}. "
                        f"Retrieval: {strategy_label}. "
                        f"Score: {similarity:.4f}"
                    ),
                    relevance_score=round(min(similarity * 2.0, 0.95), 2),
                    supports_claim=supports,
                    retrieval_method=f"hybrid_rag_{strategy_label}",
                ))

            if evidence:
                logger.info(f"RAG retriever found {len(evidence)} similar articles via hybrid search")

        except ImportError:
            logger.debug("HybridRAGService not available, falling back to direct pgvector")
            return await self._fallback_pgvector_retrieve(claim)
        except Exception as e:
            logger.warning(f"RAG evidence retrieval failed: {e}")

        return evidence

    async def _fallback_pgvector_retrieve(self, claim: str) -> list[Evidence]:
        """Direct pgvector search fallback when HybridRAGService is unavailable."""
        evidence = []
        try:
            db = get_db()

            check = db.execute_query(
                "SELECT COUNT(*) as cnt FROM articles WHERE embedding IS NOT NULL"
            )
            if not check or check[0]["cnt"] == 0:
                return []

            claim_embedding = await self._get_claim_embedding(claim)
            if claim_embedding is None:
                return []

            rows = db.execute_query(
                """
                SELECT
                    a.article_id, a.title, a.url, a.source_name,
                    a.reliability_score, a.overall_credibility,
                    a.claims_count, a.verified_claims_count,
                    1 - (a.embedding <=> :embedding::vector) as similarity
                FROM articles a
                WHERE a.embedding IS NOT NULL
                  AND a.claims_status = 'completed'
                  AND 1 - (a.embedding <=> :embedding::vector) > :threshold
                ORDER BY a.embedding <=> :embedding::vector
                LIMIT :max_results
                """,
                {
                    "embedding": claim_embedding,
                    "threshold": self.SIMILARITY_THRESHOLD,
                    "max_results": self.MAX_RESULTS,
                },
            )

            for row in (rows or []):
                similarity = float(row.get("similarity", 0))
                reliability = row.get("reliability_score")
                credibility = row.get("overall_credibility", "")

                supports = None
                if credibility == "HIGH" and reliability and reliability >= 70:
                    supports = True
                elif credibility == "LOW" or (reliability and reliability < 30):
                    supports = False

                evidence.append(Evidence(
                    source=f"CliLens Corpus ({row.get('source_name', 'Unknown')})",
                    source_url=row.get("url", ""),
                    source_reliability="high" if reliability and reliability >= 70 else "medium",
                    content_excerpt=(
                        f"Similar verified article: \"{row.get('title', '')}\". "
                        f"Credibility: {credibility}, Reliability: {reliability}/100, "
                        f"Claims: {row.get('verified_claims_count', 0)}/{row.get('claims_count', 0)} verified. "
                        f"Similarity: {similarity:.2f}"
                    ),
                    relevance_score=round(similarity * 0.9, 2),
                    supports_claim=supports,
                    retrieval_method="rag_pgvector",
                ))

        except Exception as e:
            logger.warning(f"Fallback pgvector retrieval failed: {e}")

        return evidence

    async def _get_claim_embedding(self, text: str) -> Optional[str]:
        """
        Generate an embedding vector for the claim text.

        Uses the same embedding service as article ingestion.
        Returns the vector as a string for pgvector, or None if unavailable.
        """
        try:
            from app.domains.content.embedding_service import generate_embedding
            embedding = await generate_embedding(text)
            if embedding:
                # Format as pgvector string: [0.1, 0.2, ...]
                return f"[{','.join(str(v) for v in embedding)}]"
        except ImportError:
            logger.debug("Embedding service not available")
        except Exception as e:
            logger.warning(f"Claim embedding generation failed: {e}")

        return None
