# Migration Plan

## Phase 0: Readiness
- Inventory Kafka topics/schemas; freeze Kafka feature work.
- Define envs for Redis/Celery, Postgres, LangGraph, Remotion, TTS.

## Phase 1: Monolith & Queue Layer
- Add Celery app/config under `src/backend/app/core/`.
- Map tasks: ingestion → summary (LangGraph) → video.
- Optional Kafka shim for rollback (time-boxed).

## Phase 2: Compliance & Trust
- Add robots.txt/noai gate; log skips.
- Add trust schema: publishers (tdm_opt_out, trust_score, nutrition_label), articles provenance/CTA flags.
- Expose CTA-to-source in API.

## Phase 3: LangGraph + HITL
- Non-substitutive teaser prompt; trust scoring node; HITL pause/resume; checkpoint persistence.

## Phase 4: Video (Remotion)
- Add `src/video_templates/` with parameterized Remotion compositions; Lambda trigger worker; TTS + Pexels asset fetch.

## Phase 5: Frontend Trust UX
- Trust badges, nutrition labels, CTA to source, HITL status, video cards; enforce teaser copy.

## Phase 6: Tests & Observability
- Replace Kafka tests with Redis/Celery/LangGraph coverage.
- Metrics, rate limits, circuit breakers for external APIs (LLM/TTS/Pexels).

