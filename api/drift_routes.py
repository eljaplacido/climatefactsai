"""Drift-detection endpoints — Phase 6 wave 1.

Public-but-cacheable endpoints that surface drift signals an operator
or external auditor would want to inspect. Today: source-mix KL drift.
Future waves add prompt-fingerprint drift, latency drift, and per-LLM
hallucination-rate drift.
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
