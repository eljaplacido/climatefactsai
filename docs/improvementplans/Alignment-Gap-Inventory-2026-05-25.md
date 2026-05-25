# Alignment Gap Inventory — 2026-05-25

Read-only audit of the 22-commit Honest-Gap-Audit-v2 backlog (commits `36af118…522fccf`). Walks the shipped backend endpoints, frontend surfaces, data layer, tests, docs, and agentic skills to catalogue what's wired vs. what's still drifting.

## TL;DR

- **44 distinct alignment gaps catalogued** (16 UIX coverage, 9 generated-content/data surface, 6 semantic-layer, 7 test, 4 doc, 2 agentic-skill).
- **Biggest 3 missing UI surfaces:** (1) corporate-report PDF/URL upload form on `/companies/[ticker]` (endpoint shipped, no button), (2) research-feed page rendering `/api/research/feed` + subscribe UI for `/api/research/subscriptions` (endpoint shipped, page has no feed at all), (3) PDF/Word upload on `/research` (endpoint shipped, page still only does url/doi/text).
- **Biggest doc-sync issue:** `Resume-Here-2026-05-25.md`, `Honest-Gap-Audit-v2-2026-05-25.md`, `Phase-10-Session-Summary-2026-05-25.md`, and `Production-Review-Response-2026-05-25.md` all still mark items 11/12/13/14 as MISSING/Deferred when commits `e44a1a3`, `12d9e9e`, `6c33165`, `3a9171d` shipped them. The 20-item production-review tally in Phase-10-Session-Summary still says "7 of 20 fixed" when reality is 17 of 20.
- **Top 1 to ship next session:** Add an upload card to `/research` page that POSTs to `/api/research/upload`, plus a "Subscribe to this topic" button + a `/research/feed` panel rendering `/api/research/feed`. Three endpoints, one page, ~4 hr — turns three invisible backends into a complete research-workflow surface.
- **Recommended ship order:** Research page upgrade (4 hr) → Corporate report upload button on /companies (2 hr) → Scenario explorer card on country page (3 hr) → Source 3-axis chip on SourceProfileCard (3 hr) → Source link-rot pill on article header (2 hr) → Doc resync sweep (1 hr).

---

## 1. UIX coverage gaps

For every backend endpoint shipped between commits `36af118` and `522fccf`, does a frontend surface exist that uses it? Frontend caller paths are `src/frontend/src/...`.

