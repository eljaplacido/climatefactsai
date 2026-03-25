"""
Document Adapter — Research report and PDF processing.

Handles PDF URL downloads, text extraction, DOI detection, and content type classification.
"""

import re
from typing import Any, Dict, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# Content type detection patterns
CONTENT_TYPE_PATTERNS = {
    "research_report": [
        r"abstract", r"methodology", r"findings", r"peer.?review",
        r"doi:", r"10\.\d{4,}", r"journal", r"et\s+al\.",
    ],
    "policy_document": [
        r"regulation", r"directive", r"compliance", r"legislation",
        r"framework", r"mandate", r"policy\s+brief",
    ],
    "preprint": [
        r"preprint", r"arxiv", r"medrxiv", r"biorxiv", r"ssrn",
        r"working\s+paper", r"draft",
    ],
}

DOI_PATTERN = re.compile(r'(10\.\d{4,9}/[^\s]+)')


def detect_content_type(text: str, url: str = "") -> str:
    """Detect content type from text and URL."""
    combined = (text[:3000] + " " + url).lower()

    scores = {}
    for ctype, patterns in CONTENT_TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, combined, re.IGNORECASE))
        scores[ctype] = score

    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return "news_article"


def extract_doi(text: str) -> Optional[str]:
    """Extract DOI from text."""
    match = DOI_PATTERN.search(text)
    if match:
        doi = match.group(1).rstrip(".,;)")
        return doi
    return None


async def process_document_url(url: str) -> Dict[str, Any]:
    """
    Download and process a document from URL.

    Attempts PDF extraction via pypdf2, falls back to treating as HTML/text.
    Returns dict with: title, text, content_type, doi, publication_venue
    """
    import httpx

    result = {
        "title": "",
        "text": "",
        "content_type": "news_article",
        "doi": None,
        "publication_venue": None,
        "url": url,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
                # Extract text from PDF
                text = _extract_pdf_text(resp.content)
            else:
                # Treat as HTML/text
                text = resp.text[:50000]

            result["text"] = text
            result["content_type"] = detect_content_type(text, url)
            result["doi"] = extract_doi(text)

            # Try to extract title from first line
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if lines:
                result["title"] = lines[0][:255]

            # Detect publication venue from DOI prefix or URL
            if result["doi"]:
                result["publication_venue"] = _detect_venue_from_doi(result["doi"])

    except Exception as e:
        logger.error(f"Document processing failed for {url}: {e}")
        raise

    return result


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf2."""
    try:
        import io
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages[:50]:  # Limit to 50 pages
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        return "\n".join(text_parts)[:100000]
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot extract PDF text")
        return ""
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")
        return ""


def _detect_venue_from_doi(doi: str) -> Optional[str]:
    """Map DOI prefix to known publication venue."""
    venue_prefixes = {
        "10.1038": "Nature",
        "10.1126": "Science",
        "10.1016": "Elsevier",
        "10.1007": "Springer",
        "10.1002": "Wiley",
        "10.1371": "PLOS",
        "10.3389": "Frontiers",
        "10.5194": "Copernicus",
    }
    for prefix, venue in venue_prefixes.items():
        if doi.startswith(prefix):
            return venue
    return None
