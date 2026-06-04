"""Cross-source-of-truth pin test for the agentic action protocol.

The 9 action types live in THREE places now:
  1. Canonical backend registry: src/backend/app/domains/intelligence/skills.py
     SKILLS_REGISTRY (Phase 4C, 2026-05-24 — single source of truth)
  2. Backend prompt registry: chat_synthesis_with_actions (prompts.py)
     — what the LLM is told it can emit. Should derive from (1).
  3. Frontend dispatcher: ACTION_MODES + DISPATCHERS in chatActionDispatcher.ts
     — what the frontend knows how to execute.

If these drift, the LLM emits actions the frontend silently ignores OR
the frontend rejects actions the LLM legitimately produced. Either way
it's a silent agentic-protocol break.

This test reads all three sources and pins them to match. Updating the
action set requires touching SKILLS_REGISTRY (1) + chatActionDispatcher.ts (3)
in the same PR; the prompt template (2) is cross-checked against (1).

Phase 1C ship (2026-05-23) → Phase 4C refactor (2026-05-24): the
registry is now the canonical source. Future PR may render the prompt
"AVAILABLE ACTIONS" block from `skills.render_actions_block_for_prompt()`
at template-build time, removing dual-source from (1) and (2) entirely.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.domains.intelligence.prompts import get_prompt
from app.domains.intelligence.skills import (
    SKILLS_REGISTRY,
    list_skills,
    skills_by_mode,
)


# The set the frontend dispatcher knows about. Kept in sync manually with
# `src/frontend/src/lib/chatActionDispatcher.ts:ACTION_MODES`. Any change
# requires updating that file, the canonical SKILLS_REGISTRY, and this constant.
FRONTEND_ACTION_TYPES = {
    "navigate",
    "analyze_url",
    "apply_search_filters",
    "apply_map_filters",
    "open_methodology_section",
    "open_country",
    "start_deep_search",
    "bookmark_article",
    "start_calibration_label",
    # Phase 7 B3 (2026-05-24) — corporate-claim surface.
    "open_company",
    "verify_corporate_claim",
    # Polish wave 1 (2026-05-25) — endpoint families from deferred
    # items 11/12/13/14 + Slice 3 wrapped as chat skills.
    "save_item",
    "subscribe_research_topic",
    "explore_scenario",
    "analyze_corporate_report",
    # Slice 3 (2026-05-26) — KG / SDG / curation skills wired into the
    # dispatcher; bumped here + in the prompt template 2026-06-04 (doc-align).
    "explore_entity",
    "explain_connection",
    "flag_off_topic",
    "suggest_company",
    "promote_golden_example",
    "explore_sdg",
    "tag_sdgs",
}

# The mode each frontend action expects — must match SKILLS_REGISTRY.
FRONTEND_ACTION_MODES = {
    "navigate": "auto",
    "apply_search_filters": "auto",
    "apply_map_filters": "auto",
    "open_methodology_section": "auto",
    "open_country": "auto",
    "start_deep_search": "auto",
    "open_company": "auto",
    "analyze_url": "confirm",
    "bookmark_article": "confirm",
    "start_calibration_label": "confirm",
    "verify_corporate_claim": "confirm",
    # Polish wave 1 (2026-05-25)
    "save_item": "confirm",
    "subscribe_research_topic": "confirm",
    "explore_scenario": "auto",
    "analyze_corporate_report": "confirm",
    # Slice 3 (2026-05-26)
    "explore_entity": "auto",
    "explain_connection": "confirm",
    "flag_off_topic": "confirm",
    "suggest_company": "confirm",
    "promote_golden_example": "confirm",
    "explore_sdg": "auto",
    "tag_sdgs": "auto",
}


def _extract_actions_from_prompt(template: str) -> set[str]:
    """Pull the action-type slugs out of the chat_synthesis_with_actions
    prompt template. The template lists them in the format:
        '- action_type: {{params}} — description'
    so we grep for `- <word>:` at line start (allowing whitespace prefix).
    """
    found = set()
    pattern = re.compile(r"^\s*-\s+([a-z_]+):\s*\{\{", re.MULTILINE)
    for match in pattern.finditer(template):
        found.add(match.group(1))
    return found


def _extract_actions_from_dispatcher() -> set[str]:
    """Read the frontend dispatcher source and pull out the ChatActionType
    union members. This catches a frontend-only change that wasn't
    propagated to the backend prompt.
    """
    repo_root = Path(__file__).resolve().parents[2]
    dispatcher_path = (
        repo_root / "src" / "frontend" / "src" / "lib" / "chatActionDispatcher.ts"
    )
    text = dispatcher_path.read_text(encoding="utf-8")
    # The type union is:
    #     export type ChatActionType =
    #       | "navigate"
    #       | "analyze_url"
    #       | ...;
    match = re.search(
        r"export type ChatActionType\s*=\s*(.*?);",
        text,
        re.DOTALL,
    )
    assert match, "Could not find ChatActionType union in dispatcher.ts"
    union_body = match.group(1)
    return set(re.findall(r'"([a-z_]+)"', union_body))


class TestAgenticSkillPin:
    def test_prompt_template_lists_all_frontend_actions(self):
        """Every action the frontend knows how to execute MUST be advertised
        to the LLM in the chat_synthesis_with_actions prompt. Missing
        actions silently never get suggested even when relevant."""
        prompt = get_prompt("chat_synthesis_with_actions")
        prompt_actions = _extract_actions_from_prompt(prompt.template)
        missing = FRONTEND_ACTION_TYPES - prompt_actions
        assert not missing, (
            f"Frontend knows action(s) the prompt doesn't advertise: {missing}. "
            "Add them to prompts.py:chat_synthesis_with_actions template."
        )

    def test_prompt_template_does_not_advertise_unknown_actions(self):
        """The reverse direction: the LLM can't suggest actions the
        frontend has no handler for — they would silently fail."""
        prompt = get_prompt("chat_synthesis_with_actions")
        prompt_actions = _extract_actions_from_prompt(prompt.template)
        extras = prompt_actions - FRONTEND_ACTION_TYPES
        assert not extras, (
            f"Prompt advertises action(s) the frontend cannot execute: {extras}. "
            "Add handlers in chatActionDispatcher.ts or remove from prompts.py."
        )

    def test_dispatcher_union_matches_local_constant(self):
        """Our local FRONTEND_ACTION_TYPES constant is the human-maintained
        list. If someone edits the dispatcher source directly we want this
        test to flag it so the constant gets bumped in lockstep."""
        dispatcher_actions = _extract_actions_from_dispatcher()
        assert dispatcher_actions == FRONTEND_ACTION_TYPES, (
            f"Drift between dispatcher.ts ChatActionType union ({dispatcher_actions}) "
            f"and this test's pin ({FRONTEND_ACTION_TYPES}). "
            "Update FRONTEND_ACTION_TYPES at the top of this test file."
        )

    def test_prompt_template_says_exactly_n_actions_in_copy(self):
        """The prompt body says 'N action types' in the system message;
        catch drift between that copy and the actual count. Bumped to
        15 in Polish wave 1 (2026-05-25)."""
        prompt = get_prompt("chat_synthesis_with_actions")
        actual_count = len(_extract_actions_from_prompt(prompt.template))
        assert actual_count == 22, (
            f"Action count drifted: {actual_count} actions in template, "
            "but system copy still says '22 action types'. Update one or the other."
        )

    def test_chat_synthesis_with_actions_prompt_exists(self):
        """Smoke: the prompt the dispatcher depends on MUST exist in the
        registry. A typo'd prompt key would silently swap the LLM to a
        no-actions answer."""
        prompt = get_prompt("chat_synthesis_with_actions")
        assert prompt is not None
        assert prompt.name == "chat_synthesis_with_actions"
        assert prompt.version  # any version is fine, presence is the pin


# ---------------------------------------------------------------------------
# Phase 4C (2026-05-24) — pin canonical SKILLS_REGISTRY vs all consumers
# ---------------------------------------------------------------------------


class TestCanonicalSkillsRegistry:
    """The Phase 4C refactor moved the action set into a single Python
    registry (skills.py). The frontend dispatcher + prompt template are
    now downstream consumers. These tests pin the registry against both."""

    def test_registry_matches_frontend_dispatcher(self):
        registry_names = set(SKILLS_REGISTRY.keys())
        assert registry_names == FRONTEND_ACTION_TYPES, (
            "skills.SKILLS_REGISTRY drifted from the frontend dispatcher's "
            f"ChatActionType union. Registry-only: {registry_names - FRONTEND_ACTION_TYPES}; "
            f"Frontend-only: {FRONTEND_ACTION_TYPES - registry_names}."
        )

    def test_registry_modes_match_frontend(self):
        """Every action's auto/confirm mode in the registry MUST match
        the frontend dispatcher's ACTION_MODES. A confirm-mode action
        marked auto in the registry would skip the confirmation modal."""
        for name, skill in SKILLS_REGISTRY.items():
            expected = FRONTEND_ACTION_MODES[name]
            assert skill.mode == expected, (
                f"Mode drift for {name}: registry={skill.mode!r} but "
                f"frontend says {expected!r}"
            )

    def test_registry_matches_prompt_template(self):
        """The prompt template's AVAILABLE ACTIONS list MUST cover every
        registered skill — otherwise the LLM never knows about that
        action and never emits it."""
        prompt = get_prompt("chat_synthesis_with_actions")
        prompt_actions = _extract_actions_from_prompt(prompt.template)
        registry_names = set(SKILLS_REGISTRY.keys())
        missing = registry_names - prompt_actions
        assert not missing, (
            f"Skills not advertised in prompt template: {missing}. "
            "Add them to chat_synthesis_with_actions template "
            "or remove from SKILLS_REGISTRY."
        )

    def test_every_skill_has_description(self):
        for skill in list_skills():
            assert skill.description, f"{skill.name!r} missing description"

    def test_every_skill_has_at_least_one_parameter(self):
        """Every action takes at least one parameter — actions with no
        params should usually be 'navigate' with a fixed path, which IS
        a parameter."""
        for skill in list_skills():
            assert len(skill.parameters) >= 1, (
                f"{skill.name!r} has no parameters — at minimum it should "
                "take an empty `params: {}` so the dispatcher contract holds"
            )

    def test_confirm_mode_skills_match_known_destructive_set(self):
        """The confirm-mode set is a hard-coded list because every
        confirm-mode addition needs human review (it changes user-visible
        UX). If this test fails because you added a confirm-mode action,
        update the list here AND ensure the dispatcher renders a modal.

        Bumped in Polish wave 1 (2026-05-25) to add save_item,
        subscribe_research_topic, analyze_corporate_report — all
        consume tier quota or persist new rows / claims.
        """
        confirm_names = {s.name for s in skills_by_mode("confirm")}
        assert confirm_names == {
            "analyze_url",
            "bookmark_article",
            "start_calibration_label",
            "verify_corporate_claim",
            "save_item",
            "subscribe_research_topic",
            "analyze_corporate_report",
            # Slice 3 (2026-05-26) — confirm-mode (quota / mutate / submit).
            "explain_connection",
            "flag_off_topic",
            "suggest_company",
            "promote_golden_example",
        }

    def test_auto_mode_is_remainder(self):
        """auto + confirm partition the action set with no overlap."""
        auto_names = {s.name for s in skills_by_mode("auto")}
        confirm_names = {s.name for s in skills_by_mode("confirm")}
        assert auto_names.isdisjoint(confirm_names)
        assert auto_names | confirm_names == set(SKILLS_REGISTRY.keys())

    def test_render_actions_block_emits_every_action(self):
        """The render helper feeds the prompt at template-build time
        (future PR). Pin that it covers every registered skill."""
        from app.domains.intelligence.skills import render_actions_block_for_prompt
        rendered = render_actions_block_for_prompt()
        for name in SKILLS_REGISTRY:
            assert f"- {name}:" in rendered, (
                f"render_actions_block_for_prompt missed {name!r}"
            )
