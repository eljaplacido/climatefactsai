"""
Export Routes - PDF and CSV Export (Professional+ Feature)

Allows Professional and Enterprise users to export articles and search results.
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import csv
import io
import json

from fastapi import APIRouter, HTTPException, Depends, Response, Query
from pydantic import BaseModel, Field

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ModuleNotFoundError:
    # PDF export is optional; when reportlab is missing we disable PDF routes gracefully
    REPORTLAB_AVAILABLE = False

from api.auth_routes import get_current_user
from api.rate_limiter import check_premium_feature
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("export-api")
router = APIRouter(prefix="/api/export", tags=["Export"])

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ExportRequest(BaseModel):
    """Request to export data"""
    format: str = Field(..., pattern="^(pdf|csv)$", description="Export format")
    article_ids: Optional[List[str]] = Field(None, description="Specific article IDs to export")
    search_query: Optional[dict] = Field(None, description="Search parameters to export results")


class ExportHistory(BaseModel):
    """Export history record"""
    id: str
    export_type: str  # article, search_results
    format: str  # pdf, csv
    item_count: int
    file_size_bytes: Optional[int] = None
    created_at: datetime
    download_url: Optional[str] = None


# =============================================================================
# PDF EXPORT UTILITIES
# =============================================================================

def create_article_pdf(article_data: dict) -> bytes:
    """
    Create a PDF document for a single article.

    Args:
        article_data: Article data with claims and fact-checks

    Returns:
        PDF bytes
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF export is not available (reportlab not installed)")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch)

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=10
    )

    body_style = styles['BodyText']
    body_style.fontSize = 11
    body_style.leading = 14

    # Build content
    story = []

    # Title
    title = Paragraph(article_data.get('title', 'Untitled'), title_style)
    story.append(title)
    story.append(Spacer(1, 0.2*inch))

    # Metadata
    score = article_data.get('reliability_score') or 0
    metadata_data = [
        ['Source:', article_data.get('source_name', 'Unknown')],
        ['Published:', str(article_data.get('published_at', 'N/A'))],
        ['Country:', article_data.get('country_code', 'N/A')],
        ['Credibility:', f"{article_data.get('overall_credibility', 'N/A')} ({score}/100)"]
    ]

    metadata_table = Table(metadata_data, colWidths=[1.5*inch, 4.5*inch])
    metadata_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#4a5568')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(metadata_table)
    story.append(Spacer(1, 0.3*inch))

    # Article content
    full_text = article_data.get('extracted_text') or article_data.get('excerpt') or ''
    if full_text:
        story.append(Paragraph('Article Summary', heading_style))
        content = Paragraph(full_text[:1000], body_style)
        story.append(content)
        story.append(Spacer(1, 0.2*inch))

    # Fact-checks
    fact_checks = article_data.get('fact_checks', [])
    if fact_checks:
        story.append(Paragraph(f'Fact-Checks ({len(fact_checks)})', heading_style))
        story.append(Spacer(1, 0.1*inch))

        for i, fc in enumerate(fact_checks[:10], 1):  # Limit to 10
            claim_text = f"<b>Claim {i}:</b> {fc.get('claim_text', 'N/A')}"
            story.append(Paragraph(claim_text, body_style))

            verdict = (fc.get('verification_status') or 'unknown').upper()
            verdict_color = {
                'VERIFIED': colors.green,
                'FALSE': colors.red,
                'PARTIALLY TRUE': colors.orange,
                'DISPUTED': colors.grey
            }.get(verdict, colors.grey)

            verdict_text = f"<font color='{verdict_color.hexval()}'>Status: {verdict}</font>"
            story.append(Paragraph(verdict_text, body_style))

            confidence = fc.get('confidence_score') or 0
            story.append(Paragraph(f"Confidence: {confidence:.0%}", body_style))

            story.append(Spacer(1, 0.15*inch))

    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer = Paragraph(
        f"Generated by Climatefacts.ai on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        ParagraphStyle('Footer', parent=body_style, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    )
    story.append(footer)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def create_search_results_csv(articles: List[dict]) -> str:
    """
    Create CSV export of search results.

    Args:
        articles: List of article dictionaries

    Returns:
        CSV string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        'ID',
        'Title',
        'Source',
        'Published Date',
        'Country',
        'Credibility Level',
        'Reliability Score',
        'URL'
    ])

    # Data rows
    for article in articles:
        writer.writerow([
            article.get('article_id', ''),
            article.get('title', ''),
            article.get('source_name', ''),
            article.get('published_at', ''),
            article.get('country_code', ''),
            article.get('overall_credibility', ''),
            article.get('reliability_score', 0) or 0,
            article.get('source_url', '')
        ])

    return output.getvalue()


# =============================================================================
# EXPORT ENDPOINTS
# =============================================================================

@router.post("/article/{article_id}/pdf")
async def export_article_pdf(
    article_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Export a single article as PDF (Professional+ only).

    Returns a PDF document containing:
    - Article metadata
    - Full content
    - Fact-check results with sources
    - Credibility assessment
    """
    # Check that PDF support is available
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF export is not available in this environment"
        )

    # Check premium feature access
    if not check_premium_feature(current_user, "export"):
        raise HTTPException(
            status_code=403,
            detail="PDF export requires Professional or Enterprise subscription"
        )

    db = get_postgres()

    # Fetch article
    rows = db.execute_query(
        """
        SELECT
            a.article_id, a.title, a.source_url, a.source_name, a.published_at,
            a.extracted_text, a.excerpt, a.country_code,
            a.reliability_score, a.overall_credibility
        FROM articles a
        WHERE a.article_id = :article_id AND a.is_synthetic = FALSE
        """,
        {"article_id": article_id}
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    article = rows[0]

    # Fetch fact-checks
    fact_checks = db.execute_query(
        """
        SELECT
            c.claim_text,
            fc.verification_status,
            fc.confidence_score
        FROM fact_checks fc
        JOIN claims c ON fc.claim_id = c.claim_id
        WHERE c.article_id = :article_id
        ORDER BY fc.confidence_score DESC
        """,
        {"article_id": article_id}
    )

    # Prepare data
    article_data = dict(article)
    article_data['fact_checks'] = [dict(fc) for fc in fact_checks]

    try:
        # Generate PDF
        pdf_bytes = create_article_pdf(article_data)

        # Log export
        db.execute_update(
            """
            INSERT INTO user_usage (
                usage_id, user_id, usage_type, resource_id, metadata, created_at
            ) VALUES (:usage_id, :user_id, 'export_pdf', :resource_id, :metadata, NOW())
            """,
            {
                "usage_id": str(uuid4()),
                "user_id": current_user["user_id"],
                "resource_id": article_id,
                "metadata": json.dumps({"article_id": article_id}),
            }
        )

        logger.info(f"Article {article_id} exported to PDF by user {current_user['user_id']}")

        # Return PDF
        filename = f"clilens_article_{article_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF")


