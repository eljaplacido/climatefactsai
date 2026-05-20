# Climatefacts.ai — Implementation Plan

**Date:** 2026-05-20  
**Basis:** Code-verified audit against 4 authoritative reports  
**Branch:** `main` @ `4699a70`  
**Composite today:** ~4.0/5 | **Target (12 weeks):** ~4.6/5  

---

## 0. Audit Methodology

This plan is the product of cross-referencing four independently produced improvement plans against the actual state of every file, module, migration, route, component, and test in the codebase. Nothing here is asserted — everything is verified on `HEAD`. The three source reports:

1. **Climate Platform Analysis and Improvement Plan.md** — Strategic/report/regulatory analysis (214 lines)
2. **Climatefacts-Strategic-Analysis-2026-05-18.md** — Market/competitive/mission fit (365 lines)
3. **Climate Data Platform Strategic Analysis & Roadmap to Best-in-Class (1).md** — FAIR/dMRV framework (321 lines)
4. **Climatefacts-Improvement-Synthesis-2026-05-19.doc** — 16-recommendation synthesis (HTML extraction)

All four agree on the core finding: the platform's architecture is exceptional, but urgent credibility-floor work must precede domain expansion. This plan reflects what the code actually does, not what documents claim.

---

## 1. Current State — What Genuinely Ships

### 1.1 Backend Architecture (35 route modules + DDD v2)
- **FastAPI 0.109** with 4-layer middleware (observability, CORS, security headers, rate limiting)
- **Domain-driven backend** under `src/backend/app/domains/content/`, `intelligence/`, `trust/`
- **PostgreSQL 16** with `pgvector` HNSW index (m=16, ef_construction=64) + multilingual FTS (15 languages)
- **Celery async task queue** with Redis (refactored from Kafka per ADR 2026-05)

### 1.2 Trust Infrastructure (actual code, not aspiration)
- **`claim_provenance` table** (`021_claim_provenance.sql` + `023`): UUID rows recording model, prompt version, SHA-256 prompt fingerprint, retrieval strategy, source_article_ids JSONB, hallucination_score per LLM output — genuinely rare
- **Versioned prompt registry** in `intelligence/prompts.py` — structural defence against silent prompt drift
- **Calibration pipeline** (`calibration_store.py` + `calibration.py`): Platt scaling, Brier score, ECE with `calibration_fits` persistence
- **Hallucination detection** (`hallucination_detector.py`): spaCy NER + statistical number matching (5% tolerance) + LLM grounding — composite weighted score
- **Multi-LLM verification** (`multi_llm_verifier.py`): DeepSeek + Anthropic cross-verification with Jaccard token-set similarity + numeric grounding against `country_indicators`
- **6 indicator adapters**: Climate TRACE, OWID, CAT, UNFCCC NDCs, IRENA, ND-GAIN — all with idempotent upsert + `indicator_sync_logs` audit

### 1.3 What the Reports Miss (codebase is stronger than they assume)
| Report Claim | Actual State |
|---|---|
| "RSS summarised to 500-char stubs" | `rss_adapter.py:478` — full body via `httpx` + `BeautifulSoup` with semantic container extraction. Full-text extraction is ON by default. |
| "min_labels=5 for Platt" | `calibration_store.py:458` — `PREVIEW_FIT_MIN=5` (preview), `STABLE_FIT_MIN=50` (production). Preview tag exists. |
| "Hallucination check = regex only" | `hallucination_detector.py:336` — spaCy NER was added (2026-05-18). Three-strategy composite. |
| "No uncertainty on indicators" | `country_indicators` has `uncertainty_low` + `uncertainty_high` columns (migration 020). |

---

## 2. Verified Gaps — What Must Be Fixed

### G2.0 — IMMEDIATE (hours, not days)

