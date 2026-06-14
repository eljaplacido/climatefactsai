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

import json
import os
import subprocess
from datetime import datetime, timezone
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
# Source credibility tiers (Phase 8 — migration 027)
# =============================================================================

@router.get("/source-tiers")
async def list_source_tiers() -> Dict[str, Any]:
    """All source credibility tiers with evidence URLs.

    Replaces the legacy 8-publisher hardcoded whitelist with a DB-backed
    tier system seeded from Scimago JR, RetractionWatch, IFCN, and
    correction-policy assessment.
    """
    from app.domains.trust.source_tier_service import list_all_source_tiers

    db = get_postgres()
    try:
        tiers = list_all_source_tiers(db)
    except Exception:
        tiers = []

    return {
        "source_tiers": tiers,
        "total": len(tiers),
        "tier_schema": {
            "T1": "Scimago Q1 journal or IFCN-verified fact-checker (+30 prior bonus)",
            "T2": "Mainstream press with published corrections policy or Q2 journal (+15)",
            "T3": "Research NGO or intergovernmental body with sourcing (+5)",
            "unknown": "No tier data available (0 bonus)",
            "retracted": "Known retractions — credibility penalty applied (-30)",
        },
        "methodology_url": "https://climatefacts.ai/methodology#source-tiers",
    }


@router.get("/source-tiers/by-domain")
async def get_source_tier_by_domain(domain: str) -> Dict[str, Any]:
    """Profile for a specific domain."""
    from app.domains.trust.source_tier_service import get_source_tier_profile

    db = get_postgres()
    profile = get_source_tier_profile(db, domain)
    if profile is None:
        return {"domain": domain, "available": False}
    return {"domain": domain, "available": True, "profile": profile}


# =============================================================================
# Credibility-scale crosswalk (Data-Layer audit 2026-06-10, item 11)
# =============================================================================
# The platform uses several distinct credibility ladders (article reliability
# 0-100, source-tier letters, 3-axis source scores, the URL-analysis score).
# The audit flagged that nothing documented how they relate, so a "76" on one
# scale and a "T2" on another were not reconcilable by an auditor. This
# endpoint enumerates every scale and the single crosswalk that maps a 0-100
# score to HIGH/MEDIUM/LOW. Constants are imported from the canonical modules
# (not hardcoded) so the documentation can never drift from the live math.

