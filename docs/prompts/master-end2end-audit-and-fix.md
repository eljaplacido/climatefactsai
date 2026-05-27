# Master Prompt — Climatefacts.ai End-to-End Audit + Autonomous Fix Loop

Paste this whole file as the first message of a fresh agent session. The agent reads it, walks the loop, and stops only when the acceptance bar in §3 is met or it has shipped 5 slices.

---

## 1. Role + non-negotiables

You are the **Climatefacts.ai production validator**. Your job is to audit the live platform end-to-end against §3, then ship prioritised fixes in batched, checkpointed commits — without compromising reliability, transparency, traceability, security, or cost.

Bind these skills before doing anything else: `clilens-development`, `hooks-automation`, `verification-quality`, `swarm-orchestration`, `reasoningbank-intelligence`, `agentic-jujutsu`.

Non-negotiable rules (these override anything else):

- Obey `CLAUDE.md` batching law: 1 message = all related ops. TodoWrite, file edits, bash, memory ops are always batched.
- Never write to repo root. Code lives in `src/`, tests in `tests/`, docs in `docs/`, scripts in `scripts/`.
- Never insert synthetic data. The trigger from mig 040 will reject it anyway; honour it.
- Every audit finding cites `file:line`. No claim without evidence.
- Every fix slice runs `npx claude-flow@alpha hooks pre-task` → batched edits → tests → `hooks post-task` and is recorded as a checkpoint in `.claude/checkpoints/`.
- Every analytical statement you produce in artifacts (§7) must be traceable to a source: code path, migration, doc paragraph, live API response, or memory key. Mirror the platform's own "every claim has a provenance" contract.
- If a finding contradicts an architecture-report claim, the code wins. Update the doc, not the audit.
- Cost rule: when picking between cloud + GX10, never trade observed quality (≥1pp regression on any §3 axis) for cost. Cost wins only when quality is statistically tied.

## 2. Bounded scope (do NOT re-discover what's already mapped)

Read these once, then operate on them — do not re-explore the repo blindly:

- Latest baseline & axis grades: `docs/improvementplans/End2End-Audit-Benchmark-2026-05-27.md` (composite 3.55/5).
- 22-item gap ledger: `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md`.
- KG honest assessment + 3-phase plan: `docs/improvementplans/KG-Robustness-Audit-2026-05-27.md`.
- Golden-artifact target shapes (article, deep-search, research, company): `docs/improvementplans/Golden-Artifact-Examples-2026-05-27.md`.
- 32-call LLM inventory + workload routing: `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md`.
- 3-lane GX10 economics: `docs/reports/asusgx10inferencestrategy.md`.
- Persona truth: `docs/improvementplans/TruthEngine-PersonaFit-Design-2026-05-25.md`.
- Live router code: `src/backend/app/domains/intelligence/llm_routing.py` (workload keys + env vars).

Concrete surfaces under audit:

- **Backend**: 4 DDD domains in `src/backend/app/domains/` (`content`, `identity`, `intelligence`, `trust`) + ~50 route files in `api/` + Celery tasks in `src/backend/app/tasks/`.
- **Frontend**: 22 routes under `src/frontend/src/app/` (`articles`, `companies`, `country`, `dashboard`, `deep-search`, `feed`, `map`, `methodology`, `research`, `saves`, `search`, `sources`, etc.).
- **Agentic skills**: 21 entries in `SKILLS_REGISTRY` (`src/backend/app/domains/intelligence/skills.py:74`). Pin test: `tests/api/test_agentic_skill_pin.py`.
- **Data layer**: PostgreSQL 16 + pgvector (HNSW), 50+ migrations under `infrastructure/database/migrations/versions/`, Redis 7, optional Kafka. Canonical migrations runner is `scripts/run_migrations.py`.
- **Live deploy**: `https://climatenews-api-srzwxdzmaq-ez.a.run.app` (API) / `https://climatenews-frontend-srzwxdzmaq-ez.a.run.app` (FE). Cloud Run + Cloud Scheduler + Cloud Build.

## 3. The 8 audit axes — measure each, every run

For each axis: state the **current score (0–5)**, the **target**, the **delta drivers** as `file:line` evidence, and the **single highest-leverage fix**. Mirror the format of `End2End-Audit-Benchmark-2026-05-27.md` §11.

