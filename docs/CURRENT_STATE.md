# Climatefacts.ai — Current State (Authoritative)

**Last Updated:** 2026-06-04
**Previous:** 2026-05-20
**Status:** Global Platform Operational — 194 countries, full trust infrastructure, corporate claims, agentic chat
**This is the single source of truth for the current state of the project.**

> **2026-06-26 update (DOC-03):** for the latest production-readiness snapshot —
> dimension health scores, the verified-blocker ledger, and the required deploy
> env vars (`ADMIN_EMAILS`, `CLILENS_ALERT_EMAIL`) — see
> `docs/improvementplans/Production-Readiness-Audit-2026-06-26.md`. Any "Known
> Issues" / dates lower in this document predate that audit.

---

## 2026-06-04 — E2E audit remediation wave (audit seq-1..13)

Shipped + verified live this session (see `docs/improvementplans/E2E-Audit-Roadmap-2026-06-02.md`):

- **Content API fixed**: `/api/v2/articles` returned `[]`/500 → now gates on `is_off_topic`/`is_synthetic` (dropped non-existent `headline`/`summary_text` columns), fully parameterized.
- **Agentic chat now emits actions**: `_generate_answer` advertises the full 22-skill registry; `VALID_ACTION_TYPES` derives from `SKILLS_REGISTRY` (was a stale 9). Prompt template + dispatcher + pin tests aligned at **22 skills**.
- **NEW endpoints**: `GET /api/companies/compare?a=&b=` (two-company climate head-to-head), `GET /api/admin/llm/cost` (LLM cost telemetry, cloud-vs-GX10 split).
- **Insights endpoint gated**: `POST /api/v2/intelligence/analyze-text` now requires auth + a new **`insights_extraction`** quota (anon=0, free=50 lifetime, basic=500, professional=5000).
- **Credibility scoring**: one ladder via `src/backend/shared/credibility_thresholds.py` (HIGH=80, MEDIUM=50; 0-100 scale); live URL credibility is now verification-backed (Step-7.5 verdicts), not a text-length heuristic. `/api/methodology` returns a real `git_revision`.
- **Maps**: `/api/map/country/{cc}/detail` now returns `climate_risk_score`.
- **Sources**: `/api/v2/sources` 84 unrated → 0 (name-OR-domain tier join + mig 060/061).
- **Company tracker (B3)**: **3,960 SBTi-validated companies** (was 9) via a batched SBTi sync; monthly `cn-sbti-sync` Cloud Scheduler cron.
- **Embeddings**: `articles.embedding_bge_m3 vector(1024)` + HNSW (mig 062); ~3,328/3,329 embedded via the GX10 `infrastructure/gx10/embedding_worker.py` (bge-m3, free).
- **Migrations 060-063** applied. **GX10 access** via `ssh gx10` (see project memory).

---

## What Actually Works Right Now

### Core Infrastructure (100% Operational)

#### Running Containers (7 services)
```bash
docker-compose -f docker-compose.simple.yml up -d
# Services:
- clilens-api             (FastAPI backend on port 5400)
- clilens-frontend        (Next.js frontend on port 5300)
- climatenews-postgres    (PostgreSQL 16 + pgvector on port 5433)
- climatenews-redis       (Redis 7 on port 5379)
- clilens-celery-worker   (Background task processing)
- clilens-celery-beat     (Scheduled tasks)
- climatenews-jaeger      (Distributed tracing UI on port 5686)
```

#### Database Schema
- `articles` - Article metadata, content, credibility scores
- `claims` - Extracted claims from articles
- `fact_checks` - Verification results for claims
- `countries` - Country data (structure complete, limited data)
- `publishers` - Source credibility tracking
- `users` - Authentication and user management
- `subscriptions` - User subscription tiers (Stripe integration)
- `api_keys` - API key management
- `article_feedback` - User feedback system
- `workflow_logs` - Workflow execution tracking
- `url_analyses` - User-submitted URL analysis jobs
- `user_preferences` - User settings

### Backend API (90% Complete)

