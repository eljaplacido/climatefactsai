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

from fastapi import APIRouter

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

    db = get_postgres()
    if signal not in {"reliability_score"}:
        # `agreement_score` and `hallucination_score` live in
        # claim_provenance.raw_metadata; supporting those requires a JSON
        # path query. Phase 5 wave 5 (future) adds them. For now restrict
        # to the column we can read directly.
        return {
            "signal": signal,
            "available": False,
            "reason": f"signal '{signal}' not yet supported; try 'reliability_score'",
            "metrics": None,
        }

    try:
        rows = db.execute_query(
            """
            SELECT
                cl.label_truth,
                ua.reliability_score
            FROM calibration_labels cl
            JOIN url_analyses ua ON cl.url_analysis_id = ua.analysis_id
            WHERE ua.reliability_score IS NOT NULL
            """,
            {},
        )
    except Exception as exc:
        logger.warning(f"calibration query failed: {exc}")
        return {
            "signal": signal,
            "available": False,
            "reason": f"calibration_labels query failed: {type(exc).__name__}",
            "metrics": None,
        }

    if not rows:
        return {
            "signal": signal,
            "available": True,
            "metrics": {
                "n_labels": 0,
                "note": "No calibration labels recorded yet; awaiting human review.",
            },
        }

    # Normalise the raw signal to [0, 1] for the calibration math.
    # reliability_score is stored as 0–100; divide.
    predictions: List[float] = []
    labels: List[float] = []
    for r in rows:
        rs = r.get("reliability_score")
        lt = r.get("label_truth")
        if rs is None or lt is None:
            continue
        try:
            predictions.append(float(rs) / 100.0)
            labels.append(float(lt))
        except (TypeError, ValueError):
            continue

    result = calibrate(predictions, labels, n_bins=max(1, min(int(n_bins), 50)))
    return {
        "signal": signal,
        "available": True,
        "metrics": result.as_dict(),
    }
