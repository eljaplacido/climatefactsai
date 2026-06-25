# Production-Readiness Audit — 2026-06-26

_Method: 10-dimension multi-agent audit (36 agents, ~2.4M tokens) with adversarial
verification of every P0/P1 finding. 76 findings, 17 verified blockers. This
session fixed 13 of the 17 blockers + a latent deep-search 500, applied the
Headroom context-compression patterns, and committed in 4 waves
(`b58657f`, `b4ba682`, `1d96531`, + this doc)._

> Canonical doc note (addresses DOC-01): three docs previously each claimed
> "source of truth" and disagreed. The authoritative current snapshot is THIS
> report + `docs/hermes/blueprint.md` (header). `docs/CURRENT_STATE.md` and the
> 2026-06-09 data-layer audit are historical.

## Health scores (0–5, post-verification)

| Dimension | Score | Headline |
|---|---|---|
| api-routes | 2.5 | unauth LLM-cost endpoints, premium-gate + saved-search crashes (FIXED) |
| tests | 2.5 | CI deploy-gate crashed before running a test (FIXED); Stripe webhook untested |
| docs-markdown | 2.5 | 3 contradictory "source of truth" docs; pre-rebrand "CliLens" in 21 docs |
| content-ingestion | 3.0 | RSS no-date drop (FIXED); wrong-key enrichment/attribution |
| trust-verification | 3.0 | SQLi (FIXED); reliability-scorer split-brain (deferred) |
| devops-prod | 3.0 | xdist crash (FIXED); alerts notify nobody (deferred) |
| data-semantic | 3.2 | multilingual FTS regression (deferred); dead KG entity-resolution |
| intelligence-rag | 3.5 | split-brain LLM routing; CacheAligner waste (FIXED); provenance honesty (FIXED) |
| frontend | 3.5 | un-embeddable widget (FIXED); fake GDPR success (FIXED); half-built dark mode |
| skills-agents | 3.5 | claude-flow infra (ReasoningBank/AgentDB/OpenRouter) is aspirational, not wired |

Composite ≈ **3.0 / 5** — substantial, real platform; the blocker set is
auth/cost/correctness, not architecture.

## Verified blockers & disposition

### Fixed this session
| ID | Sev | Issue | Fix |
|---|---|---|---|
| TRUST-01 | P0 | SQL injection — LLM `claim_type`/`verdict` interpolated unescaped | Parametrized all verify-pipeline SQL |
| TRUST-02 | P0 | `/verify`, `/full-analysis` unauthenticated/unmetered LLM sinks | QuotaService gating |
| API-01 | P0 | `/api/articles/ingest` unauth SSRF + corpus pollution | `require_admin` + `_validate_safe_url` |
| TEST-001 / DEVOPS-01 | P0 | CI gate crashed: `-n auto` w/o pytest-xdist | Added `pytest-xdist` |
| API-02 | P1 | premium gate read `["tier"]` (nonexistent) → 403 all paying users | Use `subscription_tier` |
| API-03 | P1 | saved-search did attr-access on a dict → 500 | Dict access |
| API-04 | P1 | admin pipeline endpoints gated by "is logged in" only | `require_admin` (fail-closed allowlist) |
| API-05 | P1 | custom-RSS validation no SSRF guard | `_validate_safe_url` before feedparser |
| CNT-2 | P1 | RSS entries w/o pubDate bound `""` to timestamptz → dropped | Emit `None` |
| FE-01 | P1 | global `frame-ancestors 'none'` made `/embed/*` un-embeddable | Scope strict policy off `/embed` |
| FE-02 | P1 | Delete/Export buttons hit 404 → fake success (GDPR) | Real `/export-data` + `/account` endpoints |
| FE-03 | P1 | `/admin` page no guard | Client guard + JWT on calls (backend is the real boundary) |
| INT-03 | P1 | advertised multi-LLM verify is gated OFF in prod | Honest copy (kept single-LLM, no new cost) |
| INT-02 | P1→P2 | deep-search provenance reported model by key-presence + ada-002 | Report actual model + bge-m3 |
| (found in test) | P1 | deep-search `structured` UnboundLocalError 500 on thin-evidence | Initialize before branch |

### Deferred (tracked follow-ups)
| ID | Sev | Why deferred |
|---|---|---|
| TRUST-03 | P1 | Reliability split-brain — live pipeline bypasses `ReliabilityScorer`; needs formula consolidation + reverify of corpus. Medium risk. |
| SEM-01 | P1 | Multilingual FTS regression across ~9 files hardcoding `to_tsvector('english', …)`; should switch all to the `search_tsv` generated column. Broad, test-heavy. |
| TEST-002 | P1 | Stripe webhook (money + signature path) has zero tests — add behavioral coverage before relying on billing. |
| DEVOPS-03 | P1 | Cloud Monitoring alerts use `--no-notification-channel` and live in a manual script — needs GCP infra (notification channel + pipeline step), not code. |

## Headroom application (token / context efficiency)

Implemented natively (no `headroom-ai` dependency, no proxy) in
`src/backend/app/domains/intelligence/context_compaction.py`:

- **CacheAligner (INT-05)** — chat now builds a *static* system prefix (identity +
  capabilities + the ~2 KB 24-skill action catalogue) via cached
  `_chat_system_prompt()`; all volatile content moved to the user message. The
  catalogue previously sat at the *end* of the user prompt, defeating any
  prompt-prefix cache and re-tokenizing every turn.
- **IntelligentContext** — `_build_multi_article_context` budget-fits article
  sections (most credible first) instead of fixed char caps.
- **SmartCrusher / guard_input** — structural JSON shrink + a whole-prompt
  middle-trim ceiling at the `llm_chat_with_fallback` chokepoint.
- **Tool-output compaction** — deep-search compacts the verbatim Perplexity
  payload (~1.5 K tokens) before synthesis.

33 unit tests (module + a CacheAligner-invariant regression guard).

## Required deploy actions
- **Set `CLILENS_ADMIN_EMAILS`** (comma-separated). It is **fail-closed**: until
  set, every admin endpoint (`/api/admin/trigger-workflow`, `/workflows`,
  `/api/articles/ingest`) returns 403 by design.
- `pytest-xdist` is now in `requirements.txt` + the Cloud Build install line —
  the deploy test-gate runs again. NOTE: it now correctly *fails red* on real
  test failures (e.g. tests requiring network/keys) — keep the suite green.
- Optional Headroom tuning: `CLILENS_CHAT_CONTEXT_TOKENS` (default 1100),
  `CLILENS_MAX_LLM_INPUT_TOKENS` (default 14000).

## Top remaining backlog (P2, not blockers)
INT-01 split-brain LLM routing (chat/deep-search bypass the circuit-breaker
router) · CNT-3/4/5 ingestion wrong-key attribution + dead ada-002 embed write ·
SEM-02 dead KG entity-resolution · TEST-004 Playwright never fails the build ·
DOC-02..07 doc drift + "CliLens" rename · AGSK-01 aspirational agentic infra in
CLAUDE.md/skills. Full per-finding detail in the audit run transcript.
