# CliLens.AI — Feature Inventory & Audit (Phase 1)

**Date:** 2026-05-05
**Scope:** Read-only inventory of every user-facing and agentic feature, every API route, every data source adapter, every frontend page, every Celery task, every semantic-layer touchpoint.
**Builds on:** `production_audit_2026_04.md` (4-28), `production_audit_2026_04_30.md` (4-30).
**Cloud target:** GCP project `climatenews-495412` (likely `europe-west4`).

---

## Summary

The platform exposes **38 API routers**, **30 frontend pages**, **7 data-source adapters**, **16+ Celery tasks**, and a chat surface that's now view-aware end-to-end. Country coverage in code is **198 codes / 200 forecast coords / 198 seeded rows** (drift of +2 in forecast). Live corpus has articles in **189 of 198** countries.

The platform is functionally complete for core features. The audit surfaces three structural debts that block the Cloud Run cutover and one that blocks "95% country coverage with content":

1. **Localhost defaults** in `carf_integration.py` and `email_service.py` will silently break in Cloud Run.
2. **URL-analyzed claims** are trapped in `url_analyses.extracted_claims` JSONB and never reach the `claims` table — cross-corpus search and chat don't see them.
3. **Cynefin classification** runs but is never branched on — the `recommended_strategy` field is dead weight.
4. **9-country content gap** (189/198) — mostly small island states; ingestion needs a targeted backfill, not a structural fix.

Plus a known UI bug (AgenticAssistant `onClick` event leak), zero test coverage on ~10 routers, and an unimplemented vector search endpoint.

---

## 1. API Routers (38 files under `api/`)

| Router | Endpoints | Data sources | View-context wired? | Status |
|---|---|---|---|---|
| **chat_routes.py** | POST `/api/chat`, sessions | articles, embeddings, claims, url_analyses, source_profiles | ✅ `_hydrate_view_context` | OK |
| **map_routes.py** | `/api/map/*` (regions, country-stats, compare, query, layers) | articles, source_credibility, climate-data | ✅ via `MapQueryRequest.view_context` | OK |
| **deep_search_routes.py** | `/api/deep-search/*` (search, compare, intelligence-brief) | articles, embeddings, Perplexity, weather | partial | OK; methodology block present |
| **url_analysis_routes.py** | POST/GET `/api/analyze-url` | url_analyses, source_credibility | partial (`analysis_id` hydrated) | **claims not mirrored** |
| **carf_routes.py** | `/api/carf/classify`, `/analyze-article` | article_entities, entity_relationships | reads KG only | depends on stub at localhost:8000 |
| **green_transition_routes.py** | `/dimensions`, `/leaderboard`, `/country/{cc}`, `/compare` | articles, categories | none | OK |
| **forecast_routes.py** | `/api/forecast/{country}` | Open-Meteo, NASA POWER, COUNTRY_COORDS | none | OK |
| **search_routes.py** | `/api/search/articles` | FTS, claims | none | **no tests** |
| **feed_routes.py** | `/api/feed/*` | user_feed_preferences, articles | none | **no tests** |
| **discovery_routes.py** | `/api/discover/*` | articles, sources | none | **no tests** |
| **translation_routes.py** | `/api/translate/article`, `/api/translate/` | articles, translations | none | **no tests** |
| **similarity_routes.py** | `/api/similarity/articles` | (claims pgvector) | none | **stub — embeddings table has no writer** |
| **transparency.py** | `/api/transparency/report/{article_id}` | claims, entities, verification | none | OK |
| **v2/sources.py** | `/api/v2/sources/*` | source_profiles | none | OK |
| **v2/intelligence.py** | `/api/v2/intelligence/*` | claims, verification | none | OK |
| auth, oauth, user, subscription, api_key, saved_query, advanced_filter, activity, conversation, research, analytics, source_registry, source_suggestion, admin_pipeline, article_ingestion, export, og_image, infographic, benchmark, email | (standard) | various | none | OK |

---

## 2. Data Source Adapters (`src/backend/app/domains/content/data_sources/`)

