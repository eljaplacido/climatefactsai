"""Prompt registry — Phase 4 wave 1.

Centralises every LLM prompt the platform uses so each is:

  * **Versioned** — `version` bumps on every meaningful template change,
    so old outputs remain reproducible by re-running the same version.
  * **Fingerprinted** — `fingerprint` is a content-hash of the template,
    surfaced in audit trails. Two responses with the same fingerprint
    came from byte-identical prompts; any drift is visible immediately.
  * **Documented** — `description` + `rationale` capture WHAT this prompt
    is for and WHY this version was chosen. Future revisions read the
    rationale before changing the wording.
  * **Inspectable** — the entire prompt corpus is one Python module that
    a reviewer can scroll through. No prompts hidden in f-strings deep
    in business logic.

Every LLM call site should resolve its prompt via `get_prompt(name)` and
record the returned `version` (and ideally `fingerprint`) in its output
metadata. The methodology drawer / audit-trail endpoint surfaces these to
users as part of the traceability axis of the truth-machine grade.

## Version-bump policy

  * **Patch (v1.0 → v1.0.1)**: cosmetic — formatting, whitespace, punctuation.
    Existing outputs are still reproducible against the new version.
  * **Minor (v1.0 → v1.1)**: tone/clarity change, added instructions, but
    the same task with the same expected output shape.
  * **Major (v1.0 → v2.0)**: changed task, changed expected output shape,
    or changed downstream parsing logic.

Old version constants are NOT deleted when a new one ships — keep the
old `PromptTemplate` instance around so historical scores can still cite it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PromptTemplate:
    """One versioned prompt template.

    `template` and `system` use `str.format`-style placeholders. Caller is
    responsible for passing the right kwargs; `format` enforces that all
    placeholders are filled.
    """
    name: str
    version: str
    template: str
    description: str
    rationale: str
    system: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    @property
    def fingerprint(self) -> str:
        """Stable 16-hex-char content hash. Changes any time `template` or
        `system` does — surfaces in audit trails so prompt drift is visible
        even if `version` was forgotten."""
        h = hashlib.sha256()
        h.update(self.template.encode("utf-8"))
        if self.system:
            h.update(b"\x00")
            h.update(self.system.encode("utf-8"))
        return h.hexdigest()[:16]

    def format(self, **kwargs) -> str:
        """Render the template with the given kwargs.

        Raises KeyError if any placeholder is missing — better than
        silently inserting empty strings into a production LLM call.
        """
        return self.template.format(**kwargs)

    def as_audit_dict(self) -> Dict[str, str]:
        """Compact representation for `methodology.prompts_used` blocks."""
        return {
            "name": self.name,
            "version": self.version,
            "fingerprint": self.fingerprint,
        }


# =============================================================================
# Registry
# =============================================================================

_DEEP_SEARCH_SYNTHESIS_TEMPLATE = """\
Based on the following sources, provide a comprehensive answer to: "{query}"

INTERNAL ARTICLES (from our verified corpus):
{articles_context}

EXTERNAL RESEARCH:
{perplexity_answer}
{weather_section}
---

Synthesize a clear, well-structured answer that:
1. Leads with the most important findings
2. Notes where internal and external sources agree or disagree
3. Indicates credibility levels of sources cited
4. Includes relevant weather/climate data if available
5. Flags any limitations or areas of uncertainty

Use markdown formatting. Be factual and concise."""

_DEEP_SEARCH_SYNTHESIS_SYSTEM = (
    "You are CliLens.AI's research assistant. Synthesize climate research "
    "from multiple sources with emphasis on source credibility and data "
    "accuracy."
)


_CYNEFIN_SYSTEM = (
    "You are a context classifier for the CliLens.AI climate-news "
    "complexity router (Cynefin-based). Classify each query into "
    "one of five domains and return ONLY a JSON object — no prose, "
    "no code fences.\n\n"
    "Domains:\n"
    "- clear: Simple factual lookup the database can answer directly.\n"
    "  Example: \"What is the current temperature in Helsinki?\"\n"
    "- complicated: Requires expert analysis of multiple known factors.\n"
    "  Example: \"Compare Germany and France on renewable adoption.\"\n"
    "- complex: Novel situation where cause-effect emerges in retrospect.\n"
    "  Example: \"How will the Loss & Damage Fund reshape adaptation?\"\n"
    "- chaotic: Emergency requiring rapid synthesis.\n"
    "  Example: \"Flash flood hit Pakistan — what just happened?\"\n"
    "- disorder: Insufficient signal; classify as disorder when unsure.\n\n"
    "Output format (JSON only):\n"
    "{\"domain\": \"clear|complicated|complex|chaotic|disorder\", "
    "\"confidence\": 0.0-1.0, \"reasoning\": \"one-sentence justification\"}\n\n"
    "Be conservative — classify as disorder rather than guessing."
)


_HALLUCINATION_GROUNDING_TEMPLATE = """\
GENERATED TEXT:
{generated_text}

