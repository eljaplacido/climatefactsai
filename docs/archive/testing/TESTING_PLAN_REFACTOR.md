# Testing Plan (Redis/Celery/LangGraph/Remotion)

## Unit
- Celery task payload/schema validation.
- Compliance gate: robots/noai parsing, skip logic.
- LangGraph nodes: teaser prompt, trust scoring, HITL interrupt/resume.
- Content repository serialization tests (`tests/unit/domains/test_content_repository.py`) to ensure `/api/v2` exposes trust, CTA, and compliance fields.

## Integration
- Ingestion → Celery → LangGraph → DB persistence.
- Video task → Remotion trigger → status update → DB.
- API /api/v2 returns trust, CTA, video fields.

## E2E
- Flow: ingest article → teaser summary → HITL route (low trust) → approve → publish → video preview available → frontend shows trust badge + CTA + video.
- Verify summaries remain non-substitutive (no full outcomes).

## Observability
- Metrics for task durations, retries, external API errors, render cost/time.
- Rate limits and circuit breakers on LLM/TTS/Pexels calls.

## Celery Workflow Smoke Test
1. Start Redis + Celery worker locally:
   ```bash
   celery -A app.core.celery_app worker -l info
   ```
2. Trigger the admin workflow:
   ```bash
   curl -X POST http://localhost:5200/api/admin/trigger-workflow \
     -H "Content-Type: application/json" \
     -d '{"country": "FI", "max_articles": 2}'
   ```
3. Monitor worker output for task chaining (ingestion → verify → summary → video → publish).
4. Verify `/api/v2/articles` shows updated trust/video fields for processed articles.

