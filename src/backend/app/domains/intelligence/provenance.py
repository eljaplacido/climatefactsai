"""Per-extraction provenance recorder — Phase 4 wave 3.

Every analytical pipeline that produces a user-visible output (URL claim
extraction, deep-search synthesis, Cynefin classification, hallucination
check, article enrichment) writes a row here recording HOW the output was
produced. The audit-trail endpoints surface these so any displayed score
can be traced back to model + prompt fingerprint + retrieval strategy +
source articles + hallucination verdict + timestamp.

Failure mode: best-effort. If the migration hasn't been applied or the
table is unreachable, `record_provenance` logs a warning and returns None
— the calling pipeline must NEVER fail because provenance recording
broke. The audit trail is non-load-bearing for user-facing functionality.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("provenance")


# ---------------------------------------------------------------------------
# Stable extraction-method slugs
# ---------------------------------------------------------------------------
# Use these constants at every call site so Phase 5 calibration analytics
# can GROUP BY a stable string instead of free-form metadata.

EXTRACTION_URL_ANALYSIS = "url_analysis_claim_extraction"
EXTRACTION_DEEP_SEARCH = "deep_search_synthesis"
EXTRACTION_CYNEFIN = "cynefin_classification"
EXTRACTION_HALLUCINATION = "hallucination_check"
EXTRACTION_INGESTION = "article_ingestion_enrichment"

EXTRACTION_NEGATIVE_CLAIM_REJECTED = "claim_rejected"
EXTRACTION_NEGATIVE_HALLUCINATION = "hallucination_flagged"
EXTRACTION_NEGATIVE_INDICATOR_MISSING = "indicator_missing"
EXTRACTION_NEGATIVE_NO_CONTRADICTION = "no_contradiction_found"
EXTRACTION_NEGATIVE_NUMERIC_GROUNDING = "numeric_grounding_failed"


# ---------------------------------------------------------------------------
# Record dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceRecord:
    """Compact, dataclass-typed shape for one provenance row.

    At least ONE identity link must be set (`claim_id`, `url_analysis_id`,
    `article_id`, `deep_search_session_id`, or `cynefin_classification_id`).
    Enforced by both `record_provenance` and the DB CHECK constraint.

    Migration 023 added `deep_search_session_id` + `cynefin_classification_id`
    to support Phase 4 wave 4 — the deep-search and Cynefin paths don't
    create durable artifacts, so they use ephemeral session UUIDs as
    their identity link.
    """
    extraction_method: str
    claim_id: Optional[str] = None
    url_analysis_id: Optional[str] = None
    article_id: Optional[str] = None
    deep_search_session_id: Optional[str] = None
    cynefin_classification_id: Optional[str] = None
    model_name: Optional[str] = None
    prompt_name: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_fingerprint: Optional[str] = None
    retrieval_strategy: Optional[str] = None
    source_article_ids: Optional[List[str]] = None
    hallucination_score: Optional[float] = None
    confidence: Optional[float] = None
    raw_metadata: Optional[Dict[str, Any]] = field(default=None)

    def has_link(self) -> bool:
        """True iff at least one identifying link is set."""
        return any((
            self.claim_id,
            self.url_analysis_id,
            self.article_id,
            self.deep_search_session_id,
            self.cynefin_classification_id,
        ))


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def record_negative_finding(
    db,
    *,
    extraction_method: str,
    article_id: Optional[str] = None,
    url_analysis_id: Optional[str] = None,
    claim_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Optional[int]:
    """Record a negative finding — what was looked for and not found.

    Unlike `record_provenance` (which records what was produced), this
    records absences: rejected claims, hallucination flags, missing
    indicators, failed numeric grounding, absent contradictions.
    """
    return record_provenance(
        db,
        ProvenanceRecord(
            extraction_method=extraction_method,
            article_id=article_id,
            url_analysis_id=url_analysis_id,
            claim_id=claim_id,
            model_name=model_name,
            raw_metadata=details or {},
            confidence=0.0,
        ),
    )
    """Insert one provenance row. Returns the new id, or None on failure.

    Best-effort: any DB error (table missing, network blip, FK violation)
    is logged as a warning and returns None. The calling pipeline MUST
    treat provenance recording as non-load-bearing.
    """
    if not record.has_link():
        _logger.warning(
            "record_provenance called without claim_id, url_analysis_id, "
            "or article_id (extraction_method=%s)",
            record.extraction_method,
        )
        return None

    try:
        rows = db.execute_query(
            """
            INSERT INTO claim_provenance (
                claim_id, url_analysis_id, article_id,
                deep_search_session_id, cynefin_classification_id,
                extraction_method, model_name,
                prompt_name, prompt_version, prompt_fingerprint,
                retrieval_strategy, source_article_ids,
                hallucination_score, confidence, raw_metadata
            ) VALUES (
                :claim_id, :url_analysis_id, :article_id,
                :deep_search_session_id, :cynefin_classification_id,
                :extraction_method, :model_name,
                :prompt_name, :prompt_version, :prompt_fingerprint,
                :retrieval_strategy, CAST(:source_article_ids AS jsonb),
                :hallucination_score, :confidence, CAST(:raw_metadata AS jsonb)
            )
            RETURNING id
            """,
            {
                "claim_id": record.claim_id,
                "url_analysis_id": record.url_analysis_id,
                "article_id": record.article_id,
                "deep_search_session_id": record.deep_search_session_id,
                "cynefin_classification_id": record.cynefin_classification_id,
                "extraction_method": record.extraction_method,
                "model_name": record.model_name,
                "prompt_name": record.prompt_name,
                "prompt_version": record.prompt_version,
                "prompt_fingerprint": record.prompt_fingerprint,
                "retrieval_strategy": record.retrieval_strategy,
                "source_article_ids": (
                    json.dumps(record.source_article_ids)
                    if record.source_article_ids is not None else None
                ),
                "hallucination_score": record.hallucination_score,
                "confidence": record.confidence,
                "raw_metadata": (
                    json.dumps(record.raw_metadata)
                    if record.raw_metadata is not None else None
                ),
            },
        )
        if rows and rows[0].get("id") is not None:
            return int(rows[0]["id"])
        return None
    except Exception as exc:
        _logger.warning(
            "record_provenance failed (extraction_method=%s): %s",
            record.extraction_method, exc,
        )
        return None


# ---------------------------------------------------------------------------
# Read paths
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows) -> List[Dict[str, Any]]:
    """Normalise DB rows to plain dicts with JSONB columns parsed."""
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        d = dict(r)
        for jsonb_col in ("source_article_ids", "raw_metadata"):
            v = d.get(jsonb_col)
            if isinstance(v, str):
                try:
                    d[jsonb_col] = json.loads(v)
                except Exception:
                    pass
        # Stringify the id columns so JSON responses are predictable.
        for uuid_col in (
            "claim_id",
            "url_analysis_id",
            "article_id",
            "deep_search_session_id",
            "cynefin_classification_id",
        ):
            if d.get(uuid_col) is not None:
                d[uuid_col] = str(d[uuid_col])
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        out.append(d)
    return out


def get_provenance_for_url_analysis(db, analysis_id: str) -> List[Dict[str, Any]]:
    """All provenance rows for one URL-analysis run, newest first."""
    try:
        rows = db.execute_query(
            """
            SELECT * FROM claim_provenance
            WHERE url_analysis_id = :id
            ORDER BY created_at DESC
            """,
            {"id": analysis_id},
        )
    except Exception as exc:
        _logger.warning(f"get_provenance_for_url_analysis failed: {exc}")
        return []
    return _rows_to_dicts(rows)


def get_provenance_for_article(db, article_id: str) -> List[Dict[str, Any]]:
    """All provenance rows for one article, newest first."""
    try:
        rows = db.execute_query(
            """
            SELECT * FROM claim_provenance
            WHERE article_id = :id
            ORDER BY created_at DESC
            """,
            {"id": article_id},
        )
    except Exception as exc:
        _logger.warning(f"get_provenance_for_article failed: {exc}")
        return []
    return _rows_to_dicts(rows)


def get_provenance_for_claim(db, claim_id: str) -> List[Dict[str, Any]]:
    """All provenance rows for one canonical claim, newest first."""
    try:
        rows = db.execute_query(
            """
            SELECT * FROM claim_provenance
            WHERE claim_id = :id
            ORDER BY created_at DESC
            """,
            {"id": claim_id},
        )
    except Exception as exc:
        _logger.warning(f"get_provenance_for_claim failed: {exc}")
        return []
    return _rows_to_dicts(rows)


def get_provenance_for_deep_search_session(
    db, session_id: str,
) -> List[Dict[str, Any]]:
    """All provenance rows tied to one deep-search request, newest first.

    A deep-search call typically writes 1–3 rows (synthesis + optional
    Cynefin classification + optional hallucination grounding). Grouping
    by session_id lets the audit-trail endpoint render a single request's
    full reasoning trail.
    """
    try:
        rows = db.execute_query(
            """
            SELECT * FROM claim_provenance
            WHERE deep_search_session_id = :id
            ORDER BY created_at DESC
            """,
            {"id": session_id},
        )
    except Exception as exc:
        _logger.warning(f"get_provenance_for_deep_search_session failed: {exc}")
        return []
    return _rows_to_dicts(rows)
