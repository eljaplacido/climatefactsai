"""Corporate route unit tests — Phase 7 B3 + Phase 8 adapters (2026-05-24).

Pins the pure-function analyzer at the heart of /api/companies/{ticker}/analyze.
The analyzer is a heuristic MVP (keyword + disclosure-context lookup) — its
contract is that the *verdict taxonomy* is stable and that ECGT-prohibited
phrasings flag deterministically. A regression here would silently green-light
greenwashing claims on a board-facing surface, which is exactly the failure
mode the business-decision-maker persona cannot tolerate.

Tests target:
  1. _analyze_claim — claim-type + verdict + flag_reason routing per
     ECGT / SBTi / disclosure-context rules. Pure function, no I/O.
  2. _format_disclosure_context — string-builder pinned so future LLM
     prompt-engineering changes don't quietly drop SBTi or scope fields.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.company_routes import _analyze_claim, _format_disclosure_context
from api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# _analyze_claim — claim-type + verdict routing
# ---------------------------------------------------------------------------


class TestAnalyzeClaimOffsetPath:
    """ECGT Article 4 prohibits offset-based 'climate neutral' product claims
    without independent verification. Any offset marker MUST flag, regardless
    of disclosure context — the regulator's red line is the marketing copy,
    not the underlying ledger."""

    @pytest.mark.parametrize("text", [
        "We are climate neutral through carbon offsets",
        "Our products use offset credits to balance emissions",
        "Carbon offsetting makes us net zero",
        "100% of emissions covered by carbon offset purchases",
    ])
    def test_offset_markers_always_flag(self, text):
        claim_type, verdict, flag, evidence = _analyze_claim(text, "SBTi validated: Yes")
        assert claim_type == "offset_claim"
        assert verdict == "flagged"
        assert flag is not None
        assert "ECGT" in flag

    def test_offset_takes_precedence_over_net_zero(self):
        """If a claim contains BOTH 'net zero' AND 'offset', offset wins —
        ECGT applies to the offset mechanism even when paired with a
        legitimate net-zero target."""
        text = "Net zero by 2030 via carbon offsets"
        claim_type, verdict, _, _ = _analyze_claim(text, "")
        assert claim_type == "offset_claim"
        assert verdict == "flagged"


class TestAnalyzeClaimNetZeroPath:
    """Net-zero claims route on SBTi validation status. SBTi-validated →
    verified. Not validated → disputed with evidence URL pointing to the
    public SBTi registry so the user can verify themselves."""

    NET_ZERO_PHRASINGS = [
        "Net zero by 2030",
        "Net-zero target for 2040",
        "Carbon neutral operations by 2030",
        "Climate neutral by 2050",
    ]

    @pytest.mark.parametrize("text", NET_ZERO_PHRASINGS)
    def test_net_zero_with_sbti_validation_verifies(self, text):
        ctx = "SBTi validated: Yes"
        claim_type, verdict, flag, evidence = _analyze_claim(text, ctx)
        assert claim_type == "net_zero_target"
        assert verdict == "verified"
        assert flag is None
        assert evidence is None

    @pytest.mark.parametrize("text", NET_ZERO_PHRASINGS)
    def test_net_zero_without_sbti_validation_disputes(self, text):
        ctx = "SBTi validated: No"
        claim_type, verdict, flag, evidence = _analyze_claim(text, ctx)
        assert claim_type == "net_zero_target"
        assert verdict == "disputed"
        assert flag is not None
        assert "SBTi" in flag
        # Evidence URL must point at the public SBTi registry, not the
        # company's own marketing site — auditability requirement.
        assert evidence is not None
        assert "sciencebasedtargets.org" in evidence

    def test_net_zero_with_empty_context_disputes(self):
        """No disclosure context = no SBTi proof = disputed by default.
        Conservatism is the correct default for a fact-checking platform."""
        claim_type, verdict, flag, _ = _analyze_claim("Net zero by 2050", "")
        assert verdict == "disputed"
        assert flag is not None


class TestAnalyzeClaimReductionPath:
    """Generic 'we reduce emissions' claims are inherently unverifiable from
    text alone — they get 'partially_true' so the UI surfaces the disclosure
    rows and lets the user judge."""

    @pytest.mark.parametrize("text", [
        "We reduce our emissions every year",
        "Our Scope 1 reduction since 2019 is significant",
        "Cut emissions by half",
        "Emissions down 30% versus baseline",
    ])
    def test_reduction_claims_route_to_partially_true(self, text):
        claim_type, verdict, flag, _ = _analyze_claim(text, "")
        assert claim_type == "emissions_reduction"
        assert verdict == "partially_true"
        # Flag must reference the verification path — directing user to
        # the disclosure rows is the whole UX contract here.
        assert flag is not None
        assert "Scope" in flag


class TestAnalyzeClaimRenewablePath:
    """100% renewable energy claims are common greenwashing vectors —
    REC/PPA documentation is the SBTi/CDP-recognised proof. Without it,
    the claim is structurally weaker than full SBTi validation but not
    automatically false."""

    def test_100pct_renewable_routes_partially_true(self):
        claim_type, verdict, flag, _ = _analyze_claim(
            "We run on 100% renewable energy", ""
        )
        assert claim_type == "renewable_energy"
        assert verdict == "partially_true"
        assert flag is not None
        assert ("REC" in flag) or ("PPA" in flag)

    def test_renewable_without_100pct_falls_through(self):
        """Without the 100% qualifier the renewable path doesn't fire — the
        claim falls through to 'other/unverified'."""
        claim_type, verdict, _, _ = _analyze_claim(
            "We invest in renewable energy projects", ""
        )
        # Not the 100%-renewable path
        assert claim_type != "renewable_energy"


class TestAnalyzeClaimUnknownPath:
    """Claims that don't match any rule fall through to 'other/unverified'
    rather than being silently dropped — the user sees the same surface
    structure regardless of whether the analyzer matched."""

    def test_completely_unrelated_text(self):
        claim_type, verdict, flag, evidence = _analyze_claim(
            "We make great products and care about our customers", ""
        )
        assert claim_type == "other"
        assert verdict == "unverified"
        assert flag is None
        assert evidence is None

    def test_case_insensitivity(self):
        """Marketing copy capitalises freely; the matcher MUST be
        case-insensitive or 'NET ZERO BY 2030' silently slips through."""
        claim_type, verdict, _, _ = _analyze_claim(
            "NET ZERO BY 2030", "SBTi validated: Yes"
        )
        assert claim_type == "net_zero_target"
        assert verdict == "verified"


# ---------------------------------------------------------------------------
# _format_disclosure_context — string builder pinned for prompt-stability
# ---------------------------------------------------------------------------


class TestFormatDisclosureContext:
    """The context string is what the analyzer reads to decide SBTi-validated
    yes/no. If a refactor silently drops the 'SBTi validated:' line, every
    net-zero claim becomes 'disputed' regardless of reality. Pin the shape."""

    def _profile(self, **kwargs):
        defaults = dict(
            name="Acme Corp",
            country_code="DE",
            sbti_validated=True,
            net_zero_target_year=2030,
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_includes_company_name(self):
        ctx = _format_disclosure_context(self._profile(), [])
        assert "COMPANY: Acme Corp" in ctx

    def test_includes_country_when_present(self):
        ctx = _format_disclosure_context(self._profile(country_code="FR"), [])
        assert "Country: FR" in ctx

    def test_omits_country_when_none(self):
        ctx = _format_disclosure_context(self._profile(country_code=None), [])
        assert "Country:" not in ctx

    def test_sbti_validated_yes_renders_yes(self):
        ctx = _format_disclosure_context(self._profile(sbti_validated=True), [])
        assert "SBTi validated: Yes" in ctx

    def test_sbti_validated_no_renders_no(self):
        ctx = _format_disclosure_context(self._profile(sbti_validated=False), [])
        assert "SBTi validated: No" in ctx

    def test_net_zero_target_year_when_present(self):
        ctx = _format_disclosure_context(
            self._profile(net_zero_target_year=2040), []
        )
        assert "Net-zero target: 2040" in ctx

    def test_net_zero_target_year_omitted_when_none(self):
        ctx = _format_disclosure_context(
            self._profile(net_zero_target_year=None), []
        )
        assert "Net-zero target:" not in ctx

    def test_disclosures_emit_scope_breakdown(self):
        disclosures = [{
            "source": "cdp",
            "reporting_year": 2024,
            "scope1_tco2e": 1234.5,
            "scope2_tco2e_market": 6789.0,
            "scope3_tco2e": 99999.0,
            "scope1_2_verified": True,
            "assurance_level": "limited",
        }]
        ctx = _format_disclosure_context(self._profile(), disclosures)
        assert "cdp/2024" in ctx
        assert "S1:1234.5" in ctx
        assert "S2m:6789.0" in ctx
        assert "S3:99999.0" in ctx
        assert "verified:True" in ctx
        assert "assurance:limited" in ctx

    def test_disclosures_truncated_to_first_three(self):
        """We only feed the top-3 most recent disclosures into the analyzer
        context — keeps the prompt cheap and recent."""
        many = [
            {"source": "cdp", "reporting_year": y, "scope1_tco2e": None,
             "scope2_tco2e_market": None, "scope3_tco2e": None,
             "scope1_2_verified": False, "assurance_level": None}
            for y in (2024, 2023, 2022, 2021, 2020)
        ]
        ctx = _format_disclosure_context(self._profile(), many)
        # First three years appear
        assert "cdp/2024" in ctx
        assert "cdp/2023" in ctx
        assert "cdp/2022" in ctx
        # Earlier years dropped
        assert "cdp/2021" not in ctx
        assert "cdp/2020" not in ctx


# ---------------------------------------------------------------------------
# End-to-end: analyzer with realistic disclosure context
# ---------------------------------------------------------------------------


class TestAnalyzerWithRealisticContext:
    """Smoke-test the analyzer against the actual context strings produced by
    _format_disclosure_context. Catches drift where the analyzer's substring
    matchers and the context builder's wording could fall out of sync."""

    def test_validated_company_net_zero_claim_verifies(self):
        profile = SimpleNamespace(
            name="Microsoft", country_code="US",
            sbti_validated=True, net_zero_target_year=2030,
        )
        ctx = _format_disclosure_context(profile, [])
        claim_type, verdict, _, _ = _analyze_claim(
            "Microsoft commits to be net zero by 2030", ctx
        )
        assert claim_type == "net_zero_target"
        assert verdict == "verified"

    def test_unvalidated_company_net_zero_claim_disputes(self):
        profile = SimpleNamespace(
            name="Acme Oil", country_code="SA",
            sbti_validated=False, net_zero_target_year=2050,
        )
        ctx = _format_disclosure_context(profile, [])
        claim_type, verdict, flag, evidence = _analyze_claim(
            "We will be net zero by 2050", ctx
        )
        assert claim_type == "net_zero_target"
        assert verdict == "disputed"
        assert "SBTi" in flag
        assert "sciencebasedtargets.org" in evidence


