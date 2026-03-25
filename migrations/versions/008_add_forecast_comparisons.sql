-- Migration 008: Add climate forecast comparisons table
-- Stores multi-source climate forecasts per country for comparison

CREATE TABLE IF NOT EXISTS climate_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    forecast_date DATE NOT NULL,
    temperature_avg FLOAT,
    temperature_min FLOAT,
    temperature_max FLOAT,
    precipitation_mm FLOAT,
    wind_speed_ms FLOAT,
    humidity_pct FLOAT,
    confidence FLOAT DEFAULT 0.5,
    raw_data JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '6 hours'
);

CREATE INDEX IF NOT EXISTS idx_forecasts_country ON climate_forecasts(country_code);
CREATE INDEX IF NOT EXISTS idx_forecasts_date ON climate_forecasts(forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_expires ON climate_forecasts(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_forecasts_unique ON climate_forecasts(country_code, source_name, forecast_date);

COMMENT ON TABLE climate_forecasts IS 'Multi-source climate forecasts for comparison view';