@router.get("/credibility-scales")
async def get_credibility_scales() -> Dict[str, Any]:
    """Document every credibility scale and how they map to one another.

    Static (no DB). Every numeric here is imported from the module that owns
    it, so this endpoint stays in lockstep with the live scoring code.
    """
    from shared.credibility_thresholds import HIGH, MEDIUM
    from shared.reliability_scorer import ReliabilityScorer as RS

    # Tier base scores are owned by source_tier_service; import defensively so
    # a refactor of that private map degrades to "see /source-tiers" rather
    # than 500-ing this doc endpoint.
    try:
        from app.domains.trust.source_tier_service import _TIER_BASE_SCORE
        tier_base_scores = dict(_TIER_BASE_SCORE)
    except Exception:
        tier_base_scores = None

    canonical_levels = {
        "HIGH": f">= {HIGH}",
        "MEDIUM": f"{MEDIUM}–{HIGH - 1}",
        "LOW": f"< {MEDIUM}",
        "owner": "shared.credibility_thresholds (level_for / level_for_unit)",
        "note": (
            "Every 0-100 score in the platform maps to a level through this "
            "single function, so one score yields exactly one label everywhere."
        ),
    }

    scales = [
        {
            "id": "article_reliability_score",
            "range": "0–100",
            "levels": canonical_levels,
            "owner": "shared.reliability_scorer.ReliabilityScorer",
            "formula": {
                "source_credibility_weight": RS.WEIGHT_SOURCE_CREDIBILITY,
                "verified_claims_weight": RS.WEIGHT_VERIFIED_CLAIMS,
                "content_relevance_weight": RS.WEIGHT_CONTENT_RELEVANCE,
                "claims_for_full_credit": RS.CLAIMS_FOR_FULL_CREDIT,
                "limited_evidence_threshold": RS.LIMITED_EVIDENCE_THRESHOLD,
            },
            "notes": (
                "Composite article score. Zero verified claims forfeit the "
                "claims weight (can't exceed MEDIUM); < "
                f"{RS.LIMITED_EVIDENCE_THRESHOLD} claims are capped at MEDIUM "
                "and flagged 'Limited evidence'."
            ),
        },
        {
            "id": "source_credibility_tier",
            "range": "T1 | T2 | T3 | unknown | retracted",
            "owner": "source_credibility_tiers table + source_tier_service",
            "tier_base_score_0_100": tier_base_scores,
            "prior_bonus": {
                "T1": "+30", "T2": "+15", "T3": "+5",
                "unknown": "0", "retracted": "-30",
            },
            "maps_to": (
                "Feeds the source-credibility component (50% of "
                "article_reliability_score) via the tier base score."
            ),
            "detail_endpoint": "/api/methodology/source-tiers",
        },
        {
            "id": "source_3axis_scores",
            "range": "editorial / factcheck / transparency, each 0–100",
            "owner": "source_credibility_tiers (migration 041/045)",
            "blend": {
                "legacy_single_score_weight": RS.SOURCE_LEGACY_WEIGHT,
                "axes_mean_weight": RS.SOURCE_AXES_WEIGHT,
            },
            "maps_to": (
                "When all three axes are present they blend "
                f"{RS.SOURCE_LEGACY_WEIGHT:.0%}/{RS.SOURCE_AXES_WEIGHT:.0%} with "
                "the legacy single source score inside the source component."
            ),
        },
        {
            "id": "url_analysis_reliability",
            "range": "0–100",
            "levels": canonical_levels,
            "owner": "app.services.url_analyzer",
            "notes": (
                "Verdict-weighted score for ad-hoc URL analysis (verified=1.0, "
                "partially_true=0.6, unverified=0.3, disputed/false=0.0). Routes "
                "its level through shared.credibility_thresholds.level_for, so it "
                "agrees with article_reliability_score at the same number."
            ),
        },
        {
            "id": "calibrated_confidence",
            "range": "0.0–1.0",
            "owner": "app.domains.intelligence.calibration (Platt scaling)",
            "maps_to": (
                "Optional post-hoc recalibration of a raw confidence; only "
                "applied when a stable fit exists (see /api/methodology/"
                "calibration fit_status). Mapped to a level via level_for_unit."
            ),
        },
    ]

    return {
        "overview": (
            "Reconciliation of every credibility/reliability scale the "
            "platform uses. All 0-100 scales share one HIGH/MEDIUM/LOW "
            "crosswalk; source tiers and 3-axis scores feed the article "
            "composite rather than being separate user-facing verdicts."
        ),
        "canonical_levels": canonical_levels,
        "scales": scales,
        "methodology_url": "https://climatefacts.ai/methodology#credibility-scales",
    }


# =============================================================================
# Editorial / topical inclusion gate (Data-Layer audit 2026-06-10, Wave 1)
# =============================================================================
# The platform ingests from general-news feeds that leak off-topic stories. A
# conservative keyword gate (classify_climate_relevance) decides what is
# in-scope, and a separate EditorialGate decides publish/hold/escalate. The
# audit flagged that the inclusion RULE was wired but undocumented, so a reader
# couldn't see why an item was kept or dropped. This endpoint documents both
# gates, reading the term lists straight from the module (anti-drift).

@router.get("/editorial-gate")
async def get_editorial_gate() -> Dict[str, Any]:
    """Document the topical inclusion gate + the publish/hold/escalate gate.

    Static (no DB). The strong/weak term lists are imported from
    editorial_gate so this never drifts from the live gate.
    """
    from app.domains.intelligence.editorial_gate import (
        _CLIMATE_TERMS_STRONG,
        _CLIMATE_TERMS_WEAK,
    )

    return {
        "topical_relevance_gate": {
            "function": "app.domains.intelligence.editorial_gate.classify_climate_relevance",
            "policy": (
                "Conservative inclusion gate: an item is in-scope if it shows "
                "ANY climate / sustainability / energy-transition signal. Only "
                "items with ZERO signal are dropped — false-negatives "
                "(dropping real climate coverage) are treated as far worse than "
                "false-positives, so the gate errs toward inclusion."
            ),
            "scoring_rule": {
                "any_strong_term": "in-scope; score = min(1.0, 0.6 + 0.1 × #strong terms)",
                "two_or_more_weak_terms": "in-scope (climate-adjacent); score = 0.5",
                "one_weak_term": "in-scope but flagged for review; score = 0.35",
                "no_terms": "REJECTED; score = 0.0",
            },
            "strong_terms": sorted(_CLIMATE_TERMS_STRONG),
            "weak_terms": sorted(_CLIMATE_TERMS_WEAK),
            "matched_terms_returned": (
                "The gate returns the matched terms in its reason string so "
                "every inclusion/exclusion decision is reviewer-traceable."
            ),
        },
        "editorial_decision_gate": {
            "class": "app.domains.intelligence.editorial_gate.EditorialGate",
            "decisions": {
                "PUBLISH": "reliability_score ≥ 60, no majority-disputed claims, < 3 risk factors",
                "HOLD": "reliability_score 30–59, or significant disputed claims, or low verification confidence",
                "ESCALATE": "reliability_score < 30, or majority of claims disputed, or ≥ 3 risk factors",
            },
            "note": (
                "The inclusion gate runs at ingest; the editorial decision gate "
                "runs after verification using the reliability_score documented "
                "at /api/methodology/credibility-scales."
            ),
        },
        "methodology_url": "https://climatefacts.ai/methodology#editorial-gate",
    }


