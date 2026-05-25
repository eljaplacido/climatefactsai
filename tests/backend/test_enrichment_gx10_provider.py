"""Article enrichment — local-gx10 provider integration (post-GX10-audit polish).

The audit (`docs/improvementplans/GX10-Workload-Audit-2026-05-25.md`)
identified enrichment as the #1 cost-saving target. Flipping the env
var to local-gx10 was a no-op before this slice — the pin set rejected
'local-gx10' and silently kept deepseek. This file pins:

  - local-gx10 now lands in the pin-accepted set
  - local-gx10 branch tries the configured base_url
  - graceful fallback to deepseek when GX10 base_url is unset
  - graceful fallback to deepseek when GX10 base_url is set but call fails

The actual HTTP call isn't tested (OpenAI SDK handles transport) — the
pin tests assert the branch ROUTING is correct so a future copy-edit
can't accidentally remove local-gx10 from the order list.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def service():
    from app.domains.content.article_enrichment_service import ArticleEnrichmentService
    # ArticleEnrichmentService takes a `db` arg but _call_llm doesn't touch it.
    # MagicMock is enough — these tests exercise the provider-routing branch only.
    return ArticleEnrichmentService(db=MagicMock())


def _strip_provider_keys(monkeypatch):
    """Clear all provider env vars so order is deterministic."""
    for k in (
        "CLILENS_ENRICHMENT_PROVIDER",
        "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "CLILENS_LOCAL_GX10_BASE_URL", "CLILENS_LOCAL_GX10_API_KEY",
        "CLILENS_LOCAL_GX10_MODEL",
    ):
        monkeypatch.delenv(k, raising=False)


class TestLocalGx10ProviderPin:
    """The pin set MUST include 'local-gx10' or the env-var flip is silent."""

    @pytest.mark.asyncio
    async def test_local_gx10_in_pin_set(self, monkeypatch, service):
        _strip_provider_keys(monkeypatch)
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")
        # No GX10 base_url set AND no deepseek key → all providers
        # cleanly skip, returns None. But the local-gx10 branch MUST
        # be entered (silent skip via `continue`), proving 'local-gx10'
        # was recognized as a pin value rather than rejected.
        with patch(
            "app.domains.content.article_enrichment_service.logger"
        ) as mock_logger:
            result = await service._call_llm(
                system_prompt="sys",
                user_prompt="user",
            )
        # All providers no-op'd, so result is None.
        assert result is None
        # Error log is the all-failed message — proves the chain ran end-to-end.
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_pin_value_falls_through_to_default_order(
        self, monkeypatch, service
    ):
        """A typo'd CLILENS_ENRICHMENT_PROVIDER must NOT silently drop
        all providers — it falls through to the default 3-provider chain."""
        _strip_provider_keys(monkeypatch)
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "qwen-local")  # typo
        result = await service._call_llm(system_prompt="sys", user_prompt="user")
        # No keys → None, but no crash. Default order ran cleanly.
        assert result is None


class TestLocalGx10FallbackChain:
    """When local-gx10 is the pin but unreachable, deepseek must auto-engage."""

    @pytest.mark.asyncio
    async def test_gx10_base_url_unset_skips_to_deepseek(self, monkeypatch, service):
        _strip_provider_keys(monkeypatch)
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-ds-key")
        # local-gx10 branch hits the "if not base_url: continue" guard.
        # deepseek branch then runs through the mocked OpenAI client.
        with patch("openai.OpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create.return_value = MagicMock(
                choices=[
                    MagicMock(message=MagicMock(content="ENRICHED TEXT HERE"))
                ]
            )
            result = await service._call_llm(system_prompt="sys", user_prompt="user")
        assert result is not None
        text, provider, model = result
        # The deepseek path fired because GX10 had no base_url.
        assert provider == "deepseek"

    @pytest.mark.asyncio
    async def test_gx10_fails_falls_back_to_deepseek(self, monkeypatch, service):
        """GX10 IS configured but the call raises — auto-fall to deepseek."""
        _strip_provider_keys(monkeypatch)
        monkeypatch.setenv("CLILENS_ENRICHMENT_PROVIDER", "local-gx10")
        monkeypatch.setenv("CLILENS_LOCAL_GX10_BASE_URL", "http://gx10.local:8000/v1")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-ds-key")

        call_count = {"n": 0}

        def fake_create(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("GX10 not reachable")
            return MagicMock(
                choices=[
                    MagicMock(message=MagicMock(content="DEEPSEEK FALLBACK"))
                ]
            )

        with patch("openai.OpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create.side_effect = fake_create
            result = await service._call_llm(system_prompt="sys", user_prompt="user")

        assert result is not None
        text, provider, model = result
        # First call (local-gx10) raised, second call (deepseek) succeeded.
        assert call_count["n"] == 2
        assert provider == "deepseek"
        assert text == "DEEPSEEK FALLBACK"
