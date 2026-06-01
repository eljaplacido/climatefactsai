"""LLM-based climate-relevance classifier (F1 — content-scope charter §3).

Why this exists: a keyword/SQL relevance sweep was measured to mis-flag ~65%
of the real corpus — truncated RSS `extracted_text` plus non-English climate
sources (ORF Klima, Reporterre, El Pais Clima …) simply don't contain the
English keywords, so even BBC/NYT Climate fail a keyword gate. Accurate
per-article relevance therefore needs an LLM that understands meaning across
languages. This module reuses the enrichment provider chain
(`ArticleEnrichmentService._call_llm`: deepseek → openai → anthropic →
local-gx10) so the same cost controls and GX10 routing apply (§8 Lane A).

The classifier is **conservative / safe-fail**: any error (LLM unreachable,
unparseable output) returns ``relevant=True`` so a genuine climate article is
never hidden by a transient failure. Off-topic hiding only happens on a
confident negative. The decision (`score` + `reason`) is persisted so it is
reviewer-traceable per the §3 charter.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.domains.content.article_enrichment_service import ArticleEnrichmentService

logger = get_logger(__name__)


RELEVANCE_SYSTEM_PROMPT = (
    "You are an editorial classifier for a climate, environment & sustainability "
    "platform. Its umbrella is broad: keep anything about the natural environment, "
    "the green transition, or sustainability. IN SCOPE:\n"
    "1. Climate science, observations, attribution, projections.\n"
    "2. Climate impacts & adaptation, extreme weather, weather/seasonal forecasts "
    "(heat, hurricanes, drought, floods, wildfires) and disaster resilience.\n"
    "3. Mitigation, decarbonisation, energy transition, cleantech, renewables.\n"
    "4. Climate & sustainability policy / regulation / finance (CSRD, SBTi, CDP, "
    "TCFD, ISSB, carbon markets).\n"
    "5. Corporate sustainability / ESG disclosure & greenwashing.\n"
    "6. Biodiversity, conservation, wildlife, nature, ecosystems, forests, land, "
    "oceans, water, pollution, waste — the environment broadly (NO explicit "
    "climate link required).\n\n"
    "OUT OF SCOPE: content with no environmental/climate/sustainability angle — "
    "generic accidents, crime, war, party politics/elections, sports, "
    "markets/economy, celebrity, entertainment, food/recipes, lifestyle, health/"
    "medicine unrelated to environment, religion, obituaries.\n\n"
    "Judge by the article's actual subject, in ANY language. Bias toward KEEPING: "
    "only mark off_topic when the subject is CLEARLY unrelated to the environment "
    "(e.g. a bus crash, an election guide, a dessert recipe, a celebrity story). "
    "When genuinely unsure, keep it (relevant=true).\n\n"
    'Respond with ONLY a compact JSON object, no prose, no code fences: '
    '{"relevant": true|false, "score": <0.0-1.0 confidence the item IS in scope>, '
    '"reason": "<=12 words"}.'
)


def _extract_json(text: str) -> Dict[str, Any]:
    """Pull the first JSON object out of an LLM reply (tolerates ``` fences,
    leading prose, reasoning preambles)."""
    if not text:
        return {}
    # First {...} block (greedy to the last } to survive nested braces).
    m = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = m.group(0) if m else text
    try:
        return json.loads(candidate)
    except Exception:
        pass
    # Last-resort: regex the fields so a near-miss reply still classifies with
    # as much signal as possible (the boolean is what matters; score/reason are
    # recovered when present).
    rel = re.search(r'"?relevant"?\s*[:=]\s*(true|false)', text, re.IGNORECASE)
    if not rel:
        return {}
    out: Dict[str, Any] = {
        "relevant": rel.group(1).lower() == "true",
        "reason": "parsed from non-JSON reply",
    }
    sc = re.search(r'"?score"?\s*[:=]\s*([01]?\.?\d+)', text)
    if sc:
        try:
            out["score"] = float(sc.group(1))
        except ValueError:
            pass
    rs = re.search(r'"?reason"?\s*[:=]\s*"([^"]{1,200})"', text)
    if rs:
        out["reason"] = rs.group(1)
    return out


class RelevanceClassifier:
    """Classifies whether an article is in scope for the climate platform.

    Holds one ``ArticleEnrichmentService`` so the LLM client/provider chain is
    reused across a batch.
    """

    def __init__(self, db: Any):
        self._svc = ArticleEnrichmentService(db)

    async def classify(
        self, title: str, excerpt: Optional[str], source_name: Optional[str]
    ) -> Dict[str, Any]:
        user_prompt = (
            f"Title: {title or '(none)'}\n"
            f"Excerpt: {(excerpt or '(none)')[:1200]}\n"
            f"Source: {source_name or 'unknown'}\n\n"
            "Is this article in scope for the climate platform?"
        )
        try:
            result = await self._svc._call_llm(
                RELEVANCE_SYSTEM_PROMPT, user_prompt, max_tokens=120
            )
        except Exception as exc:  # never let a classifier error hide content
            logger.warning("relevance classifier LLM error; safe-fail keep", error=str(exc))
            return {"relevant": True, "score": 0.5, "reason": "classifier error (kept)",
                    "llm_used": False, "error": True}

        if not result:
            return {"relevant": True, "score": 0.5, "reason": "classifier unavailable (kept)",
                    "llm_used": False, "error": True}

        text, provider, model = result
        data = _extract_json(text)
        if "relevant" not in data:
            logger.warning("relevance classifier unparseable reply; safe-fail keep",
                           reply=(text or "")[:160])
            return {"relevant": True, "score": 0.5, "reason": "unparseable reply (kept)",
                    "llm_used": True, "provider": provider, "error": True}

        try:
            score = float(data.get("score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        return {
            "relevant": bool(data["relevant"]),
            "score": max(0.0, min(1.0, score)),
            "reason": str(data.get("reason", ""))[:300],
            "llm_used": True,
            "provider": provider,
        }
