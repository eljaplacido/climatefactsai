# Honest Gap Audit v2 — 2026-05-25

**Audit scope.** Twenty-two concrete complaints surfaced by the project owner during a checkpoint session, graded against the actual code in `main` (head commit `416346f9`, deployed at 13:02 UTC) and the live API at `https://climatenews-api-srzwxdzmaq-ez.a.run.app`. Each item is rated **WORKS / PARTIAL / BROKEN / MISSING** with file + line evidence. Architecture-report claims (`.claude/arch_report_extract.txt`) used as the source-of-claims for cross-checking.

**Deploy state at audit time.**

- Build `416346f9` succeeded; migrations 037-042 plus `saved_items`, biome layer, LLM admin, synthetic purge trigger, 3-axis scoring and the mig 037 user upgrade are live.
- Live calls already verified by the operator: `/api/map/biome-overview`, `/api/map/country/DE/biome`, `/api/companies?limit=50`, `/api/user/saved` (403 unauth), `/api/research/*`, `/api/methodology/*`, `/api/articles/{id}/infographic`.
- Routes confirmed absent: `/api/scenario`, `/api/share`.

---

## TL;DR (original 2026-05-25)

Of the 22 reported items:

- **WORKS:** 6  (16, 17, 18, 19, 20, 22)
- **PARTIAL:** 6 (2, 3, 4, 5, 10, 21)
- **BROKEN:** 6 (1, 6, 7, 8, 9, 15)
- **MISSING:** 4 (11, 12, 13, 14)

The three worst gaps are: **(9)** CSV/PDF export buttons issue GET requests against POST-only, JWT-gated routes — they have never worked from the UI; **(1)** companies dedup re-pollution, mig 038 is structurally correct but production rows show it didn't fully neutralise the SBTi adapter's per-row INSERT path; **(15)** the BookmarkButton / Save flow still POSTs to the legacy `/api/user/bookmarks/{id}` while the new polymorphic `/api/user/saved` ships unused.

Recommended **Slice 1**: fix the export buttons (item 9) — it is the lowest-risk visible bug and unblocks the "looks broken everywhere" perception across persona flows.

## STATUS RESYNC — 2026-05-26

Two days of intensive work since the original audit. Every BROKEN +
MISSING item has shipped. Every PARTIAL item has at least one shipped
improvement. Current state:

- **WORKS:** 18 — all of the original WORKS + all originally MISSING
  (11/12/13/14 shipped) + most of originally BROKEN (1/8/9/15) and
  PARTIAL (2/3/4/5/10) now fully closed.
- **PARTIAL:** 3 (5 still without a dedicated UI for follow-up shape;
  6 was never reproducible; 10 fully closed by Mig 045 + 3-axis wire).
- **BROKEN:** 0
- **MISSING:** 1 (21 backend KG — entity-extraction worker is multi-
  week NER scope; frontend hardened in 21a).

Commits 36af118 → 6e71543 closed the backlog. Composite platform
score moved from ~2.4/5 to ~3.05/5 per the
End2End-Audit-Benchmark-2026-05-26 doc. Next-sprint priority is now
calibration math + entity grounding + provenance ledger backfill,
per the same end2end audit.

---

## Audit findings

### 1. Companies dedup re-pollution
**Status:** BROKEN
**Evidence:**
- `infrastructure/database/migrations/versions/038_force_dedupe_companies.sql:1-120` — re-dedupes, recreates the partial unique index `WHERE country_code IS NOT NULL`, and `RAISE EXCEPTION` if any duplicate group remains (pgcode `P0001`).
- `scripts/run_migrations.py:172-179` — `TOLERATED_CODES` only swallows `42P07/42701/42710/23505/42P06/42723`. `P0001` is NOT tolerated, so a real `RAISE EXCEPTION` would fail the build.
- `src/backend/app/domains/content/corporate/repository.py:15-76` — `upsert_company` is a **read-then-INSERT** with no `ON CONFLICT` clause. Two concurrent adapter rows for the same name+country can both pass the SELECT and both INSERT, violating the index. Index is also partial (`WHERE country_code IS NOT NULL`), so any SBTi row with an unmapped country (`sbti_adapter.py:55-65` only maps ~33 countries) stores `country_code=NULL` and dedup never applies.
- `api/company_routes.py:228-274` — adapter sync runs in a `BackgroundTasks` thread via `asyncio.run`, so each run gets its own connection — same dedup race.
- Live: `/api/companies?limit=50` still returns 12× `2Connect`, 9× `2050 Consulting` SE, 6× `20Cube Logistics`. `2050 Consulting` SE → mapped country, NULL excuse does NOT apply — so the race or a sha-skip is the cause.
**User-facing impact:** Company directory is overrun with apparent duplicates; the credibility of the corporate tracker collapses on first scroll.
**Root cause:** (a) `upsert_company` has no Postgres-level dedup primitive (no `ON CONFLICT DO UPDATE`), so concurrent SBTi rows race past the pre-SELECT; (b) every SBTi sync after mig 038 ran has been free to repopulate duplicates because the runner uses `MIGRATIONS_TOLERATE_ERRORS=true` (`cloudbuild.yaml:67`) and mig 038's hash gets registered on first apply — re-running won't catch new dups.
**Smallest fix:** Replace `INSERT INTO companies` (`repository.py:64`) with `INSERT ... ON CONFLICT (LOWER(TRIM(name)), country_code) WHERE country_code IS NOT NULL DO UPDATE SET name = EXCLUDED.name RETURNING company_id`, then add a Mig 043 that re-runs the 038 dedup pass post-deploy. Backfill country_code for unmapped SBTi rows so the partial index actually applies.