| Endpoint | Frontend caller | What it would take to wire |
|---|---|---|
| `POST /api/research/upload` (e44a1a3, `api/research_routes.py:83`) | **MISSING** — `src/frontend/src/app/research/page.tsx:109-127` only offers `url`/`doi`/`text` tabs, never the new multipart upload. | Add an `Upload PDF` tab to the existing 3-tab switcher; `<input type="file" accept=".pdf,.docx,.txt,.md,.html">`; POST via FormData to `/api/research/upload`; surface the new `text_length`/`filename`/`source: 'upload'` response fields. ~3 hr. |
| `POST /api/companies/{ticker}/analyze-report` (12d9e9e, `api/company_routes.py:186`) | **MISSING for direct UI** — only `src/frontend/src/lib/chatActionDispatcher.ts:423-475` (chat skill) calls it. `src/frontend/src/app/companies/[ticker]/page.tsx:117-146` only POSTs the single-claim `/analyze`. | Add a "Analyse full sustainability report" card on `/companies/[ticker]` with a URL input + paste-text fallback (mirrors the request body shape). Render `verdict_summary` aggregate after submit + scroll to claim ledger with `methodology_version === 'corporate_report_v1.0'` tag. ~2 hr. |
| `POST /api/research/subscriptions` (6c33165, `api/research_feed_routes.py:116`) | **MISSING for direct UI** — only `src/frontend/src/lib/chatActionDispatcher.ts:381-419` (chat skill) calls it. `src/frontend/src/app/research/page.tsx` has no subscribe UI at all. | Add a "Subscribe to topic" inline form on `/research` with text input + active subscription chips (uses `GET /subscriptions`). ~1 hr. |
| `GET /api/research/subscriptions` (6c33165, `api/research_feed_routes.py:179`) | **MISSING** — no FE consumer. | Active-chips component on the research page (delete via `DELETE /subscriptions/{id}`). ~30 min. |
| `DELETE /api/research/subscriptions/{id}` (6c33165, `api/research_feed_routes.py:193`) | **MISSING** — no FE consumer. | Wire to the chip delete handler. ~10 min. |
| `GET /api/research/feed` (6c33165, `api/research_feed_routes.py:214`) | **MISSING** — no FE consumer. | New `<ResearchFeedPanel />` below the analyze form on `/research`. Renders CrossRef items with DOI + journal chips + "Save to my saves" button. ~2 hr. |
| `GET /api/scenario/country/{cc}?target_warming_c=&horizon_year=` (3a9171d, `api/scenario_routes.py:119`) | **MISSING for direct UI** — only `src/frontend/src/lib/chatActionDispatcher.ts:226-235` (chat skill) navigates to `/country/{cc}#projections`, never calls the new interpolation endpoint. `src/frontend/src/components/ProjectionsPanel.tsx` only reads the raw scenario table. | Add an interactive `<ScenarioExplorer />` sub-card to the Projections tab of `/country/[code]`: warming-slider (0-4°C) + horizon picker (2030/2050/2100) → calls endpoint → renders interpolated anomaly + bracketing scenarios + disclaimer. ~3 hr. |
| `POST /api/admin/link-check` (adbb5c3, `api/admin_link_check_routes.py:87`) | **MISSING** — no FE consumer; pure ops endpoint. | Add a "Trigger link check" button to `src/frontend/src/app/admin/page.tsx` (already has discovery + verify panels). ~30 min. (Low priority — Cloud Scheduler handles this.) |
| `GET /api/admin/link-check/summary` (adbb5c3, `api/admin_link_check_routes.py:155`) | **MISSING** — no FE consumer. | Show count badge in admin dashboard. Could also surface a "links dead" pill on article header. ~1 hr. |
| `POST /api/admin/research-poll` (6c33165, `api/research_feed_routes.py:334`) | **MISSING** — no FE consumer; expected (Cloud Scheduler endpoint). | None required. |
| `POST /api/user/saved` (789dda1+10b696f, `api/saved_items_routes.py:119`) | **WIRED for 4 of 8 item types.** `BookmarkButton.tsx` (article), `SaveButton.tsx` on `/companies/[ticker]/page.tsx:200-205` (company), `/country/[code]/page.tsx:288-295` (country), `chatActionDispatcher.ts` save_item skill (all types). | **PARTIAL** — Missing direct UI Save buttons for: `analysis` (analyze page), `claim` (claim card), `search` (search results header), `deep_search` (deep-search result header), `feed_setting` (feed page). 5 small buttons, ~1 hr each. |
| `GET /api/user/saved` (10b696f) | `api.ts:listSavedItems` → `/saves/page.tsx` ✓ | OK |
| `GET /api/user/saved/check` (10b696f) | `api.ts:checkSavedItem` → `useSave.ts` ✓ | OK |
| `DELETE /api/user/saved/{id}` (10b696f) | `api.ts:deleteSavedItem` → `/saves/page.tsx:130` + `useSave.ts` ✓ | OK |

**Navigation discoverability gaps**

| Surface | Issue | Fix |
|---|---|---|
| `src/frontend/src/components/GlobalNav.tsx:20-29` | NAV_ITEMS does NOT include `/companies` or `/saves`. Both pages exist (`src/frontend/src/app/companies/page.tsx`, `src/frontend/src/app/saves/page.tsx`) but the only way to reach them is via direct URL or chat skills. | Add `{ href: "/companies", ... }` and `{ href: "/saves", ... }` to NAV_ITEMS. 5 min. |

---

## 2. Generated-content surface gaps

Do article/deep-search/company surfaces use the new features?

