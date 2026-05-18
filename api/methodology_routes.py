"""Methodology endpoints — Phase 4 wave 2.

Public, read-only API surface that lets users (and auditors) inspect every
prompt, formula component, and indicator the platform uses. The
methodology drawer in the frontend deep-links here; the audit-trail UI in
wave 3 uses these to render per-claim provenance.

Endpoints:
  * GET /api/methodology/prompts
        — list every PromptTemplate with version + fingerprint + description.
  * GET /api/methodology/sustainability-formula
        — full disclosure of the sustainability_score formula (weights,
          normalizations, confidence bands, methodology_version).
  * GET /api/methodology/indicators
        — every indicator the platform defines (joined indicator_definitions),
          with unit + category + methodology_url + direction.
  * GET /api/methodology
        — bundled snapshot — prompts + formula + indicators + git revision
          if available. Convenient single-call view for the methodology
          drawer and external auditors.

All endpoints are public + cacheable; nothing here exposes user data or
secrets.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional  # noqa: F401

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

import sys
from pathlib import Path

SRC_BACKEND = Path(__file__).resolve().parents[1] / "src" / "backend"
if str(SRC_BACKEND) not in sys.path:
    sys.path.insert(0, str(SRC_BACKEND))

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("methodology-api")
router = APIRouter(prefix="/api/methodology", tags=["Methodology"])


# ---------------------------------------------------------------------------
# Admin secret for write endpoints (Phase 5 wave 5)
# ---------------------------------------------------------------------------
# Matches the pattern used by scheduler_routes.py: when the env var is
# unset (dev), endpoints are open; in production set
# `CLILENS_CALIBRATION_ADMIN_SECRET` and pass it via the
# `X-Admin-Secret` header on every write.
#
# We read the env var on each call (not at module load) so test fixtures
# that monkeypatch it stay correctly scoped — no `importlib.reload`
# gymnastics required.

def _verify_admin_secret(secret: Optional[str]) -> None:
    configured = os.getenv("CLILENS_CALIBRATION_ADMIN_SECRET", "")
    if configured and secret != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin secret",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_revision() -> Optional[str]:
    """Best-effort short SHA of the current HEAD, or None if git is unavailable.

    Surfaced in /api/methodology so a methodology snapshot can be pinned to a
    specific code state. Falls back to the GIT_COMMIT_SHA env var (CI sets
    this) when the .git directory isn't present in the container.
    """
    env = os.getenv("GIT_COMMIT_SHA")
    if env:
        return env[:12]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        return out.decode("ascii", errors="ignore").strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# /api/methodology/prompts
# ---------------------------------------------------------------------------

@router.get("/prompts")
async def list_methodology_prompts() -> Dict[str, Any]:
    """Every versioned prompt the platform uses for LLM calls.

    The `fingerprint` is a content hash; two prompts with the same
    fingerprint are byte-identical. Use this to detect drift between a
    deployed version and what you see in source.
    """
    from app.domains.intelligence.prompts import list_prompts, PROMPTS

    items = list_prompts()
    detailed = {
        name: {
            **items[name],
            "rationale": PROMPTS[name].rationale,
            # Hide the actual template content from this public surface —
            # it's enough that the fingerprint + version are pinned. We can
            # add a privileged endpoint that exposes templates if/when we
            # add an admin-only methodology console.
            "has_system_prompt": bool(PROMPTS[name].system),
            "max_tokens": PROMPTS[name].max_tokens,
            "temperature": PROMPTS[name].temperature,
        }
        for name in items
    }
    return {
        "prompts": detailed,
        "total": len(detailed),
    }


# ---------------------------------------------------------------------------
# /api/methodology/sustainability-formula
# ---------------------------------------------------------------------------

@router.get("/sustainability-formula")
async def get_sustainability_formula() -> Dict[str, Any]:
    """Full disclosure of the sustainability_score formula.

    Components + weights + normalization summaries + confidence-band table
    + methodology_version + URL. The UI's methodology drawer uses this to
    explain "why is this country's score 73?" without users having to read
    the source code.
    """
    from app.domains.intelligence.sustainability_score import (
        COMPONENTS,
        METHODOLOGY_URL,
        METHODOLOGY_VERSION,
        confidence_band_for,
    )

    components = [
        {
            "indicator_id": c.indicator_id,
            "weight": c.weight,
            "description": c.description,
            "normalizer": c.normalizer.__name__,
            "normalizer_doc": (c.normalizer.__doc__ or "").strip().split("\n")[0],
        }
        for c in COMPONENTS
    ]
    confidence_table = [
        {"indicators_used": n, "band_plus_minus": confidence_band_for(n)}
        for n in range(0, 6)
    ]
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "methodology_url": METHODOLOGY_URL,
        "components": components,
        "confidence_band_table": confidence_table,
        "scoring_summary": (
            "weighted_sum(normalized_score_i * weight_i) over indicators "
            "that have data for the country; weights of missing components "
            "redistribute proportionally across the available subset; "
            "result clamped to [0, 100]; confidence band sized by the "
            "number of indicators that contributed."
        ),
        "weight_total": sum(c.weight for c in COMPONENTS),
    }


# ---------------------------------------------------------------------------
# /api/methodology/indicators
# ---------------------------------------------------------------------------

@router.get("/indicators")
async def list_indicators() -> Dict[str, Any]:
    """Every indicator the platform defines + its source registry.

    Reads from `indicator_definitions` (the catalogue created by migration
    020). If the migration hasn't been applied, returns an empty list with
    `available=False` so callers can degrade gracefully.
    """
    db = get_postgres()
    indicators: List[Dict[str, Any]] = []
    available = True

    try:
        rows = db.execute_query(
            """
            SELECT indicator_id, display_name, unit, category, description,
                   is_higher_better, methodology_url, created_at
            FROM indicator_definitions
            ORDER BY category, indicator_id
            """,
            {},
        )
    except Exception as exc:
        logger.warning(f"indicator_definitions query failed: {exc}")
        available = False
        rows = []

    for r in rows or []:
        indicators.append({
            "indicator_id": r.get("indicator_id"),
            "display_name": r.get("display_name"),
            "unit": r.get("unit"),
            "category": r.get("category"),
            "description": r.get("description"),
            "is_higher_better": bool(r.get("is_higher_better", True)),
            "methodology_url": r.get("methodology_url"),
        })

    # Count distinct (country, indicator) coverage, best-effort.
    coverage_summary: Dict[str, int] = {}
    try:
        cov_rows = db.execute_query(
            """
            SELECT indicator_id, COUNT(DISTINCT country_code) AS countries
            FROM country_indicators
            GROUP BY indicator_id
            """,
            {},
        )
        for r in cov_rows or []:
            coverage_summary[r["indicator_id"]] = int(r.get("countries") or 0)
    except Exception:
        coverage_summary = {}

    return {
        "indicators": indicators,
        "available": available,
        "total_indicators": len(indicators),
        "coverage_by_indicator": coverage_summary,
    }


# ---------------------------------------------------------------------------
# /api/methodology (bundled snapshot)
# ---------------------------------------------------------------------------

@router.get("")
@router.get("/")
async def methodology_snapshot() -> Dict[str, Any]:
    """Single-call methodology snapshot — prompts + formula + indicators + git.

    Convenient for the methodology drawer (one request, full state) and for
    external auditors who want to pin a date+commit-aligned methodology
    snapshot.
    """
    prompts_block = await list_methodology_prompts()
    formula_block = await get_sustainability_formula()
    indicators_block = await list_indicators()

    return {
        "git_revision": _git_revision(),
        "prompts": prompts_block,
        "sustainability_formula": formula_block,
        "indicators": indicators_block,
    }


# =============================================================================
# Audit-trail endpoints (Phase 4 wave 3)
# =============================================================================
# Surface per-extraction provenance to users and external auditors.
# Each row records which model + prompt fingerprint + retrieval strategy
# produced a given analytical output — pairs with the methodology snapshot
# above to answer "this score was produced under this exact pipeline".

@router.get("/audit-trail/url-analysis/{analysis_id}")
async def audit_trail_for_url_analysis(analysis_id: str) -> Dict[str, Any]:
    """All provenance rows for one URL analysis run, newest first."""
    from app.domains.intelligence.provenance import get_provenance_for_url_analysis

    db = get_postgres()
    records = get_provenance_for_url_analysis(db, analysis_id)
    return {
        "url_analysis_id": analysis_id,
        "records": records,
        "total": len(records),
    }


@router.get("/audit-trail/article/{article_id}")
async def audit_trail_for_article(article_id: str) -> Dict[str, Any]:
    """All provenance rows for one article, newest first.

    Includes ingestion-time enrichment, deep-search syntheses anchored to
    this article (via source_article_ids), and any URL-analysis mirrors.
    """
    from app.domains.intelligence.provenance import get_provenance_for_article

    db = get_postgres()
    records = get_provenance_for_article(db, article_id)
    return {
        "article_id": article_id,
        "records": records,
        "total": len(records),
    }


@router.get("/audit-trail/claim/{claim_id}")
async def audit_trail_for_claim(claim_id: str) -> Dict[str, Any]:
    """All provenance rows for one canonical claim, newest first."""
    from app.domains.intelligence.provenance import get_provenance_for_claim

    db = get_postgres()
    records = get_provenance_for_claim(db, claim_id)
    return {
        "claim_id": claim_id,
        "records": records,
        "total": len(records),
    }


# =============================================================================
# Calibration metrics (Phase 5 wave 4)
# =============================================================================
# Pairs the reliability_score the URL analysis pipeline records with the
# ground-truth labels from `calibration_labels` (migration 022), computes
# Brier + ECE + reliability diagram + (when n >= 5) Platt scaling
# parameters. The application can apply the fitted Platt at inference to
# expose a calibrated_confidence alongside the raw value.

@router.get("/calibration")
async def methodology_calibration(
    signal: str = "reliability_score",
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Compute live calibration metrics for one signal.

    Joins `calibration_labels.label_truth` against the URL analysis's
    recorded value for the requested signal (default reliability_score)
    and runs the calibration math.

    Returns 200 with `available=false` + zeros when no labels exist or
    the migration hasn't been applied — degrades gracefully so the
    methodology drawer can render an "awaiting first labels" state.
    """
    from app.domains.intelligence.calibration import calibrate
    from app.domains.intelligence.calibration_store import (
        SUPPORTED_SIGNALS,
        fetch_labelled_predictions,
    )

    if signal not in SUPPORTED_SIGNALS:
        return {
            "signal": signal,
            "available": False,
            "reason": (
                f"signal '{signal}' not supported. "
                f"Available: {sorted(SUPPORTED_SIGNALS)}"
            ),
            "metrics": None,
        }

    db = get_postgres()
    predictions, labels = fetch_labelled_predictions(db, signal)

    if not predictions:
        return {
            "signal": signal,
            "available": True,
            "metrics": {
                "n_labels": 0,
                "note": (
                    "No calibration labels recorded yet for this signal; "
                    "awaiting reviewer input via POST /api/methodology/calibration/labels."
                ),
            },
        }

    result = calibrate(predictions, labels, n_bins=max(1, min(int(n_bins), 50)))
    return {
        "signal": signal,
        "available": True,
        "metrics": result.as_dict(),
    }