| Adapter | Type | API key? | No-key behavior |
|---|---|---|---|
| `rss_adapter.py` | RSS parser + `GLOBAL_CLIMATE_FEEDS` fallback | no | falls back to hardcoded feed list |
| `open_meteo_adapter.py` | Weather (free) | no | None on HTTP error |
| `copernicus_adapter.py` | ERA5 climate | yes (CDS) | **returns None** (placeholder envelope deleted 4-30) |
| `ecmwf_adapter.py` | Multi-source aggregator | mixed | cascading partial |
| `eu_feeds_registry.py` | Feed registry helper | no | empty list |
| `document_adapter.py` | PDF/document parser | no | None |
| `__init__.py` | Module exports | — | — |

All free adapters fail-soft to None; `copernicus_adapter` was a notable mock-elimination target on 4-30 and now correctly returns None until the real CDS polling ships.

---

## 3. Frontend Pages (30 routes under `src/frontend/src/app/`)

Pages publishing into `view-context` (the chat-aware ones):
- **`map/page.tsx`** — `selectedCountry`, `compareCountries`, region.
- **`deep-search/page.tsx`** — query, compare topics, country.
- **`articles/[id]/page.tsx`** — `article_id`.
- **`articles/[id]/transparency/page.tsx`** — retains `article_id` for the sub-route.
- **`components/UrlAnalysisForm.tsx`** (mounted on `/analyze`) — `analysisId` (jobId) during processing, `articleId` after completion.

Other pages render but don't publish view state: home, search, feed, dashboard, dashboard/{settings,history,saved,subscription}, forecasts, sources, research, analyze (host), admin, admin/pipeline, admin/analytics, auth/callback, login, signup, forgot-password, suggest-source, about, methodology.

---

## 4. Agentic / Chat Components

| Component | File | Role |
|---|---|---|
| `ViewContextProvider` | `lib/view-context.tsx` | shared store; `useViewContext`, `serializeViewContext` |
| `ContextualAssistant` | `components/ContextualAssistant.tsx` | derives `currentPage` from pathname; mounts `AgenticAssistant` |
| `AgenticAssistant` | `components/AgenticAssistant.tsx` | mode router (`map_intelligence`, `article_qa`, `research_analysis`, general); posts `view_context` |
| `MapAgenticChat` | `components/map/MapAgenticChat.tsx` | inline chat on map; injects `selectedCountry`, `compareCountries` |
| `MethodologyDrawer` | `components/MethodologyDrawer.tsx` | "How this was answered" — consumes `methodology` from deep-search |
| `CompareCharts` | `components/CompareCharts.tsx` | Recharts bars + similarities/differences cards from `comparative_analysis_structured` |
| `ClarificationChips` | `components/ClarificationChips.tsx` | amber chips when results are empty; click resubmits |
| `_hydrate_view_context` | `api/chat_routes.py` | server-side resolution of view IDs into prompt content |
| `_format_view_context_block` | `api/chat_routes.py` | renders `CURRENT VIEW` preamble |
| `CynefinRouter` | `domains/intelligence/cynefin_router.py` | classifies; **result not branched on** |

---

## 5. Celery Tasks (`src/backend/app/tasks/`)

| Task | File:line | Schedule | Side-effects | Cloud Run risk |
|---|---|---|---|---|
| `discover_articles` | ingestion.py:205 | 10/min | INSERT articles + url_analyses; embedding + entity extraction inline | OK |
| `scheduled_multi_country_ingestion` | ingestion.py:286 | beat | chains discover_articles | OK |
| `scheduled_rss_ingestion` | ingestion.py:343 | beat | RSS fetch + dedupe | OK |
| `poll_rss_feeds` | ingestion.py:399 | 2/min | INSERT articles | OK |
| `scheduled_scientific_feed_ingestion` | ingestion.py:553 | beat | specialized RSS | OK |
| `verify_claims` | processing.py:21 | retry 3 | UPDATE articles, write claims/verdicts | OK |
| `create_summary` | processing.py:64 | retry 3 | summary + `EntityExtractionService.extract_and_store` (KG writer) | OK |
| `auto_verify_pending_articles` | fact_check_pipeline.py:25 | 3/min | UPDATE claims | OK |
| `retry_failed_verifications` | fact_check_pipeline.py:240 | retry 1 | re-verify | OK |
| `pipeline_health_check` | fact_check_pipeline.py:301 | beat | logs only | OK |
| `update_user_feeds` | feed_scheduler.py:98 | per-tier | UPDATE user_feed_preferences | OK |
| `translate_article` | translation.py:106 | retry 3 | UPDATE translations | OK |
| `batch_translate_recent` | translation.py:224 | beat | bulk translation | OK |
| `render_video_preview` | video.py:22 | retry 3 | DISABLED (no `videos.climatenews.local` URLs anymore) | needs GCS when re-enabled |
| `publish_article` | publication.py:18 | retry 3 | UPDATE articles.published_at | OK |

