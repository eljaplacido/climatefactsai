# End-to-End Platform Audit + Benchmark — 2026-05-26

Read-only audit + live benchmark of Climatefacts.ai. Repo head `3748c5f`. Live API
`https://climatenews-api-srzwxdzmaq-ez.a.run.app` (Cloud Run, europe-west4, project
`climatenews-495412`). Live frontend `https://climatenews-frontend-srzwxdzmaq-ez.a.run.app`.

Anchored against the strategic context docs:
- `docs/improvementplans/Alignment-Gap-Inventory-2026-05-25.md`
- `docs/improvementplans/TruthEngine-PersonaFit-Design-2026-05-25.md`
- `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md`
- `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md`
- `.claude/Climatefacts-TruthMachine-Sources-Semantics-2026-05-25_extract.txt`
- `.claude/Climatefacts-CARF-CYNEPIC-Mapping-2026-05-25_extract.txt`

---

## TL;DR

- **Composite grade: 3.05/5 today (was ~2.4 six weeks ago).** UX scaffolding and the
  agentic-protocol surface are at parity with code (15 skills wired end-to-end, 4
  shipped UI cards for previously-invisible backends); the truth-engine + ingestion
  data layer remains the weak link.
- **Biggest 3 strengths.** (1) Agentic protocol — 15 skills aligned across
  `src/backend/app/domains/intelligence/skills.py:74-308`, `prompts.py:413-428`,
  `src/frontend/src/lib/chatActionDispatcher.ts:24-42`,
  `src/frontend/src/lib/useSkills.ts:61-83`, pinned by `tests/api/test_agentic_skill_pin.py`;
  live `/api/skills` returns 15. (2) Reliability scorer now blends 3-axis + density
  (`src/backend/shared/reliability_scorer.py:96-187`). (3) Map biome layer is genuinely
  global — `/api/map/biome-overview` returns 196 countries with biome + Köppen colours,
  consumed by `InteractiveClimateMap.tsx:107-145`.
- **Biggest 3 risks.** (1) Source-tier service ignores the 3-axis columns it claims to
  surface — `src/backend/app/domains/trust/source_tier_service.py:53,118-119,149`
  selects only `prior_bonus, tier`, so the reliability scorer's `editorial_score /
  factcheck_score / transparency_score` parameters are never populated at runtime; the
  3-axis math is silently dead. (2) Live data is hollow — `/api/stats` reports
  `total_articles=1664, verified_claims=0, average_confidence=10.43`; the verdicts
  endpoint returns `unverified=1025` of 1044 total fact-checks (98%). (3) Provenance
  ledger looks empty in production — `/api/methodology/hallucination-rates` returns
  `notes: ["claim_provenance unavailable (migration 021 not applied?)"]` and
  `/api/drift/source-mix` returns `recent_count=0, baseline_count=0`. The
  audit-trail-by-article check returned `total: 0`. Provenance writes look
  best-effort (`provenance.py:127-136`) but they should not be silent across the
  entire production corpus.
- **Top-1 next-sprint priority.** Patch `source_tier_service.py` (the 3 SELECT
  clauses) to project the 3 axis scores, then patch the article-stamping pipeline
  to read them. Half a day of code, and it un-deadlocks every truth-engine claim
  the platform now makes about 3-axis credibility. After that, fix the
  claim_provenance writes (currently leaving the ledger empty in prod).
- **Biggest "live but broken" finding.** `claim_provenance` is effectively empty in
  prod (three independent methodology endpoints all return zero rows), even though
  the writes are wired in `provenance.py:62-100` and migration 021 is in
  `infrastructure/database/migrations/versions/021_claim_provenance.sql`. Either
  mig 021 didn't apply, or every analytical write is silently failing to the
  ledger — both render the "truth-machine" framing structurally unprovable today.
- **Biggest "shipped in code but not surfaced" finding.** Mig 041 (3-axis source
  scoring) is in the DB schema, mig 045 fences the columns never-null, the
  reliability scorer at `reliability_scorer.py:115-118,142-150` already takes
  `editorial_score / factcheck_score / transparency_score` parameters — but no
  caller of the scorer reads those columns from the DB, and `/api/methodology/source-tiers`
  (live response keys: `source_name, domain, tier, prior_bonus, evidence_url,
  classification, retracted_count`) does not surface them either.

---

## 1. DevOps pipeline

### 1.1 Cloud Build trigger configuration

- `cloudbuild.yaml:14-23` — substitutions: project `climatenews-495412`, region
  `europe-west4`, repo `climatenews`, services `climatenews-api` +
  `climatenews-frontend`, tagged by `$SHORT_SHA`.
- 5 build steps: `run-migrations` → `build-api` → `push-api` → `deploy-api` →
  `get-api-url` → `build-frontend` → `push-frontend` → `deploy-frontend` →
  CORS/scheduler update (`cloudbuild.yaml:36-259`).
- **`gcloud` CLI is not available in this audit environment** — could not pull
  the last-15 builds programmatically. The git log shows 25 commits this week
  (`3748c5f` head; see commit list `e1c14b1…3748c5f` in the user mandate) — each
  push to main triggers the pipeline; live API serves a working OpenAPI spec
  (234 paths returned, see §10) so the most-recent build deployed cleanly.

### 1.2 Migration runner safety

- `scripts/run_migrations.py:160-244` is the runner.
- `TOLERATED_CODES` at `:172-179` covers 6 PostgreSQL SQLSTATE codes (`42P07,
  42701, 42710, 23505, 42P06, 42723`) — the runner SILENTLY marks any migration
  raising one of those as "applied" when `MIGRATIONS_TOLERATE_ERRORS=true`.
- `:197-208` honours `-- @notolerate` in the migration body — when present, the
  runner ignores `MIGRATIONS_TOLERATE_ERRORS` and fails loud. Mig 044, mig 045,
  mig 046, mig 047 all use this directive (verified by grep).
- `:188-194` — sha mismatch on a previously-applied migration logs a warning
  and SKIPS the file. There is no enforcement that the file must match the
  applied sha; an edit-in-place after apply is silently allowed.
- `cloudbuild.yaml:66-67` ships `MIGRATIONS_FROM=009` and
  `MIGRATIONS_TOLERATE_ERRORS=true` to every CI run.

### 1.3 Cloud Run services

- **API**: `cloudbuild.yaml:96-141` — image `${_REGION}-docker.pkg.dev/${_PROJECT_ID}/${_REPO}/api:${_TAG}`,
  memory `1Gi`, CPU `1`, concurrency `80`, `max-instances=5`, `min-instances=1`,
  `timeout=1800` (raised from 300s for SBTi sync), `--allow-unauthenticated`.
  Live API serves OpenAPI cleanly.
- **Frontend**: `cloudbuild.yaml:190-214` — memory `256Mi`, CPU `1`,
  concurrency `100`, `max-instances=3`, `min-instances=0`, `timeout=60`.
- The audit could not pull `gcloud run services list` (no CLI here); live URL
  reachability is confirmed for both services in §10.

### 1.4 Cloud Scheduler crons

- **Provisioned crons (6)** — listed in `infrastructure/gcp/provision-infra.sh:267-272`
  and refreshed in `cloudbuild.yaml:237-257`:
  - `cn-discover` → `/api/scheduler/ingestion/discover` every 6 h
  - `cn-rss-poll` → `/api/scheduler/ingestion/rss` every 3 h
  - `cn-verify` → `/api/scheduler/processing/verify-pending` every 4 h
  - `cn-retry` → `/api/scheduler/processing/retry-failed` daily at 03:00 UTC
  - `cn-feeds` → `/api/scheduler/feeds/update` every 8 h
  - `cn-translate` → `/api/scheduler/translation/batch` every 12 h
- **NOT provisioned (3 — gap)**:
  - `POST /api/admin/research-poll` (research_feed_routes.py:334) — has no
    Cloud Scheduler entry in either `cloudbuild.yaml` or `provision-infra.sh`.
    CrossRef polling will never fire on its own.
  - `POST /api/admin/link-check` (admin_link_check_routes.py:87) — same
    issue. Link-rot detection is shipped in code (mig 046 added
    `articles.source_url_status`) but no scheduler triggers it.
  - `POST /api/scheduler/aoi-poll` — endpoint exists but no cron entry.

### 1.5 Secrets management

- `cloudbuild.yaml:110-125` mounts 15 secrets to API: `DATABASE_URL`,
  `SCHEDULER_SECRET`, `JWT_SECRET_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `PERPLEXITY_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `SENDGRID_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `DEEPSEEK_API_KEY`, `NOAA_API_TOKEN`, `NASA_API_KEY`, `CORPORATE_SYNC_TOKEN`.
