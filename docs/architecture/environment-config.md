# Environment Configuration for Redis/Celery Migration

**Status:** Phase 0 - Environment Definition
**Date:** 2025-12-12
**Related:** migration-plan.md, adr-kafka-to-redis-celery.md

## Overview

This document defines the environment variables and configuration needed for the Redis/Celery/LangGraph/Remotion architecture migration.

## New Environment Variables

### Redis Configuration

```env
# Redis connection for Celery broker and cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Redis URL (alternative to individual settings)
REDIS_URL=redis://localhost:6379/0

# Redis configuration for Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json,pickle
CELERY_TIMEZONE=UTC
CELERY_ENABLE_UTC=True

# Redis connection pool settings
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=True
```

### Celery Worker Configuration

```env
# Celery worker settings
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_PREFETCH_MULTIPLIER=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_DISABLE_RATE_LIMITS=False
CELERY_TASK_ACKS_LATE=True
CELERY_TASK_REJECT_ON_WORKER_LOST=True

# Task execution settings
CELERY_TASK_TIME_LIMIT=3600  # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT=3300  # 55 minutes soft limit
CELERY_TASK_DEFAULT_RATE_LIMIT=100/m  # 100 tasks per minute

# Task queue names
CELERY_QUEUE_INGESTION=ingestion_queue
CELERY_QUEUE_PROCESSING=processing_queue
CELERY_QUEUE_VIDEO=video_queue
CELERY_QUEUE_PUBLICATION=publication_queue
CELERY_QUEUE_PRIORITY=priority_queue

# Task routing
CELERY_TASK_ROUTES={
    'app.tasks.ingestion.*': {'queue': 'ingestion_queue'},
    'app.tasks.processing.*': {'queue': 'processing_queue'},
    'app.tasks.video.*': {'queue': 'video_queue'},
    'app.tasks.publication.*': {'queue': 'publication_queue'}
}
```

### LangGraph Configuration

```env
# LangGraph settings
LANGGRAPH_CHECKPOINT_BACKEND=postgres
LANGGRAPH_CHECKPOINT_TABLE=langgraph_checkpoints
LANGGRAPH_CHECKPOINT_NAMESPACE=climatenews

# LangGraph HITL settings
LANGGRAPH_HITL_ENABLED=True
LANGGRAPH_HITL_TRUST_THRESHOLD=0.7
LANGGRAPH_HITL_KEYWORDS=nuclear,war,politics,controversial

# LangGraph state persistence
LANGGRAPH_STATE_TTL_HOURS=72
LANGGRAPH_MAX_ITERATIONS=10
LANGGRAPH_RECURSION_LIMIT=25
```

### Remotion Configuration

```env
# Remotion Lambda settings
REMOTION_LAMBDA_ENABLED=True
REMOTION_LAMBDA_REGION=us-east-1
REMOTION_LAMBDA_FUNCTION_NAME=climatenews-video-renderer
REMOTION_LAMBDA_TIMEOUT=900  # 15 minutes
REMOTION_LAMBDA_MEMORY=3008  # MB

# Remotion rendering settings
REMOTION_COMPOSITION_NAME=ClimateNewsVideo
REMOTION_FRAME_RATE=30
REMOTION_VIDEO_WIDTH=1920
REMOTION_VIDEO_HEIGHT=1080
REMOTION_VIDEO_CODEC=h264
REMOTION_VIDEO_BITRATE=5M

# Remotion asset storage
REMOTION_ASSETS_BUCKET=climatenews-video-assets
REMOTION_OUTPUT_BUCKET=climatenews-video-outputs
REMOTION_S3_REGION=us-east-1

# Remotion templates directory
REMOTION_TEMPLATES_DIR=src/video_templates
```

### Text-to-Speech (TTS) Configuration

```env
# ElevenLabs TTS API
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Default voice
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_STABILITY=0.5
ELEVENLABS_SIMILARITY_BOOST=0.75
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128

# TTS fallback providers
TTS_PROVIDER=elevenlabs  # or aws_polly, google_tts
AWS_POLLY_VOICE_ID=Joanna
GOOGLE_TTS_VOICE_NAME=en-US-Neural2-F
```

### Media Asset APIs

```env
# Pexels API for stock videos/images
PEXELS_API_KEY=your-pexels-api-key
PEXELS_VIDEOS_PER_PAGE=15
PEXELS_DEFAULT_ORIENTATION=landscape
PEXELS_SIZE=large

# Unsplash API (alternative)
UNSPLASH_ACCESS_KEY=your-unsplash-access-key
UNSPLASH_SECRET_KEY=your-unsplash-secret-key

# Asset caching
MEDIA_CACHE_DIR=/tmp/climatenews/media_cache
MEDIA_CACHE_TTL_HOURS=24
```

### Database Extensions for Trust Schema

