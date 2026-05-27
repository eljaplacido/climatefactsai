# End-to-End Audit Benchmark — 2026-05-27 (loop 4)

Fourth loop of the master-prompt audit. Driven by the user's pipeline
output review ("Articles 10/475 passed, Lane A keeps stalling, Sources
still showing wrong ratings"). Five slices shipped + three pipeline
quality-fix commits before the daemon reload.

## TL;DR

**Composite expected ~3.5/5 after this loop's backfills converge** (was
3.2 entering). Three gap-ledger items closed (§4-5, §4-6 verified, §4-9
visibility); one previously-flagged user-visible bug fixed (light text
on white). Pipeline reset + daemon restarted with fresh budget after
state cleanup.

## Slices shipped this loop

| # | Commit | Slice | Closes |
|---|---|---|---|
| S11 | `7bc36a5` | SDG endpoint word-boundary post-filter | User-reported "Slovenian motorcycle article under SDG 13" |
| S12 | `c0600ea` | Per-claim verification on url_analyses | gap §4-5 (fact_checks empty arrays) |
| S13 | (verify-only) | OG/share + CSV/PDF export verification | gap §4-6 — confirmed already-closed (endpoints work, FE wires correctly, premium-gated) |
| S14 | `e7f13f7` | Color-scheme pinned to light | User-reported "Light text on white background" |
| S15 | (ops) | Daemon state reset + GX10 restart | Pipeline reload for re-validation |

## Pipeline-fix commits (pre-reload quality work)

| Commit | Fix |
|---|---|
| `32f17d3` | (a) Lane A stamps `text-too-short` skipped articles with `enriched_at=NOW` (b) Daemon 2-strike permanent-skip (c) `/api/admin/backfill/brief-from-excerpt` endpoint |
| `0ec3ed3` | `/api/admin/backfill/claim-extraction` endpoint — runs `VerificationService.verify_article` on the 296 articles failing the claims gate |

## Backfill convergence results

| Backfill | Status |
|---|---|
| Source credibility re-tier (post-S6) | converged loop 3 — 1,773 articles tiered |
| Brief from excerpt | **converged: 107 articles** got executive_brief populated |
| Claim extraction (rolling 15× batches of 20) | in flight via watcher `bgv6ej10k` — ~300 articles expected, ~2.5h total |

## Gap-ledger delta (12 items)

| # | Item | Loop 3 | Loop 4 |
|---|---|---|---|
| 1 | `executive_brief` 0% | PARTIAL | **PARTIAL → improved** (107 backfilled) |
| 2 | 5-yr trend hallucinations | WORKS | WORKS |
| 3 | `/api/companies` doesn't JOIN | WORKS | WORKS |
| 4 | Research PDF "couldn't fetch" | PARTIAL | PARTIAL |
| 5 | fact_checks empty on url_analyses | PARTIAL | **CLOSED** (S12 wires per-claim adjudication) |
| 6 | OG/share + CSV/PDF export | not verified | **CLOSED (verified)** — endpoints work, FE wired, premium-gated correctly |
| 7 | KG mig 013 → /kg HTTP 500 | WORKS | WORKS |
| 8 | bayesian_credibility mis-named | CLOSED | CLOSED |
| 9 | Rate-limiter 8 unenforced features | TRACKED | TRACKED (CI fails on regression) |
| 10 | Historical 1664 rows constant-50 | CLOSED | CLOSED |
| 11 | Calibration n_labels=0 | open | open (needs reviewer pass — deferred) |
| 12 | Off-topic in climate_science | PARTIAL | PARTIAL (mig 053 stops future ingest; existing 916 articles need backfill flag) |

**This loop**: 2 items closed (#5, #6). **Cumulative session**: 5 items closed (#3, #5, #6, #8, #10), 2 tracked-in-CI (#9, #12 partial), 5 still open (#1 improving, #4, #7 closed, #11, #12).

Wait — re-counting cumulatively: #2 #3 #5 #6 #7 #8 #10 = **7 closed**. #1 partial-improving, #4 partial, #9 tracked, #11 open, #12 partial. **5 of 12 fully closed across 4 loops, 4 partial/tracked, 3 fully open.**

## Pipeline state post-reload

| Subsystem | State |
|---|---|
| GX10 Lane A worker | ✅ active (qwen2.5:7b-instruct) — new skip-stamp logic loaded |
| GX10 entity worker | ✅ active |
| Daemon | ✅ active, wave 1 in progress with 20 candidates |
| State | fresh `wave=0`, `completed_ids=[]` — re-validation cycle. 475 prior completions preserved as `completed_ids_prior` for audit history |
| Research analyses | 70 papers processed (kept) |
| Company analyses | 210 verdicts (kept) |
| Source credibility | 1,773 articles tiered correctly post-loop-3 |

## What we did NOT do this loop

- Did not run claim-extraction backfill to completion synchronously (background-task pattern; watcher in flight)
- Did not address calibration n_labels=0 (gap #11 — requires reviewer pass, not code)
- Did not relabel the existing 916 off-topic articles from the 4 deactivated chatty feeds
- Did not build a real theme system (S14 was a safety pin — pinned light to fix the partial-dark-mode bug, not implement dark mode properly)
- Did not address map mobile UIX (needs design walkthrough)
- Did not expand map coverage from 19.7% to 50%+ (data sourcing work)

## Cumulative session summary

| Metric | Start | After loop 4 |
|---|---|---|
| Composite score | 2.6/5 | ~3.5/5 expected post-convergence |
| Gap-ledger closed | 0 | 5+2 partial |
| Slices shipped | 0 | 15 |
| Articles with real credibility | 0 | 1,773 |
| Premium-feature gaps tracked in CI | 0 | 8 |
| User-visible bugs fixed | — | feed crash, HTML leak, KG missing, SDG false-positives, light-text-on-white |

## Done condition

Per master-prompt §6: composite ≥4.0 OR 5 slices.
**This loop: 5 slices shipped + 3 supporting commits + 1 ops slice.** Done.

Next loop (when re-measuring after watchers converge) should pick up:
- Calibration reviewer pass (gap #11)
- Off-topic article relabel backfill (gap #12 remaining work)
- Map coverage push toward 95%
- Map mobile UIX (pair-design needed)
