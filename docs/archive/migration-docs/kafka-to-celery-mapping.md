# Kafka to Celery Task Mapping

**Status:** Phase 1 - Task Mapping
**Date:** 2025-12-12
**Related:** migration-plan.md, kafka-inventory.md

## Overview

This document maps the existing Kafka topics and message flows to Celery tasks in the new modular monolith architecture.

## Workflow Mapping

### Old Workflow (Kafka Topics)
```
discovery_queue → fact_checking_queue → content_creation_queue → video_queue → publication_queue
```

### New Workflow (Celery Tasks)
```
ingestion.discover_articles → processing.verify_claims → processing.create_summary → video.render_video → publication.publish_article
```

## Topic to Task Mapping

### 1. discovery_queue → ingestion.discover_articles

**Old Kafka Flow:**
- Producer: Ingestion service
- Consumer: Fact-checking service
- Schema: `discovery_to_factcheck.json`
- Payload: taskId, articleId, sourceArticle, claims

**New Celery Task:**
```python
@app.task(queue="ingestion_queue", bind=True, max_retries=3)
def discover_articles(
    self,
    country: str,
    max_articles: int = 50
) -> dict:
    """
    Discover and ingest climate news articles.

    Replaces: discovery_queue Kafka topic

    Args:
        country: Country code (e.g., "FI")
        max_articles: Maximum articles to discover

    Returns:
        {
            "task_id": "task-20251212-001",
            "articles": [
                {
                    "article_id": "abc123",
                    "url": "https://...",
                    "title": "...",
                    "extracted_text": "...",
                    "claims": [...]
                }
            ],
            "metadata": {...}
        }

    Chains to: processing.verify_claims
    """
```

**Migration Notes:**
- Check robots.txt/noai compliance BEFORE ingestion
- Store compliance decision in DB
- Extract claims during ingestion
- Chain to verify_claims task

---

### 2. fact_checking_queue → processing.verify_claims

**Old Kafka Flow:**
- Producer: Ingestion service
- Consumer: Verification service
- Schema: `factcheck_to_creation.json`
- Payload: taskId, articleId, verifiedArticle, verifiedClaims

**New Celery Task:**
```python
@app.task(queue="processing_queue", bind=True, max_retries=3)
def verify_claims(
    self,
    article_id: str,
    claims: list[dict]
) -> dict:
    """
    Verify claims using external APIs (ClimateCheck, NOAA, NASA).

    Replaces: fact_checking_queue Kafka topic

    Args:
        article_id: Article identifier
        claims: List of claims to verify

    Returns:
        {
            "article_id": "abc123",
            "verified_claims": [
                {
                    "claim_id": "claim-1",
                    "verification_status": "VERIFIED",
                    "confidence": 0.95,
                    "evidence": [...]
                }
            ],
            "overall_credibility": "HIGH",
            "trust_score": 85
        }

    Chains to: processing.create_summary
    """
```

**Migration Notes:**
- Use circuit breakers for external API calls
- Rate limit API requests
- Cache verification results
- Calculate trust_score for HITL routing

---

### 3. content_creation_queue → processing.create_summary (LangGraph)

**Old Kafka Flow:**
- Producer: Verification service
- Consumer: Content creation service
- Schema: `creation_to_publication.json`
- Payload: summaryMarkdown, videoUrl, metadata, hitlReview

**New Celery Task:**
```python
@app.task(queue="processing_queue", bind=True, max_retries=3)
def create_summary(
    self,
    article_id: str,
    verified_article: dict,
    verified_claims: list[dict]
) -> dict:
    """
    Create non-substitutive summary using LangGraph with HITL pauses.

    Replaces: content_creation_queue Kafka topic

    Uses LangGraph for:
    - Teaser prompt (3-sentence non-substitutive summary)
    - Trust scoring node
    - HITL interrupt for low trust scores
    - Checkpoint persistence

    Args:
        article_id: Article identifier
        verified_article: Verified article data
        verified_claims: List of verified claims

    Returns:
        {
            "article_id": "abc123",
            "summary_markdown": "...",
            "summary_type": "AI_GENERATED",
            "trust_score": 85,
            "hitl_status": "PENDING" | "APPROVED" | "BYPASSED",
            "provenance": {
                "prompt_version": "v1.0",
                "model": "claude-3.5-sonnet",
                "reviewer": "user@example.com"  # If HITL
            }
        }

    Chains to: video.render_video (if approved)
    """
```

