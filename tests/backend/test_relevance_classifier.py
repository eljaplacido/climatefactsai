"""Unit tests for the F1 LLM relevance classifier parsing + safe-fail logic.

The LLM call itself isn't unit-tested (needs a provider); these cover the
JSON extraction and the conservative never-hide-on-error contract.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.domains.intelligence.relevance_classifier import (
    RelevanceClassifier,
    _extract_json,
)


class TestExtractJson:
    def test_clean_json(self):
        d = _extract_json('{"relevant": false, "score": 0.0, "reason": "bus crash"}')
        assert d["relevant"] is False
        assert d["score"] == 0.0
        assert d["reason"] == "bus crash"

    def test_fenced_json(self):
        d = _extract_json('```json\n{"relevant": true, "score": 0.9, "reason": "x"}\n```')
        assert d["relevant"] is True
        assert d["score"] == 0.9

    def test_prose_preamble(self):
        d = _extract_json('Sure! Here is the result: {"relevant": true, "score": 1.0, "reason": "climate"}')
        assert d["relevant"] is True

    def test_non_json_boolean_fallback(self):
        # No valid JSON object, but the boolean + score are recoverable.
        d = _extract_json('relevant: false because score = 0.1 — off topic')
        assert d["relevant"] is False
        assert d.get("score") == 0.1

    def test_garbage_returns_empty(self):
        assert _extract_json("the model said nothing useful") == {}
        assert _extract_json("") == {}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestClassifySafeFail:
    def _clf(self):
        # db is unused by _call_llm; pass a stub.
        return RelevanceClassifier(db=object())

    def test_llm_none_keeps_article(self):
        clf = self._clf()
        with patch.object(clf._svc, "_call_llm", AsyncMock(return_value=None)):
            res = _run(clf.classify("t", "e", "src"))
        assert res["relevant"] is True
        assert res["llm_used"] is False

    def test_llm_exception_keeps_article(self):
        clf = self._clf()
        with patch.object(clf._svc, "_call_llm", AsyncMock(side_effect=RuntimeError("boom"))):
            res = _run(clf.classify("t", "e", "src"))
        assert res["relevant"] is True

    def test_unparseable_reply_keeps_article(self):
        clf = self._clf()
        with patch.object(clf._svc, "_call_llm", AsyncMock(return_value=("no json here", "deepseek", "m"))):
            res = _run(clf.classify("t", "e", "src"))
        assert res["relevant"] is True
        assert res["llm_used"] is True

    def test_off_topic_reply_flags(self):
        clf = self._clf()
        reply = ('{"relevant": false, "score": 0.02, "reason": "bus accident"}', "deepseek", "m")
        with patch.object(clf._svc, "_call_llm", AsyncMock(return_value=reply)):
            res = _run(clf.classify("Bus crash", "...", "Andina Peru"))
        assert res["relevant"] is False
        assert res["score"] == 0.02

    def test_score_clamped(self):
        clf = self._clf()
        reply = ('{"relevant": true, "score": 5.0, "reason": "x"}', "deepseek", "m")
        with patch.object(clf._svc, "_call_llm", AsyncMock(return_value=reply)):
            res = _run(clf.classify("t", "e", "s"))
        assert res["score"] == 1.0
