"""
Knowledge Graph Retriever.

Finds articles connected to query entities via the knowledge graph
(entities, entity_relationships, article_entities) using recursive CTE
traversal up to N hops. Returns articles with path explanations and scores.
"""

from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)


class GraphRetriever:
    """Find articles connected to query entities via knowledge graph traversal."""

    def __init__(self, db: Database):
        self.db = db

    def retrieve(
        self,
        query: str,
        max_hops: int = 2,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find articles connected to query entities via knowledge graph.

        1. Match query terms against entity names (fuzzy / ILIKE).
        2. Traverse entity_relationships recursively up to *max_hops*.
        3. Collect articles from article_entities along traversal paths.
        4. Score by path length (shorter = better), relationship strength,
           and entity salience.

        Args:
            query: Free-text query.
            max_hops: Maximum relationship hops (default 2).
            limit: Max articles to return.

        Returns:
            List of article dicts with path explanation and score.
        """
        seed_entities = self._find_matching_entities(query)
        if not seed_entities:
            return []

        seed_ids = [str(e["entity_id"]) for e in seed_entities]
        seed_names = {str(e["entity_id"]): e["entity_name"] for e in seed_entities}

        articles = self._traverse_and_collect(seed_ids, max_hops, limit)

        # Enrich with path explanations
        for article in articles:
            article["path_explanation"] = self._build_path_explanation(
                article, seed_names
            )

        return articles

    # ------------------------------------------------------------------
    # Entity matching
    # ------------------------------------------------------------------

    def _find_matching_entities(self, query: str) -> List[Dict[str, Any]]:
        """Find entities whose names match query keywords (ILIKE)."""
        words = [w.strip() for w in query.split() if len(w.strip()) > 2]
        if not words:
            return []

        conditions = []
        params: Dict[str, Any] = {}
        for idx, word in enumerate(words[:10]):
            conditions.append(f"e.entity_name ILIKE :w_{idx}")
            params[f"w_{idx}"] = f"%{word}%"

        where_sql = " OR ".join(conditions)

        rows = self.db.execute_query(
            f"""
            SELECT e.entity_id, e.entity_name, e.entity_type, e.article_count
            FROM entities e
            WHERE {where_sql}
            ORDER BY e.article_count DESC
            LIMIT 15
            """,
            params,
        )
        return rows or []

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def _traverse_and_collect(
        self,
        seed_ids: List[str],
        max_hops: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Recursive CTE traversal from seed entities, collecting articles."""
        if not seed_ids:
            return []

        placeholders = ", ".join(f":seed_{i}" for i in range(len(seed_ids)))
        params: Dict[str, Any] = {f"seed_{i}": sid for i, sid in enumerate(seed_ids)}
        params["max_hops"] = max_hops
        params["limit"] = limit

        rows = self.db.execute_query(
            f"""
            WITH RECURSIVE graph_walk AS (
                SELECT
                    entity_id AS reached_entity_id,
                    0 AS hops,
                    entity_name AS path_text,
                    entity_id::text AS visited
                FROM entities
                WHERE entity_id IN ({placeholders})

                UNION ALL

                SELECT
                    CASE
                        WHEN er.source_entity_id = gw.reached_entity_id
                            THEN er.target_entity_id
                        ELSE er.source_entity_id
                    END,
                    gw.hops + 1,
                    gw.path_text || ' -> ' || er.relationship_type || ' -> ' || e_next.entity_name,
                    gw.visited || ',' || CASE
                        WHEN er.source_entity_id = gw.reached_entity_id
                            THEN er.target_entity_id::text
                        ELSE er.source_entity_id::text
                    END
                FROM entity_relationships er
                JOIN graph_walk gw
                  ON (er.source_entity_id = gw.reached_entity_id
                      OR er.target_entity_id = gw.reached_entity_id)
                JOIN entities e_next
                  ON e_next.entity_id = CASE
                      WHEN er.source_entity_id = gw.reached_entity_id
                          THEN er.target_entity_id
                      ELSE er.source_entity_id
                  END
                WHERE gw.hops < :max_hops
                  AND gw.visited NOT LIKE '%%' || CASE
                      WHEN er.source_entity_id = gw.reached_entity_id
                          THEN er.target_entity_id::text
                      ELSE er.source_entity_id::text
                  END || '%%'
            ),
            scored_articles AS (
                SELECT DISTINCT ON (ae.article_id)
                    ae.article_id,
                    gw.hops AS min_hops,
                    gw.path_text,
                    ae.salience,
                    COALESCE(er_agg.avg_strength, 0.5) AS avg_strength
                FROM graph_walk gw
                JOIN article_entities ae ON ae.entity_id = gw.reached_entity_id
                LEFT JOIN LATERAL (
                    SELECT AVG(er2.strength) AS avg_strength
                    FROM entity_relationships er2
                    WHERE er2.source_entity_id = gw.reached_entity_id
                       OR er2.target_entity_id = gw.reached_entity_id
                ) er_agg ON true
                ORDER BY ae.article_id, gw.hops ASC
            )
            SELECT
                a.article_id,
                a.title,
                a.source_name,
                a.excerpt,
                a.overall_credibility,
                a.country_code,
                sa.min_hops,
                sa.path_text,
                sa.salience,
                sa.avg_strength
            FROM scored_articles sa
            JOIN articles a ON a.article_id = sa.article_id
            ORDER BY
                sa.min_hops ASC,
                (sa.salience * sa.avg_strength) DESC
            LIMIT :limit
            """,
            params,
        )

        results = []
        for r in (rows or []):
            hops = int(r.get("min_hops", 2))
            salience = float(r.get("salience", 0.5))
            strength = float(r.get("avg_strength", 0.5))

            # Score: shorter paths + higher salience + stronger relationships
            score = max(0.0, 1.0 - hops * 0.3) * salience * strength

            results.append(
                {
                    "article_id": str(r["article_id"]),
                    "title": r.get("title", ""),
                    "source_name": r.get("source_name", ""),
                    "excerpt": r.get("excerpt", ""),
                    "credibility": r.get("overall_credibility", "UNKNOWN"),
                    "country_code": r.get("country_code"),
                    "graph_score": round(score, 4),
                    "hops": hops,
                    "path_text": r.get("path_text", ""),
                    "salience": salience,
                    "avg_strength": strength,
                }
            )

        return results

    # ------------------------------------------------------------------
    # Path explanation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_path_explanation(
        article: Dict[str, Any],
        seed_names: Dict[str, str],
    ) -> str:
        """Build a human-readable path explanation for a graph result."""
        path = article.get("path_text", "")
        if path:
            return f"Connected via: {path}"
        return "Directly connected entity"
