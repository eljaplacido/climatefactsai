"""
Semantic Query Service — Unified search combining full-text + vector similarity.

Provides faceted results grouped by category, country, and credibility.
Cross-references claims from different articles sharing similar topics.
"""

from typing import Any, Dict, List, Optional

from app.core.database import Database
from app.core.logging import get_logger
from app.domains.content.embedding_service import EmbeddingService

logger = get_logger(__name__)


class SemanticQueryService:
    """Combines full-text search with pgvector semantic similarity."""

    def __init__(self, db: Database):
        self.db = db
        self.embedding_service = EmbeddingService(db)

    async def unified_search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        country: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Combined full-text + semantic search with faceted results.

        Returns articles ranked by a blended score of text relevance
        and embedding cosine similarity.
        """
        results: List[Dict] = []

        # Phase 1: Full-text search
        fts_results = self._full_text_search(
            query, country=country, category=category,
            date_from=date_from, date_to=date_to, limit=limit,
        )

        # Phase 2: Semantic search (if embeddings available)
        sem_results = await self._semantic_search(
            query, country=country, category=category, limit=limit,
        )

        # Merge results: prefer semantic matches but boost FTS rank
        seen_ids = set()
        for item in sem_results:
            aid = item["article_id"]
            if aid not in seen_ids:
                item["match_type"] = "semantic"
                results.append(item)
                seen_ids.add(aid)

        for item in fts_results:
            aid = item["article_id"]
            if aid not in seen_ids:
                item["match_type"] = "text"
                results.append(item)
                seen_ids.add(aid)

        # Build facets
        facets = self._build_facets(results)

        return {
            "query": query,
            "total": len(results),
            "results": results[:limit],
            "facets": facets,
        }

    def _full_text_search(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """PostgreSQL full-text search on title + excerpt + extracted_text."""
        filters = []
        params: Dict[str, Any] = {"query": query, "limit": limit}

        if country:
            filters.append("a.country_code = :country")
            params["country"] = country.upper()
        if category:
            filters.append("a.content_category = :category")
            params["category"] = category
        if date_from:
            filters.append("a.created_at::date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            filters.append("a.created_at::date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(filters) if filters else "TRUE"

        sql = f"""
            SELECT
                a.article_id, a.title, a.source_name, a.country_code,
                a.content_category, a.overall_credibility, a.reliability_score,
                a.published_date, a.excerpt,
                ts_rank(
                    to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.excerpt, '')),
                    plainto_tsquery('english', :query)
                ) AS text_rank
            FROM articles a
            WHERE to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.excerpt, ''))
                  @@ plainto_tsquery('english', :query)
              AND {where_clause}
            ORDER BY text_rank DESC
            LIMIT :limit
        """

        try:
            rows = self.db.execute_query(sql, params)
            return [
                {
                    "article_id": str(r["article_id"]),
                    "title": r.get("title", ""),
                    "source_name": r.get("source_name", ""),
                    "country_code": r.get("country_code"),
                    "content_category": r.get("content_category"),
                    "overall_credibility": r.get("overall_credibility"),
                    "reliability_score": r.get("reliability_score"),
                    "published_date": str(r["published_date"]) if r.get("published_date") else None,
                    "excerpt": r.get("excerpt"),
                    "relevance_score": round(float(r.get("text_rank", 0)), 4),
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"Full-text search failed: {e}")
            return []

    async def _semantic_search(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """pgvector cosine similarity search on the live bge-m3 column."""
        embedding = await self.embedding_service.generate_bge_m3_embedding(query)
        if not embedding:
            return []

        filters = []
        params: Dict[str, Any] = {"limit": limit}

        if country:
            filters.append("a.country_code = :country")
            params["country"] = country.upper()
        if category:
            filters.append("a.content_category = :category")
            params["category"] = category

        where_clause = " AND ".join(filters) if filters else "TRUE"
        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        params["embedding"] = vector_str

        sql = f"""
            SELECT
                a.article_id, a.title, a.source_name, a.country_code,
                a.content_category, a.overall_credibility, a.reliability_score,
                a.published_date, a.excerpt,
                1 - (a.embedding_bge_m3 <=> :embedding::vector) AS similarity
            FROM articles a
            WHERE a.embedding_bge_m3 IS NOT NULL
              AND {where_clause}
            ORDER BY a.embedding_bge_m3 <=> :embedding::vector
            LIMIT :limit
        """

        try:
            rows = self.db.execute_query(sql, params)
            return [
                {
                    "article_id": str(r["article_id"]),
                    "title": r.get("title", ""),
                    "source_name": r.get("source_name", ""),
                    "country_code": r.get("country_code"),
                    "content_category": r.get("content_category"),
                    "overall_credibility": r.get("overall_credibility"),
                    "reliability_score": r.get("reliability_score"),
                    "published_date": str(r["published_date"]) if r.get("published_date") else None,
                    "excerpt": r.get("excerpt"),
                    "relevance_score": round(float(r.get("similarity", 0)), 4),
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def cross_reference_articles(self, article_id: str, limit: int = 10) -> List[Dict]:
        """
        Find articles with overlapping claims at the claim level.

        Uses claim text similarity to discover cross-references,
        providing a richer view than article-level similarity alone.
        """
        rows = self.db.execute_query(
            """
            SELECT c.claim_text
            FROM claims c
            WHERE c.article_id = :article_id
            LIMIT 10
            """,
            {"article_id": article_id},
        )
        if not rows:
            return []

        # Use the combined claim text as a search query
        combined = " ".join(r.get("claim_text", "") for r in rows)[:2000]
        embedding = await self.embedding_service.generate_bge_m3_embedding(combined)
        if not embedding:
            return []

        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        results = self.db.execute_query(
            """
            SELECT
                a.article_id, a.title, a.source_name,
                a.overall_credibility, a.published_date,
                1 - (a.embedding_bge_m3 <=> :embedding::vector) AS similarity
            FROM articles a
            WHERE a.article_id != :article_id
              AND a.embedding_bge_m3 IS NOT NULL
              AND 1 - (a.embedding_bge_m3 <=> :embedding::vector) >= 0.4
            ORDER BY a.embedding_bge_m3 <=> :embedding::vector
            LIMIT :limit
            """,
            {"article_id": article_id, "embedding": vector_str, "limit": limit},
        )

        return [
            {
                "article_id": str(r["article_id"]),
                "title": r.get("title", ""),
                "source_name": r.get("source_name", ""),
                "overall_credibility": r.get("overall_credibility"),
                "published_date": str(r["published_date"]) if r.get("published_date") else None,
                "similarity_score": round(float(r.get("similarity", 0)), 3),
                "match_type": "claim_cross_reference",
            }
            for r in (results or [])
        ]

    def _build_facets(self, results: List[Dict]) -> Dict[str, Any]:
        """Build faceted aggregations from result set."""
        categories: Dict[str, int] = {}
        countries: Dict[str, int] = {}
        credibility: Dict[str, int] = {}

        for r in results:
            cat = r.get("content_category")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
            cc = r.get("country_code")
            if cc:
                countries[cc] = countries.get(cc, 0) + 1
            cred = r.get("overall_credibility")
            if cred:
                credibility[cred] = credibility.get(cred, 0) + 1

        return {
            "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
            "countries": dict(sorted(countries.items(), key=lambda x: -x[1])),
            "credibility": dict(sorted(credibility.items(), key=lambda x: -x[1])),
        }
