"""
Analysis Article Generator

Generates publication-ready Perplexity-style analysis articles from verification results.
Produces structured markdown with embedded KPIs: executive summary, key claims assessment,
evidence summary, regional context, confidence breakdown, and methodology note.
Converts markdown to HTML using the `markdown` library.
"""

import json
import os
from typing import Optional

import markdown as md

from app.core.logging import get_logger
from app.domains.intelligence.llm_client import get_llm_client, llm_chat

logger = get_logger(__name__)

# Markdown extensions for rich HTML output
_MD_EXTENSIONS = ["tables", "fenced_code", "nl2br", "smarty", "sane_lists"]


class AnalysisArticleGenerator:
    """
    Generates structured analysis articles from verification results using DeepSeek.

    Output format is markdown converted to styled HTML suitable for rendering
    in the frontend article detail view.
    """

    def __init__(self, model: str = "deepseek-chat"):
        self.llm_client, self.llm_model = get_llm_client()
        self.model = self.llm_model or model
        # Backwards compatibility
        self.client = self.llm_client

    async def generate(
        self,
        article_title: str,
        article_text: str,
        claims: list[dict],
        verdicts: list[dict],
        decomposed_confidence: Optional[dict] = None,
        reliability_breakdown: Optional[dict] = None,
        country_code: str = "FI",
        content_category: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """
        Generate a structured Perplexity-style analysis article (1200-1800 words).

        Args:
            article_title: Original article title
            article_text: Original article text (truncated to 6000 chars)
            claims: List of extracted claims with categories
            verdicts: List of verdicts with confidence scores
            decomposed_confidence: CARF-style confidence breakdown
            reliability_breakdown: Factor-by-factor reliability scores
            country_code: Country context for localization
            content_category: Content category for prompt variant tuning
            temperature: LLM temperature for creativity control (0.0-1.0)

        Returns:
            Markdown string of the analysis article, or None on failure.
        """
        if not self.llm_client:
            logger.warning("No LLM client available for article generation (DEEPSEEK_API_KEY not set)")
            return None

        # Compute KPIs
        total_claims = len(claims)
        verified_count = sum(1 for v in verdicts if v.get("verdict") in ("verified", "true"))
        disputed_count = sum(1 for v in verdicts if v.get("verdict") in ("disputed", "false"))
        unverified_count = total_claims - verified_count - disputed_count

        avg_confidence = 0.0
        if verdicts:
            scores = [v.get("confidence_score", 0) for v in verdicts]
            avg_confidence = sum(scores) / len(scores)

        # Build claims by category summary
        categories: dict[str, int] = {}
        for c in claims:
            cat = c.get("claim_category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        # Build evidence chain summary
        evidence_sources: set[str] = set()
        for v in verdicts:
            for ev in v.get("supporting_evidence", []):
                evidence_sources.add(ev.get("source", "Unknown"))
            for ev in v.get("contradicting_evidence", []):
                evidence_sources.add(ev.get("source", "Unknown"))

        # Get category-specific framing instructions
        category_instructions = self._get_category_framing(content_category)

        # Build prompt
        prompt = f"""You are a senior climate intelligence analyst writing a comprehensive, \
Perplexity-style analysis article for CliLens.AI.

ORIGINAL ARTICLE TITLE: {article_title}

ORIGINAL ARTICLE EXCERPT:
{article_text[:6000]}

VERIFICATION RESULTS:
- Total claims extracted: {total_claims}
- Verified: {verified_count}
- Disputed: {disputed_count}
- Unverified: {unverified_count}
- Average confidence: {avg_confidence:.1%}
- Claims by category: {json.dumps(categories)}
- Evidence sources used: {', '.join(evidence_sources) if evidence_sources else 'LLM knowledge base'}
- Country context: {country_code}

DECOMPOSED CONFIDENCE:
{json.dumps(decomposed_confidence, indent=2) if decomposed_confidence else 'Not available'}

RELIABILITY BREAKDOWN:
{json.dumps(reliability_breakdown, indent=2) if reliability_breakdown else 'Not available'}

CLAIMS AND VERDICTS:
{self._format_claims_verdicts(claims, verdicts)}

{category_instructions}

Generate a structured analysis article in Markdown format with these EXACT sections:

## Executive Summary
3-5 sentences providing a clear, authoritative overview of the credibility assessment. \
State the overall verdict, key metrics, and one headline finding.

## Key Claims Assessment

A markdown table with columns: | Claim | Category | Verdict | Confidence |
Include ALL claims. Use emoji indicators: ✅ verified, ⚠️ disputed, ❓ unverified.

## Why This Matters

2-3 paragraphs explaining the real-world significance of these findings. How does this \
affect policy, public understanding, or climate action? Connect to broader trends.

## Evidence Summary

For each major claim, describe the evidence found and from which sources. Be specific \
about what was confirmed vs. what remains uncertain.

## Regional Context

How do these findings relate to the {country_code} region specifically? Reference local \
climate trends, policies, or conditions. Connect to European and global context.

## Confidence Breakdown

If decomposed confidence data is available, present each factor as a structured callout:

> **Model Confidence**: [score]% — [brief interpretation]
> **Source Quality**: [score]% — [brief interpretation]
> **Evidence Breadth**: [score]% — [brief interpretation]
> **Cross-Reference Score**: [score]% — [brief interpretation]
> **Temporal Relevance**: [score]% — [brief interpretation]
> **Overall Confidence**: [score]%

## What To Watch

3-5 bullet points of developments to monitor. What upcoming data, policy decisions, \
or scientific publications could change this assessment?

## Source Assessment

Rate the original article's source credibility and note any biases or limitations \
detected in editorial approach, sourcing, or framing.

## Methodology Note

Brief explanation that this analysis was performed by CliLens.AI using multi-source \
verification including climate APIs (Open-Meteo, Copernicus), fact-check databases, \
and AI-assisted reasoning. Note any limitations.

---

REQUIREMENTS:
- Be factual and balanced, avoid alarmist language
- Use specific numbers and data points from the verification results
- If confidence is low, clearly state uncertainties
- Write in professional but accessible English
- The article should be 1200-1800 words of substantive analysis
- Each section must contain at least one full paragraph of detail
- Use structured callout blocks (>) for KPIs and key metrics
- Return ONLY the markdown content, no wrapping or explanation"""

        try:
            article_md = llm_chat(
                prompt,
                max_tokens=4000,
                temperature=temperature,
                client=self.llm_client,
                model=self.llm_model,
            )

            if article_md:
                article_md = article_md.strip()
                logger.info(
                    "Generated analysis article",
                    title=article_title[:50],
                    length=len(article_md),
                    category=content_category,
                )
                return article_md

            return None

        except Exception as e:
            logger.error(f"Analysis article generation failed: {e}")
            return None

    async def generate_executive_brief(
        self,
        article_title: str,
        claims: list[dict],
        verdicts: list[dict],
        avg_confidence: Optional[float] = None,
    ) -> Optional[str]:
        """
        Generate a 2-3 sentence executive brief for article card previews.

        Args:
            article_title: Original article title
            claims: Extracted claims
            verdicts: Claim verdicts
            avg_confidence: Pre-computed average confidence

        Returns:
            Brief text string or None on failure.
        """
        if not self.llm_client:
            return None

        total = len(claims)
        verified = sum(1 for v in verdicts if v.get("verdict") in ("verified", "true"))
        disputed = sum(1 for v in verdicts if v.get("verdict") in ("disputed", "false"))

        if avg_confidence is None and verdicts:
            scores = [v.get("confidence_score", 0) for v in verdicts]
            avg_confidence = sum(scores) / len(scores)

        try:
            result = llm_chat(
                f"Write a 2-3 sentence executive brief for a climate article analysis.\n"
                f"Title: {article_title}\n"
                f"Claims: {total} total, {verified} verified, {disputed} disputed\n"
                f"Confidence: {avg_confidence:.0%}\n\n"
                f"Be concise, factual, and authoritative. State the key finding and "
                f"overall credibility verdict. Return ONLY the brief text.",
                max_tokens=200,
                temperature=0.2,
                client=self.llm_client,
                model=self.llm_model,
            )
            if result:
                return result.strip()
            return None
        except Exception as e:
            logger.warning(f"Executive brief generation failed: {e}")
            return None

    def _get_category_framing(self, category: Optional[str]) -> str:
        """Get category-specific prompt instructions for tone and framing."""
        if not category:
            return ""

        variants = {
            "climate_science": (
                "CATEGORY FRAMING: This is a scientific article. Use precise scientific "
                "terminology, reference specific datasets and methodologies, and distinguish "
                "between established consensus and emerging research. Cite uncertainty ranges."
            ),
            "policy": (
                "CATEGORY FRAMING: This is a policy-oriented article. Frame analysis around "
                "stakeholder impacts, regulatory implications, and implementation feasibility. "
                "Identify which actors are affected and what decisions hinge on these claims."
            ),
            "sustainability": (
                "CATEGORY FRAMING: This focuses on sustainability practices. Emphasize "
                "measurable outcomes, lifecycle considerations, and scalability. Compare "
                "claims against established sustainability frameworks (SDGs, EU Taxonomy)."
            ),
            "circular_economy": (
                "CATEGORY FRAMING: This covers circular economy topics. Assess claims "
                "through material flow analysis, waste reduction metrics, and economic "
                "viability. Reference EU Circular Economy Action Plan where relevant."
            ),
            "green_transition": (
                "CATEGORY FRAMING: This addresses green transition topics. Focus on "
                "transition timelines, technology readiness levels, investment requirements, "
                "and social equity considerations. Reference national and EU targets."
            ),
            "localized_forecast": (
                "CATEGORY FRAMING: This involves localized climate forecasts. Compare "
                "claims against Open-Meteo and Copernicus data for the region. Distinguish "
                "between weather events and climate trends. Note seasonal context."
            ),
        }
        return variants.get(category, "")

    def _format_claims_verdicts(self, claims: list[dict], verdicts: list[dict]) -> str:
        """Format claims and their verdicts for the prompt."""
        lines = []
        for i, claim in enumerate(claims):
            verdict = verdicts[i] if i < len(verdicts) else {}
            lines.append(
                f"{i+1}. CLAIM: {claim.get('claim_text', 'N/A')}\n"
                f"   Category: {claim.get('claim_category', 'unknown')}\n"
                f"   Verdict: {verdict.get('verdict', 'unverified')}\n"
                f"   Confidence: {verdict.get('confidence_score', 0):.0%}\n"
                f"   Justification: {verdict.get('justification', 'N/A')[:200]}\n"
            )
        return "\n".join(lines) if lines else "No claims extracted."

    async def generate_html(self, markdown_content: str) -> str:
        """
        Convert generated markdown to HTML using the `markdown` library.

        Falls back to wrapping in <pre> if conversion fails.
        """
        try:
            html = md.markdown(
                markdown_content,
                extensions=_MD_EXTENSIONS,
                output_format="html5",
            )
            return html
        except Exception as e:
            logger.warning(f"HTML conversion failed, returning pre-wrapped markdown: {e}")
            return f"<pre>{markdown_content}</pre>"
