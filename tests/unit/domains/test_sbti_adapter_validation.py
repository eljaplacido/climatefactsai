"""Regression test for the SBTi adapter validated-target detection (seq-7).

The live SBTi dashboard splits a company across rows: action="Commitment" rows
carry the lifecycle `status` (Target set / Active / Removed), while
action="Target" rows carry the target details with status="NA". The old
condition `action=="target" AND status=="active"` could never match, so only the
9 seed companies showed as sbti_validated instead of ~3,900. The fix: a company
is validated when it has any "Target set" row, and every disclosure of that
company is marked validated.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.domains.content.corporate.sbti_adapter import SBTIAdapter

# Mimics the real CSV shape: a Commitment row carries status; a Target row
# carries the target details with status=NA.
SAMPLE_CSV = (
    "company_name,isin,lei,location,sector,status,action,target_year,base_year,"
    "target_value,type,commitment_type,target\n"
    '"Acme Corp",,,United States,C20,Target set,Commitment,,,,,,\n'
    '"Acme Corp",,,United States,C20,NA,Target,2030,2020,50,Absolute,,Near-term\n'
    '"Beta Inc",,,Germany,C10,Active,Commitment,,,,,,\n'
    '"Gamma Co",,,France,C30,Target set,Commitment,,,,Net-zero,Net-zero,Net-zero\n'
    '"Gamma Co",,,France,C30,NA,Target,2040,2020,100,Net-zero,,Long-term\n'
)


def _run_sync_capturing():
    captured = []
    adapter = SBTIAdapter()
    resp = MagicMock()
    resp.text = SAMPLE_CSV
    resp.raise_for_status = MagicMock()
    adapter.client = MagicMock()
    adapter.client.get = AsyncMock(return_value=resp)
    with patch(
        "app.domains.content.corporate.sbti_adapter.upsert_company",
        side_effect=lambda db, name, **kw: name,  # company_id = name, so we can group
    ), patch(
        "app.domains.content.corporate.sbti_adapter.upsert_disclosure",
        side_effect=lambda db, rec: captured.append(rec),
    ):
        result = asyncio.run(adapter.sync(db=MagicMock()))
    return result, captured


class TestSbtiValidatedDetection:
    def test_target_set_company_is_validated(self):
        _, captured = _run_sync_capturing()
        validated = {rec.company_id for rec in captured if rec.sbti_validated}
        assert "Acme Corp" in validated   # has a 'Target set' row
        assert "Gamma Co" in validated

    def test_active_only_company_is_not_validated(self):
        _, captured = _run_sync_capturing()
        validated = {rec.company_id for rec in captured if rec.sbti_validated}
        assert "Beta Inc" not in validated  # only 'Active' (committed, not validated)

    def test_validation_propagates_to_target_detail_row(self):
        """The action=Target row (which carries target_year) must also be marked
        validated, so the company's rich disclosure is the validated one."""
        _, captured = _run_sync_capturing()
        acme_target = [
            r for r in captured if r.company_id == "Acme Corp" and r.target_year == 2030
        ]
        assert acme_target and acme_target[0].sbti_validated

    def test_net_zero_detected_from_target_commitment_type(self):
        _, captured = _run_sync_capturing()
        gamma_nz = [
            r for r in captured if r.company_id == "Gamma Co" and r.net_zero_target_year
        ]
        assert gamma_nz  # net-zero signal picked up from target/commitment_type/type

    def test_all_rows_upserted(self):
        result, captured = _run_sync_capturing()
        assert result["upserted"] == 5
        assert len(captured) == 5
