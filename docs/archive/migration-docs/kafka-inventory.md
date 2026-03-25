# Kafka Infrastructure Inventory (Legacy)

**Status:** DEPRECATED - Being replaced by Redis/Celery
**Date:** 2025-12-12
**Phase:** Phase 0 - Readiness

## Overview

This document inventories the existing Kafka infrastructure before migration to Redis/Celery. After migration completion, Kafka components will be removed.

## Kafka Topics

### Core Event Bus Topics

1. **discovery_queue**
   - Purpose: Ingestion agent output
   - Producer: Ingestion service
   - Consumer: Verification/fact-checking service
   - Schema: TBD (needs inspection)

2. **fact_checking_queue**
   - Purpose: Verification agent input
   - Producer: Ingestion service
   - Consumer: Fact-checking service
   - Schema: `fact_checking_input`
   - Payload structure: `{schemaVersion, taskId, articles, timestamp}`

3. **content_creation_queue**
   - Purpose: Content agent input
   - Producer: Verification service
   - Consumer: Content creation service
   - Schema: TBD

4. **video_queue**
   - Purpose: Video agent input
   - Producer: Content creation service
   - Consumer: Video production service
   - Schema: TBD

5. **publication_queue**
   - Purpose: Final publication events
   - Producer: Content creation service
   - Consumer: API gateway/database service
   - Schema: TBD

### Orchestration Topics

6. **orchestrator_commands**
   - Purpose: Orchestrator commands to agents
   - Producer: Orchestrator service
   - Consumers: All agent services
   - Schema: TBD

7. **orchestrator_responses**
   - Purpose: Agent responses to orchestrator
   - Producers: All agent services
   - Consumer: Orchestrator service
   - Schema: TBD

8. **workflow_events**
   - Purpose: State change notifications
   - Producers: All services
   - Consumers: Monitoring/observability services
   - Schema: TBD

## Kafka Implementation Files

### Core Files (Active)
- `src/backend/app/core/kafka.py` - FastAPI integration wrapper
- `src/backend/shared/kafka_client.py` - Full Kafka client implementation
  - Lines 1-657: Complete implementation with schema validation
  - Producer: Synchronous with `acks=all`, 3 retries
  - Consumer: Manual offset commits, batch processing (max 10 messages)

### Legacy Files (Archived)
- `archive/legacy_agents/agents/shared/kafka_client.py`
- `archive/legacy_agents/agents_backup_20251022/shared/kafka_client.py`

## JSON Schema Validation

### Schema Location
- Directory: `/schemas/*.json`
- Format: JSON Schema Draft 07

### Known Schemas

#### 1. discovery_to_factcheck.json (v1.0)
**Purpose:** Discovery → Fact-Checking handoff
**Required fields:** schemaVersion, taskId, articleId, sourceArticle, claims
**Key structures:**
- sourceArticle: url, title, publishedDate, extractedText, sourceCredibilityScore
- claims: claimId, claimText, context, claimType (factual_data, prediction, policy_statement, etc.)
- entities: NER-identified entities (PERSON, ORG, GPE, DATE, QUANTITY)

#### 2. factcheck_to_creation.json (v1.0)
**Purpose:** Fact-Checking → Content Creation handoff
**Required fields:** schemaVersion, taskId, articleId, verifiedArticle, verifiedClaims
**Key structures:**
- verifiedArticle: url, title, extractedText, overallCredibility (HIGH/MEDIUM/LOW/MIXED)
- verifiedClaims: claimId, verificationStatus (VERIFIED/UNVERIFIED/MISLEADING/LACKS_CONTEXT/FALSE), confidence (0-1), evidence
- evidence: sourceName, sourceUrl, dataPoint, retrievalTimestamp

#### 3. creation_to_publication.json (v2.1)
**Purpose:** Content Creation → Publication queue
**Required fields:** schemaVersion, taskId, summaryMarkdown, metadata
**Key structures:**
- summaryMarkdown: Final article content (500-10000 chars)
- videoUrl: URL to produced video (if ready)
- metadata.sourceArticles: Array of source articles with credibility scores
- metadata.qualityMetrics: contentRelevanceScore, semanticSimilarity, readabilityGradeLevel
- hitlReview: status (PENDING/APPROVED/REJECTED/REQUIRES_EDIT), reviewedBy, feedback, edits

