# Climatefacts.ai — Platform Release-Readiness Audit

**Date**: 2026-05-27 · **Audit pass**: comprehensive (loop 5) · **Status**: pre-release v1.0

This is the master synthesis across every dimension the platform claims:
methodology, architecture, agentic core, data layer, UIX, freemium /
professional gear, security, devops, GX10 offload, and release blockers.
Drives the go/no-go decision and the next-30-days roadmap.

Inventory snapshot (live counts):
- **59** API route files (`api/*.py`)
- **47** database migrations (`infrastructure/database/migrations/versions/`)
- **37** Next.js pages (`src/frontend/src/app/**/page.tsx`)
- **69** React components
- **22** agentic skills (registered in `SKILLS_REGISTRY`)
- **97** test files
- **155** markdown docs (64 archived, 22 improvement-plans, 11 reports)
- **168** RSS feeds registered (4 deactivated for off-topic flood)
- **101** source tiers in `source_credibility_tiers` (1,773 articles tier-scored)

---

## 1. TL;DR + go/no-go

**Composite quality score: ~3.5 / 5** (after loop 4 backfills converge).
The platform is **functional, honest, and verifiable end-to-end** — the
core promise (verified climate intelligence with provenance) holds. But
five named release blockers must clear before public v1.0:

| Blocker | Severity | Owner | ETA |
|---|---|---|---|
| 8 unenforced premium features (gap §4-9) | High — revenue leak | per-feature triage | 2 days |
| Map coverage 19.7% of UN-193 | High — visible promise miss | data-sourcing slice | 1 week |
| Calibration `n_labels=0` (gap §4-11) | Medium — methodology page shows "0 labels" | reviewer pass | 2 days |
| 916 articles from deactivated feeds still in corpus (gap §4-12 remainder) | Medium — SDG / search pollution | backfill flag | 4 hours |
| Doc cruft: 64 archive + 22 improvement-plan files | Low — reviewer fatigue | consolidate | 2 hours |

Recommendation: **go for soft-launch (private beta)** with the 5
blockers documented as known limitations. Hold public v1.0 until
blockers 1 and 2 clear.

---

## 2. Eight-axis score table (final this session)

| # | Axis | Score | Evidence | Target | Status |
|---|---|---|---|---|---|
| 1 | Reliability (claim depth + accuracy) | **~2.8/5** | avg 2.5 claims/article pre-backfill, 296 articles in claim-extraction queue post-loop-4 → expect ~3.5 post-convergence | ≥3.5 | tracking, blocker partially mitigated |
| 2 | Calibration | **1/5** | `n_labels=0` per `/api/methodology/calibration` — needs reviewer pass | ≥3.0 | open blocker |
| 3 | Hallucination control | **~4/5** | spaCy NER in API Dockerfile, 8-signal H-Neuron, per-sentence grounding in /deep-search | ≥4.0 | at target |
| 4 | Source diversity + 3-axis | **~4/5** | 1,773 articles tier-scored (T1 = 259 articles at 90, T2 = 688 at 75, T3 = 522 at 60, unknown = 345 = Google News aggregators) | ≥4.0 | at target |
| 5 | Persona breadth | **~3/5** | 2 view modes (consumer/business) + 7 persona surfaces ship; honesty doc tracks "claimed vs delivered" depth | ≥3.5 | close to target |
| 6 | Free/paid alignment | **~2.5/5** | 7 of 15 premium features enforced; 8 unenforced + tracked in CI test (`test_premium_feature_matrix.py`) | ≥4.0 | open blocker |
| 7 | Operational reliability | **~4/5** | Cloud Run auto-deploy, scheduled crons live, `/api/admin/llm/breakers` auth-gated, daemon self-restart logic | ≥4.0 | at target |
| 8 | KG / semantic / RAG | **~3.5/5** | `/api/carf/entity-graph` 200 OK, `/api/semantic/{entity,explain}` shipped, RRF in hybrid_rag_service.py | ≥3.0 | above target |

**Composite (mean): 3.10/5 measured, ~3.5/5 expected post-backfill-convergence.**

