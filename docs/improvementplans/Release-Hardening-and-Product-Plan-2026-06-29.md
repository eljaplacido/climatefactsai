# Release Hardening & Product-Fix Plan — 2026-06-29

Consolidates four audits (complexity/maintainability, best-practices research,
docs/memory coherence, map semantics/climate-data) into one prioritized program.
This is the **coordinating document** — work is sequenced in waves to avoid the
siloed-fix pattern that motivated it.

## Root cause (the one diagnosis behind every recent incident)

> **Every boundary in this system is synced by convention, position, or
> string-matching — and validated nowhere.** Types cross no seam; there is no
> single source of truth at any layer. Each fix satisfies one side of a
> hand-maintained contract while the other drifts silently until runtime.

This explains the map 2-tuple crash, url_analysis flat-vs-nested, the shim-patch
misses, the eval-gate bypass, and the missing/stale secrets. **The fix is to
enforce contracts, not patch instances.**

---

## TRACK A — Engineering hardening (maintainability / reliability)

### Wave 0 — Guardrails & quick wins (hours–1 day each; do before release)
1. **OpenAPI→TS contract gate.** `response_model=` on every route (only ~40% have it today: 110/277), export `/openapi.json`, generate types (`openapi-typescript` or `@hey-api/openapi-ts`), commit the artifact, CI fails on `git diff --exit-code` + `tsc --noEmit`. Kills the FE/BE drift class.
2. **Test-gate guardrails.** Autouse conftest fixture that `delenv`s ALL LLM provider keys unless a test opts in (stops leaked-key masking). Replace explicit-path/`--override-ini=addopts=` selection with marker-based `-m "not evaluation"`. Assert a minimum collected-test count so a mis-selected gate fails red, not green.
3. **Secret provisioning guardrail.** `provision-infra.sh` creates every secret cloudbuild references (empty placeholder if no value) so deploy never references a nonexistent secret. Delete deprecated `deploy.sh`.
4. **Type the internal tuple contracts** (`_llm_generate_map_answer -> tuple[str|None,str,list]`), de-dup `_reliability_risk_component` and `_compute_climate_risk_score` (duplicated in services.py + routes_main.py), turn mypy on for `api/map/`.
5. **Delete dead trees:** orphaned `database/migrations/`, the phantom ORM in `trust/models.py` (declares a CHAR Article that contradicts the real UUID table), unwired `rag_evidence_retriever.py`/`semantic_query_service.py`, dead `URLAnalysisDetail` dup in `api/models.py:371`.

### Wave 1 — Medium (days; before or just after release)
6. **CI/CD migration safety:** move Alembic/SQL migrations to a gated Cloud Run **Job** run before deploy with `--wait`; **delete `MIGRATIONS_TOLERATE_ERRORS=true` + every `|| true`**; `set -euo pipefail`; expand/contract migrations; `--no-traffic --tag candidate` → `curl -f $TAG/health` → shift traffic.
7. **Consolidate schema source of truth:** one migration dir, one tracker table; widen `articles.country_code` CHAR(2)→VARCHAR and funnel all writes through the single `_normalize_country_code` (kills the `XX`/`XX-AF` truncation corruption at the column level).
8. **Move GX10 off synchronous request paths:** query-embedding + `/semantic/explain` read precomputed-only with hard 2–3s timeout + immediate FTS fallback (today they `await` an unreachable GX10 at 60s/240s timeouts).
9. **Delete the `api/map_routes.py` callable re-export shim** (the patch-target footgun).
10. **Prompt caching** with deterministic stable-prefix layout + Ollama `format=<schema>` for GX10 enrichment.