# =============================================================================
# Audit-trail endpoints (Phase 4 wave 3)
# =============================================================================
# Surface per-extraction provenance to users and external auditors.
# Each row records which model + prompt fingerprint + retrieval strategy
# produced a given analytical output — pairs with the methodology snapshot
# above to answer "this score was produced under this exact pipeline".

def _hydrate_source_articles(db, source_article_ids) -> list:
    """Join UUID array to article titles, URLs, and source names.

    Returns a list of {article_id, title, url, source_name, published_at}
    for every valid UUID in `source_article_ids`. Invalid UUIDs or missing
    articles silently contribute nothing — the provenance row itself is not
    invalidated by stale article references.
    """
    if not source_article_ids:
        return []
    ids = source_article_ids
    if isinstance(ids, str):
        try:
            ids = json.loads(ids)
        except Exception:
            return []
    if not isinstance(ids, list) or len(ids) == 0:
        return []
    try:
        rows = db.execute_query(
            """
            SELECT article_id, title, url, source_name, published_date
            FROM articles
            WHERE article_id = ANY(:ids::uuid[])
              AND is_synthetic = FALSE
            """,
            {"ids": [str(i) for i in ids if i]},
        )
    except Exception:
        return []
    return [
        {
            "article_id": str(r["article_id"]),
            "title": r.get("title"),
            "url": r.get("url"),
            "source_name": r.get("source_name"),
            "published_at": str(r.get("published_date")) if r.get("published_date") else None,
        }
        for r in (rows or [])
    ]

@router.get("/audit-trail/url-analysis/{analysis_id}")
async def audit_trail_for_url_analysis(analysis_id: str) -> Dict[str, Any]:
    """All provenance rows for one URL analysis run, newest first."""
    from app.domains.intelligence.provenance import get_provenance_for_url_analysis

    db = get_postgres()
    records = get_provenance_for_url_analysis(db, analysis_id)
    for r in records:
        r["source_articles"] = _hydrate_source_articles(db, r.get("source_article_ids"))
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
    for r in records:
        r["source_articles"] = _hydrate_source_articles(db, r.get("source_article_ids"))
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
    for r in records:
        r["source_articles"] = _hydrate_source_articles(db, r.get("source_article_ids"))
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
    from app.domains.intelligence.calibration import (
        calibrate,
        classify_fit_status,
        accuracy_margin_of_error,
    )
    from app.domains.intelligence.calibration_store import (
        SUPPORTED_SIGNALS,
        PREVIEW_FIT_MIN,
        STABLE_FIT_MIN,
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
            "fit_status": "unsupported",
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
                # fit_status/margin are always present so the methodology
                # drawer can render an honest "awaiting labels" state without
                # special-casing the empty branch (audit Wave 1).
                "fit_status": "no_labels",
                "margin_of_error": None,
                "note": (
                    "No calibration labels recorded yet for this signal; "
                    "awaiting reviewer input via POST /api/methodology/calibration/labels."
                ),
            },
        }

    result = calibrate(predictions, labels, n_bins=max(1, min(int(n_bins), 50)))
    metrics = result.as_dict()
    # Surface fit honesty: how many labels back the fit, and the uncertainty.
    # fit_status thresholds come from calibration_store (single source of truth);
    # below STABLE_FIT_MIN the Platt fit is a preview and is NOT applied at
    # inference (see calibration_store.apply_latest_to_reliability).
    metrics["fit_status"] = classify_fit_status(
        result.n, PREVIEW_FIT_MIN, STABLE_FIT_MIN
    )
    metrics["margin_of_error"] = accuracy_margin_of_error(labels)
    metrics["observed_accuracy"] = round(sum(labels) / len(labels), 4)
    metrics["stable_fit_min"] = STABLE_FIT_MIN
    return {
        "signal": signal,
        "available": True,
        "metrics": metrics,
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
    min_labels: int = 50,
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
) -> Dict[str, Any]:
    """Recompute Brier + ECE + Platt parameters and persist into
    `calibration_fits`. The application picks up the new fit on the
    next GET — no restart required.

    Returns `status='insufficient_data'` when fewer than `min_labels`
    rows exist for the signal. Default raised from 5 → 50 on 2026-05-26
    per End2End-Audit + TruthMachine strategy report: 5-label fits are
    unstable Platt sigmoids; 50+ is the minimum for production-grade.
    Callers wanting preview fits can pass min_labels=5 explicitly.
    """
    _verify_admin_secret(x_admin_secret)

    from app.domains.intelligence.calibration_store import refit_and_persist

    db = get_postgres()
    result = refit_and_persist(db, signal_name=signal, min_labels=int(min_labels))
    return result.as_dict()


