"""LLM provider routing with circuit breaker + per-workload selection.

Phase 10 (2026-05-25) — foundation for the GX10 strategy.

Every LLM call in the platform now flows through `route_chat()` which:

  1. Selects a *primary* provider for the workload based on
     `CLILENS_{WORKLOAD}_PROVIDER` env var (defaults documented below).
  2. Tries the primary; if it fails or its circuit breaker is open,
     falls through a `fallback_chain` to subsequent providers.
  3. Records every fallback to the `local_llm_fallbacks` table so we
     can see reliability over time.
  4. Trips the breaker after `N` consecutive failures and keeps it
     open for `cooldown_seconds`.

The function is OpenAI-API-compatible regardless of the provider —
vLLM (GX10), Anthropic, OpenAI, DeepSeek all speak this protocol when
wrapped correctly.

Providers (all configurable via env):

  - `deepseek` (default for enrichment, entity extraction, chat, claim
    extraction) — current production provider
  - `anthropic` (deep-search synthesis + secondary verifier) — frontier
    quality, keep on for now
  - `openai` (embeddings only) — `text-embedding-ada-002`
  - `local-gx10` (NEW) — vLLM serving Qwen-2.5-14B / Llama-3.3-70B FP4
    on the ASUS GX10 via Tailscale; reached at
    `CLILENS_LOCAL_GX10_BASE_URL`
  - `perplexity` (web discovery + claim verification) — search not
    inference, never local-replaceable

Routing decision matrix lives in `WORKLOAD_DEFAULTS`. Every workload
has a primary + fallback chain. To flip a workload to local-gx10:

  export CLILENS_ENRICHMENT_PROVIDER=local-gx10

…and the next deploy or process restart picks it up. No code change.

Failure tracking:

  CREATE TABLE local_llm_fallbacks (
    id UUID PRIMARY KEY,
    workload VARCHAR,
    primary_provider VARCHAR,
    fallback_provider VARCHAR,
    error_class VARCHAR,
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

Created by migration 039.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None
    logger.error("openai package not installed — LLM routing degraded")


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderConfig:
    """Static config for one LLM provider. All providers are
    OpenAI-API-compatible at the chat-completions level."""
    name: str
    base_url_env: str
    base_url_default: str
    api_key_env: Optional[str]
    model_env: str
    model_default: str
    timeout_seconds: float = 60.0
    # Open the circuit breaker after this many CONSECUTIVE failures.
    failures_to_trip: int = 3
    # Hold the breaker open for this long after tripping.
    cooldown_seconds: int = 60


PROVIDERS: dict[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url_env="DEEPSEEK_BASE_URL",
        base_url_default="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",
        model_default="deepseek-chat",
        timeout_seconds=60.0,
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        # Anthropic isn't natively OpenAI-API-compatible; the calling
        # site uses anthropic_client.py instead. Listed here so routing
        # decisions can name it as a fallback target.
        base_url_env="ANTHROPIC_BASE_URL",
        base_url_default="https://api.anthropic.com",
        api_key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_MODEL",
        model_default="claude-3-7-sonnet-20250219",
        timeout_seconds=90.0,
    ),
    "openai": ProviderConfig(
        name="openai",
        base_url_env="OPENAI_BASE_URL",
        base_url_default="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        model_default="gpt-4o-mini",
        timeout_seconds=60.0,
    ),
    "local-gx10": ProviderConfig(
        name="local-gx10",
        base_url_env="CLILENS_LOCAL_GX10_BASE_URL",
        # Default assumes vLLM on the GX10 reachable via Tailscale at
        # this magic hostname; configure to your Tailscale magic-DNS
        # name (e.g. http://gx10.tail-abcd.ts.net:8000/v1).
        base_url_default="http://gx10.local:8000/v1",
        api_key_env="CLILENS_LOCAL_GX10_API_KEY",  # vLLM ignores unless --api-key set
        model_env="CLILENS_LOCAL_GX10_MODEL",
        model_default="Qwen/Qwen2.5-14B-Instruct",
        # Tighter timeout because the GX10 should be on LAN; failing
        # fast lets the fallback take over before the user notices.
        timeout_seconds=20.0,
        failures_to_trip=3,
        cooldown_seconds=120,  # GX10 might be rebooting; give it longer
    ),
}


# ---------------------------------------------------------------------------
# Workload routing defaults (override per-instance via env)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkloadRouting:
    """Provider order for a workload. First entry is primary; subsequent
    entries are fallbacks tried in order when the primary's breaker is
    open or the call fails."""
    primary: str
    fallback_chain: tuple[str, ...] = ()


# Per the GX10 strategy doc (2026-05-25). Defaults are CLOUD primary
# until each workload is promoted to local after shadow-mode validation.
WORKLOAD_DEFAULTS: dict[str, WorkloadRouting] = {
    # Tier 2 — background batch, large opportunity for local promotion
    "enrichment": WorkloadRouting("deepseek", ("local-gx10",)),
    "entity_extraction": WorkloadRouting("deepseek", ("local-gx10",)),
    "embeddings": WorkloadRouting("openai", ("local-gx10",)),
    "translation": WorkloadRouting("deepseek", ("local-gx10",)),
    "hallucination_check": WorkloadRouting("deepseek", ("local-gx10",)),
    "kg_canonicalization": WorkloadRouting("deepseek", ("local-gx10",)),
    "analysis_html": WorkloadRouting("deepseek", ("local-gx10",)),
    "insight_summary": WorkloadRouting("deepseek", ("local-gx10",)),
    # Tier 3 — user-facing reasoning; cloud-primary until SLO proven
    "chat": WorkloadRouting("deepseek", ("local-gx10",)),
    "conversation": WorkloadRouting("deepseek", ("local-gx10",)),
    # Deep-search synthesis stays Anthropic (frontier quality required
    # for per-sentence citation grounding). Local-gx10 is a hard
    # fallback only.
    "deep_search_synthesis": WorkloadRouting("anthropic", ("deepseek",)),
    "deep_search_internal_only": WorkloadRouting("deepseek", ("local-gx10",)),
    # Tier 4 — DO NOT change. Diversity of model family IS the value.
    "claim_extraction_primary": WorkloadRouting("deepseek", ()),
    "claim_extraction_secondary": WorkloadRouting("anthropic", ()),
    # NEW (added by GX10 strategy): third independent verifier in the
    # cross-check, from a different family than primary + secondary.
    "claim_extraction_tertiary": WorkloadRouting("local-gx10", ()),
    # 2026-06-14: verdict adjudication — structured JSON output,
    # 200-600 calls/day. Good candidate for GX10 offload.
    "verdict_adjudication": WorkloadRouting("deepseek", ("local-gx10",)),
    # 2026-06-14: causal analysis + contradiction detection — low-volume
    # structured JSON. Already latency-tolerant.
    "causal_analysis": WorkloadRouting("deepseek", ("local-gx10",)),
    "contradiction_detection": WorkloadRouting("deepseek", ("local-gx10",)),
    "intelligence_brief": WorkloadRouting("deepseek", ("local-gx10",)),
}


def workload_provider(workload: str) -> WorkloadRouting:
    """Resolve effective routing for a workload by reading the
    `CLILENS_{WORKLOAD}_PROVIDER` env var, falling back to the default.

    Example: `CLILENS_ENRICHMENT_PROVIDER=local-gx10` overrides the
    enrichment workload's primary to local-gx10 with no other change.
    """
    default = WORKLOAD_DEFAULTS.get(workload)
    if default is None:
        # Unknown workload — sensible default of deepseek-primary with
        # local-gx10 fallback so new call sites get reasonable routing.
        default = WorkloadRouting("deepseek", ("local-gx10",))
    env_override = os.environ.get(f"CLILENS_{workload.upper()}_PROVIDER")
    if env_override and env_override in PROVIDERS:
        return WorkloadRouting(env_override, default.fallback_chain)
    return default


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


@dataclass
class BreakerState:
    consecutive_failures: int = 0
    opened_at: Optional[float] = None  # epoch seconds; None = closed


_BREAKERS: dict[str, BreakerState] = {}
_BREAKER_LOCK = Lock()


def _breaker_for(provider: str) -> BreakerState:
    with _BREAKER_LOCK:
        if provider not in _BREAKERS:
            _BREAKERS[provider] = BreakerState()
        return _BREAKERS[provider]


def _breaker_is_open(provider: str) -> bool:
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        return True  # unknown provider — treat as open
    st = _breaker_for(provider)
    if st.opened_at is None:
        return False
    # Auto-close after cooldown.
    if time.time() - st.opened_at > cfg.cooldown_seconds:
        with _BREAKER_LOCK:
            st.opened_at = None
            st.consecutive_failures = 0
        return False
    return True


def _record_failure(provider: str) -> None:
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        return
    with _BREAKER_LOCK:
        st = _BREAKERS.setdefault(provider, BreakerState())
        st.consecutive_failures += 1
        if st.consecutive_failures >= cfg.failures_to_trip:
            st.opened_at = time.time()
            logger.warning(
                f"Circuit breaker OPENED for {provider} after "
                f"{st.consecutive_failures} consecutive failures"
            )


def _record_success(provider: str) -> None:
    with _BREAKER_LOCK:
        st = _BREAKERS.setdefault(provider, BreakerState())
        st.consecutive_failures = 0
        st.opened_at = None


# ---------------------------------------------------------------------------
# Per-call execution
# ---------------------------------------------------------------------------


def _build_client(provider: str):
    """Return (client, model) for one OpenAI-API-compatible provider."""
    if OpenAIClient is None:
        return None, None
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        return None, None
    if provider == "anthropic":
        # Anthropic uses the dedicated Anthropic SDK at call sites
        # (anthropic_client.py). When the router needs to "route to
        # anthropic" it should call back through that path. For now,
        # return None so callers explicitly handle the anthropic branch.
        return None, os.environ.get(cfg.model_env, cfg.model_default)
    api_key = os.environ.get(cfg.api_key_env or "", "")
    if not api_key and provider != "local-gx10":
        # Many vLLM deployments accept any api_key; only true clouds
        # require one. So don't bail out on local-gx10 when api_key is
        # absent.
        return None, os.environ.get(cfg.model_env, cfg.model_default)
    base_url = os.environ.get(cfg.base_url_env, cfg.base_url_default)
    model = os.environ.get(cfg.model_env, cfg.model_default)
    try:
        client = OpenAIClient(
            api_key=api_key or "vllm-no-auth",
            base_url=base_url,
            timeout=cfg.timeout_seconds,
        )
        return client, model
    except Exception as exc:
        logger.warning(f"Failed to build {provider} client: {exc}")
        return None, model


def _log_fallback(workload: str, primary: str, fallback: str,
                   error_class: str, error_message: str, latency_ms: int) -> None:
    """Persist fallback event to local_llm_fallbacks (created by
    migration 039). Best-effort — never raises from this path."""
    try:
        from shared.database import get_postgres
        db = get_postgres()
        db.execute_update(
            """INSERT INTO local_llm_fallbacks
               (id, workload, primary_provider, fallback_provider,
                error_class, error_message, latency_ms)
               VALUES (:id, :wl, :pri, :fb, :cls, :msg, :lat)""",
            {
                "id": str(uuid.uuid4()),
                "wl": workload,
                "pri": primary,
                "fb": fallback,
                "cls": error_class[:64],
                "msg": (error_message or "")[:500],
                "lat": int(latency_ms),
            },
        )
    except Exception as exc:
        # Table might not exist yet; or DB unreachable. Don't break
        # the LLM call path over telemetry.
        logger.debug(f"local_llm_fallbacks insert failed (non-fatal): {exc}")


def _try_provider(
    provider: str,
    prompt: str,
    system_prompt: Optional[str],
    max_tokens: int,
    temperature: float,
) -> tuple[Optional[str], Optional[Exception], int]:
    """Try a single provider once. Returns (response, exception, latency_ms)."""
    if _breaker_is_open(provider):
        return None, RuntimeError(f"circuit breaker open for {provider}"), 0
    client, model = _build_client(provider)
    if client is None:
        return None, RuntimeError(f"no client for {provider}"), 0

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = int((time.time() - start) * 1000)
        _record_success(provider)
        text = response.choices[0].message.content
        return text, None, latency_ms
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        _record_failure(provider)
        return None, exc, latency_ms


def route_chat(
    prompt: str,
    *,
    workload: str = "enrichment",
    system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.1,
) -> Optional[str]:
    """Route an LLM chat call through the configured provider chain.

    This is the SINGLE entry point. Callers pick a `workload` string
    (`enrichment`, `entity_extraction`, `chat`, etc.); routing decides
    which provider to try first based on env-var override + the
    `WORKLOAD_DEFAULTS` matrix.

    On any provider failure (timeout, HTTP error, circuit-breaker open)
    the next provider in the fallback chain is tried. Every fallback is
    recorded to `local_llm_fallbacks`. Returns the first successful
    response or None if every provider failed.
    """
    routing = workload_provider(workload)
    chain = [routing.primary, *routing.fallback_chain]
    last_error: Optional[Exception] = None

    for i, provider in enumerate(chain):
        text, exc, latency_ms = _try_provider(
            provider, prompt, system_prompt, max_tokens, temperature,
        )
        if text is not None:
            if i > 0 and last_error is not None:
                # Successful fallback — log it for visibility.
                _log_fallback(
                    workload=workload,
                    primary=chain[0],
                    fallback=provider,
                    error_class=type(last_error).__name__,
                    error_message=str(last_error),
                    latency_ms=latency_ms,
                )
            return text
        last_error = exc
        logger.info(
            f"LLM call failed on {provider} for workload={workload}: "
            f"{type(exc).__name__ if exc else 'unknown'}; trying next"
        )

    logger.error(
        f"LLM call exhausted all providers for workload={workload}: "
        f"chain={chain}, last_error={last_error}"
    )
    return None


# ---------------------------------------------------------------------------
# Debug / status helpers (surfaced via /api/admin/llm-status route)
# ---------------------------------------------------------------------------


def breaker_status() -> dict:
    """Snapshot of every provider's breaker state, for ops surfaces."""
    now = time.time()
    out: dict = {}
    for name, cfg in PROVIDERS.items():
        st = _BREAKERS.get(name) or BreakerState()
        out[name] = {
            "open": _breaker_is_open(name),
            "consecutive_failures": st.consecutive_failures,
            "opened_at": st.opened_at,
            "seconds_since_open": (
                None if st.opened_at is None else int(now - st.opened_at)
            ),
            "cooldown_seconds": cfg.cooldown_seconds,
            "failures_to_trip": cfg.failures_to_trip,
        }
    return out


def routing_table() -> dict:
    """Effective routing per workload, resolving env-var overrides."""
    return {
        wl: {
            "primary": workload_provider(wl).primary,
            "fallback_chain": list(workload_provider(wl).fallback_chain),
        }
        for wl in WORKLOAD_DEFAULTS.keys()
    }
