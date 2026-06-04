"""Tests for the batched SBTi adapter (seq-7 + seq-7 batch, 2026-06-04).

The aggregation is pure (no DB) — these pin the validated-target detection
(status "Target set", not the legacy "active"), net-zero detection,
(name, country, year) dedup/merge, and the disclosure batch-upsert SQL shape.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.domains.content.corporate.sbti_adapter import (
    _aggregate_sbti_rows,
    _batch_upsert_disclosures,
    _resolve_company_ids,
)

_CMAP = {"united states": "US", "germany": "DE", "france": "FR"}

# Mimics the real CSV shape (rows already parsed to dicts).
_ROWS = [
    {"company_name": "Acme Corp", "status": "Target set", "action": "Commitment",
     "location": "United States", "sector": "C20"},
    {"company_name": "Acme Corp", "status": "NA", "action": "Target", "location": "United States",
     "target_year": "2030", "base_year": "2020", "target_value": "50", "type": "Absolute"},
    {"company_name": "Beta Inc", "status": "Active", "action": "Commitment", "location": "Germany"},
    {"company_name": "Gamma Co", "status": "Target set", "action": "Commitment",
     "location": "France", "target": "Net-zero", "commitment_type": "Net-zero"},
    {"company_name": "Gamma Co", "status": "NA", "action": "Target", "location": "France",
     "target_year": "2040", "type": "Net-zero"},
]


class TestAggregation:
    def test_three_distinct_companies(self):
        companies, _ = _aggregate_sbti_rows(_ROWS, _CMAP)
        assert set(companies.keys()) == {("acme corp", "US"), ("beta inc", "DE"), ("gamma co", "FR")}

    def test_target_set_company_disclosures_are_validated(self):
        _, disc = _aggregate_sbti_rows(_ROWS, _CMAP)
        acme = [d for k, d in disc.items() if k[0] == "acme corp"]
        assert acme and all(d["sbti_validated"] for d in acme)
        # the target-detail disclosure carries the year + reduction
        target = [d for d in acme if d["target_year"] == 2030]
        assert target and target[0]["target_pct_reduction"] == 50.0

    def test_active_only_company_not_validated(self):
        _, disc = _aggregate_sbti_rows(_ROWS, _CMAP)
        beta = [d for k, d in disc.items() if k[0] == "beta inc"]
        assert beta and not any(d["sbti_validated"] for d in beta)

    def test_net_zero_detected(self):
        _, disc = _aggregate_sbti_rows(_ROWS, _CMAP)
        gamma_nz = [d for k, d in disc.items() if k[0] == "gamma co" and d["net_zero_target_year"]]
        assert gamma_nz and gamma_nz[0]["net_zero_target_year"] == 2040

    def test_same_company_year_merges(self):
        # Two rows, same company+year, one validated one not -> merge keeps validated.
        rows = [
            {"company_name": "X", "status": "Target set", "action": "Commitment",
             "location": "France", "target_year": "2035"},
            {"company_name": "X", "status": "NA", "action": "Target",
             "location": "France", "target_year": "2035", "target_value": "60"},
        ]
        _, disc = _aggregate_sbti_rows(rows, _CMAP)
        keys = [k for k in disc if k[0] == "x" and k[2] == 2035]
        assert len(keys) == 1  # merged into one (name, cc, year)
        assert disc[keys[0]]["sbti_validated"] is True
        assert disc[keys[0]]["target_pct_reduction"] == 60.0


class TestBatchHelpers:
    def test_resolve_company_ids_maps_name_country(self):
        db = MagicMock()
        db.execute_query.return_value = [
            {"company_id": "id-a", "nk": "acme corp", "cc": "US"},
            {"company_id": "id-z", "nk": "other", "cc": "GB"},
        ]
        companies = {("acme corp", "US"): {}, ("missing", "US"): {}}
        cmap = _resolve_company_ids(db, companies)
        assert cmap == {("acme corp", "US"): "id-a"}  # only matched keys

    def test_batch_upsert_disclosures_builds_merge_sql(self):
        db = MagicMock()
        captured = {}
        db.execute_update.side_effect = lambda sql, params: captured.update({"sql": sql, "params": params})
        disclosures = {
            ("acme corp", "US", 2030): {"ckey": ("acme corp", "US"), "reporting_year": 2030,
                                        "sbti_validated": True, "target_year": 2030, "baseline_year": 2020,
                                        "target_pct_reduction": 50.0, "net_zero_target_year": None},
        }
        cmap = {("acme corp", "US"): "id-a"}
        n = _batch_upsert_disclosures(db, disclosures, cmap)
        assert n == 1
        assert "ON CONFLICT (company_id, source, reporting_year) DO UPDATE" in captured["sql"]
        # merge semantics: validated OR'd so a sync can't un-validate
        assert "EXCLUDED.sbti_validated OR company_climate_disclosures.sbti_validated" in captured["sql"]
        assert captured["params"]["v0"] is True and captured["params"]["cid0"] == "id-a"

    def test_disclosure_skipped_when_company_unresolved(self):
        db = MagicMock()
        disclosures = {("ghost", "US", 2030): {"ckey": ("ghost", "US"), "reporting_year": 2030,
                                               "sbti_validated": True, "target_year": None,
                                               "baseline_year": None, "target_pct_reduction": None,
                                               "net_zero_target_year": None}}
        n = _batch_upsert_disclosures(db, disclosures, cmap={})
        assert n == 0
        db.execute_update.assert_not_called()
