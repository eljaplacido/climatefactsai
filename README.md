# CliLens.AI: Climate Intelligence Platform

**Trust as a Service** — Evidence-backed climate stories with transparent provenance and credibility scoring.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

**Version:** 2.0.0 | **Updated:** 2025-11-22

---

## What is CliLens?

CliLens.AI is an AI-powered platform that discovers, verifies, and publishes climate news with transparent credibility scoring. Every claim ships with evidence trails and confidence scores.

**Key Features:**
- 🔍 Automated news discovery from 31 European countries
- ✅ Multi-layer fact-checking with authoritative climate data sources
- 📊 Transparent credibility scoring (source + content + verification)
- 🌐 Multi-country support with language-specific content analysis
- 💡 Interactive UI for exploring fact-checks and evidence trails

---

## Quick Start

Get running in 5 minutes:

```bash
# Clone and configure
git clone <repository-url> && cd climatenews
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY)

# Recommended local stack (API + Frontend + Postgres + Redis + Celery worker + Jaeger)
docker-compose -f docker-compose.simple.yml up -d

# (Optional) Full stack including Kafka + microservices + Grafana/Prometheus
# docker-compose up -d

# Access the platform
# Frontend: http://localhost:5300
# API: http://localhost:5200/docs
# Jaeger (traces): http://localhost:5686
```

**New to the project?** See **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** for comprehensive setup guide.

---

## Architecture

**Pattern:** Hierarchical multi-agent system (supervisor-worker)
**Communication:** Event-driven via Apache Kafka
**Stack:** Python + FastAPI + Next.js + Kafka + PostgreSQL + Redis

```
Orchestrator (Claude 3.5 Sonnet)
    │
    ├── Ingestion Service (News Discovery)
    ├── Verification Service (Fact Checking)
    ├── Content Creation Service (Article Synthesis)
    └── Video Production Service (Video Generation)
```

**See full architecture:** [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)

---

## Service Inventory

| Service | Purpose | Technology | Port |
|---------|---------|------------|------|
| **Orchestration** | Workflow supervisor & state management | Claude 3.5 Sonnet | - |
| **Ingestion** | News discovery & content extraction | Scrapy + Playwright | - |
| **Verification** | Fact-checking & evidence collection | GPT-4o + Climate APIs | - |
| **Content Creation** | Article synthesis & summarization | Claude 3.5 Sonnet | - |
| **Video Production** | Short-form video generation | Multimodal AI | - |
| **API Gateway** | REST API & authentication | FastAPI + PostgreSQL | 5200 |
| **Frontend** | Web application | Next.js 14 + Tailwind CSS | 5300 |
| **PostgreSQL** | Long-term storage + pgvector | PostgreSQL 16 | 5433 |
| **Redis** | Short-term memory & caching | Redis 7 | 5379 |
| **Kafka** | Event streaming & messaging | Confluent Platform 7.5 | 5092 |
| **Zookeeper** | Kafka coordination | Confluent Platform 7.5 | 5181 |
| **Schema Registry** | Kafka schema management | Confluent Platform 7.5 | 5081 |
| **Grafana** | Monitoring dashboards | Grafana 10.2 | 3001 |
| **Prometheus** | Metrics collection | Prometheus 2.48 | 5090 |
| **Jaeger** | Distributed tracing | Jaeger 1.51 | 5686 |

---

## For Different User Types

### 👨‍💻 New Developers
**Get started:**
1. Complete [Quick Start](#quick-start) setup
2. Read [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for comprehensive onboarding
3. Understand architecture: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
4. Follow coding patterns: [.cursor/.cursorrules](.cursor/.cursorrules)

### 🔧 DevOps Engineers
**Deploy and monitor:**
1. Review [Service Inventory](#service-inventory) for infrastructure needs
2. Follow deployment guide: [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md)
3. Set up monitoring: Grafana (port 3001) + Prometheus (port 5090)
4. Configure tracing: Jaeger UI (port 5686)

### 🤖 AI/ML Engineers
**Work with AI models:**
1. Explore multi-agent architecture: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
2. Review domain logic: [docs/domain/](docs/domain/)
3. Understand message schemas: `schemas/*.json`
4. See AI integration patterns in `src/backend/services/`

### 📊 Product Managers
**Understand capabilities:**
1. Review [Key Features](#what-is-cilens)
2. Explore [Vision & Roadmap](docs/VISION_GLOBAL_CLIMATE_PLATFORM.md)
3. See [MVP Roadmap](docs/MVP_EUROPE_ROADMAP.md)
4. Check workflows: [docs/WORKFLOW_AND_UX.md](docs/WORKFLOW_AND_UX.md)

---

## Development

### Add a Microservice
Follow the event-driven agent pattern with Kafka integration:
- Location: `src/backend/services/{service}_service/`
- Reference: `.cursor/rules/backend-fastapi.mdc`

### Add an API Endpoint (v2)
Use Domain-Driven Design (DDD):
- Location: `src/backend/app/domains/{domain}/`
- Documentation: `docs/domain/`

### Run Tests
```bash
pytest tests/ --cov=src/backend  # Backend tests
cd src/frontend && npm test       # Frontend tests
```

**See detailed development guide:** [docs/architecture/DEVELOPMENT.md](docs/architecture/DEVELOPMENT.md)

---

## Repository Structure

```
climatenews/
├── api/                          # FastAPI gateway (v1 + v2)
├── src/
│   ├── backend/
│   │   ├── app/                  # v2 API (Domain-Driven Design)
│   │   │   ├── domains/          # Business domains
│   │   │   └── core/             # Shared infrastructure
│   │   ├── services/             # Microservices (5 worker agents)
│   │   └── shared/               # Shared libraries
│   └── frontend/                 # Next.js 14 web application
├── docs/                         # Documentation
│   ├── architecture/             # System design & patterns
│   ├── domain/                   # Domain specifications
│   └── archive/                  # Legacy documentation
├── schemas/                      # JSON schemas for inter-service messages
├── infrastructure/               # Database, monitoring configs
└── docker-compose.yml            # Development environment
```

---

## Contributing

We welcome contributions! Before submitting a pull request:

1. **Read coding standards:** [.cursor/.cursorrules](.cursor/.cursorrules)
2. **Follow DDD patterns:** New API endpoints use Domain-Driven Design in `src/backend/app/domains/`
3. **Write tests:** Maintain 80%+ test coverage
4. **Update documentation:** Keep docs synchronized with code
5. **Use conventional commits:** `feat:`, `fix:`, `docs:`, etc.

**See contribution guide:** [docs/architecture/DEVELOPMENT.md](docs/architecture/DEVELOPMENT.md)

---

## Production Deployment

**Infrastructure Requirements:**
- PostgreSQL 16 with pgvector extension
- Redis 7+ cluster
- Apache Kafka (KRaft mode recommended)
- Docker or Kubernetes for orchestration

**Deployment Guides:**
- Production setup: [docs/architecture/DEPLOYMENT.md](docs/architecture/DEPLOYMENT.md)
- Monitoring: Grafana dashboards + Prometheus metrics
- Troubleshooting: Service-specific runbooks *(coming soon)*

---

## License

[Your License Here]

---

## Links

- **Documentation Hub:** [docs/README.md](docs/README.md)
- **Architecture Deep Dive:** [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- **Getting Started:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
- **Vision & Roadmap:** [docs/VISION_GLOBAL_CLIMATE_PLATFORM.md](docs/VISION_GLOBAL_CLIMATE_PLATFORM.md)

---

**Built with trust, powered by evidence.** 🌍
