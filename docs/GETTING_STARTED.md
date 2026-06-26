# Getting Started with CliLens.AI

**Fast-track guide to set up and run the Climate Intelligence Platform in under 10 minutes.**

**Version:** 2.1.0 | **Last Updated:** 2026-03-05

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup (5 Minutes)](#quick-setup-5-minutes)
3. [Project Overview](#project-overview)
4. [Key Concepts](#key-concepts)
5. [Development Workflows](#development-workflows)
6. [Troubleshooting](#troubleshooting)
7. [Next Steps](#next-steps)


---

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| **Docker Desktop** | 24.0+ | Container runtime | [Download](https://www.docker.com/products/docker-desktop/) |
| **Docker Compose** | 2.20+ | Multi-container orchestration | Included with Docker Desktop |
| **Git** | 2.40+ | Version control | [Download](https://git-scm.com/) |
| **Python** | 3.11+ | Backend development | [Download](https://www.python.org/) |
| **Node.js** | 20.0+ | Frontend development | [Download](https://nodejs.org/) |

### Required API Keys

You'll need API keys for the following services:

- **DeepSeek** (required) - Primary LLM for chat, claim extraction, and verification
  - Get key: https://platform.deepseek.com/
  - Set `DEEPSEEK_API_KEY`; model `deepseek-chat`

- **Anthropic Claude** (optional) - Secondary verifier / fallback in the chat chain
  - Get key: https://console.anthropic.com/
  - Set `ANTHROPIC_API_KEY`

- **OpenAI** (optional) - Fallback chat provider
  - Get key: https://platform.openai.com/
  - Set `OPENAI_API_KEY`

- **Perplexity** (optional) - Enhanced news discovery + deep-search web mode
  - Get key: https://www.perplexity.ai/

> The platform runs on **real data only** — there is no mock-verification mode.
> (The old `USE_MOCK_VERIFICATION` flag was removed; it contradicted the
> no-synthetic-data contract.)

### System Requirements

- **RAM:** 8GB minimum, 16GB recommended
- **Disk Space:** 10GB free space
- **OS:** Windows 10/11, macOS 12+, or Linux (Ubuntu 20.04+)
- **Internet:** Stable connection for API calls and Docker images

---

## Quick Setup (5 Minutes)

### Step 1: Clone the Repository

```bash
# Clone the project
git clone <repository-url>
cd climatenews

# Verify you're in the right directory
ls -la  # Should see docker-compose.yml, README.md, etc.
```

### Step 2: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
# Windows: notepad .env
# macOS/Linux: nano .env
```

**Minimal Required Configuration:**

```bash
# === Required API Keys ===
ANTHROPIC_API_KEY=sk-ant-...your-key-here
OPENAI_API_KEY=sk-...your-key-here

# === Database Configuration ===
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/climatenews
REDIS_URL=redis://redis:6379/0

# === JWT Configuration ===
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production

# === Application Settings ===
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Optional Configuration:**

```bash
# Perplexity (for enhanced news discovery)
PERPLEXITY_API_KEY=pplx-...your-key-here

# Climate APIs
CLIMATECHECK_API_KEY=your-climate-check-key
```

### Step 3: Start All Services

```bash
# Recommended: run the current "working core" stack (API + Frontend + Postgres + Redis + Celery worker + Jaeger)
docker-compose -f docker-compose.simple.yml up -d

# Wait for services to initialize (~30-60 seconds)
docker-compose -f docker-compose.simple.yml ps

# Check logs if needed
docker-compose -f docker-compose.simple.yml logs -f
```

### Step 4: Verify Installation

Open these URLs in your browser:

| Service | URL | What You'll See |
|---------|-----|-----------------|
| **Frontend** | http://localhost:5300 | CliLens.AI web interface |
| **API Docs** | http://localhost:5400/docs | Interactive API documentation |
| **Jaeger** | http://localhost:5686 | Distributed tracing UI |

**✅ Success Indicators:**

- Frontend loads without errors
- API docs show all endpoints
- `docker-compose ps` shows all services "healthy"

### Step 5: Run Your First Workflow

```bash
# Trigger the (Celery-backed) workflow pipeline
curl -X POST http://localhost:5400/api/admin/trigger-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "country": "FI",
    "max_articles": 5
  }'

# Check workflow status
curl http://localhost:5400/api/admin/workflows
```

To discover fresh articles on demand (country + keywords), open `http://localhost:5300/admin` and use **Discover Fresh News**.

**Expected Output:**
```json
{
  "status": "success",
  "task_id": "task-2025...",
  "message": "Workflow triggered successfully"
}
```

---

## Project Overview

### System Architecture

CliLens.AI uses a **hierarchical multi-agent system** where a supervisor orchestrates specialized worker agents:

```mermaid
graph TD
    A[API Gateway] --> B[Celery Task Queue<br/>discover_articles]
    B --> C[Celery Task<br/>verify_claims]
    C --> D[Celery Task<br/>create_summary]
    D --> E[Celery Task<br/>render_video_preview]
    E --> F[Celery Task<br/>publish_article]

    F --> G[PostgreSQL<br/>Long-term Storage]
    B --> H[Redis<br/>Broker & State]
    C --> H
    D --> H
    E --> H
    F --> H

    J[Next.js Frontend] --> A

    style A fill:#ff6b6b
    style B fill:#4ecdc4
    style C fill:#45b7d1
    style D fill:#96ceb4
    style E fill:#feca57
    style F fill:#a29bfe
```

### Service Roles

| Service | Role | Technology | Key Responsibility |
|---------|------|------------|-------------------|
| **Orchestration** | Supervisor | Claude 3.5 Sonnet | Workflow state management, task assignment |
| **Ingestion** | Worker | Scrapy + Playwright | Discover and extract news articles |
| **Verification** | Worker | GPT-4o + Climate APIs | Fact-check claims with evidence |
| **Content Creation** | Worker | Claude 3.5 Sonnet | Synthesize verified articles |
| **Video Production** | Worker | Multimodal AI | Generate short-form videos |
| **API Gateway** | Interface | FastAPI | REST API + Authentication |
| **Frontend** | Interface | Next.js 14 | User interface |

### Tech Stack

**Backend:**
- Python 3.11+ with FastAPI
- PostgreSQL 16 (with pgvector extension)
- Redis 7 for caching and as Celery broker
- Celery + Redis for async task queue

**Frontend:**
- Next.js 14 with App Router
- React 18
- Tailwind CSS
- Recharts for visualizations

**AI Models:**
- Claude 3.5 Sonnet (orchestration, content creation)
- GPT-4o (fact-checking, analysis)
- Perplexity (news discovery)

**Infrastructure:**
- Docker & Docker Compose
- Grafana + Prometheus (monitoring)
- Jaeger (distributed tracing)

---

## Key Concepts

### 1. Multi-Agent Workflow

CliLens uses a **Celery task chain** triggered by the API:

1. **API Gateway**: Receives workflow requests and enqueues the first Celery task
2. **Celery Workers**: Execute tasks asynchronously in a defined chain, storing results in PostgreSQL
3. **Task Flow**: Each task in the chain hands off its output to the next as input

**Example Workflow:**

```
User Request → API Gateway → Celery: discover_articles
  → Celery: verify_claims
  → Celery: create_summary
  → Celery: render_video_preview
  → Celery: publish_article → PostgreSQL
```

### 2. Two-Tier Memory System

**Short-term Memory (Redis):**
- Workflow state tracking
- Task status updates
- Agent context (last 30 days)
- Cache for API responses

**Long-term Memory (PostgreSQL):**
- Articles and claims
- Fact-checks and evidence
- User data and feedback
- Audit logs

### 3. Credibility Scoring

Every article receives a transparent credibility score (0-100) based on:

- **Source Credibility (40%)**: Historical reliability of news source
- **Content Relevance (30%)**: Alignment with climate topics
- **Verification Score (30%)**: Fact-checking confidence

**Credibility Levels:**
- 80-100: HIGH (green badge)
- 60-79: MEDIUM (yellow badge)
- 0-59: LOW (red badge)

### 4. Domain-Driven Design (v2 API)

The v2 API uses **bounded contexts**:

- **Content Domain**: Articles, searches, publications
- **Intelligence Domain**: News discovery, fact-checking
- **Identity Domain**: Users, authentication, authorization

**API Structure:**
```
/api/v2/content/*      - Content management
/api/v2/intelligence/* - AI-powered analysis
/api/v2/identity/*     - User management
```

---

## Development Workflows

### Adding a New Feature

**1. Identify the Domain**
```bash
# Check domain documentation
ls docs/domain/
# → content.md, intelligence.md, verification.md, identity.md
```

**2. Follow Domain Patterns**
```bash
# Read relevant .cursorrules
cat .cursor/rules/backend-fastapi.mdc
cat .cursor/rules/database-postgres.mdc
```

**3. Implement with TDD**
```bash
# Write tests first
touch tests/domain/test_my_feature.py

# Run tests (should fail initially)
pytest tests/domain/test_my_feature.py -v

# Implement feature
# ...

# Run tests again (should pass)
pytest tests/domain/test_my_feature.py -v
```

**4. Update Documentation**
```bash
# Update domain documentation
nano docs/domain/my_domain.md

# Update API docs if needed
nano docs/api/v2-reference.md
```

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest -m unit

# Run integration tests
pytest -m integration

# Run with coverage
pytest --cov=src/backend --cov-report=html

# Open coverage report
# Windows: start htmlcov/index.html
# macOS: open htmlcov/index.html
# Linux: xdg-open htmlcov/index.html
```

### Working with Services

**Start a specific service:**
```bash
# Start orchestration service
docker-compose up orchestration-service

# Start ingestion service
docker-compose up ingestion-service

# Start with logs
docker-compose up -d ingestion-service && docker-compose logs -f ingestion-service
```

**Rebuild after code changes:**
```bash
# Rebuild specific service
docker-compose build ingestion-service
docker-compose up -d ingestion-service

# Rebuild all services
docker-compose build
docker-compose up -d
```

**Check service health:**
```bash
# View all service status
docker-compose ps

# Check specific service logs
docker-compose logs ingestion-service --tail=100

# Follow logs in real-time
docker-compose logs -f ingestion-service
```

### Database Operations

**Connect to PostgreSQL:**
```bash
# Via Docker
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Via local client (if installed)
psql postgresql://postgres:postgres@localhost:5433/climatenews
```

**Common queries:**
```sql
-- Check articles count
SELECT COUNT(*) FROM articles;

-- View recent fact checks
SELECT * FROM fact_checks ORDER BY created_at DESC LIMIT 10;

-- Check workflow status
SELECT * FROM workflow_logs ORDER BY created_at DESC LIMIT 20;
```

**Connect to Redis:**
```bash
# Via Docker
docker exec -it climatenews-redis redis-cli

# Commands
> KEYS workflow:*
> GET workflow:wf-123
> SCAN 0 MATCH task:* COUNT 100
```

---

## Troubleshooting

### Service Won't Start

**Problem**: `docker-compose up` shows errors

**Solutions**:
1. Check Docker is running: `docker info`
2. Check ports aren't in use:
   ```bash
   # Windows
   netstat -ano | findstr :5400

   # macOS/Linux
   lsof -i :5400
   ```
3. Clean and rebuild:
   ```bash
   docker-compose down -v
   docker-compose build --no-cache
   docker-compose up -d
   ```

### API Returns 500 Errors

**Problem**: API calls fail with internal server error

**Solutions**:
1. Check API logs:
   ```bash
   docker-compose logs api-gateway --tail=100
   ```
2. Verify database connection:
   ```bash
   docker exec climatenews-postgres pg_isready
   ```
3. Check environment variables:
   ```bash
   docker exec climatenews-api-gateway env | grep DATABASE_URL
   ```

### Frontend Shows Empty Data

**Problem**: Frontend loads but shows no articles

**Solutions**:
1. Check API connectivity:
   ```bash
   curl http://localhost:5400/api/v2/content/articles
   ```
2. Verify database has data:
   ```bash
   docker exec -it climatenews-postgres \
     psql -U postgres -d climatenews -c "SELECT COUNT(*) FROM articles;"
   ```
3. Check browser console for errors (F12)

### Docker Out of Memory

**Problem**: Containers crashing with OOM errors

**Solutions**:
1. Increase Docker memory limit:
   - Docker Desktop → Settings → Resources → Memory
   - Set to 8GB minimum
2. Prune unused resources:
   ```bash
   docker system prune -a --volumes
   ```

### Common Port Conflicts

If ports are already in use, modify `docker-compose.yml`:

| Service | Default Port | Alternative Port |
|---------|--------------|------------------|
| API | 5400 | 5201 |
| Frontend | 5300 | 5301 |
| PostgreSQL | 5433 | 5434 |
| Redis | 5379 | 5380 |

---

## Next Steps

Now that you're set up, explore these resources:

### Documentation

- **[Current State](CURRENT_STATE.md)** - Live status of all services and components
- **[API Reference](api/backend.md)** - Explore available endpoints
- **[Domain Documentation](domain/)** - Learn business logic

### Development

1. **Try the Example Workflows**
   - Review `context_examples/` for AI assistant usage
   - Follow `.cursor/.cursorrules` for coding patterns

2. **Contribute**
   - Check open issues on GitHub
   - Follow the contribution guidelines
   - Submit pull requests

3. **Monitor & Optimize**
   - Explore Grafana dashboards (http://localhost:3001)
   - Review Jaeger traces (http://localhost:5686)
   - Optimize based on metrics

### Learning Resources

- **System Overview**: [docs/CURRENT_STATE.md](CURRENT_STATE.md)
- **Task Queue**: Celery worker logs via `docker-compose logs celery-worker`
- **Domain-Driven Design**: [docs/domain/](domain/)

---

## Support & Community

**Questions?**
- 📖 Check [documentation](../README.md)
- 🐛 Report issues on GitHub
- 💬 Join team Slack: #climatenews-dev

**Found a bug?**
- Check [Troubleshooting](#troubleshooting) section
- Review service logs: `docker-compose logs <service>`
- Create GitHub issue with reproduction steps

---

**Ready to build? Let's make climate news transparent! 🌍✨**