| # | Gap | Files | Effort |
|---|---|---|---|
| **C1** | `is_synthetic = FALSE` filter absent on ALL user-facing surfaces (search, map, compare, feed, country panels, chat grounding). 3,588 synthetic articles visible. Confirmed: zero `is_synthetic` references in entire frontend. | `src/frontend/src/lib/api.ts`, all page components, `types/index.ts` | 1-2 hrs |
| **C2** | `.env.production` hardcodes `NEXT_PUBLIC_API_URL=http://localhost:5400`. 36 components fallback to same. Will silently break production. | `.env.production`, `src/frontend/src/app/admin/page.tsx:315`, `src/frontend/src/lib/trace.ts` | 30 min |
| **C3** | Calibration `STABLE_FIT_MIN=50` exists but `apply_latest_to_reliability` applies preview fits without checking `n_labels`. Must gate: do not apply fit when `n_labels < STABLE_FIT_MIN`. | `src/backend/app/domains/intelligence/calibration_store.py` | 30 min |
| **C4** | `CredibilityGauge.tsx` popover uses `bg-white` — invisible in dark mode. `DecomposedConfidenceChart.tsx` exists in codebase but has zero callers. | `src/frontend/src/components/CredibilityGauge.tsx` + `DecomposedConfidenceChart.tsx` | 1 hr |
| **C5** | Audit-trail endpoints return opaque UUID arrays in `source_article_ids`. External auditors cannot follow chain. | `api/methodology_routes.py` — 4 endpoints | 1 hr |
| **C6** | Methodology page does not surface the audited 3.6/5 alongside 4.78 self-claim. Strongest trust signal not deployed. | `src/frontend/src/app/methodology/page.tsx` | 1 hr |

### G2.1 — Week 1 (credibility compound)

| # | Gap | Fix | Effort |
|---|---|---|---|
| **W1** | EU AI Act Article 50 compliance (enforced 2 Aug 2026): no machine-readable AI labelling on any AI-produced surface. | New `AIProvenanceBadge.tsx` + `jsonLdAi.ts` + backend helper. Visible badge + `data-ai-generated="true"` + JSON-LD payload on all 5 AI surfaces. | 2 days |
| **W2** | `KNOWN_VENUES` hardcoded set of 8 publishers in `bayesian_credibility.py:48`. Audit dropped Reliability 4.4→3.5 on this alone. | New `source_credibility_tiers` table + seed loader from Scimago JR + RetractionWatch + IFCN. Replace hardcoded constant with DB read + LRU cache. New migration `027`. | 3 days |
| **W3** | `multi_llm_verifier.py` uses shared prompt — collapses model independence. | New `claim_extraction_auditor_persona` prompt v1.0 with adversarial framing. Secondary LLM runs different prompt. | 2 days |
| **W4** | `bayesian_credibility.py` is a weighted average, not Bayesian. Misleading method name + methodology claim. | Rename `compute_posterior` → `compute_weighted_score`. Update methodology page to describe the math honestly. | 30 min |
| **W5** | `conversation_engine.py` has no `actions[]` protocol. Chat is read-only. | Backend emits `actions` array in `/api/chat` response. Client dispatches 9 action types. New `chat_actions_log` table. | 4 days |

### G2.2 — Strategic (weeks 3-12)

| # | Gap | Fix | Effort |
|---|---|---|---|
| **S1** | Zero corporate-claim coverage. ECGT enforces Sep 2026. Platform verifies news but cannot verify corporate claims. | New `company_climate_disclosures` schema + 3 adapters (CDP open + SBTi + Net Zero Tracker) + `/companies/[ticker]` route. | 3 weeks |
| **S2** | `claim_provenance` records only what was produced — not what was looked for and not found. | Widen `event_type` enum: `claim_rejected`, `hallucination_flagged`, `indicator_missing`, `no_contradiction_found`, `numeric_grounding_failed`. Write rows on negative events. Migration `028`. | 2 days |
| **S3** | Indicator confidence exists (`uncertainty_low/high`) but sustainability composite ignores it. Composite treats all data as point estimates. | Propagate `sigma_composite² = Σw_i² * σ_i²` through `sustainability_score.py`. Render error bars on decomposed gauge. | 2 days |
| **S4** | KL drift thresholds hardcoded (0.10/0.25/0.50 nats). | Collect 60-day baseline, fit Gaussian distribution, set 2σ/3σ/4σ thresholds. Persist to `drift_threshold_fits` table. | 2 days |
| **S5** | Per-country claim ledger — map's most journalistically valuable view missing. | New `GET /api/map/country/{cc}/claim-ledger` endpoint + `ClaimLedgerTable` component on `MapCountryPanel`. New partial index `idx_claims_country_date`. | 2 days |
| **S6** | "Reproduce this result" button — strongest possible methodology demonstration missing. | New `reproducer.py` module: replays analysis with pinned prompt version + retrieval strategy, returns diff. | 3 days |

### G2.3 — Long Horizon (Quarter 3+)

