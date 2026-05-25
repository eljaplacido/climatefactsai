"""Saved-items polymorphic save bucket — Phase 10 (2026-05-25).

Per user feedback: "save not only articles, but analysis results, their
different my feed settings". Backs the saved_items table (migration 042)
with REST endpoints. Eight item types supported:

  article | analysis | claim | search | company | feed_setting |
  deep_search | country

Endpoints (all behind JWT auth):

  GET    /api/user/saved                   — list everything I've saved
  GET    /api/user/saved?type=article      — filter by type
  POST   /api/user/saved                   — save anything (body: SavedItemRequest)
  DELETE /api/user/saved/{saved_id}        — unsave by saved_id

Quotas: same saved_articles quota gate as the legacy bookmark endpoint
when item_type='article'. Other types are unmetered for now (Pro tier
gets unlimited; Free gets 5 of each non-article type as a sensible
soft cap).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("saved-items-routes")
router = APIRouter(prefix="/api/user/saved", tags=["Saved items"])


_VALID_TYPES = {
    "article", "analysis", "claim", "search", "company",
    "feed_setting", "deep_search", "country",
}

# Soft caps for non-article types on Free tier.
_FREE_TIER_SOFT_CAPS = {
    "search": 5,
    "deep_search": 3,
    "feed_setting": 3,
    "country": 10,
    "company": 5,
    "claim": 10,
    "analysis": 5,
}


class SavedItemRequest(BaseModel):
    item_type: str = Field(..., description="article|analysis|claim|search|company|feed_setting|deep_search|country")
    item_id: Optional[str] = Field(None, description="UUID PK of the target (for FK-able types)")
    item_ref: Optional[str] = Field(None, description="Free-text reference (search URL, country code, JSON payload)")
    label: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=2000)
    folder: Optional[str] = Field("default", max_length=64)
    payload: Optional[dict] = Field(None, description="Arbitrary JSON state for the saved item")


@router.get("")
async def list_saved_items(
    item_type: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """List the current user's saved items, optionally filtered by type
    or folder."""
    db = get_postgres()
    filters = ["user_id = :uid"]
    params: dict = {"uid": current_user["user_id"], "lim": limit}

    if item_type:
        if item_type not in _VALID_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown item_type {item_type!r}. Expected: {sorted(_VALID_TYPES)}",
            )
        filters.append("item_type = :it")
        params["it"] = item_type
    if folder:
        filters.append("folder = :f")
        params["f"] = folder

    where = " AND ".join(filters)
    rows = db.execute_query(
        f"""SELECT saved_id, item_type, item_id, item_ref, label, notes,
                   folder, payload, created_at
            FROM saved_items
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :lim""",
        params,
    )
    return {
        "items": [
            {
                "saved_id": str(r["saved_id"]),
                "item_type": r["item_type"],
                "item_id": str(r["item_id"]) if r.get("item_id") else None,
                "item_ref": r.get("item_ref"),
                "label": r.get("label"),
                "notes": r.get("notes"),
                "folder": r.get("folder"),
                "payload": r.get("payload"),
                "created_at": str(r["created_at"]) if r.get("created_at") else None,
            }
            for r in (rows or [])
        ],
        "total": len(rows or []),
    }


@router.post("", status_code=201)
async def create_saved_item(
    request: SavedItemRequest,
    current_user: dict = Depends(get_current_user),
):
    """Save anything. Idempotent — re-saving the same item updates label/notes/folder."""
    if request.item_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown item_type {request.item_type!r}",
        )
    if (request.item_id is None) == (request.item_ref is None):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of item_id (UUID) or item_ref (text) must be provided",
        )

    db = get_postgres()
    user_id = current_user["user_id"]
    user_tier = str(current_user.get("subscription_tier", "freemium"))

    # Quota gate for article type — delegates to existing QuotaService
    # for parity with the legacy bookmark endpoint.
    if request.item_type == "article":
        from api.quota_service import QuotaService
        existing = db.execute_query(
            """SELECT 1 FROM saved_items
               WHERE user_id = :uid AND item_type = 'article'
                 AND item_id = :iid LIMIT 1""",
            {"uid": user_id, "iid": request.item_id},
        )
        if not existing:
            QuotaService.check_and_raise(
                user_id=str(user_id), tier=user_tier, quota_key="saved_articles",
            )
    elif user_tier in ("freemium", "free", "anonymous"):
        # Soft cap on non-article types for Free tier.
        cap = _FREE_TIER_SOFT_CAPS.get(request.item_type, 5)
        used = db.execute_query(
            """SELECT COUNT(*) AS n FROM saved_items
               WHERE user_id = :uid AND item_type = :it""",
            {"uid": user_id, "it": request.item_type},
        )
        used_count = int(used[0]["n"]) if used else 0
        existing_q = db.execute_query(
            """SELECT 1 FROM saved_items
               WHERE user_id = :uid AND item_type = :it
                 AND (item_id = :iid OR item_ref = :ref)
               LIMIT 1""",
            {"uid": user_id, "it": request.item_type,
             "iid": request.item_id, "ref": request.item_ref},
        )
        if not existing_q and used_count >= cap:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "saved_item_tier_limit",
                    "tier": user_tier,
                    "item_type": request.item_type,
                    "used": used_count,
                    "limit": cap,
                    "upgrade_url": "/dashboard/subscription",
                    "message": (
                        f"Free tier saves up to {cap} {request.item_type}s. "
                        f"Upgrade for unlimited."
                    ),
                },
            )

    try:
        import json as _json
        db.execute_update(
            """INSERT INTO saved_items
               (user_id, item_type, item_id, item_ref, label, notes, folder, payload)
               VALUES (:uid, :it, :iid, :ref, :lbl, :nt, :fl, CAST(:pl AS jsonb))
               ON CONFLICT (user_id, item_type, item_id, item_ref)
               DO UPDATE SET label = EXCLUDED.label, notes = EXCLUDED.notes,
                             folder = EXCLUDED.folder, payload = EXCLUDED.payload,
                             updated_at = NOW()""",
            {
                "uid": user_id,
                "it": request.item_type,
                "iid": request.item_id,
                "ref": request.item_ref,
                "lbl": request.label,
                "nt": request.notes,
                "fl": request.folder or "default",
                "pl": _json.dumps(request.payload) if request.payload else None,
            },
        )
    except Exception as exc:
        logger.error(f"saved_items insert failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "save_failed",
                "message": (
                    f"Couldn't save: {type(exc).__name__}. "
                    "If you were saving an article that was just removed "
                    "from the corpus (synthetic-data purge), that's expected — "
                    "try a different article."
                ),
            },
        )
    return {"message": f"Saved {request.item_type}", "item_type": request.item_type}


@router.get("/check")
async def check_saved_item(
    item_type: str = Query(..., description="One of the 8 valid item types"),
    item_id: Optional[str] = Query(None, description="UUID for FK-able types"),
    item_ref: Optional[str] = Query(None, description="Text ref (search URL, country code, ...)"),
    current_user: dict = Depends(get_current_user),
):
    """Lightweight per-item 'is this saved' probe for buttons.

    Cheaper than listing all saves of a type just to check one membership.
    Returns {saved: bool, saved_id: str|null} so the caller can immediately
    DELETE without re-querying.
    """
    if item_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown item_type {item_type!r}")
    if (item_id is None) == (item_ref is None):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of item_id or item_ref must be provided",
        )

    db = get_postgres()
    rows = db.execute_query(
        """SELECT saved_id FROM saved_items
           WHERE user_id = :uid AND item_type = :it
             AND ((item_id = :iid AND :iid IS NOT NULL)
                  OR (item_ref = :ref AND :ref IS NOT NULL))
           LIMIT 1""",
        {
            "uid": current_user["user_id"],
            "it": item_type,
            "iid": item_id,
            "ref": item_ref,
        },
    )
    if rows:
        return {"saved": True, "saved_id": str(rows[0]["saved_id"])}
    return {"saved": False, "saved_id": None}


@router.delete("/{saved_id}")
async def delete_saved_item(
    saved_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Unsave by saved_id."""
    db = get_postgres()
    try:
        uuid.UUID(saved_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid saved_id")
    deleted = db.execute_update(
        "DELETE FROM saved_items WHERE saved_id = :sid AND user_id = :uid",
        {"sid": saved_id, "uid": current_user["user_id"]},
    )
    if not deleted:
        # No-op is acceptable; FE optimistic-removes already.
        return {"message": "No matching saved item"}
    return {"message": "Saved item removed"}
