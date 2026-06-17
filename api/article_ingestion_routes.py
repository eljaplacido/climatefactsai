"""
Article Ingestion Routes - Add real climate news articles from URLs and files

This module provides endpoints to:
- Submit article URLs for ingestion
- Scrape article content
- Extract claims automatically
- Fact-check claims
- Ingest research reports and PDF documents
- Upload PDF/DOCX/TXT files for analysis
"""
import io
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, File, UploadFile, Form
from fastapi.security import HTTPBearer
from pydantic import BaseModel, HttpUrl, Field
import uuid

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_routes import get_current_user

logger = setup_logging("article-ingestion")
router = APIRouter(prefix="/api/articles", tags=["Article Ingestion"])

_bearer_scheme = HTTPBearer(auto_error=True)


class IngestArticleRequest(BaseModel):
    """Request to ingest a new article from URL"""
    url: HttpUrl = Field(..., description="Article URL to ingest")
    title: Optional[str] = Field(None, description="Optional title override")
    process_claims: bool = Field(True, description="Automatically extract and verify claims")


class IngestArticleResponse(BaseModel):
    """Response from article ingestion"""
    article_id: str
    title: str
    url: str
    status: str
    message: str
    claims_extracted: int = 0
    processing_started: bool = False


def scrape_article_content(url: str) -> dict:
    """
    Scrape article content from URL.
    Returns: {title, text, excerpt, published_date}
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title
        title = None
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()

        # Extract main content
        # Try common article selectors
        content = None
        for selector in ['article', '.article-content', '.post-content', 'main', '.content']:
            content_tag = soup.select_one(selector)
            if content_tag:
                # Remove script and style tags
                for tag in content_tag(['script', 'style']):
                    tag.decompose()
                content = content_tag.get_text(separator=' ', strip=True)
                break

        if not content:
            # Fallback: get all p tags
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs])

        # Create excerpt (first 200 chars)
        excerpt = content[:200] + '...' if len(content) > 200 else content

        # Try to extract published date
        published_date = None
        date_meta = soup.find('meta', property='article:published_time')
        if date_meta:
            published_date = date_meta.get('content')

        return {
            'title': title or 'Untitled Article',
            'text': content,
            'excerpt': excerpt,
            'published_date': published_date or datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to scrape article: {str(e)}")


async def _enrich_article_background(
    article_id: str,
    title: str,
    content: str,
    source_name: str,
    country_code: str,
):
    """
    Background task to enrich an article with LLM-generated excerpt,
    climate context, and source reliability assessment.
    """
    try:
        from app.domains.content.article_enrichment_service import ArticleEnrichmentService

        db = get_postgres()
        service = ArticleEnrichmentService(db)
        result = await service.enrich_article(
            article_id=article_id,
            title=title,
            extracted_text=content,
            source_name=source_name,
            country_code=country_code,
        )
        logger.info(f"Enrichment complete for article {article_id}")
    except Exception as e:
        logger.error(f"Background enrichment failed for {article_id}: {e}", exc_info=True)


async def process_article_claims_background(article_id: str, article_text: str):
    """
    Background task to extract and verify claims for a newly ingested article.
    """
    try:
        # Import here to avoid circular imports
        from api.admin_pipeline_routes import extract_claims_for_article, verify_claims_for_article

        # Extract claims
        logger.info(f"Starting claim extraction for article {article_id}")
        claims_count, extract_error = await extract_claims_for_article(article_id, article_text)

        if extract_error:
            logger.error(f"Claim extraction failed for {article_id}: {extract_error}")
            return

        logger.info(f"Extracted {claims_count} claims from article {article_id}")

        # Verify claims
        if claims_count > 0:
            logger.info(f"Starting claim verification for article {article_id}")
            verified_count, verify_error = await verify_claims_for_article(article_id)

            if verify_error:
                logger.error(f"Claim verification failed for {article_id}: {verify_error}")
            else:
                logger.info(f"Verified {verified_count} claims for article {article_id}")

    except Exception as e:
        logger.error(f"Background processing failed for {article_id}: {e}", exc_info=True)


@router.post("/ingest", response_model=IngestArticleResponse)
async def ingest_article(request: IngestArticleRequest, background_tasks: BackgroundTasks):
    """
    Ingest a new article from a URL.

    This endpoint will:
    1. Scrape the article content
    2. Store it in the database
    3. Optionally extract and verify claims (background)

    Returns the article ID and processing status.
    """
    db = get_postgres()
    url_str = str(request.url)

    # Check if URL already exists
    existing = db.execute_query(
        "SELECT article_id, title FROM articles WHERE url = :url",
        {"url": url_str}
    )

    if existing:
        article = existing[0]
        return IngestArticleResponse(
            article_id=str(article['article_id']),
            title=article['title'],
            url=url_str,
            status="exists",
            message="Article already exists in database"
        )

    # Scrape article content
    try:
        scraped_data = scrape_article_content(url_str)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    # Use provided title or scraped title
    title = request.title or scraped_data['title']

    # Generate article ID
    article_id = str(uuid.uuid4())

    # Store article in database
    db.execute_update(
        """
        INSERT INTO articles (
            article_id, title, url, excerpt, extracted_text,
            published_date, source_name, claims_status, created_at
        ) VALUES (
            :article_id, :title, :url, :excerpt, :text,
            :published_date, :source, 'pending', NOW()
        )
        """,
        {
            "article_id": article_id,
            "title": title,
            "url": url_str,
            "excerpt": scraped_data['excerpt'],
            "text": scraped_data['text'],
            "published_date": scraped_data['published_date'],
            "source": url_str.split('/')[2]  # Extract domain as source
        }
    )

    logger.info(f"Ingested article {article_id}: {title}")

    # Schedule background enrichment (always, when text is available)
    source_domain = url_str.split('/')[2]
    if scraped_data['text']:
        background_tasks.add_task(
            _enrich_article_background,
            article_id,
            title,
            scraped_data['text'],
            source_domain,
            "XX",  # country_code not available from URL scraping; default to International
        )

    # Schedule background processing if requested
    if request.process_claims and scraped_data['text']:
        background_tasks.add_task(
            process_article_claims_background,
            article_id,
            scraped_data['text']
        )
        processing_started = True
    else:
        processing_started = False

    return IngestArticleResponse(
        article_id=article_id,
        title=title,
        url=url_str,
        status="ingested",
        message="Article successfully ingested. Claims processing started." if processing_started else "Article ingested. Claim processing not requested.",
        processing_started=processing_started
    )


@router.get("/status/{article_id}")
async def get_article_status(article_id: str):
    """Get the processing status of an article"""
    db = get_postgres()

    article = db.execute_query(
        """
        SELECT
            article_id, title, url, claims_status,
            claims_count, verified_claims_count,
            claims_processed_at, claims_error_message
        FROM articles
        WHERE article_id = :article_id
        """,
        {"article_id": article_id}
    )

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return article[0]


# ---------------------------------------------------------------------------
# Document / Research Report ingestion
# ---------------------------------------------------------------------------

_STANDARD_TIERS = {"standard", "professional"}


class IngestDocumentRequest(BaseModel):
    """Request body for document/research-report ingestion."""

    url: HttpUrl = Field(..., description="URL of the document or PDF to ingest")
    content_type: Optional[str] = Field(
        None,
        description=(
            "Override detected content type. "
            "Allowed values: news_article, research_report, preprint, policy_document"
        ),
    )
    doi: Optional[str] = Field(None, description="DOI override (e.g. 10.1038/s41586-021-03819-2)")


class IngestDocumentResponse(BaseModel):
    """Response from document ingestion."""

    article_id: str
    title: str
    url: str
    content_type: str
    doi: Optional[str]
    publication_venue: Optional[str]
    status: str
    message: str


@router.post("/ingest/document", response_model=IngestDocumentResponse)
async def ingest_document(
    request: IngestDocumentRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Ingest a research report, preprint, policy document, or PDF from a URL.

    Requires Standard tier or higher subscription. The endpoint:
    1. Downloads the document (PDF-aware).
    2. Detects content type, DOI, and publication venue.
    3. Inserts the article record with research metadata.
    4. Schedules background claim extraction.

    Returns the new article_id and detected metadata.
    """
    # Enforce Standard+ tier
    user_tier = (current_user.get("subscription_tier") or "freemium").lower()
    if user_tier not in _STANDARD_TIERS:
        raise HTTPException(
            status_code=403,
            detail=(
                "Document ingestion requires a Standard or Professional subscription. "
                f"Your current tier is '{user_tier}'."
            ),
        )

    url_str = str(request.url)
    db = get_postgres()

    # Deduplication check
    existing = db.execute_query(
        "SELECT article_id, title FROM articles WHERE url = :url",
        {"url": url_str},
    )
    if existing:
        row = existing[0]
        return IngestDocumentResponse(
            article_id=str(row["article_id"]),
            title=row["title"],
            url=url_str,
            content_type=row.get("content_type", "news_article"),
            doi=row.get("doi"),
            publication_venue=row.get("publication_venue"),
            status="exists",
            message="Document already exists in the database.",
        )

    # Download and process the document
    try:
        from app.domains.content.data_sources.document_adapter import process_document_url
        doc = await process_document_url(url_str)
    except Exception as exc:
        logger.error(f"Document processing error for {url_str}: {exc}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to download or process document: {exc}",
        )

    # Apply caller overrides
    content_type = request.content_type or doc["content_type"]
    doi = request.doi or doc.get("doi")
    publication_venue = doc.get("publication_venue")
    title = doc.get("title") or "Untitled Document"

    article_id = str(uuid.uuid4())

    db.execute_update(
        """
        INSERT INTO articles (
            article_id, title, url, excerpt, extracted_text,
            published_date, source_name, claims_status,
            content_type, doi, publication_venue,
            created_at
        ) VALUES (
            :article_id, :title, :url, :excerpt, :text,
            NOW(), :source, 'pending',
            :content_type, :doi, :publication_venue,
            NOW()
        )
        """,
        {
            "article_id": article_id,
            "title": title[:500],
            "url": url_str,
            "excerpt": doc["text"][:200],
            "text": doc["text"],
            "source": url_str.split("/")[2],
            "content_type": content_type,
            "doi": doi,
            "publication_venue": publication_venue,
        },
    )

    logger.info(
        f"Ingested document {article_id}: type={content_type} doi={doi} title={title[:80]}"
    )

    # Schedule background enrichment and claim extraction
    if doc["text"]:
        background_tasks.add_task(
            _enrich_article_background,
            article_id,
            title,
            doc["text"],
            url_str.split("/")[2],
            "XX",
        )
        background_tasks.add_task(
            process_article_claims_background,
            article_id,
            doc["text"],
        )

    return IngestDocumentResponse(
        article_id=article_id,
        title=title,
        url=url_str,
        content_type=content_type,
        doi=doi,
        publication_venue=publication_venue,
        status="ingested",
        message=(
            f"Document ingested as '{content_type}'. "
            "Claim extraction has been scheduled."
            if doc["text"]
            else f"Document ingested as '{content_type}'. No extractable text found."
        ),
    )