**Cloud Run divergence:** Celery Beat (long-running) does not survive scale-to-zero. Migrate the `beat` schedules to Cloud Scheduler with cron expressions matching the per-tier frequency caps in `rate_limiter.TIER_LIMITS`.

---

## 6. Semantic Layer

**Writers:**
- `entities`, `entity_relationships`, `article_entities` ← `EntityExtractionService.extract_and_store()` from `create_summary` (`processing.py:create_summary`) and `_insert_discovered_articles` (`ingestion.py`). Wired 2026-04-30.
- `claims` ← `VerificationService.verify_article()` in `verify_claims` task.
- `embeddings` (article-level pgvector column) ← `populate_embedding` in `processing.py`.

**Readers:**
- KG: `carf_routes.py` reads `entities` + `article_entities` + `entity_relationships`.
- `claims`: search_routes, articles aggregate, transparency report.
- pgvector article embeddings: `hybrid_rag_service.py` for FTS+vector RRF fusion in chat / deep-search.

**Gap (the big one):** `url_analyses.extracted_claims` (JSONB, written by `url_analysis_routes.py`) is never mirrored into the `claims` table. The chat hydrator reads `url_analyses` directly via `analysis_id`, so the immediate UX works, but **deep-search, hybrid RAG, transparency cross-references, and KG entity linking all miss URL-submitted claims**. This is Phase 3's primary fix.

**Stub:** `similarity_routes.py` exposes a similarity endpoint but no implementation backs it. Either delete the route or wire it to the existing pgvector index on `articles`.

---

## 7. Mock / Synthetic / Hardcoded Sniff (production paths only)

Most of the synthetic-data sins were excised on 4-30. What remains:

| File:line | Pattern | Severity |
|---|---|---|
| `carf_integration.py:26` | `CARF_BASE_URL = os.getenv(..., "http://localhost:8000")` | **HIGH** — won't reach anything in Cloud Run |
| `carf_integration.py:81,90-111` | `_fallback_classify` keyword heuristic for Cynefin | medium — explicitly labeled fallback |
| `email_service.py:28` | `FRONTEND_URL = "http://localhost:5300"` | **HIGH** — password reset / invites break in Cloud Run |
| `chat_routes.py:359` | "HybridRAGService not available, using FTS fallback" log | medium — graceful degrade |
| `ingestion.py:366` | hardcoded fallback RSS feeds when `rss_feed_registry` is empty | low |
| `url_analysis_routes.py:319` | "Final fallback: full body text" | low — best-effort content extraction |

Scripts under `scripts/` (`seed_*`, `populate_demo_articles`) and `tests/fixtures/standalone_mock_api.py` remain gated behind `CLILENS_ALLOW_FAKE_SEED=1` / `CLILENS_ALLOW_MOCK_API=1` and refuse production env. ✅

---

## 8. Test Coverage Map

**Covered (`tests/api/`):**
auth, chat, chat_view_context, deep_search, map, url_analysis, article, green_transition.

**Covered (`tests/e2e/`):**
full_pipeline, map_and_agentic, multi_country (198-country reachability), green_transition, production_readiness, platform smoke, translations_and_benchmarks.

**Frontend (`src/frontend/src/__tests__/`):**
AgenticAssistant, ContextualAssistant, MapAgenticChat, MapCountryPanel, lib/view-context.

**Zero coverage:** `carf_routes`, `discovery_routes`, `feed_routes`, `forecast_routes`, `search_routes`, `similarity_routes`, `source_registry_routes`, `translation_routes`, `analytics_routes`, `subscription_routes`, `transparency` (route-level — internals are tested elsewhere).

