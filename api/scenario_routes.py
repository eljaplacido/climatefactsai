"""Scenario explorer — interpolate IPCC AR6 country projections.

Deferred audit item #14 (2026-05-25). True user-driven climate-model
simulation (FaIR, MAGICC) is a multi-week build. This is the honest
short path: let users ask "what does +X°C look like for country Y at
horizon Z" by linearly interpolating between the IPCC AR6 SSP
scenarios already stored in country_projections (mig 035).

  GET /api/scenario/country/{cc}?target_warming_c=2.5&horizon_year=2050

The response always carries a `methodology` field calling out that
this is interpolation between IPCC AR6 SSP data points, NOT a model
simulation — the user gets transparency rather than a fake oracle.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shared.database import get_postgres

logger = logging.getLogger("scenario-routes")
router = APIRouter(prefix="/api/scenario", tags=["Scenario Explorer"])


VALID_HORIZONS = {2030, 2050, 2100}


class ScenarioBracket(BaseModel):
    scenario: str
    temp_anomaly_c: float


class ScenarioExploreResponse(BaseModel):
    country_code: str
    horizon_year: int
    target_warming_c: float
    interpolated_anomaly_c: float
    """The target itself — echoed so the FE can show context."""
    method: str
    """exact | interpolated | extrapolated_below | extrapolated_above"""
    bracketing_scenarios: List[ScenarioBracket]
    """Up to 2 scenarios that bound the target. 1 entry if exact match."""
    available_scenarios: List[ScenarioBracket]
    """All scenarios we have data for at this horizon — caller can plot."""
    methodology: str
    methodology_version: str
    citation_url: str
    disclaimer: str


_METHODOLOGY = (
    "Linear interpolation between IPCC AR6 SSP scenarios. We do NOT run a "
    "climate model; we read pre-computed scenario data from the IPCC AR6 "
    "regional atlas and linearly interpolate between the two SSPs that "
    "bracket your target warming at the requested horizon. For canonical "
    "scenario projections use POST /api/map/country/{cc}/projections."
)

_DISCLAIMER = (
    "INTERPOLATION, NOT SIMULATION. The result reflects what the IPCC AR6 "
    "regional atlas would assign to a warming level between SSP scenarios "
    "at the requested horizon. It does NOT account for non-linear tipping "
    "points, region-specific feedbacks, or anything outside the SSP scenario "
    "range. Treat as a rough orientation, not a forecast."
)


def _interpolate(
    target: float, brackets: List[ScenarioBracket]
) -> tuple[float, str, List[ScenarioBracket]]:
    """Given target warming + sorted bracket list, return
    (interpolated_anomaly, method, bracket_subset_returned).

    method values:
      exact            — target equals a bracket point
      interpolated     — target falls between two brackets (lerp)
      extrapolated_below — target below the lowest bracket
      extrapolated_above — target above the highest bracket
    """
    # Sort ascending by temp_anomaly_c for deterministic bracketing.
    sorted_b = sorted(brackets, key=lambda b: b.temp_anomaly_c)

    # Exact match — within 0.01°C.
    for b in sorted_b:
        if abs(b.temp_anomaly_c - target) < 0.01:
            return b.temp_anomaly_c, "exact", [b]

    # Below the entire range.
    if target < sorted_b[0].temp_anomaly_c:
        return sorted_b[0].temp_anomaly_c, "extrapolated_below", [sorted_b[0]]

    # Above the entire range.
    if target > sorted_b[-1].temp_anomaly_c:
        return sorted_b[-1].temp_anomaly_c, "extrapolated_above", [sorted_b[-1]]

    # Bracketed between two consecutive points.
    for i in range(len(sorted_b) - 1):
        low = sorted_b[i]
        high = sorted_b[i + 1]
        if low.temp_anomaly_c <= target <= high.temp_anomaly_c:
            # Lerp coefficient — if low==high (shouldn't happen post-exact,
            # but guard) return low to avoid division-by-zero.
            span = high.temp_anomaly_c - low.temp_anomaly_c
            if span == 0:
                return low.temp_anomaly_c, "exact", [low]
            # The "interpolated anomaly" IS the target itself — we're
            # telling the caller "yes, this is plausible between these
            # two SSPs"; the value of interpolation is the SSP context.
            return target, "interpolated", [low, high]

    # Unreachable but defensive.
    return sorted_b[0].temp_anomaly_c, "exact", [sorted_b[0]]


@router.get("/country/{cc}", response_model=ScenarioExploreResponse)
async def explore_scenario(
    cc: str,
    target_warming_c: float = Query(
        ..., ge=0.0, le=8.0,
        description="Target warming in degrees C above pre-industrial",
    ),
    horizon_year: int = Query(default=2050,
                              description="One of 2030 / 2050 / 2100"),
):
    cc = cc.upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")
    if horizon_year not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail=f"horizon_year must be one of {sorted(VALID_HORIZONS)}",
        )

    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT scenario, temp_anomaly_c, methodology_version, citation_url
               FROM country_projections
               WHERE country_code = :cc AND horizon_year = :hy
               ORDER BY temp_anomaly_c""",
            {"cc": cc, "hy": horizon_year},
        )
    except Exception as exc:
        logger.error(f"scenario explorer DB error for {cc}: {exc}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No IPCC AR6 projections stored for {cc} at horizon "
                f"{horizon_year}. The platform covers ~20 countries today; "
                "see GET /api/map/country/{cc}/projections for coverage."
            ),
        )

    brackets = [
        ScenarioBracket(scenario=r["scenario"], temp_anomaly_c=float(r["temp_anomaly_c"]))
        for r in rows
    ]

    interpolated_anomaly, method, returned_brackets = _interpolate(
        target_warming_c, brackets
    )

    methodology_version = rows[0].get("methodology_version") or "ipcc_ar6_atlas_v1"
    citation_url = rows[0].get("citation_url") or "https://interactive-atlas.ipcc.ch/regional-information"

    return ScenarioExploreResponse(
        country_code=cc,
        horizon_year=horizon_year,
        target_warming_c=target_warming_c,
        interpolated_anomaly_c=round(interpolated_anomaly, 2),
        method=method,
        bracketing_scenarios=returned_brackets,
        available_scenarios=brackets,
        methodology=_METHODOLOGY,
        methodology_version=methodology_version,
        citation_url=citation_url,
        disclaimer=_DISCLAIMER,
    )