# ---------------------------------------------------------------------------
# File Upload — PDF, DOCX, TXT
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/html": "html",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".html"}


class UploadResponse(BaseModel):
    """Response from file upload ingestion."""
    article_id: str
    title: str
    content_type: str
    doi: Optional[str] = None
    publication_venue: Optional[str] = None
    text_length: int
    status: str
    message: str


def _extract_text_from_upload(content: bytes, filename: str, mime_type: str) -> str:
    """Extract text from uploaded file bytes based on type."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # PDF
    if ext == ".pdf" or "pdf" in mime_type:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            parts = []
            for page in reader.pages[:100]:  # Up to 100 pages
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n".join(parts)[:200000]
        except ImportError:
            raise HTTPException(500, "PDF processing library not installed (PyPDF2)")
        except Exception as e:
            raise HTTPException(422, f"Failed to extract text from PDF: {e}")

    # DOCX
    if ext == ".docx" or "wordprocessingml" in mime_type:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(io.BytesIO(content))
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(parts)[:200000]
        except ImportError:
            # Fallback: basic XML extraction without python-docx
            try:
                import zipfile
                import xml.etree.ElementTree as ET
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    xml_content = zf.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                parts = []
                for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    if p.text:
                        parts.append(p.text)
                return " ".join(parts)[:200000]
            except Exception as e:
                raise HTTPException(422, f"Failed to extract text from DOCX: {e}")
        except Exception as e:
            raise HTTPException(422, f"Failed to extract text from DOCX: {e}")

    # Plain text / markdown / HTML
    if ext in {".txt", ".md"} or "text/" in mime_type:
        try:
            return content.decode("utf-8", errors="replace")[:200000]
        except Exception:
            return content.decode("latin-1", errors="replace")[:200000]

    # HTML
    if ext == ".html" or "html" in mime_type:
        try:
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:200000]
        except Exception as e:
            raise HTTPException(422, f"Failed to extract text from HTML: {e}")

    raise HTTPException(422, f"Unsupported file type: {ext} ({mime_type})")


@router.post("/ingest/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or MD file to analyze"),
    title: Optional[str] = Form(None, description="Optional title override"),
    content_type_override: Optional[str] = Form(
        None,
        description="Override content type: research_report, policy_document, preprint, news_article",
        alias="content_type",
    ),
    country_code: Optional[str] = Form(None, description="ISO country code"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a research report, industry analysis, or any document for ingestion.

    Accepts PDF, DOCX, DOC, TXT, MD, and HTML files up to 20 MB.
    The system will:
    1. Extract text from the uploaded file
    2. Detect content type (research report, policy doc, preprint, etc.)
    3. Extract DOI if present
    4. Store the article and schedule claim extraction + scoring

    Requires authentication. Free tier allowed (limited to 2/month).
    """
    # Validate file
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            422,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.")
    if len(content) < 100:
        raise HTTPException(422, "File is too small or empty.")

    # Extract text
    mime = file.content_type or ""
    text = _extract_text_from_upload(content, file.filename, mime)
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            422,
            "Could not extract sufficient text from the file. "
            "The document may be scanned images (use OCR) or corrupted.",
        )

    # Detect content type and metadata
    from app.domains.content.data_sources.document_adapter import (
        detect_content_type, extract_doi, _detect_venue_from_doi,
    )

    detected_type = content_type_override or detect_content_type(text, file.filename)
    doi = extract_doi(text)
    publication_venue = _detect_venue_from_doi(doi) if doi else None

    # Extract title from text if not provided
    if not title:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        title = lines[0][:255] if lines else file.filename

    db = get_postgres()
    article_id = str(uuid.uuid4())
    source_url = f"upload://{file.filename}"

    # Check dedup by title similarity (files don't have URLs)
    existing = db.execute_query(
        "SELECT article_id, title FROM articles WHERE title = :title LIMIT 1",
        {"title": title},
    )
    if existing:
        row = existing[0]
        return UploadResponse(
            article_id=str(row["article_id"]),
            title=row["title"],
            content_type=detected_type,
            text_length=len(text),
            status="exists",
            message="A document with this title already exists.",
        )

    # Insert article
    db.execute_update(
        """
        INSERT INTO articles (
            article_id, title, url, excerpt, extracted_text,
            published_date, source_name, claims_status,
            content_type, doi, publication_venue,
            country_code, content_category,
            created_at, updated_at
        ) VALUES (
            :article_id, :title, :url, :excerpt, :text,
            NOW(), :source, 'pending',
            :content_type, :doi, :publication_venue,
            :country_code, :category,
            NOW(), NOW()
        )
        """,
        {
            "article_id": article_id,
            "title": title[:500],
            "url": source_url,
            "excerpt": text[:280],
            "text": text,
            "source": f"upload:{file.filename}",
            "content_type": detected_type,
            "doi": doi,
            "publication_venue": publication_venue,
            "country_code": (country_code or "XX").upper(),
            "category": detected_type,
        },
    )

    logger.info(
        f"Uploaded document {article_id}: type={detected_type} doi={doi} "
        f"text_len={len(text)} title={title[:80]}"
    )

    # Schedule background enrichment and claim extraction
    if text:
        background_tasks.add_task(
            _enrich_article_background,
            article_id,
            title,
            text,
            f"upload:{file.filename}",
            (country_code or "XX").upper(),
        )
        background_tasks.add_task(
            process_article_claims_background,
            article_id,
            text,
        )

    return UploadResponse(
        article_id=article_id,
        title=title,
        content_type=detected_type,
        doi=doi,
        publication_venue=publication_venue,
        text_length=len(text),
        status="ingested",
        message=(
            f"Document uploaded and ingested as '{detected_type}'. "
            f"Extracted {len(text):,} characters. Claim extraction scheduled."
        ),
    )
