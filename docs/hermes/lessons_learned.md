# 📜 Lessons Learned & Insights

This document is maintained by the Hermes agent. It stores the project's historical knowledge, preventing agents from repeating past mistakes and preserving long-term progress context.

## 2026

### 2026-05-05 — Wave A: Semantic-Layer Alignment + Country Discipline

Builds on the 2026-05-05 feature inventory audit (`docs/audits/2026-05-05_feature_inventory.md`). Closed the URL-claim semantic-layer gap, made Cynefin classification actionable, fixed the HK drift in REGION_COUNTRIES, and added a CI guard for country-coverage discipline. 16 new tests pass; 1 skipped (live-DB coverage floor — runs in CI when `CLILENS_ASSERT_LIVE_COVERAGE=1`).

**URL-claim mirror (the big one).** Migration 016 (`infrastructure/database/migrations/versions/016_url_claim_mirror.sql`) adds `articles.is_user_submitted`, `articles.url_analysis_id` (FK + index), `claims.importance_score`, `claims.source_kind` (`'corpus'` vs `'url_analysis'`). New helper `_mirror_url_analysis_to_corpus` in `api/url_analysis_routes.py:383` upserts the analyzed page into `articles` keyed on URL (UNIQUE), then INSERTs each extracted claim into the `claims` table with `source_kind='url_analysis'`. Wrapped in try/except — mirror failures must never break the URL analysis. Best-effort embedding population is awaited inline (skipped when no `OPENAI_API_KEY`). After this, deep-search, hybrid RAG, and transparency cross-references see URL-submitted claims like any other. **Rule:** any new entrypoint that produces claims must mirror them into the canonical `claims` table — JSONB-only storage is invisible to the rest of the platform.

**Cynefin made actionable.** `api/chat_routes.py:_generate_answer` now accepts a `cynefin` kwarg and injects domain-specific guidance into the system prompt: `direct_lookup` → "answer concisely, do not speculate"; `multi_source_analysis` → "cross-reference at least two sources, structure as claim → evidence → uncertainty"; `causal_analysis` → "trace cause-effect, surface counterfactuals, quote confidence ranges"; `rapid_assessment` → "lead with the actionable fact, flag every uncertainty, do not synthesise a tidy narrative". Only activates in `mode=research_analysis` — other modes ignore the classification, as designed. **Lesson:** when a classifier's output is added to the response payload but never branched on, it's dead weight that creates the *appearance* of intelligence without the substance. Treat "we return X to the client" and "X actually steers behaviour" as distinct review checkboxes.

**HK drift fixed.** `HK` was in COUNTRY_COORDS / COUNTRY_NAMES / `04_countries_seed.sql` but missing from `REGION_COUNTRIES.asia` — added. `XX` (the cross-border / international placeholder) is now documented in `tests/api/test_country_coverage.py::ALLOWED_EXTRAS`.

**Country-coverage discipline guard.** New `tests/api/test_country_coverage.py` enforces three invariants permanently: (1) every REGION_COUNTRIES code has matching coords + name + seed entry; (2) coords ↔ names agree (modulo allow-listed extras like XX); (3) every region bucket non-empty. Plus a live-coverage floor: `CLILENS_ASSERT_LIVE_COVERAGE=1` makes <95% article coverage of REGION_COUNTRIES codes a CI hard-fail.

**Audit correction.** The 2026-05-05 Phase 1 audit (Explore agent) flagged `similarity_routes.py` as a stub. **It is not** — it calls `EmbeddingService.find_similar()` which has a real pgvector implementation at `embedding_service.py:193`. Always verify Explore-agent claims about "this code does nothing" by reading the implementation, not just the route handler.

### 2026-05-05 — GCP Cloud Project Provisioned