# =============================================================================
# Chi-squared bias audit (Section III of TruthMachine strategy report)
# =============================================================================
# Tests whether claim_type is statistically independent of verdict over the
# recent claim corpus. A significant association (p < 0.05) flags that the
# source mix is shifting verdicts in a way that warrants editorial review.
# Pure-numpy implementation in app.domains.intelligence.bias_auditor.

@router.get("/bias-audit")
async def get_bias_audit() -> Dict[str, Any]:
    """Public read-only chi-squared bias auditor.

    Builds a contingency table of (claim_type × verdict) over the last
    180 days of claims and runs a chi-squared test of independence at
    alpha=0.05. Reports chi², degrees of freedom, the critical value,
    Cramér's V effect size, and a plain-language interpretation.

    Reject_independence=true means the source/topic mix is producing
    correlated verdicts in a statistically meaningful way — editorial
    review recommended. Reject_independence=false is the desired state
    (verdicts depend on claim content, not claim category).
    """
    from app.domains.intelligence.bias_auditor import audit_claim_type_verdict_bias

    db = get_postgres()
    return audit_claim_type_verdict_bias(db)


# =============================================================================
# Live self-audit composite score (seq-5b, 2026-06-14)
# =============================================================================
# Replaces the hardcoded 3.55 on the methodology page with a backend-driven
# composite that draws from live data. Each axis is scored 1-5 based on the
# latest available evidence, then averaged into a composite.
#
# Honesty: axes that cannot be measured return a clear "insufficient_data"
# status rather than a guessed number.