# =============================================================================
# Calibration data → fit → apply (Phase 5 wave 5)
# =============================================================================

class CalibrationLabelRequest(BaseModel):
    """One ground-truth label submitted by a reviewer."""
    url_analysis_id: str = Field(..., min_length=1, max_length=64)
    label_truth: float = Field(..., ge=0.0, le=1.0,
        description="Ground-truth verdict: 0.0 = wrong, 1.0 = correct, "
                    "intermediate = graded.")
    labeled_by: str = Field(..., min_length=1, max_length=128,
        description="Reviewer identifier — name, email, or external review-ID.")
    label_method: str = Field(default="human_review", max_length=64,
        description="One of: human_review | external_factcheck | "
                    "consensus_panel | reviewer_team_lead | auto_baseline")
    label_notes: Optional[str] = Field(default=None, max_length=8192)
    confidence_at_label: Optional[float] = Field(default=None, ge=0.0, le=1.0,
        description="Reviewer's own confidence in their label, optional.")


@router.post("/calibration/labels", status_code=status.HTTP_201_CREATED)
async def submit_calibration_label(
    request: CalibrationLabelRequest,
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
) -> Dict[str, Any]:
    """Record one ground-truth label for an analysis.

    The label feeds future calibration refit runs. Idempotent on the
    natural key (analysis_id, labeled_by, label_method); duplicate
    submissions return 409 with status='duplicate'.
    """
    _verify_admin_secret(x_admin_secret)

    from app.domains.intelligence.calibration_store import record_calibration_label

    db = get_postgres()
    result = record_calibration_label(
        db,
        url_analysis_id=request.url_analysis_id,
        label_truth=request.label_truth,
        labeled_by=request.labeled_by,
        label_method=request.label_method,
        label_notes=request.label_notes,
        confidence_at_label=request.confidence_at_label,
    )

    if result.status == "duplicate":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already labelled by this reviewer + method",
        )
    if result.status == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record label: {result.error}",
        )

    return result.as_dict()


