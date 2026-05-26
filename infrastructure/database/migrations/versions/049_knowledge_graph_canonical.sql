-- @notolerate
-- Migration 049: knowledge graph — canonical promotion of legacy mig 013.
--
-- KG-Robustness-Audit-2026-05-27 §2 Phase 1: the knowledge_graph schema
-- (entities + entity_relationships + article_entities) was defined in
-- `migrations/versions/013_knowledge_graph.sql` but that legacy path is
-- NOT the tree Cloud Build runs (`scripts/run_migrations.py` walks
-- `infrastructure/database/migrations/versions/` only). End2End audit
-- found `/api/articles/{id}/kg` returning 500 in prod because the
-- relations don't exist there.
--
-- This migration promotes the schema into the canonical tree, idempotently
-- (CREATE IF NOT EXISTS everywhere). Two additions vs mig 013:
--   1. canonical_entities table — the EntityMention / CanonicalEntity
--      split Semanticgraphlayerimprovements.md flags as the #1 fix. The
--      legacy `entities` table is kept as the mention layer; new
--      canonical_entities owns dedup'd identity + Wikidata QIDs.
--   2. entity_canonical_id FK on entities so existing rows can be linked
--      to their canonical identity by the NER worker.
--
-- The NER worker (Celery task added in this commit) populates entities +
-- article_entities. The /api/admin/scheduler/extract-entities admin
-- endpoint triggers a batch; cn-ner-extract cron fires every hour.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- ENUMs (idempotent)
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
-- canonical_entities — the dedup'd identity layer
-- =============================================================================

CREATE TABLE IF NOT EXISTS canonical_entities (
    canonical_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(500) NOT NULL,
    entity_type     entity_type_enum NOT NULL,
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    wikidata_qid    VARCHAR(64),
    wikipedia_url   TEXT,
    country_code    CHAR(2),
    confidence      NUMERIC(3,2) NOT NULL DEFAULT 0.50
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    description     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_canonical_wikidata UNIQUE (wikidata_qid)
);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_name_trgm
    ON canonical_entities USING GIN (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_aliases_trgm
    ON canonical_entities USING GIN (aliases);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_type
    ON canonical_entities (entity_type);


-- =============================================================================
-- entities — surface-form mentions (one row per surface form)
-- =============================================================================

CREATE TABLE IF NOT EXISTS entities (
    entity_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name    VARCHAR(500) NOT NULL,
    entity_type    entity_type_enum NOT NULL,
    canonical_name VARCHAR(500),
    canonical_id   UUID REFERENCES canonical_entities(canonical_id) ON DELETE SET NULL,
    description    TEXT,
    metadata       JSONB DEFAULT '{}'::jsonb,
    embedding      vector(1536),
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    article_count  INT NOT NULL DEFAULT 1,

    CONSTRAINT uq_entity_canonical_name_type UNIQUE (canonical_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_type
    ON entities (entity_type);

CREATE INDEX IF NOT EXISTS idx_entities_name_trgm
    ON entities USING GIN (entity_name gin_trgm_ops);

-- HNSW embedding index (mig 019 already enabled the extension); guarded
-- by a function check so this migration runs whether pgvector >= 0.5.0
-- or earlier.
DO $$ BEGIN
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_entities_embedding
             ON entities USING hnsw (embedding vector_cosine_ops)';
EXCEPTION WHEN feature_not_supported OR undefined_object THEN
    -- pgvector too old for hnsw; fall back to ivfflat at deploy if needed.
    NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_entities_article_count
    ON entities (article_count DESC);

CREATE INDEX IF NOT EXISTS idx_entities_canonical
    ON entities (canonical_id) WHERE canonical_id IS NOT NULL;


-- =============================================================================
-- entity_relationships — directed edges
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    target_entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relationship_type  relationship_type_enum NOT NULL,
    strength           FLOAT NOT NULL DEFAULT 0.5
                       CHECK (strength >= 0.0 AND strength <= 1.0),
    confidence         FLOAT NOT NULL DEFAULT 0.5
                       CHECK (confidence >= 0.0 AND confidence <= 1.0),
    article_id         UUID REFERENCES articles(article_id) ON DELETE SET NULL,
    evidence_text      TEXT,
    valid_from         TIMESTAMPTZ,   -- Phase 1 addition: validity windows
    valid_to           TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_rel_source
    ON entity_relationships (source_entity_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_entity_rel_target
    ON entity_relationships (target_entity_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_entity_rel_article
    ON entity_relationships (article_id)
    WHERE article_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entity_rel_pair
    ON entity_relationships (source_entity_id, target_entity_id, relationship_type);


-- =============================================================================
-- article_entities — many-to-many mentions per article
-- =============================================================================

CREATE TABLE IF NOT EXISTS article_entities (
    article_id            UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    entity_id             UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    mention_count         INT NOT NULL DEFAULT 1,
    salience              FLOAT NOT NULL DEFAULT 0.5
                          CHECK (salience >= 0.0 AND salience <= 1.0),
    first_mention_offset  INT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (article_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_article_entities_entity
    ON article_entities (entity_id, salience DESC);

-- Bidirectional join for "which articles mention canonical X?" via
-- canonical_id without a 3-table walk every time.
CREATE INDEX IF NOT EXISTS idx_article_entities_article
    ON article_entities (article_id, salience DESC);


-- =============================================================================
-- claim_entity_mentions — claims become first-class participants in the KG
-- =============================================================================

CREATE TABLE IF NOT EXISTS claim_entity_mentions (
    claim_id    UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    salience    FLOAT NOT NULL DEFAULT 0.5
                CHECK (salience >= 0.0 AND salience <= 1.0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (claim_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_entity_mentions_entity
    ON claim_entity_mentions (entity_id, salience DESC);


COMMENT ON TABLE canonical_entities IS
'Dedup''d identity layer for the KG. One row per real-world entity
(linked to a Wikidata QID when known). The legacy `entities` table is
kept as the surface-mention layer; populate canonical_id by NER + an
entity-resolution worker. See KG-Robustness-Audit-2026-05-27.md §2.';

COMMENT ON TABLE entities IS
'Surface-form mentions extracted by NER. canonical_id links a surface
form back to its canonical_entities identity once entity resolution
runs. Embedded vector(1536) supports nearest-neighbor entity matching
during the resolution step.';

COMMENT ON TABLE claim_entity_mentions IS
'Per-claim entity links. Allows claim-first retrieval to anchor on
entities without moving claims out of the claims table. Phase 2 (Neo4j
plane) will project these into property-graph edges.';


DO $$
DECLARE
    n_can INTEGER;
    n_ent INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_can FROM canonical_entities;
    SELECT COUNT(*) INTO n_ent FROM entities;
    RAISE NOTICE 'Migration 049: canonical_entities has % rows, entities has %', n_can, n_ent;
END
$$;
