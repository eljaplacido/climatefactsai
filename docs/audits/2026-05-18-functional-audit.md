# Functional audit — Climatefacts.ai (2026-05-18)

Scope: every FastAPI route under `api/*.py` and every Next.js page under
`src/frontend/src/app/**/page.tsx`. Goal: confirm each surface is wired
end-to-end to real DB queries / real services (no stubs, no mocks).

## 1. Functional core (confirmed working)

API routes — all execute real SQL or call real services with graceful
degradation:

- Core article surface — `api/main.py` (`GET /api/articles` L483, `GET /api/articles/{id}` L596, `GET /api/countries` L729, `GET /api/tags` L811, `GET /api/stats` L965, `POST /api/articles/{id}/feedback` L846, `POST /api/articles/{id}/reanalyze` L1096).
- Auth + OAuth — `api/auth_routes.py` (register/login/refresh/forgot/reset/change-password, all hit `users` table), `api/oauth_routes.py` L82–L99 (Google + Microsoft code exchange, real CSRF state check).
- Search — `api/search_routes.py` L65 FTS, L172 semantic (`pgvector` + OpenAI embedding with FTS fallback at L236), L362 save/load, L501 suggestions.
- Map — `api/map_routes.py` country-stats L305, discussed L452, topic-density L548, source-coverage L591, agentic `POST /api/map/query` L643, regions L839, country detail L1139, trends L1320, climate-data L1368, compare L1449, timeline L1571, temperature-anomaly L1617, climate-risk L1694.
- Deep search — `api/deep_search_routes.py` L124 `/`, L197 `/compare`, L248 weather-context, L293 intelligence-brief, L353 weather-location.
- Green transition — `api/green_transition_routes.py` country L234, leaderboard L354, compare L448 (defensible sustainability_score + real_indicators).
- Forecasts — `api/forecast_routes.py` L61 multi-source comparison via `ForecastService`, L90 accuracy.
- Methodology + drift — `api/methodology_routes.py` (prompts, formula, indicators, audit-trail, calibration, hallucination rates), `api/drift_routes.py` (source-mix + prompt-fingerprint KL).
- Chat — `api/chat_routes.py` POST L98 (HybridRAG → FTS fallback, view_context hydration, Cynefin classification, hallucination check), sessions L266/L296/L328.
- URL analysis — `api/url_analysis_routes.py` L1294 submit, L1365 detail, L1505 stats.
- Article ingestion — `api/article_ingestion_routes.py` L169 URL ingest, L271 status, L328 document/PDF, L556 upload.
- Translation — `api/translation_routes.py` L162–L303 (DB-backed translations + Celery on-demand).
- Subscriptions — `api/subscription_routes.py` real Stripe integration L138/L276/L382/L532.
- User / activity / bookmarks / API keys / exports / similarity / feed prefs / source registry / source suggestions / saved queries / research / CARF / benchmarks / og_image / infographic / scheduler / admin pipeline / analytics — all execute real queries against shipped tables.

Frontend pages — all render and call live endpoints:

- `/` home (`page.tsx`), `/map`, `/search`, `/deep-search`, `/analyze`, `/research`, `/sources`, `/suggest-source`, `/feed`, `/forecasts`, `/methodology`, `/about`, `/articles/[id]`, `/articles/[id]/transparency`, `/login`, `/signup`, `/forgot-password`, `/auth/callback`, `/dashboard` (+ history, saved, subscription, settings), `/admin`, `/admin/pipeline`, `/admin/analytics`, `/submit`.

## 2. Broken / incomplete

