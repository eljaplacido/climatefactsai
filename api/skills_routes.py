"""Skills introspection endpoint — Phase 4C (2026-05-24).

  GET /api/skills           — list every registered agentic skill
  GET /api/skills/{name}    — one skill's full schema

Read-only and unauthenticated. Letting external consumers (curious
journalists, future open-spec adopters, the frontend at runtime) read
the action manifest without a token is the right default for the
"agentic transparency standard" framing — same posture as /methodology.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.domains.intelligence.skills import (
    get_skill,
    serialize_registry,
    serialize_skill,
)

router = APIRouter(prefix="/api/skills", tags=["Skills"])


@router.get("")
async def list_skills_endpoint():
    """Return the full agentic skills registry.

    Response shape (counts computed live from the registry, not fixed):
      {
        "skills": [{name, description, mode, parameters[], target_surfaces[]}, ...],
        "total": 22,
        "modes": {"auto": 11, "confirm": 11}
      }
    """
    return serialize_registry()


@router.get("/{name}")
async def get_skill_endpoint(name: str):
    """Return one skill's full schema. 404 if unregistered."""
    skill = get_skill(name)
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {name!r}",
        )
    return serialize_skill(skill)