@router.post("/calibration/refit")
async def refit_calibration(
    signal: str = "reliability_score",
    min_labels: int = 5,
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
) -> Dict[str, Any]:
    """Recompute Brier + ECE + Platt parameters and persist into
    `calibration_fits`. The application picks up the new fit on the
    next GET — no restart required.

    Returns `status='insufficient_data'` when fewer than `min_labels`
    rows exist for the signal (default 5). The fit is skipped, no row
    written.
    """
    _verify_admin_secret(x_admin_secret)

    from app.domains.intelligence.calibration_store import refit_and_persist

    db = get_postgres()
    result = refit_and_persist(db, signal_name=signal, min_labels=int(min_labels))
    return result.as_dict()


# =============================================================================
# Hallucination-rate dashboard (Phase 6 wave 6)
# =============================================================================
# Aggregates `claim_provenance.hallucination_score` across the recent window
# by extraction_method, model_name, and (via JSONB unnest + article join)
# source_name. Powers the per-source hallucination dashboard called out as a
# Robustness lift in the truth-machine roadmap. Each grouping is computed
# independently so a single failing CTE doesn't black-hole the others.

def _row_stats(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    """Normalise SQL aggregate rows for the wire format.

    Each row is expected to have: <key>, n, mean_risk, high_risk_rate.
    """
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        n = int(r.get("n") or 0)
        if n == 0:
            continue
        mean = float(r.get("mean_risk") or 0.0)
        high = float(r.get("high_risk_rate") or 0.0)
        out.append({
            key: r.get(key) or "unknown",
            "n": n,
            "mean_risk": round(mean, 4),
            "high_risk_rate": round(high, 4),
        })
    return out


@router.get("/hallucination-rates")
async def get_hallucination_rates(
    window_days: int = 30,
    top_sources: int = 50,
) -> Dict[str, Any]:
    """Per-source / per-model hallucination-rate snapshot.

    Aggregates `claim_provenance.hallucination_score` over the trailing
    `window_days` window into three groupings:

      * overall              — single rolled-up stat across all extractions
      * by_extraction_method — url_analysis_claim_extraction, deep_search_synthesis, etc.
      * by_model             — deepseek-chat, claude-sonnet-4-5, gpt-4o, …
      * by_source            — joins through claim_provenance.article_id AND
                                source_article_ids[] → articles.source_name

    Each grouping reports:
      * n              — number of extractions in scope
      * mean_risk      — average hallucination_score (0–1, lower is better)
      * high_risk_rate — fraction with hallucination_score > 0.5

    `top_sources` caps the by_source list (sorted by n desc) so the
    response stays bounded even on large corpora.

    Returns `available=False` if claim_provenance is missing (migration
    not applied) or contains no scored rows in the window. Individual
    sub-queries degrade independently — a failing source join still
    returns method+model groupings.
    """
    window_days = max(1, min(int(window_days), 365))
    top_sources = max(1, min(int(top_sources), 500))
    interval = f"{window_days} days"

    db = get_postgres()
    available = True
    overall: Dict[str, Any] = {"n": 0, "mean_risk": 0.0, "high_risk_rate": 0.0}
    by_method: List[Dict[str, Any]] = []
    by_model: List[Dict[str, Any]] = []
    by_source: List[Dict[str, Any]] = []
    notes: List[str] = []

    # --- Overall ----------------------------------------------------------
    try:
        rows = db.execute_query(
            """
            SELECT
                COUNT(*)                                                  AS n,
                AVG(hallucination_score)                                  AS mean_risk,
                AVG(CASE WHEN hallucination_score > 0.5 THEN 1.0 ELSE 0.0 END)
                                                                          AS high_risk_rate
            FROM claim_provenance
            WHERE hallucination_score IS NOT NULL
              AND created_at > NOW() - :interval::interval
            """,
            {"interval": interval},
        )
        if rows:
            r0 = rows[0]
            n = int(r0.get("n") or 0)
            if n > 0:
                overall = {
                    "n": n,
                    "mean_risk": round(float(r0.get("mean_risk") or 0.0), 4),
                    "high_risk_rate": round(float(r0.get("high_risk_rate") or 0.0), 4),
                }
    except Exception as exc:
        logger.warning(f"hallucination_rates overall query failed: {exc}")
        available = False
        notes.append("claim_provenance unavailable (migration 021 not applied?)")

    # --- By extraction_method ---------------------------------------------
    if available:
        try:
            rows = db.execute_query(
                """
                SELECT
                    COALESCE(extraction_method, 'unknown') AS extraction_method,
                    COUNT(*)                               AS n,
                    AVG(hallucination_score)               AS mean_risk,
                    AVG(CASE WHEN hallucination_score > 0.5 THEN 1.0 ELSE 0.0 END)
                                                           AS high_risk_rate
                FROM claim_provenance
                WHERE hallucination_score IS NOT NULL
                  AND created_at > NOW() - :interval::interval
                GROUP BY extraction_method
                ORDER BY COUNT(*) DESC
                """,
                {"interval": interval},
            )
            by_method = _row_stats(rows, "extraction_method")
        except Exception as exc:
            logger.warning(f"hallucination_rates by_method query failed: {exc}")
            notes.append("by_extraction_method aggregation skipped")

    # --- By model_name ----------------------------------------------------
    if available:
        try:
            rows = db.execute_query(
                """
                SELECT
                    COALESCE(model_name, 'unknown') AS model_name,
                    COUNT(*)                         AS n,
                    AVG(hallucination_score)         AS mean_risk,
                    AVG(CASE WHEN hallucination_score > 0.5 THEN 1.0 ELSE 0.0 END)
                                                     AS high_risk_rate
                FROM claim_provenance
                WHERE hallucination_score IS NOT NULL
                  AND created_at > NOW() - :interval::interval
                GROUP BY model_name
                ORDER BY COUNT(*) DESC
                """,
                {"interval": interval},
            )
            by_model = _row_stats(rows, "model_name")
        except Exception as exc:
            logger.warning(f"hallucination_rates by_model query failed: {exc}")
            notes.append("by_model aggregation skipped")

    # --- By source (article_id + source_article_ids JSONB unnest) ---------
    # Sources can attach via either:
    #   * Direct article_id (article_ingestion_enrichment path)
    #   * source_article_ids[] JSONB array (deep_search + url_analysis paths)
    # Use UNION ALL to combine both, LEFT JOIN articles so a deleted source
    # article shows as 'unknown' instead of dropping the row.
    if available:
        try:
            rows = db.execute_query(
                """
                WITH per_link AS (
                    SELECT cp.id AS cp_id, cp.hallucination_score, cp.article_id AS art_id
                    FROM claim_provenance cp
                    WHERE cp.hallucination_score IS NOT NULL
                      AND cp.created_at > NOW() - :interval::interval
                      AND cp.article_id IS NOT NULL
                    UNION ALL
                    SELECT cp.id AS cp_id, cp.hallucination_score,
                           NULLIF(src_id, '')::uuid AS art_id
                    FROM claim_provenance cp
                    CROSS JOIN LATERAL
                        jsonb_array_elements_text(cp.source_article_ids) AS src_id
                    WHERE cp.hallucination_score IS NOT NULL
                      AND cp.created_at > NOW() - :interval::interval
                      AND cp.source_article_ids IS NOT NULL
                      AND jsonb_typeof(cp.source_article_ids) = 'array'
                )
                SELECT
                    COALESCE(a.source_name, 'unknown') AS source_name,
                    COUNT(*)                            AS n,
                    AVG(per_link.hallucination_score)   AS mean_risk,
                    AVG(CASE WHEN per_link.hallucination_score > 0.5
                             THEN 1.0 ELSE 0.0 END)     AS high_risk_rate
                FROM per_link
                LEFT JOIN articles a ON a.article_id = per_link.art_id
                GROUP BY a.source_name
                ORDER BY COUNT(*) DESC
                LIMIT :limit
                """,
                {"interval": interval, "limit": top_sources},
            )
            by_source = _row_stats(rows, "source_name")
        except Exception as exc:
            logger.warning(f"hallucination_rates by_source query failed: {exc}")
            notes.append("by_source aggregation skipped (UUID cast or join failure)")

    return {
        "window_days": window_days,
        "available": available,
        "overall": overall,
        "by_extraction_method": by_method,
        "by_model": by_model,
        "by_source": by_source,
        "notes": notes or None,
    }
