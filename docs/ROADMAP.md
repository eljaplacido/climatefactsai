# CliLens.AI — Complete Feature Roadmap

**Last Updated:** 2026-03-12
**Status Tracking:** Each item has a status: DONE / IN PROGRESS / PLANNED

---

## Phase 1: Core Platform (DONE)
- [x] FastAPI backend with PostgreSQL + pgvector
- [x] Next.js 14 frontend with Tailwind CSS
- [x] Article ingestion from Perplexity + RSS feeds
- [x] Multi-country RSS feed registry (49 feeds, 14+ EU countries)
- [x] JWT authentication (register, login, token refresh)
- [x] URL analysis endpoint with claim extraction
- [x] Celery + Redis for background task processing
- [x] OpenTelemetry tracing with Jaeger
- [x] Docker Compose deployment (7 containers)

## Phase 2: Architecture (DONE)
- [x] Kafka removed → Celery + Redis
- [x] Domain-Driven Design (Content, Intelligence, Trust, Identity)
- [x] 7 containers (down from 17 planned)

## Phase 3: EU Expansion (DONE)
- [x] 39 countries in DB (18 EU members)
- [x] 20-country ingestion schedule
- [x] DeepL translation integration
- [x] Staggered Celery Beat scheduling

## Phase 4: Advanced Features (IN PROGRESS)

### 4.1 Automated Fact-Checking Pipeline (DONE)
- [x] `auto_verify_pending_articles` — every 2 hours, batch of 10
- [x] `retry_failed_verifications` — daily at 4 AM
- [x] `pipeline_health_check` — hourly monitoring
- [x] Celery chain: ingestion → verification → summary → embedding

### 4.2 Advanced Analytics Dashboard (DONE)
- [x] `/api/analytics/dashboard` — aggregated analytics endpoint
- [x] `/api/analytics/pipeline` — verification pipeline status
- [x] `/api/analytics/trends` — time-series data (up to 90 days)
- [x] `/api/analytics/sources` — source performance rankings
- [x] `/api/analytics/claims` — claim category breakdowns
- [x] `/api/analytics/verdicts` — verdict distribution
- [x] Frontend analytics page at `/admin/analytics`

### 4.3 DeepSeek-Only LLM Migration (DONE)
- [x] All LLM calls routed through DeepSeek API
- [x] Unified `llm_client.py` module for all services
- [x] ClaimExtractor uses DeepSeek only
- [x] VerdictAdjudicator uses DeepSeek only
- [x] ConversationEngine uses DeepSeek only
- [x] AnalysisEngine uses DeepSeek only
- [x] AnalysisArticleGenerator uses DeepSeek only
- [x] DeepSearchService uses DeepSeek only
- [x] No more Anthropic API errors

### 4.4 Re-Run Analysis & Failure Transparency (DONE)
- [x] "Re-run Analysis" button on article detail page for failed/incomplete verifications
- [x] Clear user-facing explanation of WHY analysis failed (API limits, text too short, etc.)
- [x] Show partial results even when some claims couldn't be verified
- [x] API endpoint: `POST /api/articles/{id}/reanalyze`

### 4.5 Transparency Report Visual Fixes (DONE)
- [x] Fix grey bars in Reliability Breakdown (handle null decomposed_confidence)
- [x] Fix DecomposedConfidenceChart for articles with missing data
- [x] Graceful fallback rendering when data is incomplete
- [x] Show "Analysis incomplete" state instead of broken visuals

### 4.6 URL Analysis / Submit Article Fixes (DONE)
- [x] Fix yle.fi and other JS-rendered site scraping (BeautifulSoup + semantic selectors)
- [x] Better error messages when URL fetch fails (status-specific explanations)
- [ ] Support for non-HTTPS URLs (with warning)
- [ ] Progress indicator during analysis

### 4.7 Article Summary Quality (PLANNED)
- [ ] Consistent 2-3 sentence summaries for all articles
- [ ] Re-generate summaries for existing articles with poor quality
- [ ] Summary quality scoring and validation

### 4.8 World Map Data Gaps (DONE)
- [x] Add RSS feeds for: US, UK, Spain, Portugal, Slovenia, Austria, Greece, Bulgaria, Hungary
- [ ] Backfill articles for underrepresented countries
- [ ] Show "No articles yet" vs "0 articles" distinction on map

## Phase 5: User Features (PLANNED)

### 5.1 User Authentication & Profiles
- [ ] Full login/register flow with email verification
- [ ] User profile page with settings
- [ ] Session management and token refresh
- [ ] Password reset flow

### 5.2 Save Favorites
- [ ] Bookmark articles, sources, and reports
- [ ] Saved items page with filters
- [ ] "Save to favorites" button on article cards and detail pages
- [ ] Database: `user_favorites` table

### 5.3 Subscription Queries / Alerts
- [ ] Subscribe to countries, themes, or sources
- [ ] Regular email digests (daily/weekly)
- [ ] In-app notification feed
- [ ] Custom alert rules (e.g., "notify me about disputed climate claims in Finland")

### 5.4 Stripe Subscription Billing
- [ ] Frontend Stripe integration for payment
- [ ] Tier-based feature gating (Free/Basic/Professional/Enterprise)
- [ ] Usage tracking dashboard per user

## Phase 6: Research & Advanced Analysis (PLANNED)

### 6.1 Research Paper Analysis
- [ ] Upload PDF or provide DOI/publisher link
- [ ] Extract claims from academic papers
- [ ] Cross-reference with climate databases
- [ ] Reliability assessment for research findings
- [ ] Support for preprints (arXiv, SSRN, etc.)

### 6.2 Local Weather/Climate Data Validation
- [ ] Cross-reference article claims with Open-Meteo historical data
- [ ] Validate temperature, precipitation, wind claims against actual measurements
- [ ] Show weather context alongside article claims
- [ ] "Does this claim match local weather patterns?" indicator
- [ ] Integration with Copernicus Climate Data Store

### 6.3 Advanced Visualizations
- [ ] Knowledge graphs showing claim relationships
- [ ] Pie/radar charts of themes discussed per article
- [ ] Source credibility network visualization
- [ ] Trend lines for claim categories over time
- [ ] Interactive evidence chain explorer

## Phase 7: Production Launch (PLANNED)

### 7.1 Security Hardening
- [ ] Rate limiting per user tier
- [ ] API key rotation
- [ ] CORS configuration for production domain
- [ ] Content Security Policy headers
- [ ] Input sanitization audit

### 7.2 Deployment
- [ ] Railway/Render deployment configuration
- [ ] Environment variable management
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Health check monitoring
- [ ] Backup strategy for PostgreSQL

### 7.3 Testing
- [ ] Backend unit tests (pytest) — target: 80% coverage
- [ ] Frontend component tests (Vitest) — currently 37 tests
- [ ] Integration tests for full pipeline
- [ ] E2E tests for critical user flows
- [ ] Load testing for API endpoints

---

**Note:** This roadmap is the single source of truth for all feature requests. If something isn't here, it hasn't been requested. Update this document when new requirements come in.
