# Climatefacts.ai: Climate Intelligence Platform

**Trust as a Service** — Evidence-backed climate stories with transparent provenance and credibility scoring.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

**Version:** 3.0.0 | **Updated:** 2026-04-30

---

## What is Climatefacts.ai?

Climatefacts.ai is an AI-powered platform that discovers, verifies, and publishes climate news with transparent credibility scoring. Every claim ships with evidence trails and confidence scores.

**Key Features:**
- News discovery across 198 reference countries (live coverage depends on ingestion)
- Multi-layer fact-checking with authoritative climate data sources
- Transparent credibility scoring (source + content + verification)
- Interactive Climate Intelligence Map with chat and drill-down
- HybridRAG pipeline with a populated knowledge graph — entities and relationships are extracted by `EntityExtractionService` and called alongside `populate_embedding` from `src/backend/app/tasks/ingestion.py` (ingestion) and `src/backend/app/tasks/processing.py` (post-summary)
- Optional CARF analytical engine integration via HTTP proxy (`src/backend/app/domains/intelligence/carf_integration.py`)
- Context-aware climate intelligence assistant: knows what article / country / URL analysis / deep-search the user is viewing and grounds answers in the live article corpus + extracted claims + knowledge graph (see [docs/architecture/CHAT_VIEW_CONTEXT.md](docs/architecture/CHAT_VIEW_CONTEXT.md))
- User dashboard with reading history, bookmarks, and subscription tiers

> **CARF.** Optional. `carf_integration.py` proxies to `CARF_API_URL` (default `http://localhost:8000`); default deployments do not run that service. When unreachable, claim verification falls back to the Cynefin keyword classifier in `cynefin_router.py`.

> **Data integrity.** All production paths return real data. The Copernicus seasonal-temp synthetic fallback was removed; the former `scripts/api_mock.py` is now `tests/fixtures/standalone_mock_api.py` behind an opt-in `CLILENS_ALLOW_MOCK_API` guard. Demo seed scripts require `CLILENS_ALLOW_FAKE_SEED=1` and refuse to run when `ENV=production`.

---

## Quick Start

Get running in 5 minutes:

```bash
# Clone and configure
git clone <repository-url> && cd climatenews
cp .env.example .env
# Edit .env with your API keys (see "API keys & data sources" below)

# Recommended local stack (API + Frontend + Postgres + Redis + Celery worker + Jaeger)
docker-compose -f docker-compose.simple.yml up -d

# (Optional) Full stack including Kafka + microservices + Grafana/Prometheus
# docker-compose up -d

# Access the platform
# Frontend: http://localhost:5300
# API: http://localhost:5400/docs
# Jaeger (traces): http://localhost:5686
```

### API keys & data sources

| Provider | Required for | If missing |
|---|---|---|
| `DEEPSEEK_API_KEY` | Chat, claim extraction, adjudication | Chat / verification disabled |
| `OPENAI_API_KEY` | Semantic embeddings (`openai:text-embedding-ada-002`) | Deep-search degrades to FTS + Perplexity |
| `ANTHROPIC_API_KEY` | Optional summarisation paths (env-driven model) | Falls back to other providers |
| `PERPLEXITY_API_KEY` | External discovery + deep-search external mode | Internal-corpus only |
| Open-Meteo, NASA POWER | Weather context (no key) | Always available |
| Copernicus CDS API key | ERA5 reanalysis | Endpoint returns "unavailable" (no synthetic fallback) |
| `CARF_API_URL` (+ `CARF_API_KEY`) | Optional CARF reasoning | Cynefin keyword classifier used instead |

**New to the project?** See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

---

## Architecture

- **Pattern:** Hierarchical multi-agent system (supervisor-worker)
- **Communication:** Celery + Redis by default (`docker-compose.simple.yml`); Kafka available in the full stack (`docker-compose.yml`)
- **Stack:** Python + FastAPI + Next.js + PostgreSQL (pgvector) + Redis

```
Orchestrator (Claude 3.5 Sonnet)
    ├── Ingestion (news discovery)
    ├── Verification (fact-checking)
    ├── Content Creation (article synthesis)
    └── Video Production (short-form video)
```

**See:** [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) · [docs/architecture/](docs/architecture/)

---

## Service Inventory

| Service | Stack | Port |
|---|---|---|
| API Gateway | FastAPI + PostgreSQL | 5400 |
| Frontend | Next.js 14 + Tailwind | 5300 |
| PostgreSQL (pgvector) | PostgreSQL 16 | 5433 |
| Redis (cache + Celery broker) | Redis 7 | 5379 |
| Celery workers (ingestion, processing) | Python | internal |
| Jaeger (tracing) | Jaeger 1.51 | 5686 |
| Kafka / Grafana / Prometheus | full stack only | 5092 / 3001 / 5090 |

---

## For Different User Types

- **Developers:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) · [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) · [.cursor/rules/](.cursor/rules/)
- **DevOps:** [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md) — Grafana (3001), Prometheus (5090), Jaeger (5686)
- **AI/ML:** [docs/domain/](docs/domain/) · [docs/architecture/CHAT_VIEW_CONTEXT.md](docs/architecture/CHAT_VIEW_CONTEXT.md) · `schemas/*.json` · `src/backend/app/domains/intelligence/`
- **Product:** [Vision & Roadmap](docs/VISION_GLOBAL_CLIMATE_PLATFORM.md) · [MVP Roadmap](docs/MVP_EUROPE_ROADMAP.md) · [docs/WORKFLOW_AND_UX.md](docs/WORKFLOW_AND_UX.md)

---

## Development

- **New microservice:** `src/backend/services/{service}_service/` — see `.cursor/rules/backend-fastapi.mdc`
- **New v2 API endpoint:** `src/backend/app/domains/{domain}/` (DDD) — see `docs/domain/`
- **Tests:** `pytest tests/ --cov=src/backend` · `cd src/frontend && npm test`

**Full guide:** [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)

---

## Repository Structure

```
climatenews/
├── api/                  # FastAPI gateway (v1 + v2)
├── src/
│   ├── backend/
│   │   ├── app/          # v2 API (DDD): domains/, core/, tasks/
│   │   ├── services/     # Worker microservices
│   │   └── shared/       # Shared libraries
│   └── frontend/         # Next.js 14 web application
├── docs/                 # Documentation (architecture/, domain/, archive/)
├── schemas/              # JSON schemas for inter-service messages
├── infrastructure/       # Database, monitoring configs
├── tests/                # Backend tests + fixtures
└── docker-compose.yml    # Development environment
```

---

## Contributing

1. Coding standards: [.cursor/rules/](.cursor/rules/)
2. New API endpoints follow DDD in `src/backend/app/domains/`
3. Maintain 80%+ test coverage; keep docs in sync; use conventional commits

**See:** [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)

---

## Production Deployment

Infrastructure: PostgreSQL 16 (pgvector), Redis 7+, optional Kafka, Docker/Kubernetes. See [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md).

---

## License

[Your License Here]

---

## Links

- [docs/README.md](docs/README.md) — documentation hub
- [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) — current platform state
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — setup
- [docs/architecture/CHAT_VIEW_CONTEXT.md](docs/architecture/CHAT_VIEW_CONTEXT.md) — chat grounding contract
- [docs/VISION_GLOBAL_CLIMATE_PLATFORM.md](docs/VISION_GLOBAL_CLIMATE_PLATFORM.md) — vision & roadmap

---

**Built with trust, powered by evidence.**