# ---------------------------------------------------------------------------
# Phase 8 (2026-05-24) — Adapter sync endpoint.
#
# Token-gated, three valid sources. Run a real TestClient request against
# /api/companies/admin/sync/{source} and assert the gate behaviour. The
# adapter itself is mocked — these tests pin the ROUTE contract, not the
# upstream HTTP calls each adapter makes (those are exercised by separate
# adapter unit tests).
# ---------------------------------------------------------------------------


class TestAdapterSyncEndpoint:
    def test_503_when_sync_token_env_unset(self, monkeypatch):
        """Fail-safe default: if CORPORATE_SYNC_TOKEN is not set in the
        environment, the endpoint is *off* (503). A fresh deploy can't
        accidentally expose an unprotected ingestion trigger."""
        monkeypatch.delenv("CORPORATE_SYNC_TOKEN", raising=False)
        resp = client.post("/api/companies/admin/sync/sbti")
        assert resp.status_code == 503
        assert "CORPORATE_SYNC_TOKEN" in resp.json()["detail"]

    def test_401_when_token_wrong(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        resp = client.post(
            "/api/companies/admin/sync/sbti",
            headers={"x-corporate-sync-token": "wrong-secret"},
        )
        assert resp.status_code == 401

    def test_401_when_token_header_missing(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        resp = client.post("/api/companies/admin/sync/sbti")
        assert resp.status_code == 401

    def test_400_when_source_unknown(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        resp = client.post(
            "/api/companies/admin/sync/unknown_source",
            headers={"x-corporate-sync-token": "correct-secret"},
        )
        assert resp.status_code == 400
        # Lists the valid sources in the error so the operator can copy-paste.
        body = resp.json()
        for src in ("sbti", "cdp", "net_zero_tracker"):
            assert src in str(body)

    def test_200_when_token_valid_sbti(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        mock_result = {"source": "sbti", "upserted": 42, "errors": []}
        with patch(
            "app.domains.content.corporate.sbti_adapter.SBTIAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync = AsyncMock(return_value=mock_result)
            resp = client.post(
                "/api/companies/admin/sync/sbti",
                headers={"x-corporate-sync-token": "correct-secret"},
            )
        assert resp.status_code == 200
        assert resp.json() == mock_result

    def test_200_when_token_valid_cdp(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        mock_result = {"source": "cdp", "upserted": 100, "errors": []}
        with patch(
            "app.domains.content.corporate.cdp_adapter.CDPAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync = AsyncMock(return_value=mock_result)
            resp = client.post(
                "/api/companies/admin/sync/cdp",
                headers={"x-corporate-sync-token": "correct-secret"},
            )
        assert resp.status_code == 200
        assert resp.json()["source"] == "cdp"

    def test_200_when_token_valid_nzt(self, monkeypatch):
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        mock_result = {"source": "net_zero_tracker", "upserted": 50, "errors": []}
        with patch(
            "app.domains.content.corporate.nzt_adapter.NetZeroTrackerAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync = AsyncMock(return_value=mock_result)
            resp = client.post(
                "/api/companies/admin/sync/net_zero_tracker",
                headers={"x-corporate-sync-token": "correct-secret"},
            )
        assert resp.status_code == 200
        assert resp.json()["source"] == "net_zero_tracker"

    def test_partial_failure_still_returns_200(self, monkeypatch):
        """Adapter may report partial failures via the `errors` array.
        The endpoint surfaces that as 200 + the errors list, not 500 —
        the operator can decide whether to re-run."""
        monkeypatch.setenv("CORPORATE_SYNC_TOKEN", "correct-secret")
        mock_result = {
            "source": "sbti",
            "upserted": 30,
            "errors": ["row 5: missing target year", "row 12: invalid country"],
        }
        with patch(
            "app.domains.content.corporate.sbti_adapter.SBTIAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.sync = AsyncMock(return_value=mock_result)
            resp = client.post(
                "/api/companies/admin/sync/sbti",
                headers={"x-corporate-sync-token": "correct-secret"},
            )
        assert resp.status_code == 200
        assert len(resp.json()["errors"]) == 2
