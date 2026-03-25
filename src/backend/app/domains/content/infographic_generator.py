"""
Infographic Generator — Programmatic SVG infographic creation.

Generates visual summary cards, claim breakdowns, and confidence radars
using svgwrite-compatible string templates with CliLens brand colors.
"""

from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from app.core.logging import get_logger

logger = get_logger(__name__)

# CliLens brand palette
BRAND = {
    "primary": "#0d9488",
    "teal_600": "#0d9488",
    "teal_100": "#ccfbf1",
    "bg": "#f8fafc",
    "text": "#111827",
    "muted": "#6b7280",
    "emerald": "#10b981",
    "amber": "#f59e0b",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "purple": "#8b5cf6",
}


def _score_color(score: int) -> str:
    if score >= 70:
        return BRAND["emerald"]
    if score >= 40:
        return BRAND["amber"]
    return BRAND["red"]


def _credibility_label(level: str) -> str:
    return {"HIGH": "High", "MEDIUM": "Moderate", "LOW": "Low"}.get(level, "Unknown")


def _wrap_text(text: str, max_chars: int = 50) -> list[str]:
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
    return lines[:3]


def generate_article_infographic(
    article_data: Dict[str, Any],
    template: str = "summary",
) -> str:
    """
    Generate an SVG infographic for an article.

    Args:
        article_data: Dict with title, score, source_name, category,
                      claim_count, verified_count, credibility, brief.
        template: "summary" | "claims" | "confidence"

    Returns:
        SVG string
    """
    generators = {
        "summary": _generate_summary,
        "claims": _generate_claims,
        "confidence": _generate_confidence,
    }

    generator = generators.get(template, _generate_summary)
    try:
        return generator(article_data)
    except Exception as e:
        logger.error(f"Infographic generation failed ({template}): {e}")
        return _generate_fallback(article_data)


def _generate_summary(data: Dict) -> str:
    """Summary overview card (800x500)."""
    title = escape(data.get("title", "Untitled"))
    score = data.get("score", 0)
    source = escape(data.get("source_name", "Unknown"))
    category = (data.get("category") or "").replace("_", " ").title()
    claim_count = data.get("claim_count", 0)
    verified = data.get("verified_count", 0)
    credibility = data.get("credibility", "UNKNOWN")
    brief = escape((data.get("brief") or "")[:200])

    color = _score_color(score)
    title_lines = _wrap_text(title, 40)
    title_svg = ""
    for i, line in enumerate(title_lines):
        y = 100 + i * 30
        title_svg += f'<text x="40" y="{y}" font-family="Arial, sans-serif" font-size="22" font-weight="bold" fill="{BRAND["text"]}">{escape(line)}</text>\n'

    rate = round((verified / claim_count * 100) if claim_count > 0 else 0)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">
  <rect width="800" height="500" rx="16" fill="{BRAND["bg"]}"/>
  <rect width="800" height="6" fill="{BRAND["primary"]}"/>

  <!-- Source & Category -->
  <text x="40" y="50" font-family="Arial, sans-serif" font-size="14" fill="{BRAND["muted"]}">{source}</text>
  <text x="40" y="70" font-family="Arial, sans-serif" font-size="12" fill="{BRAND["primary"]}">{escape(category)}</text>

  <!-- Title -->
  {title_svg}

  <!-- Score circle -->
  <circle cx="700" cy="110" r="55" fill="none" stroke="#e5e7eb" stroke-width="6"/>
  <circle cx="700" cy="110" r="55" fill="none" stroke="{color}" stroke-width="6"
    stroke-dasharray="{2 * 3.14159 * 55}" stroke-dashoffset="{2 * 3.14159 * 55 * (1 - score / 100)}"
    stroke-linecap="round" transform="rotate(-90 700 110)"/>
  <text x="700" y="118" font-family="Arial, sans-serif" font-size="28" font-weight="bold" fill="{color}" text-anchor="middle">{score}</text>
  <text x="700" y="140" font-family="Arial, sans-serif" font-size="10" fill="{BRAND["muted"]}" text-anchor="middle">{_credibility_label(credibility)}</text>

  <!-- Metrics bar -->
  <rect x="40" y="220" width="720" height="1" fill="#e5e7eb"/>

  <text x="40" y="260" font-family="Arial, sans-serif" font-size="32" font-weight="bold" fill="{BRAND["text"]}">{claim_count}</text>
  <text x="40" y="280" font-family="Arial, sans-serif" font-size="12" fill="{BRAND["muted"]}">Claims Assessed</text>

  <text x="200" y="260" font-family="Arial, sans-serif" font-size="32" font-weight="bold" fill="{BRAND["emerald"]}">{verified}</text>
  <text x="200" y="280" font-family="Arial, sans-serif" font-size="12" fill="{BRAND["muted"]}">Verified</text>

  <text x="360" y="260" font-family="Arial, sans-serif" font-size="32" font-weight="bold" fill="{BRAND["primary"]}">{rate}%</text>
  <text x="360" y="280" font-family="Arial, sans-serif" font-size="12" fill="{BRAND["muted"]}">Verification Rate</text>

  <!-- Brief -->
  <text x="40" y="340" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["muted"]}">{brief[:100]}</text>

  <!-- Branding -->
  <rect y="460" width="800" height="40" rx="0" fill="{BRAND["primary"]}"/>
  <text x="40" y="486" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="white">CliLens.AI</text>
  <text x="170" y="484" font-family="Arial, sans-serif" font-size="12" fill="#99f6e4">Climate Intelligence, Verified by AI</text>
