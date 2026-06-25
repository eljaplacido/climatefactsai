"""
Context compaction — native, dependency-free LLM token reduction.

This module surgically reflects the techniques of Headroom
(github.com/headroomlabs-ai/headroom) WITHOUT adding a runtime dependency or a
proxy. The goal is the same — "fewer tokens, same answers" — applied at the
points where this platform actually stuffs context into a prompt:

  * ``estimate_tokens``   — cheap, deterministic token estimate (no tiktoken).
  * ``compact_text``      — budget-bounded truncation at a clean word boundary.
  * ``smartcrush_json``   — SmartCrusher-style structural shrink: drop empty
                            fields, round floats, collapse whitespace, truncate
                            long strings, cap list length. For view-context /
                            tool-output / structured payloads.
  * ``fit_to_budget``     — IntelligentContext-style score-based fitting: keep
                            the highest-value items until a token budget is
                            spent; report what was dropped.
  * ``dedupe_by``         — order-preserving dedup before fitting.

Design rules (mirroring the Headroom "no new dep" decision):
  * Pure Python, standard library only.
  * Never raise on the LLM path — every public helper degrades to the original
    input on unexpected types rather than throwing.
  * Budgets are env-tunable so cost/quality can be dialed without a redeploy.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Sequence

try:  # keep the platform logger when running inside the app …
    from app.core.logging import get_logger

    logger = get_logger(__name__)
except Exception:  # … but stay importable + testable in isolation.
    import logging

    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env-tunable budgets (chars/4 token estimate — see estimate_tokens)
# ---------------------------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    try:
        raw = os.getenv(name, "")
        return int(raw) if raw.strip() else default
    except (ValueError, AttributeError):
        return default


# Total context (retrieved articles/evidence) injected into a single chat/
# deep-search synthesis prompt. ~5 articles * ~250 tok was the prior cost.
CHAT_CONTEXT_TOKEN_BUDGET = _int_env("CLILENS_CHAT_CONTEXT_TOKENS", 1100)
# Per-evidence-excerpt cap used when fitting a corpus snippet.
EVIDENCE_EXCERPT_TOKENS = _int_env("CLILENS_EVIDENCE_EXCERPT_TOKENS", 70)
# Hard safety ceiling on the user-side prompt handed to a provider. A
# pathological context (runaway history, huge view payload) is trimmed to this
# rather than billed/failed. 0 disables the guard.
MAX_LLM_INPUT_TOKENS = _int_env("CLILENS_MAX_LLM_INPUT_TOKENS", 14000)

_CHARS_PER_TOKEN = 4
_EMPTY = (None, "", [], {}, ())


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: Any) -> int:
    """Estimate token count without a tokenizer dependency.

    Uses the well-worn ~4-chars-per-token heuristic for English-ish prose. It
    is intentionally cheap and slightly conservative (rounds up) so budgets
    never silently overrun. Non-strings are coerced via ``str``.
    """
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# Text compaction
# ---------------------------------------------------------------------------

def compact_text(text: Optional[str], max_tokens: int, *, suffix: str = "…") -> str:
    """Truncate ``text`` to ``max_tokens``, preferring a clean word boundary.

    Returns the input unchanged when it already fits. Never raises.
    """
    if not text:
        return text or ""
    if not isinstance(text, str):
        text = str(text)
    if max_tokens <= 0:
        return suffix
    if estimate_tokens(text) <= max_tokens:
        return text

    budget_chars = max_tokens * _CHARS_PER_TOKEN - len(suffix)
    if budget_chars <= 0:
        return suffix
    cut = text[:budget_chars]
    # Prefer to cut at the last whitespace if it's reasonably close to the end,
    # so we don't slice a word in half.
    sp = cut.rfind(" ")
    if sp > 0 and sp >= budget_chars - 40:
        cut = cut[:sp]
    return cut.rstrip() + suffix


# ---------------------------------------------------------------------------
# SmartCrusher-style structural JSON compaction
# ---------------------------------------------------------------------------

def smartcrush_json(
    obj: Any,
    *,
    max_str: int = 240,
    max_items: int = 20,
    max_depth: int = 6,
    _depth: int = 0,
) -> Any:
    """Recursively shrink a JSON-ish structure.

    * dicts: drop keys whose (compacted) value is empty/None.
    * lists: cap to ``max_items`` and append a "(+N more)" sentinel.
    * floats: round to 4 dp (kills 0.123456789012 noise).
    * strings: collapse internal whitespace, truncate to ``max_str``.

    Numeric zeros and ``False`` are preserved (only None/""/[]/{}/() drop).
    Never raises — unknown types pass through untouched.
    """
    if _depth >= max_depth:
        return "…"
    try:
        if isinstance(obj, dict):
            out: Dict[Any, Any] = {}
            for k, v in obj.items():
                cv = smartcrush_json(
                    v, max_str=max_str, max_items=max_items,
                    max_depth=max_depth, _depth=_depth + 1,
                )
                if any(cv is e or cv == e for e in _EMPTY):
                    continue
                out[k] = cv
            return out
        if isinstance(obj, (list, tuple)):
            crushed: List[Any] = []
            seq = list(obj)
            for v in seq[:max_items]:
                cv = smartcrush_json(
                    v, max_str=max_str, max_items=max_items,
                    max_depth=max_depth, _depth=_depth + 1,
                )
                if any(cv is e or cv == e for e in _EMPTY):
                    continue
                crushed.append(cv)
            if len(seq) > max_items:
                crushed.append(f"…(+{len(seq) - max_items} more)")
            return crushed
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, float):
            return round(obj, 4)
        if isinstance(obj, str):
            s = " ".join(obj.split())
            if len(s) > max_str:
                s = s[:max_str].rstrip() + "…"
            return s
        return obj
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"smartcrush_json skipped a node: {exc}")
        return obj


def compact_json_str(obj: Any, **kwargs) -> str:
    """``smartcrush_json`` then serialize compactly (no spaces). Never raises."""
    try:
        crushed = smartcrush_json(obj, **kwargs)
        return json.dumps(crushed, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"compact_json_str fell back to str(): {exc}")
        return str(obj)


# ---------------------------------------------------------------------------
# IntelligentContext-style budget fitting
# ---------------------------------------------------------------------------

def dedupe_by(items: Sequence[Any], key: Callable[[Any], Any]) -> List[Any]:
    """Order-preserving dedup by ``key(item)``."""
    seen = set()
    out: List[Any] = []
    for it in items:
        try:
            k = key(it)
        except Exception:
            out.append(it)
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def fit_to_budget(
    items: Sequence[Any],
    budget_tokens: int,
    *,
    render: Callable[[Any], str],
    score: Optional[Callable[[Any], float]] = None,
    min_items: int = 1,
    separator: str = "\n",
) -> Dict[str, Any]:
    """Keep the highest-value items that fit within ``budget_tokens``.

    Greedy by ``score`` (desc) so the most relevant evidence survives a tight
    budget; output is restored to the original order for readability. At least
    ``min_items`` are always kept even if they overflow the budget (so the LLM
    never gets an empty context block).

    Returns ``{kept, dropped, rendered, used_tokens}``.
    """
    items = list(items or [])
    if not items:
        return {"kept": [], "dropped": 0, "rendered": "", "used_tokens": 0}

    indexed = list(enumerate(items))
    if score is not None:
        try:
            indexed.sort(key=lambda p: score(p[1]), reverse=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"fit_to_budget score() failed, keeping input order: {exc}")

    sep_tok = estimate_tokens(separator)
    used = 0
    kept: List[tuple] = []
    for orig_idx, it in indexed:
        rendered = render(it)
        cost = estimate_tokens(rendered) + (sep_tok if kept else 0)
        if len(kept) < min_items or used + cost <= budget_tokens:
            kept.append((orig_idx, it, rendered))
            used += cost
        # else: skip and keep scanning — a smaller later item may still fit.

    kept.sort(key=lambda x: x[0])
    rendered_block = separator.join(r for _, _, r in kept)
    return {
        "kept": [it for _, it, _ in kept],
        "dropped": len(items) - len(kept),
        "rendered": rendered_block,
        "used_tokens": used,
    }


# ---------------------------------------------------------------------------
# Whole-prompt safety guard
# ---------------------------------------------------------------------------

def guard_input(prompt: Optional[str], max_tokens: Optional[int] = None) -> str:
    """Trim a user-side prompt to the hard input ceiling. No-op when disabled.

    This is the last line of defense against a pathological context blowing up
    cost/latency or tripping a provider's context limit. It trims the MIDDLE
    (keeping the head — task/instructions — and the tail — the actual question),
    which preserves the parts an LLM weights most.
    """
    if not prompt:
        return prompt or ""
    cap = MAX_LLM_INPUT_TOKENS if max_tokens is None else max_tokens
    if cap <= 0 or estimate_tokens(prompt) <= cap:
        return prompt

    head_tokens = int(cap * 0.7)
    tail_tokens = cap - head_tokens
    head = prompt[: head_tokens * _CHARS_PER_TOKEN]
    tail = prompt[-tail_tokens * _CHARS_PER_TOKEN:]
    logger.info(
        "guard_input trimmed prompt %d→~%d tokens",
        estimate_tokens(prompt), cap,
    )
    return f"{head}\n…[context trimmed to fit token budget]…\n{tail}"
