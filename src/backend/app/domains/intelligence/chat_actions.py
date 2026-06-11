"""Shared helpers for the agentic "chat that acts" surface.

The actions-instruction block + the parse/strip of the trailing JSON actions
block were inline in ``api.chat_routes._generate_answer``. Because the map
query (``/api/map/query``) and the article Q&A (``/api/articles/{id}/ask``)
synthesise their answers elsewhere, they always returned ``actions: []`` and
the action chips never appeared on the map or article pages — even though the
frontend renders ``data.actions`` for every chat mode and those pages actively
advertise action-triggering prompts (2026-06-10 platform audit).

Centralising the logic here lets every chat surface emit actions identically,
keyed off the single ``SKILLS_REGISTRY`` so the valid `type` values can't
drift. Lives in the intelligence domain so both ``api/`` routes and the
``conversation_engine`` (which is in ``src/backend``) can import it without a
layering violation.
"""

from __future__ import annotations

import json
from typing import List, Tuple


def _valid_action_types() -> frozenset:
    try:
        from app.domains.intelligence.skills import SKILLS_REGISTRY
        return frozenset(SKILLS_REGISTRY.keys())
    except Exception:  # pragma: no cover - registry import guard
        return frozenset()


def actions_prompt_suffix() -> str:
    """Instruction appended to a chat user-prompt telling the LLM to optionally
    append a trailing JSON actions block after a ``---`` separator. Returns ``""``
    if the skills registry is unavailable (so callers degrade to no actions).
    """
    try:
        from app.domains.intelligence.skills import render_actions_block_for_prompt
        catalogue = render_actions_block_for_prompt()
    except Exception:  # pragma: no cover - registry import guard
        return ""
    return (
        "\n\nAFTER your answer, you MAY append a JSON actions block suggesting "
        "0-3 genuinely useful next steps for the user. Separate it from your "
        "answer with a line containing only '---'. Omit the block entirely if "
        "no action is genuinely helpful.\n"
        "AVAILABLE ACTIONS (use ONLY these `type` values):\n"
        f"{catalogue}\n"
        "Each action is {\"type\": <one above>, \"params\": {..}, \"label\": "
        "\"short button text\"}. Example:\n"
        "Your answer text…\n---\n"
        "{\"actions\":[{\"type\":\"open_country\",\"params\":{\"code\":\"DE\"},"
        "\"label\":\"Open Germany on the map\"}]}"
    )


def parse_actions(answer: str) -> List[dict]:
    """Extract + validate the trailing JSON actions block (after the last
    ``---``). Caps at 5, drops unknown/malformed types, returns [] on any parse
    failure (so a stray markdown rule never breaks the answer)."""
    if "---" not in answer:
        return []
    candidate = answer.split("---")[-1].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    actions = parsed.get("actions", []) if isinstance(parsed, dict) else []
    if not isinstance(actions, list):
        return []
    valid = _valid_action_types()
    out: List[dict] = []
    for a in actions[:5]:
        if not isinstance(a, dict):
            continue
        atype = str(a.get("type", ""))
        if valid and atype not in valid:
            continue
        params = a.get("params", {})
        out.append({
            "type": atype,
            "params": params if isinstance(params, dict) else {},
            "label": str(a.get("label", atype))[:128],
        })
    return out


def split_actions(answer: str) -> Tuple[str, List[dict]]:
    """Return ``(display_answer, actions)``: parse the trailing actions block and
    strip it from the answer so the raw JSON never renders in the chat bubble.
    Only strips when the actions actually parse."""
    actions = parse_actions(answer)
    if actions:
        cut = answer.rfind("---")
        if cut != -1:
            answer = answer[:cut].rstrip()
    return answer, actions