</svg>'''


def _generate_claims(data: Dict) -> str:
    """Claim verification breakdown (800x400)."""
    claim_count = data.get("claim_count", 0)
    verified = data.get("verified_count", 0)
    disputed = max(0, claim_count - verified)
    title = escape(data.get("title", "Untitled")[:60])

    v_width = (verified / max(claim_count, 1)) * 500
    d_width = (disputed / max(claim_count, 1)) * 500

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400">
  <rect width="800" height="400" rx="16" fill="{BRAND["bg"]}"/>
  <rect width="800" height="6" fill="{BRAND["primary"]}"/>

  <text x="40" y="50" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="{BRAND["text"]}">Claim Verification Breakdown</text>
  <text x="40" y="75" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["muted"]}">{title}</text>

  <!-- Bar chart -->
  <rect x="140" y="120" width="{v_width}" height="40" rx="6" fill="{BRAND["emerald"]}"/>
  <text x="120" y="146" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["text"]}" text-anchor="end">Verified</text>
  <text x="{145 + v_width}" y="146" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="{BRAND["emerald"]}">{verified}</text>

  <rect x="140" y="180" width="{d_width}" height="40" rx="6" fill="{BRAND["amber"]}"/>
  <text x="120" y="206" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["text"]}" text-anchor="end">Other</text>
  <text x="{145 + d_width}" y="206" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="{BRAND["amber"]}">{disputed}</text>

  <!-- Total -->
  <text x="40" y="280" font-family="Arial, sans-serif" font-size="40" font-weight="bold" fill="{BRAND["text"]}">{claim_count}</text>
  <text x="40" y="305" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["muted"]}">Total Claims</text>

  <!-- Branding -->
  <rect y="360" width="800" height="40" fill="{BRAND["primary"]}"/>
  <text x="40" y="386" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="white">CliLens.AI</text>
</svg>'''


def _generate_confidence(data: Dict) -> str:
    """Confidence score card (800x400)."""
    score = data.get("score", 0)
    color = _score_color(score)
    title = escape(data.get("title", "Untitled")[:60])

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400">
  <rect width="800" height="400" rx="16" fill="{BRAND["bg"]}"/>
  <rect width="800" height="6" fill="{BRAND["primary"]}"/>

  <text x="40" y="50" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="{BRAND["text"]}">Confidence Assessment</text>
  <text x="40" y="75" font-family="Arial, sans-serif" font-size="13" fill="{BRAND["muted"]}">{title}</text>

  <!-- Large score -->
  <circle cx="400" cy="220" r="90" fill="none" stroke="#e5e7eb" stroke-width="10"/>
  <circle cx="400" cy="220" r="90" fill="none" stroke="{color}" stroke-width="10"
    stroke-dasharray="{2 * 3.14159 * 90}" stroke-dashoffset="{2 * 3.14159 * 90 * (1 - score / 100)}"
    stroke-linecap="round" transform="rotate(-90 400 220)"/>
  <text x="400" y="232" font-family="Arial, sans-serif" font-size="52" font-weight="bold" fill="{color}" text-anchor="middle">{score}</text>
  <text x="400" y="258" font-family="Arial, sans-serif" font-size="14" fill="{BRAND["muted"]}" text-anchor="middle">Credibility Score</text>

  <!-- Branding -->
  <rect y="360" width="800" height="40" fill="{BRAND["primary"]}"/>
  <text x="40" y="386" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="white">CliLens.AI</text>
</svg>'''


def _generate_fallback(data: Dict) -> str:
    """Fallback SVG when generation fails."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400">
  <rect width="800" height="400" rx="16" fill="#f8fafc"/>
  <text x="400" y="200" font-family="Arial, sans-serif" font-size="18" fill="#6b7280" text-anchor="middle">Infographic unavailable</text>
</svg>'''
