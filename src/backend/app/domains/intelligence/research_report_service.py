"""
Research Report Analysis Service — Deep analysis of academic papers and industry reports.

Handles:
- PDF/DOI upload and text extraction
- Academic repository PDF detection (Theseus, DSpace, institutional repos)
- Academic claim extraction with citation tracking
- Methodology assessment
- CrossRef DOI metadata enrichment
- Bayesian credibility scoring for research content
- Reference/citation counting from full document text
"""

import json
import re
import time
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

# Patterns for academic repository metadata pages that link to a PDF
_ACADEMIC_REPO_HOSTS = [
    "theseus.fi", "dspace", "jultika.oulu.fi", "trepo.tuni.fi",
    "helda.helsinki.fi", "lutpub.lut.fi", "urn.fi", "aaltodoc.aalto.fi",
    "epublications", "publications.jrc.ec.europa.eu",
]


class ResearchReportService:
    """Analyze research reports and academic papers for credibility."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()
        self.bayesian = BayesianCredibilityService(self.db)

    async def analyze_report(
        self, url: Optional[str] = None, doi: Optional[str] = None,
        text: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive analysis of a research report.

        For long documents (academic theses, large reports), analysis may
        take 30-60 seconds due to PDF download and text extraction.
        """
        start_time = time.time()

        doc_meta = await self._resolve_document(url, doi, text)

        if not doc_meta.get("text"):
            return {"status": "error", "error": "Could not extract text from the provided document"}

        doc_text = doc_meta["text"]
        content_type = doc_meta.get("content_type", "research_report")
        detected_doi = doc_meta.get("doi")
        venue = doc_meta.get("publication_venue")
        page_count = doc_meta.get("page_count", 0)

        metadata = {}
        if detected_doi:
            metadata = await self._fetch_doi_metadata(detected_doi)

        # Count references from the full text
        reference_count = self._count_references(doc_text)

        # Detect methodology sections
        has_methodology = self._detect_methodology_sections(doc_text)

        # Detect data tables/figures/appendices
        data_indicators = self._detect_data_indicators(doc_text)

        # For LLM analysis, send more text for longer documents (up to 30k chars)
        analysis = await self._analyze_with_llm(
            doc_text, content_type, metadata,
            reference_count=reference_count,
            has_methodology=has_methodology,
            data_indicators=data_indicators,
        )

        # Override LLM scores with heuristic-boosted scores for academic work
        analysis = self._adjust_scores(
            analysis, reference_count, has_methodology, data_indicators, content_type,
        )

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

        processing_time = round(time.time() - start_time, 1)

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
            "processing_time_seconds": processing_time,
            "processing_note": "Analysis may take 30-60 seconds for long documents" if processing_time > 15 else None,
            "document": {
                "title": doc_meta.get("title", ""), "content_type": content_type,
                "doi": detected_doi, "venue": venue or metadata.get("venue"),
                "authors": metadata.get("authors", []),
                "published_date": metadata.get("published_date"),
                "word_count": len(doc_text.split()),
                "page_count": page_count,
                "reference_count": reference_count,
            },
            "analysis": analysis,
            "credibility": {
                "prior_score": prior, "posterior": posterior,
                "content_type_basis": content_type, "has_doi": bool(detected_doi),
                "venue_recognized": bool(venue),
            },
        }

    # -----------------------------------------------------------------------
    # Document resolution with academic repository PDF detection
    # -----------------------------------------------------------------------

    async def _resolve_document(self, url, doi, text):
        if text:
            return {"text": text, "content_type": detect_content_type(text),
                    "doi": extract_doi(text), "title": text.split("\n")[0][:255] if text else "",
                    "page_count": 0}
        if doi:
            try:
                return await self._resolve_url_with_pdf_detection(f"https://doi.org/{doi}")
            except Exception as e:
                logger.warning(f"DOI resolution failed for {doi}: {e}")
                return {"text": "", "doi": doi, "page_count": 0}
        if url:
            try:
                return await self._resolve_url_with_pdf_detection(url)
            except Exception as e:
                logger.error(f"Document fetch failed for {url}: {e}")
                return {"text": "", "url": url, "page_count": 0}
        return {"text": "", "page_count": 0}

    async def _resolve_url_with_pdf_detection(self, url: str) -> Dict[str, Any]:
        """
        Fetch a URL and detect if it's an academic repository metadata page.
        If so, find the actual PDF link and download + extract that instead.
        """
        import httpx

        result = {
            "title": "", "text": "", "content_type": "news_article",
            "doi": None, "publication_venue": None, "url": url, "page_count": 0,
        }

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type_header = resp.headers.get("content-type", "")

            # If the URL directly serves a PDF, extract text from it
            if "pdf" in content_type_header.lower() or url.lower().endswith(".pdf"):
                text, page_count = self._extract_pdf_with_page_count(resp.content)
                result["text"] = text
                result["page_count"] = page_count
                result["content_type"] = detect_content_type(text, url)
                result["doi"] = extract_doi(text)
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if lines:
                    result["title"] = lines[0][:255]
                if result["doi"]:
                    result["publication_venue"] = self._detect_venue_from_doi(result["doi"])
                return result

            # It's an HTML page — check if it's an academic repository metadata page
            html_text = resp.text
            pdf_url = self._extract_pdf_url_from_metadata_page(html_text, url)

            if pdf_url:
                logger.info(f"Detected PDF URL from metadata page: {pdf_url}")
                try:
                    pdf_resp = await client.get(pdf_url)
                    pdf_resp.raise_for_status()
                    pdf_content_type = pdf_resp.headers.get("content-type", "")

                    if "pdf" in pdf_content_type.lower() or pdf_url.lower().endswith(".pdf"):
                        text, page_count = self._extract_pdf_with_page_count(pdf_resp.content)
                        if text and len(text.strip()) > 200:
                            result["text"] = text
                            result["page_count"] = page_count
                            result["content_type"] = detect_content_type(text, url)
                            result["doi"] = extract_doi(text)

                            # Try to get title from metadata page
                            title_match = re.search(
                                r'<meta\s+name="citation_title"\s+content="([^"]+)"',
                                html_text, re.IGNORECASE,
                            )
                            if title_match:
                                result["title"] = title_match.group(1)[:255]
                            elif text:
                                lines = [l.strip() for l in text.split("\n") if l.strip()]
                                if lines:
                                    result["title"] = lines[0][:255]

                            if result["doi"]:
                                result["publication_venue"] = self._detect_venue_from_doi(result["doi"])
                            return result
                except Exception as e:
                    logger.warning(f"PDF download from metadata page failed: {e}")

            # Fallback: use the HTML text directly (original behavior)
            text = html_text[:50000]
            result["text"] = text
            result["content_type"] = detect_content_type(text, url)
            result["doi"] = extract_doi(text)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if lines:
                result["title"] = lines[0][:255]
            if result["doi"]:
                result["publication_venue"] = self._detect_venue_from_doi(result["doi"])

        return result

    def _extract_pdf_url_from_metadata_page(self, html: str, base_url: str) -> Optional[str]:
        """
        Extract the actual PDF download URL from an academic repository metadata page.

        Checks for:
        1. <meta name="citation_pdf_url"> tag (standard academic metadata)
        2. <a> links ending in .pdf or containing /bitstream/
        3. Common DSpace/Theseus download patterns
        """
        from urllib.parse import urljoin

        # Strategy 1: citation_pdf_url meta tag (most reliable)
        meta_match = re.search(
            r'<meta\s+name="citation_pdf_url"\s+content="([^"]+)"',
            html, re.IGNORECASE,
        )
        if meta_match:
            return urljoin(base_url, meta_match.group(1))

        # Also try the reverse attribute order
        meta_match_rev = re.search(
            r'<meta\s+content="([^"]+)"\s+name="citation_pdf_url"',
            html, re.IGNORECASE,
        )
        if meta_match_rev:
            return urljoin(base_url, meta_match_rev.group(1))

        # Strategy 2: Look for download links with PDF indicators
        # DSpace / Theseus bitstream links
        bitstream_match = re.search(
            r'href="([^"]*(?:/bitstream/[^"]*\.pdf[^"]*|/retrieve/[^"]*\.pdf[^"]*))"',
            html, re.IGNORECASE,
        )
        if bitstream_match:
            return urljoin(base_url, bitstream_match.group(1))

        # Generic .pdf link (prefer ones with "download" or "full" in the URL)
        pdf_links = re.findall(r'href="([^"]*\.pdf[^"]*)"', html, re.IGNORECASE)
        if pdf_links:
            # Prefer links with download/full/bitstream keywords
            for link in pdf_links:
                if any(kw in link.lower() for kw in ("download", "full", "bitstream", "retrieve")):
                    return urljoin(base_url, link)
            # Fall back to first PDF link
            return urljoin(base_url, pdf_links[0])

        # Strategy 3: Check if page is from a known academic host
        is_academic = any(host in base_url.lower() for host in _ACADEMIC_REPO_HOSTS)
        if is_academic:
            # Look for any download button/link
            download_match = re.search(
                r'href="([^"]*(?:download|fulltext|document)[^"]*)"',
                html, re.IGNORECASE,
            )
            if download_match:
                return urljoin(base_url, download_match.group(1))

        return None

    def _extract_pdf_with_page_count(self, content: bytes) -> tuple:
        """Extract text from PDF bytes and return (text, page_count)."""
        try:
            import io
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            text_parts = []
            # Process up to 200 pages for thorough analysis
            for page in reader.pages[:200]:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n".join(text_parts)[:200000], page_count
        except ImportError:
            logger.warning("PyPDF2 not installed, cannot extract PDF text")
            return "", 0
        except Exception as e:
            logger.warning(f"PDF text extraction failed: {e}")
            return "", 0

    def _detect_venue_from_doi(self, doi: str) -> Optional[str]:
        """Map DOI prefix to known publication venue."""
        venue_prefixes = {
            "10.1038": "Nature", "10.1126": "Science", "10.1016": "Elsevier",
            "10.1007": "Springer", "10.1002": "Wiley", "10.1371": "PLOS",
            "10.3389": "Frontiers", "10.5194": "Copernicus",
        }
        for prefix, venue in venue_prefixes.items():
            if doi.startswith(prefix):
                return venue
        return None

    # -----------------------------------------------------------------------
    # Reference / citation counting
    # -----------------------------------------------------------------------

    def _count_references(self, text: str) -> int:
        """
        Count actual references/citations in the document text.

        Strategies:
        1. Look for a References/Bibliography section and count numbered entries
        2. Count bracketed citation markers [1], [2], etc.
        3. Count APA/Harvard style entries (Author, Year) in reference section
        """
        if not text:
            return 0

        text_lower = text.lower()

        # Find the references/bibliography section
        ref_section_start = -1
        for marker in ["references\n", "bibliography\n", "works cited\n",
                        "reference list\n", "list of references\n",
                        "references ", "bibliography ", "works cited "]:
            # Search from the latter half of the document (references are usually at the end)
            half_point = len(text_lower) // 2
            idx = text_lower.rfind(marker, half_point)
            if idx == -1:
                idx = text_lower.rfind(marker)
            if idx != -1 and idx > ref_section_start:
                ref_section_start = idx

        ref_count = 0

        if ref_section_start != -1:
            ref_section = text[ref_section_start:]

            # Count numbered references: [1], [2], ... or 1. Author, 2. Author, etc.
            numbered_refs = re.findall(r'\[(\d+)\]', ref_section)
            if numbered_refs:
                ref_count = max(int(n) for n in numbered_refs)

            # Count entries that look like bibliography items
            # Pattern: starts with author name(s) followed by year in parentheses
            if ref_count == 0:
                bib_entries = re.findall(
                    r'(?:^|\n)\s*(?:[A-Z][a-z]+(?:,?\s+[A-Z]\.?\s*)+.*?\(\d{4}\))',
                    ref_section,
                )
                ref_count = max(ref_count, len(bib_entries))

            # Count lines that start with a number (numbered list style)
            if ref_count == 0:
                numbered_lines = re.findall(r'(?:^|\n)\s*(\d{1,3})\.\s+\S', ref_section)
                if numbered_lines:
                    ref_count = max(int(n) for n in numbered_lines)

        # Fallback: count unique bracketed citations [N] across the whole text
        if ref_count == 0:
            all_citations = set(re.findall(r'\[(\d+)\]', text))
            if all_citations:
                ref_count = max(int(n) for n in all_citations)

        # Fallback: count (Author, Year) style inline citations
        if ref_count == 0:
            inline_cites = set(re.findall(
                r'\((?:[A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?),?\s*\d{4}\)',
                text,
            ))
            ref_count = len(inline_cites)

        return ref_count

    # -----------------------------------------------------------------------
    # Methodology / data indicator detection
    # -----------------------------------------------------------------------

    def _detect_methodology_sections(self, text: str) -> bool:
        """Check if the document contains methodology-related sections."""
        text_lower = text.lower()
        methodology_markers = [
            "methodology", "research method", "research design",
            "data collection", "data analysis", "research approach",
            "methods and materials", "materials and methods",
            "experimental design", "study design", "sampling method",
            "qualitative method", "quantitative method", "mixed method",
            "interview", "questionnaire", "survey design",
            "case study", "grounded theory", "thematic analysis",
            "statistical analysis", "regression analysis",
        ]
        found = sum(1 for marker in methodology_markers if marker in text_lower)
        return found >= 2  # At least 2 methodology indicators

    def _detect_data_indicators(self, text: str) -> Dict[str, bool]:
        """Check for data tables, figures, and appendices in the text."""
        text_lower = text.lower()
        return {
            "has_tables": bool(re.search(r'table\s+\d', text_lower)),
            "has_figures": bool(re.search(r'(?:figure|fig\.?)\s+\d', text_lower)),
            "has_appendices": "appendix" in text_lower or "appendices" in text_lower,
            "has_data_section": any(
                marker in text_lower for marker in ["data availability", "open data", "dataset", "data set"]
            ),
        }

    # -----------------------------------------------------------------------
    # Score adjustment for academic work
    # -----------------------------------------------------------------------

    def _adjust_scores(
        self, analysis: Dict, reference_count: int, has_methodology: bool,
        data_indicators: Dict, content_type: str,
    ) -> Dict[str, Any]:
        """
        Adjust LLM-generated scores with heuristic evidence from the full document.
        The LLM only sees the first portion of text, so it often underscores long
        academic works that have extensive references, methodology, and data.
        """
        adjusted = dict(analysis)

        # Methodology score adjustment
        if has_methodology:
            current = adjusted.get("methodology_score", 50)
            # If methodology sections are present, floor the score at 60
            adjusted["methodology_score"] = max(current, 60)
            # Boost further if multiple strong methodology indicators
            if content_type in ("research_report", "preprint"):
                adjusted["methodology_score"] = max(adjusted["methodology_score"], 70)

        # Citation score based on actual reference count
        if reference_count > 0:
            if reference_count >= 50:
                citation_score = max(85, adjusted.get("citation_score", 0))
            elif reference_count >= 30:
                citation_score = max(75, adjusted.get("citation_score", 0))
            elif reference_count >= 20:
                citation_score = max(65, adjusted.get("citation_score", 0))
            elif reference_count >= 10:
                citation_score = max(55, adjusted.get("citation_score", 0))
            else:
                citation_score = max(40, adjusted.get("citation_score", 0))
            adjusted["citation_score"] = citation_score

        # Data transparency based on detected indicators
        data_score = adjusted.get("data_transparency_score", 50)
        indicator_count = sum(1 for v in data_indicators.values() if v)
        if indicator_count >= 3:
            data_score = max(data_score, 80)
        elif indicator_count >= 2:
            data_score = max(data_score, 65)
        elif indicator_count >= 1:
            data_score = max(data_score, 55)
        adjusted["data_transparency_score"] = data_score

        # Store the reference count and indicator details in the analysis
        adjusted["reference_count"] = reference_count
        adjusted["methodology_detected"] = has_methodology
        adjusted["data_indicators"] = data_indicators

        return adjusted

    # -----------------------------------------------------------------------
    # DOI metadata
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # LLM analysis
    # -----------------------------------------------------------------------

    async def _analyze_with_llm(
        self, text: str, content_type: str, metadata: Dict,
        reference_count: int = 0, has_methodology: bool = False,
        data_indicators: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        # Send more text to LLM for thorough analysis (up to 30k chars)
        analysis_text = text[:30000]

        extra_context = ""
        if reference_count > 0:
            extra_context += f"\nNote: This document contains approximately {reference_count} references/citations."
        if has_methodology:
            extra_context += "\nNote: This document contains methodology/research design sections."
        if data_indicators:
            indicators = [k.replace("has_", "") for k, v in data_indicators.items() if v]
            if indicators:
                extra_context += f"\nNote: Document contains: {', '.join(indicators)}."

        system_prompt = """You are a scientific report analyzer for a climate news platform.
Analyze the following research document and provide a structured assessment.
Be thorough — this may be a long academic thesis or report with extensive references.
Score generously for documents with clear methodology, many references, and data transparency.
A thesis or academic paper with proper methodology should score at least 60-70 on methodology.
A document with 20+ references should score at least 65 on citations.
Return ONLY a JSON object with these fields:
{"summary": "2-3 sentence summary", "key_claims": ["list of 3-5 main claims"],
"methodology_score": 0-100, "citation_score": 0-100, "data_transparency_score": 0-100,
"topics": ["topic tags"], "climate_relevance": "high/medium/low",
"limitations_noted": true/false, "peer_reviewed_indicators": true/false,
"potential_biases": ["any biases"], "recommendation": "brief recommendation"}"""

        meta_ctx = ""
        if metadata:
            meta_ctx = f"\nAuthors={metadata.get('authors', 'Unknown')}, Venue={metadata.get('venue', 'Unknown')}\n"

        response = llm_chat(
            f"Content type: {content_type}\n{meta_ctx}{extra_context}\nDocument:\n{analysis_text}",
            system_prompt=system_prompt, max_tokens=2000, temperature=0.1,
        )

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
