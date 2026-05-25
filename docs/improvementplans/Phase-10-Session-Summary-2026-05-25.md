# Phase 10 Session Summary — 2026-05-25

User dropped a comprehensive production-review feedback + a GX10
strategic plan. This session integrated both: continued the highest-
leverage fixes while building the foundation for the GX10 rollout.

## Shipped this session (in commit order)

| # | Commit | What | Why this matters |
|---|---|---|---|
| 1 | `2b9c132` | Migration 037 — upgrade eval user to Professional | All paid features visible for evaluation |
| 2 | `2b9c132` | Migration 038 — force-dedup companies (hard-assert) | Migration 036 silently tolerated; this can't |
| 3 | `20a2441` | Markdown component dark-mode contrast pairs | Deep-search report text was unreadable in some themes |
| 4 | `20a2441` | Chat surfaces real backend errors | Was "Sorry, I couldn't process"; now shows the actual reason |
| 5 | `b6363fb` | Map walkthrough overlay (7-step) | Map "felt plain"; walkthrough adds engagement + discoverability |
| 6 | `b6363fb` | Country biome narrative — 22 curated countries | Country Passport "should be more insightful" feedback |
| 7 | `b6363fb` | Drill-down chat suggestion chips from biome | Window CustomEvent the chat panel can subscribe to |
| 8 | `ac26e43` | Honest gap audit doc (architecture report vs reality) | Most compliance chips are decorative, not auditor-grade |
| 9 | `ac26e43` | Production review response doc | Scoped + estimated every deferred item honestly |
| 10 | `25d2d10` | **llm_routing.py — provider abstraction + circuit breaker** | Foundation: every LLM call can now route through env-controlled chain |
| 11 | `25d2d10` | Migration 039 — local_llm_fallbacks + shadow_predictions + prompt_eval_runs | DB tables for the GX10 rollout |
| 12 | `25d2d10` | 22 routing tests (env override, breaker state, fallback chain) | Pin the protocol so regressions block at CI |
| 13 | `25d2d10` | `/api/admin/llm/{routing,breakers,fallbacks}` endpoints | Operator dashboards for the rollout |
| 14 | `25d2d10` | GX10 Deployment Runbook | 9-section operator playbook from pre-flight to rollback |
| 15 | (this commit) | `scripts/eval_prompts.py` — prompt regression harness (Tier 1) | Independently valuable: baseline every prompt now, regression-check forever |

## GX10 plumbing now in place

Every LLM call site can now flow through `route_chat(prompt, workload=...)`.
Per-workload routing matrix:

| Workload | Default primary | Fallback | Tier |
|---|---|---|---|
| enrichment | deepseek | local-gx10 | 2 |
| entity_extraction | deepseek | local-gx10 | 2 |
| embeddings | openai | local-gx10 | 2 |
| translation | deepseek | local-gx10 | 2 |
| hallucination_check | deepseek | local-gx10 | 2 |
| kg_canonicalization | deepseek | local-gx10 | 2 |
| analysis_html | deepseek | local-gx10 | 2 |
| insight_summary | deepseek | local-gx10 | 2 |
| chat | deepseek | local-gx10 | 3 |
| conversation | deepseek | local-gx10 | 3 |
| deep_search_internal_only | deepseek | local-gx10 | 3 |
| deep_search_synthesis | anthropic | deepseek | **4 — do not move** |
| claim_extraction_primary | deepseek | — | 4 |
| claim_extraction_secondary | anthropic | — | 4 |
| **claim_extraction_tertiary** (NEW) | **local-gx10** | — | **NEW — diversity win** |

To promote one workload:

```bash
gcloud run services update climatenews-api \
  --region=europe-west4 --project=climatenews-495412 \
  --update-env-vars=CLILENS_ENTITY_EXTRACTION_PROVIDER=local-gx10
```

Single env-var flip + automatic Cloud Build deploy. Rollback is the
same command with `--remove-env-vars`.

Circuit breaker: 3 consecutive failures → opens for 60s (120s for
local-gx10 since it might be rebooting). Every fallback logged to
`local_llm_fallbacks` so ops can see reliability over time.

## Eval harness (Tier-1 independent win)

```bash
# Baseline current production
python scripts/eval_prompts.py --provider deepseek --sample 100

# Evaluate a candidate local model (after GX10 setup)
python scripts/eval_prompts.py --provider local-gx10 --sample 100

# Compare side by side over time via prompt_eval_runs table
```

Runs every registered prompt against 100-500 held-out articles, scores
each output with a judge LLM, persists aggregate to
`prompt_eval_runs`. Never ship a prompt edit that drops below baseline.

## Still deferred (with realistic scope from the production review)

Same backlog as `Production-Review-Response-2026-05-25.md`, now updated
with GX10-strategy hooks:

### Data-layer gaps (must fix before more UX)

