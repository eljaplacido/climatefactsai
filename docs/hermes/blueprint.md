# 🏛️ Project Blueprint (Source of Truth)

This document is maintained by the Hermes agent and represents the recursive long-term memory of the project's architecture, conventions, and state.

_Last full sync: 2026-05-05. Header refreshed 2026-06-26 after the production-readiness audit._

> **Current snapshot (2026-06-26):** see `docs/improvementplans/Production-Readiness-Audit-2026-06-26.md`
> for the authoritative health scores (composite ≈ 3.0/5), the verified-blocker
> ledger, and what was fixed. The body of this blueprint below §1 predates that
> audit — treat the report as canonical where they disagree.

## 1. Project Overview

**Climatefacts.ai** (formerly CliLens.AI; CISU Regen ownership) — AI-powered climate news verification and intelligence platform.

- Worldwide coverage: ~194 UN-member countries across 9 regions (Europe, North/Central/Latin America, Africa, Asia, Middle East, Oceania, Central Asia)
- Per-country article ingestion + climate + weather data
- Fact-checking with CARF Cynefin framework + Bayesian credibility
- Interactive world map with topic density, source coverage, climate-risk and temperature-anomaly layers, and 7-dimension green-transition compare
- Deep search (Perplexity-style) with weather context auto-injection
- URL analysis with claim extraction and preliminary credibility scoring
- Agentic chat surface (map intelligence / article QA / research / general) with mode-aware routing
- Full-page Google Translate-style translation across 11+ languages
- User auth (JWT) with tier gating: Freemium / Standard (alias: Basic) / Professional / Enterprise

## 2. Core Architecture

**Stack**
- Backend: FastAPI (Python 3.12+), PostgreSQL + pgvector, Redis, Celery + Celery Beat
- Frontend: Next.js 14 App Router, TypeScript, Tailwind, Leaflet, Recharts
- Intelligence: DeepSeek (primary LLM, OpenAI-compatible) + Anthropic Claude (translation fallback) + ONNX embeddings
- External data: Open-Meteo (weather, free), NASA POWER (climate normals), Copernicus ERA5 (optional API key), Perplexity (deep search)
- 160+ RSS feeds via dynamic `rss_feed_registry` table + hardcoded fallback

**Directory layout (domain-driven design)**
```
api/                                  # FastAPI route modules (37+)
  main.py                             # app factory, CORS, security headers, route registration
  map_routes.py                       # /api/map/* — country stats, compare, layers, query
  green_transition_routes.py          # /api/green-transition/* — 7-dimension scoring
  deep_search_routes.py               # /api/deep-search/* — Perplexity + corpus synthesis
  url_analysis_routes.py              # /api/analyze-url — URL → claims → preliminary score
  chat_routes.py                      # /api/chat — mode-aware (map/article/research/general)
  rate_limiter.py                     # TIER_LIMITS, UsageTracker, RateLimitMiddleware
  ...
src/backend/app/
  domains/
    content/                          # ingestion, enrichment, sources
      data_sources/                   # rss_adapter, open_meteo_adapter, copernicus_adapter, etc.
      forecast_service.py             # COUNTRY_COORDS (199), COUNTRY_NAMES (200), ForecastService
      article_enrichment_service.py
      embedding_service.py
    intelligence/                     # LLM, RAG, claims, CARF, Cynefin
      llm_client.py                   # get_llm_client() — DeepSeek primary
      hybrid_rag_service.py           # FTS + pgvector RRF fusion
      deep_search_service.py
      bayesian_credibility.py
      cynefin_router.py
      transparency.py
    trust/                            # credibility models
  tasks/                              # Celery tasks (ingestion, processing, feed_scheduler)
src/frontend/src/
  app/                                # Next.js routes
  components/                         # AgenticAssistant, ContextualAssistant (auto-mounted via layout.tsx), GlobalNav, map/*, etc.
  lib/                                # api.ts, auth.tsx, i18n-context.tsx
scripts/                              # seed_global_sources.py, seed_full_global.py, seed_global_articles.py
tests/                                # api/, e2e/ (test_green_transition_e2e.py covers region coverage + compare + translation)
```