---

## 3. Per-feature inventory + golden-example status

### 3.1 Article enrichment
- **Pipeline**: ingest → claim extract (DeepSeek) → enrich (GX10 qwen2.5:7b) → verify (claims + fact_checks)
- **Surface**: `/articles/{id}` page renders Executive Brief + In-Depth Analysis + Climate Context + KG mini-view + Weather/Trend card + SDG chips + Topic feedback button
- **Golden example**: `07371b0c` (InfoAmazonia COP30) — brief 520c, excerpt 2073c, context 463c, 5 entities, 6 claims
- **v1 status**: ✅ shipped, golden example verifiable on cloud
- **Open work**: 107 articles backfilled; ~296 still in claim-extraction queue

### 3.2 Deep search
- **Surface**: `/deep-search` page, premium-gated (`check_premium_feature(user_tier, "deep_search")`)
- **Pipeline**: Cynefin classifier → article retrieval → Perplexity Sonar → LLM synthesis with per-sentence grounding
- **v1 status**: ✅ shipped
- **Open work**: no golden example saved this loop — flag for next pass

### 3.3 Research analysis
- **Surface**: `/research` page = feed + RecentResearchAnalyses (shipped S3) + upload + analyze form
- **Pipeline**: POST `/api/research/analyze` → ResearchReportService → methodology/citation/transparency scoring
- **v1 status**: ✅ shipped + analytical surface restored
- **Open work**: 5 of 12 url_analyses rows still have empty fact_checks for legacy data — S12 wires NEW runs; legacy rows can be re-run via `/api/admin/backfill/claim-extraction`

### 3.4 Corporate climate tracker
- **Surface**: `/companies` index + `/companies/{ticker}` detail
- **Standards**: 5 frameworks (CSRD, SBTi, TCFD, IFRS S2, GRI) with per-standard compliance matrix
- **Suggest company**: `POST /api/companies/suggestions` (auth required)
- **Analyze report URL**: `POST /api/companies/{ticker}/analyze-report` (Standard+ tier)
- **Golden example**: Microsoft Corporation — CSRD/SBTi/GRI aligned, TCFD/IFRS_S2 partial
- **v1 status**: ✅ shipped
- **Open work**: 14,797 companies, only 9 with fully-comprehensive disclosure; SBTi+CDP+NZT adapters running

### 3.5 Map (climate intelligence)
- **Surface**: `/map` page with 4 layers — article density, temperature anomaly, climate risk, source diversity
- **Cross-artifact**: `/api/map/cross-artifact-coverage` ships article + company + research counts per country
- **Country drill**: `/api/map/country/{cc}/artifacts` + `/country/{cc}` detail page
- **v1 status**: ⚠️ functional but coverage 19.7% of UN-193 (release blocker)
- **Open work**: Map mobile UIX, coverage push to 95%, OWID integration

### 3.6 Knowledge graph + semantic layer
- **Surface**: `/explore/entity/{id}` page + KG mini-view on every article + `/api/semantic/explain` "why connected"
- **Pipeline**: clilens-lane-a-entity worker (GX10) populates `entities` + `article_entities` + `entity_relationships`
- **v1 status**: ✅ shipped (loop 2)

### 3.7 UN SDG layer
- **Surface**: `/sdg/{1..17}` cross-artifact browse + `SDGChips` on article pages
- **Taxonomy**: 17 goals + curated keyword sets per goal
- **Post-loop-4**: word-boundary filter (S11) eliminates substring false-positives
- **v1 status**: ✅ shipped (loop 3)

### 3.8 Sources catalog
- **Surface**: `/sources` page, 100+ tier-scored sources visible
- **Data**: 101 rows in `source_credibility_tiers`, 1,773 articles now tier-scored
- **v1 status**: ✅ shipped post-loop-3 case-fix

### 3.9 User saves / bookmarks
- **Surface**: `/saves` page, `Save` button on article cards
- **Endpoints**: `/api/user/bookmarks/{article_id}` + `/api/saved-items`
- **Freemium quota**: 3 saved items free / unlimited Standard+
- **v1 status**: ✅ shipped

