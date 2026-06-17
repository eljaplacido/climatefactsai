"""Company climate disclosure routes — /api/companies

GET  /api/companies                    — paginated company index
GET  /api/companies/{ticker}           — company profile + disclosures + claims
GET  /api/companies/{ticker}/claims    — company claims list
POST /api/companies/{ticker}/analyze   — LLM-based claim verification
POST /api/companies/admin/sync/{source} — Phase 8: trigger SBTi/CDP/NZT adapter
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user, get_optional_user
from api.quota_service import QuotaService
from api.rate_limiter import check_premium_feature
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("company-routes")
router = APIRouter(prefix="/api/companies", tags=["Companies"])


class AnalyzeClaimRequest(BaseModel):
    claim_text: str = Field(..., min_length=10, max_length=2000)


class AnalyzeClaimResponse(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str
    verdict: str
    evidence: Optional[str] = None
    flag_reason: Optional[str] = None
    methodology_version: str = "corporate_v1.0"


# Deferred audit item #12 (Slice "report-analysis", 2026-05-25).
# ESG officers need to drop a sustainability-report URL and get
# end-to-end claim extraction + verification rather than pasting
# claim-by-claim into /analyze. Reuses the Slice 4b full_text_fetch
# helper + the existing ClaimExtractor (DeepSeek, research_report
# content-type) + the in-file _analyze_claim heuristic.

class AnalyzeReportRequest(BaseModel):
    report_url: Optional[str] = Field(
        None,
        description="Public URL of a sustainability report (HTML or PDF link page)",
    )
    report_text: Optional[str] = Field(
        None,
        min_length=200,
        max_length=200000,
        description="Pasted report text — alternative to report_url",
    )
    max_claims: int = Field(default=20, ge=1, le=50)


class AnalyzedReportClaim(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: str
    verdict: str
    flag_reason: Optional[str] = None
    evidence: Optional[str] = None


class AnalyzeReportResponse(BaseModel):
    company_id: str
    report_url: Optional[str] = None
    text_length: int
    extracted_claims_count: int
    claims: List[AnalyzedReportClaim]
    verdict_summary: Dict[str, int]
    methodology_version: str = "corporate_report_v1.0"


@router.get("")
async def list_companies(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("richness", regex="^(richness|name|recent)$"),
    has_climate_data: bool = Query(False, description="Only companies with scope/SBTi/net-zero data"),
    sbti_only: bool = Query(False, description="Only companies with sbti_validated=TRUE disclosure"),
    user: dict = Depends(get_optional_user),
):
    """List companies in the Corporate Climate Tracker.

    Golden Example fix (2026-05-27, see Golden-Artifact-Examples-2026-05-27.md):
    default sort is now `richness` (sbti_validated + scope + net_zero +
    disclosure_count + ticker), so well-known public companies (Apple,
    Microsoft, Alphabet, etc.) surface first instead of the alphabetic
    SBTi shell companies that made the index look empty.
    """
    from app.domains.content.corporate.repository import (
        list_companies as _list,
        companies_stats as _stats,
    )

    db = get_postgres()
    # Resilience fix (2026-05-27 evening): the original try/except wrapped
    # BOTH _list and _stats — when one failed, the OTHER got blanked too.
    # ba69ff3 broke _stats with a bad column reference and the entire
    # Corporate Tracker rendered empty even though _list was fine.
    # Now: independent try/except per call so a stats hiccup doesn't
    # erase the company list and vice-versa. Each surfaces zero/empty
    # instead of taking the other down.
    try:
        rows = _list(
            db, limit=limit, offset=offset, sort=sort,
            has_climate_data=has_climate_data, sbti_only=sbti_only,
        )
    except Exception as e:
        logger.warning(f"list_companies list query failed: {e}")
        rows = []
    try:
        stats = _stats(db)
    except Exception as e:
        logger.warning(f"list_companies stats query failed: {e}")
        stats = {
            "total_companies": 0,
            "with_disclosures": 0,
            "sbti_validated": 0,
            "fully_disclosed": 0,
        }
    return {
        "companies": rows,
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "stats": stats,
    }


@router.get("/standards")
async def list_standards_index():
    """Public listing of the 5 reporting standards. Must be declared
    BEFORE the /{ticker} catch-all or FastAPI treats "standards" as a
    ticker value. The duplicate definition near the bottom of this
    file is kept for backwards-import-safety but never matched."""
    from app.domains.content.corporate.standards import STANDARDS
    return {
        "standards": [
            {
                "id": s["id"],
                "name": s["name"],
                "jurisdiction": s["jurisdiction"],
                "effective_from": s["effective_from"],
                "scope": s["scope"],
                "mandatory_disclosure": s["mandatory_disclosure"],
                "evidence_url": s["evidence_url"],
            }
            for s in STANDARDS
        ],
        "total": len(STANDARDS),
    }


@router.get("/compare")
async def compare_companies(
    a: str = Query(..., description="Company A — ticker or company_id"),
    b: str = Query(..., description="Company B — ticker or company_id"),
    user: dict = Depends(get_optional_user),
):
    """Head-to-head climate comparison of two companies (seq-13) — serves the
    "compare two companies' sustainability" scenario.

    Leaders are declared ONLY for size-independent AMBITION metrics (SBTi
    validation, net-zero target year, % reduction target, scope-1/2 assurance).
    Raw scope emissions are returned without a leader because absolute tonnage
    scales with company size, so "lower" doesn't mean "greener". Declared before
    the /{ticker} route so "compare" isn't read as a ticker.

    Requires Basic+ tier — gated by QuotaService (1 compare/month on Free tier).
    """
    user_tier = "freemium"
    user_id = None
    if user and isinstance(user, dict):
        user_tier = user.get("subscription_tier", "freemium") or "freemium"
        user_id = user.get("user_id")

    QuotaService.check_and_raise(
        user_id=str(user_id) if user_id else None,
        tier=user_tier,
        quota_key="compare",
    )

    db = get_postgres()
    from app.domains.content.corporate.repository import (
        get_company,
        get_company_disclosures,
    )

    def _metrics(ident: str):
        prof = get_company(db, ident)
        if not prof:
            return None
        discs = get_company_disclosures(db, prof.company_id)  # reporting_year DESC

        def latest(field):
            for d in discs:
                if d.get(field) is not None:
                    return d.get(field)
            return None

        return {
            "company_id": prof.company_id,
            "name": prof.name,
            "ticker": prof.ticker,
            "country_code": prof.country_code,
            "sector_nace": prof.sector_nace,
            "disclosure_count": prof.disclosure_count,
            "sbti_validated": prof.sbti_validated,
            "net_zero_target_year": prof.net_zero_target_year or latest("net_zero_target_year"),
            "target_pct_reduction": latest("target_pct_reduction"),
            "target_year": latest("target_year"),
            "scope1_2_verified": any(bool(d.get("scope1_2_verified")) for d in discs),
            "scope1_tco2e": latest("scope1_tco2e"),
            "scope2_tco2e_market": latest("scope2_tco2e_market"),
            "scope3_tco2e": latest("scope3_tco2e"),
        }

    ca = _metrics(a)
    cb = _metrics(b)
    if ca is None or cb is None:
        missing = a if ca is None else b
        raise HTTPException(status_code=404, detail=f"Company not found: {missing!r}")

    def _leader(va, vb, better: str):
        # better: 'truth' (True beats False) | 'lower' (smaller wins, e.g. an
        # earlier net-zero year) | 'higher' (bigger wins, e.g. % reduction).
        if va is None and vb is None:
            return None
        if va is None:
            return "b"
        if vb is None:
            return "a"
        if better == "truth":
            if bool(va) == bool(vb):
                return "tie"
            return "a" if va else "b"
        if va == vb:
            return "tie"
        if better == "higher":
            return "a" if va > vb else "b"
        return "a" if va < vb else "b"  # 'lower'

    comparison = {
        "sbti_validated": {"a": ca["sbti_validated"], "b": cb["sbti_validated"],
                           "leader": _leader(ca["sbti_validated"], cb["sbti_validated"], "truth")},
        "net_zero_target_year": {"a": ca["net_zero_target_year"], "b": cb["net_zero_target_year"],
                                 "leader": _leader(ca["net_zero_target_year"], cb["net_zero_target_year"], "lower")},
        "target_pct_reduction": {"a": ca["target_pct_reduction"], "b": cb["target_pct_reduction"],
                                 "leader": _leader(ca["target_pct_reduction"], cb["target_pct_reduction"], "higher")},
        "scope1_2_verified": {"a": ca["scope1_2_verified"], "b": cb["scope1_2_verified"],
                              "leader": _leader(ca["scope1_2_verified"], cb["scope1_2_verified"], "truth")},
    }
    a_wins = sum(1 for d in comparison.values() if d["leader"] == "a")
    b_wins = sum(1 for d in comparison.values() if d["leader"] == "b")
    ambition_leader = "a" if a_wins > b_wins else "b" if b_wins > a_wins else "tie"

    return {
        "company_a": ca,
        "company_b": cb,
        "comparison": comparison,
        "emissions": {
            "note": "Absolute tCO2e, not size-adjusted — no leader is declared "
                    "(absolute emissions scale with company size).",
            "scope1_tco2e": {"a": ca["scope1_tco2e"], "b": cb["scope1_tco2e"]},
            "scope2_tco2e_market": {"a": ca["scope2_tco2e_market"], "b": cb["scope2_tco2e_market"]},
            "scope3_tco2e": {"a": ca["scope3_tco2e"], "b": cb["scope3_tco2e"]},
        },
        "ambition_leader": ambition_leader,
        "ambition_dimensions_won": {"a": a_wins, "b": b_wins},
    }


@router.get("/{ticker}")
async def get_company(ticker: str, user: dict = Depends(get_optional_user)):
    from app.domains.content.corporate.repository import (
        get_company,
        get_company_claims,
        get_company_disclosures,
    )
    from app.domains.content.corporate.standards import (
        assess_disclosure_against_standards,
    )

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
    disclosures = get_company_disclosures(db, profile.company_id)
    claims = get_company_claims(db, profile.company_id)
    # Stage 5 (M6) — per-standard compliance assessment across the 5
    # globally-recognized frameworks (CSRD, SBTi, TCFD, IFRS S2, GRI).
    # Heuristic-based for the MVP; the full machine-readable mapping is
    # in app/domains/content/corporate/standards.py.
    standards = assess_disclosure_against_standards(disclosures)
    return {
        "company": {
            "company_id": profile.company_id,
            "name": profile.name,
            "ticker": profile.ticker,
            "country_code": profile.country_code,
            "sector_nace": profile.sector_nace,
            "disclosure_count": profile.disclosure_count,
            "latest_disclosure_year": profile.latest_disclosure_year,
            "sbti_validated": profile.sbti_validated,
            "net_zero_target_year": profile.net_zero_target_year,
        },
        "disclosures": disclosures,
        "claims": claims,
        "standards_compliance": standards,
    }


@router.get("/{ticker}/claims")
async def get_claims(ticker: str, user: dict = Depends(get_optional_user)):
    from app.domains.content.corporate.repository import get_company, get_company_claims

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
    claims = get_company_claims(db, profile.company_id)
    return {"company_id": profile.company_id, "claims": claims, "total": len(claims)}


@router.post("/{ticker}/analyze", response_model=AnalyzeClaimResponse)
async def analyze_company_claim(
    ticker: str,
    request: AnalyzeClaimRequest,
    user: dict = Depends(get_optional_user),
):
    from app.domains.content.corporate.repository import (
        get_company,
        get_company_disclosures,
        upsert_company_claim,
    )
    from app.domains.content.corporate.schemas import CompanyClaim

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")

    disclosures = get_company_disclosures(db, profile.company_id)
    disclosure_context = _format_disclosure_context(profile, disclosures)

    claim_type, verdict, flag_reason, evidence = _analyze_claim(
        request.claim_text, disclosure_context
    )

    result = CompanyClaim(
        company_id=profile.company_id,
        claim_text=request.claim_text,
        claim_type=claim_type,
        verdict=verdict,
        flag_reason=flag_reason,
        evidence_url=evidence,
        methodology_version="corporate_v1.0",
    )
    claim_id = upsert_company_claim(db, result)

    return AnalyzeClaimResponse(
        claim_id=claim_id,
        claim_text=request.claim_text,
        claim_type=claim_type,
        verdict=verdict,
        evidence=evidence,
        flag_reason=flag_reason,
        methodology_version="corporate_v1.0",
    )


@router.post("/{ticker}/analyze-report", response_model=AnalyzeReportResponse)
async def analyze_company_report(
    ticker: str,
    request: AnalyzeReportRequest,
    current_user: dict = Depends(get_current_user),
):
    """End-to-end analysis of a corporate sustainability report.

    Pipeline:
      1. Resolve company (404 if unknown ticker/UUID).
      2. Acquire report text — either from `report_url` (via
         Slice 4b fetch_full_text) or directly from `report_text`.
      3. Run ClaimExtractor with content_type='research_report' to
         pull up to max_claims atomic claims.
      4. For each claim, run _analyze_claim against the company's
         disclosure context — same heuristic as POST /analyze.
      5. Persist every result via upsert_company_claim and return
         the structured response with verdict counts.

    Exactly one of report_url or report_text must be provided.
    Closes audit item 12 (corporate sustainability report analysis).

    End2End audit gap (2026-05-27 §6.5): this endpoint was ungated — a
    free-tier user could run a 100-page sustainability report through
    DeepSeek extraction + claim verification at no cost. Now requires
    Standard+ ("document_ingestion" premium feature) to match exports
    and weather_context tier policy.
    """
    from app.domains.content.corporate.repository import (
        get_company,
        get_company_disclosures,
        upsert_company_claim,
    )
    from app.domains.content.corporate.schemas import CompanyClaim

    if not check_premium_feature(current_user, "document_ingestion"):
        tier = current_user.get("subscription_tier", "freemium")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "premium_feature_required",
                "feature": "document_ingestion",
                "current_tier": tier,
                "required_tier": "standard",
                "upgrade_url": "/dashboard/subscription",
                "message": (
                    "Corporate sustainability report analysis requires a "
                    "Standard subscription or higher. Upgrade to unlock "
                    "/api/companies/{ticker}/analyze-report."
                ),
            },
        )

    # Phase 1A quota gate — analyze-report counts against the monthly
    # compare allowance (same gated surface family).
    user_tier = current_user.get("subscription_tier", "freemium") or "freemium"
    user_id = current_user.get("user_id")
    QuotaService.check_and_raise(
        user_id=str(user_id) if user_id else None,
        tier=user_tier,
        quota_key="compare",
    )

    if (request.report_url is None) == (request.report_text is None):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of report_url or report_text must be provided",
        )

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")

    # 2. Acquire text.
    if request.report_text:
        text = request.report_text
        report_url = None
    else:
        from shared.full_text_fetch import fetch_full_text
        text = await fetch_full_text(request.report_url, timeout=20.0)
        report_url = request.report_url
        if not text:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Could not fetch usable text from {request.report_url}. "
                    "Check the URL serves HTML (not a paywalled PDF), is reachable, "
                    "and contains more than 200 chars of body text. As a fallback, "
                    "paste the report body into the report_text field directly."
                ),
            )

    # 3. Claim extraction (DeepSeek with research-report tuning).
    try:
        from app.domains.intelligence.services import ClaimExtractor
        extractor = ClaimExtractor()
        atomic_claims = await extractor.decompose_claims(
            text=text,
            max_claims=request.max_claims,
            content_type="research_report",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"analyze-report: ClaimExtractor failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Claim extraction failed: {type(exc).__name__}",
        )

    # 4 + 5. Per-claim verdicts + persist.
    disclosures = get_company_disclosures(db, profile.company_id)
    disclosure_context = _format_disclosure_context(profile, disclosures)

    results: List[AnalyzedReportClaim] = []
    verdict_counts: Dict[str, int] = {}
    for atomic in atomic_claims:
        claim_text = getattr(atomic, "text", None) or getattr(atomic, "claim", str(atomic))
        if not isinstance(claim_text, str) or len(claim_text.strip()) < 10:
            continue
        claim_type, verdict, flag_reason, evidence = _analyze_claim(
            claim_text, disclosure_context
        )
        record = CompanyClaim(
            company_id=profile.company_id,
            claim_text=claim_text,
            claim_type=claim_type,
            verdict=verdict,
            flag_reason=flag_reason,
            evidence_url=evidence,
            methodology_version="corporate_report_v1.0",
        )
        claim_id = upsert_company_claim(db, record)
        results.append(
            AnalyzedReportClaim(
                claim_id=claim_id,
                claim_text=claim_text,
                claim_type=claim_type,
                verdict=verdict,
                flag_reason=flag_reason,
                evidence=evidence,
            )
        )
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    logger.info(
        f"analyze-report: {profile.name} ({ticker}) — "
        f"{len(results)} claims analysed from {len(text)}-char text"
    )

    return AnalyzeReportResponse(
        company_id=profile.company_id,
        report_url=report_url,
        text_length=len(text),
        extracted_claims_count=len(results),
        claims=results,
        verdict_summary=verdict_counts,
    )


def _format_disclosure_context(profile, disclosures: List[dict]) -> str:
    parts = [f"COMPANY: {profile.name}"]
    if profile.country_code:
        parts.append(f"Country: {profile.country_code}")
    parts.append(f"SBTi validated: {'Yes' if profile.sbti_validated else 'No'}")
    if profile.net_zero_target_year:
        parts.append(f"Net-zero target: {profile.net_zero_target_year}")
    for d in disclosures[:3]:
        parts.append(
            f"[{d.get('source')}/{d.get('reporting_year')}] "
            f"S1:{d.get('scope1_tco2e')} S2m:{d.get('scope2_tco2e_market')} "
            f"S3:{d.get('scope3_tco2e')} verified:{d.get('scope1_2_verified')} "
            f"assurance:{d.get('assurance_level')}"
        )
    return "\n".join(parts)


def _analyze_claim(claim_text: str, context: str) -> tuple:
    text_lower = claim_text.lower()

    net_zero_markers = ("net zero", "net-zero", "carbon neutral", "climate neutral")
    offset_markers = ("carbon offset", "offsetting", "offset credits", "carbon credit")
    reduction_markers = ("reduce", "reduction", "cut emissions", "emissions down")

    if any(m in text_lower for m in offset_markers):
        return (
            "offset_claim", "flagged",
            "ECGT prohibits offset-based 'climate neutral' product claims without independent verification",
            None,
        )

    if any(m in text_lower for m in net_zero_markers):
        # Fail-safe verification (2026-05-24): only POSITIVE SBTi confirmation
        # in context → "verified". Anything else (absent context, explicit
        # "No", or context without SBTi mention) → "disputed". Default-trust
        # is wrong for a fact-checking surface — boards rely on conservative
        # defaults.
        is_validated = "sbti validated: yes" in context.lower()
        return (
            "net_zero_target",
            "verified" if is_validated else "disputed",
            None if is_validated else "Net-zero claim not SBTi-validated",
            None if is_validated
            else "https://sciencebasedtargets.org/companies-taking-action",
        )

    if any(m in text_lower for m in reduction_markers):
        return (
            "emissions_reduction", "partially_true",
            "Verify against disclosed Scope 1/2/3 data above",
            None,
        )

    if "100%" in text_lower and "renewable" in text_lower:
        return (
            "renewable_energy", "partially_true",
            "100% renewable claims should be backed by REC or PPA documentation",
            None,
        )

    return ("other", "unverified", None, None)


# ---------------------------------------------------------------------------
# Phase 8 (2026-05-24) — Adapter sync endpoint.
#
# Triggers one of the three corporate-data adapters (SBTi / CDP / Net Zero
# Tracker). Token-gated via `CORPORATE_SYNC_TOKEN` env var. If the env var is
# unset the endpoint returns 503 — explicit opt-in so a fresh deploy doesn't
# expose an unprotected ingestion trigger.
# ---------------------------------------------------------------------------


_VALID_SOURCES = {"sbti", "cdp", "net_zero_tracker"}

# Phase 8 (2026-05-24, refactor) — in-memory last-run tracker. Single Cloud
# Run instance so this is fine for now; if we scale to >1 instance we'll
# move this to Postgres. Operators GET /api/companies/admin/sync/{source}
# to see the last run's outcome.
_LAST_SYNC_RUN: Dict[str, Dict[str, Any]] = {}


def _run_adapter_sync_blocking(source: str) -> None:
    """Run one adapter sync to completion, recording the outcome.

    Called from FastAPI BackgroundTasks as a regular `def` so it runs on
    a thread-pool worker — never blocks the main event loop. Uses its
    own asyncio event loop because the underlying adapter calls are
    async (httpx fetch) while the DB calls are sync (psycopg2).
    """
    import asyncio

    db = get_postgres()
    started = datetime.utcnow().isoformat() + "Z"
    _LAST_SYNC_RUN[source] = {
        "source": source, "status": "running",
        "started_at": started, "finished_at": None,
        "upserted": 0, "errors": [], "warning": None,
    }
    try:
        if source == "sbti":
            from app.domains.content.corporate.sbti_adapter import SBTIAdapter
            result = asyncio.run(SBTIAdapter().sync(db))
        elif source == "cdp":
            from app.domains.content.corporate.cdp_adapter import CDPAdapter
            result = asyncio.run(CDPAdapter().sync(db))
        else:  # net_zero_tracker
            from app.domains.content.corporate.nzt_adapter import NetZeroTrackerAdapter
            result = asyncio.run(NetZeroTrackerAdapter().sync(db))
        _LAST_SYNC_RUN[source].update(
            status="completed",
            finished_at=datetime.utcnow().isoformat() + "Z",
            upserted=int(result.get("upserted", 0)),
            errors=list(result.get("errors", []))[:50],
            warning=result.get("warning"),
        )
        logger.info(
            f"Adapter sync complete: {source} upserted={result.get('upserted', 0)} "
            f"errors={len(result.get('errors', []))}"
        )
    except Exception as exc:
        _LAST_SYNC_RUN[source].update(
            status="failed",
            finished_at=datetime.utcnow().isoformat() + "Z",
            errors=[str(exc)[:500]],
        )
        logger.error(f"Adapter sync {source} failed: {exc}")


@router.post("/admin/sync/{source}")
async def trigger_adapter_sync(
    source: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(
        default=False,
        description="Run synchronously (CPU stays allocated for the whole "
        "request). Cloud Run throttles CPU to ~0 AFTER the 202 response, which "
        "makes the background path crawl on the 38k-row SBTi sync (~a day); "
        "wait=true completes it in minutes, bounded by the 1800s request timeout.",
    ),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Trigger an adapter sync. Default returns 202 (background); wait=true runs
    it to completion in a worker thread and returns the outcome. Status also
    checkable via GET /admin/sync/{source}."""
    # Accept CORPORATE_SYNC_TOKEN (ops curl) OR SCHEDULER_SECRET (Cloud
    # Scheduler cron) — same dual gate as the admin backfill endpoints, so the
    # monthly SBTi cron can drive this without the corporate token.
    corp = os.environ.get("CORPORATE_SYNC_TOKEN")
    sched = os.environ.get("SCHEDULER_SECRET")
    if not corp and not sched:
        raise HTTPException(
            status_code=503,
            detail="Adapter sync disabled — set CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET",
        )
    authed = (corp and x_corporate_sync_token == corp) or (sched and x_scheduler_secret == sched)
    if not authed:
        raise HTTPException(status_code=401, detail="Invalid sync token")
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source {source!r}. Expected one of: {sorted(_VALID_SOURCES)}",
        )
    # Reject re-trigger while one is in flight
    current = _LAST_SYNC_RUN.get(source, {})
    if current.get("status") == "running":
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "source": source,
                "started_at": current.get("started_at"),
            },
        )
    if wait:
        # Run to completion in a worker thread while the REQUEST stays open, so
        # Cloud Run keeps CPU allocated. asyncio.to_thread keeps the event loop
        # free for other requests on this instance (the sync's DB calls are
        # blocking psycopg2). _run_adapter_sync_blocking records _LAST_SYNC_RUN.
        import asyncio
        await asyncio.to_thread(_run_adapter_sync_blocking, source)
        return JSONResponse(status_code=200, content=_LAST_SYNC_RUN.get(source, {
            "status": "unknown", "source": source,
        }))
    background_tasks.add_task(_run_adapter_sync_blocking, source)
    return JSONResponse(
        status_code=202,
        content={
            "status": "scheduled",
            "source": source,
            "message": (
                "Sync running in background. "
                f"GET /api/companies/admin/sync/{source} to check status."
            ),
        },
    )