**Key conventions**
- All FastAPI routes register in `api/main.py` via `app.include_router(...)` blocks. Add new routers there.
- `REGION_COUNTRIES` (`api/map_routes.py`) and `COUNTRY_COORDS`/`COUNTRY_NAMES` (`forecast_service.py`) **must stay in sync** — every code in REGION_COUNTRIES needs matching coords/names or weather endpoints silently fail for that country.
- **`countries` reference table** must contain every code that will appear in `articles.country_code` (FK constraint `fk_articles_country`). When you add a code to REGION_COUNTRIES, regenerate `infrastructure/database/04_countries_seed.sql` from `forecast_service.COUNTRY_NAMES` so fresh DBs get it.
- Tier naming: `basic` is aliased to `standard` (`rate_limiter.py:82`). Code may receive either. Premium feature gates use `check_premium_feature()`.
- Default Docker port mapping: API exposes 8000 internally → host 5400. Frontend maps 3000 → 5300. `NEXT_PUBLIC_API_URL=http://localhost:5400`.
- LLM model names live in env vars (`DEEPSEEK_MODEL`, `ANTHROPIC_MODEL`) — never hardcode current model strings; they rot.
- **HTTPException raised inside `BaseHTTPMiddleware.dispatch` is wrapped by starlette's TaskGroup and surfaces as a 500.** `RateLimitMiddleware.dispatch` wraps `_dispatch` in a try/except that converts HTTPException to a JSONResponse — preserve this pattern in any new middleware.
- **Pydantic v2 strict response_model rejects implicit UUID→str coercion.** When a column is `uuid` in Postgres but the response model field is `str`, cast explicitly in the response factory (e.g. `analysis_id=str(row["analysis_id"])`).
- **DB schema migrations** must be runnable on a clean Postgres data volume — `db-init.sh` (mounted into `/docker-entrypoint-initdb.d/`) applies init.sql + 02 + 03 + 04_countries_seed + every `migrations/versions/*.sql` and pre-creates `vector`, `uuid-ossp`, `pg_trgm`. If you add a new migration file under `migrations/versions/`, it picks up automatically.
- **Topic terms are tagged inconsistently** across the corpus (LLM emits underscores, seed tags use hyphens, content_category uses underscores). Map-query handler now matches all separator variants. If you add a new topic-filter endpoint, normalize space/hyphen/underscore before querying.

## 3. Agentic Workflows

- **Top-level layout** (`src/frontend/src/app/layout.tsx`) renders `<ContextualAssistant />` globally inside `<ViewContextProvider>` (added 2026-04-30). ContextualAssistant inspects `pathname` and instantiates `<AgenticAssistant />` with the appropriate `currentPage` and `currentArticleId`.
- **View context layer** (added 2026-04-30): `src/frontend/src/lib/view-context.tsx` exports `ViewContextProvider`, `useViewContext`, `serializeViewContext`. Pages publish what's currently on screen (selected country, compare set, deep-search query/topics, URL-analysis jobId/articleId). AgenticAssistant pulls this state and posts it as a top-level `view_context` field to `/api/chat`, `/api/map/query`, `/api/articles/{id}/ask`. Backend (`api/chat_routes.py:_hydrate_view_context`) resolves IDs server-side (article body+claims, country aggregates, url_analyses row+claims, source_profile) and renders a `CURRENT VIEW` preamble in the system prompt so the LLM binds pronouns ("this article", "this country") to live state. Full spec: `docs/architecture/CHAT_VIEW_CONTEXT.md`.
- **AgenticAssistant** (`src/frontend/src/components/AgenticAssistant.tsx`) routes requests by mode:
  - `map_intelligence` → `POST /api/map/query` (LLM-parsed filters + answer with article citations)
  - `article_qa` → `POST /api/articles/{id}/ask`
  - everything else → `POST /api/chat` (general chat, hybrid RAG)
  - Cited articles open with `target=_blank` so chat session is preserved.
  - When the response includes `clarification_needed`, the assistant renders inline chips that re-submit the query when clicked.
