# Master Prompt — Climatefacts.ai End-to-End Audit + Autonomous Fix Loop (v2 — Final Polish)

Paste this whole file as the first message of a fresh agent session. The agent reads it, walks the loop, and stops only when the acceptance b
ar in §6 is met or it has shipped its slice budget.

> **v2 changelog (2026-05-30)** — folds in the full `docs/improvementplans/fixes.md` punch-list (15 issue clusters from the user's hands-on review) on top of the v1 trust-engine audit. New: **Content-Scope Charter (§3)**, **Experience axes 9–13 (§5)**, a re-prioritised **P0/P1/P2 gap ledger (§7)** with `file:line` evidence verified by recon on 2026-05-30, an expanded **Cloud/Local mandate (§8)**, and a **Production-readiness streamlining section (§9)**. Evidence line numbers are "as of 2026-05-30 — re-locate before editing, lines drift." Several user-reported bugs were found **already fixed in code** during recon; those are flagged `VERIFY-ON-LIVE` (confirm against the live deploy + a hard cache/Service-Worker refresh — the screenshots in `docs/bugpics/` likely predate the fix).
>
> **v3 status (2026-06-01, session 3)** — ran with the full local docker stack up, so changes were validated against a running app (not blind). Shipped+deployed: off-topic articles now hidden from ALL listing surfaces (F1/T12 — `is_off_topic` column mig 056/057 + curated `topic_feedback` backfill + ~40 query sites + feedback-driven flagging; the ~916 curated/Eastern-EU-skew rows drop out), and KG relationships render as a visual node-link graph (F7, Playwright render-verified). Re-confirmed `VERIFY-ON-LIVE` items are **fixed in code**: F2 contrast (clean `dark:`-paired colours) and F4 export (POST+JWT). **Key finding:** the off-topic *per-article* class (the bus-accident example) CANNOT be caught by a keyword/SQL sweep — measured to mis-flag 65% of the real corpus (truncated RSS text + non-English climate sources) — and embeddings are unpopulated (0/666); it needs the §3/§8 LLM/GX10 relevance pass, for which the shipped column+filter+feedback plumbing is the write target. Full record: `docs/improvementplans/Deploy-Status-2026-06-01.md`.

---

## 1. Role + non-negotiables

You are the **Climatefacts.ai production validator + finisher**. Audit the live platform end-to-end against §3–§5, then ship prioritised fixes in batched, checkpointed commits — without compromising reliability, transparency, traceability, security, accessibility, or cost.

Bind these skills before doing anything else: `clilens-development`, `hooks-automation`, `verification-quality`, `swarm-orchestration`, `reasoningbank-intelligence`, `agentic-jujutsu`.

Non-negotiable rules (these override anything else):

- Obey `CLAUDE.md` batching law: 1 message = all related ops. TodoWrite, file edits, bash, memory ops are always batched.
- Never write to repo root. Code → `src/`, tests → `tests/`, docs → `docs/`, scripts → `scripts/`. (The root currently has stray files — see §9; clean them, don't add to them.)
- Never insert synthetic data. The mig 040 trigger rejects it; honour it.
- **Every audit finding cites `file:line`. No claim without evidence. If a finding contradicts a doc, the code wins — fix the doc.**
- Every fix slice: `npx claude-flow@alpha hooks pre-task` → checkpoint → batched edits → tests → `hooks post-task`.
- Every analytical statement in your artifacts (§7) must be traceable to a source: code path, migration, doc paragraph, live API response, or memory key. Mirror the platform's own "every claim has provenance" contract.
- **Honesty bar**: when a feature is *present but shallow*, grade it as shallow — do not round up. When the user reports a bug you cannot reproduce in code, say "code looks correct at `file:line`; reproduce on live before/after" rather than silently closing it.
- Cost rule: when choosing cloud vs GX10, never trade observed quality (≥1pp regression on any §4 axis) for cost. Cost wins only when quality is statistically tied.

## 2. Bounded scope (do NOT re-discover what's already mapped)

Read these once, then operate on them:

- This file's source punch-list: `docs/improvementplans/fixes.md` (the 15 clusters) + screenshots `docs/bugpics/Bug1.png`, `docs/bugpics/climateanalytics.png`.
- Latest baseline & axis grades: `docs/improvementplans/End2End-Audit-Benchmark-2026-05-27d.md` (composite ~3.5/5, loop 4).
- KG honest assessment + 3-phase plan: `docs/improvementplans/KG-Robustness-Audit-2026-05-27.md`.
- Golden-artifact target shapes: `docs/improvementplans/Golden-Artifact-Examples-2026-05-27.md`.
- GX10 economics + workloads: `docs/reports/asusgx10inferencestrategy.md`, `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md`, `docs/improvementplans/GX10-Deployment-Runbook-2026-05-25.md`.
- Persona truth: `docs/improvementplans/TruthEngine-PersonaFit-Design-2026-05-25.md`.

**Path map (verified 2026-05-30 — use these, don't guess):**

- **Frontend**: Next.js 14, routes under `src/frontend/src/app/` (`articles`, `companies`, `country`, `dashboard`, `deep-search`, `feed`, `map`, `methodology`, `research`, `saves`, `search`, `sources`, …). Components under `src/frontend/src/components/`. i18n at `src/frontend/src/lib/i18n.ts`. Tailwind `src/frontend/tailwind.config.js` (`darkMode: 'class'`).
- **Backend**: FastAPI route layer in `api/*.py`; DDD domains in `src/backend/app/domains/` (`content`, `identity`, `intelligence`, `trust`); Celery tasks in `src/backend/app/tasks/`; config in `src/backend/app/core/`.
- **Agentic skills**: `SKILLS_REGISTRY` in `src/backend/app/domains/intelligence/skills.py` (~14 actions; the in-file "9" comment is stale). Pin test: `tests/api/test_agentic_skill_pin.py`. Frontend dispatcher: `chatActionDispatcher.ts`.
- **Data layer**: PostgreSQL 16 + pgvector (HNSW), migrations under `infrastructure/database/migrations/versions/`, runner `scripts/run_migrations.py`.
- **Live deploy**: API `https://climatenews-api-srzwxdzmaq-ez.a.run.app`, FE `https://climatenews-frontend-srzwxdzmaq-ez.a.run.app`.

## 3. Content-Scope Charter — what belongs on Climatefacts.ai (cluster 1, HIGH PRIORITY)

**Problem (confirmed 2026-05-30):** there is **no topical relevance gate at ingest**. `src/backend/app/tasks/ingestion.py:376-388` (`scheduled_rss_ingestion`) and `src/backend/app/domains/content/data_sources/rss_adapter.py:213-286` (`_parse_feed`) accept entries after URL-dedup only (`dedup_against_existing`, `rss_adapter.py:465-495`); category detection (`ingestion.py:158-170`) is **descriptive, not gating**. A bus-accident story from a general feed (e.g. "Andina Peru") passes. There is an unused `src/backend/app/domains/intelligence/editorial_gate.py` — **check whether it's wired into the ingest path; it is the natural home for this gate.**

**The charter the platform must enforce (and surface to reviewers):** an item is in-scope iff it materially concerns one of:
1. Climate science, observations, attribution, projections.
2. Climate impacts & adaptation (incl. extreme-weather events **when a climate-causal link is data-traceable** — e.g. a landslide/flood/heatwave attributed to climate effects, *not* a generic traffic accident).
3. Mitigation, decarbonisation, energy transition, cleantech, renewables.
4. Climate & sustainability **policy / regulation / finance** (CSRD, SBTi, CDP, TCFD, ISSB, carbon markets).
5. Corporate sustainability / ESG disclosure & greenwashing.
6. Biodiversity / nature / land / ocean **where climate-linked**.

**Acceptance criteria for the fix:**
- A relevance gate runs at ingest (keyword + embedding-similarity to a climate centroid, or a cheap classifier — Lane A/B, GX10-eligible per §8) and **persists a reviewer-traceable justification** per article (matched reason + score), not just a boolean.
- Off-topic articles already in the corpus (gap ledger T12; the ~916 from deactivated chatty feeds) get a backfill `is_off_topic`/relevance flag and drop out of map/search/compare surfaces (`is_synthetic = FALSE` pattern).
- The `/methodology` page documents the inclusion rule in plain language.

## 4. Trust axes (1–8) — grade each 0–5, every run

For each: state **current score**, **target**, **delta drivers as `file:line`**, **single highest-leverage fix**. Mirror `End2End-Audit-Benchmark-2026-05-27d.md` §11.

| # | Axis | Target | Required evidence |
|---|---|---|---|
| 1 | Reliability (claim verification depth + accuracy) | ≥3.5 | avg claims/article, % with ≥6 claims, verified rate; extractor path in `src/backend/app/domains/intelligence/services.py` |
| 2 | Calibration (do scores predict reality?) | ≥3.0 | `n_labels` per signal, Brier, ECE via `/api/methodology/calibration` (still `n_labels=0` — needs reviewer pass) |
| 3 | Hallucination control | ≥4.0 | spaCy NER live (`api/Dockerfile`); 8-signal detector `hallucination_detector.py`; **entity boilerplate filter** (see F7) |
| 4 | Source diversity + 3-axis scoring + rating coverage | ≥4.0 | `articles.source_credibility_score` distribution; 3-axis surfaced in ≥4 UI components; **% of `source_profiles` with non-NULL tier** (see F11) |
| 5 | Persona breadth (real vs claimed) | ≥3.5 | dashboard `PersonaLensSection`; honest "2 view modes + 7 copy flavours", not "7 personas served" |
| 6 | Free/paid alignment | ≥4.0 | every premium feature in `api/rate_limiter.py` / `api/quota_service.py` has a `check_premium_feature(`/`check_and_raise(` call site |
| 7 | Operational reliability | ≥4.0 | Cloud Scheduler crons in `infrastructure/gcp/provision-infra.sh`; `MIGRATIONS_TOLERATE_ERRORS` audit; breaker state `/api/admin/llm/breakers` |
| 8 | KG / semantic / RAG robustness | ≥3.0 | `/api/articles/{id}/kg` 200 not 500; canonical mig 049 promoted; NER worker populating `article_entities`; RRF fusion in `hybrid_rag_service.py` |

## 5. Experience axes (9–13) — new in v2, grade each 0–5

| # | Axis | Target | Required evidence |
|---|---|---|---|
| 9 | **Content scope & editorial relevance** (cluster 1) | ≥4.0 | relevance gate exists at ingest + per-article justification persisted; off-topic rate in a 100-article sample (§3) |
| 10 | **Visual integrity & accessibility** (cluster 2/3) | ≥4.0 | WCAG-AA contrast on chat/compare/report surfaces; theme state coherent (see F2/F3); icon-only buttons have `aria-label`; `<main>` landmarks |
| 11 | **Surface feature-depth** (clusters 5–11) | ≥3.5 | per-surface depth audit: deep-search, map, KG, research, companies, saves, sources — count "present-but-shallow" vs "complete" against fixes.md asks |
| 12 | **Geographic & verdict balance** (cluster 12) | ≥3.5 | per-country article distribution (no Eastern-EU skew); verdict distribution (not ~99% Unverified); analytics admin-gated |
| 13 | **Localisation robustness** (cluster 13) | ≥3.0 | locale coverage; missing-key behaviour (no raw `t("nav.home")` leaks); article-content translation pipeline status |

Composite = mean of all 13. Report it; compare to prior run.

## 6. Done condition & loop budget

- **Done**: composite ≥4.0/5 **OR** the slice budget is spent (default **6 slices** for this final-polish push; raise only on explicit user "+budget").
- Walk the loop in §10. Stop on the hard-stop conditions there.

## 7. The gap ledger — P0 / P1 / P2 (verify each, then close)

Mark every item `WORKS` / `PARTIAL` / `BROKEN` / `MISSING` with `file:line` before acting. Items prefixed **F** are from `fixes.md` (recon 2026-05-30); **T** are carried trust-debt from the v1 ledger.

### P0 — user-visible breakage / trust-critical

| ID | Item | Recon state (2026-05-30) | Evidence / fix target |
|---|---|---|---|
| F1 | **Off-topic ingestion** (bus-accident class) | PARTIAL (2026-06-01) — ingest gate live + **existing off-topic now hidden from all listing surfaces** (`is_off_topic` mig 056/057 + ~40 query sites, `8394b56`) + curated `topic_feedback` backfill (~916). Per-article bus-class still shows — needs the LLM/source-aware relevance pass (keyword sweep mis-flags 65% of corpus; embeddings 0/666). | §3; `editorial_gate.classify_climate_relevance`; `api/topic_feedback_routes.py`; mig 056/057 |
| F12a | **Analytics view publicly reachable** | BROKEN — no auth/admin gate | `api/analytics_routes.py:92-178` (only `Depends(get_db)`); gate behind admin like `/api/admin/dashboard` (`api/main.py:158`) |
| F8a | **Research "audit trail" = raw JSON** | BROKEN | `src/frontend/src/components/RecentResearchAnalyses.tsx:141-147` links to raw `/api/methodology/audit-trail/...`; render a readable report (like article analysis) |
| F2 | **Chat "Claim:" contrast** (Bug1.png) | WORKS in code (2026-06-01) — static audit: deep-search + chat colours are `dark:`-paired / context-correct; only bare `text-white` is on teal buttons. No light-on-light in the pinned-light theme. Screenshots predate `ae920ea`. | `AgenticAssistant.tsx:632,637`; `app/deep-search/page.tsx` |
| F4 | **Article export failing** | WORKS in code (2026-06-01) — rewired to `POST`+JWT+blob (`lib/api.ts:480-496`); old `<a href>` GET "never worked" (live GET → 405, expected). Only a *logged-in* live test remains. | `ArticleExportButtons.tsx`, `lib/api.ts:480-496` |
| F6a | **Map layer visuals don't update** | `VERIFY-ON-LIVE` — code looks OK | `InteractiveClimateMap.tsx:435-439` (`geoJsonKey` includes `activeLayer`), `:320-361` (`styleFeature` deps include `activeLayer`). Reproduce live; if stale, inspect `mapData` fetch keying |

### P1 — depth / feature gaps (present-but-shallow or missing)

| ID | Item | Recon state | Evidence / fix target |
|---|---|---|---|
| F3 | **Theme switching removed** | MISSING (intentionally pinned) | `src/frontend/src/app/layout.tsx:44` (`className="light"`), `GlobalNav.tsx:74-83,153-154` (toggle deleted, `localStorage` cleared). **Decide**: implement a real dark theme (audit all `dark:` token pairs first) *or* remove the affordance cleanly. Don't ship half a theme |
| F5a | **Deep-search: no platform-only vs external toggle** | MISSING | service always runs both (`deep_search_service.py:42-72`); add `platform_only`/`include_external` param through `api/deep_search_routes.py:27-33` + `lib/api.ts:392-401` + UI |
| F5b | **Deep-search free cap** | PARTIAL — cap is **2**, user wants **3** | `api/quota_service.py:44-50` (`deep_research: 2`). Reconcile target (3) with the freemium-quota decision; also a legacy per-day limit at `deep_search_routes.py:157-165` |
| F5c | **Deep-search "weak evidence" default** | PARTIAL | low-evidence route when `internal+external < 3` (`deep_search_service.py:144-149`); LLM picks label (`:1507`, default `balanced :1554`). Tune threshold + surface why |
| F5d | **Deep-search excludes academic research** | MISSING | only `articles` + Perplexity web (`deep_search_service.py:684-834,900-946`); add the research/DOI corpus |
| F5e | **Region selector illogical labels** | BROKEN | `src/frontend/src/components/CountrySelector.tsx:62-145` ("EU countries" / "Other European countries" via `is_eu_member`). Re-group by continent/region, not EU-membership |
| F6b | **"Open country on map" deep-link** | PARTIAL — fails silently | `ArticleMapBridge.tsx:94-96` emits `?country=`; `map/page.tsx:105-109` reads it; `InteractiveClimateMap.tsx:162-190` `FlyToCountry` returns early if `geoData` null. Add ready-guard/retry |
| F6c | **Walkthroughs** | PARTIAL | `FirstTimerTour.tsx` (tested) + `map/MapWalkthrough.tsx` (no spotlight; `data-testid` selectors absent in `MapLayerControl.tsx`). Implement DOM-anchored highlight or simplify; audit both tours work |
| F7 | **KG as text rows + "cookies" entity + SDG copy** | PARTIAL (2026-06-01) — **relationships now render as a visual node-link SVG graph** (`KnowledgeGraphMini.tsx` `RelationshipGraph`, `b052293`, Playwright-verified) + cookies/boilerplate filter shipped earlier (`92d8242`). **Remaining:** related-coverage still rows; SDG chips copy minimal (`SDGChips.tsx:60-79`) → add real copy. | `KnowledgeGraphMini.tsx`; `SDGChips.tsx` |
| F8b | **Research scope not academic-only** | PARTIAL | `eu_feeds_registry.py` mixes "research" + industry (McKinsey/BNEF) with scientific journals; `research_report_service.py` detects Theseus but doesn't enforce academic-only. Scope research feed to theses (Theseus) + peer-reviewed + lit reviews |
| F8c | **Research metadata (theme/SDG tags)** | MISSING | `research/page.tsx:27-60` schema has `topics`/`climate_relevance` but no `sdgs`/`theme`; add tags + related SDGs per paper |
| F9a | **Verify-claim: no notification / weak trace** | PARTIAL | `companies/[ticker]/page.tsx:569-586` (form), `:651-698` (result), evidence_url `:686-690`. Add toast on result; surface verdict reasoning/provenance, not just `flag_reason` |
| F9b | **Compliance lenses not switchable** | PARTIAL | 5 frameworks mapped `standards.py:28-154`, shown all-at-once `companies/[ticker]/page.tsx:406-472`. Add a lens switcher (CSRD/SBTi/TCFD/IFRS-S2/GRI) |
| F9c | **PPP (Planet/People/Profit) lens** | MISSING | derive from disclosures; new view |
| F9d | **Auto drill-down questions** | MISSING | generate follow-ups per finding on company profile |
| F9e | **Compare two companies** | MISSING | company-vs-company view (topic & country compare exist as patterns: `CompareCharts.tsx`, map compare) |
| F10a | **Saves: social share** | MISSING | `SaveButton.tsx` / `saves/page.tsx` have no share; add share-to-social |
| F10b | **Saves: company-comparison asset type** | MISSING | 8 polymorphic types exist (`api/saved_items_routes.py:38-41`: article/analysis/claim/search/company/feed_setting/deep_search/country) — add `company_comparison`; persona-aware export formats |
| F11 | **Unrated sources** | PARTIAL | `source_profiles.py:303-366` sets `tier=NULL` when no `source_credibility_tiers` match → "Unrated" in `SourceProfileCard.tsx:77-80`. Backfill tiers/3-axis for all feeds in `rss_feed_registry`; expand best-in-class coverage per persona |
| F12b | **Eastern-EU geographic bias** | CONFIRMED | `celery_app.py:138-147` UN-193 default, `ingestion.py:305-307` flat 5/country, no rebalancing; skew comes from per-country feed density + Perplexity yield. Add per-country balancing/caps |
| F12c | **Verdict distribution ~99% Unverified** | CONFIRMED | default `verdict="unverified"` when evidence <0.50 (`services.py:765-772,841-844`); pipeline marks complete with all-unverified. Lift verification yield (claim extraction + evidence retrieval), not the default |
| F13 | **Localisation robustness** | PARTIAL | `lib/i18n.ts:11-29` 16 locales (backend 20, `translation_routes.py:23-44`); missing key → returns key text (`i18n.ts:86-94`) = leak risk; article-content translation pipeline unclear (`tasks/translation.py`). Audit all locales, add safe fallback, confirm `cn-translate` populates `article_translations` |

### P2 — carried trust-debt (v1 ledger — verify still open)

| ID | Item | Last state | Evidence |
|---|---|---|---|
| T1 | `executive_brief` low populate | PARTIAL (107 backfilled) | `article_enrichment_service.py`, `article_generator.py:220-268` |
| T2 | 5-yr temp trend hallucination | WORKS | `_fetch_5year_temperature_trend` |
| T4 | Research PDF upload "couldn't fetch" | PARTIAL | `research/page.tsx` ↔ `POST /api/research/upload` multipart |
| T7 | KG mig 013 not in canonical tree → `/kg` 500 | open | promote canonical mig 049 |
| T9 | Rate-limiter features unenforced | TRACKED in CI | `api/rate_limiter.py` |
| T11 | Calibration `n_labels=0` | open (reviewer pass) | not code |
| T12 | Off-topic in `climate_science` (916 rows) | PARTIAL | mig 053 stops future ingest; existing rows need relevance backfill (ties to F1) |

If an item is already closed, mark `WORKS` with `file:line` proof and move on.

## 8. Cloud/Local (GX10) optimization mandate (cluster 14)

**Confirmed wiring (2026-05-30):** provider pin in `src/backend/app/domains/content/article_enrichment_service.py:968-994` — `CLILENS_ENRICHMENT_PROVIDER=local-gx10` → order `[local-gx10, deepseek, openai, anthropic]`; env `CLILENS_LOCAL_GX10_BASE_URL`, `_API_KEY`, `_MODEL` (default `Qwen/Qwen2.5-14B-Instruct`), `_TIMEOUT=240`.

**Mandate:** push enrich / data-validation / inference onto the GX10 **autonomously, without touching any client-facing cloud feature**, and chart a path to fine-tuned/quantized house models. For every LLM call site (the 32 in `GX10-Workload-Audit-2026-05-25.md`) assign `MOVE-TO-GX10` / `HYBRID-WITH-FALLBACK` / `KEEP-CLOUD` via the 3-lane model:

- **Lane A — overnight batch** (RSS enrichment, **the new relevance gate (§3)**, KG canonicalisation, entity extraction, distillation, full-corpus backfills, eval harness): GX10 always. Default `MOVE-TO-GX10`.
- **Lane B — background-recent, seconds–minutes** (URL analysis post-trigger, hallucination check, verdict adjudication): GX10 primary, cloud fallback. Default `HYBRID-WITH-FALLBACK`.
- **Lane C — user-facing sub-5s streaming** (article chat, deep-search synthesis, comparison): cloud primary; GX10 specialist only after streaming p95 is met.

Always `KEEP-CLOUD`: Perplexity Sonar (web search, not inference); frontier deep-search synthesis (per-sentence citation grounding); primary+secondary of the multi-LLM verifier (diversity signal).

Per promotion, output 4 lines: workload key, env var to flip, acceptance criteria (JSON-valid ≥99% on a 200-sample backfill OR ≤1pp regression on `eval_prompts.py`), and `$/mo` delta. When the captured SFT dataset (`CLILENS_TRAINING_DATASET_PATH`, ≥20k pairs) justifies it, recommend the LoRA adapter, base model, and where it lives (GX10 batch / cloud serve). **House-model path:** specify the first workload to quantize+fine-tune (likely enrichment or the relevance gate) and the eval gate before it can serve.

## 9. Production-readiness streamlining (cluster 15)

Produce `docs/improvementplans/Prod-Readiness-Inventory-<YYYY-MM-DD>.md` covering:

- **Root clutter to remove/relocate** (confirmed 2026-05-30): `ERROR` (empty stray), `.coverage*`/`htmlcov/`/`coverage.json` (gitignore or build dir), `POLISH-AUDIT-PROGRESS.md` and any working `*.md`/`*.txt` notes in root → `docs/` or delete. The `.claude/*_extract.txt` scratch files too.
- **Duplicate/legacy routes**: `src/frontend/src/app/dashboard/saved` vs `/saves` (resolve to one); confirm no other dead routes. `archive/` legacy frontend — confirm excluded from build.
- **Agentic-skills inventory**: reconcile `skills.py` count (~14) with the stale "9" comment and `test_agentic_skill_pin.py`; ensure registry ↔ prompt template ↔ `chatActionDispatcher.ts` ↔ frontend FALLBACK are single-sourced.
- **Docs sprawl**: `docs/improvementplans/` has 20+ dated benchmarks — keep latest + index, archive the rest under `docs/improvementplans/archive/`.
- **DevOps tracing/debugging**: confirm structured logging + request-context propagation (`src/backend/app/shared/`), Cloud Run revision-verify gate, and the `MIGRATIONS_TOLERATE_ERRORS` landmine are all sound for prod debugging.

## 10. Fix-batch cadence (the loop)

One pass:

1. Run §4–§5 measurements against live API + DB. Persist to memory `reasoningbank://climatenews/end2end/<YYYY-MM-DD>/scores`.
2. Diff §7 against recon; mark each item `WORKS/PARTIAL/BROKEN/MISSING` with `file:line`.
3. Run §8 for any workload changed since the last GX10-Workload-Audit.
4. Pick **≤ the slice budget (§6)**. Each slice: ≤2 days effort, closes ≥1 ledger row, no cross-slice dependency. **Order P0 before P1 before P2**, then by `(quality_lift × user_visibility) ÷ effort`.
5. Per slice: `hooks pre-task` + checkpoint → one batched message (TodoWrite + all reads + all edits + tests) → `cd src/frontend && npm run lint && npm run typecheck && npm test` (if FE) + `pytest tests/ -q` (if BE) → `hooks post-edit`/`notify`/`post-task` → conventional commit citing the ledger ID.
6. After all slices: regenerate §7 artifacts, push, open one PR per slice (or one PR if slices share scope).

**Hard stops** (do NOT continue): a test suite regresses and the cause isn't obvious in 15 min → revert checkpoint, open issue, move on; composite would drop on any axis → revert, don't commit; a migration without the proper guard in `scripts/run_migrations.py` → block the slice.

## 11. Required artifacts per run (in `docs/improvementplans/`)

- `End2End-Audit-Benchmark-<YYYY-MM-DD>.md` — same shape as `2026-05-27d.md`: TL;DR, 13-axis grades, ledger delta, sprint plan, **"what we did NOT do (transparency)"**.
- `Golden-Artifact-Examples-<YYYY-MM-DD>.md` — one **live** ID per artifact type (article, deep-search, research, company); the article must be climate-relevant (verify) with ≥3 claims; list which target fields populate/miss.
- `Prod-Readiness-Inventory-<YYYY-MM-DD>.md` (§9) — once per polish push.

Persist: `reasoningbank://climatenews/end2end/<date>/scores` (13-axis JSON), `.../slices` (manifest + shas); `npx claude-flow@alpha metrics log --feature "end2end-audit" --status used --notes "<composite>"`.

## 12. Verification ritual (before any PR) — run all, in order, one batched message

1. `cd src/frontend && npm run lint && npm run typecheck && npm test`
2. `pytest tests/ -q --cov=src/backend`
3. Live API smoke for any touched surface (deep-search scope param, analytics admin-gate 401 for anon, export endpoints, `/api/articles/{id}/kg` 200, research report render).
4. `gh pr create` only after 1–3 are green.

If any of 1–3 fails: do not open the PR. Revert to the last checkpoint, log the failure to memory, move to the next slice.

---

**Done condition (repeat)**: composite ≥4.0/5 OR slice budget spent. Then stop and post the §11 artifacts as the summary.
