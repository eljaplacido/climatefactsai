"""
RAG Evidence Retriever — queries the article corpus for similar verified claims.

Uses HybridRAGService (pgvector semantic + full-text + knowledge graph) with
Reciprocal Rank Fusion to find previously verified articles with similar claims,
providing internal cross-reference evidence.
"""

from typing import Optional

from app.core.logging import get_logger
from app.core.database import get_db
from .schemas import Evidence
from shared.credibility_thresholds import HIGH, MEDIUM, level_for

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

                # INT-09: a similar article EXISTING is "related coverage", not
                # claim-level corroboration — don't map article credibility to
                # supports/contradicts. supports_claim stays None (neutral);
                # a claim-vs-claim comparison is the tracked follow-up.
                # Label from the ACTUAL contributing layers (semantic/fts/graph),
                # never a hardcoded "hybrid" — semantic only appears here when the
                # vector layer genuinely contributed (ML-02 honesty).
                strategy_label = ", ".join(retrieval_sources) if retrieval_sources else "unknown"

                evidence.append(Evidence(
                    source=f"Climatefacts.ai Corpus ({source_name})",
                    source_url="",
                    source_reliability="high" if credibility == "HIGH" else "medium",
                    content_excerpt=(
                        f"Related coverage: \"{title}\". "
                        f"Article credibility: {credibility}. "
                        f"Retrieval: {strategy_label}. "
                        f"Score: {similarity:.4f}"
                    ),
                    relevance_score=round(min(similarity * 2.0, 0.95), 2),
                    supports_claim=None,
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
                "SELECT COUNT(*) as cnt FROM articles WHERE embedding_bge_m3 IS NOT NULL"
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
                    1 - (a.embedding_bge_m3 <=> :embedding::vector) as similarity
                FROM articles a
                WHERE a.embedding_bge_m3 IS NOT NULL
                  AND a.claims_status = 'completed'
                  AND 1 - (a.embedding_bge_m3 <=> :embedding::vector) > :threshold
                ORDER BY a.embedding_bge_m3 <=> :embedding::vector
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

                # INT-09: related coverage, not claim-level corroboration.
                evidence.append(Evidence(
                    source=f"Climatefacts.ai Corpus ({row.get('source_name', 'Unknown')})",
                    source_url=row.get("url", ""),
                    source_reliability=level_for(reliability).lower() if reliability else "medium",
                    content_excerpt=(
                        f"Related coverage: \"{row.get('title', '')}\". "
                        f"Credibility: {credibility}, Reliability: {reliability}/100, "
                        f"Claims: {row.get('verified_claims_count', 0)}/{row.get('claims_count', 0)} verified. "
                        f"Similarity: {similarity:.2f}"
                    ),
                    relevance_score=round(similarity * 0.9, 2),
                    supports_claim=None,
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
            # bge-m3 is the live column (2026-06-11 audit). The old import of a
            # module-level generate_embedding never existed (ImportError every
            # call), so this path was dead. Use the EmbeddingService bge-m3
            # method; None when the GX10 endpoint is unreachable.
            from app.domains.content.embedding_service import EmbeddingService
            embedding = await EmbeddingService(get_db()).generate_bge_m3_embedding(text)
            if embedding:
                return f"[{','.join(str(v) for v in embedding)}]"
        except Exception as e:
            logger.warning(f"Claim embedding generation failed: {e}")

        return None
