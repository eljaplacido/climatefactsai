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
        assert body["methodology_version"] == "sustainability_v2_2026_05"
        assert body["methodology_url"].startswith("http")

    def test_components_weights_sum_to_one(self):
        resp = client.get("/api/methodology/sustainability-formula")
        body = resp.json()
        components = body["components"]
        # 2026-05-19: 5 components after ND-GAIN + UNFCCC NDC were wired in.
        # (emissions, renewable share, CAT rating, ND-GAIN, NDC reduction).
        assert len(components) == 5
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

class TestCalibrationEndpoint:
    """Phase 5 wave 4: /api/methodology/calibration computes Brier + ECE +
    Platt over the labeled dataset."""

    def _swap_db(self, fake):
        import shared.database as _shared_db
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = fake
        return prior

    def _restore(self, prior):
        import shared.database as _shared_db
        _shared_db._postgres_client = prior

    def test_returns_zero_state_when_no_labels(self):
        class _EmptyDB:
            def execute_query(self, q, p=None):
                return []
        prior = self._swap_db(_EmptyDB())
        try:
            r = client.get("/api/methodology/calibration")
            assert r.status_code == 200
            body = r.json()
            assert body["signal"] == "reliability_score"
            assert body["available"] is True
            assert body["metrics"]["n_labels"] == 0
            # Wave 1: fit_status is always present, even with zero labels.
            assert body["metrics"]["fit_status"] == "no_labels"
            assert body["metrics"]["margin_of_error"] is None
        finally:
            self._restore(prior)

    def test_degrades_when_migration_missing(self):
        """Phase 5 wave 6: fetch_labelled_predictions catches table-missing
        errors and returns empty, so the endpoint surfaces the same
        "awaiting reviewer input" state in both "migration missing" and
        "no labels yet" cases. DB internals don't leak to the API."""
        class _BrokenDB:
            def execute_query(self, q, p=None):
                raise RuntimeError("relation calibration_labels does not exist")
        prior = self._swap_db(_BrokenDB())
        try:
            r = client.get("/api/methodology/calibration")
            assert r.status_code == 200
            body = r.json()
            assert body["available"] is True
            assert body["metrics"]["n_labels"] == 0
            assert "awaiting reviewer input" in body["metrics"]["note"].lower()
        finally:
            self._restore(prior)

    def test_computes_metrics_on_labelled_data(self):
        """5 labels with mixed accuracy → Brier > 0, n_labels = 5, Platt fitted."""
        class _LabelledDB:
            def execute_query(self, q, p=None):
                return [
                    {"label_truth": 1.0, "reliability_score": 80},
                    {"label_truth": 0.0, "reliability_score": 70},
                    {"label_truth": 1.0, "reliability_score": 90},
                    {"label_truth": 0.0, "reliability_score": 60},
                    {"label_truth": 1.0, "reliability_score": 75},
                ]
        prior = self._swap_db(_LabelledDB())
        try:
            r = client.get("/api/methodology/calibration?n_bins=5")
            assert r.status_code == 200
            body = r.json()
            assert body["signal"] == "reliability_score"
            assert body["available"] is True
            m = body["metrics"]
            assert m["n_labels"] == 5
            assert isinstance(m["brier_score"], float)
            assert 0.0 <= m["brier_score"] <= 1.0
            assert isinstance(m["ece"], float)
            # Platt fitted because n >= 5.
            assert m["platt_a"] is not None
            assert m["platt_b"] is not None
            # Reliability diagram has the right number of bins.
            assert len(m["reliability_diagram"]) == 5
            # Wave 1 fit honesty: 5 labels is a "preview" fit (>=5, <50) with
            # a real margin of error; it is NOT applied at inference.
            assert m["fit_status"] == "preview"
            assert isinstance(m["margin_of_error"], float)
            assert m["stable_fit_min"] == 50
        finally:
            self._restore(prior)

    def test_unsupported_signal_returns_unavailable(self):
        """Phase 5 wave 6: agreement_score + hallucination_score ARE supported
        now; only invented names should return available=false."""
        r = client.get("/api/methodology/calibration?signal=made_up_signal")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert "not supported" in body["reason"]
        assert body["fit_status"] == "unsupported"

    def test_agreement_score_signal_supported(self):
        """Phase 5 wave 6: agreement_score now goes through the JSONB path query."""
        import shared.database as _shared_db

        class _AgreementDB:
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "from calibration_labels" in qn and "agreement_score" in qn:
                    return [
                        {"label_truth": 1.0, "raw": 0.85},
                        {"label_truth": 0.0, "raw": 0.30},
                        {"label_truth": 1.0, "raw": 0.90},
                        {"label_truth": 0.0, "raw": 0.40},
                        {"label_truth": 1.0, "raw": 0.75},
                    ]
                return []

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _AgreementDB()
        try:
            r = client.get("/api/methodology/calibration?signal=agreement_score")
            assert r.status_code == 200
            body = r.json()
            assert body["signal"] == "agreement_score"
            assert body["available"] is True
            assert body["metrics"]["n_labels"] == 5
            # Platt fitted (n >= 5).
            assert body["metrics"]["platt_a"] is not None
        finally:
            _shared_db._postgres_client = prior

    def test_hallucination_score_signal_supported(self):
        """Phase 5 wave 6: hallucination_score path works too."""
        import shared.database as _shared_db

        class _HallucinationDB:
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "1.0 - cp.hallucination_score" in qn:
                    return [
                        {"label_truth": 1.0, "raw": 0.9},
                        {"label_truth": 0.0, "raw": 0.3},
                    ]
                return []

        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _HallucinationDB()
        try:
            r = client.get("/api/methodology/calibration?signal=hallucination_score")
            assert r.status_code == 200
            body = r.json()
            assert body["signal"] == "hallucination_score"
            assert body["available"] is True
            assert body["metrics"]["n_labels"] == 2
        finally:
            _shared_db._postgres_client = prior