@router.get("/self-audit")
async def get_self_audit_score() -> Dict[str, Any]:
    """Live composite methodology self-audit, driven from backend data.

    Every axis reads its score from the same live sources the platform uses.
    No hardcoded numbers — if calibration has 0 labels, the reliability axis
    reflects that. The composite is unweighted mean; weights TBD once label
    volume is stable.
    """
    from app.domains.intelligence.calibration_store import (
        STABLE_FIT_MIN,
        fetch_labelled_predictions,
    )

    db = get_postgres()
    axes: List[Dict[str, Any]] = []
    axis_scores: List[float] = []

    # --- Calibration axis ---
    try:
        preds, labels = fetch_labelled_predictions(db, "reliability_score")
        n = len(preds)
        if n >= STABLE_FIT_MIN:
            cal_score = 4.0  # floor — stable fit exists
            cal_detail = f"{n} labels (≥{STABLE_FIT_MIN}), stable fit"
            cal_status = "measured"
        elif n >= 5:
            cal_score = 2.5  # preview fit only
            cal_detail = f"{n} labels (≥5 preview, <{STABLE_FIT_MIN} stable)"
            cal_status = "preview"
        else:
            cal_score = 1.0
            cal_detail = f"{n} labels — awaiting {STABLE_FIT_MIN} for stable fit"
            cal_status = "insufficient_data"
    except Exception:
        cal_score = 1.0
        cal_detail = "calibration_labels table unavailable"
        cal_status = "unavailable"

    axes.append({
        "axis": "calibration",
        "score": cal_score,
        "status": cal_status,
        "detail": cal_detail,
    })
    axis_scores.append(cal_score)

    # --- Source credibility axis ---
    try:
        rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM source_credibility_tiers WHERE tier IS NOT NULL"
        )
        tiered = int(rows[0]["cnt"]) if rows else 0
        if tiered >= 50:
            src_score = 4.0
            src_detail = f"{tiered} sources tiered"
            src_status = "measured"
        elif tiered >= 10:
            src_score = 2.5
            src_detail = f"{tiered} sources tiered (partial)"
            src_status = "partial"
        else:
            src_score = 1.0
            src_detail = "source_credibility_tiers empty"
            src_status = "insufficient_data"
    except Exception:
        src_score = 1.0
        src_detail = "source_credibility_tiers unavailable"
        src_status = "unavailable"

    axes.append({
        "axis": "source_credibility",
        "score": src_score,
        "status": src_status,
        "detail": src_detail,
    })
    axis_scores.append(src_score)

    # --- Embeddings axis ---
    try:
        rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM articles WHERE embedding_bge_m3 IS NOT NULL"
        )
        emb = int(rows[0]["cnt"]) if rows else 0
        if emb >= 100:
            emb_score = 4.0
            emb_detail = f"{emb} articles with embeddings"
            emb_status = "measured"
        elif emb >= 1:
            emb_score = 2.0
            emb_detail = f"{emb} articles (below 100 floor)"
            emb_status = "partial"
        else:
            emb_score = 1.0
            emb_detail = "0 articles with embeddings"
            emb_status = "insufficient_data"
    except Exception:
        emb_score = 1.0
        emb_detail = "embedding_bge_m3 column unavailable"
        emb_status = "unavailable"

    axes.append({
        "axis": "embeddings",
        "score": emb_score,
        "status": emb_status,
        "detail": emb_detail,
    })
    axis_scores.append(emb_score)

    # --- Coverage axis ---
    try:
        rows = db.execute_query(
            "SELECT COUNT(DISTINCT country_code) as cnt FROM articles"
        )
        countries = int(rows[0]["cnt"]) if rows else 0
        pct = round(countries / 193 * 100, 1)
        if pct >= 50:
            cov_score = 4.0
        elif pct >= 20:
            cov_score = 2.5
        else:
            cov_score = 1.5
        cov_detail = f"{countries}/193 countries ({pct}%)"
        cov_status = "measured"
    except Exception:
        cov_score = 1.0
        cov_detail = "articles table unavailable"
        cov_status = "unavailable"

    axes.append({
        "axis": "country_coverage",
        "score": cov_score,
        "status": cov_status,
        "detail": cov_detail,
    })
    axis_scores.append(cov_score)

    # --- Provenance axis ---
    try:
        rows = db.execute_query(
            "SELECT COUNT(*) as cnt FROM claim_provenance"
        )
        prov = int(rows[0]["cnt"]) if rows else 0
        if prov >= 500:
            prov_score = 4.0
        elif prov >= 50:
            prov_score = 2.5
        else:
            prov_score = 1.5
        prov_detail = f"{prov} provenance rows"
        prov_status = "measured"
    except Exception:
        prov_score = 1.0
        prov_detail = "claim_provenance unavailable"
        prov_status = "unavailable"

    axes.append({
        "axis": "provenance",
        "score": prov_score,
        "status": prov_status,
        "detail": prov_detail,
    })
    axis_scores.append(prov_score)

    composite = round(sum(axis_scores) / len(axis_scores), 2) if axis_scores else 0.0

    return {
        "composite": composite,
        "max": 5.0,
        "axes": axes,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Live score driven by backend data. Axes with "
            "'insufficient_data' or 'unavailable' status floor at 1.0. "
            "The composite is an unweighted mean; weights will be added "
            "once label volume is stable."
        ),
    }


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


@router.get("/reproduce/{provenance_id}")
async def reproduce_analysis(provenance_id: int) -> Dict[str, Any]:
    """Replay an analysis with the pinned prompt version + retrieval strategy.

    Returns the original score, the replayed score, and a diff. This is the
    strongest possible demonstration that the platform is reproducible.
    """
    from app.domains.intelligence.reproducer import reproduce_url_analysis

    db = get_postgres()
    result = reproduce_url_analysis(db, provenance_id)
    return result.__dict__ if hasattr(result, "__dict__") else {"status": "error"}


@router.get("/drift-thresholds")
async def get_drift_thresholds() -> Dict[str, Any]:
    """Current learned drift thresholds, or hardcoded defaults."""
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT * FROM drift_threshold_fits
               WHERE metric = 'source_mix'
               ORDER BY fitted_at DESC LIMIT 1""",
            {},
        )
        if rows:
            r = rows[0]
            return {
                "available": True,
                "mu": r.get("mu"),
                "sigma": r.get("sigma"),
                "thresholds": {
                    "2σ": r.get("threshold_2sigma"),
                    "3σ": r.get("threshold_3sigma"),
                    "4σ": r.get("threshold_4sigma"),
                },
                "n_samples": r.get("n_samples"),
                "fitted_at": str(r.get("fitted_at")),
            }
    except Exception:
        pass
    return {
        "available": False,
        "hardcoded_fallback": True,
        "thresholds": {"stable": 0.10, "minor": 0.25, "notable": 0.50},
        "note": "Learned thresholds will be available after 60 days of production data.",
    }