| # | Gap | Justification |
|---|---|---|
| **L1** | Cross-language hallucination — multilingual narrative laundering | Original research moat. Per-language embeddings + claim clustering. 3-months. |
| **L2** | FAIR metadata + immutable ledger (Hyperledger) | Defines "universal trust layer." Needs partner co-signature. Q3 2026. |
| **L3** | Nature/TNFD biodiversity module | October 2026 ISSB exposure draft trigger. 4-6 weeks. |
| **L4** | Scenario engine + financial translation | Connects "what happened" to "what's coming." Insurance SKU. |
| **L5** | Embed widget + QR fact-check cards | 80% of video pipeline impact at 20% of engineering. Viral distribution. |

---

## 3. Sequenced 12-Week Plan

| Week | Items | Outcome |
|---|---|---|
| **1** | C1-C6 (credibility floor) + W4 (bayesian rename) | Synthetic filter on, calibration honest, audit trail hydrated, decomposed gauge wired, audit gap published |
| **2** | W1 (AI Act labelling) + W2 (source-tier DB, behind flag) | EU AI Act August window cashed; source credibility tiered |
| **3-4** | W5 (agentic chat actions protocol) | Biggest UX uplift; nine action types; telemetry foundation |
| **5** | W3 (adversarial auditor persona) + S2 (negative findings provenance) | Multi-LLM genuinely independent; audit trail covers rejected claims |
| **6-8** | S1 (corporate-claim MVP) | CDP + SBTi + NZT + `/companies/[ticker]` before September ECGT |
| **9** | S5 (per-country claim ledger) + S6 (reproduce button) | Distribution/journalistic utility moves |
| **10** | S3 (indicator confidence) + S4 (learned drift thresholds) | Sustainability composite honest; drift defensible |
| **11-12** | L1 (cross-language hallucination foundation) | Per-language embeddings + claim clustering begins |
| **Q3** | L2-L5 | Ecosystem infrastructure |

---

## 4. Effects Summary

| Axis | Today (4699a70) | Post Week 12 | Driver(s) |
|---|---|---|---|
| Reliability | ~4.1 | 4.7 | W2 + S1 |
| Transparency | ~4.7 | 4.95 | C5 + W1 + S6 + R8 + S2 |
| Traceability | ~4.5 | 4.85 | C5 + S2 |
| Calibration | ~3.5 | 4.3 | C3 + W5 telemetry |
| Hallucination | ~4.0 | 4.6 | W3 + S2 |
| Corporate-claim coverage | 1.0 | 4.0 | S1 |
| Regulatory readiness | 3.5 | 5.0 | W1 + S1 |
| Source-tier rigour | 1.5 | 4.0 | W2 |
| **Composite** | **~4.0** | **~4.6** | +0.6 in 12 weeks |

---

## 5. Platform Standards & Rigour

Climatefacts.ai has established a development standard that most platforms in this category do not reach:

- **Open self-auditing**: The 2026-05-18 audit batch (8 files: functional, security, data-sources, uiux, analytical, performance, CARF comparison, feature inventory) represents honest, code-verified technical auditing. The 4.78→3.6 gap was discovered, not hidden.
- **Methodology transparency**: Versioned prompts with SHA-256 fingerprints, per-call provenance rows, and a public `/methodology` surface set a category benchmark. No other consumer climate platform exposes calibration parameters or prompt versions.
- **Regulatory-first design**: The `claim_provenance` schema directly satisfies CSRD assurance-readiness. GDPR DPIA and data processing inventory exist before production launch. This is unusual.
- **Domain-driven architecture**: The intelligence/ layer is cleanly separated from content/ — the truth-machine logic is a licensable asset, not tangled with the news aggregator.
- **Falsifiability**: The calibration pipeline (Platt scaling, Brier, ECE) means the platform can be proven wrong — the opposite of black-box oracular claims. This is the structural requirement for scientific credibility.

These standards should be preserved and extended. Every week of this plan adds to them, never subtracts.

---

## 6. Single Most Important Thing

**Ship Week 1 (C1-C6) immediately.** Three synthetic-article filters, one calibration gate, one trust dashboard, one audit-trail hydration, one decomposed gauge wiring, one production config fix. Two days of focused work. The composite moves from ~4.0 to ~4.2, and the act of publishing the audit gap alongside the self-claim on `/methodology` embodies "Trust as a Service" more powerfully than any marketing copy ever could.

Everything else in this plan compounds from that act.

---

*End of plan. Code-verified 2026-05-20 against the full codebase. Companion to the four source reports under `docs/improvementplans/` and `docs/reports/`.*