### 2. Article generation length (enrichment too short)
**Status:** PARTIAL
**Evidence:**
- `src/backend/app/domains/content/article_enrichment_service.py:479-504` — prompt explicitly asks for "200-400 words, plain prose paragraphs"; `max_tokens=1200`.
- `:526-575` — climate context summary capped at "exactly 2-3 sentences", `max_tokens=300`.
- `:769` — fallback excerpt truncates source text to 600 chars.
**User-facing impact:** Articles appear thin — 200-400 words is the intentional design but doesn't surface the body of long source articles.
**Root cause:** Design choice — the enrichment is a *summary*, not the article body. The full source content lives in `articles.extracted_text` but the frontend only renders `enriched_excerpt` and `climate_context_summary` (`articles/[id]/page.tsx:384-411`); there is no panel that shows the underlying long-form text.
**Smallest fix:** Bump the prompt to "300-700 words" and raise `max_tokens` to 2200; OR add a collapsible "Full article" panel that renders `article.extracted_text` separately.

### 3. Claim count — "1 claim per article"
**Status:** PARTIAL
**Evidence:**
- `api/admin_pipeline_routes.py:87` — feed-article claim extraction uses `max_claims=10`.
- `api/url_analysis_routes.py:1548-1559` — URL analysis uses `URL_ANALYSIS_MAX_CLAIMS_TOTAL` default `60`.
- `api/admin_pipeline_routes.py:327-329` — claim extraction skips articles where `len(article_text) < 50`.
- Ingestion fallback: `article_text = article.get("extracted_text") or article.get("excerpt") or ""` (`:327`) — RSS-only articles often have <300-char excerpts.
- `src/backend/app/domains/intelligence/prompts.py:218-239` — `claim_extraction` prompt enforces "atomic, singular, specific, verifiable" claims, so a 200-word RSS excerpt typically yields 0-2 atomic claims.
**User-facing impact:** Most feed articles show 0-1 claim chips; the chrome looks empty.
**Root cause:** The pipeline runs claim extraction on whatever text was ingested. RSS feeds often deliver excerpt-only payloads; without a full-text scrape step, the extractor has nothing to chew on.
**Smallest fix:** Add a `full_text_fetch` pre-pass before claim extraction (HEAD + GET the `source_url`, run trafilatura, store into `extracted_text`). Cheap; bounded; converts most "1 claim" articles to 4-8 claims.

### 4. "90% credibility with 1 claim" trust gap
**Status:** PARTIAL
**Evidence:**
- `src/backend/shared/reliability_scorer.py:1-166` — formula is `source_credibility×0.50 + verified_claims×0.30 + content_relevance×0.20`.
- `:119-141` — when `total_claims > 0`, claims_component is `(verified_ratio×100 − false_ratio×100 − misleading_ratio×50) × 0.30`. With `total_claims=1, verified_claims=1`, claims_score=100 → adds 30 points. Source 80 → 40 points. Relevance default neutral → 12 points. Total 82 → HIGH.
- **No claim-density factor anywhere**: 1/1 verified scores the same as 8/8 verified.
**User-facing impact:** Articles with one trivial verified claim show "90% credibility" — the headline number tells the user the article is rock-solid when it's barely been examined.
**Root cause:** The scorer was specified to weight VERIFICATION RATE, not VERIFICATION DEPTH. A penalty for "thinly-claimed articles" was never added.
**Smallest fix:** Add a `claim_density_penalty` factor — e.g., `density_factor = min(1.0, total_claims / 6)`; multiply the claims_component by this. An article with 1 claim now contributes `100 × 0.30 × 0.17 = 5` to the score instead of `30`. Or surface "Limited evidence" badge when `total_claims < 3` and cap the HIGH label.

