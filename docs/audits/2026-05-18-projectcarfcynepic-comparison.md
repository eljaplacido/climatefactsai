# projectcarfcynepic vs Climatefacts.ai — Component-Level Comparison

**Date:** 2026-05-18
**Author:** audit agent
**Upstream repo:** https://github.com/eljaplacido/projectcarfcynepic (BSL 1.1, converts to Apache 2.0 in Feb 2030)
**Scope:** identify components in projectcarfcynepic that would add value to climatenews beyond what was already ported in commit `cd32005`.

---

## Already imported (per `truth_machine_roadmap_2026_05_16.md`)

- **Cynefin classifier prompt** — `src/backend/app/domains/intelligence/cynefin_router.py` (315 lines)
- **CARF HTTP fallback** — `src/backend/app/domains/intelligence/carf_integration.py` delegates to `CynefinRouter` when the remote CARF FastAPI is unreachable.
- **In-house Bayesian credibility scorer** — `bayesian_credibility.py` (181 lines) implements DOI/venue priors and likelihood updates (Anthropic-style, no PyMC).
- **In-house hallucination detector** — `hallucination_detector.py` (301 lines) uses entity overlap, statistic verification, and an LLM grounding check with a 0.3/0.3/0.4 weighted fusion.
- **In-house KL-divergence drift detector** — `drift_detection.py` (394 lines) on source-mix instead of routing distribution.
- **Causal claim analyzer** — `causal_analysis.py` (128 lines) is LLM-only; `causal_claim_analyzer.py` exists too.

---

## Should import next

| # | Component | projectcarfcynepic location | climatenews target | Effort | Value |
|---|-----------|----------------------------|--------------------|--------|-------|
| 1 | **8-signal weighted hallucination fusion** (deepeval_risk 0.35, confidence_risk 0.20, epistemic_uncertainty 0.15, reflection_risk 0.10, brevity 0.05, shallow_reasoning 0.05, irrelevancy 0.07, verbosity 0.03) | `src/services/h_neuron_interceptor.py` | extend `intelligence/hallucination_detector.py:48–80` to add 5 missing signals; bump prompt registry version | 1 day | Current detector uses only 3 signals; the 8-signal scheme catches "fluent but vague" hallucinations our entity/statistic check misses. Direct numeric port. |
| 2 | **Chi-squared bias auditor** with 3 tests (domain distribution χ² p<0.05, quality disparity >20%, approval disparity >15%) | `src/services/bias_auditor.py` | new `intelligence/bias_auditor.py`; surface in `/api/admin` and methodology drawer | 2 days | Climate corpus inherits ideological skew from source mix; chi-square over claim-type × verdict counts gives a defensible "we audit ourselves" number for the truth-machine grade. No equivalent exists. |
| 3 | **Three-mode Bayesian inference** (approximate / PyMC MCMC / cached) with separated epistemic vs aleatoric uncertainty | `src/services/bayesian.py` | upgrade `bayesian_credibility.py:23` — add `mode="mcmc"` path; report 90% credible interval | 3 days | Today the credibility score is a single point estimate. Adding `(lo, hi)` 90% CIs and splitting epistemic/aleatoric noise directly lifts the "honesty" axis. PyMC is already a transitive dep of many sci-py stacks. |
| 4 | **DoWhy refutation battery** (placebo treatment, random common cause, 80% data-subset, E-value sensitivity) | `src/services/causal.py` | new `intelligence/causal_refutation.py`; call from `causal_claim_analyzer.py` after LLM extracts a cause→effect edge | 4 days | LLM-only causal extraction is the weakest part of the platform. Even running DoWhy on the temperature/CO₂ + IPCC tabular series for the headline claims gives one real causal number per article — citable, falsifiable. |
| 5 | **MAP–PRICE–RESOLVE governance** trio: cross-domain link triples (keyword + cosine ≥0.35), cost-per-query breakdown, policy-conflict surfacing | `src/services/governance_service.py`, `cost_intelligence_service.py`, `federated_policy_service.py` | new `intelligence/governance/` package; PRICE wires into `core/cost.py`; expose via methodology drawer | 5 days | PRICE gives users a per-article token/$ cost; MAP shows which climate sub-domains an article touches (energy ↔ finance ↔ health); RESOLVE flags when our editorial policies disagree. Strong differentiator for "truth-machine" framing. |
| 6 | **Plotly visualizations**: `CausalDAG.tsx`, `SensitivityPlot.tsx`, `BayesianPanel.tsx`, `RiskTopographyTab.tsx`, `DomainVisualization.tsx` (Cynefin matrix), `InterventionSimulator.tsx` | `carf-cockpit/src/components/carf/` | `src/frontend/src/components/` — new `CausalDAG.tsx`, `BayesianPosteriorChart.tsx`, `CynefinMatrix.tsx`; mount in `articles/[slug]` + `analyze/page.tsx` | 4 days | Frontend currently has `ArgumentationGraph`, `CredibilityGauge`, `DecomposedConfidenceChart` — but no causal DAG and no Cynefin matrix view. These three additions visually justify the scoring instead of just printing a number. |
| 7 | **CSL policy YAML scaffold** — `config/policies.yaml` + `config/policy_scaffolds/` | `infrastructure/policies/` (new) | declare editorial rules ("reject IPCC citations >10 years old without caveat", "require ensemble CI on projections") as YAML, evaluated in `editorial_gate.py` | 2 days | Current `editorial_gate.py` hardcodes rules in Python. Externalising to YAML matches the projectcarfcynepic guardian pattern and lets editorial team edit policies without code review. |
| 8 | **Versioned `config/prompts.yaml`** (router / causal-analyst / bayesian-explorer / deterministic-runner / policy-check / self-correction system prompts) | `config/prompts.yaml` | merge into `intelligence/prompts.py` `_REGISTRY` as new `PromptTemplate` entries (router v2.0, self_correction v1.0) | 1 day | The "self-correction" reflection prompt (process rejection → retry → escalate after N attempts) is missing from our prompt registry — would harden the deep-search and analyze pipelines. |
| 9 | **Drift-detector multi-dimension** — current climatenews tracks only source mix; CARF tracks routing distribution (Cynefin domain frequencies) with baseline=100 / window=50 / KL>0.15 thresholds | `src/services/drift_detector.py` | extend `drift_detection.py:50–60` — add a second `DriftReport` for "claim-type drift" (attribution / projection / baseline) | 1 day | Catches narrative shifts (e.g. sudden spike in projection-style claims = misinformation campaign) that source-mix drift cannot. |