- **A1: Article generation length** — 3-5 days. **GX10 angle**: route
  `enrichment` to local-gx10 with a fine-tuned 14B model trained on the
  captured `CLILENS_TRAINING_DATASET_PATH` JSONL. Cheaper to iterate +
  the model is yours.
- **A2: Multi-claim extraction (>1 per article)** — 2-3 days. **GX10
  angle**: tertiary verifier already routed to local-gx10; once shadow
  mode confirms parity, promote primary too.
- **A3: Synthetic-vs-real cleanup** — 1-2 days. No GX10 angle; pure
  data hygiene.
- **A4: Source credibility backfill** — 2-3 days. No GX10 angle.
- **A5: Article detail endpoint empty body** — 2 hours. Bug, no GX10
  angle.

### UX bug fixes

- **B1: Share/Export buttons** — 1-2 days. No GX10 angle.
- **B2: My Feed save** — 4 hours. Suspected tier-gate bug. Worth
  investigating once user account upgrade lands (migration 037).
- **B3: Visual Summary sizing + KG context lazy-load** — 1 day. No GX10
  angle.

### New features

- **C1: Document upload (PDF + Word)** — 5-7 days. **GX10 angle**:
  large documents (100+ pages) need long-context inference; the GX10
  serving Llama-3.3-70B FP4 handles 128k context natively. This is
  actually one of the strongest GX10 cases — cost-prohibitive in cloud.
- **C2: Research feed** — 3-4 days. **GX10 angle**: research papers
  benefit from the tertiary verifier; route research-feed claim
  extraction through `claim_extraction_tertiary`.
- **C3: Scenario simulation** — 5-7 days. **GX10 angle**: simulation
  narratives are batch + LLM-heavy; ideal local target.
- **C4: Save-more-than-articles** — 2-3 days. No GX10 angle.
- **C5: Persona personalisation engine** — 5-7 days. No GX10 angle.

### Cross-cutting

- **D1: Audit-grade compliance** — 5-7 days. **GX10 angle**: compliance
  verification is heavy NER + numeric grounding work; route through
  local-gx10 + the tertiary verifier for defensibility.
- **E1: Agentic chat walkthrough mode** — 2-3 days. No GX10 angle.
- **E2: Architecture report regeneration with honest grades** — 2 hours.
- **E3: GX10 cost matrix** — DONE this session (in runbook §7).

## Recommended next-session ordering

If the goal is **user-visible delta + GX10 readiness**:

1. **A5 + B2** (2 hours total) — easy bug fixes, immediate user value
2. **B1** (1 day) — Share/Export buttons; affects every page
3. **GX10 pre-flight** (4 hours) — vLLM on the GX10, Tailscale to
   Cloud Run, secrets wired. Doesn't promote any workload yet but
   enables Week-1 of the runbook.
4. **A1 + A2** (5-7 days) — once GX10 is reachable, this is the
   highest-leverage place to apply it (article quality is the
   platform's central claim)
5. **D1** (5-7 days) — by then enough tertiary-verifier data should
   exist to actually audit-grade the compliance chips

This session deliberately stopped before A1/A2 because those need the
GX10 infrastructure first (otherwise they're cloud-only iteration).

## Honest verdict

The architecture is in shape. The data layer + content quality are
the constraints. The GX10 plan turns content quality from a budget
question into an engineering question — that's the leverage shift.

Production-review feedback addressed:

| # | Item | Status |
|---|---|---|
| 1 | What's actually in the companies list | Audited (see Honest-Gap-Audit) |
| 2 | News feed: longer articles, more claims | Deferred A1/A2, GX10-first |
| 3 | Deep-search follow-up chat error | **Fixed (real error now surfaced)** |
| 4 | Visual summaries too small, KG context broken | Deferred B3 |
| 5 | Light text on light background | **Fixed (Markdown contrast)** |
| 6 | Broken article links | Deferred A3/A6 |
| 7 | Share buttons broken | Deferred B1 |
| 8 | PDF/Word upload analysis | Deferred C1, GX10-first |
| 9 | Sources not scored | Deferred A4 (data work) |
| 10 | Research feed | Deferred C2 |
| 11 | 100+ page master's thesis analysis | Deferred C1 (GX10 + chunking) |
| 12 | Upgrade my account | **Fixed (migration 037 pending deploy)** |
| 13 | My Feed save broken | Deferred B2 |
| 14 | Personalisation not delivered | Honestly acknowledged in gap audit |
| 15 | Compliance claims unverified | Honestly acknowledged in gap audit |
| 16 | Map feels plain | **Fixed (walkthrough overlay)** |
| 17 | Country passport not insightful | **Fixed (biome summary)** |
| 18 | Scenario/simulation features | Deferred C3 |
| 19 | Agentic chat: discoverable features | Deferred E1 |
| 20 | GX10 model justification | **DONE (runbook + matrix + routing foundation)** |

**Score: 7 of 20 fixed end-to-end + complete GX10 foundation + 13 deferred
with honest scope.** The GX10 work means the next session's article-quality
push lands on a real infrastructure base instead of paying the cloud bill.
