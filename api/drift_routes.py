"""Drift-detection endpoints — Phase 6 waves 1 + 5.

Public-but-cacheable endpoints that surface drift signals an operator
or external auditor would want to inspect:

  * `/api/drift/source-mix`           — wave 1 (article source distribution)
  * `/api/drift/prompt-fingerprints`  — wave 5 (LLM prompt usage distribution)

Future waves add latency drift and per-LLM hallucination-rate drift.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query

SRC_BACKEND = Path(__file__).resolve().parents[1] / "src" / "backend"
if str(SRC_BACKEND) not in sys.path:
    sys.path.insert(0, str(SRC_BACKEND))

from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("drift-api")
router = APIRouter(prefix="/api/drift", tags=["Drift Detection"])


@router.get("/source-mix")
async def get_source_mix_drift(
    recent_days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=365),
) -> Dict[str, Any]:
    """KL-divergence drift on the per-source article share.

    Compares the last `recent_days` to the prior `baseline_days` (the two
    windows do not overlap). Returns a `DriftReport` with the KL value,
    a verdict bucket (`stable` / `minor` / `notable` / `significant`),
    and the top-10 source share-shifts that drove the divergence.

    Typical usage: the ops dashboard polls this hourly and pages when
    verdict transitions to `significant`. The `top_shifts` list explains
    which source(s) drove the spike.
    """
    from app.domains.intelligence.drift_detection import detect_source_mix_drift

    db = get_postgres()
    report = detect_source_mix_drift(
        db,
        recent_days=recent_days,
        baseline_days=baseline_days,
    )
    return report.as_dict()


@router.get("/prompt-fingerprints")
async def get_prompt_fingerprint_drift(
    recent_days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=365),
) -> Dict[str, Any]:
    """KL-divergence drift on the per-prompt-fingerprint claim share.

    Identifies silent prompt edits (template changed without a version
    bump → fingerprint shifts), phase-out of an old prompt version,
    or adoption of a new one. Each `top_shifts` row carries an extra
    `display` field with the resolved `name@version` label.

    Verdict thresholds match `/api/drift/source-mix`:
      * KL < 0.10  — stable
      * 0.10 ≤ KL < 0.25 — minor
      * 0.25 ≤ KL < 0.50 — notable
      * KL ≥ 0.50 — significant (page on-call)
    """
    from app.domains.intelligence.drift_detection import (
        detect_prompt_fingerprint_drift,
    )

    db = get_postgres()
    report = detect_prompt_fingerprint_drift(
        db,
        recent_days=recent_days,
        baseline_days=baseline_days,
    )
    return report.as_dict()