```env
# Postgres extensions and features
POSTGRES_ENABLE_JSONB=True
POSTGRES_ENABLE_VECTOR=False  # For future semantic search
POSTGRES_MAX_CONNECTIONS=100
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10

# Migration settings
DATABASE_AUTO_MIGRATE=False
DATABASE_MIGRATION_TIMEOUT=300
```

### Compliance & Trust Configuration

```env
# Robots.txt/noai compliance
COMPLIANCE_CHECK_ROBOTS_TXT=True
COMPLIANCE_CHECK_NOAI=True
COMPLIANCE_RESPECT_TDM_OPT_OUT=True
COMPLIANCE_LOG_SKIPS=True
COMPLIANCE_ALLOW_LIST=bbc.com,reuters.com,apnews.com
COMPLIANCE_DENY_LIST=

# Trust scoring
TRUST_SCORE_MIN=0
TRUST_SCORE_MAX=100
TRUST_SCORE_DEFAULT=50
TRUST_SCORE_THRESHOLD_LOW=40
TRUST_SCORE_THRESHOLD_HIGH=80

# Nutrition label defaults
NUTRITION_LABEL_ENABLED=True
NUTRITION_LABEL_SHOW_SOURCES=True
NUTRITION_LABEL_SHOW_VERIFICATION=True
```

### Rate Limiting & Circuit Breakers

```env
# API rate limits (per minute)
RATE_LIMIT_LLM_CALLS=60
RATE_LIMIT_TTS_CALLS=30
RATE_LIMIT_PEXELS_CALLS=50
RATE_LIMIT_ELEVENLABS_CALLS=30

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60
CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT=30

# Retry configuration
TASK_RETRY_MAX_ATTEMPTS=3
TASK_RETRY_BACKOFF_BASE=2  # exponential backoff: 2^retry_count seconds
TASK_RETRY_BACKOFF_MAX=300  # max 5 minutes
```

### Observability & Monitoring

```env
# Metrics collection
METRICS_ENABLED=True
METRICS_EXPORT_INTERVAL=60
METRICS_BACKEND=prometheus  # or datadog, cloudwatch

# Celery monitoring
CELERY_SEND_TASK_EVENTS=True
CELERY_SEND_TASK_SENT_EVENT=True
CELERY_TRACK_STARTED=True

# Logging
LOG_CELERY_TASKS=True
LOG_LANGGRAPH_STATE=True
LOG_REMOTION_RENDERS=True
LOG_COMPLIANCE_SKIPS=True
LOG_TRUST_SCORES=True
```

## Migration from Kafka Configuration

### Variables to Deprecate
```env
# These will be removed after Phase 6
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SCHEMA_REGISTRY_URL=http://localhost:8081
KAFKA_CONSUMER_GROUP_PREFIX=climatenews
```

### Transition Period
During phases 1-5, both Kafka and Redis/Celery configurations will coexist:
- Kafka variables remain active for rollback capability
- New Celery tasks will only use Redis/Celery
- Optional Kafka shim can bridge during parallel validation

## Docker Compose Updates

### New Services Required
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    command: redis-server --appendonly yes

  celery_worker:
    build: ./src/backend
    command: celery -A app.core.celery worker --loglevel=info --concurrency=4
    environment:
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      - redis
      - postgres
    volumes:
      - ./src/backend:/app

  celery_beat:
    build: ./src/backend
    command: celery -A app.core.celery beat --loglevel=info
    environment:
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      - redis
      - postgres

  flower:
    build: ./src/backend
    command: celery -A app.core.celery flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      - redis
      - celery_worker

volumes:
  redis_data:
```

## Configuration Files Structure

```
src/backend/app/core/
├── celery.py          # Celery app configuration
├── celery_config.py   # Celery settings class
├── redis_client.py    # Redis connection manager
└── config.py          # Updated with new settings

src/backend/app/tasks/
├── __init__.py
├── ingestion.py       # Ingestion tasks
├── processing.py      # LangGraph processing tasks
├── video.py           # Remotion video tasks
└── publication.py     # Publication tasks
```

## Validation Checklist

- [ ] All Redis/Celery environment variables defined
- [ ] LangGraph configuration complete
- [ ] Remotion Lambda settings configured
- [ ] TTS provider credentials added
- [ ] Pexels API key obtained
- [ ] Compliance settings defined
- [ ] Rate limits and circuit breakers configured
- [ ] Docker Compose updated with new services
- [ ] .env.example updated with all new variables
- [ ] Secrets manager integration for production

## Next Steps

1. Update `.env.example` with all new variables
2. Create `src/backend/app/core/celery.py`
3. Implement Redis client wrapper
4. Define Celery task structure
5. Test local Redis/Celery setup

---

**Related Documents:**
- `migration-plan.md` - Phase 1 implementation details
- `adr-kafka-to-redis-celery.md` - Architecture decision record
- `.env.example` - Environment variable template
