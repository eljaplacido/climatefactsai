"""
RAG Evidence Retriever — queries the article corpus for similar verified claims.

Uses pgvector cosine similarity on article embeddings to find previously verified
articles with similar claims, providing internal cross-reference evidence.
"""

import os
from typing import Optional

from app.core.logging import get_logger
from app.core.database import get_db
from .schemas import Evidence

logger = get_logger(__name__)


class RAGEvidenceRetriever:
    """
    Retrieves evidence from the internal article corpus using pgvector similarity search.

    Queries articles that have been previously verified and have embeddings,
    finding similar content that can serve as corroborating or contradicting evidence.
    """

    SIMILARITY_THRESHOLD = 0.7
    MAX_RESULTS = 5

    async def retrieve(self, claim: str, country_code: str = "FI") -> list[Evidence]:
        """
        Search for similar verified articles using pgvector cosine similarity.

        Falls back gracefully if embeddings are not populated or pgvector is unavailable.
        """
        evidence = []

        try:
            db = get_db()

            # First check if we have any articles with embeddings
            check = db.execute_query(
                "SELECT COUNT(*) as cnt FROM articles WHERE embedding IS NOT NULL"
            )
            if not check or check[0]["cnt"] == 0:
                logger.debug("No article embeddings available for RAG retrieval")
                return []

            # Generate embedding for the claim using the same method as articles
            claim_embedding = await self._get_claim_embedding(claim)
            if claim_embedding is None:
                return []

            # Query similar articles using pgvector cosine distance
            rows = db.execute_query(
                """
                SELECT
                    a.article_id,
                    a.title,
                    a.url,
                    a.source_name,
                    a.reliability_score,
                    a.overall_credibility,
                    a.claims_count,
                    a.verified_claims_count,
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

                # Determine if similar article supports or contradicts
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
                    relevance_score=round(similarity * 0.9, 2),  # Slightly discount internal evidence
                    supports_claim=supports,
                    retrieval_method="rag_pgvector",
                ))

            if evidence:
                logger.info(f"RAG retriever found {len(evidence)} similar articles")

        except Exception as e:
            logger.warning(f"RAG evidence retrieval failed: {e}")

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