#### Working Endpoints (50+)
```
# Articles & Content
GET  /api/articles                      - List articles (filter: country, credibility, category, tags, q)
GET  /api/articles/{id}                 - Article detail with claims, fact checks, evidence
POST /api/articles/{id}/feedback        - Submit feedback
POST /api/articles/{id}/reanalyze       - Re-run analysis with failure explanation
POST /api/articles/{id}/ask             - Ask question about article (grounded Q&A)
GET  /api/articles/{id}/conversations   - Conversation history
POST /api/articles/ingest               - Ingest article from URL
POST /api/articles/ingest/document      - Ingest research report/PDF from URL
POST /api/articles/ingest/upload        - Upload PDF/DOCX/TXT file for analysis

# General Chat (cross-article Q&A)
POST /api/chat                          - Ask general climate question
GET  /api/chat/sessions                 - List chat sessions
GET  /api/chat/sessions/{id}            - Get session history

# Map & Geographic Intelligence
GET  /api/map/country-stats             - Per-country stats (filter: category, source, reliability, region)
GET  /api/map/discussed-country-stats   - Stats by discussed country (filter: category, source, reliability, region)
GET  /api/map/topic-density             - Topic heatmap data
GET  /api/map/source-coverage           - Source-to-country coverage matrix
POST /api/map/query                     - Agentic map query (NL or structured, returns country highlights)
GET  /api/map/regions                   - List geographic regions with country codes
GET  /api/map/available-sources         - List all sources with article counts (for source filter dropdown)
GET  /api/map/available-themes          - List all themes/tags ranked by frequency (for theme filtering)

# Search & Explore
GET  /api/search                        - Full-text search with filters
POST /api/explore/articles              - Advanced multi-criteria filter
GET  /api/explore/topics                - Trending topics
GET  /api/explore/sources               - Source listing with credibility
POST /api/explore/trends                - Time-series trend data
GET  /api/explore/coverage              - Data coverage report

# Deep Search & Research
POST /api/deep-search                   - Perplexity-type deep search
POST /api/deep-search/compare           - Comparative analysis
GET  /api/deep-search/weather-context   - Weather context enrichment

# User Management
POST /api/auth/register                 - User registration
POST /api/auth/login                    - User login
POST /api/auth/refresh                  - Token refresh
GET  /api/auth/me                       - User profile
GET  /api/user/preferences              - User preferences
PUT  /api/user/preferences              - Update preferences
GET  /api/user/bookmarks                - List bookmarks
GET  /api/user/activity                 - Activity history
GET  /api/user/saved-queries            - Saved recurring queries
POST /api/user/saved-queries            - Create saved query
POST /api/user/saved-queries/{id}/run   - Run saved query on demand

# Feed Management
GET  /api/feed/preferences              - Feed country preferences
PUT  /api/feed/preferences              - Set preferred countries/keywords
POST /api/feed/refresh                  - Manual feed refresh

# Subscription & Billing
GET  /api/subscription/current          - Current tier
POST /api/subscription/create           - Create (Stripe)
PUT  /api/subscription/upgrade          - Upgrade/downgrade
DELETE /api/subscription/cancel         - Cancel

# Analytics
GET  /api/analytics/dashboard           - Full analytics dashboard
GET  /api/analytics/pipeline            - Pipeline status
GET  /api/analytics/sources             - Source performance
GET  /api/analytics/countries           - Country analytics

# Admin
POST /api/admin/trigger-workflow        - Trigger ingestion workflow
GET  /api/admin/workflows               - Recent workflows
```

#### API Features
- JWT authentication (register, login, token refresh)
- API key management
- Rate limiting (Redis-backed)
- CORS configured for local development
- Request/response tracing (X-Request-ID, Jaeger)
- Structured logging (structlog)
- Subscription tier management (Stripe webhooks)
- Celery background task processing
- URL analysis with claim extraction

### Frontend (75% Complete)

#### Working Pages
- Homepage (`/`) - Article listing with filters
- Article Detail (`/articles/[id]`) - Full article view with claims
- Search (`/search`) - Search interface with suggestions
- Analyze (`/analyze`) - URL analysis form
- Admin Dashboard (`/admin`) - Admin interface
- Sources (`/sources`) - Source profiles
- About (`/about`) - Platform info
- Methodology (`/methodology`) - How it works
- Deep Search (`/deep-search`) - Advanced search
- Map (`/map`) - Global Climate Intelligence World Map with agentic query, source/theme/reliability filtering
- Feed (`/feed`) - Personalized feed
- Forecasts (`/forecasts`) - Climate forecasts