- **Visualization layer** (added 2026-04-29):
  - `MethodologyDrawer.tsx` — collapsible "How this was answered" drawer consuming `methodology` from `/api/deep-search` responses. Used by deep-search page (search + compare modes).
  - `CompareCharts.tsx` — Recharts bar chart + similarities/differences cards. Activates when `comparative_analysis_structured` is present in the compare response; falls back to markdown otherwise.
  - `ClarificationChips.tsx` — amber chip strip rendered when a search returns zero results; clicking re-submits the search with the chip text.
  - **InteractiveClimateMap** "no coverage" countries: tooltip shows "Click to suggest a source"; click opens `/suggest-source?country=XX` in a new tab.
- **Chat enrichment**: chat_routes.py `/api/chat` calls `_get_platform_metrics(db)` (10-min cache) so the system prompt always reports live country/source counts. Mode `map_intelligence` extracts highlighted_countries from sources; `research_analysis` runs CynefinRouter.
- **Highlighted countries flow back to map**: AgenticAssistant calls the `onHighlightCountries` callback, used by `/map` page to update marker styling.
- **Session continuity**: chat_routes.py persists sessions in `chat_sessions` + `chat_messages` tables. session_id flows through query/response.
- **Hooks-based coordination** (per `CLAUDE.md`): Tasks should run claude-flow `pre-task`, `post-edit`, `post-task` hooks for memory coordination across sessions.

## 4. Current State

**Verified live after 2026-04-29 launch run** — `docker compose up` to a clean stack, full-stack smoke pass, visualization layer added.
**Updated 2026-04-30** — chat made view-aware, all mock/synthetic data fallbacks deleted from production paths, semantic-layer gap closed (KG entity extraction wired into ingestion), 127 new unit tests passing.

**Production-data discipline (2026-04-30 contract)**
- No production code path returns synthetic/placeholder data. Missing API keys → `RuntimeError` or `None`, never a fabricated payload.
- `forecast_service._fetch_copernicus_indicators` returns `None` without CDS key (was: synthetic seasonal sinusoid).
- `copernicus_adapter.fetch_era5_data` returns `None` until real CDS polling ships (was: placeholder envelope).
- `tasks/video.render_video_preview` marks jobs `DISABLED` with `video_url=None` (was: fake `videos.climatenews.local` URLs).
- `content_creation_service.content_creator.analyze_trends` computes from real article tags/countries/sources via Counter; missing API key raises `RuntimeError` (was: `_create_fallback_summary`).
- `content_creation_service/main.py` refuses to start without `PERPLEXITY_API_KEY` (was: `"demo"` literal accepted).
- `deep_search_service.methodology.embedding_model` reports `openai:text-embedding-ada-002` only when `OPENAI_API_KEY` is set, else `None` (was: hardcoded `"onnx-minilm"` lie).
- `scripts/populate_demo_articles.py`, `seed_full_global.py`, `seed_global_articles.py` gated behind `CLILENS_ALLOW_FAKE_SEED=1` AND refuse to run when `ENV=production` / `CLILENS_ENV=production`.
- Standalone mock API moved to `tests/fixtures/standalone_mock_api.py`; refuses to start unless `CLILENS_ALLOW_MOCK_API=1`.
- **Rule:** when adding a new feature that depends on an external service, never ship a "fallback" or "demo" payload. Either the dependency is configured or the feature surfaces as disabled/None.

