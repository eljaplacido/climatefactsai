-- Migration 006: Add analysis article fields to articles table
-- Stores AI-generated analysis articles with embedded KPIs

ALTER TABLE articles ADD COLUMN IF NOT EXISTS analysis_article_html TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS analysis_article_generated_at TIMESTAMPTZ;

-- Index for quickly finding articles with/without analysis
CREATE INDEX IF NOT EXISTS idx_articles_analysis_generated
ON articles (analysis_article_generated_at)
WHERE analysis_article_generated_at IS NOT NULL;

COMMENT ON COLUMN articles.analysis_article_html IS 'AI-generated structured analysis article in HTML format';
COMMENT ON COLUMN articles.analysis_article_generated_at IS 'Timestamp when analysis article was last generated';