| Surface | What's wired | What's missing |
|---|---|---|
| Article page (`src/frontend/src/app/articles/[id]/page.tsx`) | claim_density / Limited Evidence badge ✓ (`:235-244`), Full Article panel ✓ (`:472-477`), reliability_breakdown ✓ (`:480-527`), executive_brief + enriched_excerpt ✓, infographic gallery ✓ (`:537-558`), ArgumentationGraph ✓ (`:576`), WeatherContext ✓ (`:573`), OG metadata ✓ (`:94-133`), export buttons ✓ (`:276`), bookmark + share ✓. | **Source 3-axis scoring NOT surfaced** — `source_credibility_tiers.editorial_score/factcheck_score/transparency_score` (mig 041) are in DB but article page only shows `source_name` and `source_credibility_score`. No surface on this page references the new 3-axis numbers. **`source_url_status` (mig 046) NOT surfaced** — no link-rot pill on the header / "view original article" link. |
| Article page (KG / Weather panels) | After 3e01649, both components render proper state messages (loading / forbidden / unavailable) — no longer silently hide. ✓ | KG endpoint backend itself still 500s per deferred #21b (Honest-Gap-Audit-v2 §21 / `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md:250`). Out of scope this session. |
| Article enrichment prompt (`src/backend/app/domains/content/article_enrichment_service.py`) | local-gx10 provider wired via 60253df. ✓ | Prompt template content unchanged — no awareness of Limited Evidence framing, no new 3-axis source signals injected into the enrichment context window. |
| Deep-search page (`src/frontend/src/app/deep-search/page.tsx`) | Sentence-grounded answer + hallucination_check chips ✓ (`:458-467`, `:553-571`), credibility spread bar ✓ (`:546-551`, `:572-578`), avg reliability ✓ (`:559-571`), follow-up chat ✓ (`:473-477`). | **No 3-axis source chips per citation** — citations only show `credibility: HIGH/MED/LOW`. **No "Save this deep search" button** — even though `save_item` with `item_type=deep_search` is registered. **External Perplexity citations show no credibility chip at all** — internal articles have `c.credibility`, but external web sources return null/none and no chip renders (confirmed by reading `:482-498` — `credCounts` falls through to LOW for any null). |
| Deep-search result citations (`src/frontend/src/app/deep-search/page.tsx`) | reliability_score and credibility text rendered. | No factuality/methodology/independence chips. No source link-rot indicator. |
| Research page (`src/frontend/src/app/research/page.tsx`) | URL / DOI / paste-text analyse via `POST /api/research/analyze` ✓. | **NO file upload UI** (endpoint shipped). **NO subscribe UI** (endpoint shipped). **NO research-feed panel** (endpoint shipped). Three new endpoints, zero consumers. |
| My Saves page (`src/frontend/src/app/saves/page.tsx`) | Lists all 8 item types ✓; filter chips ✓; remove button ✓. | OK. |
| Company detail page (`src/frontend/src/app/companies/[ticker]/page.tsx`) | Per-claim verify form ✓, business view + ECGT framework chips ✓, save company chip ✓ (`:200-205`). | **NO analyze-report form** (endpoint shipped). Verdicts created by per-claim vs report-driven flows are NOT visually distinguished — `methodology_version === 'corporate_report_v1.0'` is persisted by backend but ignored by FE rendering (`page.tsx:425-461`). |
| Scenario explorer | Country Passport has Projections tab ✓ (`/country/[code]/page.tsx:504-511`) which renders ProjectionsPanel with raw scenarios. | **NO interactive interpolation card** — `/api/scenario/country/{cc}` endpoint shipped but only chat skill consumes. No slider, no horizon picker, no disclaimer surface. |
| Sources page (`src/frontend/src/app/sources/page.tsx`) | Tier badges ✓ (`SourceProfileCard.tsx:70-84`), single credibility_score ✓, editorial_standards/fact_check_record/transparency_level **strings** ✓. | **3-axis numeric scores NOT shown** — `editorial_score`, `factcheck_score`, `transparency_score` from mig 041 not selected by `src/backend/app/domains/content/source_profiles.py:86-93`, so even if FE wanted to render them they don't reach the type. The page methodology copy (`page.tsx:171-194`) still talks about the 4 string-tier factors, not the new 3-axis numerics. |
| Insights generator (`src/backend/app/domains/intelligence/services.py` / similar) | Reliability + claims processing. | Insight prompt does NOT reference Limited Evidence framing or any 3-axis numbers; the headline credibility number stays the only signal. |

