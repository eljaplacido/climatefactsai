# End-to-End Audit Benchmark — 2026-05-31 (Final-Polish loop, session 2)

Driven by the v2 master prompt (`docs/prompts/master-end2end-audit-and-fix.md`)
which folded the user's `fixes.md` punch-list into the trust-engine audit.
User granted full autonomy for fixes mid-session.

## TL;DR

Three slices shipped on branch **`polish/final-fixes-2026-05-30`** (NOT merged
to main — awaiting review). One security **P0** closed (the analytics dashboard
was world-readable), plus two correctness/UX fixes, each with a passing gate.
Remaining ledger items are documented honestly below; several were deliberately
**not** attempted because this environment cannot reach the live Cloud Run
deploy / prod DB.

**No composite re-score this loop** — §10-step-1 live measurement (live API +
prod DB) is not reachable here, so a numeric composite would be fabricated.
Grading is deferred to a session with live access; changes are stated as
per-axis deltas, not new absolute scores.

## Slices shipped this loop

| # | Commit | Slice | Ledger | Test gate |
|---|---|---|---|---|
| S1 | `d1e2523` | Gate `/api/analytics/*` behind admin auth | **F12a (P0)** | `tests/api/test_analytics_admin_gate.py` — 23 pass |
| S3 | `92d8242` | Filter web/CMS boilerplate from KG entities ("cookies" bug) | **F7 partial (P1)** | `tests/backend/test_entity_boilerplate_filter.py` — 36 pass |
| S2 | `0575d19` | Group CountrySelector by world region (not EU membership) | **F5e (P1)** | `npx tsc --noEmit` — 0 errors |

Branch is linear: `af851da` (main tip) → S1 → S3 → S2. S2 is last because it
was amended to add the new `countryRegions.ts` module after `tsc` caught a
missing import (see Process notes — the gate did its job pre-merge).

## What each slice actually changed

### S1 — F12a: analytics admin gate (security P0)
- **Before:** all 7 `/api/analytics/*` endpoints (`dashboard`, `pipeline`,
  `trends`, `sources`, `claims`, `verdicts`, `countries`) took only
  `Depends(get_db)` → publicly reachable. Exposed platform-wide aggregates:
  country distribution (reveals the Eastern-EU ingestion bias the user
  flagged), verdict distribution (~99% Unverified), pipeline health.
- **After:** new `require_analytics_admin` dependency on every route. Mirrors
  the existing `/api/admin/dashboard` + `admin_pipeline_routes` pattern:
  anonymous → 401, non-admin → 403, admin (`subscription_tier == "enterprise"`
  OR email in `ADMIN_EMAILS`) → 200.
- **Pin test** covers all 7 routes behaviourally (anon / non-admin / admin +
  email-allowlist) AND structurally (a route added later without the guard
  fails the test). Files: `api/analytics_routes.py`,
  `tests/api/test_analytics_admin_gate.py`.
- Directly answers the user's "I hope this [analytics] view is just for me as
  an admin" — it now is.

### S3 — F7 (partial): KG entity boilerplate filter
- **Before:** `EntityExtractionService` upserted every LLM-extracted entity;
  cookie-consent / nav / legal-footer strings leaked from RSS/HTML into the
  knowledge graph (user-reported "cookies" node).
- **After:** pure, unit-tested `is_boilerplate_entity(name)` (exact-match set +
  substring guards) skips boilerplate before upsert. 36-case pin test
  (boilerplate filtered; legit climate entities like "European Union",
  "Paris Agreement", "Amazon rainforest" pass through).
- **Still open in F7:** relationships still render as ASCII text rows
  (`KnowledgeGraphMini.tsx`), no graph-viz library yet; SDG chips copy minimal.
  This slice only closes the "cookies" sub-item.

### S2 — F5e: region selector relabel
- **Before:** `CountrySelector.tsx` grouped by `is_eu_member` into
  "EU countries" / **"Other European countries"** — the latter mislabelling
  the US, China, Brazil, etc. as European.