#### Working Components (27 components)
ArticleCard, ArticleDetailTabs, ArticleQA, AdvancedInsights,
BookmarkButton, ClaimCard, ClaimCategoryBreakdown, CountrySelector,
CredibilityGauge, DecomposedConfidenceChart, EuropeMap, EvidenceChain,
EvidenceTimeline, FactCheckBadge, FactCheckDetail, LoadingSpinner,
Markdown, ShareButton, SimilarArticles, SiteLayout, SkeletonCard,
SourceProfileCard, StatCard, TraceDebug, TrendingTopics,
UrlAnalysisForm, WeatherContext

#### UI Features
- Responsive design (mobile/tablet/desktop)
- Dark mode support
- Filter by country, credibility, date, tags
- Search with autocomplete suggestions
- Error handling and empty states
- Markdown rendering (react-markdown + GFM)

### Testing (Vitest - 37 tests passing)

```bash
cd src/frontend && npx vitest run
# 7 test files, 37 tests:
# - CredibilityGauge.test.tsx (7 tests)
# - FactCheckBadge.test.tsx (6 tests)
# - LoadingSpinner.test.tsx (3 tests)
# - StatCard.test.tsx (4 tests)
# - ArticleCard.test.tsx (4 tests)
# - HomePage.test.tsx (6 tests)
# - SearchPage.test.tsx (7 tests)
```

---

## Architecture

### Current Architecture (What's Running)

```
┌─────────────────┐
│   Frontend      │  Next.js 14 + TypeScript + Tailwind
│  (Port 5300)    │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│   API Server    │  FastAPI + Python 3.11
│  (Port 5400)    │  18+ route modules
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
┌────────┐ ┌────────┐ ┌──────────────┐
│Postgres│ │ Redis  │ │ Celery       │
│:5433   │ │:5379   │ │ Worker+Beat  │
└────────┘ └────────┘ └──────────────┘
                           │
                      ┌────┴────┐
                      ▼         ▼
                  ┌────────┐ ┌────────┐
                  │ Jaeger │ │ Tasks  │
                  │:5686   │ │(async) │
                  └────────┘ └────────┘
```

**Communication:** Direct HTTP → API → SQL queries
**Async:** Celery + Redis for background tasks
**Tracing:** OpenTelemetry → Jaeger
**Scalability:** Vertical (single API instance) + horizontal via Celery workers

### Architecture Decision (Phase 2 - Complete)
- Kafka removed — REST + Celery + Redis
- 7 containers (down from 17 planned)
- Lower complexity, easier debugging, production-ready

---

## Known Issues & Limitations

### Medium Priority
1. **API Credits Exhausted** - Anthropic + OpenAI quotas depleted; claim extraction and embeddings degraded
2. **Identity Domain Empty** - `src/backend/app/domains/identity/` is a placeholder
3. **Limited Country Data** - Only Finland has significant article data
4. **V2 Domains Partially Integrated** - Some V2 endpoints work, others are stubs

### Low Priority
5. **Documentation Overload** - 90+ markdown files with overlapping info (this doc is authoritative)
6. **Legacy Kafka Code** - `shared/kafka_client.py` still exists but is unused

---

## Environment Requirements

### Required
```bash
DATABASE_URL=postgresql://...        # Auto-configured in Docker
REDIS_URL=redis://...                # Auto-configured in Docker
JWT_SECRET_KEY=...                   # For authentication
ANTHROPIC_API_KEY=sk-ant-...         # For claim extraction
```

### Optional
```bash
OPENAI_API_KEY=...                   # Embeddings for similar articles
PERPLEXITY_API_KEY=...               # News discovery
STRIPE_SECRET_KEY=...                # Payment processing
STRIPE_WEBHOOK_SECRET=...            # Stripe webhooks
DEEPL_API_KEY=...                    # Translation (future)
```

