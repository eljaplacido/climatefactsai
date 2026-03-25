-- Migration 011: Add content_type and research metadata to articles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_type VARCHAR(30) DEFAULT 'news_article';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS doi TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS publication_venue TEXT;
CREATE INDEX IF NOT EXISTS idx_articles_content_type ON articles(content_type);
CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi) WHERE doi IS NOT NULL;
-- Backfill: all existing articles are news_article (default)
