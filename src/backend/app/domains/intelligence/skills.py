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
    # Polish wave 1 (2026-05-25) — 4 new skills wrap the endpoint
    # families shipped in deferred items 11/12/13/14 + Slice 3. Each
    # is added to BOTH this registry AND chatActionDispatcher.ts;
    # test_agentic_skill_pin enforces parity at CI time.
    "save_item": Skill(
        name="save_item",
        description="Save anything to the user's saves — article / analysis / claim / search / company / country / deep_search / feed_setting. Polymorphic Slice 3 endpoint.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="item_type",
                type="string",
                description=("One of: article, analysis, claim, search, "
                             "company, feed_setting, deep_search, country"),
            ),
            SkillParameter(
                name="item_id",
                type="string",
                description=("UUID for FK-able types (article/analysis/claim/"
                             "company). Provide either item_id or item_ref, "
                             "never both."),
                required=False,
            ),
            SkillParameter(
                name="item_ref",
                type="string",
                description=("Text ref for non-UUID types (search URL, "
                             "country code, JSON payload)."),
                required=False,
            ),
            SkillParameter(
                name="label",
                type="string",
                description="Optional human-readable label for the save.",
                required=False,
            ),
        ),
        target_surfaces=("/api/user/saved", "/saves"),
    ),
    "subscribe_research_topic": Skill(
        name="subscribe_research_topic",
        description="Subscribe the user to a research topic — the CrossRef poller will deliver new papers to their /research feed.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="topic",
                type="string",
                description="Short label like 'Arctic sea ice' or 'CBAM compliance'",
            ),
        ),
        target_surfaces=("/api/research/subscriptions",),
    ),
    "explore_scenario": Skill(
        name="explore_scenario",
        description="Interpolate IPCC AR6 SSP projections for a country at a target warming level + horizon. Read-only; returns transparent 'not simulation' disclaimer.",
        mode="auto",
        parameters=(
            SkillParameter(
                name="country_code",
                type="string",
                description="ISO 3166-1 alpha-2 country code",
            ),
            SkillParameter(
                name="target_warming_c",
                type="number",
                description="Target warming in degrees C above pre-industrial (0-8)",
            ),
            SkillParameter(
                name="horizon_year",
                type="number",
                description="One of 2030 / 2050 / 2100",
                required=False,
            ),
        ),
        target_surfaces=("/api/scenario/country/[cc]",),
    ),
    "analyze_corporate_report": Skill(
        name="analyze_corporate_report",
        description="End-to-end analysis of a corporate sustainability report URL — fetches text, extracts claims, runs each through the ECGT/SBTi analyzer, returns aggregated verdicts.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="ticker",
                type="string",
                description="Ticker of the company whose report is being analyzed",
            ),
            SkillParameter(
                name="report_url",
                type="string",
                description="Public URL of the corporate sustainability report (HTML page or PDF)",
            ),
        ),
        target_surfaces=("/api/companies/[ticker]/analyze-report",),
    ),
    # ----- Stage 4 / M5 — semantic layer skills -----
    "explore_entity": Skill(
        name="explore_entity",
        description="Drill into a knowledge-graph entity to see its full neighborhood — connected entities, relationships, every article that mentions it, and the cross-article connections that emerge.",
        mode="auto",
        parameters=(
            SkillParameter(
                name="entity_id",
                type="string",
                description="UUID of the entity to explore",
            ),
        ),
        target_surfaces=("/explore/entity/[id]", "/api/semantic/entity/[id]"),
    ),
    "explain_connection": Skill(
        name="explain_connection",
        description="LLM-driven 'why are these connected' for a small set of articles or entities. Computes shared bridge entities + asks the LLM to write a 100-200 word paragraph citing them. Powers cross-artifact systemic insights.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="article_ids",
                type="string",
                description="Comma-separated article UUIDs (2-5). Use this OR entity_ids.",
                required=False,
            ),
            SkillParameter(
                name="entity_ids",
                type="string",
                description="Comma-separated entity UUIDs (2-5). Use this OR article_ids.",
                required=False,
            ),
        ),
        target_surfaces=("/api/semantic/explain",),
    ),
    # ----- Stage 3 / M4 — evolving validation corpus -----
    "flag_off_topic": Skill(
        name="flag_off_topic",
        description="Mark an article as off-topic / on-topic / borderline. Feeds the platform's evolving validation corpus — flagged articles are excluded from future enrichment selection so slop doesn't recirculate.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="article_id",
                type="string",
                description="UUID of the article to flag",
            ),
            SkillParameter(
                name="verdict",
                type="string",
                description="One of: on_topic, off_topic, borderline",
            ),
            SkillParameter(
                name="off_topic_category",
                type="string",
                description="If off_topic: politics, sports, finance, crime, celebrity, general_news, other",
                required=False,
            ),
        ),
        target_surfaces=("/api/feedback/topic/[article_id]",),
    ),
    # ----- Stage 5 / M6 — corporate suggestions -----
    "suggest_company": Skill(
        name="suggest_company",
        description="Suggest a company for the Corporate Climate Tracker — submission goes into the review queue. Auto-matches against existing companies and returns matched_company_id when found.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="company_name",
                type="string",
                description="Legal or common company name",
            ),
            SkillParameter(
                name="ticker",
                type="string",
                description="Stock ticker if listed",
                required=False,
            ),
            SkillParameter(
                name="country_code",
                type="string",
                description="ISO-2 country code (e.g. FI, DE)",
                required=False,
            ),
            SkillParameter(
                name="report_url",
                type="string",
                description="URL to a corporate sustainability report PDF for follow-up analyze-report run",
                required=False,
            ),
            SkillParameter(
                name="reason",
                type="string",
                description="Why this company should be tracked (claims to verify, news to follow, etc.)",
                required=False,
            ),
        ),
        target_surfaces=("/api/companies/suggestions",),
    ),
    # ----- Golden examples corpus (post-Stage-5) -----
    "promote_golden_example": Skill(
        name="promote_golden_example",
        description="Mark an artifact (article enrichment, research analysis, company verdict, semantic explanation, map insight, KG drill-down) as a golden example. Feeds the curated 'best of' corpus that doubles as LoRA training-data seeds for GX10 specialist fine-tunes.",
        mode="confirm",
        parameters=(
            SkillParameter(
                name="artifact_kind",
                type="string",
                description="One of: article_enrichment, research_analysis, company_verdict, semantic_explanation, map_insight, kg_drill_down",
            ),
            SkillParameter(
                name="artifact_ref",
                type="string",
                description="UUID or composite reference of the artifact being promoted",
            ),
            SkillParameter(
                name="why_golden",
                type="string",
                description="Short curator note explaining why this is golden",
            ),
            SkillParameter(
                name="quality_score",
                type="number",
                description="Quality rating 1-5 (default 4). LoRA exporter filters to >= 4.",
                required=False,
            ),
        ),
        target_surfaces=("/api/golden-examples",),
    ),
    # ----- Stage 6 / M7 — UN SDG layer -----
    "explore_sdg": Skill(
        name="explore_sdg",
        description="Browse all articles, research analyses, and companies tagged to a specific UN Sustainable Development Goal (1-17). E.g. goal_id=13 surfaces every Climate Action artifact in the corpus.",
        mode="auto",
        parameters=(
            SkillParameter(
                name="goal_id",
                type="number",
                description="SDG goal number, 1-17",
            ),
        ),
        target_surfaces=("/api/sdg/[goal_id]", "/sdg/[goal_id]"),
    ),
    "tag_sdgs": Skill(
        name="tag_sdgs",
        description="Tag arbitrary text (or article body / company disclosure / research excerpt) with the UN SDGs it most likely relates to. Returns goal_ids + per-goal confidence (matched_keywords / total).",
        mode="auto",
        parameters=(
            SkillParameter(
                name="text",
                type="string",
                description="Text to tag (10-20000 chars)",
            ),
        ),
        target_surfaces=("/api/sdg/tag",),
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
