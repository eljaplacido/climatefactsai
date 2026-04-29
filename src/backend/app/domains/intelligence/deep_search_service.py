"""
Deep Search Service — User-facing Perplexity-type search with corpus synthesis.

Combines internal corpus search (pgvector), external web search (Perplexity),
and weather context enrichment into a synthesized answer with citations.

Gated to Professional+ tiers.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.database import Database
from app.core.logging import get_logger
from app.domains.content.embedding_service import EmbeddingService
from app.domains.intelligence.evidence_retriever import (
    PerplexityEvidenceRetriever,
    OpenMeteoEvidenceRetriever,
)

logger = get_logger(__name__)


class DeepSearchService:
    """
    User-facing deep search combining internal corpus + external sources.

    Unlike the internal evidence retriever (which verifies claims),
    this service answers user research questions with synthesized responses.
    """

    def __init__(self, db: Database):
        self.db = db
        self.embedding_service = EmbeddingService(db)
        self.perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    async def search(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        include_weather: bool = True,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Perform a deep search combining multiple sources.

        Returns a synthesized answer with citations from internal articles,
        external web sources, and optionally weather data.
        """
        # Run all searches concurrently
        tasks = [
            self._search_internal_corpus(query, country=country, category=category, limit=limit),
            self._search_perplexity(query, country=country),
        ]
        if include_weather and self._has_weather_keywords(query):
            tasks.append(self._get_weather_context(query, country=country))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        internal_results = results[0] if not isinstance(results[0], Exception) else []
        perplexity_results = results[1] if not isinstance(results[1], Exception) else {}
        weather_context = None
        if len(results) > 2 and not isinstance(results[2], Exception):
            weather_context = results[2]

        # Build citations from internal articles
        citations = []
        for art in (internal_results or []):
            citations.append({
                "type": "internal_article",
                "article_id": art.get("article_id"),
                "title": art.get("title", ""),
                "source_name": art.get("source_name", ""),
                "published_date": art.get("published_date"),
                "credibility": art.get("overall_credibility"),
                "reliability_score": art.get("reliability_score"),
                "relevance_score": art.get("relevance_score", 0),
                "excerpt": (art.get("excerpt") or "")[:200],
            })

        # Add Perplexity citations
        if perplexity_results.get("citations"):
            for url in perplexity_results["citations"]:
                citations.append({
                    "type": "external_web",
                    "source_url": url,
                    "source_name": _domain_from_url(url),
                })

        # Synthesize answer
        synthesis = await self._synthesize_answer(
            query=query,
            internal_articles=internal_results or [],
            perplexity_answer=perplexity_results.get("answer", ""),
            weather_context=weather_context,
        )

        return {
            "query": query,
            "answer": synthesis,
            "citations": citations,
            "internal_articles_count": len(internal_results or []),
            "external_sources_count": len(perplexity_results.get("citations", [])),
            "weather_context": weather_context,
            "filters": {
                "country": country,
                "category": category,
            },
            "searched_at": datetime.utcnow().isoformat(),
        }

    async def compare(
        self,
        query_a: str,
        query_b: str,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare two topics/queries side by side.

        Returns results for both queries plus a comparative analysis.
        If one side fails, partial results are still returned.
        """
        raw_a, raw_b = await asyncio.gather(
            self.search(query_a, country=country, include_weather=True, limit=5),
            self.search(query_b, country=country, include_weather=True, limit=5),
            return_exceptions=True,
        )

        empty_result = {
            "query": "",
            "answer": "Search failed for this topic.",
            "citations": [],
            "internal_articles_count": 0,
            "external_sources_count": 0,
            "weather_context": None,
            "filters": {},
            "searched_at": datetime.utcnow().isoformat(),
        }

        result_a: Dict[str, Any] = empty_result.copy() if isinstance(raw_a, Exception) else raw_a
        result_b: Dict[str, Any] = empty_result.copy() if isinstance(raw_b, Exception) else raw_b

        if isinstance(raw_a, Exception):
            result_a["query"] = query_a
            logger.warning(f"Compare side A failed: {raw_a}")
        if isinstance(raw_b, Exception):
            result_b["query"] = query_b
            logger.warning(f"Compare side B failed: {raw_b}")

        comparative = await self._generate_comparison(
            query_a, query_b, result_a, result_b
        )

        return {
            "query_a": query_a,
            "query_b": query_b,
            "result_a": result_a,
            "result_b": result_b,
            "comparative_analysis": comparative,
            "compared_at": datetime.utcnow().isoformat(),
        }

    async def _search_internal_corpus(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Search internal article corpus using hybrid FTS + semantic search."""
        embedding = await self.embedding_service.generate_embedding(query)

        results = []

        # Semantic search if embeddings available
        if embedding:
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
                    1 - (a.embedding <=> :embedding::vector) AS similarity
                FROM articles a
                WHERE a.embedding IS NOT NULL
                  AND {where_clause}
                ORDER BY a.embedding <=> :embedding::vector
                LIMIT :limit
            """

            try:
                rows = self.db.execute_query(sql, params)
                for r in (rows or []):
                    results.append({
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
                    })
            except Exception as e:
                logger.error(f"Internal corpus search failed: {e}")

        # Fallback to FTS if no semantic results
        if not results:
            fts_filters = []
            fts_params: Dict[str, Any] = {"query": query, "limit": limit}
            if country:
                fts_filters.append("a.country_code = :country")
                fts_params["country"] = country.upper()

            fts_where = " AND ".join(fts_filters) if fts_filters else "TRUE"

            # Try websearch_to_tsquery first (supports OR/phrase), fall back to plainto
            for tsq_func in ["websearch_to_tsquery", "plainto_tsquery"]:
                if results:
                    break
                fts_sql = f"""
                    SELECT a.article_id, a.title, a.source_name, a.country_code,
                           a.content_category, a.overall_credibility, a.reliability_score,
                           a.published_date, a.excerpt,
                           ts_rank(
                               to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,'')),
                               {tsq_func}('english', :query)
                           ) AS text_rank
                    FROM articles a
                    WHERE to_tsvector('english', COALESCE(a.title,'') || ' ' || COALESCE(a.excerpt,''))
                          @@ {tsq_func}('english', :query)
                      AND {fts_where}
                    ORDER BY text_rank DESC LIMIT :limit
                """
                try:
                    rows = self.db.execute_query(fts_sql, fts_params)
                    for r in (rows or []):
                        results.append({
                            "article_id": str(r["article_id"]),
                            "title": r.get("title", ""),
                            "source_name": r.get("source_name", ""),
                            "country_code": r.get("country_code"),
                            "overall_credibility": r.get("overall_credibility"),
                            "reliability_score": r.get("reliability_score"),
                            "published_date": str(r["published_date"]) if r.get("published_date") else None,
                            "excerpt": r.get("excerpt"),
                            "relevance_score": round(float(r.get("text_rank", 0)), 4),
                        })
                except Exception as e:
                    logger.warning(f"FTS search ({tsq_func}) failed: {e}")

        # Final fallback: ILIKE keyword search if FTS found nothing
        if not results:
            # Split query into keywords and search with ILIKE
            keywords = [w.strip() for w in query.split() if len(w.strip()) > 2][:4]
            if keywords:
                ilike_conditions = " OR ".join(
                    f"LOWER(a.title) LIKE :kw{i} OR LOWER(a.excerpt) LIKE :kw{i}"
                    for i in range(len(keywords))
                )
                ilike_params: Dict[str, Any] = {"limit": limit}
                for i, kw in enumerate(keywords):
                    ilike_params[f"kw{i}"] = f"%{kw.lower()}%"
                if country:
                    ilike_params["country"] = country.upper()

                country_clause = "AND a.country_code = :country" if country else ""
                ilike_sql = f"""
                    SELECT a.article_id, a.title, a.source_name, a.country_code,
                           a.content_category, a.overall_credibility, a.reliability_score,
                           a.published_date, a.excerpt,
                           0.1 AS text_rank
                    FROM articles a
                    WHERE ({ilike_conditions}) {country_clause}
                    ORDER BY a.published_date DESC NULLS LAST
                    LIMIT :limit
                """
                try:
                    rows = self.db.execute_query(ilike_sql, ilike_params)
                    for r in (rows or []):
                        results.append({
                            "article_id": str(r["article_id"]),
                            "title": r.get("title", ""),
                            "source_name": r.get("source_name", ""),
                            "country_code": r.get("country_code"),
                            "overall_credibility": r.get("overall_credibility"),
                            "reliability_score": r.get("reliability_score"),
                            "published_date": str(r["published_date"]) if r.get("published_date") else None,
                            "excerpt": r.get("excerpt"),
                            "relevance_score": 0.1,
                        })
                except Exception as e:
                    logger.warning(f"ILIKE fallback search failed: {e}")

        return results

    async def _search_perplexity(
        self, query: str, country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search external sources via Perplexity Sonar."""
        if not self.perplexity_key:
            logger.warning(
                "PERPLEXITY_API_KEY not configured; deep search will skip external citations."
            )
            return {"answer": "", "citations": []}

        country_context = f" Focus on {country} region." if country else ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("PERPLEXITY_MODEL", "sonar"),
                        "messages": [{
                            "role": "user",
                            "content": (
                                f"Research this climate/environment topic thoroughly: \"{query}\".{country_context} "
                                "Provide a comprehensive answer with specific data points, statistics, "
                                "and findings from credible sources (scientific papers, government agencies, "
                                "international organizations). Include temporal context (when data is from)."
                            ),
                        }],
                        "temperature": 0.1,
                        "max_tokens": 1500,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])

                return {
                    "answer": content,
                    "citations": citations,
                }
        except Exception as e:
            logger.warning(f"Perplexity deep search failed: {e}")
            return {"answer": "", "citations": []}

    async def _get_weather_context(
        self, query: str, country: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather context relevant to the query.

        Uses the explicitly requested country, or tries to extract a country
        code from the query text, before falling back to a global context.
        """
        retriever = OpenMeteoEvidenceRetriever()
        cc = country or self._extract_country_from_query(query)
        if not cc:
            return None
        evidence_list = await retriever.retrieve(query, cc)

        if not evidence_list:
            return None

        return {
            "country_code": cc,
            "data_points": [
                {
                    "source": e.source,
                    "content": e.content_excerpt,
                    "reliability": e.source_reliability,
                    "retrieval_method": e.retrieval_method,
                }
                for e in evidence_list
            ],
        }

    async def _synthesize_answer(
        self,
        query: str,
        internal_articles: List[Dict],
        perplexity_answer: str,
        weather_context: Optional[Dict],
    ) -> str:
        """Synthesize a unified answer from all sources using Claude or DeepSeek."""
        # Build context from internal articles
        articles_context = ""
        if internal_articles:
            for i, art in enumerate(internal_articles[:5], 1):
                cred = art.get("overall_credibility", "UNKNOWN")
                rel = art.get("reliability_score")
                rel_str = f", reliability: {rel:.0%}" if rel else ""
                articles_context += (
                    f"\n{i}. [{cred}{rel_str}] \"{art.get('title', '')}\""
                    f"\n   Source: {art.get('source_name', 'Unknown')}"
                    f"\n   Excerpt: {(art.get('excerpt') or '')[:150]}\n"
                )

        weather_section = ""
        if weather_context and weather_context.get("data_points"):
            weather_section = "\nWEATHER DATA:\n"
            for dp in weather_context["data_points"]:
                weather_section += f"- {dp['content']}\n"

        prompt = f"""Based on the following sources, provide a comprehensive answer to: "{query}"

INTERNAL ARTICLES (from our verified corpus):
{articles_context or 'No matching articles found.'}

EXTERNAL RESEARCH:
{perplexity_answer or 'No external sources available.'}
{weather_section}
---

Synthesize a clear, well-structured answer that:
1. Leads with the most important findings
2. Notes where internal and external sources agree or disagree
3. Indicates credibility levels of sources cited
4. Includes relevant weather/climate data if available
5. Flags any limitations or areas of uncertainty

Use markdown formatting. Be factual and concise."""

        # Try Claude first
        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=1500,
                    temperature=0.2,
                    system="You are CliLens.AI's research assistant. Synthesize climate research from multiple sources with emphasis on source credibility and data accuracy.",
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    return message.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Claude synthesis failed: {e}")

        # Fallback to DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=15.0,
                )
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "Synthesize climate research concisely."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1500,
                    temperature=0.2,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"DeepSeek synthesis failed: {e}")

        # No LLM available — return raw concatenation
        parts = []
        if internal_articles:
            parts.append(f"Found {len(internal_articles)} related articles in our corpus.")
        if perplexity_answer:
            parts.append(f"External research:\n{perplexity_answer[:500]}")
        if weather_context:
            for dp in weather_context.get("data_points", []):
                parts.append(dp["content"])
        return "\n\n".join(parts) if parts else "No results found for this query."

    async def _generate_comparison(
        self,
        query_a: str,
        query_b: str,
        result_a: Dict,
        result_b: Dict,
    ) -> str:
        """Generate a comparative analysis between two search results."""
        prompt = f"""Compare these two climate topics:

TOPIC A: "{query_a}"
- {result_a.get('internal_articles_count', 0)} internal articles found
- Answer summary: {(result_a.get('answer') or '')[:300]}

TOPIC B: "{query_b}"
- {result_b.get('internal_articles_count', 0)} internal articles found
- Answer summary: {(result_b.get('answer') or '')[:300]}

Provide a structured comparison covering:
1. Key similarities and differences
2. Which topic has stronger evidence/coverage
3. How they relate to each other
4. Notable gaps in either topic

Be concise and factual. Use markdown."""

        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=1000,
                    temperature=0.2,
                    system="You compare climate topics with factual precision.",
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    return message.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Comparison synthesis (Claude) failed: {e}")

        # Fallback to DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=15.0,
                )
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "You compare climate topics with factual precision."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.2,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Comparison synthesis (DeepSeek) failed: {e}")

        return f"Comparison between \"{query_a}\" and \"{query_b}\" could not be generated. Both individual analyses are available above."

    @staticmethod
    def _extract_country_from_query(query: str) -> Optional[str]:
        """Try to extract a 2-letter country code from the query text.

        Handles explicit codes like 'US', 'DE', common country name mentions,
        and regional terms like 'southern europe' (returns a representative
        country for weather context).
        """
        import re

        query_lower = query.lower()

        # Regional terms -> representative country code for weather context
        REGION_TO_CODE = {
            "southern europe": "ES", "south europe": "ES",
            "northern europe": "SE", "north europe": "SE",
            "western europe": "FR", "west europe": "FR",
            "eastern europe": "PL", "east europe": "PL",
            "central europe": "DE",
            "mediterranean": "IT",
            "iberian peninsula": "ES", "iberia": "ES",
            "scandinavia": "SE", "nordic": "SE", "nordics": "SE",
            "balkans": "RS", "balkan": "RS",
            "southeast asia": "TH", "south east asia": "TH",
            "east asia": "JP", "eastern asia": "JP",
            "south asia": "IN", "southern asia": "IN",
            "central asia": "KZ",
            "middle east": "SA", "mideast": "SA",
            "north africa": "EG", "northern africa": "EG",
            "west africa": "NG", "western africa": "NG",
            "east africa": "KE", "eastern africa": "KE",
            "southern africa": "ZA", "south africa": "ZA",
            "central africa": "CD",
            "sub-saharan africa": "KE", "subsaharan": "KE",
            "latin america": "BR", "south america": "BR",
            "central america": "MX",
            "caribbean": "JM",
            "oceania": "AU", "pacific islands": "NZ",
            "arctic": "NO", "antarctic": "AQ",
        }

        for region, code in REGION_TO_CODE.items():
            if region in query_lower:
                return code

        # Common country name -> code mapping
        NAME_TO_CODE = {
            "united states": "US", "usa": "US", "america": "US",
            "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
            "germany": "DE", "france": "FR", "italy": "IT", "spain": "ES",
            "canada": "CA", "australia": "AU", "japan": "JP", "china": "CN",
            "india": "IN", "brazil": "BR", "russia": "RU", "mexico": "MX",
            "finland": "FI", "sweden": "SE", "norway": "NO", "denmark": "DK",
            "netherlands": "NL", "belgium": "BE", "austria": "AT",
            "switzerland": "CH", "portugal": "PT", "greece": "GR",
            "poland": "PL", "ireland": "IE", "south korea": "KR",
            "nigeria": "NG", "egypt": "EG",
            "kenya": "KE", "indonesia": "ID", "philippines": "PH",
            "turkey": "TR", "argentina": "AR", "colombia": "CO",
            "chile": "CL", "new zealand": "NZ", "pakistan": "PK",
            "thailand": "TH", "vietnam": "VN", "malaysia": "MY",
            "saudi arabia": "SA", "iran": "IR", "iraq": "IQ",
            "ukraine": "UA", "romania": "RO", "czech republic": "CZ",
            "hungary": "HU", "croatia": "HR", "serbia": "RS",
            "bulgaria": "BG", "slovakia": "SK", "slovenia": "SI",
            "estonia": "EE", "latvia": "LV", "lithuania": "LT",
            "cyprus": "CY", "malta": "MT", "luxembourg": "LU",
            "iceland": "IS", "morocco": "MA", "tunisia": "TN",
            "algeria": "DZ", "ethiopia": "ET", "tanzania": "TZ",
            "ghana": "GH", "senegal": "SN", "ivory coast": "CI",
            "peru": "PE", "venezuela": "VE", "ecuador": "EC",
            "bolivia": "BO", "paraguay": "PY", "uruguay": "UY",
            "cuba": "CU", "costa rica": "CR", "panama": "PA",
            "jamaica": "JM", "singapore": "SG", "bangladesh": "BD",
            "nepal": "NP", "sri lanka": "LK", "myanmar": "MM",
            "cambodia": "KH", "mongolia": "MN", "kazakhstan": "KZ",
        }

        for name, code in NAME_TO_CODE.items():
            if name in query_lower:
                return code

        # Check for explicit 2-letter code pattern (e.g. "in US", "for DE")
        code_match = re.search(r'\b([A-Z]{2})\b', query.upper())
        if code_match:
            candidate = code_match.group(1)
            skip_words = {"IN", "IT", "IS", "OR", "AN", "AT", "AS", "IF", "ON",
                          "TO", "UP", "NO", "SO", "DO", "BY", "OF", "BE", "ME",
                          "MY", "HE", "WE", "AM", "VS"}
            if candidate not in skip_words:
                return candidate

        return None

    def _has_weather_keywords(self, text: str) -> bool:
        """Check if text contains weather-related keywords."""
        keywords = [
            "weather", "temperature", "precipitation", "rainfall", "wind",
            "heatwave", "heat wave", "flood", "drought", "storm", "hurricane",
            "typhoon", "cyclone", "snow", "frost", "ice", "cold wave",
            "forecast", "meteorolog", "climate data", "°c", "celsius",
            "climate", "warming", "cooling", "solar", "energy",
            "renewable", "emission", "carbon",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)


def _domain_from_url(url: str) -> str:
    """Extract domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url
