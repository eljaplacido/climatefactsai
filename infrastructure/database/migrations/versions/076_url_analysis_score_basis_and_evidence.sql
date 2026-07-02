-- @notolerate
-- Migration 076: url_analyses.score_basis + auditable evidence (ML-09 / ML-10)
-- Date: 2026-07-02
--
-- ML-09 — the URL-analysis credibility badge could read HIGH from a pure
-- text-length/claim-count heuristic even when NO claim reached a supporting
-- verdict. The route now FLOORS such cases to UNVERIFIED and stamps how the
-- score was decided. `score_basis` persists that provenance so the label is
-- self-explaining end-to-end:
--   * 'verification_backed'  — fact-check verdicts drove the score
--   * 'extraction_heuristic' — text-length/claim-count fallback (unverified)
--
-- ML-10 — the adjudicator's evidence_chain (source_url + retrieval_method),
-- decomposed_confidence, and top Evidence used to be discarded, leaving the
-- live GET returning evidence:[] with no way to drill a verdict to its sources.
-- The per-verdict payload now rides inside the existing `fact_checks` JSONB; the
-- aggregated, source-linked top evidence is persisted here in `evidence`.
--
-- Both columns are additive + nullable + IF NOT EXISTS => idempotent and safe to
-- re-run. `evidence` may already exist (early bootstrap schema); IF NOT EXISTS
-- makes the ADD a no-op in that case. No CREATE TABLE (url_analyses already
-- exists — see migration 031 which ALTERs it). No backfill: legacy rows keep
-- score_basis NULL / evidence NULL and the API falls back gracefully.
-- The @notolerate directive forces a failure to be LOUD, never silently marked
-- applied.

ALTER TABLE url_analyses
    ADD COLUMN IF NOT EXISTS score_basis VARCHAR(32),
    ADD COLUMN IF NOT EXISTS evidence    JSONB;

COMMENT ON COLUMN url_analyses.score_basis IS
    'How the credibility label was decided: verification_backed (fact-check '
    'verdicts drove the score) or extraction_heuristic (text-length/claim-count '
    'fallback, nothing verified). NULL for legacy rows predating migration 076.';

COMMENT ON COLUMN url_analyses.evidence IS
    'Aggregated top evidence across verdicts (ML-10). JSON array; each item '
    'carries source_url + retrieval_method + excerpt so each verdict drills down '
    'to its sources. Per-verdict evidence also rides inside fact_checks.';

DO $$
DECLARE has_basis INT; has_evidence INT;
BEGIN
    SELECT COUNT(*) INTO has_basis
    FROM information_schema.columns
    WHERE table_name = 'url_analyses' AND column_name = 'score_basis';
    SELECT COUNT(*) INTO has_evidence
    FROM information_schema.columns
    WHERE table_name = 'url_analyses' AND column_name = 'evidence';
    RAISE NOTICE 'migration 076: url_analyses.score_basis present=% evidence present=%', has_basis, has_evidence;
END $$;