GCP project `climatenews-495412` (number `696885797915`) created as the future home for production deployment. Empty shell — no services enabled, no billing alerts, no Cloud SQL / Memorystore / Cloud Run yet. Decision deferred on:
- Region (leaning `europe-west4` for EU residency + Open-Meteo provenance, but not finalized)
- Whether to keep DeepSeek third-party or migrate intelligence pipeline to Vertex AI Gemini
- pgvector index strategy at scale (HNSW vs IVFFlat) — needs benchmark before cutover
- Celery Beat → Cloud Scheduler rewrite for per-tier feed frequency caps

**Lesson captured up-front (not from incident yet):** the local docker-compose stack and Cloud Run will diverge on three concrete points the existing code already encodes — (1) Cloud Run is stateless so any in-process cache (`_get_platform_metrics`'s 10-min TTL) needs to be backed by Redis when traffic spans multiple revisions; (2) Cloud Run scales to zero, so the first request after idle pays cold-start; gate `feed_scheduler` to Cloud Scheduler instead of relying on a long-running container; (3) `BaseHTTPMiddleware.dispatch` HTTPException-wrapping (RateLimitMiddleware) must keep its try/except converter — the failure mode (429 → 500) is invisible until a load test catches it. **Rule:** before the cloud cutover, write a load-test that explicitly fires anonymous traffic past the rate limit and asserts a 429 (not 500) is returned.

See `docs/hermes/blueprint.md` § 5 (Cloud Deployment Plan) for the full proposed architecture.

### 2026-04-30 — Mock Elimination + View-Aware Chat + Semantic-Layer Wiring

End-to-end audit + fix wave. Three concurrent objectives: (a) zero synthetic data in production paths, (b) chat that can see what the user is currently viewing, (c) ingestion → embedding → KG chain wired end-to-end. 127 new unit tests landed at 100% pass.

**Mock/synthetic data — surgically removed.** Every "fallback" payload that fabricated data when an external service was unavailable is gone. `forecast_service._fetch_copernicus_indicators` (synthetic seasonal sinusoid), `copernicus_adapter.fetch_era5_data` (placeholder envelope), `tasks/video.render_video_preview` (fake `videos.climatenews.local` URLs), `content_creator._create_fallback_summary`, `content_creation_service/main.py`'s `"demo"` literal, and `deep_search_service.methodology.embedding_model = "onnx-minilm"` (which lied — no ONNX MiniLM was running) — all replaced with `None` / `RuntimeError` / `DISABLED` markers. Seed scripts gated behind `CLILENS_ALLOW_FAKE_SEED=1` and refuse to run when `ENV=production`. **Rule:** when a feature depends on an external service, ship it as disabled when the service is unavailable, not as a fabricated payload. Demo data lives behind explicit env gates outside production.

**Chat view-context plumbing.** Frontend now publishes everything currently on screen (route, selected country, compare set, deep-search query+topics, URL-analysis jobId/articleId, source label) through `ViewContextProvider` (`src/frontend/src/lib/view-context.tsx`). `AgenticAssistant` posts it as a top-level `view_context` field. Backend (`api/chat_routes.py:_hydrate_view_context`) resolves IDs server-side — article body+claims, country aggregates, url_analyses row+claims, source_profile — and renders a `CURRENT VIEW` preamble in the system prompt so pronouns ("this article", "this country", "these results") bind to live state. `api/map_routes.py:MapQueryRequest` also accepts `view_context`; promotes `country` / `compare_countries` into the retrieval filter when no explicit countries are passed. Full spec: `docs/architecture/CHAT_VIEW_CONTEXT.md`.

**Semantic-layer chain closed.** Before this wave, the KG (`entities`, `entity_relationships`) had a schema and a reader but no writer — ingestion never populated it. Now `tasks/processing.py:create_summary` runs `EntityExtractionService.extract_and_store` next to `populate_embedding`, and `tasks/ingestion.py:_insert_discovered_articles` enriches newly discovered articles inline (embedding + entity extraction, best-effort). **Rule:** every ingestion-stage enrichment must be reachable from both the bulk processing path (`create_summary`) AND the inline discovery path (`_insert_discovered_articles`); otherwise, articles ingested via different routes get inconsistent enrichment.

**Known follow-ups left open after this wave:**
- URL-analysis claims still in `url_analyses.extracted_claims` JSONB. Chat hydrator reads from `url_analyses` directly via `analysis_id` so the immediate UX works, but cross-corpus claim search misses them. Mirror into `claims` + create an `articles` row with `is_user_submitted=true`.
- `AgenticAssistant.handleSend` is wired as `onClick={handleSend}` so the click event leaks into `overrideText` and crashes on `.trim()`. Enter-key path works; mouse click does not. Tests sidestep via key event. Latent — fix before public launch.
- CARF integration still defaults to localhost:8000 stub; either ship a CARF service in compose or strip the proactive claims.
- CynefinRouter classifies but `chat_routes.py` doesn't branch on `recommended_strategy` — make it actionable.
- FTS path of `/api/map/query` uses `to_tsvector('english', ...)`; Finnish/multilingual articles miss matches. Switch to `simple` config or rely on embeddings.
- `tests/pages/HomePage.test.tsx`, `SearchPage.test.tsx` have 2 pre-existing failures unrelated to this wave.
- Project venv at `venv/` lacks pytest etc.; system Python has the deps installed instead.

**Lesson on test discipline:** the audit wave that *deleted* fallback code paths needed test coverage to prevent regression — i.e., a test that asserts `forecast_service._fetch_copernicus_indicators` returns `None` (not a fabricated dict) when `CDS_API_KEY` is absent. Without that assertion, a future "let's restore the demo data so the page doesn't look empty" PR re-introduces the lie. **Rule:** when removing a fallback, the test for that path must assert *what the no-data state looks like*, not just "no exception raised".

### 2026-04-29 — Live Launch + Visualization Layer

The 2026-04-28 audit was a paper-only sweep — code was reviewed and patched but the stack was never brought up to verify end-to-end. The 2026-04-29 session ran `docker compose up` against a fresh data volume and immediately uncovered ~7 schema and runtime bugs the prior pass missed. Fixed:

- **DB schema didn't actually apply on a fresh volume.** Compose mounted only `init.sql`, so `chat_sessions`, `entities`, `user_usage`, `articles.insight_summary`, `articles.enriched_excerpt`, and `source_profiles.reliability_tier` were all missing. **Fix:** new `infrastructure/database/db-init.sh` applies init + 02 + 03 + 04_countries_seed + every numbered migration in `migrations/versions/`; pre-creates `vector`, `uuid-ossp`, `pg_trgm`. **Rule:** every schema change must be reachable from `db-init.sh`. Fresh-volume launch is the integration test.
- **`articles.country_code` FK to `countries` silently drops seed inserts.** Only ~52 country rows existed → seed_full_global landed 49 countries instead of the targeted 198. **Fix:** `infrastructure/database/04_countries_seed.sql` generated from `forecast_service.COUNTRY_NAMES` (200 entries, deterministic flag emoji). After seed: 3795 articles across 189 countries. **Rule:** when REGION_COUNTRIES grows, regenerate 04_countries_seed.sql.
- **HTTPException → 500 inside BaseHTTPMiddleware.dispatch.** A 429 raised inside `RateLimitMiddleware` was wrapped by starlette's TaskGroup and surfaced to the client as a 500 — anonymous URL analysis appeared broken. **Fix:** wrap `_dispatch` in a try/except that converts HTTPException to a JSONResponse. **Rule:** any new BaseHTTPMiddleware that raises HTTPException must follow the same pattern.
- **Pydantic v2 strict response_model rejects implicit UUID coercion.** `URLAnalysisDetail.analysis_id: str` rejected the `uuid.UUID` value coming back from psycopg2 with a 500 — even though the row was valid. **Fix:** cast `str(result["analysis_id"])` in the response factory. **Rule:** any UUID column going into a `str` field needs an explicit cast.
- **Anonymous user_id sentinel string failed UUID column.** UsageTracker passed `"anonymous"` to `user_usage.user_id` (uuid). Error was swallowed; rate-limit gate silently disabled for anon. **Fix:** `_coerce_user_uuid()` returns None for non-UUID input; `log_usage`/`get_usage_count` short-circuit; anon traffic falls back to IP-based limiter as designed. **Rule:** never pass arbitrary strings to UUID columns; coerce explicitly.
- **Map-query topic separator drift.** LLM emits `"renewable energy"` (space), seed tags use `"renewable-energy"` (hyphen), `content_category` uses `"renewable_energy"` (underscore). The `:topic = ANY(a.tags)` filter matched none of them → "0 articles" answers despite 995 in DB. **Fix:** generate every separator variant and match against `tags && variants OR content_category = ANY(variants)`. **Rule:** any topic filter that crosses LLM output ↔ stored data must normalize separators.
- **`/api/v2/sources` selected `source_profiles.reliability_tier` — a column only on `source_credibility`.** 500'd until added. **Fix:** ALTER TABLE in `apply_all_migrations.sql` so fresh DBs get it. **Rule:** when copying SQL between tables, verify column existence on the actual target.

**Visualization layer landed in the same session:**

- `/api/deep-search` and `/compare` now return `methodology` (queries_run, weather_used, synthesis_model, embedding_model, sources_consulted) and `clarification_needed` (3 LLM-suggested scope refinements when results are empty). Compare also returns `comparative_analysis_structured` with summary/similarities/differences/evidence_strength/common_gaps.
- Three new frontend components: `MethodologyDrawer.tsx`, `CompareCharts.tsx` (Recharts), `ClarificationChips.tsx`. Wired into deep-search page; AgenticAssistant chat also renders chips inline when API surfaces them. Cited-article links open `target=_blank` so chat history isn't wiped.
- Map: countries with `article_count === 0` route clicks to `/suggest-source?country=XX` (new tab) instead of opening an empty country panel.

**Lesson on agentic skill design:** the pre-launch audit narrative ("production-ready") created false confidence. The real test was always going to be the first `docker compose up` against a fresh volume. From now on, treat fresh-stack launch as the audit's exit criterion, not a separate task.

### 2026-04-28 — Production Audit & Polish

End-to-end audit of all platform surfaces. Fixed worldwide coverage gaps, stale prompts, hardcoded model names, fabricated URL-analysis scores. See `memory/production_audit_2026_04.md` for the full punch list.

### General Insights

- **REGION_COUNTRIES ↔ COUNTRY_COORDS drift is the silent killer.** `api/map_routes.py:230` lists countries by region; `src/backend/app/domains/content/forecast_service.py` holds capital coords. When they fall out of sync, `/api/map/country/{cc}/climate-data`, `/api/forecast/country/{cc}`, and the temperature-anomaly map layer all silently fail or 404 for the missing countries — but no test catches it because the regions test only verifies REGION_COUNTRIES, not coord coverage. **Rule:** every code added to REGION_COUNTRIES must also land in `COUNTRY_COORDS` and `COUNTRY_NAMES` in the same PR. As of 2026-04-28 these dicts hold 198/199/200 entries respectively and are aligned.

- **Hardcoded model names rot fast.** `api/main.py:386` had `claude-sonnet-4-20250514` — a model name from May 2025. By April 2026 it was 11 months stale. Same pattern would have hit `chat_routes.py` if not caught. **Rule:** all LLM model names go through env vars (`ANTHROPIC_MODEL`, `DEEPSEEK_MODEL`) with sensible current defaults. Never inline the dated model string.

- **System prompts hardcode counts at your peril.** `chat_routes.py` system prompt said "136 countries" and "277 sources". As ingestion scales, those numbers drift and the assistant lies to users. **Rule:** when a number can change, fetch it live (TTL-cached). `_get_platform_metrics()` does this with a 10-minute cache against the `articles` table.

- **Anonymous URL analysis without verification is misleading.** `url_analysis_routes.py` previously returned `reliability_score=50, MEDIUM` for every URL because the full verification pipeline wasn't being invoked from the synchronous handler. Users saw a "MEDIUM credibility" badge that was completely fabricated. **Rule:** scoring fields exposed to the UI must reflect *something real*. The current heuristic uses text length + claim count + average claim importance. The full claim-by-claim verification still runs as a separate Celery pipeline; the synchronous response is now labelled "preliminary" in the code comment.

- **Tier naming alias `basic` ≡ `standard` is fragile.** `rate_limiter.py:82` does `TIER_LIMITS["basic"] = TIER_LIMITS["standard"]`. Most code paths read both, but new code that only checks one of them will misbehave. **Rule:** always use `TIER_LIMITS.get(tier, TIER_LIMITS["freemium"])` rather than `TIER_LIMITS[tier]` directly, so unknown tiers fall through safely.

- **REGION_COUNTRIES.asia includes middle_east intentionally.** UN definition of Asia includes Middle Eastern countries. The two regions overlap on AE/SA/IL/JO/LB/IQ/IR/QA/KW/OM/BH/YE/SY/PS. This is a hierarchical relationship, not a bug. Filtering by `region=asia` returns Middle Eastern coverage too.

- **`localhost:5400` is the correct frontend → API URL.** Docker maps internal API:8000 to host:5400, frontend 3000 → 5300. CORS_ORIGINS in `api/main.py` defaults to `localhost:3000,5173,5300` — these are the *frontend* origins, not the API host. Don't add 5400 to CORS_ORIGINS.

- **`api/main.py` has a UTF-8 BOM at byte 0.** Pre-existing. Python's tokenizer handles it transparently. `ast.parse()` from a string read with default encoding errors out, but `open(..., encoding='utf-8-sig')` fixes that. Don't try to "fix" the BOM — IDE saves can re-introduce it; downstream behavior is correct.

- **PageTranslator + MutationObserver = full-page translation works.** `src/frontend/src/components/PageTranslator.tsx` walks all text nodes, batches via 300ms debounce to `/api/translate/`. Don't try to translate per-component — the global walker already covers dynamic content.

- **AgenticAssistant routes by `currentPage` + `currentArticleId`**, not by URL pattern matching inside the assistant. `ContextualAssistant.tsx` does the URL → page-name mapping. To add a new mode, extend `MODE_LABELS` and `EXAMPLE_QUERIES`/`PAGE_HELP` in `AgenticAssistant.tsx` and update `ContextualAssistant` to recognize the new path.

- **DeepSeek-only for intelligence, Anthropic-optional for translation.** `llm_client.py` is the gateway for claim extraction, fact-checking, RAG synthesis, chat. `api/main.py` translation tries Anthropic first (longer context windows) and falls back to DeepSeek. Don't introduce Anthropic into the intelligence pipeline — it would split the cost/latency profile.

### Bug History

- **Worldwide weather coverage was broken for ~24 countries (2026-04-28)**: `COUNTRY_COORDS` was missing Bhutan, Maldives, Belize, Bahamas, Barbados, Kosovo, San Marino, and 18 African nations (Benin, Burundi, Cape Verde, CAR, Comoros, Congo, Djibouti, Eq. Guinea, Gabon, Gambia, Guinea, Guinea-Bissau, Lesotho, Liberia, Mauritania, Mauritius, Eswatini, Togo, Sierra Leone). `/api/forecast/country/{cc}` returned "Unsupported country", `/api/map/country/{cc}/climate-data` 404'd, temperature-anomaly map layer silently skipped them. **Fix:** added all to COUNTRY_COORDS + COUNTRY_NAMES, made climate-data graceful (empty payload instead of 404), added debug log when temp-anomaly skips. **Prevention:** if a country is in REGION_COUNTRIES, add it to both dicts in the same change.

- **URL analysis fabricated credibility scores (2026-04-28)**: `url_analysis_routes.py:491-493` hardcoded `reliability_score = 50; overall_credibility = 'MEDIUM'` regardless of input. **Fix:** replaced with text-length + claim-count + avg-importance heuristic. **Prevention:** never expose a numeric score field to UI without it being computed from input data.

- **Stale platform stats in chat system prompt (2026-04-28)**: chat_routes.py said "136 countries" and "277 sources" — values from initial seed, no longer accurate. **Fix:** added `_get_platform_metrics()` with 10-min TTL cache that pulls live counts. **Prevention:** any factual claim in a system prompt should either be derived from live data or be intentionally vague ("a curated set of sources").

- **Outdated Anthropic model `claude-sonnet-4-20250514` (2026-04-28)**: hardcoded model name was 11 months stale. **Fix:** env-driven via `ANTHROPIC_MODEL` with current default. **Prevention:** never inline a dated model string. Use `os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")` pattern.

- **`rss_adapter.py` comment said "9 international sources" but dict had 13 (2026-04-28)**: cosmetic doc drift, but signals lack of review discipline. **Fix:** changed comment to non-numerical phrasing. **Prevention:** if you add to a dict, count it before re-asserting count in a comment.

- **`AgenticAssistant.tsx` imported unused `X` icon (2026-04-28)**: minor lint warning. **Fix:** removed import. **Prevention:** run `npm run lint` before merging frontend changes.

### 2026-06-26 — Production-Readiness Audit (10-dimension, 36-agent + adversarial verify)

- **SQL injection via f-string + hand-rolled `''` escaping (TRUST-01).** The verify pipeline interpolated LLM-generated `claim_type`/`verdict` into INSERTs; the manual `.replace("'", "''")` didn't even cover those fields. **Prevention:** ALWAYS bind params (`:name` + dict). Never interpolate model output into SQL; treat `.replace("'","''")` in a query string as a smell to grep for.

- **The auth user dict has NO `.id` and NO `["tier"]`.** `get_current_user` returns `{user_id, email, full_name, subscription_tier, is_active, ...}`. Two prod bugs came from this: `current_user.get("tier")` (None → 403 all paying users) and `current_user.subscription_tier`/`.id` attribute access on a dict (→ 500). **Prevention:** it's a dict — use `["user_id"]` / `.get("subscription_tier")`.

- **CI deploy-gate inherited `-n auto`/`--dist` from `pytest.ini` but pytest-xdist wasn't installed → pytest crashed before any test ran**, so the gate never gated. **Prevention:** a CI `pytest` step must install `pytest-xdist` or pass `-o addopts=` / `--override-ini`. Fixing it makes the gate correctly fail-red on real failures — keep the suite green.

- **CacheAligner: static blocks belong in the system prefix, not the user-prompt tail.** Chat appended the ~2 KB action catalogue AFTER the volatile context, so no prompt-prefix cache could hit. Invariant catalogues → cached static system prompt; only live context in the user message. See `app/domains/intelligence/context_compaction.py`.

- **Fail-closed admin allowlist.** No admin/role concept existed — "admin" endpoints were gated by "is logged in" only. `require_admin` is keyed to `CLILENS_ADMIN_EMAILS`; **unset = nobody is admin = 403.** Must be set in prod.

- **GDPR delete = anonymize-and-deactivate, not hard delete.** `user_id` is referenced by many tables with no guaranteed `ON DELETE CASCADE`, so erase PII + deactivate + best-effort purge personal tables rather than risk orphans / a mid-delete 500.

- **Provenance must report what ACTUALLY ran, not what keys exist.** Deep-search claimed `synthesis_model="anthropic"` whenever a key was present (even on DeepSeek fallback) and a hardcoded ada-002 embedder (real one is bge-m3). Record the model on the success path; report the live embedder.

---
> **Note to Agents**: Always append your findings and insights to this file after completing significant refactoring, debugging, or feature implementation.
