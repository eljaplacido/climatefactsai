"""Prompt registry tests (Phase 4 wave 1).

Pins the versioning + fingerprinting contract so future prompt changes are
visible in code review.
"""

from __future__ import annotations

import pytest

from app.domains.intelligence.prompts import (
    PROMPTS,
    PromptTemplate,
    get_prompt,
    list_prompts,
)


class TestPromptTemplateFingerprint:
    def test_fingerprint_is_stable_for_same_content(self):
        p1 = PromptTemplate(
            name="x", version="v1.0",
            template="Hello {name}",
            description="d", rationale="r",
        )
        p2 = PromptTemplate(
            name="y",  # different name
            version="v9.9",  # different version
            template="Hello {name}",  # SAME content
            description="d2", rationale="r2",
        )
        assert p1.fingerprint == p2.fingerprint

    def test_fingerprint_changes_when_template_changes(self):
        p1 = PromptTemplate(
            name="x", version="v1.0",
            template="Hello {name}",
            description="d", rationale="r",
        )
        p2 = PromptTemplate(
            name="x", version="v1.0",
            template="Hello {name}!",  # different
            description="d", rationale="r",
        )
        assert p1.fingerprint != p2.fingerprint

    def test_fingerprint_includes_system_prompt(self):
        """Changes to system prompt must also change fingerprint."""
        p1 = PromptTemplate(
            name="x", version="v1.0",
            template="t", system="You are A.",
            description="d", rationale="r",
        )
        p2 = PromptTemplate(
            name="x", version="v1.0",
            template="t", system="You are B.",
            description="d", rationale="r",
        )
        assert p1.fingerprint != p2.fingerprint

    def test_fingerprint_is_16_hex_chars(self):
        p = PromptTemplate(
            name="x", version="v1.0",
            template="x", description="d", rationale="r",
        )
        fp = p.fingerprint
        assert len(fp) == 16
        # Pure hex
        assert all(c in "0123456789abcdef" for c in fp)


class TestPromptTemplateFormat:
    def test_format_renders_placeholders(self):
        p = PromptTemplate(
            name="x", version="v1.0",
            template="Hello {name}, you have {n} messages.",
            description="d", rationale="r",
        )
        out = p.format(name="World", n=3)
        assert out == "Hello World, you have 3 messages."

    def test_format_missing_placeholder_raises(self):
        p = PromptTemplate(
            name="x", version="v1.0",
            template="Hello {name}",
            description="d", rationale="r",
        )
        with pytest.raises(KeyError):
            p.format()  # no `name` passed


class TestPromptRegistry:
    def test_get_prompt_returns_registered(self):
        p = get_prompt("deep_search_synthesis")
        assert p.name == "deep_search_synthesis"
        assert p.version == "v1.0"

    def test_get_prompt_unknown_raises_with_registered_list(self):
        with pytest.raises(KeyError) as exc:
            get_prompt("not_a_real_prompt")
        msg = str(exc.value)
        # Error message includes the list of known prompts for discoverability.
        assert "not_a_real_prompt" in msg
        assert "deep_search_synthesis" in msg

    def test_required_prompts_registered(self):
        """These prompts are referenced by production code paths."""
        for name in (
            "deep_search_synthesis",
            "cynefin_classifier",
            "hallucination_grounding",
        ):
            assert name in PROMPTS, f"Required prompt {name} not registered"

    def test_list_prompts_returns_audit_metadata(self):
        out = list_prompts()
        for name, meta in out.items():
            assert meta["version"]
            assert meta["fingerprint"]
            assert meta["description"]
            assert len(meta["fingerprint"]) == 16


class TestAuditDict:
    def test_as_audit_dict_compact_shape(self):
        p = get_prompt("deep_search_synthesis")
        audit = p.as_audit_dict()
        # Compact: only the three keys we want in methodology blocks.
        assert set(audit.keys()) == {"name", "version", "fingerprint"}
        assert audit["name"] == "deep_search_synthesis"


# ---------------------------------------------------------------------------
# Spot-check: registered prompts have content
# ---------------------------------------------------------------------------

class TestRegisteredPromptsHaveContent:
    @pytest.mark.parametrize("name", list(PROMPTS.keys()))
    def test_prompt_has_required_fields(self, name):
        p = PROMPTS[name]
        assert p.template.strip(), f"{name} has empty template"
        assert p.description.strip(), f"{name} has empty description"
        assert p.rationale.strip(), f"{name} has empty rationale"
        # Version starts with "v"
        assert p.version.startswith("v"), f"{name} version doesn't start with 'v'"
