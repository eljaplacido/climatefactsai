"""Corporate sustainability report analysis — endpoint contract pins.

Deferred audit item #12 (2026-05-25). The endpoint glues three things:
fetch_full_text (Slice 4b) → ClaimExtractor → _analyze_claim. These
tests focus on the glue — not the LLM behaviour itself, which has its
own pin tests. We mock the heavy bits and verify:
  - shape: exactly one of report_url / report_text required
  - 404 for unknown company
  - 422 when fetch_full_text returns None for a URL
  - happy path: persists every extracted claim and aggregates verdicts
  - methodology_version is the report-specific value (not the
    single-claim one) so downstream audit trail can distinguish.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.company_routes import (
    AnalyzeReportRequest,
    AnalyzeReportResponse,
    analyze_company_report,
)


@pytest.fixture
def fake_profile():
    profile = MagicMock()
    profile.company_id = "cmp-uuid-1"
    profile.name = "Acme Climate Co"
    profile.country_code = "DE"
    profile.sbti_validated = True
    profile.net_zero_target_year = 2040
    return profile


def _atomic(text: str):
    """Build a minimal stand-in for AtomicClaim that has a `.text` attribute."""
    return MagicMock(text=text)


class TestAnalyzeReportRequestValidation:
    @pytest.mark.asyncio
    async def test_neither_url_nor_text_raises_400(self, fake_profile):
        from fastapi import HTTPException

        req = AnalyzeReportRequest()
        with patch(
            "app.domains.content.corporate.repository.get_company",
            return_value=fake_profile,
        ), patch("api.company_routes.get_postgres"):
            with pytest.raises(HTTPException) as exc:
                await analyze_company_report("ACME", req)
        assert exc.value.status_code == 400
        assert "Exactly one" in exc.value.detail

    @pytest.mark.asyncio
    async def test_both_url_and_text_raises_400(self, fake_profile):
        from fastapi import HTTPException

        req = AnalyzeReportRequest(
            report_url="https://example.com/r",
            report_text="a" * 300,
        )
        with patch(
            "app.domains.content.corporate.repository.get_company",
            return_value=fake_profile,
        ), patch("api.company_routes.get_postgres"):
            with pytest.raises(HTTPException) as exc:
                await analyze_company_report("ACME", req)
        assert exc.value.status_code == 400


class TestAnalyzeReportUnknownCompany:
    @pytest.mark.asyncio
    async def test_404_when_ticker_unknown(self):
        from fastapi import HTTPException

        req = AnalyzeReportRequest(report_text="x" * 300)
        with patch(
            "app.domains.content.corporate.repository.get_company",
            return_value=None,
        ), patch("api.company_routes.get_postgres"):
            with pytest.raises(HTTPException) as exc:
                await analyze_company_report("NOPE", req)
        assert exc.value.status_code == 404


class TestAnalyzeReportFetchFailure:
    @pytest.mark.asyncio
    async def test_422_when_fetch_returns_none(self, fake_profile):
        from fastapi import HTTPException

        req = AnalyzeReportRequest(report_url="https://example.com/dead")
        with patch(
            "app.domains.content.corporate.repository.get_company",
            return_value=fake_profile,
        ), patch("api.company_routes.get_postgres"), patch(
            "shared.full_text_fetch.fetch_full_text",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc:
                await analyze_company_report("ACME", req)
        assert exc.value.status_code == 422
        assert "report_text" in exc.value.detail  # fallback hint surfaced


class TestAnalyzeReportHappyPath:
    @pytest.mark.asyncio
    async def test_persists_and_aggregates_verdicts(self, fake_profile):
        req = AnalyzeReportRequest(
            report_text=(
                "Acme reached net-zero in 2024. "
                "We offset all remaining emissions via carbon credits. "
                "Scope 1 emissions reduced by 40% since baseline."
            ) * 5,  # padded past the 200-char min_length
        )

        # Extracted claims — each will hit a different _analyze_claim branch:
        #   "carbon-neutral via offsets" -> offset_claim, flagged
        #   "net zero by 2040, SBTi-validated" -> net_zero_target, verified
        #   "scope 1 reduced 40%" -> emissions_reduction, partially_true
        fake_claims = [
            _atomic("Acme is climate neutral through carbon offsets in 2024"),
            _atomic("Acme reached net zero with SBTi-validated targets"),
            _atomic("Acme cut emissions by 40 percent since the 2020 baseline"),
        ]

        with patch(
            "app.domains.content.corporate.repository.get_company",
            return_value=fake_profile,
        ), patch(
            "app.domains.content.corporate.repository.get_company_disclosures",
            return_value=[],
        ), patch(
            "app.domains.content.corporate.repository.upsert_company_claim",
            side_effect=lambda db, claim: f"claim-{hash(claim.claim_text) % 9999:04d}",
        ), patch("api.company_routes.get_postgres"), patch(
            "app.domains.intelligence.services.ClaimExtractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            instance.decompose_claims = AsyncMock(return_value=fake_claims)

            resp = await analyze_company_report("ACME", req)

        assert isinstance(resp, AnalyzeReportResponse)
        assert resp.company_id == "cmp-uuid-1"
        assert resp.text_length > 200
        assert resp.extracted_claims_count == 3
        # Three different verdicts hit.
        assert "flagged" in resp.verdict_summary
        assert "verified" in resp.verdict_summary
        assert "partially_true" in resp.verdict_summary
        # Methodology version distinguishes report-driven from single-claim.
        assert resp.methodology_version == "corporate_report_v1.0"
        # Every claim got an id from upsert_company_claim.
        assert all(c.claim_id.startswith("claim-") for c in resp.claims)