SOURCE DOCUMENTS:
{source_excerpts}

Analyze whether the generated text is faithful to the source documents.
Return JSON:
{{
  "hallucination_risk": 0.0-1.0,
  "flagged_segments": [
    {{"text": "problematic quote", "reason": "why it is unsupported", "severity": "low/medium/high"}}
  ]
}}"""


PROMPTS: Dict[str, PromptTemplate] = {
    "deep_search_synthesis": PromptTemplate(
        name="deep_search_synthesis",
        version="v1.0",
        template=_DEEP_SEARCH_SYNTHESIS_TEMPLATE,
        system=_DEEP_SEARCH_SYNTHESIS_SYSTEM,
        max_tokens=1500,
        temperature=0.2,
        description=(
            "Synthesises internal corpus + external Perplexity + weather "
            "context into a single markdown-formatted research answer with "
            "explicit credibility / agreement / disagreement annotations."
        ),
        rationale=(
            "v1.0 is the prompt that has been in production since "
            "2026-03 — extracted from the inline f-string in "
            "deep_search_service.py during Phase 4 wave 1 (2026-05-16) "
            "without behavioural change. Future revisions should preserve "
            "the credibility-emphasis instruction (#3) — it's how the "
            "methodology drawer's source attribution stays honest."
        ),
    ),
    "cynefin_classifier": PromptTemplate(
        name="cynefin_classifier",
        version="v1.0",
        template='Query: "{query}"',
        system=_CYNEFIN_SYSTEM,
        max_tokens=200,
        temperature=0.0,
        description=(
            "Classifies a user query into Cynefin domains "
            "(clear / complicated / complex / chaotic / disorder) with a "
            "confidence and one-sentence reasoning. Powers retrieval "
            "strategy selection in chat + deep-search."
        ),
        rationale=(
            "v1.0 ported from projectcarfcynepic/config/prompts.yaml#router "
            "in commit cd32005 (2026-05-16). The strict-JSON output is "
            "deliberate — the calling code parses it and won't tolerate "
            "extra prose."
        ),
    ),
    "hallucination_grounding": PromptTemplate(
        name="hallucination_grounding",
        version="v1.0",
        template=_HALLUCINATION_GROUNDING_TEMPLATE,
        system=(
            "You detect hallucinations in AI text. Return ONLY JSON."
        ),
        max_tokens=800,
        temperature=0.0,
        description=(
            "Asks the LLM to grade whether a generated text is faithful to "
            "given source documents, flagging unsupported segments with "
            "severity. Used by HallucinationDetector._llm_grounding_check."
        ),
        rationale=(
            "v1.0 extracted from HallucinationDetector inline (2026-05-16) "
            "during Phase 4 wave 1. Returns hallucination_risk + "
            "flagged_segments JSON — calling code expects this exact shape."
        ),
    ),
}


def get_prompt(name: str) -> PromptTemplate:
    """Lookup a registered prompt; raises KeyError on unknown name.

    Encourages every LLM-using path to register its prompt rather than
    embedding it inline. Reviewers can list all platform prompts by
    importing PROMPTS.
    """
    try:
        return PROMPTS[name]
    except KeyError:
        raise KeyError(
            f"Unknown prompt name: {name!r}. Registered names: "
            f"{sorted(PROMPTS.keys())}"
        )


def list_prompts() -> Dict[str, Dict[str, str]]:
    """Audit helper — returns name → {version, fingerprint, description}."""
    return {
        name: {
            "version": p.version,
            "fingerprint": p.fingerprint,
            "description": p.description,
        }
        for name, p in PROMPTS.items()
    }