**Migration Notes:**
- Implement LangGraph state machine
- Add HITL pause/resume mechanism
- Store checkpoints in PostgreSQL
- Enforce non-substitutive prompt constraints
- Store provenance data

---

### 4. video_queue → video.render_video (Remotion)

**Old Kafka Flow:**
- Producer: Content creation service
- Consumer: Video production service
- Payload: summary, assets, metadata

**New Celery Task:**
```python
@app.task(queue="video_queue", bind=True, max_retries=3)
def render_video(
    self,
    article_id: str,
    summary_text: str,
    metadata: dict
) -> dict:
    """
    Render programmatic video using Remotion Lambda.

    Replaces: video_queue Kafka topic

    Workflow:
    1. Generate TTS audio (ElevenLabs)
    2. Fetch stock media (Pexels)
    3. Trigger Remotion Lambda render
    4. Upload to S3
    5. Store video_url in DB

    Args:
        article_id: Article identifier
        summary_text: Summary text for TTS
        metadata: Video metadata (location, tags)

    Returns:
        {
            "article_id": "abc123",
            "video_url": "https://s3.../video.mp4",
            "duration_seconds": 45,
            "cost_cents": 12,
            "render_time_seconds": 120
        }

    Chains to: publication.publish_article
    """
```

**Migration Notes:**
- Use Remotion Lambda for rendering
- Implement TTS with ElevenLabs
- Fetch assets from Pexels
- Store render costs/metrics
- Handle render failures gracefully

---

### 5. publication_queue → publication.publish_article

**Old Kafka Flow:**
- Producer: Content creation service
- Consumer: API gateway/database service
- Payload: Final article with all metadata

**New Celery Task:**
```python
@app.task(queue="publication_queue", bind=True, max_retries=3)
def publish_article(
    self,
    article_id: str,
    summary_markdown: str,
    video_url: Optional[str],
    metadata: dict
) -> dict:
    """
    Publish article to database and trigger API updates.

    Replaces: publication_queue Kafka topic

    Workflow:
    1. Store article in DB (articles table)
    2. Update trust scores
    3. Update nutrition labels
    4. Trigger cache invalidation
    5. Send notifications (if enabled)

    Args:
        article_id: Article identifier
        summary_markdown: Final summary
        video_url: Video URL (if rendered)
        metadata: Publication metadata

    Returns:
        {
            "article_id": "abc123",
            "published_at": "2025-12-12T10:00:00Z",
            "url": "https://climatenews.com/articles/abc123",
            "trust_score": 85,
            "hitl_reviewed": True
        }
    """
```

**Migration Notes:**
- Update articles table with trust/provenance data
- Invalidate frontend cache
- Log publication event
- Update statistics

---

## Orchestration Topics → Celery Chains

### orchestrator_commands → Celery Canvas (chain/group)

**Old Kafka Flow:**
- Orchestrator sends commands to agents via `orchestrator_commands` topic
- Agents respond via `orchestrator_responses` topic

**New Celery Approach:**
```python
from celery import chain, group

# Sequential workflow (replaces command/response flow)
workflow = chain(
    discover_articles.s(country="FI", max_articles=50),
    verify_claims.s(),
    create_summary.s(),
    render_video.s(),
    publish_article.s()
)

# Execute workflow
result = workflow.apply_async()

# Track progress
result.get()  # Blocks until complete
```

**Canvas Patterns:**
- `chain`: Sequential tasks (a → b → c)
- `group`: Parallel tasks ([a, b, c])
- `chord`: Parallel then callback (group → callback)

---

### workflow_events → Celery Task Events

**Old Kafka Flow:**
- State changes published to `workflow_events`
- Monitoring services consume events

**New Celery Approach:**
- Built-in task events: `task-sent`, `task-started`, `task-succeeded`, `task-failed`, `task-retried`
- Consume events via Celery Flower or custom event receivers
- Store state in Redis/PostgreSQL

