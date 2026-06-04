"""Tests for LLM cost telemetry (audit seq-8, 2026-06-04).

_record_cost writes one llm_cost_log row per successful provider call with an
estimated USD cost. Pins the token extraction (OpenAI vs Anthropic field names),
the per-provider rate math, the free-GX10 case, and the never-raises contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.domains.intelligence.llm_client import _record_cost, _COST_RATES_PER_M


class _Usage:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _capture(provider, model, usage, purpose="llm_chat"):
    captured = {}
    db = MagicMock()
    db.execute_update.side_effect = lambda sql, params: captured.update(params)
    with patch("shared.database.get_postgres", return_value=db):
        _record_cost(provider, model, usage, purpose)
    return captured


def test_deepseek_cost_math():
    c = _capture("deepseek", "deepseek-chat", _Usage(prompt_tokens=1000, completion_tokens=500))
    assert c["pt"] == 1000 and c["ct"] == 500
    # 1000/1M*0.14 + 500/1M*0.28 = 0.00014 + 0.00014 = 0.00028
    assert abs(c["cost"] - 0.00028) < 1e-9
    assert c["p"] == "deepseek"


def test_local_gx10_is_free():
    c = _capture("local-gx10", "qwen2.5:14b", _Usage(prompt_tokens=5000, completion_tokens=2000))
    assert c["cost"] == 0.0


def test_anthropic_uses_input_output_token_names():
    c = _capture("anthropic", "claude-sonnet", _Usage(input_tokens=2000, output_tokens=1000))
    assert c["pt"] == 2000 and c["ct"] == 1000
    # 2000/1M*3 + 1000/1M*15 = 0.006 + 0.015 = 0.021
    assert abs(c["cost"] - 0.021) < 1e-9


def test_none_usage_records_zeroes_not_crash():
    c = _capture("openai", "gpt-4o-mini", None)
    assert c["pt"] == 0 and c["ct"] == 0 and c["cost"] == 0.0


def test_never_raises_on_db_failure():
    db = MagicMock()
    db.execute_update.side_effect = RuntimeError("db down")
    with patch("shared.database.get_postgres", return_value=db):
        # Must not raise — telemetry is best-effort.
        _record_cost("openai", "gpt-4o-mini", _Usage(prompt_tokens=1, completion_tokens=1), "x")


def test_all_providers_have_rates():
    for p in ("deepseek", "openai", "anthropic", "local-gx10"):
        assert p in _COST_RATES_PER_M
