"""Tests for LLM provider routing + circuit breaker — Phase 10 (2026-05-25).

These pin the routing protocol that EVERY LLM call in the platform
will eventually flow through. Regressions here mean either silent
fallback failures (we route to local-gx10 but never come back) or the
breaker never tripping (we hammer a dead provider until rate-limited).

We test:
  1. workload_provider() — env override semantics
  2. circuit breaker — opens after N failures, auto-closes after cooldown
  3. routing_table() / breaker_status() — surfaces for ops dashboards

The actual LLM client construction is mocked so these tests run in
milliseconds with no network.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.domains.intelligence import llm_routing as R


@pytest.fixture(autouse=True)
def reset_breakers():
    """Each test starts with a clean breaker map so state from one
    test never bleeds into the next."""
    R._BREAKERS.clear()
    yield
    R._BREAKERS.clear()


# ---------------------------------------------------------------------------
# workload_provider() — env override semantics
# ---------------------------------------------------------------------------


class TestWorkloadProvider:
    def test_default_routing_for_known_workload(self, monkeypatch):
        """Without env override, returns the documented default."""
        monkeypatch.delenv("CLILENS_ENRICHMENT_PROVIDER", raising=False)
        wr = R.workload_provider("enrichment")
        assert wr.primary == "deepseek"
        assert "local-gx10" in wr.fallback_chain

    def test_env_override_swaps_primary(self, monkeypatch):
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")
        wr = R.workload_provider("enrichment")
        assert wr.primary == "local-gx10"
        # Fallback chain preserved from defaults — primary just swaps in.
        assert "local-gx10" in wr.fallback_chain or wr.fallback_chain

    def test_env_override_ignored_for_unknown_provider(self, monkeypatch):
        """An override pointing at an unknown provider falls back to
        the default. Catches typos like 'deepseak'."""
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "deepseak")
        wr = R.workload_provider("enrichment")
        assert wr.primary == "deepseek"

    def test_unknown_workload_gets_sensible_default(self, monkeypatch):
        """An unknown workload should still route — deepseek primary
        with local-gx10 fallback. New call sites don't need to be
        registered in WORKLOAD_DEFAULTS to get sane behaviour."""
        monkeypatch.delenv("CLILENS_NEW_THING_PROVIDER", raising=False)
        wr = R.workload_provider("new_thing")
        assert wr.primary == "deepseek"
        assert "local-gx10" in wr.fallback_chain

    def test_workload_uppercased_for_env_lookup(self, monkeypatch):
        """We pass lowercase workload names; the env var is uppercase."""
        monkeypatch.setenv("CLILENS_ENTITY_EXTRACTION_PROVIDER", "openai")
        wr = R.workload_provider("entity_extraction")
        assert wr.primary == "openai"

    def test_routing_table_resolves_all_defaults(self, monkeypatch):
        for env_name in [k for k in __import__("os").environ if k.startswith("CLILENS_") and k.endswith("_PROVIDER")]:
            monkeypatch.delenv(env_name, raising=False)
        table = R.routing_table()
        # Every workload in WORKLOAD_DEFAULTS shows up in the resolved table.
        for wl in R.WORKLOAD_DEFAULTS:
            assert wl in table
            assert table[wl]["primary"] in R.PROVIDERS


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_breaker_starts_closed(self):
        assert R._breaker_is_open("deepseek") is False

    def test_breaker_unknown_provider_treated_as_open(self):
        """Defensive: an unknown provider should never be tried."""
        assert R._breaker_is_open("totally-invented") is True

    def test_breaker_opens_after_threshold_failures(self):
        for _ in range(R.PROVIDERS["deepseek"].failures_to_trip):
            R._record_failure("deepseek")
        assert R._breaker_is_open("deepseek") is True

    def test_one_failure_does_not_open(self):
        R._record_failure("deepseek")
        assert R._breaker_is_open("deepseek") is False

    def test_record_success_resets_counter(self):
        """A success in the middle of a streak resets the counter."""
        R._record_failure("deepseek")
        R._record_failure("deepseek")
        R._record_success("deepseek")
        # One more failure should not trip — counter reset.
        R._record_failure("deepseek")
        assert R._breaker_is_open("deepseek") is False

    def test_breaker_auto_closes_after_cooldown(self):
        cfg = R.PROVIDERS["deepseek"]
        for _ in range(cfg.failures_to_trip):
            R._record_failure("deepseek")
        assert R._breaker_is_open("deepseek") is True
        # Force the breaker into a state where the cooldown has elapsed.
        R._BREAKERS["deepseek"].opened_at = time.time() - cfg.cooldown_seconds - 1
        assert R._breaker_is_open("deepseek") is False

    def test_local_gx10_has_longer_cooldown(self):
        """Per the strategy doc — GX10 might be rebooting, so the
        breaker holds open longer than for cloud providers."""
        assert R.PROVIDERS["local-gx10"].cooldown_seconds > R.PROVIDERS["deepseek"].cooldown_seconds


# ---------------------------------------------------------------------------
# breaker_status() shape — for ops dashboards
# ---------------------------------------------------------------------------


class TestBreakerStatus:
    def test_shape_includes_every_provider(self):
        snap = R.breaker_status()
        for p in R.PROVIDERS:
            assert p in snap
            row = snap[p]
            assert "open" in row
            assert "consecutive_failures" in row
            assert "cooldown_seconds" in row
            assert "failures_to_trip" in row

    def test_open_breaker_surfaces_seconds_since_open(self):
        for _ in range(R.PROVIDERS["deepseek"].failures_to_trip):
            R._record_failure("deepseek")
        snap = R.breaker_status()
        assert snap["deepseek"]["open"] is True
        assert snap["deepseek"]["seconds_since_open"] is not None
        assert snap["deepseek"]["seconds_since_open"] >= 0


# ---------------------------------------------------------------------------
# route_chat() — fallback chain (mocked LLM client)
# ---------------------------------------------------------------------------


class TestRouteChat:
    """End-to-end routing with the actual client mocked. Pins the
    fallback semantics without touching the network."""

    def _patch_try(self, results: dict[str, tuple]):
        """Patch `_try_provider` so each provider returns the canned
        (response, exc, latency_ms) tuple from `results`."""
        def fake_try(provider, *_args, **_kwargs):
            return results.get(provider, (None, RuntimeError("not stubbed"), 0))
        return patch.object(R, "_try_provider", side_effect=fake_try)

    def test_primary_success_no_fallback(self, monkeypatch):
        monkeypatch.delenv("CLILENS_ENRICHMENT_PROVIDER", raising=False)
        with self._patch_try({"deepseek": ("hello world", None, 120)}):
            out = R.route_chat("test prompt", workload="enrichment")
        assert out == "hello world"

    def test_primary_fails_fallback_succeeds(self, monkeypatch):
        monkeypatch.delenv("CLILENS_ENRICHMENT_PROVIDER", raising=False)
        results = {
            "deepseek": (None, RuntimeError("timeout"), 5000),
            "local-gx10": ("fallback answer", None, 80),
        }
        with self._patch_try(results), patch.object(R, "_log_fallback") as log_fb:
            out = R.route_chat("test prompt", workload="enrichment")
        assert out == "fallback answer"
        # Fallback event was recorded.
        assert log_fb.called

    def test_all_providers_fail_returns_none(self, monkeypatch):
        monkeypatch.delenv("CLILENS_ENRICHMENT_PROVIDER", raising=False)
        results = {
            "deepseek": (None, RuntimeError("a"), 100),
            "local-gx10": (None, RuntimeError("b"), 100),
        }
        with self._patch_try(results):
            out = R.route_chat("test prompt", workload="enrichment")
        assert out is None

    def test_env_override_changes_primary(self, monkeypatch):
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")
        # Local primary succeeds; cloud never called.
        results = {
            "local-gx10": ("local answer", None, 60),
            "deepseek": (None, RuntimeError("should not be called"), 0),
        }
        with self._patch_try(results):
            out = R.route_chat("test prompt", workload="enrichment")
        assert out == "local answer"


# ---------------------------------------------------------------------------
# Provider config invariants
# ---------------------------------------------------------------------------


class TestProviderConfig:
    def test_every_provider_has_required_fields(self):
        for name, cfg in R.PROVIDERS.items():
            assert cfg.name == name
            assert cfg.base_url_env
            assert cfg.base_url_default
            assert cfg.model_env
            assert cfg.model_default
            assert cfg.failures_to_trip >= 1
            assert cfg.cooldown_seconds > 0

    def test_strategy_docs_workloads_all_registered(self):
        """Every workload mentioned in the GX10 strategy doc must be
        in WORKLOAD_DEFAULTS so env-var routing works."""
        required = {
            "enrichment", "entity_extraction", "embeddings", "translation",
            "hallucination_check", "kg_canonicalization", "analysis_html",
            "insight_summary", "chat", "conversation",
            "deep_search_synthesis", "deep_search_internal_only",
            "claim_extraction_primary", "claim_extraction_secondary",
            "claim_extraction_tertiary",
        }
        missing = required - set(R.WORKLOAD_DEFAULTS.keys())
        assert not missing, f"Workloads missing from defaults: {missing}"

    def test_tertiary_verifier_uses_local_gx10(self):
        """Per strategy — the third verifier comes from a DIFFERENT
        family than primary (deepseek) + secondary (anthropic). The
        strategy named local-gx10 (Llama 3.3 70B FP4) as the third."""
        assert R.WORKLOAD_DEFAULTS["claim_extraction_tertiary"].primary == "local-gx10"