```python
from celery import signals

@signals.task_success.connect
def task_success_handler(sender=None, **kwargs):
    """Log successful task completion."""
    logger.info(f"Task {sender.name} succeeded", extra=kwargs)

@signals.task_failure.connect
def task_failure_handler(sender=None, **kwargs):
    """Log task failure."""
    logger.error(f"Task {sender.name} failed", extra=kwargs)
```

---

## Task Queue Routing

```python
CELERY_TASK_ROUTES = {
    "app.tasks.ingestion.*": {"queue": "ingestion_queue"},
    "app.tasks.processing.*": {"queue": "processing_queue"},
    "app.tasks.video.*": {"queue": "video_queue"},
    "app.tasks.publication.*": {"queue": "publication_queue"},
}
```

---

## Schema Migration: JSON → Pydantic

### Old: JSON Schema Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "taskId": {"type": "string"},
    "articleId": {"type": "string"}
  },
  "required": ["taskId", "articleId"]
}
```

### New: Pydantic Models

```python
from pydantic import BaseModel, Field

class ArticleDiscoveryPayload(BaseModel):
    task_id: str = Field(..., pattern=r"^task-\d{8}-\d{3}$")
    article_id: str
    source_article: SourceArticle
    claims: list[Claim]
    metadata: dict
```

**Benefits:**
- Type safety
- Automatic validation
- Better IDE support
- Easier testing

---

## Retry Strategy

```python
@app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=300,  # Max 5 minutes
    retry_jitter=True  # Add randomness
)
def example_task(self):
    pass
```

---

## Error Handling

### Old: Manual error handling in Kafka consumer

```python
try:
    process_message(payload)
    consumer.commit()  # Manual offset commit
except Exception as e:
    logger.error(f"Processing failed: {e}")
    # Don't commit offset, message will be retried
```

### New: Automatic retries with Celery

```python
@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def process_task(self, payload):
    # Celery handles retries automatically
    # On final failure, task goes to dead letter queue
    pass
```

---

## Monitoring & Observability

### Old: Custom Kafka monitoring

- Consumer lag monitoring
- Partition rebalancing alerts
- Message rate tracking

### New: Celery/Redis monitoring

- **Flower**: Web-based monitoring UI
  - Real-time task monitoring
  - Worker status
  - Task history
  - Rate graphs

- **Celery Events**: Task lifecycle events
  - task-sent, task-started, task-succeeded
  - task-failed, task-retried, task-revoked

- **Redis metrics**: Queue depth, memory usage

---

## Testing Migration

### Old: Kafka integration tests

```python
def test_article_workflow():
    producer.send("discovery_queue", payload)
    # Wait for consumer to process
    time.sleep(5)
    # Check result in database
    assert article_exists_in_db()
```

### New: Celery eager mode tests

```python
@pytest.fixture(autouse=True)
def celery_eager():
    app.conf.task_always_eager = True  # Synchronous execution

def test_article_workflow():
    result = discover_articles.apply(args=["FI", 50])
    assert result.successful()
    assert result.get()["articles"]
```

---

## Rollback Strategy

During phases 1-5:

1. **Parallel Operation**: Both Kafka and Celery run simultaneously
2. **Optional Shim**: Kafka → Celery bridge for gradual migration
3. **Feature Flags**: Switch between Kafka/Celery per endpoint
4. **Validation**: Compare Kafka vs Celery outputs

Rollback procedure:
```python
# Feature flag in config
USE_CELERY = os.getenv("USE_CELERY_TASKS", "false").lower() == "true"

if USE_CELERY:
    discover_articles.delay(country, max_articles)
else:
    kafka_client.produce("discovery_queue", payload)
```

---

## Next Steps

1. ✅ Create Celery configuration
2. ✅ Create task mapping document
3. **Create task modules** (ingestion.py, processing.py, video.py, publication.py)
4. **Implement Pydantic schemas** for task payloads
5. **Add LangGraph integration** to processing tasks
6. **Test locally** with Redis + Celery worker
7. **Update Docker Compose** with Celery services

---

**Related Documents:**
- `kafka-inventory.md` - Original Kafka infrastructure
- `environment-config.md` - Redis/Celery configuration
- `migration-plan.md` - Overall migration phases
