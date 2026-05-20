-- Migration 028: drift threshold fits table
--
-- Stores learned drift thresholds so the platform can replace hard-coded
-- 0.10 / 0.25 / 0.50 KL thresholds with Gaussian 2σ/3σ/4σ fits from
-- production baseline data.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS drift_threshold_fits (
    id              BIGSERIAL PRIMARY KEY,
    metric          VARCHAR(64) NOT NULL,
    mu              DOUBLE PRECISION NOT NULL,
    sigma           DOUBLE PRECISION NOT NULL,
    threshold_2sigma DOUBLE PRECISION NOT NULL,
    threshold_3sigma DOUBLE PRECISION NOT NULL,
    threshold_4sigma DOUBLE PRECISION NOT NULL,
    n_samples       INTEGER NOT NULL,
    fitted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_threshold_fits_metric
    ON drift_threshold_fits (metric, fitted_at DESC);
