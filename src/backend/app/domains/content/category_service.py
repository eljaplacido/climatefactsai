"""
Content Category Service

Detects content category for climate articles using keyword matching
with an optional LLM fallback for ambiguous cases.

Categories:
    climate_science   — peer-reviewed research, IPCC, modelling studies
    sustainability    — SDGs, ESG, corporate responsibility
    circular_economy  — waste, recycling, material flows
    green_transition  — energy transition, EVs, renewables policy
    localized_forecast— weather events, regional climate projections
    policy            — regulation, legislation, international agreements
"""

import os
import re
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Ordered so more specific patterns match before generic ones
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "circular_economy": [
        "circular economy", "recycling", "waste management", "material flow",
        "reuse", "upcycl", "lifecycle analysis", "waste-to-energy",
        "kiertotalous", "extended producer responsibility", "EPR",
    ],
    "localized_forecast": [
        "weather forecast", "temperature record", "heatwave", "cold snap",
        "flood warning", "drought", "extreme weather", "storm",
        "precipitation", "snowfall", "wildfire", "sea level rise",
        "regional climate", "local weather",
    ],
    "green_transition": [
        "green transition", "energy transition", "renewable energy",
        "solar power", "wind power", "electric vehicle", "EV", "hydrogen",
        "decarboni", "net zero", "carbon neutral", "clean energy",
        "green deal", "just transition", "vihreä siirtymä",
    ],
    "sustainability": [
        "sustainab", "ESG", "SDG", "corporate responsibility",
        "carbon footprint", "greenwash", "biodiversity", "ecosystem",
        "kestävä kehitys", "nature-based solution",
    ],
    "policy": [
        "regulation", "legislation", "treaty", "agreement", "COP",
        "EU taxonomy", "carbon tax", "emissions trading", "ETS",
        "green bond", "climate finance", "Paris Agreement",
        "Fit for 55", "CBAM", "climate law", "policy",
    ],
    "climate_science": [
        "IPCC", "climate model", "peer-reviewed", "study finds",
        "research shows", "scientific consensus", "global warming",
        "greenhouse gas", "carbon dioxide", "methane", "sea ice",
        "paleoclimate", "climate sensitivity", "attribution",
        "ilmastonmuutos", "climate change",
    ],
}

VALID_CATEGORIES = list(CATEGORY_KEYWORDS.keys())


def detect_category(
    title: str,
    text: str = "",
    tags: Optional[list[str]] = None,
) -> str:
    """
    Detect the content category of a climate article.

    Uses weighted keyword matching against title (3x weight),
    text body (1x), and tags (2x). Returns the best-matching
    category or 'climate_science' as the default fallback.

    Args:
        title: Article title
        text:  Article body text (first ~2000 chars recommended)
        tags:  Article tags

    Returns:
        Category string from VALID_CATEGORIES
    """
    corpus_title = (title or "").lower()
    corpus_text = (text[:2000] if text else "").lower()
    corpus_tags = " ".join(tags or []).lower()

    scores: dict[str, float] = {cat: 0.0 for cat in VALID_CATEGORIES}

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            # Title matches are worth 3x
            if kw_lower in corpus_title:
                scores[category] += 3.0
            # Text body matches worth 1x
            if kw_lower in corpus_text:
                scores[category] += 1.0
            # Tag matches worth 2x
            if kw_lower in corpus_tags:
                scores[category] += 2.0

    best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_category]

    if best_score < 1.0:
        # No meaningful match — default to climate_science
        return "climate_science"

    logger.debug(
        "Category detected",
        category=best_category,
        score=best_score,
        title=title[:60],
    )
    return best_category


def get_category_prompt_variant(category: str) -> str:
    """
    Return a prompt instruction variant tailored to the given content category.

    Used by the AnalysisArticleGenerator to adjust tone and framing.

    Args:
        category: One of VALID_CATEGORIES

    Returns:
        Prompt instruction string (may be empty for unknown categories).
    """
    variants = {
        "climate_science": (
            "Focus on scientific rigour. Reference specific datasets, confidence "
            "intervals, and methodological strengths/weaknesses. Distinguish "
            "between established consensus and emerging findings."
        ),
        "policy": (
            "Frame around regulatory and political context. Identify affected "
            "stakeholders, policy timelines, and implementation challenges. "
            "Reference relevant EU directives or national legislation."
        ),
        "sustainability": (
            "Emphasize measurable outcomes and framework alignment (SDGs, EU "
            "Taxonomy, CSRD). Assess claims against recognised sustainability "
            "standards and corporate reporting requirements."
        ),
        "circular_economy": (
            "Analyse through material flow and lifecycle perspectives. Assess "
            "economic viability and scale potential. Reference the EU Circular "
            "Economy Action Plan and waste hierarchy principles."
        ),
        "green_transition": (
            "Focus on transition readiness, technology maturity (TRL), and "
            "investment requirements. Assess timeline feasibility against "
            "national/EU targets. Consider social equity impacts."
        ),
        "localized_forecast": (
            "Compare claims against verifiable meteorological data from "
            "Open-Meteo and Copernicus. Distinguish weather from climate. "
            "Provide seasonal and regional context for the reader."
        ),
    }
    return variants.get(category, "")


# Category display metadata for the frontend
CATEGORY_DISPLAY: dict[str, dict[str, str]] = {
    "climate_science": {"label": "Climate Science", "icon": "beaker", "color": "blue"},
    "sustainability": {"label": "Sustainability", "icon": "leaf", "color": "green"},
    "circular_economy": {"label": "Circular Economy", "icon": "recycle", "color": "emerald"},
    "green_transition": {"label": "Green Transition", "icon": "zap", "color": "yellow"},
    "localized_forecast": {"label": "Local Forecast", "icon": "cloud-sun", "color": "cyan"},
    "policy": {"label": "Policy & Regulation", "icon": "landmark", "color": "purple"},
}