### Wave 2 — Large (1–2 weeks; post-release unless we delay launch)
11. **Resolve the `api/`↔`src/backend` dual import root** (make `src/backend` an installable package, drop `PYTHONPATH` flattening). Highest-leverage structural fix — underlies the "fixes break elsewhere" complaint, the mypy duplicate-src, the models.py/models/ collision.
12. **Decompose `chat_routes.py`** (1408-line god-route); make prompt assembly return a structured object so tests assert on fields not positions; collapse the skills protocol to one source of truth.
13. **Semantic-layer anti-split-brain:** `tsvector` as a GENERATED STORED column; embeddings via trigger→outbox worker with `content_hash` skip + `model_version`/`is_current`; hybrid search via RRF. Backfill bge-m3 via GX10 so production search stops silently degrading to FTS.

---

## TRACK B — Product fixes (the reported issues)

### P0 — broken / dishonest / blocking
- **Login** — OAuth redirect URIs in Google Console (USER) + callback full-reload fix (shipping in Deploy 1).
- **url_analysis success card never renders** — GET returns flat, FE reads nested `response.article.*`. Fix shape (the contract gate prevents recurrence).
- **Climate Risk = article volume in disguise** (confirmed: score ≈ f(article_count)+1.2; top "risk" = highest-news countries pegged at 9.5). **Recompute Phase 1 from `country_projections` warming (already populated 193/200); Phase 2 blend ND-GAIN.** Rename, new 5-band hazard legend. Strip the false "ND-GAIN/IFRS S2" claim from the walkthrough NOW.
- **Temperature Anomaly broken** — instantaneous reading minus *same-month-last-year* mean (not a climatology); nulls render as 0/"normal" (France shows null→yellow). Fix: 1991–2020 monthly normal, month-to-date vs normal, **persist in a table + cron** (today it's in-memory per-instance only), null≠0 in FE.
- **Methodology page** — "Last audited 2026-06-14, 3.55/5" is **hardcoded JSX** (`methodology/page.tsx:285`), self-contradictory and **overstated** (real latest = ~3.0). Make it backend-driven; the number rises to 4+ only when the engine work earns it.

### P1
- **News Events** — fixed in Deploy 1 (interval bind).
- **NDC Targets + Adaptation Gap** — empty because `country_indicators` never populated; **blocked on ND-GAIN source URL 403** — needs a working download/mirror. Until then, self-gate the layers as "coverage pending N/200" instead of all-grey.
- **Map per-layer legends + interactions** — relabel "Article Density"→"News Attention"; honest legends; hover/click/drill per the per-layer table; per-tab coachmark walkthrough (driver.js) replacing the one lying modal.
- **Sources mostly "Not assessed"** (Editorial Standards / Fact-Check Record / Transparency) + **company-profile data gaps** — investigate why evaluations aren't populated (likely an unrun enrichment/scoring pass), then backfill.
- **Dark-theme chat** — dark text on dark background in headers.
- **Warming Outlook UX** — clearer horizon-toggle affordance + legend.

### P2
- **Docs consolidation:** one authoritative set (SKILL.md + a rewritten CURRENT_STATE + the latest audit + a RUNBOOK); demote the 4 conflicting "source of truth" docs; move CLAUDE.md's aspirational claude-flow body to `docs/archive/`; CI grep fails if >1 non-archive doc says "source of truth"; finish CliLens→Climatefacts rename.
- **Content usability + robust ingestion tests:** Pydantic v2 ingestion gate + quarantine/DLQ table + Pandera batch checks; LLM-quality evals tracked nightly, never in the deploy gate.

---

## Data backfills needed (unblock several P0/P1 at once)
- **ND-GAIN** (403 on `gain.nd.edu` CSV) → working source/mirror → unblocks Climate Risk Phase 2 + NDC + Adaptation Gap.
- **Source evaluations** (why "Not assessed") → re-run the scoring/enrichment pass.
- **bge-m3 embeddings** via GX10 → real semantic search.
- **Temperature normals** (1991–2020) → reliable anomaly layer.

## Recommended sequencing
Wave 0 guardrails + Track-B P0 product fixes **before** official release; Wave 1 +
P1 around launch; Wave 2 structural refactors immediately **after** launch (they're
high-value but destabilizing to rush pre-release).
