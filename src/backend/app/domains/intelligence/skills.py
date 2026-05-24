"""Agentic skills registry — Phase 4C (2026-05-24).

Canonical source of truth for the platform's agentic action protocol.
Previously the 9 action types were defined in TWO places — the
`chat_synthesis_with_actions` prompt template (telling the LLM what
it could emit) and the frontend `chatActionDispatcher.ts` (telling
the client how to execute them). The `test_agentic_skill_pin.py`
cross-source test caught drift but didn't fix the underlying
duplication.

This module is now the single backend source of truth. The prompt
registry consults it (`render_actions_block()`) to generate the
"AVAILABLE ACTIONS" copy at template-build time. The skill-pin test
asserts the frontend dispatcher matches THIS registry rather than
regex-grepping the prompt template.

Adding a new action = add one entry here. Touch the prompt registry
or the frontend dispatcher only if their integration changes; the
action set itself flows from here.

Each skill entry is intentionally NOT a JSON manifest — keeping the
schema in Python lets us use frozen dataclasses for compile-time
typo protection on field names. The `/api/skills` endpoint serialises
the registry to JSON on request, so external consumers still get a
machine-readable view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SkillMode = Literal["auto", "confirm"]
"""How the frontend dispatcher should execute a skill.

  - "auto": navigation-only or read-only side effect; dispatcher runs
    it immediately on click.
  - "confirm": consumes quota OR mutates server state OR sends messages.
    Dispatcher MUST gate behind a user-confirmation modal.
"""


@dataclass(frozen=True)
class SkillParameter:
    """One named parameter of a skill's input schema.

    The LLM is told it can emit values for these; the dispatcher
    extracts them from the `params` object at execution time.
    """
    name: str
    type: Literal["string", "number", "boolean"] = "string"
    description: str = ""
    required: bool = True


@dataclass(frozen=True)
class Skill:
    """One agentic action that the chat LLM can emit and the frontend
    dispatcher can execute."""
    name: str
    description: str
    mode: SkillMode
    parameters: tuple[SkillParameter, ...] = ()
    # Routes/surfaces touched — purely documentary, surfaces in /api/skills
    # so introspecting consumers know what part of the platform is affected.
    target_surfaces: tuple[str, ...] = ()


# -----------------------------------------------------------------------------
# Registry — the 9 action types pinned by test_agentic_skill_pin.py
# -----------------------------------------------------------------------------

SKILLS_REGISTRY: dict[str, Skill] = {
    "navigate": Skill(
        name="navigate",
        description="Open a platform route (top-level navigation).",
        mode="auto",
        parameters=(
            SkillParameter(name="path", type="string",
                           description="Platform route, e.g. /map, /search, /deep-search"),
        ),
        target_surfaces=("/map", "/search", "/deep-search", "/methodology",
                          "/feed", "/sources"),
    ),
    "analyze_url": Skill(
        name="analyze_url",
        description="Submit a URL for fact-checking analysis.",
        mode="confirm",
        parameters=(
            SkillParameter(name="url", type="string",
                           description="HTTPS URL of a climate news article"),
        ),
        target_surfaces=("/analyze",),
    ),
    "apply_search_filters": Skill(
        name="apply_search_filters",
        description="Apply filters to /search and navigate the user there.",
        mode="auto",
        parameters=(
            SkillParameter(name="q", type="string", description="Search query", required=False),
            SkillParameter(name="credibility", type="string",
                           description="HIGH | MEDIUM | LOW", required=False),
            SkillParameter(name="country", type="string",
                           description="2-char ISO country code", required=False),
            SkillParameter(name="tags", type="string",
                           description="Comma-separated tags", required=False),
            SkillParameter(name="category", type="string",
                           description="Content category slug", required=False),
        ),
        target_surfaces=("/search",),
    ),
    "apply_map_filters": Skill(
        name="apply_map_filters",
        description="Apply layer + country filters to the world map.",
        mode="auto",
        parameters=(
            SkillParameter(name="country", type="string", required=False),
            SkillParameter(name="layer", type="string",
                           description="article_density | temperature_anomaly | climate_risk | source_diversity",
                           required=False),
        ),
        target_surfaces=("/map",),
    ),
    "open_methodology_section": Skill(
        name="open_methodology_section",
        description="Jump to a section of the /methodology page.",
        mode="auto",
        parameters=(
            SkillParameter(
                name="section",
                type="string",
                description=(
                    "prompts | calibration | sustainability-formula | "
                    "source-tiers | corporate-verification"
                ),
            ),
        ),
        target_surfaces=("/methodology",),
    ),
    "open_country": Skill(
        name="open_country",
        description="Open a country's climate panel on the map.",
        mode="auto",
        parameters=(
            SkillParameter(name="code", type="string",
                           description="2-character ISO country code"),
        ),
        target_surfaces=("/map", "/country/[code]"),
    ),
    "start_deep_search": Skill(
        name="start_deep_search",
        description="Launch a deep research query on /deep-search.",
        mode="auto",
        parameters=(
            SkillParameter(name="q", type="string",
                           description="Research question or topic"),
        ),
        target_surfaces=("/deep-search",),
    ),
    "bookmark_article": Skill(
        name="bookmark_article",
        description="Save an article to the user's bookmarks (consumes saved_articles quota).",
        mode="confirm",
        parameters=(
            SkillParameter(name="article_id", type="string"),
        ),
        target_surfaces=("/api/user/bookmarks",),
    ),
    "start_calibration_label": Skill(
        name="start_calibration_label",
        description="Submit a calibration rating for an existing URL analysis.",
        mode="confirm",
        parameters=(
            SkillParameter(name="url_analysis_id", type="string"),
        ),
        target_surfaces=("/analyze",),
    ),
    # Phase 7 B3 (2026-05-24) — corporate-claim surface. Connects the
    # /companies/{ticker} disclosure trail to the chat agent so users can
    # ask "what does Shell disclose?" and get a working navigation, or
    # "verify Shell's net-zero claim" and get an analyzer-graded verdict.
    "open_company": Skill(
        name="open_company",
        description="Open a company's climate disclosure profile (ticker-keyed).",
        mode="auto",
        parameters=(
            SkillParameter(
                name="ticker",
                type="string",
                description="Ticker symbol (e.g. MSFT, SHEL) — case-insensitive",
            ),
        ),
        target_surfaces=("/companies", "/companies/[ticker]"),
    ),
    "verify_corporate_claim": Skill(
        name="verify_corporate_claim",
        description="Verify a corporate climate claim against the disclosure ledger (ECGT / SBTi rules).",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="ticker",
                type="string",
                description="Ticker of the company the claim is about",
            ),
            SkillParameter(
                name="claim_text",
                type="string",
                description="The corporate climate claim to verify, verbatim",
            ),
        ),
        target_surfaces=("/api/companies/[ticker]/analyze",),
    ),
}


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def list_skills() -> list[Skill]:
    """Return all skills as a stable-ordered list."""
    return list(SKILLS_REGISTRY.values())


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name. Returns None if not registered."""
    return SKILLS_REGISTRY.get(name)