### 5. Deep-search follow-up chat
**Status:** PARTIAL
**Evidence:**
- `src/frontend/src/app/deep-search/page.tsx:468-478` — there is a single "Ask about this result in chat" button that calls `openAssistant(...)` with a templated string.
- No `<textarea>` or input for inline follow-up on the result; conversation is fire-and-forget.
- `:276, :292, :319, :328` — only inputs on the page are the initial query / topic-A / topic-B / country fields.
**User-facing impact:** User asks one deep question, gets one answer, and cannot iterate without re-running a fresh deep-search query.
**Root cause:** Deep search was built as a single-shot synthesis; the chat panel is a separate global surface. There is no "continue this conversation" wiring between the synthesised result and a thread.
**Smallest fix:** Add an inline `<textarea>` below the result that POSTs to `/api/chat` with `view_context.deep_search_query = searchResult.query`. The chat backend already supports `view_context` (`api/chat_routes.py:43, 165-229`) so the round-trip is one new component, no backend work.

### 6. Light-mode contrast bug in deep-search report
**Status:** WORKS
**Evidence:**
- `src/frontend/src/app/deep-search/page.tsx` — every textual class pair audited has a `dark:` partner (counts: `text-gray-*` 55 occurrences vs `dark:text-*` 98 occurrences, all `text-gray-*` paired with a dark variant).
- `src/frontend/src/components/SentenceGroundedAnswer.tsx:29-58` — sentence pills define explicit light + dark token pairs.
- The `prose prose-sm dark:prose-invert` wrapper at `:463` ensures markdown content respects the active theme.
**User-facing impact:** None observed in current code; prior reports of this bug appear to have been fixed in the most recent rebuild.
**Root cause (if BROKEN):** N/A — no missing-dark-variant pattern found.
**Smallest fix:** N/A. If the user is still seeing low-contrast text, capture a screenshot — most likely a deployed CSS cache issue rather than a code defect.

### 7. Broken article links
**Status:** BROKEN
**Evidence:**
- `src/backend/services/ingestion_service/src/scraper.py:74-94` — RSS scraper takes `entry.link` as-is, no HEAD validation.
- `src/backend/services/ingestion_service/src/main.py:255-317` — `article_url = article_data.get("url")` is persisted unchecked.
- Grep across `src/backend` for `link_check|url_validate|broken_link|httpx.head` returned 0 files in backend code.
**User-facing impact:** A non-trivial fraction of article links lead to 404 / paywalled / removed pages; the "Source" link in article detail page is unreliable.
**Root cause:** No link-rot detection runs. Once a URL is stored at ingest, it never gets re-verified, and stale URLs accumulate.
**Smallest fix:** Add a nightly Cloud Scheduler job that HEADs the 100 oldest unverified `source_url`s, flags 4xx/5xx in a new `articles.source_url_status` column, and either marks them with a visible "Original link unavailable" affordance or hides the link.

### 8. Share buttons
**Status:** BROKEN
**Evidence:**
- `src/frontend/src/components/ShareButton.tsx:48-68` — opens Twitter/LinkedIn/Facebook intent URLs + copy-link + mailto. The popup invocation works in principle.
- **But:** the share URL is `${window.location.origin}/articles/${articleId}?ref=share` (`:17-20`). The article page has no OG meta defined for `[id]` route — grep for `openGraph|og:title|og:image|og:description` in the page files returns nothing for `articles/[id]/page.tsx`. Twitter/LinkedIn previews will be blank.
- `src/frontend/src/app/articles/[id]/page.tsx` is a client component (`"use client"`) so it cannot export Next.js `generateMetadata` — OG enrichment is impossible without a server-rendered wrapper.
- No `navigator.share` usage either (Web Share API would let mobile users share natively).
**User-facing impact:** Share clicks open the platform window, but social previews show generic site-name / no thumbnail — links look untrusted; engagement is suppressed.
**Root cause:** Article page is client-rendered with no server-side metadata generation; OG image route exists (`api/og_image_routes.py`) but isn't wired to article pages.
**Smallest fix:** Split `articles/[id]/page.tsx` into a server `layout.tsx` (or sibling `page.tsx` server component) that emits `generateMetadata` with title/excerpt/og:image (point og:image at `/api/og/article/{id}`), keep the interactive bits as a client child. ~30 lines.