- **After:** groups by actual world region via a new
  `src/frontend/src/lib/countryRegions.ts` (ISO-3166 → `Europe`,
  `North America`, `Latin America & Caribbean`, `Middle East`, `Africa`,
  `Asia`, `Oceania`, then `Other`), ordered by `REGION_ORDER`. Default
  `allOptionLabel` changed "All EU countries" → "All countries".
- The three other `CountrySelector` call sites (map compare ×2, country panel)
  pass an explicit `allOptionLabel`, so the default change touches only the
  deep-search usage.

## Gap-ledger delta (this loop)

| ID | Item | Pre-loop | Post-loop |
|---|---|---|---|
| F12a | Analytics publicly reachable | BROKEN (P0) | **CLOSED** (S1, gated + pin-tested) |
| F5e | Region selector illogical labels | BROKEN | **CLOSED** (S2) |
| F7 | KG text-rows + cookies + SDG copy | BROKEN/PARTIAL | **PARTIAL** (S3 closes cookies; graph-viz + SDG copy remain) |

All other F/T ledger items unchanged this loop; none regressed.

## What we did NOT do (transparency)

- **F2 / F4 / F6a (`VERIFY-ON-LIVE`)** — chat "Claim:" contrast, article export,
  map layer visuals. Code reads correct at the cited lines; these need a live
  reproduce (the `docs/bugpics/` screenshots likely predate recent fixes). Not
  reachable from this environment → left open with that note, not closed.
- **F5b (deep-search cap 2→3)** — deliberately deferred. `fixes.md` says
  "max 3 for free users"; current cap is 2 per the documented 2026-05-23
  freemium decision (3 saved / 3 searches / **2** deep-research). This is a
  product-policy change, not a bug, and it ripples into quota test semantics
  (`tests/api/test_quota_service.py::test_free_tier_is_3_3_2` pins the 2).
  Needs explicit owner confirmation before flipping `api/quota_service.py:47`.
- **F1 / §3 (ingest relevance gate)** — highest-value content fix, but it
  touches the live ingestion pipeline and needs supervised landing + a live
  backfill of the ~916 off-topic rows. `editorial_gate.py` exists but is NOT
  wired to ingest — that's the wiring target. Not attempted unsupervised.
- **F5a/F5d, F8a/b/c, F9a–e, F10a/b, F11, F12b/c, F13, F3** — remain open per
  the v2 ledger §7. None regressed.
- **No live composite re-score** — see TL;DR.

## Process notes (for the next session)

- **Local test gate:** repo `pytest.ini` `addopts` require `pytest-cov` +
  `pytest-xdist` (CI-only; not installed locally). Run backend tests with
  `python -m pytest <target> -o addopts="" -p no:cacheprovider`. The ini
  itself is fine (an earlier "duplicate --cov" reading was a tool-output
  artifact under channel lag, not real corruption).
- **Frontend gate:** `cd src/frontend && npx tsc --noEmit` (vitest is the test
  runner; there is no jest config). The S2 typecheck caught a missing-module
  import before it could merge — fixed forward by adding the module and
  amending the slice, so the branch has no broken intermediate commit.
- **Branch is intentionally NOT pushed / NOT merged.** Cloud Build triggers
  only on push to `main`, so nothing deployed. Open a PR for review.
- Verify `git rev-parse HEAD` after each commit; this environment had
  intermittent tool-output truncation that made git state hard to read.

## Suggested next-session order (unchanged priorities)

1. F1/§3 ingest relevance gate (wire `editorial_gate.py`; Lane A / GX10) — highest content-quality leverage.
2. F8a research readable-report rendering (P0 UX) + F8b/c academic scope.
3. F12c verdict-yield lift (claim extraction + evidence retrieval).
4. F9a verify-claim toast + provenance trace.
5. Confirm F5b policy with owner, then flip if approved.