def skills_by_mode(mode: SkillMode) -> list[Skill]:
    """Filter skills by execution mode."""
    return [s for s in SKILLS_REGISTRY.values() if s.mode == mode]


def serialize_skill(skill: Skill) -> dict:
    """Serialise one Skill to the JSON shape returned by /api/skills."""
    return {
        "name": skill.name,
        "description": skill.description,
        "mode": skill.mode,
        "parameters": [
            {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "required": p.required,
            }
            for p in skill.parameters
        ],
        "target_surfaces": list(skill.target_surfaces),
    }


def serialize_registry() -> dict:
    """Serialise the whole registry. Powers GET /api/skills."""
    return {
        "skills": [serialize_skill(s) for s in list_skills()],
        "total": len(SKILLS_REGISTRY),
        "modes": {
            "auto": len(skills_by_mode("auto")),
            "confirm": len(skills_by_mode("confirm")),
        },
    }


def render_actions_block_for_prompt() -> str:
    """Render the "AVAILABLE ACTIONS" section of the
    chat_synthesis_with_actions prompt from the registry.

    The prompt registry can optionally consume this so the prompt
    template stays in lockstep with the skill registry — currently
    cross-checked by test_agentic_skill_pin.py instead of consumed
    directly (changing the prompt template wholesale is a v2 concern).
    """
    lines: list[str] = []
    for skill in list_skills():
        # Match the existing prompt template's format:
        #   - <name>: {{params}} — <description>
        param_part = "{" + ", ".join(p.name for p in skill.parameters) + "}"
        lines.append(f"- {skill.name}: {{{param_part}}} — {skill.description}")
    return "\n".join(lines)
