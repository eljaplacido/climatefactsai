"""Regression guard for the chat CacheAligner invariant (Headroom, INT-05).

The agentic-chat system prompt must be a STATIC, byte-identical prefix so it is
eligible for provider-side prompt/KV-cache reuse across turns. All volatile
content (live counts, the current view, retrieved articles, the question) belongs
in the user message. These tests fail loudly if someone re-splices dynamic
content back into the system prefix.
"""

from __future__ import annotations

from api.chat_routes import _chat_system_prompt


class TestChatCachePrefix:
    def test_system_prompt_is_stable_and_cached(self):
        a = _chat_system_prompt()
        b = _chat_system_prompt()
        assert a == b
        assert a is b  # cached singleton → identical bytes every turn

    def test_system_prompt_carries_the_static_catalogues(self):
        s = _chat_system_prompt()
        assert "CAPABILITIES" in s
        assert "PLATFORM FEATURES" in s
        # The ~2KB action catalogue now lives in the prefix (was appended to the
        # END of the user prompt, defeating prefix caching).
        assert "AVAILABLE ACTIONS" in s

    def test_system_prompt_has_no_volatile_content(self):
        s = _chat_system_prompt()
        # These markers belong to the per-request USER message only.
        assert "PLATFORM SNAPSHOT" not in s
        assert "CURRENT VIEW" not in s
        assert "USER QUESTION" not in s
        assert "RELEVANT ARTICLES FROM DATABASE" not in s
