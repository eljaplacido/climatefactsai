"""Skills registry + /api/skills endpoint tests — Phase 4C (2026-05-24).

Pins the structural properties of the canonical SKILLS_REGISTRY plus
the HTTP contract for the introspection endpoints. The cross-source
drift test (registry ↔ prompt ↔ frontend dispatcher) lives in
test_agentic_skill_pin.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

from app.domains.intelligence.skills import (
    SKILLS_REGISTRY,
    Skill,
    SkillParameter,
    get_skill,
    list_skills,
    render_actions_block_for_prompt,
    serialize_registry,
    serialize_skill,
    skills_by_mode,
)


client = TestClient(app)


class TestRegistryShape:
    def test_registry_has_expected_skill_count(self):
        """Canonical skill-count pin. 2026-06-02: corrected to 22 — the
        registry had grown (open_company, verify_corporate_claim, save_item,
        subscribe_research_topic, explore_scenario, analyze_corporate_report,
        explore_entity, explain_connection, flag_off_topic, suggest_company,
        promote_golden_example, explore_sdg, tag_sdgs) while this pin still
        asserted 11, silently failing CI. Bumping needs an explicit decision."""
        assert len(SKILLS_REGISTRY) == 22

    def test_list_skills_returns_stable_order(self):
        """Two consecutive calls return the same order — clients can
        rely on positional stability for UI rendering."""
        a = [s.name for s in list_skills()]
        b = [s.name for s in list_skills()]
        assert a == b

    def test_get_skill_known_name(self):
        skill = get_skill("navigate")
        assert skill is not None
        assert skill.name == "navigate"
        assert skill.mode == "auto"

    def test_get_skill_unknown_returns_none(self):
        assert get_skill("definitely_not_a_skill") is None

    def test_skills_by_mode_partition(self):
        auto = {s.name for s in skills_by_mode("auto")}
        confirm = {s.name for s in skills_by_mode("confirm")}
        # No skill is both
        assert auto.isdisjoint(confirm)
        # Union covers everything
        assert auto | confirm == set(SKILLS_REGISTRY.keys())

    @pytest.mark.parametrize("skill_name", list(SKILLS_REGISTRY.keys()))
    def test_every_skill_has_complete_metadata(self, skill_name):
        skill = SKILLS_REGISTRY[skill_name]
        assert skill.name == skill_name
        assert skill.description
        assert skill.mode in ("auto", "confirm")
        # Target surfaces is required documentation
        assert len(skill.target_surfaces) >= 1


class TestSerialisation:
    def test_serialize_skill_shape(self):
        skill = get_skill("navigate")
        payload = serialize_skill(skill)
        assert payload["name"] == "navigate"
        assert payload["mode"] == "auto"
        assert payload["description"]
        assert isinstance(payload["parameters"], list)
        assert isinstance(payload["target_surfaces"], list)
        for p in payload["parameters"]:
            assert "name" in p
            assert "type" in p
            assert "description" in p
            assert "required" in p

    def test_serialize_registry_envelope(self):
        envelope = serialize_registry()
        assert isinstance(envelope["skills"], list)
        assert envelope["total"] == len(SKILLS_REGISTRY)
        assert envelope["modes"]["auto"] + envelope["modes"]["confirm"] == len(SKILLS_REGISTRY)

    def test_serialized_skill_is_pure_json(self):
        """Every serialised skill must be JSON-roundtrippable so the
        /api/skills endpoint can ship it without dataclass-isnotjson
        errors at runtime."""
        import json
        envelope = serialize_registry()
        s = json.dumps(envelope)
        rev = json.loads(s)
        assert rev["total"] == len(SKILLS_REGISTRY)


class TestRenderActionsBlock:
    def test_renders_every_action(self):
        block = render_actions_block_for_prompt()
        for name in SKILLS_REGISTRY:
            assert f"- {name}:" in block

    def test_renders_descriptions(self):
        block = render_actions_block_for_prompt()
        for skill in list_skills():
            # Description text appears verbatim
            assert skill.description in block


# ---------------------------------------------------------------------------
# /api/skills endpoint
# ---------------------------------------------------------------------------


class TestSkillsEndpoint:
    def test_list_endpoint_returns_full_registry(self):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(SKILLS_REGISTRY)
        assert len(body["skills"]) == len(SKILLS_REGISTRY)
        names = {s["name"] for s in body["skills"]}
        assert names == set(SKILLS_REGISTRY.keys())

    def test_list_endpoint_is_unauthenticated(self):
        """The skills registry IS public — same posture as /methodology.
        No Authorization header sent here = should still work."""
        resp = client.get("/api/skills")
        assert resp.status_code == 200

    def test_single_skill_endpoint_returns_one(self):
        resp = client.get("/api/skills/navigate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "navigate"
        assert body["mode"] == "auto"

    def test_single_skill_endpoint_404s_unknown(self):
        resp = client.get("/api/skills/send_email")
        assert resp.status_code == 404

    def test_single_skill_payload_matches_serialize_skill(self):
        """The single-skill endpoint payload must match the entry that
        appears in the list endpoint — same skill, same serialiser, same
        bytes."""
        list_resp = client.get("/api/skills").json()
        single_resp = client.get("/api/skills/bookmark_article").json()
        list_entry = next(
            s for s in list_resp["skills"] if s["name"] == "bookmark_article"
        )
        assert list_entry == single_resp


# ---------------------------------------------------------------------------
# Dataclass invariants — guard against frozen=True being removed
# ---------------------------------------------------------------------------


class TestDataclassInvariants:
    def test_skill_dataclass_is_frozen(self):
        """Mutability would let runtime code patch the canonical registry —
        which would break the cross-source pin without warning."""
        skill = get_skill("navigate")
        with pytest.raises((AttributeError, Exception)):
            skill.name = "renamed"

    def test_skill_parameter_dataclass_is_frozen(self):
        skill = get_skill("navigate")
        if not skill.parameters:
            return
        p = skill.parameters[0]
        with pytest.raises((AttributeError, Exception)):
            p.name = "renamed"

    def test_skill_module_exports_expected_symbols(self):
        """Public surface of skills.py — adding to this set is fine, but
        removing anything here breaks downstream consumers (api/skills_routes.py,
        api/aoi_*, chatActionDispatcher.ts at runtime, the skill-pin test)."""
        from app.domains.intelligence import skills as skills_mod
        for sym in (
            "SKILLS_REGISTRY",
            "Skill",
            "SkillParameter",
            "list_skills",
            "get_skill",
            "skills_by_mode",
            "serialize_skill",
            "serialize_registry",
            "render_actions_block_for_prompt",
        ):
            assert hasattr(skills_mod, sym), f"skills module missing {sym!r}"
