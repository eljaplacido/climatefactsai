-- Migration 050: topic_feedback table (Stage 3 / M4 — evolving validation corpus)
--
-- Source-of-truth for "is this article actually climate-relevant?". Lets
-- the user mark an article as off-topic from the article-detail page,
-- and lets the golden pipeline daemon exclude flagged articles from
-- future selection waves.
--
-- The user said: "we should build some sort of evolving validation
-- corpus on what articles, research etc. we filter on the platform."
-- This is the first concrete substrate for that.
--
-- Each row is one (article, verdict) opinion. Multiple rows per article
-- allowed so we can later compute a "consensus" verdict (e.g. 3 users
-- mark off-topic → exclude; 1 contested opinion → keep). For now a
-- single opinion is enough to gate.

CREATE TABLE IF NOT EXISTS topic_feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL CHECK (verdict IN ('on_topic', 'off_topic', 'borderline')),
    reason          TEXT,
    -- Optional reporter — null for anonymous flags from the article page.
    -- Keeps the schema permissive for the MVP; consensus weighting can
    -- later use this to give signed-in users more weight than anon flags.
    reporter_id     UUID,
    -- Free-form category tag so reporters can express WHY a piece is off
    -- topic (e.g. "politics", "sports", "finance"). Powers future
    -- per-category training of the classifier.
    off_topic_category TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topic_feedback_article
    ON topic_feedback(article_id);
CREATE INDEX IF NOT EXISTS idx_topic_feedback_verdict
    ON topic_feedback(verdict, created_at DESC);
