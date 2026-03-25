# Deployment (MVP)

This document describes a minimal, production‑oriented deployment for the Climate Intelligence MVP.

## Environments

- Dev: local via `docker-compose.yml`
- Staging/Prod: containerized services on a managed platform (ECS/EKS/GKE) with managed Postgres and Redis

## Required Services

- API Gateway: FastAPI (`api/`)
- Frontend: Next.js (`src/frontend`)
- PostgreSQL 16 (with pgvector)
- Redis 7
- Optional (Phase 2): Kafka, Schema Registry, Observability stack

## Configuration

- Copy `.env.example` to `.env` and set secrets:
  - Database, Redis, JWT, API keys (OpenAI/Anthropic/Perplexity), CORS
- Frontend consumes `NEXT_PUBLIC_API_URL` at build/runtime

## Local (Compose)

```
# From repo root
cp .env.example .env
# Adjust secrets and CORS_ORIGINS

# Build + start
docker-compose up -d --build

# Frontend → http://localhost:5300
# API → http://localhost:5200/docs
# Health → http://localhost:5200/healthz
```

## Production Notes

- Networking
  - Terminate TLS at a load balancer; forward to API/Frontend containers
  - Set `CORS_ORIGINS` precisely to your domains
- Database
  - Use managed Postgres with automated backups
  - Apply schema migrations on release; restrict direct access to app network
- Secrets
  - Use a secret manager (AWS/GCP/Azure) and inject via environment variables
- Observability
  - Centralized logs, metrics, and alerts (Datadog, Grafana Cloud, etc.)
- Images
  - Build immutable images in CI; pin base versions
- Health
  - Use `/healthz` for liveness; add `/readyz` if you need dependency checks

## CI/CD (Sketch)

- Lint + test → build images → push to registry → deploy to staging → smoke tests → promote to prod

```
# Example steps (platform‑agnostic)
- run: pip install -r requirements.txt && pytest -q
- run: docker build -t your-registry/api:SHA -f api/Dockerfile .
- run: docker build -t your-registry/frontend:SHA -f src/frontend/Dockerfile .
- run: docker push your-registry/api:SHA && docker push your-registry/frontend:SHA
- deploy: staging with updated image tags
```

## Security Checklist

- HTTPS everywhere; HSTS enabled
- JWT secrets rotated regularly
- Principle of least privilege for DB/Redis
- CORS restricted to required origins
- SAST/Dependency scanning in CI

