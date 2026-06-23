-- Migration 015: Widen credibility columns to support MIXED and UNVERIFIED levels
-- Fix: overall_credibility VARCHAR(20) was too narrow for ReliabilityScorer output
-- The scorer produces HIGH, MEDIUM, LOW, MIXED, UNVERIFIED - all fit but the
-- CHECK constraint in some schemas rejected MIXED/UNVERIFIED, and future
-- labels (e.g. "DISPUTED_SOURCE") would overflow VARCHAR(20).

-- Widen url_analyses.overall_credibility
ALTER TABLE url_analyses ALTER COLUMN overall_credibility TYPE VARCHAR(50);

-- Drop the restrictive CHECK constraint if it exists (some schemas have it, some don't)
DO $$
BEGIN
    ALTER TABLE url_analyses DROP CONSTRAINT IF EXISTS valid_credibility;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;

-- Add the inclusive CHECK constraint
DO $$
BEGIN
    ALTER TABLE url_analyses ADD CONSTRAINT valid_credibility
        CHECK (overall_credibility IS NULL OR overall_credibility IN ('HIGH', 'MEDIUM', 'LOW', 'MIXED', 'UNVERIFIED'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Widen articles.overall_credibility
ALTER TABLE articles ALTER COLUMN overall_credibility TYPE VARCHAR(50);
