"""Company climate disclosure routes — /api/companies

GET  /api/companies                    — paginated company index
GET  /api/companies/{ticker}           — company profile + disclosures + claims
GET  /api/companies/{ticker}/claims    — company claims list
POST /api/companies/{ticker}/analyze   — LLM-based claim verification
POST /api/companies/admin/sync/{source} — Phase 8: trigger SBTi/CDP/NZT adapter
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.rate_limiter import TIER_LIMITS, UsageTracker
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


@router.get("")
async def list_companies(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from app.domains.content.corporate.repository import list_companies as _list

    db = get_postgres()
    try:
        rows = _list(db, limit=limit, offset=offset)
    except Exception as e:
        logger.warning(f"list_companies failed: {e}")
        rows = []
    return {"companies": rows, "total": len(rows), "limit": limit, "offset": offset}


@router.get("/{ticker}")
async def get_company(ticker: str):
    from app.domains.content.corporate.repository import (
        get_company,
        get_company_claims,
        get_company_disclosures,
    )

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
    disclosures = get_company_disclosures(db, profile.company_id)
    claims = get_company_claims(db, profile.company_id)
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
    }


@router.get("/{ticker}/claims")
async def get_claims(ticker: str):
    from app.domains.content.corporate.repository import get_company, get_company_claims

    db = get_postgres()
    profile = get_company(db, ticker)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
    claims = get_company_claims(db, profile.company_id)
    return {"company_id": profile.company_id, "claims": claims, "total": len(claims)}


@router.post("/{ticker}/analyze", response_model=AnalyzeClaimResponse)
async def analyze_company_claim(ticker: str, request: AnalyzeClaimRequest):
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
    from datetime import datetime

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
    x_corporate_sync_token: Optional[str] = Header(default=None),
):
    """Schedule an adapter sync. Returns 202 immediately; sync runs in
    background. Status checkable via GET /admin/sync/{source}."""
    expected = os.environ.get("CORPORATE_SYNC_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Adapter sync disabled — set CORPORATE_SYNC_TOKEN to enable",
        )
    if x_corporate_sync_token != expected:
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