---

## Development Roadmap

### Completed Phases

**Phase 1: Fix Known Issues (100%)**
- Removed mock data fallbacks → explicit HTTP 503 errors
- Added `claims_status` field to articles
- Markdown rendering verified working
- URL analysis endpoint implemented
- Search working (suggestions + full-text)
- Fixed `execute_query`/`execute_update` misuse across all route files
- Fixed Celery Beat permissions and LogRecord key collisions
- Created missing database tables (article_feedback)
- Frontend Vitest tests (5 files, 24 tests)

**Phase 2: Architecture Decision (100%)**
- Kafka removed, Celery + Redis adopted
- docker-compose.simple.yml is the operational config
- 7 healthy containers running

**Phase 3: EU Expansion (100%)**
- 49 RSS feeds (29 European) across 14+ EU countries
- DeepL translation task with batch scheduling
- 20-country ingestion schedule (Celery Beat)

**Phase 4: Global Expansion + Advanced Features (100%)**
- 215 RSS feeds across 8 regions (europe, north_america, africa, latin_america, asia, middle_east, global, research)
- File upload ingestion (PDF, DOCX, TXT, MD, HTML) with content type detection
- General chat endpoint for cross-article Q&A with session management
- Saved query scheduling (hourly/daily/weekly/monthly)
- Agentic map query API for chat-driven map interactions
- Source-based and reliability-based map filtering
- Weather data for 60+ countries via Open-Meteo (global, no key needed)
- Research report / industry analysis feed integration (Nature, Science, McKinsey, BloombergNEF, etc.)
- Security review completed (see docs/SECURITY_REVIEW.md)

### Data Source Coverage (215 feeds)
| Region | Feeds | Key Countries |
|--------|-------|---------------|
| Europe | 70 | 45 countries + EU institutions |
| North America | 20 | US (NOAA, NASA, EPA, NYT, Yale, MIT, etc.) |
| Africa | 25 | Kenya, Nigeria, South Africa, Ghana, Tanzania, Egypt, Morocco |
| Latin America | 20 | Brazil, Mexico, Argentina, Colombia, Chile, Peru |
| Asia/Oceania | 29 | China, India, Japan, Korea, Indonesia, Australia |
| Middle East | 17 | UAE, Saudi Arabia, Israel, Qatar, Jordan, Lebanon |
| Global/International | 19 | IPCC, WMO, UNEP, Reuters, IEA, IRENA |
| Research/Industry | 15 | Nature, Science, McKinsey, Bloomberg, S&P, RMI |

### Weather/Climate Data Sources (Global)
- Open-Meteo (current, forecast, historical — no API key, global)
- NOAA CDO (US-focused, global coverage)
- NASA POWER (satellite data, global)
- Copernicus ERA5 (European, global reanalysis)
- ECMWF (climate models, air quality, flood, marine)

### Next: Phase 5 - Production & Scale
1. Production deployment (HTTPS, CDN, monitoring)
2. GDPR compliance endpoints (data export, account deletion)
3. Mobile app (React Native or PWA)
4. Real-time alerting for breaking climate events

---

## Quick Start

```bash
cd C:\Users\35845\Desktop\DIGICISU\climatenews

# Start all services
docker-compose -f docker-compose.simple.yml up -d

# Verify
curl http://localhost:5400/health
# → {"status":"healthy","timestamp":"..."}

# Frontend at http://localhost:5300
# API docs at http://localhost:5400/docs
# Jaeger at http://localhost:5686
```

---

**Last updated by:** Claude Code (2026-03-20)
**Changes (latest):** Multi-language translation (10+ languages with UI i18n), scientific benchmark auditing (10 reference standards), article audit trails, source evaluation with explained scoring, platform KPI benchmarking, enhanced map with source/theme filters and agentic query, language selector in navigation, mobile responsive nav, security headers (backend+frontend), XSS/SSRF hardening, auth token attachment, 42+ E2E tests, global seed data (70+ articles across 6 continents), integration feasibility audit of 3 external libraries.
**Previous:** Global expansion to 215 feeds across 8 regions, file upload ingestion, agentic map query, chat endpoints, security review.