@router.get("/admin/sync/{source}")
async def get_adapter_sync_status(source: str):
    """Last-run outcome for an adapter sync. Public — surfaces only
    aggregate counts + status, never row-level data."""
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source {source!r}. Expected one of: {sorted(_VALID_SOURCES)}",
        )
    return _LAST_SYNC_RUN.get(source) or {
        "source": source, "status": "never_run",
        "started_at": None, "finished_at": None,
        "upserted": 0, "errors": [], "warning": None,
    }


# ---------------------------------------------------------------------------
# Stage 5 (M6) — company suggestions + standards index
# ---------------------------------------------------------------------------

class CompanySuggestionRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    ticker: Optional[str] = Field(None, max_length=20)
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    website: Optional[str] = Field(None, max_length=500)
    report_url: Optional[str] = Field(
        None,
        max_length=500,
        description=(
            "Optional URL to a corporate sustainability report (e.g. "
            "https://www.fazer.com/.../fazer-annual-report-2025.pdf). When "
            "matched, the analyst can run /companies/{id}/analyze-report on it."
        ),
    )
    reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Why this company should be analyzed (e.g. claims to verify)",
    )


@router.post("/suggestions")
async def suggest_company(
    payload: CompanySuggestionRequest,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Suggest a new company for analysis (Stage 5 / M6).

    Advanced-user endpoint — anyone authenticated can submit. The
    submission goes into the company_suggestions queue (mig 051) for
    analyst review. If a matching company already exists in
    `companies`, the response includes its company_id so the user
    can navigate straight there.
    """
    db = get_postgres()
    reporter_id = (current_user or {}).get("user_id")

    # Cheap dedup: did we already see this name?
    existing = db.execute_query(
        """SELECT suggestion_id::text AS sid, status, matched_company_id::text AS mcid
           FROM company_suggestions
           WHERE lower(company_name) = lower(:n)
           ORDER BY created_at DESC
           LIMIT 1""",
        {"n": payload.company_name.strip()},
    )

    # And: is there already a matching row in `companies`?
    matched = db.execute_query(
        """SELECT company_id::text AS cid, name
           FROM companies
           WHERE lower(name) = lower(:n)
              OR (ticker IS NOT NULL AND :t IS NOT NULL AND lower(ticker) = lower(:t))
           LIMIT 1""",
        {"n": payload.company_name.strip(), "t": payload.ticker or None},
    )
    matched_cid = matched[0]["cid"] if matched else None

    suggestion_id = str(uuid4())
    db.execute_update(
        """INSERT INTO company_suggestions (
               suggestion_id, company_name, ticker, country_code, website,
               report_url, reason, reporter_id, matched_company_id, status
           ) VALUES (
               :sid, :name, :ticker, :cc, :web, :rurl, :reason, :rep, :mcid,
               CASE WHEN :mcid IS NOT NULL THEN 'matched' ELSE 'queued' END
           )""",
        {
            "sid": suggestion_id,
            "name": payload.company_name.strip(),
            "ticker": payload.ticker,
            "cc": payload.country_code,
            "web": payload.website,
            "rurl": payload.report_url,
            "reason": payload.reason,
            "rep": reporter_id,
            "mcid": matched_cid,
        },
    )
    return {
        "suggestion_id": suggestion_id,
        "status": "matched" if matched_cid else "queued",
        "matched_company_id": matched_cid,
        "matched_company_name": matched[0]["name"] if matched else None,
        "duplicate_of": existing[0]["sid"] if existing else None,
        "note": (
            "Company already in tracker — navigate to /companies/{matched_company_id}"
            if matched_cid
            else "Queued for analyst review. Status: queued."
        ),
    }


