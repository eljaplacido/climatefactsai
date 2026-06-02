"""Regression tests for agentic chat action parsing (audit seq-2, 2026-06-02).

The chat "actions" surface returned [] in prod because (a) _generate_answer never
told the LLM to emit an actions block and (b) VALID_ACTION_TYPES was a stale
9-item hardcode that dropped 13 of the registry's 22 skills. These tests pin the
validator against the registry and the parse/split contract.
"""

from __future__ import annotations

from api.chat_routes import _parse_actions, VALID_ACTION_TYPES
from app.domains.intelligence.skills import SKILLS_REGISTRY


def test_valid_action_types_match_registry():
    """The validator must equal the skills registry — never lag it again."""
    assert VALID_ACTION_TYPES == frozenset(SKILLS_REGISTRY.keys())
    assert len(VALID_ACTION_TYPES) == 22


def test_parse_accepts_previously_rejected_registry_action():
    """open_company / explore_scenario were in the registry + frontend dispatcher
    but NOT in the old 9-item whitelist, so they were silently dropped."""
    answer = (
        "Here is the company's disclosure picture.\n"
        "---\n"
        '{"actions":[{"type":"open_company","params":{"ticker":"SHEL"},"label":"Open Shell"},'
        '{"type":"explore_scenario","params":{"country_code":"DE"},"label":"Scenario"}]}'
    )
    actions = _parse_actions(answer)
    types = {a["type"] for a in actions}
    assert "open_company" in types
    assert "explore_scenario" in types


def test_parse_returns_empty_without_separator():
    assert _parse_actions("Just a plain answer, no actions block.") == []


def test_parse_rejects_unknown_type_and_caps_at_five():
    blob = ",".join(
        '{"type":"navigate","params":{"path":"/map"},"label":"Map %d"}' % i for i in range(8)
    )
    answer = "Answer.\n---\n" + '{"actions":[%s,{"type":"not_a_real_skill","params":{},"label":"x"}]}' % blob
    actions = _parse_actions(answer)
    assert all(a["type"] in VALID_ACTION_TYPES for a in actions)
    assert "not_a_real_skill" not in {a["type"] for a in actions}
    assert len(actions) <= 5


def test_parse_handles_malformed_json():
    assert _parse_actions("Answer.\n---\n{not valid json") == []