**Pre-existing failures:** `tests/pages/HomePage.test.tsx`, `tests/pages/SearchPage.test.tsx` — unrelated to recent waves.

---

## 9. Country Coverage — Actual State

| Source | Count | Notes |
|---|---|---|
| `infrastructure/database/04_countries_seed.sql` | **198 country rows** (single multi-row INSERT in 202-line file) | seeded by `db-init.sh` on fresh DB |
| `api/map_routes.py` `REGION_COUNTRIES` union | **198 unique codes** | matches seed |
| `forecast_service.py` `COUNTRY_COORDS` | **200 entries** | +2 drift — likely placeholder + duplicate |
| `forecast_service.py` `COUNTRY_NAMES` | **200 entries** | matches coords |
| Live articles | **189 distinct country codes** | 9-country content gap |

The 9 missing-content countries are most likely small island states / micro-nations where RSS coverage is genuinely thin. Phase 2 needs to either (a) backfill them via targeted Perplexity ingestion or (b) drop the threshold and accept 95.4% (189/198) as the floor.

---

## 10. Top Findings — Punch List

| # | Severity | Finding | Where | Phase |
|---|---|---|---|---|
| 1 | **CRITICAL (cloud)** | CARF base URL defaults to `localhost:8000` | `carf_integration.py:26` | 5 (cloud planning) |
| 2 | **CRITICAL (cloud)** | Email service `FRONTEND_URL` hardcoded localhost | `email_service.py:28` | 5 |
| 3 | **HIGH** | URL-analysis claims trapped in JSONB; not in `claims` table | `url_analysis_routes.py` writes; readers miss | 3 |
| 4 | **HIGH** | `CynefinRouter` classifies but `chat_routes.py` doesn't branch | `chat_routes.py:206-208` | 3 |
| 5 | **HIGH** | `AgenticAssistant.handleSend` onClick event leak crashes mouse path | `AgenticAssistant.tsx:169` | 4 |
| 6 | **MEDIUM** | Redis hardcoded localhost (Celery broker + rate limiter) | `celery_config.py`, `redis_client.py` | 5 |
| 7 | ~~MEDIUM~~ **CORRECTED** | ~~`similarity_routes.py` is a stub~~ — actually wired to `EmbeddingService.find_similar()` (`embedding_service.py:193`); pgvector implementation is real. Audit agent was wrong on this finding. | n/a | — |
| 8 | **MEDIUM** | COUNTRY_COORDS = 200 vs seed = 198; +2 drift | `forecast_service.py` | 2 |
| 9 | **MEDIUM** | ~10 routers have zero test coverage | see § 8 | 4 |
| 10 | **LOW** | 9-country content gap (189/198 = 95.4%) | live data | 2 |

---

## Phase 2-6 Recommendation

The audit confirms the original 6-phase plan is right, and lets me sharpen each phase:

- **Phase 2 (Country coverage to 95%):** Already at 95.4% (189/198). Either (a) accept and add a CI guard at 95%, or (b) targeted Perplexity backfill for the 9 missing countries. Also fix the `COUNTRY_COORDS` +2 drift. **~2 hours.**
- **Phase 3 (Semantic-layer alignment):** URL-claims → mirror to `claims` table + `articles is_user_submitted=true`; either delete or implement `similarity_routes.py`; make `CynefinRouter` actually route by domain. **~3-4 hours.**
- **Phase 4 (Test hardening):** Fix the `AgenticAssistant` onClick bug, fix the 2 pre-existing page-test failures, add API tests for the 10 untested routers, add Playwright E2E. **~4-6 hours.**
- **Phase 5 (Doc + cloud-prep):** Externalize `CARF_BASE_URL`, `FRONTEND_URL`, Redis URL into env-driven config that defaults to localhost in dev but **errors on missing-in-prod**. Update README, CHAT_VIEW_CONTEXT.md, agent skill prompts. **~2-3 hours.**
- **Phase 6 (Launch + smoke):** `docker compose up`, run full backend pytest + frontend vitest + Playwright; capture results report. **~1 hour.**

Total: roughly **12-16 hours of agent execution** across Phases 2-6.