| Route / page | Sev | Problem | File:line |
|---|---|---|---|
| `POST /api/translate` | P2 | Falls back to 503 when **both** ANTHROPIC_API_KEY and DEEPSEEK_API_KEY unset — silent in dev, hard to spot since frontend i18n-context calls this on every locale switch. | `api/main.py:436` |
| `POST /api/discovery/discover-news` | P2 | Hard 400 if `PERPLEXITY_API_KEY` not set; no fallback path. Anonymous-IP rate-limit key (`anon-{ip}`) bypasses tier accounting. | `api/discovery_routes.py:168-184` |
| `GET /api/methodology/hallucination-rates` | P2 | `by_source` join uses `articles.id` but the schema uses `article_id`; LEFT JOIN silently buckets every source as `unknown` if that column doesn't exist. | `api/methodology_routes.py:655` |
| `GET /api/methodology/indicators` | P2 | Returns `available=False` + empty list when `indicator_definitions` / `country_indicators` migration not applied. Defensible, but the methodology page is the public-trust surface — degrade message is silent. | `api/methodology_routes.py:206-243` |
| `GET /api/green-transition/country/{cc}` | P2 | Legacy `overall_green_score` is an article-count "coverage_index", not a sustainability metric. Mitigated by `score_basis` + `coverage_caveat` fields (L129–140) and `sustainability_score` block, but UI must surface the caveat. | `api/green_transition_routes.py:117-147` |
| `POST /submit` (frontend) | P1 | Hardcodes `http://localhost:5400`; will 404 in production. | `src/frontend/src/app/submit/page.tsx:20` |
| `POST /api/scheduler/*` | P2 | Every endpoint returns `{"status": "skipped", "reason": "task_module_unavailable"}` on ImportError instead of failing loudly. Cloud Scheduler will report 200 OK on a non-functional pipeline. | `api/scheduler_routes.py:72-92,113-114,131-132,153-154,171-172` |
| `POST /api/admin/trigger-workflow` | P2 | Requires Celery broker; if Redis isn't reachable, raises 500 — fine, but no fallback path documented. Default country `FI` and `max_articles=5` are hardcoded at L1008-L1009. | `api/main.py:983-1032` |
| `GET /api/carf/status` | P2 | Reports `configured=True/False` from `CARF_API_URL`; downstream endpoints (`/causal`, `/counterfactual`) return `{"status": "unavailable"}` when CARF is unreachable — gracefully degraded but UX has no "service unavailable" affordance. | `api/carf_routes.py:55-100` |
| `POST /api/research/analyze` | P2 | Returns 500 on any failure (PDF parse, DOI resolution, LLM error) without distinguishing — frontend has no actionable error. | `api/research_routes.py:31-66` |
| `POST /api/methodology/calibration/refit` | P2 | Returns `status='insufficient_data'` when <5 labels; correct, but no UI to actually create labels through `POST /calibration/labels` is wired from `/methodology` page. | `api/methodology_routes.py:450-470` |

## 3. Dead code / orphaned

- **Nav missing entries**: `GlobalNav.tsx` does NOT link `/forecasts`, `/methodology`, `/dashboard`, `/admin`, `/admin/analytics` (other than logged-in icon), `/feed`. Most are reachable only via homepage footer (`page.tsx:267-270`) or user dropdown. New users have no obvious path to forecasts or methodology.
- **`GET /api/admin/dashboard`** (`api/main.py:975`) duplicates `/api/stats` and is unreferenced from frontend.
- **`api/conversation_routes.py`** — `POST /api/articles/{id}/ask` (L61) is called by `AgenticAssistant` when in article_qa mode; **history endpoint L180 is never read** by the frontend.
- **`api/observability_middleware.py`** is loaded but `TraceDebug.tsx` only renders when `?trace=1` query param is set — dev-only.
- **`api/email_service.py`** — only used by auth flows; no admin notification path uses it.
- **`api/og_image_routes.py:113`** — `/og-image/{article_id}` is wired in but no `<meta property="og:image">` tag in any page head; social sharing won't pick it up.
- **`/dashboard/history`, `/dashboard/saved`, `/dashboard/subscription`, `/dashboard/settings`** — pages exist but only `/dashboard` is linked from `GlobalNav` user menu; sub-routes reached only via `/dashboard/layout.tsx` internal nav.
- **CARF entity-graph endpoint** (`api/carf_routes.py:194`) — `/api/carf/entity-graph/{article_id}` exists but no frontend component fetches it.

## 4. Chat-panel coverage

The `ContextualAssistant` / `AgenticAssistant` panel (`src/frontend/src/components/AgenticAssistant.tsx`) is **read-only / answer-only**. It selects one of three POST endpoints based on context:

CAN trigger:
- General Q&A — `POST /api/chat` (full HybridRAG + view-context hydration; L98).
- Map intelligence — `POST /api/map/query` (when on `/map`).
- Single-article Q&A — `POST /api/articles/{id}/ask` (when on `/articles/[id]`).
- Country highlighting callback (`onHighlightCountries`) — passes back to map page state.
- Clarification chips re-submit (`handleSend(s)` at L444) — same chat endpoint.
- Source/article citations open in new tab (no in-app preview).

CANNOT trigger (despite being plausibly chat-actionable):
- Submitting a URL for analysis (`/analyze` flow) — no `POST /api/url-analysis` hook.
- Triggering deep search — `/api/deep-search` is only reachable from `/deep-search` page form.
- Triggering article re-analysis (`POST /api/articles/{id}/reanalyze`) — only `ReanalyzeButton` calls it.
- Saving a query / bookmarking (`/api/saved-queries`, `/api/bookmarks`) — no chat action.
- Requesting translation (`POST /api/translations/request`) — language switch handled by header dropdown only.
- Subscribing to feed / changing feed preferences (`/api/feed/preferences`).
- Triggering ingestion (`/api/articles/ingest`, scheduler endpoints).
- Comparing countries from chat — chat only **answers** about a comparison the user already opened; cannot navigate the user to `/map?compare=…`.
- Suggesting a new source (`POST /api/source-suggestions`).
- Generating an infographic / OG image.
- Running calibration label submission, refit, or any methodology mutation.

The panel is purely conversational; it has no tool-call / function-call protocol with the backend. Adding any of the above requires the LLM client to return a structured action and the frontend to dispatch it — neither exists today.