**Country coverage (verified 2026-04-29)**
- REGION_COUNTRIES: **198 unique codes** across 9 regions (>=100% UN-state coverage)
- COUNTRY_COORDS: **199 entries** (capital lat/lon for weather/climate APIs)
- COUNTRY_NAMES: **200 entries**
- `countries` reference table: **201 rows** seeded from `infrastructure/database/04_countries_seed.sql` (auto-applied by `db-init.sh` on fresh DBs). Required because `articles.country_code` has FK to `countries`.
- Worldwide weather: Open-Meteo (free, no key) + NASA POWER + optional Copernicus ERA5
- Live seeded corpus: 3795 articles across 189 distinct country codes (49 → 189 once `countries` was filled)

**Feature surface (operational)**
- ✅ `/api/map/country-stats`, `/discussed-country-stats`, `/topic-density`, `/source-coverage`, `/regions`, `/available-sources`, `/available-themes`
- ✅ `/api/map/country/{cc}/detail` (article stats + weather + claim risk)
- ✅ `/api/map/country/{cc}/trends`, `/climate-data` (graceful degrade for missing coords)
- ✅ `/api/map/compare` (7 green-transition dimensions + climate-risk + topics + summary)
- ✅ `/api/map/timeline`, `/layers/temperature-anomaly`, `/layers/climate-risk`
- ✅ `/api/map/query` (LLM-parsed natural-language → map highlights with citations + session continuity)
- ✅ `/api/green-transition/country/{cc}`, `/leaderboard`, `/dimensions`, `/compare`
- ✅ `/api/deep-search`, `/compare`, `/intelligence-brief`, `/weather-context/{article_id}`, `/weather-location` — `/api/deep-search` and `/compare` now return a `methodology` block (queries_run, weather_used, synthesis_model, embedding_model, sources_consulted) and `clarification_needed` array for empty results. `/compare` also returns `comparative_analysis_structured` with summary/similarities/differences/evidence_strength/common_gaps for visual rendering.
- ✅ `/api/v2/sources` reads `source_profiles.reliability_tier` (added to schema 2026-04-29). `seed_full_global.py` backfills source_profiles from articles+source_credibility on each run, so the Sources page renders post-seed.
- ✅ `/api/analyze-url` (preliminary credibility from text length + claim importance heuristic; full verification runs in separate Celery pipeline)
- ✅ `/api/chat` (mode-aware, dynamic platform metrics in system prompt, hybrid RAG retrieval)
- ✅ `/api/translate/` (Anthropic primary via env-driven model + DeepSeek fallback)
- ✅ Translation: PageTranslator walks DOM, MutationObserver for dynamic content, batched POST /api/translate/

**Data ingestion**
- `feed_scheduler` Celery task respects per-tier frequency caps (freemium=daily, basic=12h, professional=6h, enterprise=hourly)
- RSS adapter prefers `rss_feed_registry` DB table; falls back to hardcoded `GLOBAL_CLIMATE_FEEDS` (13 sources)
- Dedup against existing URLs in `articles` table

**Tier matrix (rate_limiter.py)**

| Feature              | Freemium  | Standard/Basic | Professional | Enterprise |
|----------------------|-----------|----------------|--------------|------------|
| Articles/day         | 10        | 100            | unlimited    | unlimited  |
| URL analyses/month   | 0         | 5              | unlimited    | unlimited  |
| Searches/day         | 10        | 25             | 50           | unlimited  |
| Discovery queries/d  | 1         | 5              | 10           | unlimited  |
| Countries limit      | 3         | 5              | 10           | unlimited  |
| Auto-update freq.    | weekly    | daily          | daily        | realtime   |
| Source tiers         | public    | +research      | +scientific  | +scientific|
| Deep search          | basic     | basic          | full + brief | full + brief |
| Chat questions/day   | 5         | 25             | unlimited    | unlimited  |

## 5. Cloud Deployment Plan (GCP — provisioned 2026-05-05)

**GCP project**
- Name: `climatenews`
- Project ID: `climatenews-495412`
- Project number: `696885797915`
- Status: empty shell — no resources, services, or billing alerts configured yet.