---

## 3. Data/semantic-layer coherence

| Layer | Status |
|---|---|
| `saved_items` (mig 042) | Backend route ✓ (`api/saved_items_routes.py`), TS type ✓ (`types/index.ts:789-819`), api.ts ✓ (`:336-365`), useSave hook ✓ (`lib/useSave.ts`), Saves page ✓. **WIRED end-to-end for 3 of 8 types** (article + company + country with explicit Save buttons in the UI). Other 5 types reachable only via chat skill. |
| `research_subscriptions` / `research_feed_items` (mig 047) | Backend route ✓ (`api/research_feed_routes.py`), tests ✓ (`tests/backend/test_research_feed.py`). **NO frontend types, NO api.ts wrapper, NO UI consumer.** Pure backend layer. |
| `articles.source_url_status` (mig 046) | Backend job ✓ (`api/admin_link_check_routes.py`), populated by link-check. **NO frontend exposure** — column is selected nowhere in the article detail route to FE; no chip/pill UI. |
| `source_credibility_tiers.editorial_score / factcheck_score / transparency_score` (mig 041, mig 045 fence) | Schema ✓, populated ✓ (Tier defaults + curated overrides for Reuters/AP/Carbon Brief/IPCC/Inside Climate News/Google News). **NOT selected by `source_profiles.py:_profile_select_clause` (`:86-93`)** — so the numeric scores never reach FE. SourceProfileCard renders the legacy string fields only. |
| `country_projections` (mig 035) | Backend ✓, ProjectionsPanel renders raw scenarios ✓. NEW: `/api/scenario/country/{cc}` interpolation endpoint reads same table but is consumed only by chat skill. |
| `companies` / `company_claims_by_report` (12d9e9e) | Backend persists `methodology_version='corporate_report_v1.0'` to distinguish per-claim vs report-driven verdicts (`api/company_routes.py:186-440` analyze-report path). Companies page FE does NOT filter or visually distinguish; `Claim` type in `app/companies/[ticker]/page.tsx:65-73` lacks `methodology_version` field. |
| `companies` dedup (mig 043+044, commits 900af29+85b770d+9260f2c) | Hard-asserted unique on `(LOWER(TRIM(name)), country_code)`. Verified live via Resume-Here check-3. ✓ |
| Skills registry (Phase 4C / Polish wave 1) | Backend single source ✓ (`src/backend/app/domains/intelligence/skills.py:74-308` — 15 skills). Prompt template lists 15 ✓ (`prompts.py:425-441`). chatActionDispatcher.ts ChatActionType union has 15 ✓ (`chatActionDispatcher.ts:24-42`). **DRIFT in `useSkills.ts:61-71`** — FALLBACK_SKILL_MODES is the OLD 9-skill set; missing `open_company`, `verify_corporate_claim`, `save_item`, `subscribe_research_topic`, `explore_scenario`, `analyze_corporate_report`. Backend `/api/skills` is fine; the fallback used when API is unreachable is stale. |

---

## 4. Test coverage gaps

### Backend endpoints without a pytest pin test