### 9. CSV/PDF export buttons
**Status:** BROKEN
**Evidence:**
- `src/frontend/src/app/articles/[id]/page.tsx:220-235` — buttons are `<a href=".../api/export/article/${article_id}?format=csv" target="_blank">` and same for `pdf`.
- `api/export_routes.py:225` — `@router.post("/article/{article_id}/pdf")` — POST only, no GET.
- `api/export_routes.py:328` — `@router.post("/search/csv")` — POST only, takes search filters as query params.
- Both endpoints require `Depends(get_current_user)` (`:228, :335`) — anchor-link GETs send no Authorization header, would return 401 even if the method matched.
- There is NO `GET /api/export/article/{id}?format=csv` route — the per-article CSV doesn't exist at all.
**User-facing impact:** Clicking CSV or PDF on the article page yields 404 or 405 in a new tab — every paying user clicking export hits a dead button.
**Root cause:** Frontend was wired to a contract the backend never implemented (GET + query-param format selector). Backend has POST endpoints, JWT-gated, with method-specific routes.
**Smallest fix:** Either (a) add `GET /api/export/article/{id}/csv` and `GET /api/export/article/{id}/pdf` that accept a `?token=...` query param (or session cookie) and stream the file; or (b) replace the `<a>` tags with onClick handlers that `fetch(..., {method:"POST", headers:{Authorization: ...}})` and blob-download the response. Option (b) is smaller (~20 lines, no backend change).

### 10. Sources not scored (3-axis)
**Status:** PARTIAL
**Evidence:**
- `infrastructure/database/migrations/versions/041_source_3axis_scoring.sql:24-107` — adds `editorial_score`, `factcheck_score`, `transparency_score` columns, backfills tier-based defaults for ALL rows (T1→90/90/90, T2→70/75/65, T3→55/50/60, unknown→30/25/30, retracted→5/5/5), then hand-curates ~6 named sources.
- Migration's `RAISE NOTICE` at `:111-122` only logs — never raises if rows remain unscored, so we can't be certain prod is 100% backfilled.
- `api/source_registry_routes.py:1-80` — register/list custom sources; no scoring writeback at registration (new user-registered sources start with no 3-axis scores; they fall under the partial `WHERE tier=...` updates only if a tier is set at insert).
- No editorial UI to mutate scores per source — must be done via direct SQL.
**User-facing impact:** Defaults are reasonable, but the moment a source slips through without a `tier` value (or is registered fresh) its 3 axes are NULL, which the frontend renders as "—" / hidden, and the audit trail looks empty.
**Root cause:** Migration backfills tier-bucketed sources but doesn't fence new inserts. The source-suggest path doesn't auto-assign a tier.
**Smallest fix:** Add a check constraint or default-value clause to the `INSERT` paths in `api/source_registry_routes.py` and `api/source_suggestion_routes.py` so new sources land with `tier='unknown'` and the 30/25/30 defaults from mig 041. Plus a one-shot SELECT to ensure no row has NULL scores after deploy.

### 11. Doc upload analysis (PDF/Word, 100+ pages)
**Status:** MISSING
**Evidence:**
- `api/research_routes.py:21-66` — `ResearchAnalysisRequest` accepts only `url | doi | text`; no `UploadFile`, no multipart endpoint anywhere in the route.
- `src/backend/app/domains/intelligence/research_report_service.py:170-249` — `_resolve_url_with_pdf_detection` handles a remote PDF URL or HTML metadata page; extracts via PyPDF2 in `_extract_pdf_with_page_count` (`:310`) — but the user must give it a *public URL*.
- `:239` — fallback `text = html_text[:50000]` (50KB cap). For a 100-page report this is ~10-15% of content.
- No Word (.docx) handling anywhere.
**User-facing impact:** Users cannot upload a local file. They must host it publicly first. 100-page corporate sustainability reports → only first 50KB analysed even if URL-hosted.
**Root cause:** Research route was never spec'd for file upload.
**Smallest fix:** Add `POST /api/research/upload` with `UploadFile`, save to GCS/tmp, run the existing `_extract_pdf_with_page_count` against the bytes. Raise the chunked-LLM cap so 100-page PDFs aren't truncated. For Word, add `python-docx` text extraction. ~1-2 days.

### 12. Corporate sustainability report analysis
**Status:** MISSING (effective)
**Evidence:**
- `api/url_analysis_routes.py` — URL analysis pipeline works on article URLs; corporate PDFs go through `/api/research/analyze` instead.
- `api/research_routes.py` accepts URLs, so technically a corporate report URL works — but only on the first 50KB of HTML or first PDF if directly served.
- `api/company_routes.py:103-143` — `/api/companies/{ticker}/analyze` takes only a `claim_text` string, not a report URL. There is no path that says "given this 200-page company sustainability report, extract all claims, verify against the disclosure ledger."
**User-facing impact:** ESG officer cannot drop a corporate report URL and get an end-to-end audit; they must paste claim-by-claim into the company analyser.
**Root cause:** No multi-claim corporate-report ingestion path exists.
**Smallest fix:** Add a `/api/companies/{ticker}/analyze-report` route that downloads the report (via research_report_service), runs the URL-analysis claim extractor against full text, then runs each claim through `_analyze_claim`. ~1 day.

