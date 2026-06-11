"""Shared agentic-actions helper (2026-06-10 audit).

Pins the parse/strip + prompt-suffix logic that now powers the map and article
chat surfaces (not just /api/chat), so action chips appear everywhere the
frontend renders data.actions.
"""

from __future__ import annotations

import json

from app.domains.intelligence.chat_actions import (
    actions_prompt_suffix,
    parse_actions,
    split_actions,
)


def test_suffix_lists_available_actions():
    s = actions_prompt_suffix()
    assert "AVAILABLE ACTIONS" in s
    # A couple of real skill types should appear in the catalogue.
    assert "open_country" in s


def test_parse_valid_actions_block():
    answer = (
        "Germany leads on renewables.\n---\n"
        + json.dumps({"actions": [
            {"type": "open_country", "params": {"code": "DE"}, "label": "Open Germany"},
        ]})
    )
    actions = parse_actions(answer)
    assert len(actions) == 1
    assert actions[0]["type"] == "open_country"
    assert actions[0]["params"] == {"code": "DE"}


def test_unknown_action_type_dropped():
    answer = "Text\n---\n" + json.dumps({"actions": [
        {"type": "definitely_not_a_real_skill", "label": "x"},
        {"type": "open_country", "params": {"code": "FR"}, "label": "France"},
    ]})
    actions = parse_actions(answer)
    assert [a["type"] for a in actions] == ["open_country"]


def test_no_separator_returns_empty():
    assert parse_actions("Just a plain answer, no actions.") == []


def test_garbage_after_separator_returns_empty():
    assert parse_actions("Answer\n---\nnot json at all") == []


def test_caps_at_five():
    many = {"actions": [
        {"type": "open_country", "params": {"code": "DE"}, "label": f"a{i}"}
        for i in range(8)
    ]}
    answer = "Text\n---\n" + json.dumps(many)
    assert len(parse_actions(answer)) == 5


def test_split_strips_block_from_answer():
    answer = "The headline answer.\n---\n" + json.dumps({"actions": [
        {"type": "open_country", "params": {"code": "DE"}, "label": "Open Germany"},
    ]})
    display, actions = split_actions(answer)
    assert display == "The headline answer."
    assert "---" not in display
    assert len(actions) == 1


def test_split_leaves_answer_untouched_when_no_actions():
    # A stray markdown rule with no valid actions block must not be stripped.
    answer = "Line one\n---\nLine two with no JSON"
    display, actions = split_actions(answer)
    assert display == answer
    assert actions == []