---

## Different design choice — worth a discussion, not a copy

- **PyMC vs LLM-only Bayesian.** projectcarfcynepic enforces strict honesty: "will never fabricate posterior updates" — it returns priors unchanged when real data is absent. climatenews currently runs likelihood updates from LLM-derived signals. Decision needed: do we want the harder honesty constraint, or do we keep LLM-driven updates with a confidence haircut? See `bayesian_credibility.py:23`.
- **Neo4j neurosymbolic grounding.** CARF runs forward-chaining logic over a Neo4j graph (`neurosymbolic_engine.py` + `graph_retriever.py`). climatenews already has `graph_retriever.py` and the KG is populated by ingestion (per memory 2026-04-30). Worth evaluating whether to add a NeSy reasoning pass instead of pure RAG — but ~2 weeks of work, do not port blindly.
- **Cynefin domains as routing keys.** CARF routes 5 domains → 5 engines (deterministic / causal / Bayesian / circuit-breaker / human). climatenews uses Cynefin only for *labelling*. Question: should `editorial_gate.py` route Clear → cache, Complicated → DoWhy, Complex → Bayesian, Chaotic → human review? Architecturally cleaner but invasive.
- **License risk.** projectcarfcynepic is BSL 1.1 (no production use until Feb 2030). Treat all imports as **algorithmic inspiration, re-implement clean**. Do not vendor source files.

---

## Skip / not applicable

- **LangGraph StateGraph workflow** — climatenews already has its own orchestration via `services.py` + Celery; LangGraph would be a rewrite, not an improvement.
- **OPA / Open Policy Agent integration** — overkill for a public fact-check site; YAML policies (item 7) are sufficient.
- **HumanLayer approval workflows** — there is no editorial human-in-the-loop UI yet; defer until we have a moderation queue.
- **Kafka audit log** — current Postgres `audit_events` table is sufficient at our scale.
- **TLA+ formal specs** (`tla_specs/`) — not justifiable for the truth-machine grade.
- **17 demo scenarios / benchmark harness** — they cover Scope-3, supply-chain, manufacturing — none climate-news-specific. Build our own DeepEval suite (already planned in roadmap phase 4).
- **MCP server (18 cognitive tools)** — we expose REST + Next.js; no MCP consumers in our roadmap.
- **Firebase Auth / Cloud SQL** — climatenews is already on GCP Cloud SQL with custom auth; no migration value.

---

## Priority recommendation

If only one week of work were available, ship **items 1, 2, and 6** (8-signal hallucination fusion + bias auditor + 3 frontend visualizations). All three are local, low-risk, and visibly raise the truth-machine grade by populating the methodology drawer with audit numbers and the article page with causal/Bayesian visuals. Items 3, 4, 5 are bigger lifts but unlock the headline "we ran DoWhy on this claim" differentiator.