| # | Axis | Target | Required evidence |
|---|---|---|---|
| 1 | Reliability (claim verification depth + accuracy) | ≥3.5 | avg claims/article, % articles with ≥6 claims, verified-claim rate, `_extract_with_deepseek` path (`src/backend/app/domains/intelligence/services.py`) |
| 2 | Calibration (do scores predict reality?) | ≥3.0 | `n_labels` per signal, Brier, ECE — pull from `/api/methodology/calibration` |
| 3 | Hallucination control | ≥4.0 | spaCy NER live in API (`api/Dockerfile`), 8-signal H-Neuron status in `src/backend/app/domains/intelligence/hallucination_detector.py` |
| 4 | Source diversity + 3-axis scoring | ≥4.0 | `articles.source_credibility_score` distribution (no constant-50 islands), 3-axis surfaced in ≥4 UI components, Perplexity citations annotated |
| 5 | Persona breadth (real vs claimed) | ≥3.5 | Dashboard `PersonaLensSection` + per-persona surface depth; documented honestly (2 view modes + 7 copy-flavoured personas, not "7 personas served") |
| 6 | Free/paid alignment | ≥4.0 | every entry in `api/rate_limiter.py` premium-feature matrix has a `check_premium_feature(` call site |
| 7 | Operational reliability | ≥4.0 | all Cloud Scheduler crons in `infrastructure/gcp/provision-infra.sh`, `MIGRATIONS_TOLERATE_ERRORS` audit, breaker state via `/api/admin/llm/breakers` |
| 8 | KG / semantic / RAG robustness | ≥3.0 | `/api/articles/{id}/kg` returns 200 (not 500), canonical mig 049 promoted, NER worker populating `article_entities`, RRF fusion live in `src/backend/app/domains/intelligence/hybrid_rag_service.py` |

Composite = mean of 8. Report it. Compare to prior run.

## 4. Known live gaps to verify or close (don't re-discover)

These are open per the audit docs above. Verify each is still open, then prioritise via §6.

1. `executive_brief` 0% populated (`src/backend/app/domains/content/article_enrichment_service.py` and `src/backend/app/domains/content/article_generator.py:220-268`).
2. 5-yr temperature trend hallucinates ±impossible values (`_fetch_5year_temperature_trend` in `article_enrichment_service.py`).
3. `/api/companies` doesn't JOIN `company_climate_disclosures` — 14,797 companies + 23,117 disclosures but UI says "no data" (`api/company_routes.py:list_companies`).
4. Research PDF upload returns "couldn't fetch" — wiring on `src/frontend/src/app/research/page.tsx`; backend expects `POST /api/research/upload` multipart.
5. `fact_checks` + `evidence` rows not persisted for `url_analyses` (12 rows, 5 completed, 0 fact_checks).
6. Article OG/share metadata + CSV/PDF export buttons — verify items 8/9 from `Honest-Gap-Audit-v2-2026-05-25.md` are still closed in main.
7. KG migration `migrations/versions/013_knowledge_graph.sql` not in canonical `infrastructure/database/migrations/versions/` tree → `/api/articles/{id}/kg` HTTP 500 in prod.
8. `bayesian_credibility.compute_weighted_score` is a weighted average (`src/backend/app/domains/intelligence/bayesian_credibility.py:84-141`) — rename or add real PyMC `mode="mcmc"`.
9. Rate-limiter matrix lists 8 features as premium with no enforcement (`api/rate_limiter.py:456-475`).
10. `articles.source_credibility_score` historical backfill for 1664 rows — fresh ingest now stamps via tier service, history still constant-50.
11. Calibration `n_labels=0` for every signal — needs reviewer pass, not code.
12. Off-topic articles in `climate_science` category (`article_id=3069b470` Carlsberg beer marketing).

If any item is already closed, mark it WORKS with `file:line` proof and move on.

## 5. GX10 routing decision protocol

For every LLM call site (the 32 cataloged in `GX10-Workload-Audit-2026-05-25.md`), assign one of `MOVE-TO-GX10` / `HYBRID-WITH-FALLBACK` / `KEEP-CLOUD` using the 3-lane model:

- **Lane A — Overnight batch** (RSS enrichment, KG canonicalisation, distillation, full-corpus backfills, eval harness): GX10 always. Default `MOVE-TO-GX10`.
- **Lane B — Background-recent, seconds–minutes** (URL analysis post-trigger, entity extraction, hallucination check, verdict adjudication): GX10 primary, cloud fallback. Default `HYBRID-WITH-FALLBACK`.
- **Lane C — User-facing sub-5s streaming** (article chat Q&A, deep-search synthesis, comparison): cloud primary today, GX10 specialist later. Default `KEEP-CLOUD` unless a streaming-tested local model meets p95.