### 13. Research feed (subscribe-to-topic)
**Status:** MISSING
**Evidence:**
- `api/saved_query_routes.py:1-40` — there IS a recurring search subscription API for *articles* (`/api/user/saved-queries`) with intervals hourly|daily|weekly|monthly. Not wired to /research.
- Grep across `api/` for `subscribe.*research|research.*subscribe|research.*feed` → 0 hits.
- `src/frontend/src/app/research/page.tsx:53-80` — single-shot form; no save/subscribe affordance.
**User-facing impact:** No way for a researcher to be alerted when new papers on their topic land — they must re-run the form daily.
**Root cause:** Research is conceptualised as a single-doc analyser, not a feed.
**Smallest fix:** Reuse the `saved_queries` table with a `query_type='research'` flag; add a Cloud Scheduler poller that runs the user's query against CrossRef / OpenAlex; surface new hits in a `Research Inbox` tab. ~2 days.

### 14. Scenario simulation
**Status:** MISSING
**Evidence:**
- Grep for `scenario_simulate|temperature_raise|what_if|/api/scenario` returns 0 files.
- `api/map_routes.py` has country_projections endpoints (`/api/map/country/{cc}/projections`) which return IPCC AR6 SSP1-2.6 / SSP2-4.5 / SSP3-7.0 fixed scenarios for ~20 countries (per arch-report `[P] 5.7`).
- No user-driven "raise CO₂ by X%, what happens to this country" path.
**User-facing impact:** Users can read pre-canned IPCC scenarios but cannot simulate counterfactuals.
**Root cause:** Was never specced. The architecture report does not actually claim it ships.
**Smallest fix:** Out of scope for any short slice — true scenario simulation needs a climate-model backend (FaIR, MAGICC) which is a multi-week build. Until then, document explicitly that "Projections" = IPCC pre-canned, not user-driven.

### 15. My Feed save flow
**Status:** BROKEN
**Evidence:**
- `src/frontend/src/components/BookmarkButton.tsx:95-101` — `api.createBookmark(articleId)` / `api.deleteBookmark(articleId)`.
- `src/frontend/src/lib/api.ts:303-323` — those hit `/api/user/bookmarks/{articleId}` (POST/DELETE/STATUS).
- `api/user_routes.py:533-708` — these legacy bookmarks endpoints exist and work.
- `api/saved_items_routes.py:1-244` — the NEW polymorphic `/api/user/saved` endpoints ship in this deploy but **nothing in the frontend calls them**.
- `src/frontend/src/lib/chatActionDispatcher.ts:198-236` — `bookmark_article` chat skill ALSO points at the legacy `/api/user/bookmarks/{id}` (`:205`), not the new endpoint.
- Two parallel save systems exist; both quota-gate `saved_articles`; neither is reconciled.
**User-facing impact:** The save button works for articles (legacy path), but the user feedback "save not only articles but analyses, searches, feed settings" remains entirely unserved on the FE — `/api/user/saved` is fully implemented and zero-used.
**Root cause:** Migration 042 + saved_items routes shipped without frontend integration; BookmarkButton was never migrated.
**Smallest fix:** Add a `useSave({type, id})` hook that POSTs to `/api/user/saved`; replace BookmarkButton's bookmark call; add Save buttons on /search, /deep-search, /companies, /feed result rows. Build a `My Saves` page that lists rows from `/api/user/saved`. ~1-2 days.

### 16. Persona personalization UX
**Status:** WORKS (as designed — but the "7 personas" claim is overstated)
**Evidence:**
- `src/frontend/src/lib/view-context.tsx:33-43` — `ViewContextState` has no `persona` field; only `route, articleId, countryCode, analysisId, deepSearchQuery, ...`.
- The only persona-aware toggle is `?view=business` on Country Passport (`src/frontend/src/app/country/[code]/page.tsx:143, 317, 352`) and Company Detail (`src/frontend/src/app/companies/[ticker]/page.tsx:85-275`).
- Grep for `setPersona|userPersona|usePersona` in `src/frontend/src/components` returns ZERO. The only `persona` hit is a comment line in `ProjectionsPanel.tsx:9`.
**User-facing impact:** Two-state toggle (Public / Business). The "Consumer / Journalist / Scientist / Policymaker / Financial Analyst" personas described in the architecture report have NO routing, defaults, or UI of their own.
**Root cause (if BROKEN):** N/A — design works; doc claim is overstated.
**Smallest fix:** Rename docs from "7 personas served" to "Public + Business view modes (with persona-flavoured copy)". If the goal is real persona routing, that's a multi-week project.

