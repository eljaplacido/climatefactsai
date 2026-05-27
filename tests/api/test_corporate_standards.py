"""Unit tests for corporate.standards (Stage 5 / M6).

Pure-function tests of assess_disclosure_against_standards — no DB,
no LLM. Verifies that the 5 standards each emit a verdict shape and
that the heuristic actually distinguishes well-disclosed from
sparsely-disclosed companies.
"""

from __future__ import annotations

import pytest

from app.domains.content.corporate.standards import (
    STANDARDS,
    STANDARDS_BY_ID,
    assess_disclosure_against_standards,
)


class TestStandardsRegistry:
    def test_five_standards_present(self):
        ids = {s["id"] for s in STANDARDS}
        assert ids == {"CSRD", "SBTi", "TCFD", "IFRS_S2", "GRI"}
        assert len(STANDARDS) == 5

    def test_every_standard_has_required_fields(self):
        required = {"id", "name", "jurisdiction", "effective_from",
                    "scope", "mandatory_disclosure", "evidence_url"}
        for s in STANDARDS:
            missing = required - set(s.keys())
            assert not missing, f"{s.get('id')}: missing {missing}"

    def test_standards_by_id_lookup(self):
        assert STANDARDS_BY_ID["CSRD"]["jurisdiction"] == "EU"
        assert STANDARDS_BY_ID["SBTi"]["jurisdiction"] == "Global (voluntary)"
        assert "SASB" in STANDARDS_BY_ID["IFRS_S2"]["mandatory_disclosure"][3]


class TestAssessmentAlignedCompany:
    """Apple-like profile: scope 1+2+3, SBTi validated, net-zero,
    reasonable assurance, no offset claims."""

    @pytest.fixture
    def disclosures(self):
        return [{
            "scope1_tco2e": 55400,
            "scope2_tco2e_market": 0,
            "scope2_tco2e_location": 32000,
            "scope3_tco2e": 14800000,
            "scope1_2_verified": True,
            "sbti_validated": True,
            "target_year": 2030,
            "baseline_year": 2015,
            "target_pct_reduction": 75,
            "net_zero_target_year": 2030,
            "offset_based_claims": False,
            "assurance_level": "reasonable",
        }]

    def test_all_five_standards_emit_verdict(self, disclosures):
        out = assess_disclosure_against_standards(disclosures)
        assert len(out) == 5
        ids = {r["id"] for r in out}
        assert ids == {"CSRD", "SBTi", "TCFD", "IFRS_S2", "GRI"}

    def test_sbti_aligned_for_validated_target(self, disclosures):
        out = assess_disclosure_against_standards(disclosures)
        sbti = next(r for r in out if r["id"] == "SBTi")
        # SBTi-validated + scope 1+2 + scope 3 + net-zero + no offsets
        # → should be aligned (all 5 points covered)
        assert sbti["status"] == "aligned", (
            f"SBTi expected aligned, got {sbti['status']}; "
            f"covered={sbti['covered_points']} missing={sbti['missing_points']}"
        )

    def test_csrd_partial_or_aligned(self, disclosures):
        out = assess_disclosure_against_standards(disclosures)
        csrd = next(r for r in out if r["id"] == "CSRD")
        assert csrd["status"] in {"aligned", "partial"}
        assert "Scope 1 emissions" in csrd["covered_points"]
        assert "Scope 3 across categories" in csrd["covered_points"]


class TestAssessmentOffsetCompany:
    """Company with offset-based 'climate neutral' claim. SBTi should
    explicitly flag this as missing the 'no offset pathways' point."""

    @pytest.fixture
    def disclosures(self):
        return [{
            "scope1_tco2e": 1000,
            "scope2_tco2e_market": 500,
            "scope3_tco2e": None,
            "sbti_validated": False,
            "target_year": 2030,
            "target_pct_reduction": 100,  # offset-based "carbon neutral"
            "net_zero_target_year": 2030,
            "offset_based_claims": True,
            "assurance_level": None,
        }]

    def test_sbti_flags_offset_claim(self, disclosures):
        out = assess_disclosure_against_standards(disclosures)
        sbti = next(r for r in out if r["id"] == "SBTi")
        # Missing SBTi validation + offset-only path → not aligned
        assert sbti["status"] in {"partial", "gap"}
        assert any("offset" in m.lower() for m in sbti["missing_points"])


class TestAssessmentEmptyDisclosure:
    def test_empty_disclosures_returns_gap_or_unknown(self):
        out = assess_disclosure_against_standards([])
        for r in out:
            # No data → either gap (missing everything) or unknown
            assert r["status"] in {"gap", "unknown", "partial"}, (
                f"{r['id']} should have signaled missing data; got {r['status']}"
            )