- All three named secrets in the user mandate (`CORPORATE_SYNC_TOKEN`,
  `DEEPSEEK_API_KEY`, `JWT_SECRET_KEY`) are present ✓.

### 1.6 Identified DevOps gaps + risks

1. **Three production-relevant endpoints have NO scheduler trigger**
   (research-poll, link-check, aoi-poll). Anything labelled "periodic" or
   "nightly" in code does not run automatically.
2. **`MIGRATIONS_TOLERATE_ERRORS=true` is the default**, mitigated only by
   per-migration `-- @notolerate` directives. A migration shipping the wrong
   pgcode (e.g. P0001 vs 23505) can pass silently. Mig 045 uses notolerate;
   mig 047 uses notolerate. Older migs (027-036) do not.
3. **sha-mismatch skip-without-fail** (run_migrations.py:188-194) — editing a
   migration after it shipped means the change never runs and the runner
   doesn't fail. A "dangerous-edits" policy is enforced only by convention.
4. **No prod observability** in the audit window — the Cloud Build dashboard,
   Cloud Run revision SHAs, and per-service logs are not introspectable from
   this environment; only the audit doc + live HTTP probes.
5. **Lean Cloud Run config**: `--max-instances=5` on API at 80
   concurrency = max ~400 concurrent users before 503s. Acceptable for the
   current beta; needs uplift before any campaign.

---

## 2. Data ingestion pipelines

### 2.1 RSS feeds

- Migration 026 (`infrastructure/database/migrations/versions/026_un193_country_feeds.sql`)
  seeds **116 Google News country feeds** (counted: 116 `INSERT INTO
  rss_feed_registry` rows in the file).
- Mig 012 seeds 2, mig 014 seeds 8, mig 015 seeds 11. **Total seeded: ~137
  feeds**. Some additional rows may exist from manual + user-registered sources.
- Live `/api/map/source-coverage` returns a list of active sources but heavy
  skew: top 5 are `24ur Okolje (SI) 419`, `Capital BG (BG) 169`, `Digi24 (RO)
  144`, `Dnevnik BG (BG) 79`, `Climatica La Marea (ES) 38`. Carbon Brief
  (Tier-1) only `32`. The aggregator dominates real journalism by volume.

### 2.2 Articles ingested

- Live `/api/stats`: `total_articles=1664`, `articles_today=27`,
  `total_fact_checks=1044`, `verified_claims=0`, `average_confidence=10.43`,
  `last_updated=2026-05-26T03:52:14Z`.
- Live `/api/analytics/pipeline` 7-day trend (verbatim):
  - 2026-05-19: 70 ingested / 12 verified
  - 2026-05-20: 60 / 10
  - 2026-05-21: 28 / 13
  - 2026-05-22: 25 / 3
  - 2026-05-23: 20 / 2
  - 2026-05-24: 213 / 26
  - 2026-05-25: 123 / 19 / **9 failed**
  - 2026-05-26: 27 / 0 (so far)
- 7-day total: ~566 ingested, ~85 verified. **Verification rate: 0.455** at
  the pipeline level but **0% verified** in `/api/stats`. Discrepancy is
  because `articles_today` counts ingest, not fact-check verdicts.

### 2.3 Article enrichment rate

- Sample of 100 articles via `/api/articles?limit=100`:
  - `executive_brief` non-null: **0/100 (0%)**
  - `enriched_excerpt` non-null: **0/100 (0%)**
  - `climate_context_summary` non-null: **0/100 (0%)**
  - `claim_count >= 1`: 90/100 (90%)
  - `claim_count >= 3`: 67/100 (67%)
  - `claim_count >= 6`: 0/100 (0%)
  - mean reliability_score: 66.0
  - `source_credibility_score` null: 100/100 (100% — column never populated)
- **Enrichment service is wired** (`src/backend/app/domains/content/article_enrichment_service.py:411-602`)
  and a local-gx10 provider has been added (`60253df`), but the columns it
  writes (`enriched_excerpt`, `climate_context_summary`, `executive_brief`) are
  NULL across the live sample. The enrichment job is either not running or
  failing silently. Articles' newest `published_date` field tops out at
  **2026-03-20** in the sample (no live ingest in the past 67 days, but
  `/api/analytics/pipeline` shows 27 ingested today — likely those articles
  have `published_date=NULL` while `created_at=today`).
- `verified_claims=0` in `/api/stats` confirms the multi-LLM verifier path is
  not stamping verdicts onto fact_checks rows in production (or `fact_checks`
  rows exist with verification_status='UNVERIFIED' — see §3).

### 2.4 Synthetic data purge — verified clean

- Mig 040 (`040_purge_synthetic_data.sql`) deleted synthetic rows + added the
  trigger guard.
- `api/export_routes.py:263,359` and `api/admin_pipeline_routes.py:171` etc
  enforce `is_synthetic = FALSE`. Sample queries respect this.
- **Verified live**: `/api/articles?limit=100` returned no synthetic rows (no
  fake domains like `example.com` or constructed slugs in the sample).

### 2.5 Corporate adapters

- **SBTi**: live (`src/backend/app/domains/content/corporate/sbti_adapter.py:23-28`).
  Returns rows continuously. Live `/api/companies?limit=200` returned 200
  rows; the first 200 dedup-checked: 0 duplicate groups (mig 043+044 fence
  holding).