#### 4. orchestrator_task.json (v1.0)
**Purpose:** Orchestrator task/workflow management
**Required fields:** taskId, workflowType, status, createdAt
**Workflow stages:**
- discovery: articlesFound, startedAt, completedAt
- factChecking: articlesProcessed, claimsVerified, apiCallsMade
- contentCreation: summaryWordCount, qualityScore
- videoProduction: videoUrl, videoDurationSeconds
- hitlReview: reviewedBy, reviewedAt
- publication: publishedAt, cmsContentId, publishedUrls
**Cost tracking:** LLM costs (Claude, GPT-4o), API costs (ClimateCheck, video, media)

## Environment Configuration

### Current Variables
```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SCHEMA_REGISTRY_URL=http://localhost:8081
```

### Settings Class
Location: `src/backend/shared/config.py`
- `KafkaSettings` class with bootstrap servers and consumer group prefix

## Consumer Groups

Format: `{KAFKA_CONSUMER_GROUP_PREFIX}_{agent_name}`

Example groups:
- `climatenews_ingestion_agent`
- `climatenews_verification_agent`
- `climatenews_content_creation_agent`

## Performance Characteristics

### Producer
- **Delivery guarantee:** At-least-once (acks=all)
- **Ordering:** Guaranteed per partition (max_in_flight=1)
- **Retries:** 3 automatic retries
- **Serialization:** JSON

### Consumer
- **Commit strategy:** Manual offset commits
- **Batch size:** Max 10 messages per poll
- **Auto offset reset:** Earliest
- **Error handling:** Exponential backoff (5s sleep on error)

## Migration Strategy

### Phase Out Plan
1. ✅ **Inventory complete** (this document)
2. **Freeze features** - No new Kafka topics or schemas
3. **Optional shim** - Time-boxed Kafka compatibility layer
4. **Parallel run** - Redis/Celery alongside Kafka for validation
5. **Cutover** - Switch all services to Redis/Celery
6. **Deprecation** - Remove Kafka files and configuration
7. **Cleanup** - Archive Kafka Docker containers

### Rollback Strategy
If Redis/Celery migration fails:
1. Keep Kafka configuration intact during Phase 1-2
2. Maintain Kafka Docker services until Phase 6 complete
3. Document rollback procedure in migration plan

## Dependencies to Remove

### Python Packages
```txt
kafka-python==2.0.2  # KafkaProducer, KafkaConsumer
jsonschema==4.x      # May be needed for other validation
```

### Docker Services
```yaml
# From docker-compose.yml
services:
  kafka:
    image: confluentinc/cp-kafka:latest
    ports: 9092

  schema-registry:
    image: confluentinc/cp-schema-registry:latest
    ports: 8081
```

## Testing Artifacts to Update

### Test Files Using Kafka
- `tests/integration/test_kafka_messaging.py` (if exists)
- `tests/unit/test_kafka_client.py` (if exists)
- Any service tests that mock Kafka

### Mocks to Replace
- `KafkaProducer` mocks → Celery task mocks
- `KafkaConsumer` mocks → Celery worker mocks
- Schema validation mocks → Pydantic model validation

## Notes

- **Schema directory**: `/schemas/*.json` needs to be migrated to Pydantic models
- **Logging**: Kafka client uses structured logging with `LoggerMixin`
- **Error handling**: All Kafka errors logged with context (topic, task_id, offset)
- **Message keys**: Used for partition assignment and ordering

## Action Items

- [ ] Freeze Kafka feature development
- [ ] Document all schema files in `/schemas/`
- [ ] Map Kafka topics to Celery task names
- [ ] Plan Pydantic model migration for schemas
- [ ] Create Kafka → Redis/Celery mapping table
- [ ] Set up parallel validation environment

---

**Next Steps:** Proceed to Phase 1 - Celery setup and task mapping