### 17. Business view toggle
**Status:** WORKS
**Evidence:**
- `src/frontend/src/app/country/[code]/page.tsx:317, 352` — toggle UI + persistent `?view=business` URL state.
- `src/frontend/src/app/companies/[ticker]/page.tsx:208-275` — same pattern on company detail.
- `src/frontend/src/lib/plainLanguage.ts:254-414` — separate framing strings; `complianceFrameworksFor(...)` returns the per-KPI chip set (CSRD/IFRS S2/TCFD/TNFD).
**User-facing impact:** Real per-KPI sentence + chip swap; not cosmetic.
**Root cause:** N/A.
**Smallest fix:** N/A. Could expand to deep-search/analysis surfaces; currently only on Country + Company.

### 18. Compliance chips (CSRD / IFRS S2 / TCFD / TNFD)
**Status:** WORKS
**Evidence:**
- `src/frontend/src/lib/plainLanguage.ts:394-414` — `complianceFrameworksFor(kpi)` maps KPI categories to chip arrays (e.g. `temp_anomaly → ["CSRD","IFRS S2","TCFD"]`).
- `src/frontend/src/app/country/[code]/page.tsx:600-615` — chips render via `KpiCard.complianceFrameworks` prop with `data-testid` and `title="Relevant to ${fw} disclosure"`.
- `:368, :390, :411, :437` — chips passed through for 4 KPIs in business view.
**User-facing impact:** Per-KPI chips appear in business view with consistent typography + tooltips. Real, not placeholder.
**Root cause:** N/A.
**Smallest fix:** Extend `complianceFrameworksFor` to per-CLAIM (currently per-KPI only). Not blocking.

### 19. Map walkthrough beyond the on-load 7-step
**Status:** WORKS (4-step, not 7, but functional)
**Evidence:**
- `src/frontend/src/components/map/MapWalkthrough.tsx:28-100, 132-218` — 4 steps + dismiss + re-trigger via "Take the tour" button; persists dismissal in `localStorage[clilens_map_walkthrough_dismissed]`.
- No per-layer tooltip detail or persistent help drawer beyond the walkthrough.
**User-facing impact:** Onboarding works; deeper exploration help isn't there.
**Root cause:** N/A — the architecture report says "tooltips" but never says the layer cards have hover-help; current implementation matches.
**Smallest fix:** Add a `?` icon on each layer button that opens a small popover with the layer's methodology + source citation. ~half day.

### 20. Country passport for all 195 vs only 22 curated
**Status:** WORKS (with explicit fallback)
**Evidence:**
- `src/backend/app/domains/content/country_biome.py:53` onwards — 22 entries in `_BIOMES` dict (verified via grep `^    \"[A-Z][A-Z]\":\s*CountryBiome` → 22 matches).
- `:35-50` — `GENERIC` fallback narrates "summary being assembled" with drill-down CTAs to the chat.
- `src/frontend/src/app/country/[code]/page.tsx:624-642` — `CountryBiomeSummary` rendered for every country; calls `onAskAssistant` for chat handoff when only the generic stub returns.
- Live: `/api/map/biome-overview` returns 196 countries with biome symbols (verified by operator). Full narrative ≠ biome symbol — symbol/colour exists for all, prose narrative for 22.
**User-facing impact:** All 195 countries get a map symbol + colour + the generic affordance; only 22 get hand-curated prose. Honest fallback in place.
**Root cause:** N/A — design choice; described in code comments.
**Smallest fix:** Optional — generate AI-written biome narratives for the remaining 173 via the existing enrichment service; gate on editorial review.

### 21. KG / weather context on article pages
**Status:** PARTIAL
**Evidence:**
- `src/frontend/src/app/articles/[id]/page.tsx:383-411` — `enriched_excerpt` + `climate_context_summary` panel renders weather + 5-year trend context **inline as one panel**, not as separate KG/weather modules.
- Grep for `KnowledgeGraph|WeatherPanel|/api/articles/.*kg|/api/articles/.*weather` against `src/frontend/src/app/articles` → 0 hits. No standalone KG panel; no separate weather widget.
- Backend `/api/research/weather-enrich` exists (`api/research_routes.py:69-96`) but the article page doesn't call it.
**User-facing impact:** Weather context is present but baked into the same panel; there is no knowledge-graph entity panel at all.
**Root cause:** KG was wired through ingestion (mig 013) but no UI consumer was built on the article page.
**Smallest fix:** Add `<KnowledgeGraphPanel articleId={...} />` + `<WeatherContextPanel articleId={...} />` as sibling cards; backend endpoints `/api/articles/{id}/kg` and `/api/articles/{id}/weather` already implied by mig 013 — verify or add them.

