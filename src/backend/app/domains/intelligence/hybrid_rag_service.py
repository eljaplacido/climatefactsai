"""
Hybrid RAG Service with Reciprocal Rank Fusion.

Combines three retrieval strategies — pgvector semantic search, PostgreSQL
full-text search, and knowledge graph traversal — then fuses results using
Reciprocal Rank Fusion (RRF) to produce a single ranked list of articles.
"""

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)


class HybridRAGService:
    """Multi-strategy retrieval with Reciprocal Rank Fusion."""

    def __init__(self, db: Database):
        self.db = db
        self._openai_api_key = os.getenv("OPENAI_API_KEY")

    async def retrieve(
        self,
        query: str,
        limit: int = 15,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Multi-strategy retrieval with RRF fusion.

        Runs semantic search, full-text search, and knowledge graph traversal
        in sequence, then combines the ranked lists using Reciprocal Rank Fusion.

        Args:
            query: The search query text.
            limit: Maximum number of fused results to return.
            filters: Optional dict with 'country_code' and/or 'content_category'.

        Returns:
            Fused list of article dicts sorted by RRF score.
        """
        filters = filters or {}

        semantic_results = await self._semantic_search(query, limit=30, filters=filters)
        fts_results = self._fulltext_search(query, limit=30, filters=filters)
        graph_results = self._graph_search(query, limit=20, filters=filters)

        fused = self._reciprocal_rank_fusion(
            [semantic_results, fts_results, graph_results],
            list_names=["semantic", "fts", "graph"],
            k=60,
        )

        return fused[:limit]

    # ------------------------------------------------------------------
    # Strategy 1: pgvector semantic search
    # ------------------------------------------------------------------

    async def _semantic_search(
        self,
        query: str,
        limit: int = 30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Cosine-distance search on articles.embedding_bge_m3 via pgvector."""
        embedding = await self._generate_query_embedding(query)
        if embedding is None:
            # INT-06: make the silent semantic->FTS degradation observable. Fires
            # when the bge-m3 embedder is unreachable (e.g. GX10 off from Cloud
            # Run); RRF then runs on FTS + graph only, with no vector recall.
            logger.warning(
                "Semantic search unavailable (no query embedding) — "
                "degrading to FTS+graph only for query=%r",
                (query or "")[:80],
            )
            return []

        where_clauses = [
            "a.embedding_bge_m3 IS NOT NULL",
        ]
        params: Dict[str, Any] = {
            "embedding": embedding,
            "limit": limit,
        }
        self._apply_filters(where_clauses, params, filters)
        where_sql = " AND ".join(where_clauses)

        rows = self.db.execute_query(
            f"""
            SELECT
                a.article_id,
                a.title,
                a.source_name,
                a.excerpt,
                a.overall_credibility,
                a.country_code,
                1 - (a.embedding_bge_m3 <=> :embedding::vector) AS similarity_score
            FROM articles a
            WHERE {where_sql}
            ORDER BY a.embedding_bge_m3 <=> :embedding::vector
            LIMIT :limit
            """,
            params,
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "excerpt": r.get("excerpt", ""),
                "credibility": r.get("overall_credibility", "UNKNOWN"),
                "similarity_score": round(float(r.get("similarity_score", 0)), 4),
                "retrieval_strategy": "semantic",
                "country_code": r.get("country_code"),
            }
            for r in (rows or [])
        ]

    # ------------------------------------------------------------------
    # Strategy 2: PostgreSQL full-text search
    # ------------------------------------------------------------------

    def _fulltext_search(
        self,
        query: str,
        limit: int = 30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Full-text search using PostgreSQL tsvector/tsquery with ts_rank.

        ML-01 (migration 072): uses articles.search_tsv — a STORED generated
        column rebuilt with a FIXED `to_tsvector('english', …)` config. The
        query side must use the SAME 'english' config or nothing matches
        (the pre-072 build stemmed per-row via clilens_lang_cfg(language_code),
        but language_code is mislabelled 'fi' on ~all rows, so Finnish-stemmed
        lexemes never matched the 'simple'/'english' queries → 0 hits). The
        corpus is English-dominant, so a fixed 'english' config is correct and
        decouples FTS from the language_code bug (see ML-20 for the attribution
        fix).
        """
        where_clauses = [
            "a.search_tsv @@ websearch_to_tsquery('english', :query)"
        ]
        params: Dict[str, Any] = {"query": query, "limit": limit}
        self._apply_filters(where_clauses, params, filters)
        where_sql = " AND ".join(where_clauses)

        rows = self.db.execute_query(
            f"""
            SELECT
                a.article_id,
                a.title,
                a.source_name,
                a.excerpt,
                a.overall_credibility,
                a.country_code,
                ts_rank(a.search_tsv, websearch_to_tsquery('english', :query)) AS similarity_score
            FROM articles a
            WHERE {where_sql}
            ORDER BY similarity_score DESC
            LIMIT :limit
            """,
            params,
        )
        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "excerpt": r.get("excerpt", ""),
                "credibility": r.get("overall_credibility", "UNKNOWN"),
                "similarity_score": round(float(r.get("similarity_score", 0)), 4),
                "retrieval_strategy": "fts",
                "country_code": r.get("country_code"),
            }
            for r in (rows or [])
        ]

    # ------------------------------------------------------------------
    # Strategy 3: Knowledge graph traversal
    # ------------------------------------------------------------------

    def _graph_search(
        self,
        query: str,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find articles via knowledge graph entity relationships.

        Extracts candidate entity names from the query, finds matching entities,
        then traverses entity_relationships up to 2 hops to collect connected
        articles via the article_entities junction table.
        """
        # Step 1: find seed entities matching query keywords
        query_words = [w.strip() for w in query.split() if len(w.strip()) > 2]
        if not query_words:
            return []

        # Build ILIKE conditions for each word
        like_conditions = []
        params: Dict[str, Any] = {"limit": limit}
        for idx, word in enumerate(query_words[:8]):
            like_conditions.append(f"e.entity_name ILIKE :word_{idx}")
            params[f"word_{idx}"] = f"%{word}%"

        if not like_conditions:
            return []

        like_sql = " OR ".join(like_conditions)

        seed_rows = self.db.execute_query(
            f"""
            SELECT e.entity_id
            FROM entities e
            WHERE {like_sql}
            ORDER BY e.article_count DESC
            LIMIT 10
            """,
            params,
        )
        if not seed_rows:
            return []

        seed_ids = [str(r["entity_id"]) for r in seed_rows]

        # Step 2: 2-hop recursive CTE traversal
        placeholders = ", ".join(f":seed_{i}" for i in range(len(seed_ids)))
        hop_params: Dict[str, Any] = {f"seed_{i}": sid for i, sid in enumerate(seed_ids)}
        hop_params["limit"] = limit

        filter_clauses = []
        self._apply_filters(filter_clauses, hop_params, filters, table_alias="a")
        extra_where = ""
        if filter_clauses:
            extra_where = "AND " + " AND ".join(filter_clauses)

        rows = self.db.execute_query(
            f"""
            WITH RECURSIVE graph_walk AS (
                -- Seed entities
                SELECT
                    entity_id AS reached_entity_id,
                    0 AS hops,
                    entity_id::text AS path
                FROM entities
                WHERE entity_id IN ({placeholders})

                UNION ALL

                -- Traverse relationships up to 2 hops
                SELECT
                    CASE
                        WHEN er.source_entity_id = gw.reached_entity_id THEN er.target_entity_id
                        ELSE er.source_entity_id
                    END,
                    gw.hops + 1,
                    gw.path || ' -> ' || er.relationship_type
                FROM entity_relationships er
                JOIN graph_walk gw
                  ON (er.source_entity_id = gw.reached_entity_id
                      OR er.target_entity_id = gw.reached_entity_id)
                WHERE gw.hops < 2
            ),
            connected_articles AS (
                SELECT DISTINCT
                    ae.article_id,
                    MIN(gw.hops) AS min_hops,
                    MAX(ae.salience) AS max_salience
                FROM graph_walk gw
                JOIN article_entities ae ON ae.entity_id = gw.reached_entity_id
                GROUP BY ae.article_id
            )
            SELECT
                a.article_id,
                a.title,
                a.source_name,
                a.excerpt,
                a.overall_credibility,
                a.country_code,
                ca.min_hops,
                ca.max_salience
            FROM connected_articles ca
            JOIN articles a ON a.article_id = ca.article_id
            WHERE 1=1 {extra_where}
            ORDER BY ca.min_hops ASC, ca.max_salience DESC
            LIMIT :limit
            """,
            hop_params,
        )

        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "excerpt": r.get("excerpt", ""),
                "credibility": r.get("overall_credibility", "UNKNOWN"),
                "similarity_score": round(
                    max(0.0, 1.0 - float(r.get("min_hops", 2)) * 0.3)
                    * float(r.get("max_salience", 0.5)),
                    4,
                ),
                "retrieval_strategy": "graph",
                "country_code": r.get("country_code"),
            }
            for r in (rows or [])
        ]

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion
    # ------------------------------------------------------------------

    def _reciprocal_rank_fusion(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        list_names: Optional[List[str]] = None,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Combine results using Reciprocal Rank Fusion.

        For each document, score = sum( 1 / (k + rank_i) ) across all lists.
        """
        if list_names is None:
            list_names = [f"list_{i}" for i in range(len(ranked_lists))]

        scores: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"score": 0.0, "article": None, "sources": []}
        )

        for list_name, ranked_list in zip(list_names, ranked_lists):
            for rank, item in enumerate(ranked_list):
                doc_id = item["article_id"]
                scores[doc_id]["score"] += 1.0 / (k + rank + 1)
                # Keep the richer article record
                if scores[doc_id]["article"] is None:
                    scores[doc_id]["article"] = item
                scores[doc_id]["sources"].append(list_name)

        results = []
        for doc_id, info in scores.items():
            article = dict(info["article"])
            article["rrf_score"] = round(info["score"], 6)
            article["retrieval_sources"] = info["sources"]
            results.append(article)

        results.sort(key=lambda x: x["rrf_score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _generate_query_embedding(self, text: str) -> Optional[str]:
        """Generate a bge-m3 query-embedding vector string for pgvector.

        Uses the live bge-m3 column (2026-06-11 audit, semantic split-brain) —
        the old ada-002 embed matched the empty `embedding` column. Returns
        None when the GX10 endpoint is unreachable (e.g. from Cloud Run), so the
        caller degrades to FTS rather than vector search.
        """
        try:
            from app.domains.content.embedding_service import EmbeddingService
            embedding = await EmbeddingService(self.db).generate_bge_m3_embedding(text[:8000])
            if not embedding:
                return None
            return "[" + ",".join(str(v) for v in embedding) + "]"
        except Exception as e:
            logger.warning(f"bge-m3 query embedding generation failed: {e}")
            return None

    @staticmethod
    def _apply_filters(
        where_clauses: List[str],
        params: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        table_alias: str = "a",
    ) -> None:
        """Append WHERE clauses for optional country_code / content_category filters."""
        # Always exclude synthetic seeds + off-topic articles from RAG
        # retrieval — they must never surface as chat citations / grounding
        # context (review fix; mirrors the listing-surface is_off_topic filter).
        where_clauses.append(f"{table_alias}.is_synthetic = FALSE")
        where_clauses.append(f"{table_alias}.is_off_topic = FALSE")
        if not filters:
            return
        if filters.get("country_code"):
            where_clauses.append(f"{table_alias}.country_code = :filter_country")
            params["filter_country"] = filters["country_code"].upper()
        if filters.get("content_category"):
            where_clauses.append(f"{table_alias}.content_category = :filter_category")
            params["filter_category"] = filters["content_category"].lower()
