"""Tests for the company head-to-head compare endpoint (audit seq-13).

Pins the ambition-leader logic (earlier net-zero / higher reduction / SBTi /
assurance) and that raw scope emissions are returned WITHOUT a leader, plus 404
on a missing company.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from app.domains.content.corporate.schemas import CompanyProfile

client = TestClient(app)


def _profile(cid, name, ticker, sbti, nz):
    return CompanyProfile(
        company_id=cid, name=name, ticker=ticker, country_code="US",
        sector_nace="Tech", disclosure_count=1, latest_disclosure_year=2023,
        sbti_validated=sbti, net_zero_target_year=nz,
    )


def _run(profs, discs, a="AAA", b="BBB"):
    with patch(
        "app.domains.content.corporate.repository.get_company",
        side_effect=lambda db, ident: profs.get(ident),
    ), patch(
        "app.domains.content.corporate.repository.get_company_disclosures",
        side_effect=lambda db, cid, **k: discs.get(cid, []),
    ):
        return client.get(f"/api/companies/compare?a={a}&b={b}")


def test_ambition_leaders_declared_correctly():
    profs = {
        "AAA": _profile("id-a", "Alpha", "AAA", True, 2030),
        "BBB": _profile("id-b", "Beta", "BBB", True, 2040),
    }
    discs = {
        "id-a": [{"target_pct_reduction": 50, "target_year": 2030, "scope1_2_verified": True,
                  "scope1_tco2e": 100, "scope2_tco2e_market": 50, "scope3_tco2e": 1000,
                  "net_zero_target_year": 2030}],
        "id-b": [{"target_pct_reduction": 30, "target_year": 2040, "scope1_2_verified": False,
                  "scope1_tco2e": 200, "scope2_tco2e_market": 80, "scope3_tco2e": 2000,
                  "net_zero_target_year": 2040}],
    }
    r = _run(profs, discs)
    assert r.status_code == 200
    body = r.json()
    c = body["comparison"]
    assert c["net_zero_target_year"]["leader"] == "a"   # 2030 earlier than 2040
    assert c["target_pct_reduction"]["leader"] == "a"    # 50% > 30%
    assert c["scope1_2_verified"]["leader"] == "a"        # verified beats not
    assert c["sbti_validated"]["leader"] == "tie"         # both validated
    assert body["ambition_leader"] == "a"


def test_raw_emissions_have_no_leader():
    profs = {"AAA": _profile("id-a", "Alpha", "AAA", True, 2030),
             "BBB": _profile("id-b", "Beta", "BBB", True, 2030)}
    discs = {"id-a": [{"scope1_tco2e": 100}], "id-b": [{"scope1_tco2e": 200}]}
    body = _run(profs, discs).json()
    # emissions block is values-only — no 'leader' key anywhere in it
    assert body["emissions"]["scope1_tco2e"] == {"a": 100, "b": 200}
    assert "leader" not in body["emissions"]["scope1_tco2e"]


def test_404_when_a_company_is_missing():
    with patch("app.domains.content.corporate.repository.get_company",
               side_effect=lambda db, ident: None):
        r = client.get("/api/companies/compare?a=NOPE&b=ALSO")
    assert r.status_code == 404


def test_missing_metric_defers_to_company_with_data():
    profs = {"AAA": _profile("id-a", "Alpha", "AAA", True, 2030),
             "BBB": _profile("id-b", "Beta", "BBB", True, None)}
    discs = {"id-a": [{"target_pct_reduction": 40}], "id-b": [{}]}
    body = _run(profs, discs).json()
    # a has a reduction target, b has none -> a leads that dimension
    assert body["comparison"]["target_pct_reduction"]["leader"] == "a"
    # b has no net-zero year, a does -> a leads
    assert body["comparison"]["net_zero_target_year"]["leader"] == "a"
