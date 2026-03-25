# Refactor Alignment to New_plan.md

## Current vs Target
- Current: FastAPI + Kafka microservices, InVideo video path, Next.js 14 frontend.
- Target: Modular monolith (FastAPI), Redis/Celery queues, LangGraph with HITL, Remotion Lambda, trust-first UX, compliance gate.

## Scope (from New_plan.md)
1) Architecture pivot to monolith
2) Queue migration to Redis/Celery
3) Compliance gate (robots.txt / noai)
4) LangGraph teaser + HITL
5) Trust data model (publishers, nutrition_label, provenance)
6) API alignment `/api/v2`
7) Frontend trust UX + video previews
8) Remotion pipeline
9) Observability/rate limits
10) Tests/docs refresh

## Non-Goals
- No new Kafka work.
- No generative avatar video (programmatic Remotion only).

