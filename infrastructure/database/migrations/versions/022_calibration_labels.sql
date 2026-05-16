-- =============================================================================
-- 022_calibration_labels.sql — Ground-truth labels for confidence calibration
-- =============================================================================
-- Phase 5 wave 4: the platform now records per-analysis `reliability_score`,
-- `agreement_score` (multi-LLM), and `hallucination_score` for every URL
-- analysis (wired in commits 8a3402e, 71997f9, 39c36b7). To turn those raw
-- signals into CALIBRATED confidence we need ground truth — labels saying
-- "for this analysis, the platform's claims were actually true/false".
--
-- This table holds those labels. Operators/auditors review URL analyses
-- and record a binary or graded truth label (0.0–1.0). The calibration
-- module then computes Brier score + ECE and fits Platt-scaling parameters
-- against the (raw_confidence, ground_truth) pairs.
--
-- Why graded labels (0–1) not just binary:
--   * "Some claims true, some false" is a real category; forcing binary
--     loses signal.
--   * The reviewer can encode their own confidence in the label
--     (e.g., 0.9 = "very confident this is mostly true").
--
-- Workflow:
--   1. Operator reads a URL analysis.
--   2. Records a label (`label_truth` 0–1) + reviewer ID + optional notes.
--   3. Periodic Celery job recomputes Brier/ECE + Platt parameters over
--      all available labels.
--   4. Future wave: the application reads the Platt parameters at inference
--      and surfaces calibrated_confidence alongside raw confidence.
--
-- The UNIQUE constraint (analysis_id, labeled_by, label_method) allows
-- multiple reviewers to label the same analysis (their judgments
-- aggregate); a single reviewer can't double-label via the same method.
-- =============================================================================

CREATE TABLE IF NOT EXISTS calibration_labels (
    id                  BIGSERIAL PRIMARY KEY,

    -- The analysis being labelled. CASCADE delete keeps labels in sync
    -- with the analyses table if an analysis is purged.
    url_analysis_id     UUID NOT NULL,

    -- Ground truth: 0.0 = analysis was wrong, 1.0 = analysis was correct.
    -- Graded labels in [0, 1] are supported (reviewer's own confidence
    -- in the truth verdict).
    label_truth         DOUBLE PRECISION NOT NULL
        CHECK (label_truth >= 0.0 AND label_truth <= 1.0),

    -- Who/what produced this label.
    labeled_by          VARCHAR(128) NOT NULL,
    label_method        VARCHAR(64)  NOT NULL DEFAULT 'human_review',
        -- 'human_review' | 'external_factcheck' | 'consensus_panel' |
        -- 'reviewer_team_lead' | 'auto_baseline'

    labeled_at          TIMESTAMP    NOT NULL DEFAULT NOW(),

    -- Snapshot of what the platform thought at labelling time. Useful for
    -- temporal calibration drift analysis (Phase 6 wave 3).
    confidence_at_label DOUBLE PRECISION,

    label_notes         TEXT,

    -- A single reviewer + method can't double-label the same analysis,
    -- but multiple reviewers (or the same reviewer via a different
    -- method) can each label it — those rows aggregate in calibration.
    CONSTRAINT uq_calibration_labels_natural
        UNIQUE (url_analysis_id, labeled_by, label_method)
);

CREATE INDEX IF NOT EXISTS idx_calibration_labels_analysis_id
    ON calibration_labels(url_analysis_id);

CREATE INDEX IF NOT EXISTS idx_calibration_labels_labeled_at
    ON calibration_labels(labeled_at DESC);

CREATE INDEX IF NOT EXISTS idx_calibration_labels_method
    ON calibration_labels(label_method);


-- -----------------------------------------------------------------------------
-- Platt-scaling fitted parameters (one row per fit run).
-- -----------------------------------------------------------------------------
-- Each calibration run snapshots the Platt parameters (A, B) plus the
-- Brier score + ECE at fit time. The application reads the most recent
-- row to apply calibrated_confidence at inference. Old rows are kept
-- forever so we can audit how calibration evolved.

CREATE TABLE IF NOT EXISTS calibration_fits (
    id              BIGSERIAL PRIMARY KEY,
    fitted_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    -- Which raw signal was calibrated. Same signal can be calibrated
    -- multiple times as more labels accumulate.
    signal_name     VARCHAR(64) NOT NULL,
        -- 'reliability_score' | 'agreement_score' | 'hallucination_score'
    -- Platt parameters: P_calibrated(y=1 | p) = 1 / (1 + exp(A * p + B))
    platt_a         DOUBLE PRECISION NOT NULL,
    platt_b         DOUBLE PRECISION NOT NULL,
    -- Quality metrics at fit time
    brier_score     DOUBLE PRECISION NOT NULL,
    ece             DOUBLE PRECISION NOT NULL,
    n_labels        INTEGER         NOT NULL,
    -- Reliability diagram bins as JSON: [{bin_lower, bin_upper, mean_pred, mean_actual, count}, ...]
    reliability_diagram JSONB,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_calibration_fits_signal_recency
    ON calibration_fits(signal_name, fitted_at DESC);

COMMENT ON TABLE calibration_labels IS
    'Per-URL-analysis ground-truth labels supplied by reviewers; '
    'used to compute Brier / ECE and fit Platt scaling.';

COMMENT ON TABLE calibration_fits IS
    'Versioned record of every Platt-scaling fit. Application reads the '
    'most-recent row per signal_name to apply calibrated_confidence at '
    'inference.';
