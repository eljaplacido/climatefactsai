-- Migration 004: Add decomposed confidence and claim classification
-- Supports CARF-inspired multi-factor credibility scoring

-- Per-claim decomposed confidence
ALTER TABLE fact_checks ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE fact_checks ADD COLUMN IF NOT EXISTS evidence_chain JSONB DEFAULT NULL;

-- Claim classification for verification routing
ALTER TABLE claims ADD COLUMN IF NOT EXISTS claim_category VARCHAR(50) DEFAULT 'statistical';

-- Article-level aggregate decomposed confidence
ALTER TABLE articles ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS insight_summary TEXT DEFAULT NULL;

-- URL analysis decomposed results
ALTER TABLE url_analyses ADD COLUMN IF NOT EXISTS decomposed_confidence JSONB DEFAULT NULL;
ALTER TABLE url_analyses ADD COLUMN IF NOT EXISTS reliability_breakdown JSONB DEFAULT NULL;

-- Index for claim category filtering
CREATE INDEX IF NOT EXISTS idx_claims_category ON claims(claim_category);

COMMENT ON COLUMN fact_checks.decomposed_confidence IS 'Multi-factor confidence: model_confidence, source_quality, evidence_breadth, cross_reference_score, temporal_relevance';
COMMENT ON COLUMN claims.claim_category IS 'Claim type: scientific_causal, statistical, policy, anecdotal, predictive';
COMMENT ON COLUMN articles.insight_summary IS 'AI-generated 2-3 paragraph summary of verification findings';
