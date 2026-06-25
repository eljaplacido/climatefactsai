"""
Unified LLM client with multi-provider fallback chain.

2026-05-28 refactor: previously DeepSeek-only with no fallback — if DeepSeek
hiccupped (rate limit, latency spike, outage), chat would 500. Now mirrors
the article_enrichment_service.py fallback pattern: try providers in order
(local-gx10 → deepseek → openai → anthropic), return on the first one that
produces non-empty content. Production-resilient by default.

Set CLILENS_CHAT_PROVIDER (or CLILENS_ENRICHMENT_PROVIDER) to pin a single
provider when you need deterministic cost behavior (backfill jobs, etc.).
"""

import os
from typing import Optional, Tuple, List

from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None
    logger.error("openai package not installed — LLM features unavailable")


# --- Cost telemetry (seq-8, 2026-06-04) -------------------------------------
# USD per 1,000,000 tokens (input, output). Rough public list prices — the goal
# is relative visibility (cloud spend vs the free on-prem GX10), not invoicing
# accuracy. Keyed by provider with a representative model rate; local-gx10 free.
_COST_RATES_PER_M = {
    "deepseek": (0.14, 0.28),       # deepseek-chat
    "openai": (0.15, 0.60),         # gpt-4o-mini
    "anthropic": (3.00, 15.00),     # claude sonnet-class
    "local-gx10": (0.0, 0.0),       # free, on-prem
}