### 22. Agentic chat — 11 skills coverage
**Status:** WORKS
**Evidence:**
- `src/backend/app/domains/intelligence/skills.py:74-214` — `SKILLS_REGISTRY` has exactly 11 entries: `navigate, analyze_url, apply_search_filters, apply_map_filters, open_methodology_section, open_country, start_deep_search, bookmark_article, start_calibration_label, open_company, verify_corporate_claim`.
- `src/frontend/src/lib/chatActionDispatcher.ts:24-35` — `ChatActionType` union enumerates the same 11.
- `:52-64` — `ACTION_MODES` classifies 7 auto / 4 confirm — matches the arch report's claim verbatim.
- Pin test `tests/api/test_agentic_skill_pin.py` referenced in arch report and skills.py preamble.
- `bookmark_article` skill still POSTs to legacy `/api/user/bookmarks/{id}` (`chatActionDispatcher.ts:205`) — see item 15.
**User-facing impact:** Chat correctly proposes any of the 11 skills; dispatcher executes them. `bookmark_article` shares the legacy bug, but the protocol itself is in sync.
**Root cause:** N/A.
**Smallest fix:** Once item 15 is fixed, update the dispatcher's `bookmark_article` URL.

---

## Slice progress — autonomous run 2026-05-25

| Slice | Commit | Status |
|---|---|---|
| 1 — Export buttons (item 9) | `36af118` | shipped + deployed |
| 2 — Companies dedup hardening (item 1) | `900af29` | shipped; ON CONFLICT live |
| 2b — Mig 044 + runner @notolerate (cross-cutting) | `85b770d` | shipped; dedup TRULY clean (100/100 unique live) |
| 3 — Save flow unification (item 15) | `10b696f` | shipped; useSave hook + My Saves page |
| 4a — Credibility honesty (items 3 + 4) | `1cda89a` | shipped; density factor + Limited Evidence badge |
| 4b — full_text_fetch pre-pass | — | deferred (~0.5d separate slice) |
| 5b — Article OG metadata (item 8) | `4789a4e` | shipped; metadataBase + per-article OG + Twitter |
| 5a — Link rot detection (item 7) | — | deferred (~0.5d, needs Cloud Scheduler) |
| 6 — Deep-search follow-up (item 5) | `89ac8d7` | shipped; inline thread + session_id |
| 7 — Source scoring fence (item 10) | Mig 045 in progress | NULL-fill + P0001 assertion, runner @notolerate |
| Persona overclaim correction | this doc + memory | reality: Public/Business toggle only, NOT 7 distinct persona routings |

## Persona-claim correction

The architecture report `Climatefacts-Architecture-Report-2026-05-24.docx`
claims "7 personas served." The actual implementation is a single
Public ↔ Business view-mode toggle exposed on Country Passport
(`src/frontend/src/app/country/[code]/page.tsx:317, 352`) and Company
Detail (`src/frontend/src/app/companies/[ticker]/page.tsx:208-275`).
The 7 named personas (Consumer / Journalist / ESG / Scientist /
Policymaker / Financial Analyst / Business Decision-Maker) influence
*copy framing* in `lib/plainLanguage.ts` and *quota tier defaults* but
have no routing, no persona-aware default views, no per-persona UI.

Update the docx (or replace the wording) to: **"Public + Business
view modes (with persona-flavoured copy and quota tiers)"** unless
real persona routing is added — which is itself a multi-week project.

## Cross-cutting findings