### 3.10 Chat / agentic actions
- **Surface**: `<ContextualAssistant />` on every page
- **Skills registered**: 22 (in `SKILLS_REGISTRY`)
- **Pin test**: `test_agentic_skill_pin.py` ensures registry ↔ frontend dispatcher sync
- **v1 status**: ✅ shipped

---

## 4. Freemium / Professional tier matrix (audited)

| Feature | Free | Standard ($) | Pro ($$) | Enterprise ($$$) | Enforced? |
|---|---|---|---|---|---|
| Browse articles + KG | ✓ | ✓ | ✓ | ✓ | n/a |
| Saves (count) | 3 | ∞ | ∞ | ∞ | ✓ (`saved_searches` enforced) |
| Searches | 3/day | ∞ | ∞ | ∞ | ✓ |
| Deep-search runs | 2/day | 10/day | ∞ | ∞ | ✓ (`deep_search`) |
| Document upload | — | ✓ | ✓ | ✓ | ✓ (`document_ingestion`) |
| URL analysis | 3/day | ∞ | ∞ | ∞ | ❌ **UNENFORCED — release blocker** |
| Export PDF/CSV | — | ✓ | ✓ | ✓ | ✓ (`export`) |
| Weather context overlay | — | ✓ | ✓ | ✓ | ✓ (`weather_context`) |
| API access | — | — | ✓ | ✓ | ✓ (`api_access`) |
| Semantic search | — | — | ✓ | ✓ | ✓ (`semantic_search`) |
| Comparative analysis | — | — | ✓ | ✓ | ❌ **UNENFORCED** |
| Advanced analytics | — | — | ✓ | ✓ | ❌ **UNENFORCED** |
| Infographics | ✓ | ✓ | ✓ | ✓ | ❌ **UNENFORCED** (matrix says paid, behavior is free — pick one) |
| Notifications | — | ✓ | ✓ | ✓ | ❌ **UNENFORCED** (route doesn't exist yet) |
| Feed customization | — | ✓ | ✓ | ✓ | ❌ **UNENFORCED** |
| Advanced insights | — | — | ✓ | ✓ | ❌ **UNENFORCED** |
| Source registration | — | ✓ | ✓ | ✓ | ❌ **UNENFORCED** (anyone authenticated can suggest) |

**Action required**: 8 unenforced features (caught in CI test `test_premium_feature_matrix.py`). Triage per feature: either add enforcement OR drop from matrix. **Cannot ship public v1.0 with unenforced premium claims** — revenue leak + marketing dishonesty.

---

## 5. Security audit

### 5.1 Authentication
- **Mechanism**: JWT Bearer via `HTTPBearer` + API key fallback for `Pro+` tier
- **JWT secret**: `JWT_SECRET_KEY` from Google Secret Manager
- **Session refresh**: `/api/auth/refresh` endpoint
- **OAuth**: Google + GitHub (mig 013 oauth_and_user_activity)
- **Issues found**: ✅ no exposed secrets in repo · ✅ all secrets from `--set-secrets` in `cloudbuild.yaml` · ⚠️ `clilens_token` localStorage key — XSS exposure risk; document mitigation (no third-party scripts in `layout.tsx`, CSP needed)

### 5.2 Authorization
- **Tier check**: `check_premium_feature(user, feature)` — see §4 matrix
- **Admin endpoints**: `X-Scheduler-Secret` or `X-Corporate-Sync-Token` header — both auth-gated
- **Per-article rate limits**: `RateLimitMiddleware` global, per-user quotas in `TIER_LIMITS`
- **Issues found**: 8 unenforced features (§4) — **release blocker**

### 5.3 Input validation
- **Pydantic**: all POST endpoints use Pydantic models with `min_length`/`max_length`
- **SSRF**: `_validate_safe_url` in `url_analysis_routes.py` rejects private IPs
- **XSS**: `DOMPurify.sanitize` in `ArticleDetailTabs` with strict tag/attr allowlist + render-time `stripHtml` defense (`src/frontend/src/lib/stripHtml.ts`)
- **SQL**: parameterized via SQLAlchemy `text()` throughout; spot-checked 10 random handlers — none use string interpolation for user input

### 5.4 Secrets
- **In repo**: ✅ none (`.env` gitignored, `.env.example` is sanitized template)
- **In Cloud Run**: 10 secrets from Google Secret Manager via `--set-secrets`
- **In GX10**: `lane-a.env` has DATABASE_URL — file is mode 600, on user-only systemd unit
- **Rotation**: ⚠️ no automated rotation — document in operational playbook

### 5.5 CSP / CORS
- **CORS**: env-driven `ALLOWED_ORIGINS`, locked to FE production URL + localhost
- **CSP**: ⚠️ no Content-Security-Policy header set — recommend adding for v1.0
- **HSTS**: Cloud Run sets automatically

### 5.6 Specific risks reviewed
- ✅ SSRF on `/research/analyze` URL field — blocked by `_validate_safe_url`
- ✅ XSS via article excerpt with raw HTML — fixed slice S1 (stripHtml defensive render)
- ✅ Prompt injection via article text — content category + length caps applied; provenance ledger tracks LLM call inputs
- ⚠️ CSRF on POST endpoints — JWT in Authorization header (not cookie) so cross-site CSRF mitigated, but document explicitly
- ⚠️ Rate-limit bypass via API-key endpoints — verify quota_routes covers API key usage

---

## 6. DevOps + CI/CD pipeline

### 6.1 Build pipeline
- **API**: `cloudbuild.yaml` — 9 steps (run-migrations, build-api, push-api, deploy-api, get-api-url, build-frontend, push-frontend, deploy-frontend, update-schedulers)
- **Frontend**: separate `cloudbuild-frontend.yaml`
- **Trigger**: pushes to `main` → auto-deploy to Cloud Run via Cloud Build webhook
- **CI**: `.github/workflows/ci.yml` — lint + typecheck + unit tests on every PR

### 6.2 Migration runner
- **File**: `scripts/run_migrations.py` (Step 0 of cloudbuild)
- **Tolerance**: `MIGRATIONS_TOLERATE_ERRORS=true` set on Cloud Run env — idempotency errors logged but don't block deploy
- **Risk**: silent migration failures can mask drift — loop 1 caught mig 049 not actually applying because of ON CONFLICT-DO-NOTHING masking; **recommend strict-mode for production deploys**

### 6.3 Scheduler crons
- **Provisioned via**: `infrastructure/gcp/provision-infra.sh`
- **Active crons**: `cn-aoi-poll` (AOI alerts), `cn-enrich-pending` (article enrichment), `cn-source-tier-refresh`, `cn-source-credibility-backfill`
- **Auth**: `X-Scheduler-Secret` header
- **Issue**: ⚠️ Cron list is not in source-controlled YAML — provision script is shell loop. Recommend `gcloud scheduler jobs list --format=yaml > infrastructure/scheduler-jobs.yaml` for diff-able state.

### 6.4 Observability
- **Logs**: Cloud Run structured logging + `gcloud logging read`
- **Metrics**: `/api/metrics/log-feature` endpoint + manual ReasoningBank export
- **Health**: `/api/health` endpoint (basic)
- **Gap**: ⚠️ no SLA dashboard, no error budget tracking, no alerting on Cloud Run revision errors — document as v1.1 work

### 6.5 Test coverage
- **97 test files** under `tests/`
- **Coverage on backend**: estimated 35-50% (no recent coverage run with passing config)
- **Coverage on frontend**: jsdom tests under `src/frontend/src/__tests__/` — modest
- **Recommendation**: ship v1.0 with current coverage + commit to >70% by v1.1

---

## 7. Documentation hygiene

**155 markdown files** is too many for a release-ready repo. Breakdown:
- **64 archive** (`docs/archive/`) — historical sprint reports; safe to keep but should not appear in default ToC
- **22 improvement-plan docs** (`docs/improvementplans/`) — 4 of them are this audit's loops a/b/c/d; **consolidate into one running CHANGELOG-style file**
- **11 reports**
- **~58 other** (methodology, golden-examples, prompts, testing, contributors, etc.)

**Action items**:
1. Consolidate loop-a/b/c/d benchmarks into one `Audit-Trail.md` running file
2. Move historic improvement plans (pre-2026-05-25) to `docs/archive/improvementplans/`
3. Promote canonical docs (`docs/methodology/`, `docs/release/`, `docs/contributing/`) into a top-level index
4. Add `docs/README.md` with the canonical ToC

See `docs/release/Documentation-Consolidation-Plan-2026-05-27.md` (next slice).

---

## 8. Agentic skills audit

**22 skills** registered in `SKILLS_REGISTRY`. Inventory:

| Category | Skills | Status |
|---|---|---|
| Navigation | `navigate`, `apply_search_filters`, `apply_map_filters`, `open_country`, `open_methodology_section`, `open_company` | ✅ all dispatched on frontend |
| Action | `analyze_url`, `bookmark_article`, `save_item`, `subscribe_research_topic`, `start_deep_search`, `start_calibration_label`, `explore_scenario` | ✅ all dispatched |
| B3 corporate | `verify_corporate_claim`, `analyze_corporate_report`, `suggest_company` | ✓ + 1 new (loop 2) |
| M4-M7 (this session) | `flag_off_topic`, `explore_entity`, `explain_connection`, `promote_golden_example`, `explore_sdg`, `tag_sdgs` | ⚠️ 5 are backend-routable but **not yet dispatched on frontend** — chat can call them via tool-use but FE has no fallback UI |

**Action**: extend `src/frontend/src/lib/chatActionDispatcher.ts` to dispatch the 5 new skills (`flag_off_topic`, `explore_entity`, `explain_connection`, `explore_sdg`, `tag_sdgs`, `promote_golden_example`, `suggest_company`). The pin test in `test_agentic_skill_pin.py` allows registry > frontend so this isn't a hard regression — just a feature parity gap.

---

## 9. Data sources audit

### 9.1 Article ingestion sources (RSS)
- **168 RSS feeds** registered in `rss_feed_registry`
- **4 deactivated** (mig 053 ingestion bias rebalance)
- **Coverage by continent (active feeds)**:
  - North America: ~30 feeds (US heavy)
  - Europe: ~80 feeds (broad)
  - Asia: ~20 feeds (India, China, Japan, Indonesia)
  - Africa: ~15 feeds (gap — only Ghana, Nigeria, Kenya, ZA covered)
  - South America: ~12 feeds (Brazil, Mexico, Argentina, Colombia, Chile, Peru)
  - Oceania: ~6 feeds (Australia, NZ)

**Gaps for release**:
- Russia (deliberately limited per user — only state media accessible)
- Middle East beyond Israel/UAE
- Many African countries (release blocker for "95% UN-193" promise)
- Central Asia
- Caribbean

### 9.2 Reference data sources (research)
- IPCC, IEA, UNEP, WMO, Global Carbon Budget, World Bank, OECD, Climate Action Tracker
- 35 curated paper targets in `CLIMATE_RESEARCH_TARGETS`
- Hansen, Rockström, Lenton, Steffen — frontier science covered
- **Recommendation**: add Our World in Data integration (M11 planned, not yet shipped)

### 9.3 Corporate data sources
- SBTi (Google Sheets adapter live), CDP (public CSV gated since 2024 → seed only), NZT (GraphQL endpoint)
- 14,797 companies tracked; 23,117 disclosure rows
- **Gap**: CDP real-time sync requires API registration

---

## 10. Map view audit

| Layer | State | Issue |
|---|---|---|
| Article density | ✅ working | underrepresents Africa, Latam, Central Asia |
| Temperature anomaly | ✅ live | Open-Meteo source |
| Climate risk | ⚠️ partial | needs ND-GAIN integration |
| Source diversity | ✅ working | shows tier distribution per country |
| Cross-artifact | ✅ shipped (loop 2) | `GET /api/map/cross-artifact-coverage` |
| Country drill-down | ✅ working | `/country/{cc}` page |
| Mobile UIX | ❌ broken | "selections cover most of screen" (user report) |
| Coverage % UN-193 | 19.7% | **release blocker** |

**Cross-feature transitions audit**:
- Click country on map → `/country/{cc}` ✅
- Click country flag on article → `/country/{cc}` ⚠️ partial (some pages do, some don't)
- Click company in map filter → `/companies/{ticker}` ✅
- Click research paper on country page → ❌ not yet wired
- Show SDG color overlay on map → ❌ not yet shipped (would compose §7 SDG + map)

**Recommended slice**: SDG color overlay layer on map (composes work from loop 3).

---

## 11. Release blockers (5 items)

Repeating from §1 with concrete next-steps:

1. **Premium-feature enforcement gaps** (gap §4-9) — see §4 table, 8 features. Triage per feature: add `check_premium_feature` in route OR drop from matrix. **2 days of focused work.**

2. **Map coverage 19.7% → ≥80%** — data-sourcing slice: add ~150 country-level climate feeds, populate `country_indicators` for the missing 150+ countries via WMO + ND-GAIN backfill. **1 week.**

3. **Calibration `n_labels=0`** — methodology page shows "0 labels in calibration corpus". Two-part fix:
   - Build a labeling UI on existing `/calibration` admin route (already exists per mig 028)
   - Seed 50 articles with reviewer labels
   - Brier + ECE will compute automatically once `n_labels >= 30`
   **2 days.**

4. **916 articles from deactivated feeds still pollute SDG / search** — backfill flag in `topic_feedback` table marking them `off_topic`. **4 hours of SQL + endpoint.**

5. **Doc cruft** — consolidate 22 improvement-plan files + 64 archive files into a clean canonical structure. **2 hours.**

---

## 12. What we are NOT shipping at v1.0 (honest)

- **PyMC-backed Bayesian credibility** — current is weighted average labeled `weighted_score`; honesty contract in place
- **Real dark mode** — color-scheme pinned to light (slice S14)
- **LoRA-fine-tuned GX10 specialists** — base qwen2.5:7b in production; LoRA distillation is the v1.5 roadmap (see `GX10-Offload-Plan-2026-05-27.md`)
- **OWID integration** (M11) — referenced in semantic explainer but not wired
- **Multi-LLM cross-verification opt-in** — feature exists, not enabled by default (cost)
- **Map mobile UIX redesign** — known broken on small screens
- **Streaming chat responses** — current is synchronous; streaming is v1.1
- **Webhook-based ingestion** — current is poll-based via Cloud Scheduler
- **Multi-region deploy** — europe-west4 only

---

## 13. Recommended release sequencing

| Week | Focus |
|---|---|
| Week 0 (now) | Triage 8 unenforced features (§4) — close blocker 1 |
| Week 1 | Map coverage data push (blocker 2) + 916-article off-topic backfill (blocker 4) |
| Week 2 | Calibration reviewer pass (blocker 3) + doc consolidation (blocker 5) |
| Week 3 | Soft-launch / private beta with monitoring |
| Week 4 | Public v1.0 if all metrics hold |

---

## 14. Cross-reference

- **GX10 offload plan**: `docs/release/GX10-Offload-Plan-2026-05-27.md`
- **Security + DevOps detail**: `docs/release/Security-DevOps-Audit-2026-05-27.md`
- **Loop benchmarks**: `End2End-Audit-Benchmark-2026-05-27{a,b,c,d}.md` → to be consolidated
- **Master prompt**: `docs/prompts/master-end2end-audit-and-fix.md`
- **Honest gap audit**: `Honest-Gap-Audit-v2-2026-05-25.md` (still tracking residual items)

---

**Auditor**: Claude (master-prompt audit protocol, 4 loops + this synthesis)
**Reviewer signoff needed**: human review of blockers 1-5 before public v1.0