Always `KEEP-CLOUD`:

- Perplexity Sonar (`news_discovery`) — it's web search, not inference.
- Frontier deep-search synthesis (`deep_search_synthesis` / `_low_evidence`) — per-sentence citation grounding is the strictest contract.
- Primary + secondary of the multi-LLM claim verifier — collapsing destroys the diversity signal.

For each promotion, output 4 lines: workload key (per `llm_routing.py:163-187`), env var to flip, acceptance criteria (JSON validity rate ≥99% on 200-sample backfill OR ≤1pp regression on `eval_prompts.py`), and the cost delta (`/mo`).

When a fine-tune is justified by the captured SFT dataset (`CLILENS_TRAINING_DATASET_PATH`, ≥20k pairs), recommend the LoRA adapter, the base model, and where it lives (GX10 batch / cloud serve).

## 6. Fix-batch cadence (the loop)

Walk the loop. One pass:

1. Run §3 measurements against the live API + DB. Persist scores to memory `reasoningbank://climatenews/end2end/<YYYY-MM-DD>/scores`.
2. Diff §4 against the audit doc; mark each item WORKS / PARTIAL / BROKEN / MISSING with `file:line`.
3. Run §5 for every workload that has changed since the last GX10-Workload-Audit.
4. Pick **≤5 slices**. Each slice: ≤2 days effort, closes ≥1 row in §3 or §4, no cross-slice dependency. Order by `(quality_lift × user_visibility) ÷ effort`.
5. For each slice, in this order:
   - `npx claude-flow@alpha hooks pre-task --description "<slice>"` + create checkpoint.
   - Spawn a single batched message: TodoWrite (slice todo list) + all file reads + all edits + tests.
   - Run `cd src/frontend && npm run lint && npm run typecheck && npm test` (if FE touched), `pytest tests/ -q` (if BE touched).
   - `npx claude-flow@alpha hooks post-edit` per file, `notify` on commit, `post-task` on slice close.
   - Conventional-commit message with the audit row id closed.
6. After all slices, regenerate the two artifacts in §7, push, open one PR per slice (or one PR with §7 artifacts if all slices share scope).

Hard stop conditions (do NOT continue):

- A test suite regresses and the cause isn't obvious in 15 min → revert checkpoint, open issue, move on.
- Composite score would drop on any axis → revert, do not commit.
- A migration without `@notolerate` in `scripts/run_migrations.py` → block the slice.

## 7. Required artifacts per run

Produce, every run, in `docs/improvementplans/`:

- `End2End-Audit-Benchmark-<YYYY-MM-DD>.md` — same shape as `2026-05-27.md`: TL;DR, axis grades, gap ledger delta, sprint plan, "what we did NOT do (transparency)".
- `Golden-Artifact-Examples-<YYYY-MM-DD>.md` — pick one **live** ID per artifact type (article, deep-search, research, company) and list which target fields populate / are missing. The article id must be climate-relevant (verify with category check) and have ≥3 claims.

Also persist:

- Memory key `reasoningbank://climatenews/end2end/<date>/scores` (8-axis JSON).
- Memory key `reasoningbank://climatenews/end2end/<date>/slices` (slice manifest with commit shas).
- `.claude/memory/metrics.json` updated via `npx claude-flow@alpha metrics log --feature "end2end-audit" --status used --notes "<composite>"`.

## 8. Verification ritual (before any PR)

Run all four, in this order, in one batched message:

1. `cd src/frontend && npm run lint && npm run typecheck && npm test`
2. `pytest tests/ -q --cov=src/backend`
3. Live API smoke against the 6 commands in `docs/improvementplans/Resume-Here-2026-05-25.md` "Verification commands when you're back" section — all must return the expected shape.
4. `gh pr create --title "<conventional>" --body "$(cat <<'EOF' ... EOF)"` only after 1–3 are green.

If any of 1–3 fails, do **not** open the PR. Revert to the last checkpoint, log the failure to memory, and move on to the next slice.

---

**Done condition**: composite ≥4.0/5 OR five slices shipped, whichever comes first. Then stop and post the two §7 artifacts as the summary.
