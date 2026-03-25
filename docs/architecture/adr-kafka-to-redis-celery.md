# ADR: Sunset Kafka → Redis/Celery Modular Monolith

## Context
- Current: Kafka-centric multi-services (`src/backend/services/*`, `shared/kafka_client.py`), schemas in `/schemas`.
- Target (New_plan.md): Modular monolith (FastAPI), Redis + Celery for async tasks, LangGraph for stateful/HITL, Remotion for video.
- MVP workloads are discrete jobs (ingest → summarize → render), not continuous streams.

## Decision
- Deprecate Kafka for MVP. Introduce Redis as broker/cache and Celery workers for async jobs.
- Consolidate services into a single FastAPI app (`src/backend/app`) with domain modules: ingestion, processing (LangGraph), video, api_gateway.
- Keep a short-lived Kafka shim only for transition/testing; no new Kafka features.

## Rationale
- Lower ops overhead, faster iteration, simpler developer experience.
- Aligns with compliance/HITL (LangGraph pauses) and trust-first UX.
- Matches programmatic video path (Remotion) without streaming requirements.

## Consequences
- Rewrite message contracts as Celery task payloads.
- Update tests/ops scripts to Redis/Celery; retire Kafka CI paths after cutover.
- Add Redis/Celery config, health checks, metrics, and rate limits.

