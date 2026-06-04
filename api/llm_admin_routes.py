"""Admin routes for LLM routing health — Phase 10 (2026-05-25).

GET /api/admin/llm/routing    — effective workload→provider table
GET /api/admin/llm/breakers   — live circuit-breaker snapshot
GET /api/admin/llm/fallbacks  — recent fallback events (last 100)

Token-gated via CORPORATE_SYNC_TOKEN (same gate as adapter sync — same
operator audience). When the env var is unset all endpoints return 503.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.domains.intelligence.llm_routing import breaker_status, routing_table
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("llm-admin-routes")
router = APIRouter(prefix="/api/admin/llm", tags=["Admin / LLM"])


def _auth(token: Optional[str]) -> None:
    expected = os.environ.get("CORPORATE_SYNC_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="LLM admin endpoints disabled — set CORPORATE_SYNC_TOKEN to enable",
        )
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/routing")
async def get_routing(
    x_corporate_sync_token: Optional[str] = Header(default=None),
):
    """Effective provider routing for every workload, after env-var
    overrides. Operators use this to confirm a deploy moved the
    expected workloads to local-gx10."""
    _auth(x_corporate_sync_token)
    return {"routing": routing_table()}


@router.get("/breakers")
async def get_breakers(
    x_corporate_sync_token: Optional[str] = Header(default=None),
):
    """Circuit-breaker snapshot per provider. `open: true` means new
    calls to that provider are short-circuited to the fallback."""
    _auth(x_corporate_sync_token)
    return {"breakers": breaker_status()}


@router.get("/fallbacks")
async def get_fallbacks(
    x_corporate_sync_token: Optional[str] = Header(default=None),
    workload: Optional[str] = None,
    limit: int = 100,
):
    """Last N fallback events from `local_llm_fallbacks` table.

    Filter by workload to see (e.g.) how often enrichment falls back
    from local-gx10 to deepseek during a rollout.
    """
    _auth(x_corporate_sync_token)
    limit = max(1, min(limit, 500))
    db = get_postgres()
    where = ""
    params: dict = {"lim": limit}
    if workload:
        where = "WHERE workload = :wl"
        params["wl"] = workload
    try:
        rows = db.execute_query(
            f"""SELECT id, workload, primary_provider, fallback_provider,
                       error_class, error_message, latency_ms, created_at
                FROM local_llm_fallbacks
                {where}
                ORDER BY created_at DESC
                LIMIT :lim""",
            params,
        )
    except Exception as exc:
        logger.warning(f"local_llm_fallbacks query failed: {exc}")
        rows = []
    return {
        "fallbacks": [
            {
                "id": str(r["id"]),
                "workload": r["workload"],
                "primary_provider": r["primary_provider"],
                "fallback_provider": r["fallback_provider"],
                "error_class": r.get("error_class"),
                "error_message": r.get("error_message"),
                "latency_ms": r.get("latency_ms"),
                "created_at": str(r["created_at"]) if r.get("created_at") else None,
            }
            for r in (rows or [])
        ],
        "total": len(rows or []),
    }


@router.get("/cost")
async def get_cost(
    x_corporate_sync_token: Optional[str] = Header(default=None),
    window_hours: int = 24,
):
    """LLM spend telemetry (seq-8). Aggregates llm_cost_log by provider over the
    window, showing the cloud-vs-GX10(free) split + estimated USD. Makes the
    enrichment/embeddings→GX10 savings visible and surfaces a deep-search
    Anthropic runaway before it shows up on a bill."""
    _auth(x_corporate_sync_token)
    window_hours = max(1, min(window_hours, 24 * 90))
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT provider,
                      COUNT(*)               AS calls,
                      SUM(prompt_tokens)     AS prompt_tokens,
                      SUM(completion_tokens) AS completion_tokens,
                      SUM(est_cost_usd)      AS est_cost_usd
                 FROM llm_cost_log
                WHERE created_at >= NOW() - (:hrs || ' hours')::interval
                GROUP BY provider
                ORDER BY est_cost_usd DESC NULLS LAST""",
            {"hrs": window_hours},
        )
    except Exception as exc:
        logger.warning(f"llm_cost_log query failed (table may be unmigrated): {exc}")
        return {"window_hours": window_hours, "by_provider": [], "total_usd": 0.0,
                "note": "no cost data yet (llm_cost_log empty or unmigrated)"}

    by_provider = [
        {
            "provider": r["provider"],
            "calls": int(r.get("calls") or 0),
            "prompt_tokens": int(r.get("prompt_tokens") or 0),
            "completion_tokens": int(r.get("completion_tokens") or 0),
            "est_cost_usd": round(float(r.get("est_cost_usd") or 0), 4),
        }
        for r in (rows or [])
    ]
    total_usd = round(sum(p["est_cost_usd"] for p in by_provider), 4)
    paid = round(sum(p["est_cost_usd"] for p in by_provider if p["provider"] != "local-gx10"), 4)
    free_calls = sum(p["calls"] for p in by_provider if p["provider"] == "local-gx10")
    total_calls = sum(p["calls"] for p in by_provider)
    return {
        "window_hours": window_hours,
        "by_provider": by_provider,
        "total_usd": total_usd,
        "paid_usd": paid,
        "free_gx10_calls": free_calls,
        "total_calls": total_calls,
        "gx10_offload_pct": round(100.0 * free_calls / total_calls, 1) if total_calls else 0.0,
    }