class TestCalibrationAdminEndpoints:
    """Phase 5 wave 5: POST /api/methodology/calibration/labels +
    POST /api/methodology/calibration/refit."""

    def _swap_db(self, fake):
        import shared.database as _shared_db
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = fake
        return prior

    def _restore(self, prior):
        import shared.database as _shared_db
        _shared_db._postgres_client = prior

    def test_submit_label_records_and_returns_id(self, monkeypatch):
        monkeypatch.delenv("CLILENS_CALIBRATION_ADMIN_SECRET", raising=False)

        class _LabelDB:
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "insert into calibration_labels" in qn:
                    return [{"id": 17, "labeled_at": "2026-05-16T12:00:00"}]
                return []

        prior = self._swap_db(_LabelDB())
        try:
            r = client.post(
                "/api/methodology/calibration/labels",
                json={
                    "url_analysis_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "label_truth": 0.85,
                    "labeled_by": "reviewer-1",
                    "label_method": "human_review",
                    "label_notes": "Mostly correct.",
                },
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["status"] == "recorded"
            assert body["id"] == 17
        finally:
            self._restore(prior)

    def test_submit_label_duplicate_returns_409(self, monkeypatch):
        monkeypatch.delenv("CLILENS_CALIBRATION_ADMIN_SECRET", raising=False)

        class _DupDB:
            def execute_query(self, q, p=None):
                raise RuntimeError(
                    'duplicate key value violates unique constraint "uq_calibration_labels_natural"'
                )

        prior = self._swap_db(_DupDB())
        try:
            r = client.post(
                "/api/methodology/calibration/labels",
                json={
                    "url_analysis_id": "x",
                    "label_truth": 0.5,
                    "labeled_by": "r",
                },
            )
            assert r.status_code == 409
        finally:
            self._restore(prior)

    def test_submit_label_rejects_out_of_range(self):
        # Pydantic validation should catch this before we even hit the DB.
        r = client.post(
            "/api/methodology/calibration/labels",
            json={
                "url_analysis_id": "x",
                "label_truth": 2.0,  # > 1.0
                "labeled_by": "r",
            },
        )
        assert r.status_code == 422

    def test_admin_secret_enforced_when_configured(self, monkeypatch):
        # Setting the env var via monkeypatch is scoped to this test; the
        # endpoint reads it on each call, so no module reload needed.
        monkeypatch.setenv("CLILENS_CALIBRATION_ADMIN_SECRET", "secret-xyz")

        # Wrong secret → 403.
        r = client.post(
            "/api/methodology/calibration/labels",
            headers={"X-Admin-Secret": "wrong"},
            json={
                "url_analysis_id": "x",
                "label_truth": 0.5,
                "labeled_by": "r",
            },
        )
        assert r.status_code == 403

    def test_admin_secret_correct_passes_through(self, monkeypatch):
        """Sanity: correct secret + valid body → 201 with the recorded label."""
        monkeypatch.setenv("CLILENS_CALIBRATION_ADMIN_SECRET", "secret-xyz")

        class _LabelDB:
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "insert into calibration_labels" in qn:
                    return [{"id": 42, "labeled_at": "2026-05-16T12:00:00"}]
                return []

        prior = self._swap_db(_LabelDB())
        try:
            r = client.post(
                "/api/methodology/calibration/labels",
                headers={"X-Admin-Secret": "secret-xyz"},
                json={
                    "url_analysis_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "label_truth": 0.85,
                    "labeled_by": "reviewer-1",
                },
            )
            assert r.status_code == 201, r.text
            assert r.json()["id"] == 42
        finally:
            self._restore(prior)

    def test_refit_returns_insufficient_data_when_few_labels(self, monkeypatch):
        monkeypatch.delenv("CLILENS_CALIBRATION_ADMIN_SECRET", raising=False)

        class _FewLabelsDB:
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "from calibration_labels" in qn:
                    return [{"label_truth": 1.0, "reliability_score": 80}]
                return []

        prior = self._swap_db(_FewLabelsDB())
        try:
            r = client.post("/api/methodology/calibration/refit")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "insufficient_data"
            assert body["n_labels"] == 1
        finally:
            self._restore(prior)

    def test_refit_writes_fit_row_and_returns_ok(self, monkeypatch):
        monkeypatch.delenv("CLILENS_CALIBRATION_ADMIN_SECRET", raising=False)

        class _EnoughLabelsDB:
            inserts: list = []
            def execute_query(self, q, p=None):
                qn = " ".join(q.split()).lower()
                if "from calibration_labels" in qn:
                    return [
                        {"label_truth": 1.0, "reliability_score": 90},
                        {"label_truth": 0.0, "reliability_score": 30},
                        {"label_truth": 1.0, "reliability_score": 80},
                        {"label_truth": 0.0, "reliability_score": 40},
                        {"label_truth": 1.0, "reliability_score": 75},
                    ]
                if "insert into calibration_fits" in qn:
                    self.inserts.append({"q": qn, "p": p or {}})
                    return [{"id": 7}]
                return []

        prior = self._swap_db(_EnoughLabelsDB())
        try:
            # min_labels default is 50 (production fence, commit 5dc7b12); this
            # test exercises the success path with the documented preview
            # override so 5 labels still produce an 'ok' fit.
            r = client.post(
                "/api/methodology/calibration/refit?signal=reliability_score&min_labels=5"
            )
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ok"
            assert body["n_labels"] == 5
            assert body["fit_id"] == 7
            assert body["platt_a"] is not None
            assert body["brier_score"] is not None
        finally:
            self._restore(prior)


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


# ---------------------------------------------------------------------------
# /api/methodology/hallucination-rates (Phase 6 wave 6)
# ---------------------------------------------------------------------------

class TestHallucinationRatesEndpoint:
    """Per-source / per-model hallucination-rate dashboard.

    Mocks the four DB queries the endpoint runs (overall, by_method,
    by_model, by_source) so each test exercises a specific scenario
    without needing the migrations or seeded data.
    """

    def _swap_db(self, fake):
        import shared.database as _shared_db
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = fake
        return prior

    def _restore(self, prior):
        import shared.database as _shared_db
        _shared_db._postgres_client = prior

    def test_graceful_degradation_when_table_missing(self):
        """Migration 021 not applied → available=False, all blocks empty,
        no 500."""
        class _BrokenDB:
            def execute_query(self, query, params=None):
                raise RuntimeError("relation claim_provenance does not exist")

        prior = self._swap_db(_BrokenDB())
        try:
            r = client.get("/api/methodology/hallucination-rates")
            assert r.status_code == 200
            body = r.json()
            assert body["available"] is False
            assert body["overall"]["n"] == 0
            assert body["by_extraction_method"] == []
            assert body["by_model"] == []
            assert body["by_source"] == []
            # The note should explain why.
            assert body["notes"] and any("claim_provenance" in n for n in body["notes"])
        finally:
            self._restore(prior)

    def test_overall_stats_populated_from_db(self):
        class _OverallDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                # Strip aliases to match across all four queries.
                if "from claim_provenance" in q and "group by" not in q and "with per_link" not in q:
                    # Overall: aggregate without grouping.
                    return [{"n": 100, "mean_risk": 0.12, "high_risk_rate": 0.04}]
                if "group by extraction_method" in q:
                    return []
                if "group by model_name" in q:
                    return []
                if "with per_link" in q:
                    return []
                return []

        prior = self._swap_db(_OverallDB())
        try:
            r = client.get("/api/methodology/hallucination-rates?window_days=30")
            assert r.status_code == 200
            body = r.json()
            assert body["available"] is True
            assert body["window_days"] == 30
            assert body["overall"]["n"] == 100
            assert body["overall"]["mean_risk"] == 0.12
            assert body["overall"]["high_risk_rate"] == 0.04
        finally:
            self._restore(prior)

    def test_by_method_sorted_descending(self):
        class _MethodDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                if "from claim_provenance" in q and "group by" not in q and "with per_link" not in q:
                    return [{"n": 1, "mean_risk": 0.0, "high_risk_rate": 0.0}]
                if "group by extraction_method" in q:
                    return [
                        {"extraction_method": "url_analysis_claim_extraction", "n": 80, "mean_risk": 0.15, "high_risk_rate": 0.05},
                        {"extraction_method": "deep_search_synthesis", "n": 20, "mean_risk": 0.08, "high_risk_rate": 0.02},
                    ]
                return []

        prior = self._swap_db(_MethodDB())
        try:
            r = client.get("/api/methodology/hallucination-rates")
            assert r.status_code == 200
            body = r.json()
            methods = body["by_extraction_method"]
            assert len(methods) == 2
            # Sorted by n descending.
            assert methods[0]["extraction_method"] == "url_analysis_claim_extraction"
            assert methods[0]["n"] == 80
            assert methods[1]["extraction_method"] == "deep_search_synthesis"
        finally:
            self._restore(prior)

    def test_by_model_aggregation(self):
        class _ModelDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                if "group by model_name" in q:
                    return [
                        {"model_name": "deepseek-chat", "n": 60, "mean_risk": 0.14, "high_risk_rate": 0.05},
                        {"model_name": "claude-sonnet-4-5", "n": 20, "mean_risk": 0.06, "high_risk_rate": 0.01},
                        # NULL model_name → coerced to 'unknown'
                        {"model_name": None, "n": 5, "mean_risk": 0.20, "high_risk_rate": 0.10},
                    ]
                if "from claim_provenance" in q and "group by" not in q and "with per_link" not in q:
                    return [{"n": 1, "mean_risk": 0.0, "high_risk_rate": 0.0}]
                return []

        prior = self._swap_db(_ModelDB())
        try:
            r = client.get("/api/methodology/hallucination-rates")
            body = r.json()
            models = body["by_model"]
            assert len(models) == 3
            # NULL model handled gracefully (or coerced to 'unknown' in row_stats).
            names = {m["model_name"] for m in models}
            assert "deepseek-chat" in names
            assert "claude-sonnet-4-5" in names
            assert "unknown" in names
        finally:
            self._restore(prior)

    def test_by_source_aggregation_with_top_n_limit(self):
        class _SourceDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                if "with per_link" in q:
                    # Verify the LIMIT parameter is honoured downstream.
                    assert params is not None
                    assert "limit" in params
                    # Return more rows than top_sources to verify capping happens
                    # at SQL level (we trust the DB; here just return the canned
                    # rows that should pass through).
                    return [
                        {"source_name": "reuters.com", "n": 30, "mean_risk": 0.08, "high_risk_rate": 0.03},
                        {"source_name": "bbc.com", "n": 25, "mean_risk": 0.10, "high_risk_rate": 0.04},
                        {"source_name": "unknown", "n": 5, "mean_risk": 0.20, "high_risk_rate": 0.10},
                    ]
                if "from claim_provenance" in q and "group by" not in q and "with per_link" not in q:
                    return [{"n": 1, "mean_risk": 0.0, "high_risk_rate": 0.0}]
                return []

        prior = self._swap_db(_SourceDB())
        try:
            r = client.get("/api/methodology/hallucination-rates?top_sources=2")
            body = r.json()
            sources = body["by_source"]
            # We return 3 rows from the fake (the fake doesn't enforce LIMIT);
            # the real DB would cap. Here we just verify the wire shape.
            assert any(s["source_name"] == "reuters.com" for s in sources)
            # Sorted by n descending.
            ns = [s["n"] for s in sources]
            assert ns == sorted(ns, reverse=True)
        finally:
            self._restore(prior)

    def test_partial_failure_degrades_gracefully(self):
        """If the by_source CTE fails (e.g. malformed UUID in source_article_ids)
        but the simpler queries succeed, we return what we have plus a note."""
        class _PartialFailDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                if "with per_link" in q:
                    raise RuntimeError("invalid input syntax for type uuid")
                if "from claim_provenance" in q and "group by" not in q:
                    return [{"n": 50, "mean_risk": 0.10, "high_risk_rate": 0.03}]
                if "group by extraction_method" in q:
                    return [{"extraction_method": "deep_search_synthesis", "n": 50, "mean_risk": 0.10, "high_risk_rate": 0.03}]
                if "group by model_name" in q:
                    return [{"model_name": "deepseek-chat", "n": 50, "mean_risk": 0.10, "high_risk_rate": 0.03}]
                return []

        prior = self._swap_db(_PartialFailDB())
        try:
            r = client.get("/api/methodology/hallucination-rates")
            body = r.json()
            assert r.status_code == 200
            assert body["available"] is True
            assert body["overall"]["n"] == 50
            assert len(body["by_extraction_method"]) == 1
            assert len(body["by_model"]) == 1
            # by_source failed → empty + note
            assert body["by_source"] == []
            assert body["notes"] and any("by_source" in n for n in body["notes"])
        finally:
            self._restore(prior)

    def test_window_days_param_clamped(self):
        """Out-of-range window_days clamps to [1, 365] — protects against
        accidental DoS on very large windows."""
        captured = {}

        class _CapturingDB:
            def execute_query(self, query, params=None):
                if params and "interval" in params:
                    captured["interval"] = params["interval"]
                return [{"n": 1, "mean_risk": 0.0, "high_risk_rate": 0.0}]

        prior = self._swap_db(_CapturingDB())
        try:
            # Negative → clamp to 1
            r = client.get("/api/methodology/hallucination-rates?window_days=-5")
            assert r.status_code == 200
            assert r.json()["window_days"] == 1
            # Excessive → clamp to 365
            r = client.get("/api/methodology/hallucination-rates?window_days=99999")
            assert r.json()["window_days"] == 365
            assert captured["interval"] == "365 days"
        finally:
            self._restore(prior)

    def test_zero_division_safety_with_empty_window(self):
        """Empty result set (no hallucination scores in window) → n=0, no NaN
        leakage."""
        class _EmptyDB:
            def execute_query(self, query, params=None):
                q = " ".join(query.split()).lower()
                # Aggregate query with no rows → return single row with NULLs.
                if "from claim_provenance" in q and "group by" not in q and "with per_link" not in q:
                    return [{"n": 0, "mean_risk": None, "high_risk_rate": None}]
                return []

        prior = self._swap_db(_EmptyDB())
        try:
            r = client.get("/api/methodology/hallucination-rates")
            body = r.json()
            assert r.status_code == 200
            assert body["available"] is True
            assert body["overall"]["n"] == 0
            assert body["overall"]["mean_risk"] == 0.0
            assert body["overall"]["high_risk_rate"] == 0.0
            # No NaN should leak to the wire.
            assert isinstance(body["overall"]["mean_risk"], (int, float))
        finally:
            self._restore(prior)
