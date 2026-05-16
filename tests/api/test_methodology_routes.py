"""Methodology endpoint tests (Phase 4 wave 2).

Pins the public transparency surface so refactors of prompts.py /
sustainability_score.py / indicator_definitions can't silently break the
methodology drawer.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# /api/methodology/prompts
# ---------------------------------------------------------------------------

class TestMethodologyPrompts:
    def test_returns_registered_prompts(self):
        resp = client.get("/api/methodology/prompts")
        assert resp.status_code == 200
        body = resp.json()
        assert "prompts" in body
        assert body["total"] >= 3  # at least the three production prompts
        # The three known production prompts must all be listed.
        for name in (
            "deep_search_synthesis",
            "cynefin_classifier",
            "hallucination_grounding",
        ):
            assert name in body["prompts"], f"Missing prompt: {name}"

    def test_each_prompt_has_audit_metadata(self):
        resp = client.get("/api/methodology/prompts")
        prompts = resp.json()["prompts"]
        for name, meta in prompts.items():
            assert "version" in meta
            assert "fingerprint" in meta
            assert "description" in meta
            assert "rationale" in meta
            assert "has_system_prompt" in meta
            # Fingerprint shape: 16 hex chars
            assert re.fullmatch(r"[0-9a-f]{16}", meta["fingerprint"])

    def test_template_content_not_exposed(self):
        """The public endpoint must not leak the raw prompt template text —
        that's an exposure of internal IP / could enable prompt-injection
        crafting. Fingerprint + version are enough."""
        resp = client.get("/api/methodology/prompts")
        for name, meta in resp.json()["prompts"].items():
            assert "template" not in meta
            assert "system" not in meta  # also kept private


# ---------------------------------------------------------------------------
# /api/methodology/sustainability-formula
# ---------------------------------------------------------------------------

class TestSustainabilityFormulaEndpoint:
    def test_returns_methodology_version_and_url(self):
        resp = client.get("/api/methodology/sustainability-formula")
        assert resp.status_code == 200
        body = resp.json()
        assert body["methodology_version"] == "sustainability_v1_2026_05"
        assert body["methodology_url"].startswith("http")

    def test_components_weights_sum_to_one(self):
        resp = client.get("/api/methodology/sustainability-formula")
        body = resp.json()
        components = body["components"]
        assert len(components) == 3
        total = sum(c["weight"] for c in components)
        assert total == pytest.approx(1.0)
        # Each component must declare its normalizer name + a doc line.
        for c in components:
            assert "indicator_id" in c
            assert "weight" in c
            assert "description" in c
            assert "normalizer" in c
            assert c["normalizer_doc"]

    def test_confidence_band_table_covers_zero_through_five(self):
        resp = client.get("/api/methodology/sustainability-formula")
        body = resp.json()
        table = body["confidence_band_table"]
        # The endpoint emits bands for indicators_used in [0, 5].
        indicators_used = [row["indicators_used"] for row in table]
        assert indicators_used == [0, 1, 2, 3, 4, 5]
        # The band widths follow the documented schedule.
        bands = {row["indicators_used"]: row["band_plus_minus"] for row in table}
        assert bands[0] == 50.0
        assert bands[1] == 25.0
        assert bands[2] == 15.0
        assert bands[3] == 10.0


# ---------------------------------------------------------------------------
# /api/methodology/indicators
# ---------------------------------------------------------------------------

class TestIndicatorsEndpoint:
    def test_graceful_degradation_when_table_missing(self, monkeypatch):
        """If migration 020 hasn't been applied (table missing), endpoint
        must return available=False with an empty list, not 500."""
        import shared.database as _shared_db

        class _BrokenDB:
            def execute_query(self, query, params=None):
                raise RuntimeError("relation indicator_definitions does not exist")

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _BrokenDB()
        try:
            resp = client.get("/api/methodology/indicators")
            assert resp.status_code == 200
            body = resp.json()
            assert body["available"] is False
            assert body["indicators"] == []
            assert body["total_indicators"] == 0
        finally:
            _shared_db._postgres_client = prior

    def test_returns_seeded_indicators_when_table_present(self):
        """With the schema migration applied, the 9 seed indicators show up."""
        import shared.database as _shared_db

        class _SeededDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                if "from indicator_definitions" in q:
                    return [
                        {
                            "indicator_id": "emissions_tco2e_total",
                            "display_name": "Total GHG emissions",
                            "unit": "tCO2e",
                            "category": "emissions",
                            "description": "...",
                            "is_higher_better": False,
                            "methodology_url": "https://climatetrace.org/methodology",
                            "created_at": None,
                        },
                        {
                            "indicator_id": "renewable_share_electricity_percent",
                            "display_name": "Share of electricity from renewables",
                            "unit": "%",
                            "category": "energy",
                            "description": "...",
                            "is_higher_better": True,
                            "methodology_url": "https://ourworldindata.org/renewable-energy",
                            "created_at": None,
                        },
                    ]
                if "from country_indicators" in q:
                    return [
                        {"indicator_id": "emissions_tco2e_total", "countries": 50},
                        {"indicator_id": "renewable_share_electricity_percent", "countries": 35},
                    ]
                return []

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _SeededDB()
        try:
            resp = client.get("/api/methodology/indicators")
            assert resp.status_code == 200
            body = resp.json()
            assert body["available"] is True
            assert body["total_indicators"] == 2
            assert body["coverage_by_indicator"]["emissions_tco2e_total"] == 50
            # Methodology URLs preserved
            urls = [i["methodology_url"] for i in body["indicators"]]
            assert all(u.startswith("http") for u in urls)
        finally:
            _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# /api/methodology (bundle)
# ---------------------------------------------------------------------------

class TestMethodologyBundle:
    def test_bundle_contains_all_blocks(self):
        resp = client.get("/api/methodology")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("prompts", "sustainability_formula", "indicators"):
            assert key in body
        # git_revision is best-effort — present but may be None.
        assert "git_revision" in body

    def test_trailing_slash_alias(self):
        """/api/methodology and /api/methodology/ both work."""
        resp = client.get("/api/methodology/")
        assert resp.status_code == 200
