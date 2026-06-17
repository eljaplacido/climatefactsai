"""Golden examples — the curated "best of" corpus.

User's framing: "we should always have the best case examples to refer
to and which guide also the development of gx10 local inference
workflows."

Two purposes:
  1. Quality reference — clickable index of the best enriched articles,
     research analyses, company verdicts, semantic explanations, map
     insights, KG drill-downs.
  2. LoRA training data seeds — exports filtered to quality_score >= 4
     for the climate-claim-extractor-7B / context-summarizer-7B /
     verdict-adjudicator-7B specialists in
     docs/reports/asusgx10inferencestrategy.md.

Endpoints:
  POST /api/golden-examples            — promote an artifact (auth)
  GET  /api/golden-examples            — list, paginated, filterable
  GET  /api/golden-examples/{kind}     — list one kind
  GET  /api/golden-examples/export     — JSONL export for LoRA training
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from api.admin_pipeline_routes import require_admin
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("golden-examples")
router = APIRouter(prefix="/api/golden-examples", tags=["Golden Examples"])

ARTIFACT_KINDS = {
    "article_enrichment",
    "research_analysis",
    "company_verdict",
    "semantic_explanation",
    "map_insight",
    "kg_drill_down",
}


class PromoteRequest(BaseModel):
    artifact_kind: str = Field(..., description="One of the 6 supported kinds")
    artifact_ref: str = Field(..., min_length=1, max_length=200)
    why_golden: str = Field(..., min_length=10, max_length=1000)
    quality_score: int = Field(default=4, ge=1, le=5)
    domain_tag: Optional[str] = Field(None, max_length=80)


@router.post("")
async def promote_to_golden(
    payload: PromoteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Mark an artifact as a golden example. Idempotent per (kind, ref)
    — re-promoting updates the why_golden + quality_score in place.

    Admin/curator-gated (2026-06-10 audit): golden examples seed LoRA training
    data for the GX10 specialists, so promotion must not be open to any
    logged-in user. Enterprise tier or an ADMIN_EMAILS address only."""
    require_admin(current_user or {})
    if payload.artifact_kind not in ARTIFACT_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"artifact_kind must be one of {sorted(ARTIFACT_KINDS)}",
        )
    db = get_postgres()
    curator_id = (current_user or {}).get("user_id")
    db.execute_update(
        """INSERT INTO golden_examples (
               golden_id, artifact_kind, artifact_ref,
               why_golden, quality_score, domain_tag, curator_id
           ) VALUES (:gid, :kind, :ref, :why, :score, :tag, :cur)
           ON CONFLICT (artifact_kind, artifact_ref) DO UPDATE
              SET why_golden    = EXCLUDED.why_golden,
                  quality_score = EXCLUDED.quality_score,
                  domain_tag    = EXCLUDED.domain_tag,
                  updated_at    = NOW()""",
        {
            "gid": str(uuid4()),
            "kind": payload.artifact_kind,
            "ref": payload.artifact_ref,
            "why": payload.why_golden,
            "score": payload.quality_score,
            "tag": payload.domain_tag,
            "cur": curator_id,
        },
    )
    logger.info(
        f"golden-example: kind={payload.artifact_kind} ref={payload.artifact_ref[:60]} "
        f"score={payload.quality_score} curator={curator_id or 'anon'}"
    )
    return {"status": "promoted", "kind": payload.artifact_kind, "ref": payload.artifact_ref}


@router.get("")
async def list_golden_examples(
    kind: Optional[str] = None,
    min_score: int = Query(1, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
):
    """List golden examples — optionally filter by kind + min score."""
    if kind and kind not in ARTIFACT_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind must be one of {sorted(ARTIFACT_KINDS)}",
        )
    db = get_postgres()
    sql = (
        """SELECT golden_id::text AS golden_id,
                  artifact_kind, artifact_ref,
                  why_golden, quality_score, domain_tag,
                  curator_id::text AS curator_id,
                  created_at, updated_at
           FROM golden_examples
           WHERE quality_score >= :score"""
    )
    params: dict = {"score": min_score, "lim": limit}
    if kind:
        sql += " AND artifact_kind = :kind"
        params["kind"] = kind
    sql += " ORDER BY quality_score DESC, updated_at DESC LIMIT :lim"
    rows = db.execute_query(sql, params)
    # Group by kind for the response
    by_kind: dict[str, list] = {k: [] for k in ARTIFACT_KINDS}
    for r in rows:
        by_kind.setdefault(r["artifact_kind"], []).append(dict(r))
    return {
        "total": len(rows),
        "by_kind": by_kind,
    }


@router.get("/export")
async def export_lora_training_set(
    kind: str,
    min_score: int = Query(4, ge=1, le=5),
    limit: int = Query(1000, ge=1, le=10000),
):
    """JSONL export of golden examples for LoRA fine-tuning seeds.

    Output: newline-delimited JSON, one record per line, with the
    artifact reference + curator's why_golden note. Downstream training
    scripts in scripts/ join this with the actual artifact content
    (enrichment metadata, claim text, etc.) to build the prompt/answer
    pairs.

    `kind` is required — the LoRA specialists target one artifact kind
    each (claim-extractor on company_verdict + research_analysis,
    context-summarizer on article_enrichment).
    """
    if kind not in ARTIFACT_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind must be one of {sorted(ARTIFACT_KINDS)}",
        )
    db = get_postgres()
    rows = db.execute_query(
        """SELECT artifact_ref, why_golden, quality_score, domain_tag,
                  created_at
           FROM golden_examples
           WHERE artifact_kind = :kind AND quality_score >= :score
           ORDER BY quality_score DESC, updated_at DESC
           LIMIT :lim""",
        {"kind": kind, "score": min_score, "lim": limit},
    )
    import json
    out = "\n".join(
        json.dumps({
            "ref": r["artifact_ref"],
            "why": r["why_golden"],
            "score": int(r["quality_score"]),
            "tag": r.get("domain_tag"),
            "promoted_at": str(r["created_at"]),
        }, ensure_ascii=False)
        for r in rows
    )
    return PlainTextResponse(content=out, media_type="application/x-ndjson")
