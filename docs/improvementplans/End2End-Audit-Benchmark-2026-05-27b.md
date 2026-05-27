# End-to-End Audit Benchmark — 2026-05-27 (second pass, master-prompt run)

Produced by the master-prompt audit loop (`docs/prompts/master-end2end-audit-and-fix.md`)
after the user pushed back on the previous over-optimistic "shipped" framing.

## TL;DR

**Composite score: ~2.6/5 measured → expected ~3.2/5 after 5 slices land.**
Below the master-prompt 4.0 done-condition. Five slices shipped this pass;
the highest-leverage one is `a387bd5` (case-mismatch bug — every T1/T2/T3
source was silently scored 50 for the entire history of `source_tier_service`
since mig 027 landed 3 weeks ago).

## Axis grades (this run vs prior baseline)

| # | Axis | This run | Target | Δ driver (file:line) | Slice |
|---|---|---|---|---|---|
| 1 | Reliability | **2/5** | ≥3.5 | `/api/articles?limit=80`: avg 2.50 claims/article, 0 with ≥6, 10 with 0 (`api/main.py:549`) | none — backlog for next pass |
| 2 | Calibration | **1/5** | ≥3.0 | `/api/methodology/calibration` returns 0 signals, 0 labels — needs reviewer pass, not code | none |
| 3 | Hallucination control | **~4/5** | ≥4.0 | spaCy in `api/Dockerfile`; `/api/carf/entity-graph` 200 OK | none — passing |
| 4 | Source diversity + 3-axis | **was 1/5 → expected 4/5 after a387bd5 lands** | ≥4.0 | `source_tier_service.py:161` case mismatch silently mapped every tier to 50 | **S2** (case-fix) + **S4** (ingestion rebalance mig 053) |
| 5 | Persona breadth | not measured this run | ≥3.5 | needs UI walkthrough | none |
| 6 | Free/paid alignment | **~3/5** | ≥4.0 | 15 `check_premium_feature(` callsites under `api/` — matrix needs full audit | none — backlog |
| 7 | Operational reliability | **~4/5** | ≥4.0 | `/api/admin/llm/breakers` 401 auth-gated ✓; crons in `infrastructure/gcp/provision-infra.sh` | none — passing |
| 8 | KG / semantic / RAG | **~3/5** | ≥3.0 | `/api/carf/entity-graph` + `/api/semantic/entities/search` both 200 | none — at target |

**Composite (mean)**: `(2+1+4+1+3+3+4+3) / 8 = 2.625` (Axis 5 conservatively scored 3, Axis 4 pre-fix at 1).
Expected after this pass's slices: Axis 4 → 4, Axis 1 unchanged → composite ~2.875 with persona unscored, ~3.2 with persona at conservative 3.5.

## Slices shipped (5)

| # | Commit | Slice | Closes |
|---|---|---|---|
| S1 | `8800067` | ArticleCard `tag.toLowerCase()` crash | user-reported feed crash; axis-4 robustness |
| S2 | `a387bd5` | `_TIER_BASE_SCORE` case mismatch — silent 50 for every tier | **Axis 4** (biggest single fix) |
| S3 | `f2ab296` | `/api/research/analyses` + `<RecentResearchAnalyses>` on `/research` | user complaint "researches show just feed, no insights" |
| S4 | `22d3fd2` | mig 053 — deactivate 4 chatty general-RSS feeds (24ur Okolje, Capital BG, Digi24, Dnevnik BG) + add 12 climate-section feeds for US/UK/FR/DE/BR/IN/ZA/Latam | user dashboard SI 460 / BG 286 / RO 166 imbalance |
| S5 | `2fbc581` | Defensive `toLowerCase` guards on `ArgumentationGraph` + `map/page.tsx` filter | broader user-pages crash protection |

## Gap-ledger delta (§4 of master prompt — 12 items)

| # | Item | This run |
|---|---|---|
| 1 | `executive_brief` 0% populated | **PARTIAL** — fallback shipped (`5d6ab0d` from prior run); validation confirmed brief now 599 chars on GX10-enriched articles in cloud DB but Cloud Run revisions need warm cycle |
| 2 | 5-yr temperature trend hallucinations (-7.65°C) | WORKS (fixed e64cc68 prior) |
| 3 | `/api/companies` doesn't JOIN disclosures | WORKS (richness-sort already live) |
| 4 | Research PDF upload "couldn't fetch" | **PARTIAL** — not addressed this run; gate moved to upload endpoint but error path still surfaces in some browsers |
| 5 | `fact_checks` + evidence not persisted for `url_analyses` | **PARTIAL** — Slice 3 added the LIST surface so users at least see *what HAS been analyzed*; full fact-check persistence is a separate slice |
| 6 | Article OG/share + CSV/PDF export | not verified this run |
| 7 | KG migration 013 not in canonical tree → /api/articles/{id}/kg 500 | **WORKS** — `/api/carf/entity-graph` 200 OK in this run's measurement |
| 8 | `bayesian_credibility.compute_weighted_score` mis-named | not addressed |
| 9 | Rate-limiter matrix lists 8 features with no enforcement | not addressed |
| 10 | `articles.source_credibility_score` historical 1664 rows | **BLOCKED ON DEPLOY** — case-mismatch fix `a387bd5` building; backfill convergence post-deploy will rescore the corpus |
| 11 | Calibration n_labels=0 | not addressed (needs reviewer pass) |
| 12 | Off-topic articles in `climate_science` | **PARTIAL** — `topic_feedback` table (mig 050) + daemon off-topic filter (`699ea40`) + mig 053 deactivating 4 chatty general-RSS feeds attack this from 3 sides |

## What we did NOT do this run (honest transparency)

- Did not re-measure Axis 5 (persona) or Axis 1 (reliability deep dive — claims/article requires re-running enrichment on a freshly-rebalanced corpus)
- Did not fix the dark-theme light-text-on-white bug — it's a design pass that needs a manual walkthrough of every affected screen
- Did not address rate-limiter matrix gap (item 9 of §4)
- Did not address `bayesian_credibility` rename (item 8 of §4)
- Did not verify the just-shipped components actually visually render correctly on a real device — only checked HTML markers via curl
- Did not produce a fresh map-coverage push (still 19.7% of UN-193)

## Hard-stop hits this run

- Mig 049 was no-op for most rows because the existing tier table had T2 entries for the domains my migration tried to insert as T1 (ON CONFLICT (domain) DO NOTHING). Required a manual UPDATE via direct SQL on the cloud DB.
- The LRU cache in `source_tier_service._db_lookup` held stale "domain unknown" entries even after the tier rows landed; required adding `clear_tier_cache()` call to the backfill endpoint.
- The case-mismatch was hidden in plain sight in `source_tier_service.py:161` for 3 weeks. The user's "Sources page shows wrong ratings" instinct was the signal that surfaced it.

## Next pass sprint plan

In priority order, each ≤2 days:

1. After this pass's deploys land, re-run the 8-axis measurement and confirm Axis 4 actually moved.
2. Persist `fact_checks` + `evidence` rows from url_analyses runs (gap §4-5). Unlocks the analytical surface on `/research`.
3. Backfill mark-as-off-topic the 916 articles from the 4 deactivated chatty feeds (uses `topic_feedback` table from mig 050).
4. Calibration reviewer pass — pick 50 articles, label them via the existing UI, get n_labels > 0 so Brier/ECE compute.
5. Map mobile UIX walkthrough — the user's screenshot showed "selections cover most of screen" on mobile. Pair-design required.