@router.post("/article/{article_id}/csv")
async def export_article_csv(
    article_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Export a single article's metadata as CSV (Professional+ only).

    One-row CSV with the same columns as search-results CSV, useful for
    researcher / journalist note-taking and reference management.
    """
    if not check_premium_feature(current_user, "export"):
        raise HTTPException(
            status_code=403,
            detail="CSV export requires Professional or Enterprise subscription",
        )

    db = get_postgres()
    rows = db.execute_query(
        """
        SELECT article_id, title, source_name, published_at, country_code,
               overall_credibility, reliability_score, source_url
        FROM articles
        WHERE article_id = :article_id AND is_synthetic = FALSE
        """,
        {"article_id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    csv_text = create_search_results_csv([dict(rows[0])])

    db.execute_update(
        """
        INSERT INTO user_usage (
            usage_id, user_id, usage_type, resource_id, metadata, created_at
        ) VALUES (:usage_id, :user_id, 'export_csv', :resource_id, :metadata, NOW())
        """,
        {
            "usage_id": str(uuid4()),
            "user_id": current_user["user_id"],
            "resource_id": article_id,
            "metadata": json.dumps({"article_id": article_id, "scope": "single"}),
        },
    )

    filename = f"clilens_article_{article_id[:8]}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/search/csv")
async def export_search_csv(
    country: Optional[str] = Query(None),
    credibility_level: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """
    Export search results as CSV (Professional+ only).

    Returns a CSV file with article data matching the search criteria.

    **Max 1000 articles per export.**
    """
    # Check premium feature access
    if not check_premium_feature(current_user, "export"):
        raise HTTPException(
            status_code=403,
            detail="CSV export requires Professional or Enterprise subscription"
        )

    db = get_postgres()

    # Build query with named params
    query = """
        SELECT
            article_id, title, source_name, published_at, country_code,
            overall_credibility, reliability_score, source_url
        FROM articles
        WHERE is_synthetic = FALSE
    """
    params = {}

    if country:
        query += " AND country_code = :country"
        params["country"] = country

    if credibility_level:
        query += " AND overall_credibility = :credibility"
        params["credibility"] = credibility_level

    if date_from:
        query += " AND published_at >= :date_from"
        params["date_from"] = date_from

    if date_to:
        query += " AND published_at <= :date_to"
        params["date_to"] = date_to

    query += " ORDER BY published_at DESC LIMIT :lim"
    params["lim"] = limit

    # Fetch articles
    articles = db.execute_query(query, params)

    if not articles:
        raise HTTPException(status_code=404, detail="No articles found matching criteria")

    try:
        # Generate CSV
        csv_content = create_search_results_csv(articles)

        # Log export
        db.execute_update(
            """
            INSERT INTO user_usage (
                usage_id, user_id, usage_type, metadata, created_at
            ) VALUES (:usage_id, :user_id, 'export_csv', :metadata, NOW())
            """,
            {
                "usage_id": str(uuid4()),
                "user_id": current_user["user_id"],
                "metadata": json.dumps({"article_count": len(articles)}),
            }
        )

        logger.info(f"{len(articles)} articles exported to CSV by user {current_user['user_id']}")

        # Return CSV
        filename = f"clilens_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Error generating CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate CSV")


@router.get("/history", response_model=List[ExportHistory])
async def get_export_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get export history for the current user.

    Returns list of past exports with metadata.
    """
    # Check premium feature access
    if not check_premium_feature(current_user, "export"):
        raise HTTPException(
            status_code=403,
            detail="Export history requires Professional or Enterprise subscription"
        )

    db = get_postgres()

    results = db.execute_query(
        """
        SELECT
            usage_id, usage_type, metadata, created_at
        FROM user_usage
        WHERE user_id = :user_id
          AND usage_type LIKE 'export%'
        ORDER BY created_at DESC
        LIMIT :lim
        """,
        {"user_id": current_user["user_id"], "lim": limit}
    )

    history = []
    for row in results:
        metadata = row.get('metadata') or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        export_type = 'article' if 'article_id' in metadata else 'search_results'
        format_type = 'pdf' if 'pdf' in (row.get('usage_type') or '') else 'csv'

        history.append(ExportHistory(
            id=str(row['usage_id']),
            export_type=export_type,
            format=format_type,
            item_count=metadata.get('article_count', 1),
            created_at=row['created_at']
        ))

    return history