def _record_cost(provider: str, model: str, usage, purpose: str) -> None:
    """Best-effort: write one llm_cost_log row for a successful provider call.
    Never raises — telemetry must never break the LLM path."""
    try:
        pt = int(getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", 0) or 0)
        ct = int(getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", 0) or 0)
        rate_in, rate_out = _COST_RATES_PER_M.get(provider, (0.0, 0.0))
        cost = (pt / 1_000_000.0) * rate_in + (ct / 1_000_000.0) * rate_out
        from shared.database import get_postgres
        get_postgres().execute_update(
            "INSERT INTO llm_cost_log (provider, model, purpose, prompt_tokens, "
            "completion_tokens, est_cost_usd) VALUES (:p, :m, :purpose, :pt, :ct, :cost)",
            {"p": provider, "m": model, "purpose": purpose,
             "pt": pt, "ct": ct, "cost": round(cost, 6)},
        )
    except Exception as exc:
        logger.debug(f"llm cost telemetry skipped: {exc}")


def _provider_order(pin: Optional[str] = None) -> List[str]:
    """Resolve the provider chain order from env or argument.

    Two distinct policies depending on caller's intent:

      * `CLILENS_ENRICHMENT_PROVIDER=local-gx10` — background-only path
        (article enrichment, KG extraction, backfills). GX10 first,
        cloud fallbacks behind. Acceptable to depend on GX10 since
        the user is not blocked if it's offline.

      * `CLILENS_CHAT_PROVIDER` — user-facing real-time path (chat,
        deep-search synthesis). The user's rule: customer-facing
        features MUST NOT have GX10 in the critical chain because GX10
        is the user's on-prem device that can be powered off any time.
        Default chain is cloud-only.

    See [[feedback-devops-antipatterns]] for the rule's origin.
    """
    pin = (pin or os.getenv("CLILENS_CHAT_PROVIDER", "")).strip().lower()

    # Explicit user pin overrides defaults.
    if pin == "local-gx10":
        # User opted IN explicitly — full chain with GX10 first.
        return ["local-gx10", "deepseek", "openai", "anthropic"]
    if pin in {"deepseek", "openai", "anthropic"}:
        return [pin]

    # Fall back to enrichment-provider env only if it's NOT local-gx10
    # (background-only pin must not leak into user-facing chat).
    enrichment_pin = os.getenv("CLILENS_ENRICHMENT_PROVIDER", "").strip().lower()
    if enrichment_pin in {"deepseek", "openai", "anthropic"}:
        return [enrichment_pin]

    # DEFAULT: cloud-only chain for chat. No local-gx10 — chat must
    # work even when the user's GX10 box is off.
    return ["deepseek", "openai", "anthropic"]


def get_llm_client():
    """
    Return the primary LLM client and model name (backwards-compat).

    Most NEW code should call `llm_chat_with_fallback` instead — that walks
    the full provider chain. This single-provider getter is kept for the
    handful of callers that still construct a raw OpenAI-compatible client
    (e.g. direct streaming integrations).

    Returns:
        Tuple of (client, model_name) or (None, model_name) if unavailable.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        logger.error("DEEPSEEK_API_KEY not set — falling back to other providers")
        # Try OpenAI as next-best raw client
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and OpenAIClient:
            return (
                OpenAIClient(api_key=openai_key),
                os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            )
        return None, model

    if not OpenAIClient:
        logger.error("openai package not installed — LLM features unavailable")
        return None, model

    return OpenAIClient(api_key=api_key, base_url=base_url), model


def llm_chat_with_fallback(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1200,
    temperature: float = 0.3,
    provider_pin: Optional[str] = None,
    purpose: str = "llm_chat",
) -> Optional[Tuple[str, str, str]]:
    """
    Multi-provider chat completion with auto-fallback.

    Tries providers in order: by default deepseek → openai → anthropic →
    local-gx10 (cheapest/most-reliable first). On any failure (no key,
    network error, empty response, rate limit) falls through to the next.
    Pin a single provider with CLILENS_CHAT_PROVIDER to disable fallback.

    Returns:
        Tuple of (text, provider_name, model_name) on success.
        None if every provider in the chain failed.
    """
    if not OpenAIClient:
        logger.error("openai package not installed — cannot call any provider")
        return None

    order = _provider_order(provider_pin)

    # Headroom safety net: bound the user-side prompt so a pathological context
    # (runaway history, huge pasted payload) never blows a provider's context
    # window or the token bill. Static system prompts are left untouched so the
    # cacheable prefix stays byte-identical. Never fails the call.
    try:
        from app.domains.intelligence.context_compaction import guard_input
        user_prompt = guard_input(user_prompt)
    except Exception as _gi_exc:  # pragma: no cover - defensive
        logger.debug(f"guard_input skipped: {_gi_exc}")

    for provider in order:
        try:
            if provider == "local-gx10":
                base_url = os.getenv("CLILENS_LOCAL_GX10_BASE_URL")
                if not base_url:
                    continue
                api_key = os.getenv("CLILENS_LOCAL_GX10_API_KEY", "EMPTY")
                model = os.getenv(
                    "CLILENS_LOCAL_GX10_MODEL", "Qwen/Qwen2.5-14B-Instruct"
                )
                timeout_s = float(os.getenv("CLILENS_LOCAL_GX10_TIMEOUT", "60"))
                client = OpenAIClient(
                    api_key=api_key, base_url=base_url, timeout=timeout_s
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                msg = response.choices[0].message
                text = (getattr(msg, "content", None) or "").strip()
                if not text:
                    extras = (msg.model_extra or {}) if hasattr(msg, "model_extra") else {}
                    text = (
                        extras.get("reasoning")
                        or extras.get("thinking")
                        or extras.get("reasoning_content")
                        or ""
                    ).strip()
                if text:
                    logger.info(f"local-gx10 chat OK ({len(text)} chars)")
                    _record_cost("local-gx10", model, getattr(response, "usage", None), purpose)
                    return text, "local-gx10", model

            elif provider == "deepseek":
                key = os.getenv("DEEPSEEK_API_KEY")
                if not key:
                    continue
                model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                client = OpenAIClient(
                    api_key=key,
                    base_url=os.getenv(
                        "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                    ),
                    timeout=float(os.getenv("DEEPSEEK_TIMEOUT", "45")),
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    _record_cost("deepseek", model, getattr(response, "usage", None), purpose)
                    return text, "deepseek", model

            elif provider == "openai":
                key = os.getenv("OPENAI_API_KEY")
                if not key:
                    continue
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                client = OpenAIClient(
                    api_key=key,
                    timeout=float(os.getenv("OPENAI_TIMEOUT", "45")),
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    _record_cost("openai", model, getattr(response, "usage", None), purpose)
                    return text, "openai", model

            elif provider == "anthropic":
                key = os.getenv("ANTHROPIC_API_KEY")
                if not key:
                    continue
                try:
                    import anthropic
                except ImportError:
                    continue
                model = os.getenv(
                    "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"
                )
                client = anthropic.Anthropic(api_key=key)
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                if message.content:
                    text = message.content[0].text.strip()
                    if text:
                        _record_cost("anthropic", model, getattr(message, "usage", None), purpose)
                        return text, "anthropic", model

        except Exception as exc:
            logger.warning(
                f"{provider} chat call failed; falling back: "
                f"{type(exc).__name__}: {str(exc)[:200]}"
            )
            continue

    logger.error(
        "All LLM providers failed — no chain member produced a usable response. "
        f"Order tried: {order}"
    )
    return None


def llm_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.1,
    client=None,
    model: str = None,
) -> Optional[str]:
    """
    Backwards-compat single-call wrapper.

    NEW code should call `llm_chat_with_fallback` directly to get the
    (text, provider, model) tuple. This wrapper returns just the text
    and preserves the old single-provider behavior when a pre-created
    `client` is passed.
    """
    if client is not None and OpenAIClient is not None:
        # Caller passed their own client — preserve old single-provider path.
        if model is None:
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {type(e).__name__}: {e}")
            return None

    # No client passed — walk the full fallback chain.
    result = llm_chat_with_fallback(
        system_prompt=system_prompt or "",
        user_prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if result is None:
        return None
    text, _provider, _model = result
    return text