| Route file | Endpoint | Test file present? |
|---|---|---|
| `api/saved_items_routes.py` | `GET /api/user/saved`, `POST /api/user/saved`, `GET /api/user/saved/check`, `DELETE /api/user/saved/{id}` (all 4 endpoints — entire route file from 789dda1) | **NO pytest** — `tests/api/`, `tests/backend/`, `tests/unit/` have ZERO test file matching `saved_items*`. The only pin is FE `useSave.test.tsx` (7 cases on request shape). |
| `api/research_feed_routes.py:334` | `POST /api/admin/research-poll` admin endpoint | Test exists (`tests/backend/test_research_feed.py`) but only for CrossRef mapping + the 3 token-gate cases, not the asyncio.Semaphore politeness window. |
| `api/admin_link_check_routes.py:155` | `GET /api/admin/link-check/summary` | Test exists for `POST /api/admin/link-check` (`tests/backend/test_link_check.py`) — summary endpoint coverage status not visible by grep. Worth a confirmation read. |
| `api/company_routes.py:186` | `POST /api/companies/{ticker}/analyze-report` (12d9e9e) | **OK** — `tests/backend/test_analyze_report.py` (5 cases). |
| `api/scenario_routes.py:119` | `GET /api/scenario/country/{cc}` (3a9171d) | **OK** — `tests/backend/test_scenario_explorer.py` (10 cases). |
| `api/research_routes.py:83` | `POST /api/research/upload` (e44a1a3) | **OK** — `tests/backend/test_research_upload.py` (6 cases). |
| `src/backend/app/domains/content/article_enrichment_service.py` local-gx10 | `_call_llm` pin set + provider routing (60253df) | **OK** — `tests/backend/test_enrichment_gx10_provider.py` (4 cases). |
| `src/backend/shared/reliability_scorer.py` density factor (1cda89a) | Claim-density + Limited Evidence | **OK** — `tests/backend/test_reliability_scorer_density.py` (19 cases). |
| `src/backend/shared/full_text_fetch.py` (b3caa18) | RSS-excerpt pre-pass | **OK** — `tests/backend/test_full_text_fetch.py` (14 cases). |

### Frontend components shipped this session without tests

| Component | Origin | Status |
|---|---|---|
| `src/frontend/src/components/FullArticlePanel.tsx` (f2a18a4) | Polish wave 1, audit item 2 | **NO test** — `src/frontend/src/__tests__/components/FullArticlePanel.test.tsx` absent. Logic is light (preview vs expanded), but no pin for the 200-char minimum guard or word-count math. |
| `src/frontend/src/components/SaveButton.tsx` (10b696f) | Slice 3, polymorphic save | **NO test** — `src/frontend/src/__tests__/components/SaveButton.test.tsx` absent. BookmarkButton.test.tsx was updated; SaveButton is the new generic primitive. |
| `src/frontend/src/components/CountryBiomeSummary.tsx` (6798122 — pre-session) | Phase 9 country biome narrative | NO test — older but discovered during walk. |
| `src/frontend/src/components/FactCheckDetail.tsx` | Pre-session | NO test. |
| `src/frontend/src/components/EvidenceChain.tsx` | Pre-session | NO test. |
| `src/frontend/src/components/EvidenceTimeline.tsx` | Pre-session | NO test. |
| `src/frontend/src/components/ClaimCard.tsx` | Pre-session | NO test. |
| `src/frontend/src/components/Markdown.tsx` (20a2441 dark-mode fix) | Pre-session | NO test. |

Aggregate: **23 of 60 components tested (38%)**, **5 of 35 pages tested (14%)**.

### Frontend pages shipped this session without page-level tests

| Page | Status |
|---|---|
| `src/frontend/src/app/saves/page.tsx` (10b696f) | **NO page test** — list + filter + delete flow unverified. |
| `src/frontend/src/app/research/page.tsx` | NO page test. (Pre-session existence.) |
| `src/frontend/src/app/companies/page.tsx` + `[ticker]/page.tsx` | Only the business-view sub-flow is tested (`__tests__/pages/company-detail-business-view.test.tsx`). Per-claim verify form is not pinned. |

---

## 5. Docs sync gaps