**Target deployment shape (proposed, not yet decided)**
- **API + workers**: Cloud Run for FastAPI (stateless, HTTPS, auto-scale to zero) + Cloud Run Jobs for Celery beat/workers, OR GKE Autopilot if long-running Celery beat with high concurrency wins out. Cloud Run is the cheaper default; revisit if Celery scheduling latency becomes the bottleneck.
- **Postgres + pgvector**: Cloud SQL for PostgreSQL 16 with the `pgvector` extension (officially supported as of Cloud SQL PG15+). Private IP only; API connects via Cloud SQL Auth Proxy / Cloud SQL connector.
- **Redis**: Memorystore for Redis (standard tier with replica) for Celery broker + RateLimitMiddleware backing store + `_get_platform_metrics()` cache.
- **Object storage**: GCS bucket for video previews (when re-enabled), URL-analysis raw HTML snapshots, generated translation cache.
- **Secrets**: Secret Manager for `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `OPENAI_API_KEY`, `JWT_SECRET`, DB password. Mounted into Cloud Run via `--set-secrets`.
- **CDN + frontend**: Next.js to Cloud Run (SSR + ISR) behind Cloud CDN. Alternative: static export to GCS + CDN if SSR isn't needed for any route — verify, since translation and chat are client-driven.
- **Observability**: Cloud Logging + Cloud Trace; existing OTel exporter (currently noisy because jaeger:4318 is unreachable) re-pointed to Cloud Trace. Cloud Monitoring dashboards for the rate-limiter tier matrix.
- **CI/CD**: GitHub Actions → Artifact Registry → Cloud Run via Cloud Deploy. Two environments: `staging` (auto-deploy on `main` push) and `production` (manual approval gate).

**User-tied features & data residency planning**
- JWT auth already in place; tier matrix lives in `rate_limiter.py`. Cloud move adds: Identity Platform OR Firebase Auth as an SSO option (Google/GitHub/email); existing JWT issuance can sit alongside.
- Per-user data: `user_usage` (rate-limit counters), `chat_sessions` + `chat_messages`, future: saved deep-search briefs, saved compare snapshots, suggested-source submissions. All currently in the same Postgres — fine for v1; partition into a `user` schema only if compliance requires it.
- Data residency: pick a single region (recommend `europe-west4` Netherlands) for v1, given expected EU traffic + Dutch Open-Meteo provenance. Document in this blueprint when the decision is finalized.
- Billing tier upgrades: Stripe Checkout integration is not yet wired. When added, handler should write to `users.tier` AND invalidate `_get_platform_metrics()` + the user's rate-limit window in Redis.

**Migration sequence (when we're ready)**
1. Provision Cloud SQL + Memorystore in `europe-west4`; export current local Postgres via `pg_dump`, restore into Cloud SQL.
2. Build & push API + frontend images to Artifact Registry; deploy to Cloud Run staging with secrets mounted.
3. Run smoke tests against staging URL (same set as `lessons_learned.md` 2026-04-29 launch checklist).
4. Configure Cloud Scheduler triggers to replace Celery Beat (`feed_scheduler` per-tier cadence).
5. Cut DNS to production Cloud Run revision; keep local docker-compose stack as a dev / test target.

**Open questions for cloud planning**
- Do we keep DeepSeek (third-party) or move to Vertex AI Gemini for sovereignty + billing consolidation? Cost per 1M tokens favors DeepSeek today; latency from EU favors Gemini.
- Celery Beat → Cloud Scheduler migration: per-tier frequency caps need rewriting as cron expressions or as a single coordinator job that fans out.
- pgvector index strategy at scale: HNSW vs IVFFlat — currently uses default; needs benchmarking against ~50k+ articles target before cutover.

---
> **Note to Agents**: Always read this blueprint before beginning a major task. If you make architectural changes, you must update this document.
