-- =============================================================================
-- 013: Knowledge graph — entities, relationships, article-entity links
-- Powers cross-article intelligence, entity timelines, and network analysis
-- for climate actors, policies, technologies, and events.
-- Run: docker exec -i climatenews-postgres psql -U postgres -d climatenews < migrations/versions/013_knowledge_graph.sql
-- =============================================================================

BEGIN;

INSERT INTO schema_migrations (version, description)
VALUES (13, '013_knowledge_graph.sql - knowledge graph entities and relationships')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- ENTITY TYPE ENUM
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE entity_type_enum AS ENUM (
        'PERSON',
        'ORGANIZATION',
        'LOCATION',
        'POLICY',
        'EVENT',
        'TECHNOLOGY',
        'EMISSION_SOURCE',
        'CONCEPT'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- RELATIONSHIP TYPE ENUM
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE relationship_type_enum AS ENUM (
        'CAUSES',
        'AFFECTS',
        'REGULATES',
        'FUNDS',
        'OPPOSES',
        'MITIGATES',
        'REPORTS_ON',
        'LOCATED_IN',
        'MEMBER_OF'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- ENTITIES — named actors, concepts, and objects extracted from articles
-- =============================================================================
CREATE TABLE IF NOT EXISTS entities (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identification
    entity_name VARCHAR(500) NOT NULL,                          -- as-extracted surface form
    entity_type entity_type_enum NOT NULL,                      -- classification
    canonical_name VARCHAR(500),                                -- de-duplicated canonical form

    -- Descriptive fields
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,                         -- wikidata_id, aliases, urls, etc.

    -- Semantic vector for similarity search (matches article embedding dimensions)
    embedding vector(1536),

    -- Bookkeeping
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    article_count INT NOT NULL DEFAULT 1,                       -- incremented on each new mention

    -- De-duplication constraint: one canonical name per type
    CONSTRAINT uq_entity_canonical UNIQUE (canonical_name, entity_type)
);

-- Fast lookups by type (e.g., "all POLICY entities")
CREATE INDEX IF NOT EXISTS idx_entities_type
    ON entities (entity_type);

-- Full-text search on entity name
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm
    ON entities USING GIN (entity_name gin_trgm_ops);

-- Nearest-neighbor search on embeddings (requires pgvector ivfflat or hnsw)
-- Using HNSW for better recall; falls back gracefully if pgvector < 0.5.0
CREATE INDEX IF NOT EXISTS idx_entities_embedding
    ON entities USING hnsw (embedding vector_cosine_ops);

-- Frequency ranking
CREATE INDEX IF NOT EXISTS idx_entities_article_count
    ON entities (article_count DESC);

-- =============================================================================
-- ENTITY_RELATIONSHIPS — directed edges in the knowledge graph
-- =============================================================================
CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Edge endpoints
    source_entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,

    -- Edge label
    relationship_type relationship_type_enum NOT NULL,

    -- Scores
    strength FLOAT NOT NULL DEFAULT 0.5 CHECK (strength >= 0.0 AND strength <= 1.0),
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- Provenance: which article surfaced this relationship?
    article_id UUID REFERENCES articles(article_id) ON DELETE SET NULL,
    evidence_text TEXT,                                         -- supporting excerpt

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Outgoing edges from a source entity
CREATE INDEX IF NOT EXISTS idx_entity_rel_source
    ON entity_relationships (source_entity_id, relationship_type);

-- Incoming edges to a target entity
CREATE INDEX IF NOT EXISTS idx_entity_rel_target
    ON entity_relationships (target_entity_id, relationship_type);

-- All relationships sourced from a given article
CREATE INDEX IF NOT EXISTS idx_entity_rel_article
    ON entity_relationships (article_id)
    WHERE article_id IS NOT NULL;

-- Composite: find specific edge between two entities
CREATE INDEX IF NOT EXISTS idx_entity_rel_pair
    ON entity_relationships (source_entity_id, target_entity_id, relationship_type);

-- =============================================================================
-- ARTICLE_ENTITIES — many-to-many link between articles and entities
-- =============================================================================
CREATE TABLE IF NOT EXISTS article_entities (
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,

    -- Mention metrics
    mention_count INT NOT NULL DEFAULT 1,
    salience FLOAT NOT NULL DEFAULT 0.5 CHECK (salience >= 0.0 AND salience <= 1.0),
    first_mention_offset INT,                                   -- character offset in extracted_text

    PRIMARY KEY (article_id, entity_id)
);

-- "Which entities appear in article X?" (already covered by PK)
-- "Which articles mention entity Y?"
CREATE INDEX IF NOT EXISTS idx_article_entities_entity
    ON article_entities (entity_id, salience DESC);

-- =============================================================================
-- ENABLE TRIGRAM EXTENSION (needed for entity name search)
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$ BEGIN RAISE NOTICE 'Migration 013 applied successfully — knowledge graph tables created.'; END $$;

COMMIT;
