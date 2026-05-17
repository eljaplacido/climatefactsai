"""
OG Image Routes — Dynamic Open Graph images for article sharing.

Generates SVG-based OG images with article title, credibility score, and branding.
Cached in Redis with 24h TTL.
"""

import json
from typing import Any, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import Response as FastAPIResponse

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("og-image-api")
router = APIRouter(prefix="/api/og-image", tags=["OG Images"])


def _wrap_text(text: str, max_chars: int = 45) -> list[str]:
    """Wrap text into lines of max_chars length, breaking on spaces."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        lines.append(current)
    return lines[:4]  # Max 4 lines


def _score_color(score: int) -> str:
    if score >= 70:
        return "#10b981"  # emerald
    if score >= 40:
        return "#f59e0b"  # amber
    return "#ef4444"  # red


def generate_og_svg(title: str, score: int, source_name: str, category: Optional[str] = None) -> str:
    """Generate an SVG Open Graph image (1200x630)."""
    escaped_title = escape(title)
    wrapped = _wrap_text(escaped_title, 40)
    color = _score_color(score)

    # Build title lines
    title_lines = ""
    for i, line in enumerate(wrapped):
        y = 220 + i * 52
        title_lines += f'<text x="80" y="{y}" font-family="Arial, sans-serif" font-size="42" font-weight="bold" fill="#111827">{escape(line)}</text>\n'

    category_label = (category or "").replace("_", " ").title()
    category_element = ""
    if category_label:
        category_element = f'''
        <rect x="80" y="140" rx="14" ry="14" width="{len(category_label) * 11 + 24}" height="28" fill="#f0f9ff" stroke="#bae6fd" stroke-width="1"/>
        <text x="92" y="159" font-family="Arial, sans-serif" font-size="13" fill="#0369a1">{escape(category_label)}</text>
        '''

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#f8fafc"/>
    </linearGradient>
    <linearGradient id="brand" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0d9488"/>
      <stop offset="100%" stop-color="#14b8a6"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Top brand bar -->
  <rect width="1200" height="6" fill="url(#brand)"/>

  <!-- Source name -->
  <text x="80" y="100" font-family="Arial, sans-serif" font-size="18" fill="#6b7280">{escape(source_name)}</text>

  <!-- Category badge -->
  {category_element}

  <!-- Title -->
  {title_lines}

  <!-- Credibility score circle -->
  <circle cx="1060" cy="200" r="70" fill="none" stroke="#e5e7eb" stroke-width="8"/>
  <circle cx="1060" cy="200" r="70" fill="none" stroke="{color}" stroke-width="8"
    stroke-dasharray="{2 * 3.14159 * 70}" stroke-dashoffset="{2 * 3.14159 * 70 * (1 - score / 100)}"
    stroke-linecap="round" transform="rotate(-90 1060 200)"/>
  <text x="1060" y="210" font-family="Arial, sans-serif" font-size="36" font-weight="bold" fill="{color}" text-anchor="middle">{score}</text>
  <text x="1060" y="236" font-family="Arial, sans-serif" font-size="12" fill="#6b7280" text-anchor="middle">CREDIBILITY</text>

  <!-- Bottom bar -->
  <rect y="560" width="1200" height="70" fill="#0d9488"/>
  <circle cx="110" cy="595" r="18" fill="white"/>
  <text x="110" y="602" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#0d9488" text-anchor="middle">C</text>
  <text x="140" y="602" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="white">Climatefacts.ai</text>
  <text x="310" y="600" font-family="Arial, sans-serif" font-size="14" fill="#99f6e4">Climate Intelligence, Verified by AI</text>
</svg>'''

    return svg


@router.get("/{article_id}")
async def get_og_image(article_id: str):
    """
    Generate and return an SVG OG image for an article.
    Cached in Redis for 24 hours.
    """
    # Try Redis cache first
    try:
        from app.core.redis_client import get_redis
        redis = get_redis()
        cache_key = f"og_image:{article_id}"
        cached = redis.get(cache_key)
        if cached:
            return Response(content=cached, media_type="image/svg+xml")
    except Exception:
        pass  # Redis unavailable, generate fresh

    db = get_postgres()
    rows = db.execute_query(
        """SELECT title, reliability_score, source_name, content_category
           FROM articles WHERE article_id = :id""",
        {"id": article_id},
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")

    row = rows[0]
    svg = generate_og_svg(
        title=row.get("title", "Untitled"),
        score=row.get("reliability_score") or 0,
        source_name=row.get("source_name", "Unknown"),
        category=row.get("content_category"),
    )

    # Cache in Redis
    try:
        from app.core.redis_client import get_redis
        redis = get_redis()
        redis.setex(f"og_image:{article_id}", 86400, svg)
    except Exception:
        pass

    return Response(content=svg, media_type="image/svg+xml")
