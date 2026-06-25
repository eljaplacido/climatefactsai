"""Unit tests for the native context-compaction utilities.

Covers the Headroom-reflected token-reduction helpers used on the LLM path:
token estimation, word-boundary truncation, SmartCrusher JSON shrink,
order-preserving dedup, IntelligentContext budget fitting, and the whole-prompt
safety guard. All pure-Python, no external services.
"""

from __future__ import annotations

import json

import pytest

from app.domains.intelligence.context_compaction import (
    compact_json_str,
    compact_text,
    dedupe_by,
    estimate_tokens,
    fit_to_budget,
    guard_input,
    smartcrush_json,
)


class TestEstimateTokens:
    def test_empty_is_zero(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_rounds_up(self):
        # 5 chars / 4 -> 2 tokens (conservative ceil)
        assert estimate_tokens("abcde") == 2

    def test_monotonic(self):
        assert estimate_tokens("a" * 100) > estimate_tokens("a" * 10)

    def test_coerces_non_str(self):
        assert estimate_tokens(12345) >= 1


class TestCompactText:
    def test_noop_when_fits(self):
        s = "short text"
        assert compact_text(s, 100) == s

    def test_truncates_and_marks(self):
        s = "word " * 200  # ~1000 chars
        out = compact_text(s, 10)
        assert out.endswith("…")
        assert estimate_tokens(out) <= 11  # budget + suffix slack

    def test_never_exceeds_budget_materially(self):
        s = "x" * 4000
        out = compact_text(s, 50)
        assert len(out) <= 50 * 4 + 1

    def test_empty_input(self):
        assert compact_text("", 10) == ""
        assert compact_text(None, 10) == ""

    def test_zero_budget(self):
        assert compact_text("anything", 0) == "…"


class TestSmartcrushJson:
    def test_drops_empty_fields(self):
        out = smartcrush_json({"a": 1, "b": None, "c": "", "d": [], "e": {}})
        assert out == {"a": 1}

    def test_preserves_zero_and_false(self):
        out = smartcrush_json({"zero": 0, "flag": False, "n": 0.0})
        assert out["zero"] == 0
        assert out["flag"] is False
        assert "n" in out  # 0.0 preserved (numeric zero, not "empty")

    def test_rounds_floats(self):
        out = smartcrush_json({"x": 0.123456789})
        assert out["x"] == 0.1235

    def test_truncates_long_strings(self):
        out = smartcrush_json({"t": "a" * 500}, max_str=100)
        assert out["t"].endswith("…")
        assert len(out["t"]) <= 101

    def test_collapses_whitespace(self):
        out = smartcrush_json({"t": "a   b\n\n  c"})
        assert out["t"] == "a b c"

    def test_caps_list_length(self):
        out = smartcrush_json({"items": list(range(50))}, max_items=10)
        # 10 kept + 1 sentinel
        assert len(out["items"]) == 11
        assert "more" in str(out["items"][-1])

    def test_nested_depth_guard(self):
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}
        # Should not recurse forever / raise.
        out = smartcrush_json(deep, max_depth=3)
        assert out is not None

    def test_never_raises_on_unknown(self):
        class Weird:
            pass
        # passes through untouched, no raise
        assert smartcrush_json(Weird()) is not None


class TestCompactJsonStr:
    def test_compact_serialization(self):
        out = compact_json_str({"a": 1, "b": None})
        assert out == json.dumps({"a": 1}, separators=(",", ":"))

    def test_no_spaces(self):
        out = compact_json_str({"a": 1, "c": 2})
        assert " " not in out


class TestDedupeBy:
    def test_preserves_order(self):
        items = [{"id": 1}, {"id": 2}, {"id": 1}, {"id": 3}]
        out = dedupe_by(items, key=lambda x: x["id"])
        assert [x["id"] for x in out] == [1, 2, 3]

    def test_empty(self):
        assert dedupe_by([], key=lambda x: x) == []


class TestFitToBudget:
    def test_empty(self):
        res = fit_to_budget([], 100, render=str)
        assert res["kept"] == []
        assert res["dropped"] == 0

    def test_keeps_highest_score_first(self):
        items = [
            {"id": "low", "s": 0.1, "txt": "x" * 400},
            {"id": "high", "s": 0.9, "txt": "y" * 400},
        ]
        # Budget fits only one ~100-token item.
        res = fit_to_budget(
            items, 100, render=lambda i: i["txt"], score=lambda i: i["s"], min_items=1
        )
        kept_ids = [i["id"] for i in res["kept"]]
        assert kept_ids == ["high"]
        assert res["dropped"] == 1

    def test_min_items_guarantee(self):
        items = [{"txt": "z" * 4000}]  # way over budget
        res = fit_to_budget(items, 5, render=lambda i: i["txt"], min_items=1)
        assert len(res["kept"]) == 1  # forced in despite overflow

    def test_restores_original_order(self):
        items = [
            {"id": 0, "s": 0.2, "txt": "a"},
            {"id": 1, "s": 0.9, "txt": "b"},
            {"id": 2, "s": 0.5, "txt": "c"},
        ]
        res = fit_to_budget(
            items, 1000, render=lambda i: i["txt"], score=lambda i: i["s"]
        )
        # All fit; output should be back in original index order.
        assert [i["id"] for i in res["kept"]] == [0, 1, 2]

    def test_reports_used_tokens(self):
        items = [{"txt": "hello world"}]
        res = fit_to_budget(items, 1000, render=lambda i: i["txt"])
        assert res["used_tokens"] >= 1


class TestGuardInput:
    def test_noop_under_cap(self):
        s = "small prompt"
        assert guard_input(s, max_tokens=1000) == s

    def test_trims_when_over(self):
        s = "HEAD " + ("m" * 8000) + " TAIL"
        out = guard_input(s, max_tokens=100)
        assert "trimmed" in out
        assert estimate_tokens(out) <= 130  # cap + sentinel slack
        assert out.startswith("HEAD")
        assert out.rstrip().endswith("TAIL")

    def test_disabled_when_zero(self):
        s = "x" * 10000
        assert guard_input(s, max_tokens=0) == s

    def test_empty(self):
        assert guard_input("", max_tokens=100) == ""