| Doc | Issue | Severity |
|---|---|---|
| `docs/improvementplans/Resume-Here-2026-05-25.md:42-63` | Calls last commit `6798122`; reality is `522fccf` with 22 commits in between. The "F1 quick win" was already shipped in `e1c14b1`. The Remaining table lists C1 (doc upload), C2 (research feed), C3 (scenario sim), B1 (share/export) as open — all 4 shipped (e44a1a3, 6c33165, 3a9171d, 36af118). | **HIGH** — this is the file the next operator opens first. |
| `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md:18-20` | TL;DR still says "MISSING: 4 (11, 12, 13, 14)". All four shipped (e44a1a3, 12d9e9e, 6c33165, 3a9171d). Slice progress table at `:266-280` does not include the deferred-items rows. | HIGH |
| `docs/improvementplans/Phase-10-Session-Summary-2026-05-25.md:80-130` | "Still deferred" matrix lists A1/A2/A3/B1/C1/C2/C3/C4/D1 as open. B1 (Slice 1, 36af118), C1 (e44a1a3), C2 (6c33165), C3 (3a9171d), C4 (10b696f) shipped. The honest-verdict scoreboard at `:155-181` says "7 of 20 fixed end-to-end" but real number is 17 of 20 after this session's wave. | HIGH |
| `docs/improvementplans/Production-Review-Response-2026-05-25.md:50-85` | Same staleness — C1/C2/C3/C4/B1 still labelled "NOT done in this session" though all shipped. | HIGH |
| `docs/reports/Climatefacts-Architecture-Report-2026-05-24.docx` | Already flagged in `Honest-Gap-Audit-v2:282-296` — overclaims "7 personas served." Reality is Public/Business toggle only. Doc not yet regenerated. | MEDIUM (acknowledged) |
| `README.md` | Last "Updated: 2026-04-30" stamp (line 9). Never mentions: `/saves`, `/companies`, `/api/research/upload`, `/api/research/subscriptions`, `/api/companies/{ticker}/analyze-report`, `/api/scenario/country/{cc}`, polymorphic saves, 3-axis source scoring, GX10 routing, link-check job. Greps for all these terms return zero hits. | HIGH — README is the only "official" doc visible from GitHub. |
| `CLAUDE.md` | Project-level instructions doc. Same gap — no mention of the new endpoint families. Not strictly stale (no contradictions), but it's the file Claude sessions read first and it's missing the entire Phase 10 shape. | MEDIUM |
| `src/frontend/src/lib/useSkills.ts:61-71` (treated as a doc since it's a fallback constant) | FALLBACK_SKILL_MODES has 9 entries; backend has 15. When `/api/skills` is unreachable, the dispatcher loses 6 confirm/auto classifications. The dev-console warning at `:135-139` will fire but isn't an end-user-visible signal. | LOW (real registry is correct; just the offline fallback drifted). |

---

## 6. Agentic skill coverage gaps

15 skills registered. For each: dispatcher implementation present? Prompt template lists it? UI affordance somewhere?

| Skill | Mode | Dispatcher | In prompt template (`prompts.py:413-428`) | UI affordance the LLM could surface from |
|---|---|---|---|---|
| `navigate` | auto | ✓ (NAV_DISPATCHERS:158-162) | ✓ | Always-available |
| `analyze_url` | confirm | ✓ (NAV_DISPATCHERS:163-167) | ✓ | `/analyze` page |
| `apply_search_filters` | auto | ✓ (:168-176) | ✓ | `/search` page |
| `apply_map_filters` | auto | ✓ (:177-182) | ✓ | `/map` page |
| `open_methodology_section` | auto | ✓ (:183-186) | ✓ | `/methodology` page |
| `open_country` | auto | ✓ (:187-191) | ✓ | `/map`, `/country/[code]` |
| `start_deep_search` | auto | ✓ (:192-198) | ✓ | `/deep-search` page |
| `bookmark_article` | confirm | ✓ (ASYNC_DISPATCHERS:246-288 — uses polymorphic `/api/user/saved` now) | ✓ | Article header BookmarkButton |
| `start_calibration_label` | confirm | ✓ (NAV_DISPATCHERS:203-209) | ✓ | `/analyze` page |
| `open_company` | auto | ✓ (NAV_DISPATCHERS:210-216) | ✓ | `/companies` list (but NOT in global nav — only direct URL/chat) |
| `verify_corporate_claim` | confirm | ✓ (ASYNC_DISPATCHERS:293-328) | ✓ | `/companies/[ticker]` claim verify form |
| `save_item` | confirm | ✓ (ASYNC_DISPATCHERS:331-378) | ✓ | **PARTIAL** — only 3 of 8 item types have a UI Save button (article via BookmarkButton, company on company page, country on country page). The skill claims 8 types but a chat-suggested "save this search" or "save this deep_search" has no corresponding UI button the user could otherwise click. |
| `subscribe_research_topic` | confirm | ✓ (ASYNC_DISPATCHERS:381-419) | ✓ | **NONE** — no subscribe UI exists. Chat is the only entry point. |
| `explore_scenario` | auto | ✓ (NAV_DISPATCHERS:226-235) — navigates to existing projections panel, does NOT call the new interpolation endpoint | ✓ | **PARTIAL** — Projections tab on country page exists but only shows pre-baked scenarios, not the interactive interpolator. |
| `analyze_corporate_report` | confirm | ✓ (ASYNC_DISPATCHERS:423-475) | ✓ | **NONE** — no UI form exists on company page. Chat is the only entry point. |

**Skills with zero direct UI affordance (chat-only):** 3 of 15 (`subscribe_research_topic`, `analyze_corporate_report`, and partially `explore_scenario` + `save_item`). The skill protocol is the ONLY way to invoke them today — fine for power users, anti-pattern for the "all features discoverable" mandate.

---

## 7. Priority recommendation

### Ship NOW (sub-day, high impact)

1. **Add `/companies` and `/saves` to GlobalNav.tsx NAV_ITEMS** — 5 min. Closes discoverability gap for 2 entire pages.
2. **Wire upload tab + subscribe form on `/research`** — ~4 hr. Three shipped endpoints become user-reachable (`/upload`, `/subscriptions`, `/feed`).
3. **Add `analyze-report` form card to `/companies/[ticker]`** — ~2 hr. Single most-asked-for ESG feature from the audit gets a UI.
4. **Doc resync sweep** — ~1 hr. Update Resume-Here, Honest-Gap-Audit-v2 TL;DR, Phase-10-Session-Summary deferred matrix, Production-Review-Response status table. Bump README version + add new endpoints to the feature list. The 17-of-20 reality should be the public face.
5. **Refresh `useSkills.ts` FALLBACK_SKILL_MODES** to all 15 skills — 5 min. Removes the only known FE/BE drift point in the agentic protocol.

### Ship SOON (1-2 days, real value)

6. **Interactive `<ScenarioExplorer />` on `/country/[code]`** — slider + horizon picker → calls `/api/scenario/country/{cc}`. ~3 hr.
7. **Expose 3-axis source scores end-to-end** — extend `source_profiles.py:_profile_select_clause` to pull `editorial_score`/`factcheck_score`/`transparency_score`, add `factuality`/`methodology`/`independence` numeric fields to `SourceProfile` type, render as a 3-pill row on `SourceProfileCard`. Touch both Sources page and the new chips on article header. ~4 hr.
8. **Surface `source_url_status` on article header** — small "Link verified Xd ago / Link 404 / Link redirect" pill next to "View Original Article". ~2 hr.
9. **Distinguish report-driven vs per-claim verdicts on `/companies/[ticker]`** — read `methodology_version`, render a small "Source: corporate report" chip on the claim card. ~30 min once `methodology_version` is added to the FE Claim type.
10. **Save buttons for the 5 remaining item types** — `analysis`, `claim`, `search`, `deep_search`, `feed_setting`. Each adds the existing `<SaveButton type=... />` primitive in the appropriate page header. ~1 hr each, batchable.
11. **pytest for `api/saved_items_routes.py`** — 7 cases mirroring FE useSave.test.tsx. ~2 hr.
12. **Vitest for `FullArticlePanel.tsx` and `SaveButton.tsx`** — 5 cases each. ~1 hr.

### Defer (sprint-scale)

13. **KG endpoint 500 fix** (deferred audit item #21b) — separate weeks-of-work.
14. **Regenerate architecture report `.docx`** with honest persona/3-axis/Limited-Evidence/scenario-explorer/research-feed/polymorphic-saves coverage — needs source materials review beyond this audit's scope.
15. **Insight prompt enrichment** — make insight_summary generator aware of new agentic skills + Limited Evidence framing + 3-axis source signals so generated content references them naturally. Coupled with GX10 prompt iteration loop.
16. **Persona routing engine** (item 16 from Honest-Gap-Audit-v2) — still acknowledged as multi-week.