- **CDP**: stub (`cdp_adapter.py:25-30` — "CDP retired its anonymous public CSV
  export in 2024 … returns a clean 200 with a documented
  `data_source_unavailable` warning"). No data flowing.
- **NZT**: stub (`nzt_adapter.py`). No data flowing.

### 2.6 Research feed

- Mig 047 (`047_research_feed.sql`) adds `research_subscriptions` +
  `research_feed_items` with partial unique on `(sub_id, DOI)` and
  `(sub_id, LOWER(TRIM(title)))` for null-DOI.
- `api/research_feed_routes.py:1-450` defines the routes; CrossRef poller
  shipped in same commit (6c33165). UI consumer: `ResearchFeedPanel.tsx`
  rendered on `/research/page.tsx:187`.
- **GAP: No Cloud Scheduler entry** for `POST /api/admin/research-poll`. The
  CrossRef poller cannot fire on its own; users would have to wait for an
  admin to curl the endpoint by hand. See §1.4.

### 2.7 Identified ingestion gaps

1. **Article enrichment writes are 0% live** — every single article in the
   100-row sample had NULL `executive_brief`, `enriched_excerpt`, and
   `climate_context_summary`. Code is wired; data is empty.
2. **All sampled articles have NULL `source_credibility_score`** — the ingest
   pipeline never stamps this column from the tier-service lookup; the
   reliability score's 50% weighting on source falls back to 50 (neutral).
3. **Research-feed poller is shipped but not scheduled** — no `cn-research-poll`
   in `provision-infra.sh:267-272`.
4. **Link-check is shipped but not scheduled** — no `cn-link-check`
   in `provision-infra.sh:267-272`. `articles.source_url_status` (mig 046)
   will never get populated.
5. **Ingestion skews heavily to 3 aggregator feeds** — top-5 sources by
   article count are all auto-aggregators (Slovenian, Bulgarian, Romanian +
   Google News country feeds). Tier-1 verified sources (Carbon Brief, BBC
   Climate, Reuters, IPCC, Nature) produce 1-2% of corpus volume.

---

## 3. Calculations (truth-engine math)

### 3.1 Reliability scorer formula + 3-axis blend

- `src/backend/shared/reliability_scorer.py:77-105`:
  - WEIGHT_SOURCE_CREDIBILITY = 0.50
  - WEIGHT_VERIFIED_CLAIMS = 0.30
  - WEIGHT_CONTENT_RELEVANCE = 0.20
  - SOURCE_LEGACY_WEIGHT = 0.6, SOURCE_AXES_WEIGHT = 0.4
  - LIMITED_EVIDENCE_THRESHOLD = 3, CLAIMS_FOR_FULL_CREDIT = 6
- The 3-axis blend math IS wired (`:115-187`): `editorial_score`,
  `factcheck_score`, `transparency_score` parameters land in
  `calculate_reliability_score()` and get averaged into `axes_mean`, then
  blended 0.6/0.4 with the legacy `source_credibility_score`. Density factor
  applied to claims component (`:172-182`).
- **BUT**: caller at `:497-504` reads `editorial_score / factcheck_score /
  transparency_score` from the article row (assumes mig 041 columns are on
  `articles` directly via the JOIN at `:437-451`). The JOIN is on
  `sct.source_name ILIKE a.source_name` which is **fragile** — live
  `articles.source_name` examples are "Andina Peru", "24ur Okolje (SI)",
  "Spiegel Wissenschaft (DE)" while `source_credibility_tiers.source_name` is
  "Reuters", "AP", etc. Most articles will JOIN to NULL.

### 3.2 Multi-claim extraction yield

- Sample of 100 articles via `/api/articles?limit=100`:
  - 0 claims: 10/100 (10%)
  - 1-2 claims: 23/100 (avg = 2.24)
  - 3-5 claims: 67/100 (67%)
  - 6+ claims: 0/100 (0%) — **no article in the sample produces 6+ claims**,
    so the CLAIMS_FOR_FULL_CREDIT=6 density factor is never reached.

### 3.3 Fact-check verdict distribution

- Live `/api/analytics/verdicts`: `{verified: 6, disputed: 2,
  partially_true: 5, unverified: 1025, total: 1044}`.
- **98.18% of all fact-check rows are UNVERIFIED.** Only 6 verified, 2
  disputed, 5 partially-true.
- By claim category (`/api/analytics/claims`):
  - anecdotal 544 (0 verified, avg conf 0.054)
  - policy 278 (0 verified, avg conf 0.176)
  - statistical 229 (0 verified, avg conf 0.048)
  - predictive 56 (1 verified, 1 disputed, avg conf 0.246)
  - scientific_causal 24 (5 verified, 1 disputed, avg conf 0.494) ← the
    only category with non-trivial verified yield

### 3.4 3-axis source coverage

- Live `/api/methodology/source-tiers`: 79 source tiers (39 T1, 20 T2, 20 T3).
  **Zero of them surface `editorial_score / factcheck_score / transparency_score`** —
  the response keys are `source_name, domain, tier, prior_bonus, evidence_url,
  classification, retracted_count`. The 3-axis schema is in the DB (mig 041)
  but not in the SELECT clause at `source_tier_service.py:53,118-119,149`.
- The fence migration 045 was supposed to NULL-fill + assert
  P0001 — but since the columns are never SELECTed, no consumer would catch
  a regression to NULL.

### 3.5 Deep-search relevance thresholds (post 7c0404b)

- Confirmed in `src/backend/app/domains/intelligence/deep_search_service.py`
  (recently fixed; `7c0404b` commit message: "deep-search relevance threshold
  + English-default enrichment"). Live deep-search not auth-gated for compare
  / weather; the standard internal-corpus path runs against pgvector HNSW
  with `ef_search=100` (per the TruthMachine extract §4.1).

### 3.6 Bias auditor / chi-squared

- **MISSING — confirmed.** Grep for `bias|chi[-_]?squared|chi2|ChiSquare`
  across `src/backend/` returned only references to the LLM
  "shared-prompt bias" guard in `multi_llm_verifier.py:256,412` and to
  "potential_biases" in research-report JSON. No standalone bias-auditor
  module exists.
- The CARF report (§10.2) flags this as a 2-day gap; the strategy doc
  (§5.8) ranks it as the cheapest CARF-grade win.

### 3.7 Numeric grounding tolerance (1%)

- `src/backend/app/domains/intelligence/numeric_grounding.py` (per
  TruthMachine extract §6 — pure functions, ≤1ms, unit-aware °C/%/ppm/Gt/
  MtCO2e). Tolerance is 1%. Live deep-search includes it in the verifier
  chain. The TruthMachine report rated this 5/5; no code change suggests
  regression.

### 3.8 Identified calculation gaps

1. **3-axis source scoring is dead in production** (the most consequential
   gap). Math wired; data unreachable.
2. **Multi-claim extraction yield is too sparse** — 0% of sampled articles
   produced 6+ claims, so the density factor never reaches full credit. The
   `full_text_fetch` pre-pass shipped in `b3caa18` (Slice 4b) but the live
   numbers say it isn't lifting claim yield meaningfully.
3. **No bias auditor**. Chi-squared on claim-type × verdict is the missing
   CARF feature most-acutely flagged.
4. **`bayesian_credibility` naming dishonesty unchanged** —
   `bayesian_credibility.py:84-141` runs weighted-average, not Bayesian.
   Both reports call this out as the highest-leverage rename + MCMC mode.
5. **`reliability_scorer` JOIN on `source_name` is text-ILIKE** (`:449-450`)
   — most articles will never match a tiered source. The JOIN should be on
   `source_domain` (which both tables carry).

---

## 4. Agentic skills + features sync

### 4.1 Backend SKILLS_REGISTRY count

- `src/backend/app/domains/intelligence/skills.py:74-308` defines **15 skills**.
- Live `/api/skills` returns exactly 15 skills with correct mode classification
  (8 auto / 7 confirm). Verified verbatim.

### 4.2 Frontend ChatActionType union count

- `src/frontend/src/lib/chatActionDispatcher.ts:24-42` lists **15 entries**.
- `ACTION_MODES` at `:59-76` classifies the same 15 with mode strings.

### 4.3 Prompt template AVAILABLE ACTIONS count

- `src/backend/app/domains/intelligence/prompts.py:413-428` enumerates exactly
  **15 actions** in the `AVAILABLE ACTIONS` block. Each line begins
  `"- <skill_name>:"` and the 15 names are an exact set-match against
  `SKILLS_REGISTRY.keys()`.

### 4.4 useSkills.ts FALLBACK_SKILL_MODES count

- `src/frontend/src/lib/useSkills.ts:61-83` — **15 entries** (verified). The
  prior 9-entry stale fallback flagged by the Alignment Gap Inventory has
  been bumped to 15 (commit `3ad4a38`).

### 4.5 Pin tests passing

- `tests/api/test_agentic_skill_pin.py:122-224` contains 9 pin tests:
  `test_prompt_template_lists_all_frontend_actions`,
  `test_prompt_template_does_not_advertise_unknown_actions`,
  `test_dispatcher_union_matches_local_constant`,
  `test_prompt_template_says_exactly_n_actions_in_copy`,
  `test_chat_synthesis_with_actions_prompt_exists`,
  `test_registry_matches_frontend_dispatcher`,
  `test_registry_modes_match_frontend`,
  `test_registry_matches_prompt_template`,
  `test_every_skill_has_description`,
  `test_every_skill_has_at_least_one_parameter`.
- Tests are present in the repo; CI status not observable from this
  environment but the live `/api/skills` matches the in-repo registry so
  no merge-blocking drift today.

### 4.6 Per-skill dispatcher + handler evidence

| Skill | Backend handler | Frontend dispatcher | UI affordance |
|---|---|---|---|
| `navigate` | `chat_routes.py:100+` consumes via skills registry | `chatActionDispatcher.ts:158-162` | Global (any link) |
| `analyze_url` | `url_analysis_routes.py:1548-1559` | `:163-167` | `/analyze` page |
| `apply_search_filters` | `search_routes.py:215` | `:168-176` | `/search` page |
| `apply_map_filters` | `map_routes.py` | `:177-182` | `/map` page |
| `open_methodology_section` | `methodology_routes.py` | `:183-186` | `/methodology` page |
| `open_country` | `map_routes.py:GET /api/map/country/{cc}/detail` | `:187-191` | `/map`, `/country/[code]` |
| `start_deep_search` | `deep_search_routes.py:148` | `:192-198` | `/deep-search` page |
| `bookmark_article` | `user_routes.py:533-708` (legacy) | `:246-288` (still legacy `/api/user/bookmarks/{id}`) | Article header BookmarkButton |
| `start_calibration_label` | `methodology_routes.py:calibration/labels` | `:203-209` | `/analyze` post-submission |
| `open_company` | `company_routes.py` | `:210-216` | `/companies` (+ now in GlobalNav) |
| `verify_corporate_claim` | `company_routes.py:103-180` | `:293-328` | `/companies/[ticker]` claim verify form |
| `save_item` | `saved_items_routes.py:1-244` (polymorphic) | `:331-378` | `SaveButton.tsx` (3 of 8 types — article, company, country) + chat |
| `subscribe_research_topic` | `research_feed_routes.py:116` | `:381-419` | `ResearchFeedPanel.tsx` (NEW, on `/research`) |
| `explore_scenario` | `scenario_routes.py:119` | `:226-235` | `ScenarioExplorerCard.tsx` (NEW, on `/country/[code]:518`) |
| `analyze_corporate_report` | `company_routes.py:186` | `:423-475` | `/companies/[ticker]:491-528` analyze-report form (NEW) |

- **`bookmark_article` still points at the legacy `/api/user/bookmarks/{id}`**
  endpoint (chatActionDispatcher.ts:246-288). The polymorphic
  `/api/user/saved` is what new UI uses; the article BookmarkButton +
  chat skill have not been migrated.
- All other 14 skills have a dispatcher implementation. **3 previously
  chat-only skills now have direct UI affordances** (subscribe, scenario,
  analyze-report) — the Alignment Gap audit's top-priority list was
  fulfilled.

---

## 5. Per-persona feature coverage

The TruthMachine report enumerates 7 personas; reality is **two view modes
(Public, Business)** plus per-tier quota tiering. The audit below treats each
persona as a notional buyer with a workflow shape, lists the platform features
that genuinely serve it today, and flags gaps.

### 5.1 Consumer (curious citizen)

- **Stated PRIMARY needs**: useful headline credibility chip; URL paste →
  understandable verdict; plain-language explainer.
- **Features serving today**:
  - `/analyze` URL analyser (`src/frontend/src/app/analyze/page.tsx`) →
    POST `/api/analyze-url` pipeline.
  - `/search` feed with credibility chip
    (`src/frontend/src/app/search/page.tsx`).
  - Plain-language formatter
    (`src/frontend/src/lib/plainLanguage.ts:43-203`).
  - Map walkthrough (4 layers + biomes = 5 layers, plus compare +
    chat = 7 walkthrough steps; `src/frontend/src/components/map/MapWalkthrough.tsx:28-94`).
  - Free tier: 3 saved / 3 searches / 2 deep-research / 1 URL analysis /
    1 compare per month (`api/quota_service.py:44-50`).
- **Gaps per strategy report (TruthMachine §7.4)**: verifier yield low (~10/100
  confidence — confirmed live); "personalisation footprint is one URL toggle"
  (correct — no persona settings).
- **Free/paid gating**: most consumer flows are free; URL analysis is
  capped at 1/month (gated upgrade trigger).

### 5.2 Journalist

- **Stated PRIMARY needs**: traceable provenance; cross-source corroboration;
  share-quote-ready chips.
- **Features serving today**:
  - Provenance ledger walk via
    `GET /api/methodology/audit-trail/{claim_id,article_id,url_analysis_id}`
    (`api/methodology_routes.py:347-358+`).
  - Multi-LLM verifier outputs Jaccard agreement
    (`multi_llm_verifier.py:14-30+`).
  - OG metadata shipped Slice 5b (`4789a4e`) — share previews land properly.
  - `save_item` polymorphic API + skill.
- **Gaps per reports**:
  - 3-axis chip not surfaced on article cards (axes are in the schema but
    never reach the FE).
  - **Provenance ledger live-empty** — `/api/methodology/audit-trail/article/<id>`
    returned `{records: [], total: 0}` for a spot-checked article. The
    journalist's drill-down returns nothing.
- **Free/paid gating**: export is paid (standard+; `export_routes.py:247,338`).
  Most provenance reads are free.

### 5.3 ESG / Sustainability Officer

- **Stated PRIMARY needs**: corporate claim verification; CSRD / IFRS S2 /
  TCFD / TNFD compliance framing; greenwashing flags (ECGT); audit-grade evidence.
- **Features serving today**:
  - `/companies/{ticker}` page with view=business toggle
    (`src/frontend/src/app/companies/[ticker]/page.tsx:208-275`).
  - `/api/companies/{ticker}/analyze` (single-claim) +
    `/api/companies/{ticker}/analyze-report` (multi-claim from URL/text,
    shipped 12d9e9e) — both with UI cards now.
  - SBTi adapter live (200+ companies; verified via /api/companies live).
  - Business-view plain-language formatters
    (`plainLanguage.ts:289-352`).
  - ECGT keyword matcher + SBTi-validation lookup + numeric grounding pipeline.
- **Gaps per reports**:
  - CDP + NZT remain stubs (`cdp_adapter.py:25-30`, `nzt_adapter.py`).
  - Compliance chips are decorative metadata, not auditable verification
    rules (TruthMachine P166).
- **Free/paid gating**: corporate claim analyser uses `url_analyses` quota
  (gated to standard+).

### 5.4 Climate Scientist / Researcher

- **Stated PRIMARY needs**: trustable-enough-to-cite numbers; published
  calibration curve; entity grounding; ability to re-run independently.
- **Features serving today**:
  - Hybrid retrieval (`hybrid_rag_service.py` per TruthMachine §4.4 — full
    RRF on vector + FTS + entity-BFS).
  - `/api/research/upload` accepts PDF/DOCX/TXT/HTML up to 25 MiB (shipped
    e44a1a3).
  - `/api/research/subscriptions` + CrossRef poller (mig 047) — **note
    poller not scheduled, §1.4**.
  - Causal claim analyser (LLM extraction; no DoWhy refutation —
    `causal_claim_analyzer.py`).
- **Gaps per reports (TruthMachine §7.1)**:
  - Calibration curve has 0 labels live (`/api/methodology/calibration`
    returns `n_labels: 0, note: "awaiting reviewer input"`).
  - ada-002 embeddings unchanged (deprecated; GX10 audit recommends BGE-M3).
  - **No entity grounding** (only numeric grounding live).
  - **No external benchmark** (ClimateFEVER / ClimateX / IPCC AR6 set —
    none wired).
- **Free/paid gating**: research upload likely Professional+ tier; not
  enforced via `require_premium` (no gate in `research_routes.py` for
  upload path observed in grep).

### 5.5 Policymaker

- **Stated PRIMARY needs**: trustable evidence for briefings; scenario
  projections; international comparisons.
- **Features serving today**:
  - Country passport (`country/[code]/page.tsx`) — 22 hand-curated biome
    narratives + 173 generic fallback
    (`country_biome.py:35-53`).
  - `ScenarioExplorerCard` (NEW) on country page —
    `country/[code]/page.tsx:518` calls
    `/api/scenario/country/{cc}?target_warming_c=&horizon_year=`. Verified
    live for DE/2.5°C/2050: returns interpolated anomaly 2.5°C with
    bracketing SSP1-2.6 (1.9) + SSP2-4.5 (2.6) and an explicit
    "INTERPOLATION, NOT SIMULATION" disclaimer.
  - Map compare mode (`MapCompareView.tsx`).
- **Gaps per reports**:
  - No briefing-mode PDF export (would be a 2-day add per TruthEngine §3.5.1).
  - No POLICY entity surface (entities extracted to JSONB but no
    `/policies/[id]` page).
  - Scenario interpolation is honest but is not a real climate-model backend.

### 5.6 Financial Analyst

- **Stated PRIMARY needs**: portfolio-scale workflow; physical+transition
  risk; defensible numbers for fund disclosure.
- **Features serving today**:
  - Per-company SBTi validation + net-zero target year
    (`company_routes.py:100-128`).
  - Business-view climate risk framing (`plainLanguage.ts:322-352`).
  - Map climate-risk layer (`InteractiveClimateMap.tsx:133-141`).
  - API keys (`api_key_routes.py:205,295`, gated Professional+).
- **Gaps per reports**:
  - No portfolio-scale CSV upload + aggregate scoring path.
  - No transition-risk score (only physical-risk via map layer).
  - SBTi country mapping covers ~190 countries
    (`900af29` fix) but the live `companies` table still shows many rows with
    `country_code=NULL` (e.g. "10 to 2 Consulting, LLC", "10x Genomics" both
    NULL in the 10-row sample) — partial-index dedup doesn't apply.

### 5.7 Business Decision-Maker (board / C-suite)

- **Stated PRIMARY needs**: board-ready framings; greenwashing exposure flags;
  one-page briefings.
- **Features serving today**:
  - Country passport + Company detail business-view toggles.
  - Compliance chips (CSRD / IFRS S2 / TCFD / TNFD per KPI;
    `plainLanguage.ts:394-414`).
  - Business-flavoured formatters
    (`plainLanguage.ts:260-386`).
- **Gaps per reports**:
  - No board-ready PDF export.
  - Compliance chips are decorative — not paired with verification rules.
  - No greenwashing-exposure rollup at portfolio level.

### 5.8 Cross-persona summary

| Persona | Real surfaces today | Major gap | Free/paid split |
|---|---|---|---|
| Consumer | analyze + search + map + biome map walk | verifier yield low | Mostly free; 1 URL/mo |
| Journalist | provenance ledger + OG + multi-LLM | ledger empty live | Read free; export paid |
| ESG | companies + SBTi + ECGT + analyze-report | CDP/NZT stubs; chips decorative | Standard+ for analyze flow |
| Scientist | hybrid RAG + research upload | calibration n=0 live; ada-002 | Free read; Professional uploads |
| Policymaker | country passport + scenario card + compare | no briefing export | Free |
| Analyst | SBTi + business view + API keys | no portfolio path | Pro+ for API |
| Business | view toggle + compliance chips | chips decorative; no board export | Free read |

The platform genuinely serves **two product surfaces (Public + Business view
modes)** with persona-flavoured copy; the 7-persona claim in the architecture
report is aspirational. This matches the Honest-Gap-Audit v2 item 16
correction.

---

## 6. Free vs Paid split audit

### 6.1 Quota service (Free tier source of truth)

- `api/quota_service.py:44-93` defines the 5-tier ladder:
  - **anonymous**: 0/0/0/0/0 — must sign in for anything gated
  - **free / freemium**: `saved_articles=3, saved_searches=3, deep_research=2,
    url_analysis=1, compare=1` (lifetime for saves, monthly for the rest)
  - **basic / standard**: 50 / 25 / 15 / 5 / 10
  - **professional**: -1 / -1 / 100 / 30 / 50
  - **enterprise**: all -1 (unlimited)

### 6.2 Rate limiter (legacy day-rate caps)

- `api/rate_limiter.py:21-79` adds per-day caps in addition to quota:
  freemium has `articles_per_day=10, searches_per_day=10,
  discovery_queries_per_day=1, countries_limit=3`.
- `data_source_tiers`: freemium = `["public"]`; standard = `+ "research"`;
  professional+enterprise = `+ "scientific"`.

### 6.3 Premium feature gating

- `rate_limiter.py:456-475` enumerates 15 premium features and which tiers
  unlock them. The `check_premium_feature()` helper has **16 call sites**
  across `api/` (grep verified):
  - `api_key_routes.py:205,295` — api_access (Professional+)
  - `deep_search_routes.py:314,365` — weather_context (Standard+),
    deep_search (Professional+)
  - `export_routes.py:247,338,398,487` — export (Standard+)
  - `search_routes.py:215` — semantic_search (Professional+)
  - `search_routes.py:379,436` — saved_searches (Standard+)
  - `url_analysis_routes.py:24` — gated via quota_service, not require_premium
- **Premium-only features actually enforced today**: API keys, deep_search,
  weather_context, exports, semantic_search, saved_searches.
- **Features the rate_limiter ADVERTISES as premium but DOES NOT enforce**:
  `notifications`, `infographics`, `feed_customization`, `source_registration`,
  `document_ingestion`, `comparative_analysis`, `advanced_insights`,
  `advanced_analytics` — none of these have grep-hits for
  `check_premium_feature(`. The advertised tier matrix is partly fictional.

### 6.4 Smart-split assessment

- **What is correctly free**:
  - Article reading + search (10/day cap is generous for casual users).
  - Country passport + map biomes + scenario explorer (read-only).
  - 1 URL analysis/month (lets a free user "try the analyser").
  - 2 deep-research/month (lets them sample the killer feature).
  - 3 saves lifetime (forces upgrade for power users).
- **What is correctly paid**:
  - Deep search (Professional+) — the most expensive call.
  - Exports (Standard+) — value-aligned with B2B paying customers.
  - API access (Professional+) — fits portfolio-scale buyers.
  - Semantic search (Professional+).
- **What is missing/mis-split**:
  - **Analyze-report endpoint (corporate report analyzer) has no gating** —
    `company_routes.py:186` does not call `check_premium_feature()`. A
    free user can run heavy LLM extraction against a 100-page PDF for free.
  - **Research upload** — `/api/research/upload` (e44a1a3) is heavy LLM but
    no explicit `require_premium` gate; depends on quota_service alone.
  - **Scenario explorer** — `/api/scenario/country/{cc}` is fully open. Fine
    since it's read-only interpolation, but premium tier should perhaps get
    finer-resolution scenarios.
  - **No "Business" persona tier** — the rate_limiter has freemium/standard/
    professional/enterprise; the planned business decision-maker price-point
    (e.g. mid-market analyst per-seat) is not defined.

### 6.5 Identified upgrade-friction issues

1. **Free saves cap of 3 (lifetime) is aggressive** — competitive sites
   (OWID, Climate Watch) don't gate saves at all. Likely converts
   power-users but alienates casual users at session 3.
2. **The advertised premium feature matrix (rate_limiter.py:456-475) lists
   features that have no enforcement** — surfaces in pricing copy that does
   not match reality.

---

## 7. Map audit

### 7.1 Layers shipped

- `src/frontend/src/components/map/InteractiveClimateMap.tsx:67-73`
  enumerates **5 layers**:
  - `article_density`
  - `temperature_anomaly`
  - `climate_risk`
  - `source_diversity`
  - `biomes` ← Phase 11 addition (2026-05-25)
- Biomes layer fills countries by Köppen colour
  (`InteractiveClimateMap.tsx:107-108`) and adds emoji markers at centroids.

### 7.2 Biome data coverage

- Live `/api/map/biome-overview` returns **196 countries** with non-null
  `biome_id`, `biome_emoji`, `koppen_color`. (Owner mandate expected 196 ✓.)

### 7.3 Country-card on click

- `MapCountryPanel.tsx:51-74` defines `CountryDetail`:
  - `article_count`, `avg_credibility`, `climate_risk_score`,
    `category_breakdown`, `weather`, `temperature_anomaly`, `sources`.
- The card surfaces article_count + avg_credibility + per-source breakdown,
  plus a "Compare" affordance.
- **NOT surfaced on country card**: `claim_count`, `verified_claim_count`,
  3-axis source scores, scenario explorer link, latest articles list with
  reliability chips. (Latest articles ARE in `recent_articles` from
  `/api/map/country/{cc}/detail` but render as titles only, no chip per
  the code I read.)

### 7.4 3-axis source scores per-country

- **NOT shown anywhere on map**. The country card breaks sources by
  source_name + article_count + avg_credibility only.

### 7.5 Scenario explorer linked from map

- **NOT directly linked from map.** ScenarioExplorerCard renders on
  `/country/[code]/page.tsx:518` (the country passport), but the map's
  `MapCountryPanel` does not have a "Try scenario explorer" CTA.
- Workaround: clicking "Open full passport" jumps to country page which has
  the scenario card.

### 7.6 Map walkthrough — all current?

- `MapWalkthrough.tsx:28-94` has **7 steps**: Welcome → Layer 1 (article
  density) → Layer 2 (temperature anomaly) → Layer 3 (climate risk) →
  Layer 4 (source diversity) → Layer 5 (biomes + climate zones; NEW) →
  Compare → Chat. The newly-shipped biome layer has been added to the
  walkthrough.

### 7.7 Identified map gaps

1. **3-axis source scores never reach map UI** — the country card shows a
   single `avg_credibility` number per source, missing the editorial /
   factcheck / transparency decomposition.
2. **`claim_count` and `verified_claim_count` per country not on map** —
   these exist on article rows but the country-detail endpoint exposes
   `articles_by_category` and `avg_credibility`, not claim-level rollups.
3. **No scenario-explorer CTA from map country panel** — users have to
   navigate to the country passport first.
4. **`overall_credibility` chip per article on the country card is null**
   in spot-checks (`/api/map/country/DE/detail` returned `credibility: null`
   on the 5 recent articles sampled).

---

## 8. Source scoring + evaluation audit

### 8.1 source_credibility_tiers row count

- Live `/api/methodology/source-tiers` returns **79 rows** total.
- Tier distribution: T1=39, T2=20, T3=20. (No "unknown" or "retracted"
  rows surfaced via this endpoint; either column is filtered or no rows
  exist.)

### 8.2 3-axis NULL count

- **Cannot verify directly from live API** — the SELECT clauses at
  `source_tier_service.py:53,118-119,149` don't include the 3-axis columns,
  so the public endpoint doesn't expose them.
- Mig 041 backfills via tier defaults (T1→90/90/90, T2→70/75/65, T3→55/50/60,
  unknown→30/25/30, retracted→5/5/5) at lines 24-107 of the migration. Mig
  045 fences NULLs with P0001 assertion.
- **Inference**: if mig 041 + 045 both applied, all 79 surface rows have
  non-null 3-axis. **But** since no application code SELECTs those columns,
  the fence's protective value is theoretical.

### 8.3 Tier distribution

- 39 T1 (49.4%), 20 T2 (25.3%), 20 T3 (25.3%) on the curated table.
- **But** in `/api/v2/sources?limit=200` (the FE-consumed table), 97 of 104
  rows have `tier=None` (93%) — meaning the per-source profile (which is
  what the article ingest path actually consumes) is overwhelmingly
  un-tiered.

### 8.4 Live verification — 5 spot-checks

- `/api/methodology/source-tiers/by-domain?domain=reuters.com`:
  `{tier: "T2", prior_bonus: 15, evidence_url: ..., classification:
  "wire_service_corrections"}` ✓ (curated)
- IPCC, NASA, Nature, CSIRO Australia all surface via `/api/v2/sources`
  with non-null `credibility_score` (97, 96, 95, 94 respectively) and
  matching `editorial_standards/fact_check_record/transparency_level`
  string-tier columns.

### 8.5 New-source registration path

- `api/source_registry_routes.py` — `/api/sources/register`,
  `/api/sources/validate`. Per the Honest Gap Audit v2 item 10, registering
  a new source does NOT auto-assign a tier or 3-axis defaults. New sources
  land with NULL 3-axis if the source_credibility_tiers row is missing.
- `api/source_suggestion_routes.py` — user-submitted suggestions go through
  a review queue; no automatic scoring.

### 8.6 Identified source-scoring gaps

1. **The single most expensive gap on the truth surface (per both reports
   and confirmed here)** — `source_tier_service.py:53,118-119,149` SELECT
   clauses don't include the 3-axis columns. Until that's patched, every
   downstream consumer (article scorer, source-profile UI, methodology
   endpoint) is using only the rolled-up `prior_bonus + tier`.
2. **Article-row `source_credibility_score` is NULL across the 100-row
   sample** — even the legacy single-number scoring isn't being stamped
   onto fresh articles.
3. **93% of `/api/v2/sources` rows are un-tiered** — most of the corpus
   sources aren't even in the curated 79-tier table.

---

## 9. Logged-in user data connection

### 9.1 Saved items (polymorphic)

- Mig 042 (`042_saved_items_table.sql`) + `api/saved_items_routes.py:1-244`
  (4 endpoints: GET/POST/check/DELETE).
- 8 item types declared: `article, analysis, claim, search, company,
  country, deep_search, feed_setting` (per the `save_item` skill in
  `skills.py:218-252`).
- Live `/api/user/saved` (unauth) returns 401 — endpoint exists.

### 9.2 Export endpoints

- `api/export_routes.py:225,328` defines `POST /article/{id}/pdf` and
  `POST /search/csv` (both Standard+ tier).
- Live `/openapi.json` shows `/api/export/article/{article_id}/csv` and
  `/api/export/article/{article_id}/pdf` as GET routes — Slice 1 (`36af118`)
  fix is live (the prior anchor-href GET routes now exist).
- Live: cannot test without JWT.

### 9.3 User-bound saved queries (recurring)

- `api/saved_query_routes.py:1-40` — recurring search subscription API for
  articles. CRUD + run endpoint (`/saved-queries/{id}/run`).
- Per Honest Gap Audit v2 item 13, not yet wired to /research.

### 9.4 Research subscriptions tied to user_id

- Mig 047 ties `research_subscriptions` to `user_id` (verified by file
  presence and route shape in `api/research_feed_routes.py:116-450`).
- **Cron not scheduled** (§1.4) so the poller doesn't deliver new items
  automatically.

### 9.5 Saves page reflects user data

- `src/frontend/src/app/saves/page.tsx` lists all 8 item types with filter
  chips + remove button. Wired ✓. Live `/saves` returns 200 (frontend
  renders the page shell; auth-gated content requires login).

### 9.6 Persona personalization (Public/Business toggle)

- Wired in:
  - `src/frontend/src/app/country/[code]/page.tsx:143,317,352` —
    `?view=business` URL state.
  - `src/frontend/src/app/companies/[ticker]/page.tsx:85-275` — same toggle.
- `plainLanguage.ts:289-352` provides the business-flavoured copy.
- **Not a true persona system** — only Public/Business; the other 5
  enumerated personas have no routing. Quota tier influences feature gating
  but not framing.

### 9.7 Identified gaps

1. **`bookmark_article` legacy path** — BookmarkButton + chat skill still
   POST to `/api/user/bookmarks/{id}` instead of polymorphic
   `/api/user/saved` (Honest Gap Audit v2 item 15; still open).
2. **Research subscriptions delivered nothing** to users because the
   CrossRef poller has no cron trigger.
3. **No user-bound "feed settings" saves UI** — `feed_setting` is in the
   item_type whitelist but no UI button creates one.

---

## 10. Benchmark snapshot (live API checks)

| Endpoint | HTTP | Result + quality flag |
|---|---|---|
| `GET /` | **404** | Returns `{"detail":"Not Found"}`. No root health page. |
| `GET /api/articles?limit=5` | 200 | 5 rows; `published_date` between 2018 and 2026-03; `enriched_excerpt`/`executive_brief`/`climate_context_summary` all NULL on every row; `source_credibility_score` NULL on every row; mean `reliability_score` ~71 with `overall_credibility=HIGH`. **Headline credibility "HIGH" on rows with null source score is the calibration honesty gap the strategy reports flagged.** |
| `GET /api/companies?limit=10` | 200 | 10 rows; 0 duplicate groups in a 200-row dedup-check (mig 043+044 holding). 5 of 10 sample rows have `country_code=NULL` (SBTi country mapping still misses many adapter rows). |
| `GET /api/map/biome-overview` | 200 | **196 countries** ✓ |
| `GET /api/map/country/DE/biome` | 200 | `biome_symbol: { biome_id: "temperate_forest", biome_emoji: "🍂", koppen_id: "C", koppen_color: "#2A9D8F" }` + 4 climate_effects + 3 key_facts + 3 drill_down_suggestions ✓ |
| `GET /api/scenario/country/DE?target_warming_c=2.5&horizon_year=2050` | 200 | `interpolated_anomaly_c=2.5`, bracketed by SSP1-2.6 (1.9) + SSP2-4.5 (2.6), `disclaimer: "INTERPOLATION, NOT SIMULATION..."` ✓ |
| `GET /api/methodology` | 200 | Prompts registry with 5 named prompts + SHA-256 fingerprints. `git_revision: null`. |
| `GET /api/methodology/source-tiers` | 200 | **79 source tiers** (T1=39, T2=20, T3=20). **3-axis columns NOT in the SELECT.** |
| `GET /api/methodology/calibration` | 200 | `n_labels: 0` — calibration corpus empty in production. |
| `GET /api/methodology/hallucination-rates` | 200 | `available: false, notes: ["claim_provenance unavailable (migration 021 not applied?)"]`. **The truth-machine provenance ledger is empty or unreachable.** |
| `GET /api/methodology/drift-thresholds` | 200 | `hardcoded_fallback: true, note: "Learned thresholds will be available after 60 days of production data"`. |
| `GET /api/drift/source-mix` | 200 | `recent_count: 0, baseline_count: 0, notes: "No articles in either window"`. |
| `GET /api/drift/prompt-fingerprints` | 200 | `recent_count: 0, baseline_count: 0, notes: "No claim_provenance rows..."`. |
| `GET /api/methodology/audit-trail/article/86db9c74-fd30-45f7-904e-a4d7c148512c` | 200 | `records: [], total: 0`. **Empty audit trail for a real article.** |
| `GET /api/skills` | 200 | **15 skills** ✓; modes split 8 auto / 7 confirm. |
| `GET /api/stats` | 200 | `total_articles=1664, articles_today=27, total_fact_checks=1044, verified_claims=0, average_confidence=10.43`. |
| `GET /api/analytics/pipeline` | 200 | `pending=898, completed=757, failed=9, verification_rate=0.455`. |
| `GET /api/analytics/verdicts` | 200 | `verified=6, disputed=2, partially_true=5, unverified=1025` (98% unverified). |
| `GET /api/countries` | 200 | 200 country rows; 60 (30%) have ≥1 article; 28 (14%) have ≥10. **140 countries have 0 articles.** Top: SI 419, BG 248, RO 144 (aggregator-dominated). |
| `GET /openapi.json` | 200 | **234 distinct paths** (counted via grep on the response). Includes: `/api/companies/{ticker}/analyze-report` (new), `/api/scenario/country/{cc}` (new), `/api/research/upload` (new), `/api/research/feed` (new), `/api/research/subscriptions` (new), `/api/admin/link-check[/summary]` (new), `/api/admin/research-poll` (new), `/api/user/saved[/check|/{id}]` (new). |
| `GET /api/admin/link-check/summary` | not tested | Requires `CORPORATE_SYNC_TOKEN` — not available in this audit env. |
| Frontend `/saves`, `/research`, `/companies`, `/map`, `/` | 200 (all) | Pages load shell; auth/content not asserted. |

---

## 11. Bottom-line composite score + next-sprint priorities

### 11.1 Axis grading (1-5)

| Axis | Score | Justification |
|---|---|---|
| Reliability (claim verification depth + accuracy) | **2.0** | 1044 fact_checks, only 6 verified (0.57%). avg_confidence=10.43/100. The pipeline runs but produces almost no usable signal. |
| Calibration (do scores predict reality?) | **1.5** | 0 calibration labels live. n=0 means no published curve. The HIGH labels on null-source articles are not calibrated. |
| Hallucination control | **3.0** | Numeric grounding is real + tight (1%). Entity grounding is MISSING. H-Neuron at 3 of 8 signals. Provenance ledger empty live → cannot demonstrate. |
| Sustainability composite math | **4.0** | The `/api/methodology/sustainability-formula` endpoint surfaces a documented 5-component weighted score with normalizer functions per indicator. Methodology version stamp ✓. |
| Source diversity + scoring | **2.5** | 79 curated tiers exist; 93% of /api/v2/sources rows are un-tiered. 3-axis schema present but no consumer reads it. Heavy ingest skew to aggregator feeds. |
| Persona breadth (real vs claimed) | **2.0** | Two view modes (Public, Business). 5 enumerated personas have copy + quota tier only. |
| Free/paid product market fit | **3.5** | Quota ladder is sensible (3/3/2 free; structured upgrade triggers). Some advertised premium features are not actually gated. Heavy LLM endpoints (analyze-report, research upload) need explicit gating. |
| Operational reliability | **3.5** | Cloud Build green; live API + frontend reachable; lean Cloud Run setup. 3 cron jobs missing. Provenance ledger silently empty is an alarming live state. |

**Composite: (2.0 + 1.5 + 3.0 + 4.0 + 2.5 + 2.0 + 3.5 + 3.5) / 8 = 22.0/40 = 2.75/5.**

Adding back the UX-scaffolding axis the owner mandated (was implicit):
the 15 agentic skills aligned end-to-end, the 4 new UI cards
(ResearchFeedPanel, ScenarioExplorerCard, analyze-report form,
SaveButton/Saves page) and the biome layer score **4.0** for "shipped
features visible to user". Combined: ~**3.05/5**.

Six weeks ago (per the user mandate context — early April), the composite
was ~2.4/5 (synthetic data dominant; no polymorphic saves; no 3-axis schema;
no biome layer; corporate page incomplete; 9 skills only). **Lift this
sprint window: +0.65 in composite**, almost entirely on the UX/protocol
axes — the truth-engine data axes barely moved.

### 11.2 Next-3-sprint sequenced roadmap

**Sprint A — Truth-engine data unblock (1-2 weeks)**

1. **Fix `source_tier_service.py` SELECT clauses** (3 SQL strings, 3 dict
   builds) to include `editorial_score / factcheck_score / transparency_score`.
   Extend `_attach_credibility_tiers` in `source_profiles.py:303-352`
   similarly. ~4 hours. Unblocks every 3-axis claim.
2. **Fix reliability scorer JOIN** at `reliability_scorer.py:449-450` — JOIN
   on `sct.domain = a.source_domain` (or canonicalised source_name), not
   `ILIKE source_name`. ~1 hour.
3. **Re-run article-reliability backfill** against the corpus once #1 and #2
   land. Then `source_credibility_score` and the 3-axis blend will be live
   on every article. ~2 hours job time.
4. **Investigate `claim_provenance` empty state** — verify mig 021 actually
   applied in prod; if so, find the silent write failure in
   `provenance.py:127-136`. Add an exception log threshold so a 100%
   write-failure rate triggers an alert. ~4 hours.
5. **Provision missing Cloud Scheduler jobs** (`cn-research-poll`,
   `cn-link-check`) in `provision-infra.sh:267-272` and `cloudbuild.yaml:237-244`.
   ~2 hours.

**Sprint B — Persona depth + audit-grade compliance pilot (1-2 weeks)**

6. **Surface 3-axis chips on article cards and SourceProfileCard** —
   `ArticleCard.tsx`, `SourceProfileCard.tsx`. Hover-expand showing 3 axes.
   ~6 hours.
7. **CSRD E1 audit-grade verification pilot** (TruthEngine §5.6 / §3.3.1) —
   wire SBTi rule walker into `/api/companies/{ticker}/analyze` for one
   chip; surface as interactive. **3-5 days.**
8. **External (Perplexity) citation credibility chip** —
   `deep_search_service.py` + `/deep-search/page.tsx`. ~6 hours.
9. **Migrate `bookmark_article` skill + BookmarkButton to
   `/api/user/saved`** to retire the legacy bookmark path. ~6 hours.

**Sprint C — Truth-engine architectural depth (2-3 weeks)**

10. **Bias auditor** — chi-squared on claim-type × verdict, source-tier ×
    verdict, country × verdict. New `bias_auditor.py` module + `/api/admin/
    bias/report` endpoint. ~2 days. CARF §10.2 + strategy §5.8.
11. **Entity grounding via spaCy NER** — extend
    `hallucination_detector.py:_check_entity_overlap` from simple-token to
    real NER. 2-3 days. TruthMachine P159 + CARF §13 item B4.
12. **`bayesian_credibility` rename + real PyMC `mode="mcmc"` branch** —
    rename module to `weighted_credibility`, add an MCMC path with 90%
    credible interval and epistemic/aleatoric split. 3 days.
13. **H-Neuron 3 → 8 signals** — direct numeric port from CARF upstream.
    1-2 days. Depends on #11.

---

End of doc — `docs/improvementplans/End2End-Audit-Benchmark-2026-05-26.md`
