"""
Embedding service for article similarity using pgvector.

Generates embeddings via OpenAI text-embedding-ada-002 and finds
similar articles using pgvector cosine distance operator.
"""

import os
from typing import List, Optional
from uuid import UUID

from app.core.database import Database
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generate and query article embeddings for similarity search."""

    EMBEDDING_MODEL = "text-embedding-ada-002"
    EMBEDDING_DIM = 1536

    # seq-6: free local embeddings on the GX10. bge-m3 is multilingual and
    # 1024-dim; generated via the GX10's OpenAI-compatible Ollama endpoint
    # (localhost:11434/v1 inside the embedding_worker — no OpenAI spend).
    BGE_M3_MODEL = "bge-m3"
    BGE_M3_DIM = 1024

    def __init__(self, db: Database):
        self.db = db
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text using OpenAI."""
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set — cannot generate embeddings")
            return None

        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)

            # Truncate to ~8000 tokens (~32000 chars)
            truncated = text[:32000]

            response = client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=truncated,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    async def generate_bge_m3_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a 1024-dim bge-m3 embedding via the GX10's OpenAI-compatible
        Ollama endpoint (CLILENS_LOCAL_GX10_BASE_URL, default localhost:11434/v1).

        Designed to run INSIDE the GX10 embedding_worker, where the base URL is
        localhost — free, no OpenAI spend. Returns None on any failure so the
        caller can skip the article and retry later.
        """
        base = os.getenv("CLILENS_LOCAL_GX10_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        api_key = os.getenv("CLILENS_LOCAL_GX10_API_KEY", "ollama")
        model = os.getenv("CLILENS_EMBEDDING_MODEL", self.BGE_M3_MODEL)
        truncated = (text or "")[:32000]
        if not truncated.strip():
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{base}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "input": truncated},
                )
                resp.raise_for_status()
                emb = resp.json()["data"][0]["embedding"]
            if len(emb) != self.BGE_M3_DIM:
                logger.warning(
                    "bge-m3 embedding dim %s != expected %s (model=%s)",
                    len(emb), self.BGE_M3_DIM, model,
                )
                return None
            return emb
        except Exception as e:
            logger.error(f"bge-m3 embedding generation failed: {e}")
            return None

    async def store_bge_m3_embedding(self, article_id: str, embedding: List[float]) -> bool:
        """Store an article's bge-m3 embedding in the parallel column."""
        try:
            vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
            self.db.execute_update(
                """UPDATE articles
                   SET embedding_bge_m3 = CAST(:embedding AS vector)
                   WHERE article_id = :article_id""",
                {"embedding": vector_str, "article_id": article_id},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store bge-m3 embedding for {article_id}: {e}")
            return False

    async def populate_bge_m3_embedding(self, article_id: str) -> bool:
        """Generate + store the bge-m3 embedding for one article (if missing)."""
        rows = self.db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') AS text
               FROM articles
               WHERE article_id = :id AND embedding_bge_m3 IS NULL""",
            {"id": article_id},
        )
        if not rows:
            return False
        row = rows[0]
        text = f"{row.get('title', '')}. {row.get('excerpt', '')} {row.get('text', '')}".strip()
        embedding = await self.generate_bge_m3_embedding(text)
        if not embedding:
            return False
        return await self.store_bge_m3_embedding(article_id, embedding)

    async def batch_populate_bge_m3(self, limit: int = 25) -> dict:
        """Embed the next `limit` non-synthetic articles missing a bge-m3 vector.

        Returns {total_found, processed, failed} so the GX10 worker can decide
        whether to sleep (corpus caught up) or run the next batch immediately.
        """
        rows = self.db.execute_query(
            """SELECT article_id::text AS id
               FROM articles
               WHERE embedding_bge_m3 IS NULL
                 AND is_synthetic = FALSE
                 AND COALESCE(NULLIF(extracted_text, ''), excerpt, title) IS NOT NULL
               ORDER BY created_at DESC NULLS LAST
               LIMIT :n""",
            {"n": limit},
        ) or []
        processed = failed = 0
        for r in rows:
            if await self.populate_bge_m3_embedding(r["id"]):
                processed += 1
            else:
                failed += 1
        return {"total_found": len(rows), "processed": processed, "failed": failed}

    async def store_embedding(self, article_id: str, embedding: List[float]) -> bool:
        """Store an article's embedding vector in the database."""
        try:
            vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
            self.db.execute_update(
                """UPDATE articles
                   SET embedding = CAST(:embedding AS vector)
                   WHERE article_id = :article_id""",
                {"embedding": vector_str, "article_id": article_id},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding for {article_id}: {e}")
            return False

    async def populate_embedding(self, article_id: str) -> bool:
        """Generate and store embedding for an article."""
        rows = self.db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') as text
               FROM articles WHERE article_id = :id AND embedding IS NULL""",
            {"id": article_id},
        )
        if not rows:
            return False

        row = rows[0]
        text = f"{row.get('title', '')}. {row.get('excerpt', '')} {row.get('text', '')}"
        embedding = await self.generate_embedding(text.strip())
        if not embedding:
            return False

        return await self.store_embedding(article_id, embedding)

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        """Search articles by semantic similarity to a query string."""
        embedding = await self.generate_embedding(query)
        if not embedding:
            return []

        where_clauses = ["a.embedding IS NOT NULL"]
        params: dict = {"limit": limit}

        if filters:
            if filters.get("country"):
                where_clauses.append("a.country_code = :country")
                params["country"] = filters["country"]
            if filters.get("category"):
                where_clauses.append("a.content_category = :category")
                params["category"] = filters["category"]

        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        params["embedding"] = vector_str
        where_sql = " AND ".join(where_clauses)

        results = self.db.execute_query(
            f"""SELECT
                  a.article_id, a.title, a.source_name,
                  a.published_date, a.overall_credibility,
                  a.content_category, a.country_code,
                  1 - (a.embedding <=> CAST(:embedding AS vector)) AS similarity_score
                FROM articles a
                WHERE {where_sql}
                ORDER BY a.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit""",
            params,
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "similarity_score": round(float(r.get("similarity_score", 0)), 3),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "overall_credibility": r.get("overall_credibility", "UNKNOWN"),
                "content_category": r.get("content_category"),
                "country_code": r.get("country_code"),
            }
            for r in (results or [])
        ]

    async def cross_reference_articles(self, article_id: str, limit: int = 5) -> List[dict]:
        """Find articles with similar claims (claim-level cross-referencing)."""
        claim_rows = self.db.execute_query(
            "SELECT claim_text FROM claims WHERE article_id = :id LIMIT 10",
            {"id": article_id},
        )
        if not claim_rows:
            return await self.find_similar(article_id, limit=limit)

        combined_text = " ".join(r.get("claim_text", "") for r in claim_rows)[:4000]
        embedding = await self.generate_embedding(combined_text)
        if not embedding:
            return []

        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        results = self.db.execute_query(
            """SELECT
                 a.article_id, a.title, a.source_name,
                 a.published_date, a.overall_credibility,
                 1 - (a.embedding <=> CAST(:embedding AS vector)) AS similarity_score
               FROM articles a
               WHERE a.article_id != :id
                 AND a.embedding IS NOT NULL
                 AND 1 - (a.embedding <=> CAST(:embedding AS vector)) >= 0.35
               ORDER BY a.embedding <=> CAST(:embedding AS vector)
               LIMIT :limit""",
            {"id": article_id, "embedding": vector_str, "limit": limit},
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "similarity_score": round(float(r.get("similarity_score", 0)), 3),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "overall_credibility": r.get("overall_credibility", "UNKNOWN"),
                "match_type": "claim_cross_reference",
            }
            for r in (results or [])
        ]

    async def find_related_data_sources(self, article_id: str) -> List[dict]:
        """Find related data source articles for cross-referencing."""
        rows = self.db.execute_query(
            "SELECT title, excerpt FROM articles WHERE article_id = :id",
            {"id": article_id},
        )
        if not rows:
            return []

        row = rows[0]
        query_text = f"{row.get('title', '')} {row.get('excerpt', '')}"
        return await self.semantic_search(
            query_text,
            limit=5,
            filters={"category": "climate_science"},
        )

    async def find_similar(
        self,
        article_id: str,
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> List[dict]:
        """Find similar articles using pgvector cosine distance."""
        # First check if the article has an embedding
        rows = self.db.execute_query(
            "SELECT embedding FROM articles WHERE article_id = :id AND embedding IS NOT NULL",
            {"id": article_id},
        )
        if not rows:
            # Try to generate it first
            success = await self.populate_embedding(article_id)
            if not success:
                return []

        results = self.db.execute_query(
            """SELECT
                 a.article_id,
                 a.title,
                 a.source_name,
                 a.published_date,
                 a.overall_credibility,
                 1 - (a.embedding <=> target.embedding) AS similarity_score
               FROM articles a
               CROSS JOIN (
                 SELECT embedding FROM articles WHERE article_id = :id
               ) target
               WHERE a.article_id != :id
                 AND a.embedding IS NOT NULL
                 AND 1 - (a.embedding <=> target.embedding) >= :min_sim
               ORDER BY a.embedding <=> target.embedding
               LIMIT :limit""",
            {"id": article_id, "limit": limit, "min_sim": min_similarity},
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "similarity_score": round(float(r.get("similarity_score", 0)), 3),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "overall_credibility": r.get("overall_credibility", "UNKNOWN"),
            }
            for r in results
        ]