- **Migrations idempotency vs `MIGRATIONS_TOLERATE_ERRORS=true`.** `cloudbuild.yaml:67` and `infrastructure/gcp/cloudbuild-migrate.yaml:79` both ship the tolerate flag. `scripts/run_migrations.py:172-179` swallows `42P07/42701/42710/23505/42P06/42723`. Means a migration that fails on `23505 unique_violation` is silently marked applied — exactly the situation the comment in `038_force_dedupe_companies.sql:3-7` describes for 036. Migration 038's `RAISE EXCEPTION` (P0001) is NOT in the tolerated set, so it would fail loudly — but only the FIRST time. Subsequent SBTi syncs that re-create dups will pass build because 038's hash is already registered. **The build pipeline currently cannot prevent dedup regressions.**
- **`upsert_company` race.** Two adapter rows for the same name+country in the same sync execute under different psycopg2 connections (the SBTi adapter is async + row-by-row). Both can SELECT empty, both INSERT, both pass — only the second one violates the partial index, but that violation is per-statement and the previous one's INSERT survives. Need `ON CONFLICT DO UPDATE` to make this watertight.
- **Two parallel save systems** (legacy `user_bookmarks` + new `saved_items`) is a smell. Both quota-gate `saved_articles` independently; both have their own DB tables; only one is FE-wired. Pick one and migrate.
- **Article URL persistence has no rot detection** (item 7) — accumulates dead links forever.
- **Articles `is_synthetic=FALSE` is enforced everywhere relevant** (`api/export_routes.py:263, :359`; `api/admin_pipeline_routes.py:171` etc.) — synthetic purge from mig 040 is being respected.
- **Source-credibility scoring formula has no claim-density factor** (item 4) — this is the single most consequential algorithmic gap; it makes the headline trust number untrustworthy.
- **Persona claim in architecture report is significantly overstated** vs reality (1 toggle ≠ 7 personas).

---

## Suggested slice order

Designed so each slice is ≤2 days, prevents downstream blockers, and ships something the user sees first.

### Slice 1 — Export buttons (item 9)  ·  0.5 day
Replace `<a href="...?format=pdf">` with onClick → `fetch` + blob download, send `Authorization: Bearer ...` header. No backend change. Highest-visibility fix; touches paying tier directly; unblocks the "looks broken everywhere" impression on the article page.

### Slice 2 — Companies dedup hardening (item 1 + cross-cutting `upsert_company`)  ·  1-2 days
Add `ON CONFLICT (LOWER(TRIM(name)), country_code) DO UPDATE` to `repository.py:64`. Backfill `country_code` for the 33→195 unmapped SBTi locations. Add a Mig 043 that re-runs the 038 dedupe pass post-deploy and that migration is FRESH (new hash → guaranteed to run). Replaces the company-directory disaster impression.

### Slice 3 — Save flow unification (item 15)  ·  1-2 days
Migrate `BookmarkButton` + `chatActionDispatcher.bookmark_article` to `/api/user/saved`. Add Save buttons on search/deep-search/companies/feed. Ship a `My Saves` page consuming `/api/user/saved`. Deprecate (but don't delete) legacy bookmark endpoints behind a 6-week feature flag. Visible product improvement; closes the "save not only articles" feedback.

### Slice 4 — Credibility formula honesty (item 4 + item 3)  ·  1-2 days
Add claim-density factor to `ReliabilityScorer`. Add a "Limited evidence" badge + cap on HIGH when `total_claims < 3`. In the same slice, add a `full_text_fetch` pre-pass in the ingestion pipeline so articles with <50-char excerpts get scraped before claim extraction. Together these turn "90% credibility / 1 claim" into either "60% credibility / 1 claim with limited-evidence label" or "85% credibility / 6 claims" — both honest.

### Slice 5 — Link rot + Share OG metadata (items 7 + 8)  ·  1 day
Add nightly HEAD-check job for `source_url`s; populate `source_url_status`. Split `articles/[id]/page.tsx` into server-component shell + client child; export `generateMetadata` that uses `/api/og/article/{id}` for previews. Restores trust in outbound links and makes share clicks land properly.

### Slice 6 — Deep-search follow-up (item 5)  ·  0.5 day
Add inline `<textarea>` below the synthesised result; POST to `/api/chat` with `view_context.deep_search_query` set. Pure FE work.

### Slice 7 — Source scoring fence + persona doc correction (item 10 + cross-cutting)  ·  1 day
Make `source_registry_routes` insert with `tier='unknown'` default and the 30/25/30 scores from mig 041; add a Mig 044 NULL-fill pass. Update README + docs/methodology page to say "Public + Business view modes" instead of "7 personas served".

Items deferred (out of any short slice): **(11)** PDF/Word upload, **(12)** corporate-report claim ingestion, **(13)** research feed, **(14)** scenario simulation, **(21)** standalone KG + weather panels. These are 1-3 day each builds; queue for sprint after the 7 slices land.

Order rationale: Slices 1-3 are user-visible quality-of-life fixes that don't depend on each other and can land in parallel if multiple workstreams exist. Slice 4 is the highest-impact integrity fix and depends on nothing. Slice 5 needs Slice 1 patterns for the SSR/CSR split but doesn't block other work. Slices 6-7 are clean-ups with no dependencies. Nothing in the order blocks the deferred items if priority shifts.
