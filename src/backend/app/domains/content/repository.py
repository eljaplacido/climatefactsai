"""
Content Domain Repository

Data access layer for articles, claims, and fact-checks.
Encapsulates all database queries for the content domain.
"""

import json
from typing import Optional, Dict, Any
from uuid import UUID

from app.core.database import Database
from app.core.logging import get_logger
from .models import Article, ArticleDetail, ClaimWithFactCheck, FactCheck, Evidence, TagStat

logger = get_logger(__name__)


class ArticleRepository:
    """
    Repository for article data access.
    
    Handles all database operations for articles, claims, and fact-checks.
    """
    
    def __init__(self, db: Database):
        self.db = db
        self._trust_queries_supported = True
    
    def get_by_id(self, article_id: UUID) -> Optional[Article]:
        """
        Get article by ID.
        
        Args:
            article_id: Article UUID
        
        Returns:
            Article model or None if not found
        """
        params = {"article_id": str(article_id)}
        trust_query = f"""
            SELECT
                {self._article_select_columns()}
            FROM articles a
            LEFT JOIN publishers p ON a.publisher_id = p.id
            WHERE a.article_id = :article_id
        """
        legacy_query = """
            SELECT
                article_id, title, url, source_name, author, published_date,
                excerpt, reliability_score, overall_credibility,
                source_credibility_score, country_code, language_code,
                tags, claims_count as claim_count,
                verified_claims_count as verified_claim_count,
                claims_status, claims_error_message, claims_processed_at,
                created_at, updated_at
            FROM articles
            WHERE article_id = :article_id
        """
        results = self._execute_trust_query(trust_query, legacy_query, params)
        
        if not results:
            return None
        
        return self._row_to_article(results[0])
    
    def get_detail(self, article_id: UUID) -> Optional[ArticleDetail]:
        """
        Get article with full content, claims, and fact-checks.
        
        Args:
            article_id: Article UUID
        
        Returns:
            ArticleDetail with claims or None if not found
        """
        params = {"article_id": str(article_id)}
        trust_query = f"""
            SELECT
                {self._article_select_columns(include_detail=True)}
            FROM articles a
            LEFT JOIN publishers p ON a.publisher_id = p.id
            WHERE a.article_id = :article_id
        """
        legacy_query = """
            SELECT
                article_id, title, url, source_name, author, published_date,
                COALESCE(extracted_text, '') as extracted_text, excerpt, reliability_score, overall_credibility,
                source_credibility_score, country_code, language_code,
                tags, claims_count as claim_count,
                verified_claims_count as verified_claim_count,
                claims_status, claims_error_message, claims_processed_at,
                decomposed_confidence, insight_summary,
                analysis_article_generated_at,
                content_category, executive_brief,
                enriched_excerpt, climate_context_summary, enrichment_metadata,
                created_at, updated_at
            FROM articles
            WHERE article_id = :article_id
        """
        article_results = self._execute_trust_query(trust_query, legacy_query, params)
        
        if not article_results:
            return None
        
        article_result = article_results[0]
        
        # Get claims with fact-checks (match actual schema columns)
        claims_results = self.db.execute_query(
            """
            SELECT
                c.claim_id,
                c.article_id,
                c.claim_text,
                c.claim_type,
                c.claim_context,
                c.claim_category,
                c.created_at as extracted_at,
                fc.fact_check_id,
                fc.verification_status,
                fc.confidence_score,
                fc.justification,
                fc.evidence,
                fc.evidence_chain,
                fc.decomposed_confidence,
                fc.verified_at
            FROM claims c
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE c.article_id = :article_id
            ORDER BY c.created_at ASC
            """,
            {"article_id": str(article_id)}
        )
        
        # Build claims list with fact-checks
        claims = []
        for row in claims_results:
            claim_data = {
                "claim_id": row["claim_id"],
                "article_id": row["article_id"],
                "claim_text": row["claim_text"],
                "claim_type": row["claim_type"],
                "claim_context": row["claim_context"],
                "claim_category": row.get("claim_category"),
                "importance_score": None,  # Not in schema
                "extracted_at": row["extracted_at"],
                "extraction_model": None,  # Not in schema
            }
            
            # Add fact-check if exists
            fact_check = None
            if row.get("fact_check_id"):
                # Parse evidence JSON
                evidence_list = []
                evidence_payload = self._parse_json_field(row.get("evidence"))
                if isinstance(evidence_payload, list):
                    for item in evidence_payload:
                        if isinstance(item, dict):
                            evidence_list.append(Evidence(**item))
                        else:
                            evidence_list.append(item)

                # Parse decomposed_confidence and evidence_chain JSONB
                dc_data = self._parse_json_field(row.get("decomposed_confidence"))
                ec_data = self._parse_json_field(row.get("evidence_chain"))

                fact_check = FactCheck(
                    fact_check_id=row["fact_check_id"],
                    claim_id=row["claim_id"],
                    verdict=row["verification_status"],  # Match actual column name
                    verification_status=row["verification_status"],  # Also set for frontend
                    confidence_score=float(row["confidence_score"]),
                    justification=row["justification"],
                    evidence=evidence_list,
                    sources=[],  # sources column doesn't exist
                    verified_at=row["verified_at"],
                    verified_date=row["verified_at"],  # Also set for frontend
                    verification_model=None,  # Not in schema
                    verification_method=None,  # Not in schema
                    decomposed_confidence=dc_data,
                    evidence_chain=ec_data if isinstance(ec_data, list) else [],
                )
            
            claims.append(ClaimWithFactCheck(**claim_data, fact_check=fact_check))
        
        return self._row_to_article_detail(article_result, claims=claims)
    
    def list_articles(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        credibility: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
        include_non_climate: bool = False
    ) -> list[Article]:
        """List articles with optional filters."""
        source_credibility = {
            'NASA': 95, 'NOAA': 95, 'IPCC': 98,
            'MIT Technology Review': 85,
            'International Energy Agency': 90,
            'UNFCCC': 92,
            'European Sting': 75,
            'Nordic Council of Ministers': 80,
            'Finnish Government': 80,
            'Finnish Industries EK': 70,
            'Helsingin Sanomat': 75,
            'Uutiset - Helsingin Sanomat': 75,
            'Perplexity Research': 50,
            'Reccessary': 60
        }

        # Bound params for every user-controlled filter — no f-string
        # interpolation (closes the SQL-injection surface the single-quote
        # escape only half-covered). limit/offset are always bound.
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        where_conditions = ["a.is_synthetic IS NOT TRUE"]

        # Relevance gate: the off-topic classifier (mig 056/057) is the source
        # of truth for "is this a climate article", NOT a hardcoded tag
        # whitelist. The old `a.tags && ARRAY[...climate_tags...]` filter
        # silently returned [] for the entire corpus (articles ingested without
        # those exact tag strings / NULL tags), which made /api/v2/articles dead
        # in prod despite 3k+ articles — matches the legacy /api/articles gate.
        if not include_non_climate:
            where_conditions.append("a.is_off_topic IS NOT TRUE")

        if query:
            # title/excerpt are the real columns; the old headline/summary_text
            # refs do not exist in prod and 500'd every ?q= search.
            where_conditions.append(
                "a.search_tsv "
                "@@ websearch_to_tsquery('simple', :q_text)"
            )
            params["q_text"] = query

        if country:
            where_conditions.append("a.country_code = :country")
            params["country"] = country

        if credibility:
            where_conditions.append("a.overall_credibility = :credibility")
            params["credibility"] = credibility

        if tags:
            placeholders = []
            for i, t in enumerate(tags):
                key = f"tag{i}"
                placeholders.append(f":{key}")
                params[key] = t
            where_conditions.append(f"a.tags && ARRAY[{','.join(placeholders)}]::text[]")

        where_clause = " AND ".join(where_conditions)

        source_cases = []
        for source, score in source_credibility.items():
            safe_source = source.replace("'", "''")
            source_cases.append(f"WHEN a.source_name = '{safe_source}' THEN {score}")
        source_credibility_sql = "CASE " + " ".join(source_cases) + " ELSE 50 END"

        trust_query = f"""
            SELECT
                {self._article_select_columns()},
                (
                    (COALESCE(a.reliability_score, {source_credibility_sql}) * 0.6) +
                    (100 * EXP(-EXTRACT(EPOCH FROM (NOW() - COALESCE(a.published_date, a.created_at))) / (30 * 86400)) * 0.3) +
                    (LEAST(a.verified_claims_count * 2, 100) * 0.1)
                ) as relevance_score
            FROM articles a
            LEFT JOIN publishers p ON a.publisher_id = p.id
            WHERE {where_clause}
            ORDER BY relevance_score DESC, a.published_date DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """

        legacy_query = f"""
            SELECT
                article_id, title, url, source_name, author, published_date,
                excerpt, reliability_score, overall_credibility,
                source_credibility_score, country_code, language_code,
                tags, claims_count as claim_count,
                verified_claims_count as verified_claim_count,
                claims_status, claims_error_message, claims_processed_at,
                created_at, updated_at,
                (
                    (COALESCE(reliability_score, {source_credibility_sql}) * 0.6) +
                    (100 * EXP(-EXTRACT(EPOCH FROM (NOW() - COALESCE(published_date, created_at))) / (30 * 86400)) * 0.3) +
                    (LEAST(verified_claims_count * 2, 100) * 0.1)
                ) as relevance_score
            FROM articles a
            WHERE {where_clause.replace('a.', '')}
            ORDER BY relevance_score DESC, published_date DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """

        results = self._execute_trust_query(trust_query, legacy_query, params)
        return [self._row_to_article(row) for row in results]

    def get_tags(self, limit: int = 50) -> list[TagStat]:
        """
        Get popular tags with article counts.
        
        Args:
            limit: Max number of tags to return
        
        Returns:
            List of TagStat models
        """
        results = self.db.execute_query(
            """
            SELECT
                UNNEST(tags) as tag,
                COUNT(*) as article_count
            FROM articles
            WHERE tags IS NOT NULL
            GROUP BY tag
            ORDER BY article_count DESC
            LIMIT :limit
            """,
            {"limit": limit}
        )
        
        return [TagStat(tag=row["tag"], article_count=row["article_count"]) for row in results]
    
    def get_stats(self) -> dict:
        """
        Get aggregate statistics for the platform.
        
        Returns:
            Dict with platform stats
        """
        results = self.db.execute_query(
            """
            SELECT
                COUNT(*) as total_articles,
                COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as articles_today,
                SUM(claims_count) as total_claims,
                SUM(verified_claims_count) as verified_claims,
                AVG(reliability_score) as avg_reliability,
                MAX(created_at) as last_updated
            FROM articles
            WHERE 1=1
            """
        )
        
        if not results:
            return {
                "total_articles": 0,
                "articles_today": 0,
                "total_fact_checks": 0,
                "verified_claims": 0,
                "average_confidence": 0.0,
                "last_updated": None
            }
        
        result = results[0]
        avg_reliability = result["avg_reliability"]
        if avg_reliability is not None:
            avg_confidence = float(avg_reliability) / 100.0
        else:
            avg_confidence = 0.0
        
        return {
            "total_articles": result["total_articles"] or 0,
            "articles_today": result["articles_today"] or 0,
            "total_fact_checks": result["total_claims"] or 0,
            "verified_claims": result["verified_claims"] or 0,
            "average_confidence": avg_confidence,
            "last_updated": result["last_updated"]
        }

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _article_select_columns(self, include_detail: bool = False) -> str:
        columns = [
            "a.article_id",
            "a.title",
            "COALESCE(a.url, a.original_url) AS url",
            "a.source_name",
            "a.author",
            "a.published_date",
            "a.excerpt",
            "a.reliability_score",
            "a.overall_credibility",
            "a.source_credibility_score",
            "a.country_code",
            "a.language_code",
            "a.tags",
            "a.claims_count AS claim_count",
            "a.verified_claims_count AS verified_claim_count",
            "a.claims_status",
            "a.claims_error_message",
            "a.claims_processed_at",
            "a.created_at",
            "a.updated_at",
            "COALESCE(a.original_url, a.url) AS cta_url",
            "a.summary_type",
            "a.video_url",
            "a.video_status",
            "a.hitl_status",
            "a.compliance_check_passed",
            "a.compliance_skip_reason",
            "a.trust_score_cache",
            "p.trust_score AS publisher_trust_score",
            "p.nutrition_label",
            "p.tdm_opt_out"
        ]
        if include_detail:
            columns.append("COALESCE(a.extracted_text, '') AS extracted_text")
            columns.append("a.provenance")
            # Golden Example fix (2026-05-27): the End2End audit found
            # /api/v2/articles/{id} was silently dropping every enrichment
            # column even after Lane A worker populated them. ArticleDetail
            # already declares these fields (Pydantic accepts them), but
            # the SELECT here didn't include them, so the FE article-detail
            # page never saw executive_brief / enriched_excerpt / climate
            # context / metadata. Add them now so the Golden Example
            # commits (#5 brief, #3 trend) actually surface in the UI.
            columns.append("a.enriched_excerpt")
            columns.append("a.climate_context_summary")
            columns.append("a.enrichment_metadata")
            columns.append("a.executive_brief")
            columns.append("a.insight_summary")
            columns.append("a.content_category")
        return ",\n                ".join(columns)

    def _execute_trust_query(
        self,
        trust_sql: str,
        legacy_sql: str,
        params: Dict[str, Any],
    ):
        if not self._trust_queries_supported:
            return self.db.execute_query(legacy_sql, params)
        try:
            return self.db.execute_query(trust_sql, params)
        except Exception as exc:
            logger.warning(
                f"Trust-aware query failed, falling back to legacy schema: {str(exc)}"
            )
            self._trust_queries_supported = False
            return self.db.execute_query(legacy_sql, params)

    def _parse_json_field(self, value: Any):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None

    def _build_compliance_flags(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        flags: Dict[str, Any] = {}
        passed = row.get("compliance_check_passed")
        reason = row.get("compliance_skip_reason")
        tdm_opt_out = row.get("tdm_opt_out")

        if passed is not None:
            flags["passed"] = passed
        if reason:
            flags["reason"] = reason
        if tdm_opt_out is not None:
            flags["tdm_opt_out"] = tdm_opt_out

        return flags or None

    def _row_to_article(self, row: Dict[str, Any]) -> Article:
        compliance_flags = self._build_compliance_flags(row)
        nutrition_label = self._parse_json_field(row.get("nutrition_label"))
        article_kwargs = {
            "article_id": row.get("article_id"),
            "title": row.get("title"),
            "url": row.get("url"),
            "source_name": row.get("source_name"),
            "author": row.get("author"),
            "published_date": row.get("published_date"),
            "excerpt": row.get("excerpt"),
            "reliability_score": row.get("reliability_score"),
            "overall_credibility": row.get("overall_credibility"),
            "source_credibility_score": row.get("source_credibility_score"),
            "country_code": row.get("country_code"),
            "language_code": row.get("language_code"),
            "tags": row.get("tags") or [],
            "claim_count": row.get("claim_count") or 0,
            "verified_claim_count": row.get("verified_claim_count") or 0,
            "claims_status": row.get("claims_status", "pending"),
            "claims_error_message": row.get("claims_error_message"),
            "claims_processed_at": row.get("claims_processed_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "cta_url": row.get("cta_url") or row.get("url"),
            "summary_type": row.get("summary_type"),
            "video_url": row.get("video_url"),
            "video_status": row.get("video_status"),
            "hitl_status": row.get("hitl_status"),
            "compliance_flags": compliance_flags,
            "trust_score": row.get("trust_score_cache"),
            "publisher_trust_score": row.get("publisher_trust_score"),
            "nutrition_label": nutrition_label,
        }
        return Article(**article_kwargs)

    def _row_to_article_detail(
        self,
        row: Dict[str, Any],
        *,
        claims: list[ClaimWithFactCheck],
    ) -> ArticleDetail:
        base_article = self._row_to_article(row)
        detail_data = base_article.model_dump()

        # Parse decomposed confidence JSONB
        dc_data = self._parse_json_field(row.get("decomposed_confidence"))

        # Build reliability breakdown from decomposed confidence
        reliability_breakdown = None
        if isinstance(dc_data, dict) and dc_data.get("overall"):
            factor_config = [
                ("model_confidence", "AI Model Confidence", 0.20),
                ("source_quality", "Source Quality", 0.30),
                ("evidence_breadth", "Evidence Breadth", 0.20),
                ("cross_reference_score", "Cross-Reference Score", 0.15),
                ("temporal_relevance", "Temporal Relevance", 0.15),
            ]
            reliability_breakdown = {}
            for key, label, weight in factor_config:
                score = dc_data.get(key, 0)
                reliability_breakdown[key] = {
                    "label": label,
                    "score": score,
                    "weight": weight,
                    "weighted_score": round(score * weight, 4),
                }

        detail_data.update({
            "extracted_text": row.get("extracted_text", "") if row.get("extracted_text") is not None else "",
            "full_text": row.get("extracted_text", "") if row.get("extracted_text") is not None else "",
            "claims": claims,
            "provenance": self._parse_json_field(row.get("provenance")),
            "decomposed_confidence": dc_data,
            "reliability_breakdown": reliability_breakdown,
            "insight_summary": row.get("insight_summary"),
            "analysis_article_html": row.get("analysis_article_html"),
            "analysis_article_generated_at": row.get("analysis_article_generated_at"),
            # Golden Example fix follow-up (2026-05-27): the SELECT pulls
            # these columns now, but the mapper was discarding them so the
            # FE article-detail page still saw empty values. Explicitly
            # forward enriched_excerpt + climate_context_summary +
            # executive_brief + enrichment_metadata into the response.
            "enriched_excerpt": row.get("enriched_excerpt"),
            "climate_context_summary": row.get("climate_context_summary"),
            "executive_brief": row.get("executive_brief"),
            "enrichment_metadata": self._parse_json_field(row.get("enrichment_metadata")),
            "content_category": row.get("content_category"),
        })
        return ArticleDetail(**detail_data)

