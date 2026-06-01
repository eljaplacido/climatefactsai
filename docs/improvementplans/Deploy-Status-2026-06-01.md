# Climatefacts.ai — Audit + Deploy Status (2026-06-01, session 3)

Continuation of the `fixes.md` final-polish push. This session ran on the
owner's machine **with the full local docker stack up** (postgres + API +
frontend + Playwright), so — unlike sessions 1-2 — migrations, query edits and
visual components were **validated against a running app** before deploy, not
shipped blind.

## Audit corrections to the prior record

The 2026-05-31 record said "17 items live". Re-auditing against the **live**
deploy + code corrected three entries:

| Item | Prior record | True state (2026-06-01) | Evidence |
|---|---|---|---|
| **F1** off-topic | "live" (ingest gate) | **HALF done** — gate blocked NEW articles, but the existing corpus was still served everywhere. The user's bus-accident article was still live. | No display surface read the off_topic flags; `is_synthetic = FALSE` was the only filter across 30+ query sites. |
| **F4** export | `VERIFY-ON-LIVE` | **WORKS in code** — rewired to `POST`+JWT+blob (`lib/api.ts:480-496`); the old `<a href>` GET "never worked". Needs a *logged-in* live test, not a code change. | Live GET → 405 (POST-only, expected). |
| **F2** contrast | `VERIFY-ON-LIVE` | **WORKS in code** — deep-search + chat use `dark:`-paired / context-correct colours; no light-on-light remains in the pinned-light theme. User screenshots predate `ae920ea` (dark-mode kill). | Static audit: only bare `text-white` is on teal buttons. |

## Shipped + deployed this session (validated against the running stack)

### Slice 1 — F1/T12: off-topic articles hidden from all listing surfaces · `8394b56` (LIVE)
- **mig 056** `articles.is_off_topic` column + partial index (bulletproof,
  `IF NOT EXISTS`). **mig 057** backfills it from the **curated**
  `topic_feedback` off_topic verdicts (~916 rows = the 4 deactivated SI/BG/RO
  general feeds, which are *also* the Eastern-EU skew the owner flagged).
- `AND is_off_topic = FALSE` wired into **every listing/aggregation query**
  (main list, feed, search results + facets, country/tag/dashboard counts,
  green-transition, all map density/stats/detail surfaces — ~40 sites).
  Single-article-by-id fetches stay UNFILTERED so a flagged article is still
  reachable by URL and can be un-flagged.
- The "report off-topic" button now drives the flag: `on_topic` un-hides for
  anyone; `off_topic` hides only for **authenticated** reporters (anon abuse
  guard); curated backfill is the bulk path. 9/9 unit tests (3 new).
- **Verified live:** prod `/api/articles` 200 (proves the column exists);
  locally, flagged articles confirmed excluded from list + FTS search + map.

### Slice 2 — F7: KG relationships as a visual graph · `b052293` (deploying)
- Replaced the ASCII `━REPORTS_ON━▶` rows with a deterministic **circular
  node-link SVG** (fixed geometry, no force-sim → stable layout), nodes
  coloured by entity type, directed edges with **humanised** labels
  ("reports on"), precise detail kept in a collapsible list.
- **Render-verified via Playwright** (route-mocked 6-entity/6-edge graph
  against `next dev`): nodes, labels, arrowheads and edge labels all legible.

## The honest gap: off-topic per-article relevance (the bus class)

The bus-accident article is from **"Andina Peru"**, *not* one of the curated
flagged feeds, so it is **not** hidden by slice 1. Catching it accurately is a
real classifier job, not a SQL heuristic:

- **A keyword sweep is categorically unsafe here.** Measured on the real
  corpus: it would flag **65%** of articles — including BBC Climate, NYT
  Climate, Grist and most non-English climate sources — because RSS
  `extracted_text` is truncated and short titles rarely contain the exact
  keywords. Shipping it would hide most of the real corpus.
- **Embeddings aren't a shortcut either** — 0/666 real articles have an
  `embedding` populated, so a climate-centroid similarity can't run yet.
- **Correct path (next):** an LLM/source-aware relevance pass over the corpus
  (the §3/§8 GX10 Lane A relevance gate) that writes `is_off_topic` +
  `content_relevance_score` + a reviewer-traceable reason, run with a
  dry-run + per-source review so impact is measured before it hides anything.
  The column + filter + feedback plumbing shipped this session are exactly
  what that job writes into.

## Environment constraints that shaped scope

- Local `.env` → **local docker postgres**, `ENVIRONMENT=development`. No
  reach to prod Cloud SQL → data backfills must go via migrations (Cloud
  Build) or admin endpoints/GX10, not direct runs.
- The local dev DB is **stale** (predates mig 050): no `topic_feedback`,
  `source_credibility_tiers`, or `schema_migrations_applied`, and still holds
  the 3588 synthetic seeds. So data-curation items (**F11** source ratings,
  **F12b/c** balance/verdict) can't be validated locally — they are genuine
  prod-DB/compute jobs.

## Genuinely remaining (with the real blocker named)

| Item | Blocker / next step |
|---|---|
| **F1 bus-class** | LLM/source-aware relevance backfill (GX10 Lane A). Plumbing is ready; needs the classifier pass + dry-run review. |
| **F3** dark theme | Decision pending (build real ThemeProvider + full `dark:` token audit, OR remove the affordance). Light is pinned on purpose. |
| **F8a-full / F8b / F8c** research | Backend must emit `summary`/`key_findings`/`sdgs` + academic-only scope before the frontend can render a readable report. |
| **F9c** PPP lens | Company data is emissions-heavy; People/Profit pillars render thin without richer disclosure parsing. |
| **F11** source ratings | `source_credibility_tiers` data backfill (prod DB). |
| **F12b/F12c** | Ingestion rebalance + a verification-pipeline corpus run (prod DB/compute). |
| **F5c / F5d** | Surface "why weak evidence" prominently; add the research/DOI corpus to deep-search. |
| **F4** | Logged-in live export test (code is correct). |

## Live tally
F12a · F1(ingest+**display+curated-backfill**) · F5e · F5b · F5a · F9a · F9b ·
F9d · F9e · F10a · F6b · F7(**graph viz**+cookies) · F13 · F8a(relabel) · F2
(contrast clean) · F4 (export wired) — plus pre-existing map-sync, SDG titles.
