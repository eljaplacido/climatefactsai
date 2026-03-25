"""
Research Report Analysis Service — Deep analysis of academic papers and industry reports.

Handles:
- PDF/DOI upload and text extraction
- Academic claim extraction with citation tracking
- Methodology assessment
- CrossRef DOI metadata enrichment
- Bayesian credibility scoring for research content
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.database import Database, get_db
from app.core.logging import get_logger
from app.domains.content.data_sources.document_adapter import (
    process_document_url, detect_content_type, extract_doi,
)
from app.domains.intelligence.bayesian_credibility import BayesianCredibilityService
from app.domains.intelligence.llm_client import llm_chat

logger = get_logger(__name__)

CROSSREF_API = "https://api.crossref.org/works"


class ResearchReportService:
    """Analyze research reports and academic papers for credibility."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()
        self.bayesian = BayesianCredibilityService(self.db)

    async def analyze_report(
        self, url: Optional[str] = None, doi: Optional[str] = None,
        text: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive analysis of a research report."""
        doc_meta = await self._resolve_document(url, doi, text)

        if not doc_meta.get("text"):
            return {"status": "error", "error": "Could not extract text from the provided document"}

        doc_text = doc_meta["text"]
        content_type = doc_meta.get("content_type", "research_report")
        detected_doi = doc_meta.get("doi")
        venue = doc_meta.get("publication_venue")

        metadata = {}
        if detected_doi:
            metadata = await self._fetch_doi_metadata(detected_doi)

        analysis = await self._analyze_with_llm(doc_text, content_type, metadata)

        prior = self.bayesian.compute_research_prior(
            has_doi=bool(detected_doi), venue=venue or metadata.get("venue"), content_type=content_type,
        )

        evidence_scores = []
        if analysis.get("methodology_score"):
            evidence_scores.append(analysis["methodology_score"] / 100.0)
        if analysis.get("citation_score"):
            evidence_scores.append(analysis["citation_score"] / 100.0)
        if analysis.get("data_transparency_score"):
            evidence_scores.append(analysis["data_transparency_score"] / 100.0)

        posterior = self.bayesian.compute_posterior(prior, evidence_scores, prior_weight=0.2)

        report_id = None
        if user_id:
            try:
                result = self.db.execute_query(
                    """INSERT INTO saved_analyses (user_id, title, analysis_type, content, tags)
                       VALUES (:uid, :title, 'research_report', :content::jsonb, :tags)
                       RETURNING analysis_id""",
                    {"uid": user_id, "title": doc_meta.get("title", "Research Report")[:500],
                     "content": json.dumps({"url": url, "doi": detected_doi, "analysis": analysis, "credibility": posterior}),
                     "tags": analysis.get("topics", [])[:10]}
                )
                if result:
                    report_id = str(result[0]["analysis_id"])
            except Exception as e:
                logger.warning(f"Failed to save analysis: {e}")

        return {
            "status": "completed", "report_id": report_id,
            "document": {
                "title": doc_meta.get("title", ""), "content_type": content_type,
                "doi": detected_doi, "venue": venue or metadata.get("venue"),
                "authors": metadata.get("authors", []),
                "published_date": metadata.get("published_date"),
                "word_count": len(doc_text.split()),
            },
            "analysis": analysis,
            "credibility": {
                "prior_score": prior, "posterior": posterior,
                "content_type_basis": content_type, "has_doi": bool(detected_doi),
                "venue_recognized": bool(venue),
            },
        }

    async def _resolve_document(self, url, doi, text):
        if text:
            return {"text": text, "content_type": detect_content_type(text),
                    "doi": extract_doi(text), "title": text.split("\n")[0][:255] if text else ""}
        if doi:
            try:
                return await process_document_url(f"https://doi.org/{doi}")
            except Exception as e:
                logger.warning(f"DOI resolution failed for {doi}: {e}")
                return {"text": "", "doi": doi}
        if url:
            try:
                return await process_document_url(url)
            except Exception as e:
                logger.error(f"Document fetch failed for {url}: {e}")
                return {"text": "", "url": url}
        return {"text": ""}

    async def _fetch_doi_metadata(self, doi: str) -> Dict[str, Any]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{CROSSREF_API}/{doi}",
                                        headers={"User-Agent": "CliLens.AI/2.0 (climate-news-platform)"})
                if resp.status_code != 200:
                    return {}
                data = resp.json().get("message", {})
                authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in data.get("author", [])]
                published = data.get("published-print") or data.get("published-online") or {}
                date_parts = published.get("date-parts", [[]])[0]
                pub_date = "-".join(str(p) for p in date_parts) if date_parts else None
                container = data.get("container-title", [])
                return {
                    "title": data.get("title", [""])[0], "authors": [a for a in authors if a],
                    "venue": container[0] if container else None, "published_date": pub_date,
                    "citation_count": data.get("is-referenced-by-count", 0),
                    "references_count": data.get("references-count", 0),
                    "publisher": data.get("publisher"), "subjects": data.get("subject", []),
                }
        except Exception as e:
            logger.warning(f"CrossRef metadata fetch failed for {doi}: {e}")
            return {}

    async def _analyze_with_llm(self, text: str, content_type: str, metadata: Dict) -> Dict[str, Any]:
        analysis_text = text[:15000]
        system_prompt = """You are a scientific report analyzer for a climate news platform.
Analyze the following research document and provide a structured assessment.
Return ONLY a JSON object with these fields:
{"summary": "2-3 sentence summary", "key_claims": ["list of 3-5 main claims"],
"methodology_score": 0-100, "citation_score": 0-100, "data_transparency_score": 0-100,
"topics": ["topic tags"], "climate_relevance": "high/medium/low",
"limitations_noted": true/false, "peer_reviewed_indicators": true/false,
"potential_biases": ["any biases"], "recommendation": "brief recommendation"}"""

        meta_ctx = ""
        if metadata:
            meta_ctx = f"\nAuthors={metadata.get('authors', 'Unknown')}, Venue={metadata.get('venue', 'Unknown')}\n"

        response = llm_chat(f"Content type: {content_type}\n{meta_ctx}\nDocument:\n{analysis_text}",
                            system_prompt=system_prompt, max_tokens=2000, temperature=0.1)

        if not response:
            return {"summary": "LLM analysis unavailable", "key_claims": [], "methodology_score": 50,
                    "citation_score": 50, "data_transparency_score": 50, "topics": [], "climate_relevance": "unknown",
                    "limitations_noted": False, "peer_reviewed_indicators": False, "potential_biases": [],
                    "recommendation": "Manual review recommended"}

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        return {"summary": response[:500], "key_claims": [], "methodology_score": 50,
                "citation_score": 50, "data_transparency_score": 50, "topics": [], "climate_relevance": "unknown",
                "limitations_noted": False, "peer_reviewed_indicators": False, "potential_biases": [],
                "recommendation": "Parse error — manual review recommended"}
