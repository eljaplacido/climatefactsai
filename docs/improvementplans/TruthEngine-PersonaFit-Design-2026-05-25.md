# Truth Engine x Sources x Semantics x Personas — Design 2026-05-25

Companion to:
- `.claude/Climatefacts-TruthMachine-Sources-Semantics-2026-05-25_extract.txt` (244 paragraphs)
- `.claude/Climatefacts-CARF-CYNEPIC-Mapping-2026-05-25_extract.txt` (193 paragraphs)
- `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md`
- `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md`
- `docs/improvementplans/Phase-10-Session-Summary-2026-05-25.md`

Repo head referenced by both source reports: `6798122` (biome+Köppen map layer).
At time of this doc, the autonomous run continued through `Slice 7` (mig 045, 046, 047) and 4 polish skills (`save_item`, `subscribe_research_topic`, `explore_scenario`, `analyze_corporate_report`) — surface count is now **15 agentic skills**, not 11 as the TruthMachine report still records.

---

## TL;DR

1. The TruthMachine report grades the platform's **architecture** as truth-machine-deserving while its **delivered data** is not. The CARF/CYNEPIC report grades the platform as a "faithful but reduced" implementation of the upstream framework, with five of the five most-important CARF ideas present and most of them at roughly 50-70% upstream depth.
2. The biggest single contradiction with the existing platform: both reports explicitly call out that `bayesian_credibility.compute_weighted_score()` (`src/backend/app/domains/intelligence/bayesian_credibility.py:84-141`) is a **weighted-average dressed in Bayesian clothing**, with no posterior, no 90% CI, and no epistemic/aleatoric split. The module name is structurally dishonest. This is the most expensive falseness on the platform's truth surface.
3. Three other gaps are repeated across both reports and the v2 audit:
   - 3-axis source scoring is in the schema (mig 041 + mig 045) but **not consumed by the credibility math** — the legacy single `prior_bonus` path is what actually runs.
   - Entity grounding is missing — only numbers are grounded today (`numeric_grounding.py`), not entities, so hallucinated names/places slip through.
   - External (Perplexity) citations in deep-search have **no credibility annotation** — a `some-blog.example.com` link sits next to `Reuters [T1]` with no chip.
4. Persona reality: the architecture report and the gap audit both agree — **two view modes (Public, Business) exist; the other 5 named personas are copy-flavour only**. The CARF report adds that human-escalation queue (Disorder routing) is absent, which is the missing scaffold for any "Editor" persona.
5. The five highest-leverage designs (detailed in §6, sorted by leverage):
   1. **Wire 3-axis source scoring into the credibility math** (the schema exists; the math ignores it).
   2. **Add entity grounding** (spaCy NER + cross-LLM entity overlap) — the cheapest H-Neuron upgrade.
   3. **External citation credibility annotation** — domain-tier chip for Perplexity sources.
   4. **Honesty rename: `bayesian_credibility` -> `weighted_credibility`** + add a real `mode="mcmc"` branch.
   5. **Cynefin-domain engine routing** (today we label, we don't route).

---

## 1. Source-report synthesis

### 1.1 TruthMachine / Sources / Semantics report

**Core thesis (extract paragraphs 14-22):** the platform is built around a single architectural commitment — every displayed claim should be traceable to its source, and verdicts should not be produced by an LLM summarising its own confidence. The architecture deserves the "truth machine" label; the delivered data does not yet.

**Seven key claims about what the truth engine SHOULD do:**

| # | Claim (with paragraph reference) | Implication |
|---|---|---|
| C1 | "every news outlet ... has (in principle) a credibility tier and three scoring axes: editorial standards, fact-check engagement, transparency" (P15) | The schema must surface all three axes per source and feed them into article-level math. |
| C2 | "every analytical output writes a row to a provenance ledger" (P16) | Mandatory. The report grades this as SHIPPED. |
| C3 | "claim verdicts come from deterministic Python ... LLMs extract candidate claims; pure code decides truth" (P18) | The current architectural contract. Must not be diluted. |
| C4 | "The three axes from migration 041 are not surfaced in the feed — only the single rolled-up reliability_score is shown" (P33) | Gap to close. |
| C5 | "Average verified-claim confidence on production articles is around 10/100. Most articles yield one verified claim out of a possible five to ten." (P40) | Yield is the single biggest data-layer gap. |
| C6 | "External web citations (Perplexity) have no credibility tier — they are surfaced raw" (P46) | Truth-axis credibility leak in deep-search. |
| C7 | "There is NO dedicated knowledge-graph table. Entities ... live as JSONB on claims and traversal is BFS" (P86) | The shadow KG cannot do relational reasoning. |

**Direct contradictions with current platform:**

- **Persona overclaim:** report P165 lists 7 personas (Consumer / Journalist / ESG / Researcher / Policymaker / Analyst / Business decision-maker). Reality, per Honest-Gap-Audit v2 item 16: **one Public/Business view-mode toggle**. The TruthMachine report acknowledges this in P21 ("persona-specific UX for six of the seven personas described in copy") — so it is internally consistent with the gap audit.
- **"Truth machine" naming:** P22 explicitly says "the right north star and the wrong present-tense claim. The architecture deserves the label; the delivered data does not yet." This is consonant with the platform's current `/methodology` framing — no contradiction, but the report is firm that the label is aspirational today.
- **`bayesian_credibility` naming:** P37 explicitly calls out "explicitly NOT a Bayesian conjugate update, a weighted-average model with prior weight 0.3 and evidence weight 0.7." The CARF report (P65) is even more pointed: "the module is called bayesian_credibility but the math is a weighted average ... The upstream CARF runs full PyMC posterior updates and separates epistemic uncertainty ... from aleatoric uncertainty. We do not."

### 1.2 CARF / CYNEPIC mapping report

**Core thesis (P14-16):** CARF (Complexity-Adaptive and Context-Aware Reasoning Fabric) is the upstream research framework. Its central idea is that every query passes through an **epistemic router** that decides which kind of reasoning is needed (Cynefin domains: Clear / Complicated / Complex / Chaotic / Disorder), then routes Clear -> rule lookup, Complicated -> DoWhy causal, Complex -> PyMC Bayesian, Chaotic -> circuit breaker, Disorder -> human escalation. Around that core: Guardian policy layer (YAML+CSL+OPA), H-Neuron hallucination sentinel (8 signals), ChimeraOracle fast-path causal models, EpistemicState provenance schema, MAP/PRICE/RESOLVE governance, drift/bias/convergence monitoring.

**Six key claims about what the truth engine SHOULD do:**

| # | Claim (paragraph) | Implication for our platform |
|---|---|---|
| D1 | "five domains: Clear, Complicated, Complex, Chaotic, Disorder ... each domain has a target engine" (P22-23) | We label domains today; we don't route them into different engines (P36). |
| D2 | "compliance check unavailable returns 'compliant: True' — structurally optimistic and worth re-examining" (P166) | Honesty fix: flip the default to `compliant: unknown` (also called out in their §12.2). |
| D3 | "H-Neuron sentinel runs eight signals ... we run three" (P98-107) | Cheapest CARF upgrade (1 day to extend our detector). |
| D4 | "DoWhy refutation battery ... we run none of these" (P92-96) | LLM-only causal extraction has no falsification step. |
| D5 | "CARF's EpistemicState splits uncertainty into epistemic ... and aleatoric ... climatenews collapses both into a single 'confidence' float" (P118) | Single biggest semantic gap in the provenance ledger. |
| D6 | "CARF runs three chi-squared tests ... climatenews has no equivalent module" for bias auditing (P145-146) | Without this, ideological skew in the corpus is invisible. |

**Direct contradictions with current platform:**

- **"Bayesian" naming** (already covered above): P65-76. The report is explicit that this is a contractual misnomer.
- **Guardian YAML externalisation:** P131-134 — our `editorial_gate.py:1-114` uses Python if-branches. CARF declares 35 formal CSL-Core rules in `config/policies.yaml`. The report notes that we declined OPA for good reasons but recommends YAML externalisation (2 days work) so the editorial team can mutate rules without code review.
- **"Truth machine" framing** is not contradicted — both reports converge on "architecture yes, data not yet."

---

## 2. Cross-reference matrix

For each truth-related capability, scored against what the reports demand:

| Capability | What reports demand | What we ship today (file:line evidence) | Alignment (1-5) | Gap |
|---|---|---|---|---|
| **reliability_scorer** | Source 50% + claims 30% + relevance 20%; claim-density factor; cap HIGH when evidence thin | `src/backend/shared/reliability_scorer.py:78-94` (weights) + lines 147-157 (density factor SHIPPED Slice 4) + lines 264-272 (HIGH-cap SHIPPED). | **4** | Doesn't consume 3-axis source scores yet (only single rolled-up `source_credibility_score`). No epistemic vs aleatoric split. |
| **3-axis source scoring** | All three axes (editorial/factcheck/transparency) must be surfaced AND consumed by the credibility math | Schema: `infrastructure/database/migrations/versions/041_source_3axis_scoring.sql:24-107`. Fence: `045_source_3axis_fence.sql:24-87` (NULL-fill + P0001 assert). Consumer: `src/backend/app/domains/intelligence/bayesian_credibility.py:28-42` reads `prior_bonus` only — the three axes are read by `source_profiles._attach_credibility_tiers` for display, not used in `compute_weighted_score()`. | **2** | TruthMachine P39 + P157 explicitly flag this. Schema lands, math ignores. |
| **claim extractor** | Atomic, singular, specific, verifiable; mean 3-5 per article | `src/backend/app/domains/intelligence/prompts.py:218-239` enforces atomicity. `api/admin_pipeline_routes.py:87` uses `max_claims=10`. `api/url_analysis_routes.py:1548-1559` defaults `URL_ANALYSIS_MAX_CLAIMS_TOTAL=60`. Yield in production is 0-1 per article (Gap-audit v2 item 3 + TruthMachine P40 P125). | **2** | Pure data issue — full_text_fetch pre-pass is the unlock (Slice 4b deferred). |
| **multi-LLM verifier** | Two independent LLM voices; Jaccard agreement; calibration penalty for uncorroborated claims | `src/backend/app/domains/intelligence/multi_llm_verifier.py:1-60+` — primary (DeepSeek) + secondary (Anthropic), Jaccard ≥ 0.5, `confidence_penalty_uncorroborated=0.7`. Plumbed end-to-end. | **5** | None — this is one of the platform's strongest surfaces. GX10-audit Migration 2 adds a tertiary local-gx10 voice for further family diversity. |
| **numeric grounding** | Deterministic check that numbers in the claim appear in evidence within tolerance | `src/backend/app/domains/intelligence/numeric_grounding.py:1-80+` — pure functions, ≤1ms, unit-aware (°C, %, ppm, Gt, MtCO2e, etc.). | **5** | None. The TruthMachine report calls this out as a strength (P19, P152). |
| **entity grounding** | NER + cross-LLM entity overlap to catch hallucinated names/places | NOT IMPLEMENTED. Closest: `hallucination_detector.py:97-122` (`_check_entity_overlap`) but it uses simple-token extraction, not real NER. | **1** | TruthMachine P159 + CARF report §13 item B4 both demand this. Estimated 2-3 days. |
| **corporate disclosure ledger** | Verifiable corporate claims; deterministic verdict from SBTi + ECGT rules | `api/company_routes.py:143-180` (`_analyze_claim` runs SBTi-validation lookup + ECGT keyword matcher + numeric grounding). New `/api/companies/{ticker}/analyze-report` for end-to-end report analysis. 200+ live SBTi companies post-Phase-8. | **4** | CDP and NZT adapters are stubs (`data_source_unavailable`). Compliance chips (CSRD/IFRS S2/TCFD/TNFD) are decorative metadata, not paired with directive-grounded verification rules — TruthMachine P166 + Gap-audit v2 item 18 both call this out. |
| **KG / entity extraction** | Real graph store with entity canonicalisation; relational reasoning | `src/backend/app/domains/intelligence/entity_extraction_service.py:18-65` extracts via LLM, stores entities + relationships in `entities` / `entity_relationships` / `article_entities` tables. JSONB shadow on claims also. BFS via `hybrid_rag_service._graph_search`. | **3** | TruthMachine P86 + P164 + CARF P158 all flag: per-article dedup, no canonicalisation (EU / European Union / Brussels as separate strings), no graph-pattern queries. |
| **semantic search / embeddings** | Vector search with high-recall multilingual embeddings | `embedding_service.py:28-48` uses OpenAI `text-embedding-ada-002` (1536-dim). `hybrid_rag_service._semantic_search` does cosine via pgvector HNSW (ef_search=40 chat, 100 deep-search). | **3** | ada-002 is deprecated (TruthMachine P183, CARF P159). GX10-audit Migration 4 specifies BGE-M3 1024-dim on local-gx10. |
| **hybrid retrieval (RRF)** | Vector + FTS + entity-graph fused by Reciprocal Rank Fusion | `src/backend/app/domains/intelligence/hybrid_rag_service.py:26-58`. Top-15 fused via 1/(k+rank) with k=60. | **5** | None — both reports describe this as fully shipped (CARF §11.1 "the cleanest match"). |
| **deep-search synthesis** | Internal + external + weather context, with per-sentence citation grounding | `src/backend/app/domains/intelligence/deep_search_service.py:42-100` runs internal + Perplexity + weather concurrently; Anthropic Sonnet synthesises; per-sentence grounding via `SentenceGroundedAnswer.tsx`. | **4** | TruthMachine P46: external Perplexity citations have no credibility tier. Compare mode (`mode=compare`) is partially implemented (Gap-audit item 5). |
| **scenario interpolation** | Counterfactual ("what if +X°C") reasoning | `api/scenario_routes.py:1-80` — linear interpolation between IPCC AR6 SSP scenarios stored in `country_projections` (mig 035). Honest "INTERPOLATION, NOT SIMULATION" disclaimer baked in. Skill `explore_scenario` added to registry (`skills.py:266-289`). | **4** | TruthMachine P169 + CARF P46-47 demand a real counterfactual surface; we have a linearisation. Disclaimer is honest. |
| **research feed** | Subscribe-to-topic with periodic poller + dedup | `api/research_feed_routes.py:1-60` + mig 047. CrossRef poller, partial-unique on (sub_id, DOI) + LOWER(TRIM(title)) for NULL-DOI. Cloud Scheduler cron `cn-research-poll`. Skill `subscribe_research_topic` (`skills.py:253-265`). | **5** | None — Gap-audit item 13 closed. |
| **URL analysis** | Validate URL → claim extraction → multi-LLM verification → numeric grounding → credibility math | `src/backend/app/services/url_analyzer.py` (validate, hash, dedup-cache, ClaimExtractor, multi_llm_verifier, numeric_grounding). Credibility via `compute_weighted_score` (prior 0.3, evidence 0.7). | **4** | TruthMachine P40 P125: yield is the gap — average verified-claim confidence ~10/100. |
| **Cynefin router** | Five domains (Clear/Complicated/Complex/Chaotic/Disorder); domain-conditional engine routing | `src/backend/app/domains/intelligence/cynefin_router.py:1-315`. Keyword scoring + LLM fallback. Disorder maps to Complicated with capped confidence (lines 285-296). Provenance write at lines 139-176. | **3** | CARF §3.4: "we label Cynefin domains; we do not yet route into different engines based on them." A Clear question goes through the same multi-source pipeline as a Complicated one. No human-escalation queue for Disorder. |
| **CARF HTTP integration** | Proxy to upstream CARF service for causal / counterfactual / compliance | `src/backend/app/domains/intelligence/carf_integration.py:1-100`. Service not deployed; every call falls through to local code. `compliant: True` default is structurally optimistic (CARF report P166). | **3** | Stub by design. Local `analyze-claim` path composes Cynefin + CausalClaimAnalyzer + HallucinationDetector and works without the remote service. |
| **Bayesian credibility** | Full PyMC posterior, 90% CI, epistemic vs aleatoric split | `src/backend/app/domains/intelligence/bayesian_credibility.py:84-141` — weighted average. Returns `posterior_score` + `confidence_interval` (single point + ±1.96·std_err margin), no posterior distribution, no uncertainty split, no MCMC. | **2** | The module name is a contract lie. Both reports explicit (TruthMachine P37; CARF P65-76). Cheapest fix is a rename + a real `mode="mcmc"` branch. |
| **causal claim analyzer** | Cause/effect/mechanism extraction + DoWhy refutation battery (placebo, random common cause, data subsets, E-value) | `src/backend/app/domains/intelligence/causal_claim_analyzer.py:1-80` extracts via LLM. No DoWhy. No refutation. | **2** | CARF P92-96: 1138x MSE accuracy gap over raw LLM if upstream is right. 4 days to add `causal_refutation.py`. |
| **provenance ledger** | Per-extraction row with model + prompt fingerprint + retrieval strategy + source ids; CHECK constraint requires identity link | `provenance.py:1-100+` + mig 021. CHECK constraint enforced. Best-effort write (never breaks user response). 5 extraction methods + 5 negative finding methods. `claim_provenance` is the table; `record_provenance` is the write path. | **5** | None — both reports rate as SHIPPED. The lone gap is the epistemic/aleatoric collapse (covered by `bayesian_credibility` row). |
| **editorial gate (Guardian)** | YAML-externalised policy rules; CSL-Core; fail-closed | `src/backend/app/domains/intelligence/editorial_gate.py:1-114` — Python if-branches. PUBLISH/HOLD/ESCALATE based on reliability_score thresholds, disputed ratio, source tier, confidence, content type. | **3** | CARF P131-134: no YAML; editorial team can't change rules without a deploy. 2 days to externalise. |
| **drift detection** | KL divergence on routing distribution + source mix + claim type | `src/backend/app/domains/intelligence/drift_detection.py:1-80+` — KL on source_mix. Smoothing ε=1e-6. Thresholds 0.10/0.25/0.50. | **3** | CARF §10.1: missing a second DriftReport on claim-type drift (attribution / projection / baseline). 1 day. |
| **bias auditing** | Chi-squared on domain distribution, quality disparity, approval disparity | NOT IMPLEMENTED. | **1** | CARF §10.2 + §13 item #2 (2 days). Climate corpora inherit ideological skew from source mix; without this, the skew is invisible to the truth-machine grade. |
| **hallucination detector** | 8-signal H-Neuron sentinel (entity, statistic, semantic, citation, calibration, drift, NLI contradiction, KG support) | `hallucination_detector.py:27-92` — 3 signals (entity overlap 0.3, statistic accuracy 0.3, LLM grounding 0.4). | **2** | CARF §7.2 + §13 item #1 (1 day, cheapest CARF upgrade). Add 5 signals; direct numeric port. |
| **agentic skills protocol** | Single-sourced action surface; LLM cannot suggest an action the dispatcher cannot execute | `src/backend/app/domains/intelligence/skills.py:74-308` (15 skills). `tests/api/test_agentic_skill_pin.py` blocks CI on drift. | **5** | None — both reports rate as the cleanest agentic protocol on the platform (TruthMachine P144). Reports still list 11; reality is 15. |
| **EU AI Act Article 50** | AI-generated artefacts disclosed with model + prompt fingerprint + timestamp in JSON-LD | Implemented per article page via Schema.org CreativeWork JSON-LD (CARF §12.1). | **5** | None. |
| **EU AI Act Articles 9/12/13/14** | Risk management, record-keeping, transparency, human oversight | `carf_integration.check_eu_ai_compliance()` returns `{compliant: True, note: 'CARF compliance check unavailable'}` when remote down — structurally optimistic. | **2** | CARF P166 honesty fix: flip default to `compliant: unknown`. |

---

## 3. Persona-by-persona feature audit

The TruthMachine report names 7 personas; the gap audit confirms reality is **Public + Business view-mode** + per-tier quota flavouring. The CARF report doesn't name personas but its emphasis on **human escalation for Disorder routing** implicitly names an "Editor / Auditor" role.

For each persona below: information needs (from the source reports), workflow shape, what we ship today, what's missing per the reports, prioritised improvements.

### 3.1 Consumer (curious citizen)

- **Information needs (TruthMachine §7.3 + §7.4):** a credible-looking sandbox; pasted URL → useful verdict; plain-language interpretation; colour-coded credibility chips.
- **Workflow shape:** one-shot URL paste; occasional feed scan.
- **Today:**
  - `src/frontend/src/app/analyze/page.tsx` URL analyser (one-shot).
  - `src/frontend/src/app/search/page.tsx` feed with credibility chips (read from `articles.overall_credibility` stamp at ingest time).
  - Plain-language interpretation strings in `src/frontend/src/lib/plainLanguage.ts:43-203` (consumer formatters).
  - Map walkthrough overlay (`src/frontend/src/components/map/MapWalkthrough.tsx`, 4 steps).
  - Free tier 3 saved / 3 searches / 2 deep-research.
- **Missing per reports (TruthMachine P211-213):** verifier yield is low; share buttons broken until Slice 5b OG metadata landed; "personalisation footprint is one URL toggle."
- **Designed improvements:**
  1. **Verifier yield lift via full_text_fetch pre-pass** (1 day) — fixes the "1 verified claim per analyser run" feel. (Slice 4b deferred; this is the unblock).
  2. **"Why this score?" expandable card** (4-6 hours) — surface the three reliability factors (source, claims, relevance) plus the new claim-density factor. Today the user sees one number with no decomposition.
  3. **Plain-language explainer for claim-density penalty** (2 hours) — `plainLanguage.ts` already has the framework; add a `formatLimitedEvidence(count)` returning "Only 1 claim verified — limited evidence" alongside the existing badge.

### 3.2 Journalist

- **Information needs:** sourceable claims with traceable provenance; share-quote-ready chips; cross-source corroboration evidence.
- **Workflow shape:** repeated URL paste during reporting; saved bundles per story.
- **Today:**
  - URL analysis pipeline + provenance ledger walk via `/api/methodology/audit-trail/{claim_id}`.
  - Multi-LLM verifier surfaces the Jaccard agreement score in the verifier output (`multi_llm_verifier.py:14-30+`).
  - Article OG metadata SHIPPED Slice 5b (`4789a4e`).
  - Save-anything API + skill (`save_item`).
- **Missing per reports (TruthMachine P157 P175):** 3-axis source scores not surfaced in the feed; per-publisher diversity not visible.
- **Designed improvements:**
  1. **Surface 3-axis source chips** (1 day) — wire `editorial_score / factcheck_score / transparency_score` from `source_credibility_tiers` (mig 041 + 045 fence) into the article card hover state. Today only the rolled-up chip shows.
  2. **"Corroboration footprint" badge** (1 day) — show whether each claim is "Both LLMs agreed" / "Primary-only" / "Disputed" using the agreement_score already produced by `multi_llm_verifier`.
  3. **Saved-bundle export** (4-6 hours) — extend `/api/user/saved` (`api/saved_items_routes.py:1-60+`) with a `/api/user/saved/bundle/{label}/export.zip` route packaging articles + provenance + claims for offline writing.

### 3.3 ESG / Sustainability Officer

- **Information needs (TruthMachine §7.2 strong points):** corporate claim verification; CSRD / IFRS S2 / TCFD / TNFD compliance framing; greenwashing flags (ECGT); audit-grade evidence.
- **Workflow shape:** report-driven (annual disclosures); company-by-company drilldown.
- **Today:**
  - `/companies/{ticker}` page with view=business toggle (`src/frontend/src/app/companies/[ticker]/page.tsx:208-275`).
  - SBTi adapter live (200+ companies); CDP / NZT stubs.
  - `/api/companies/{ticker}/analyze` (single-claim) + `/api/companies/{ticker}/analyze-report` (multi-claim from URL/text).
  - Business-view plain-language `formatCredibilityBusiness` etc. (`plainLanguage.ts:289-352`) with greenwashing-risk wording for low credibility.
  - ECGT keyword matcher + SBTi-validation lookup + numeric grounding pipeline.
- **Missing per reports (TruthMachine P166 + Gap-audit v2 item 18):** compliance chips are metadata stamps without verification rules. CDP coverage is table stakes for ESG buyers; we have honest stubs.
- **Designed improvements:**
  1. **Audit-grade CSRD verification rule pilot** (3-5 days) — convert at least one compliance chip (CSRD E1 climate disclosure) from "tag attached to KPI" to "rule that walks the corporate disclosure → checks for ESRS E1-6 quantitative scope targets → produces a verdict and a rule-citation." Today the chip is decoration; this turns one chip into a real verification claim. Pairs with `_analyze_claim` corporate analyser.
  2. **CDP coverage path A (manual ingest)** (2-3 days) — even without live CDP feed, accept signed PDFs of CDP responses via `analyze_corporate_report`, extract emissions tables, and feed into the disclosure ledger. Stops the "we have no CDP data" cliff.
  3. **Greenwashing risk score per company** (2 days) — aggregate ECGT triggers per company + claim-density per disclosure + delta-vs-target. Surface in business view. The ingredients exist (ECGT matcher + claim analyser + SBTi target ledger).

### 3.4 Climate Scientist / Researcher

- **Information needs (TruthMachine §7.1):** trustable-enough-to-cite numbers; published calibration curve; external benchmark grading; entity grounding.
- **Workflow shape:** narrow query → drill into provenance → re-run independently.
- **Today:**
  - Hybrid retrieval (`hybrid_rag_service.py`) with vector + FTS + entity-BFS.
  - Provenance ledger (`provenance.py`) traceable via `/api/methodology/audit-trail/{claim_id}`.
  - Research feed subscriptions (`research_feed_routes.py` + mig 047) + CrossRef poller.
  - PDF/Word upload via `/api/research/upload` (`research_routes.py:30-80`).
  - Causal claim analyser (LLM extraction; no DoWhy).
- **Missing per reports (TruthMachine P190 + CARF §13):** calibration label volume low; embeddings are ada-002 (deprecated); no DoWhy refutation; no entity grounding; no published benchmark grade (ClimateX / ClimateFEVER / IPCC AR6 set).
- **Designed improvements:**
  1. **DoWhy refutation battery on causal claims** (4 days, CARF §13 item #4) — on the temperature/CO2 + IPCC tabular series we already ingest, run DoWhy once per headline causal claim with placebo treatment + random common cause + 80% data-subset + E-value sensitivity. Produces one falsifiable causal number per article. Wire into `causal_claim_analyzer.py:64-100+` after LLM extracts the cause/effect edge.
  2. **Entity grounding via spaCy NER** (2-3 days, TruthMachine P159) — extend `hallucination_detector._check_entity_overlap` with real NER (en_core_web_sm + multilingual models). Cross-LLM entity overlap then becomes the cheapest hallucination signal we don't yet have.
  3. **Public calibration curve with bootstrap CI** (2 days) — already collect calibration labels; build a /methodology endpoint that returns the reliability-vs-truth curve with bootstrap 95% CI bands. Hides the small-n caveat in the CI width rather than the absence of data.
  4. **External benchmark harness** (3-5 days, TruthMachine P176) — wire `scripts/eval_prompts.py` (Phase 10) against the ClimateFEVER public dataset; publish weekly F1 / Brier score in /methodology. Converts "verifier confidence ~10/100" into an externally-grounded number.

### 3.5 Policymaker

- **Information needs:** trustable evidence for legislative briefings; scenario projections; international comparisons.
- **Workflow shape:** scheduled briefings; periodic comparison reports.
- **Today:**
  - Country passport (22 hand-curated biome narratives + 173 generic fallback with chat handoff; `src/backend/app/domains/content/country_biome.py:35-53`).
  - Compare mode in deep-search (`mode=compare`; partial per Gap-audit item 5).
  - Scenario interpolation (`/api/scenario/country/{cc}`; honest interpolation-not-simulation disclaimer).
  - Multi-country comparison via map filters.
- **Missing per reports:** no per-policy traceability (POLICY entity type exists but isn't a first-class surface); no legislative-grade citation export; no scheduled briefing.
- **Designed improvements:**
  1. **Briefing-mode export PDF** (2 days) — extend `api/export_routes.py` with a `/api/export/briefing` POST that bundles a country + N saved articles + claim-verdict table + provenance ledger walk into a single PDF with cover page and signature line.
  2. **Policy entity surface** (3 days) — POLICY entities are extracted today (`entity_extraction_service.py:18`) but not surfaced. Add `/policies/{policy_id}` page showing all articles mentioning a policy + a debate ledger (POLICY ↔ ORGANIZATION via OPPOSES / SUPPORTS relationships).
  3. **Comparison report generator** (3 days) — combine deep-search compare with the briefing exporter. Today the chat handoff is workable; this makes a single-click "Norway vs Sweden offshore drilling" report.

### 3.6 Financial Analyst

- **Information needs:** physical-risk + transition-risk exposure scoring; portfolio overlap; defensible numbers for fund disclosure.
- **Workflow shape:** portfolio-scale (many companies); recurring updates.
- **Today:**
  - Business-view climate risk framing (`plainLanguage.ts:322-352`) with TCFD physical-risk disclosure trigger language.
  - Per-company SBTi validation + net-zero target year (`api/company_routes.py:100-128`).
  - Country climate exposure via map layers.
- **Missing per reports:** no portfolio-scale workflow; no transition-risk score (we have physical-risk via map layers); no API key surface for programmatic access at scale.
- **Designed improvements:**
  1. **Portfolio upload + aggregate scoring** (3 days) — POST `/api/portfolio/analyze` accepting a CSV of tickers, returning per-company SBTi status + ECGT risk + numeric grounding of recent claims. Reuses everything we already have.
  2. **Transition-risk score** (3-5 days) — compose ECGT keyword density per company + claim-density + SBTi target gap into a single 0-100 transition-risk number. Mirror the existing physical-risk surface.
  3. **API key surface for programmatic access** (1 day) — `api/api_key_routes.py` already exists. Add scopes for `/api/companies` and `/api/portfolio` and surface the keys in /settings.

### 3.7 Business Decision-Maker (board / C-suite)

- **Information needs:** board-ready framings; fiduciary risk language; greenwashing exposure flags; one-page briefings.
- **Workflow shape:** view-mode toggle on existing surfaces.
- **Today (per Gap-audit v2 item 17):**
  - Country passport + company detail business-view toggle.
  - Compliance chips (CSRD / IFRS S2 / TCFD / TNFD per KPI).
  - `formatTemperatureAnomalyBusiness` / `formatCredibilityBusiness` / `formatClimateRiskBusiness` / `formatArticleCountBusiness` (`plainLanguage.ts:260-386`).
- **Missing per reports:** compliance chips are decorative; no board-ready export; no greenwashing-exposure roll-up.
- **Designed improvements:**
  1. **Board-ready one-pager export** (2 days) — `/api/export/board-pack/{country|ticker}` returns a styled PDF with the four KPI cards + the business-view sentences + the compliance chips, plus the provenance trail in a footnote table.
  2. **Greenwashing-exposure rollup at portfolio level** (1 day after §3.6.2 transition-risk lands) — aggregate per-company greenwashing risk into a board-pack chart.
  3. **Per-claim compliance chips** (1 day, Gap-audit item 18) — currently chips are per-KPI; extend `complianceFrameworksFor` to per-claim categorisation so a claim like "Shell will achieve net zero by 2050" carries [CSRD E1, IFRS S2-29, SBTi] chips automatically.

---

## 4. CARF / CYNEFIN mapping (from the second report)

### 4.1 The framework decoded

**CYNEFIN** (Snowden) gives five domains for the kind of problem the system faces:

| Domain | Type | Best response | Our routing today |
|---|---|---|---|
| Clear (Simple) | Known cause→effect; recipes work | Best practice | Same multi-source pipeline (no specialised path) |
| Complicated | Knowable; expertise required | Good practice (analyse + apply) | Same multi-source pipeline |
| Complex | Patterns emerge from interaction; cannot predict | Probe-sense-respond | Same multi-source pipeline (no PyMC) |
| Chaotic | No cause→effect discernible; act first | Act-sense-respond (stabilise) | Same multi-source pipeline (no circuit-breaker) |
| Disorder | Don't know which domain | Decompose / clarify | Caps confidence at 0.4, falls back to Complicated (`cynefin_router.py:285-296`) |

**CARF** (upstream framework, BSL 1.1) wraps Cynefin with an epistemic router, Guardian policy layer, H-Neuron hallucination sentinel (8 signals), ChimeraOracle fast-path causal models, EpistemicState provenance schema, MAP/PRICE/RESOLVE governance, drift/bias/convergence monitoring.

### 4.2 Mapping current platform components into the CARF framework

| CARF component | Climatefacts.ai location | Grade (CARF report's own assessment) | Mismatch flag |
|---|---|---|---|
| Cynefin router | `cynefin_router.py:1-315` | PARTIAL (label-only, no engine routing) | We label, we don't route. |
| HTTP backend | `carf_integration.py:1-100` | STUB (service not deployed) | Honest fallback to local. |
| Bayesian credibility | `bayesian_credibility.py:1-197` | PARTIAL (weighted average, not MCMC) | **Naming contract lie** — module is named for what upstream does, not for what we do. |
| Causal analysis | `causal_analysis.py` / `causal_claim_analyzer.py` | PARTIAL (LLM extraction; no DoWhy refutation) | No falsification step. |
| H-Neuron sentinel | `hallucination_detector.py:1-92+` | PARTIAL (3 of 8 signals) | Cheapest upgrade. |
| EpistemicState / provenance ledger | `provenance.py` + mig 021 | SHIPPED | One gap: no epistemic vs aleatoric split (single `confidence` float). |
| Guardian / EditorialGate | `editorial_gate.py:1-114` | PARTIAL (Python if-branches, not YAML) | No live editor workflow. |
| Three-Layer RAG with RRF | `hybrid_rag_service.py:1-100+` | SHIPPED | "Cleanest match" per CARF §11. |
| Drift detection | `drift_detection.py:1-80+` | PARTIAL (source_mix only; no claim-type) | 1-day gap to add the second DriftReport. |
| Bias auditing | NOT IMPLEMENTED | MISSING | Highest-priority CARF item the platform doesn't have. |
| Convergence monitor | NOT IMPLEMENTED | DEFERRED (we don't train models in-platform) | Becomes relevant when GX10 distillation flywheel spins. |
| Plotly visualisations | Frontend uses Recharts / D3 | DECLINED | Not a mismatch — different visualisation stack. |
| MAP / PRICE / RESOLVE governance | NOT IMPLEMENTED | MISSING | These are upstream organisational frameworks; not necessarily worth porting at our scale. |
| EU AI Act Article 50 disclosure | Schema.org CreativeWork JSON-LD per artefact | SHIPPED | None. |
| EU AI Act Articles 9/12/13/14 | `carf_integration.check_eu_ai_compliance()` returns optimistic default | STUB | Flip default to `compliant: unknown` (CARF P166). |

**Mismatches to flag for the owner:**

- **Naming integrity:** `bayesian_credibility` does not run a Bayesian update. Rename or implement.
- **Guardian externalisation:** rules are in Python; CARF demands YAML so editors can mutate without code review.
- **Bias auditor:** the platform has no chi-squared bias check. Climate corpora carry ideological skew; we can't claim "we audit ourselves" without it.
- **Causal refutation:** LLM-extracted causal claims have no falsification step. The upstream's 1138× MSE accuracy claim is unverifiable on our side without the refutation battery.
- **Disorder handling:** caps confidence at 0.4 and falls back to Complicated. There is no human escalation queue. Without one we cannot claim true Cynefin routing.

---

## 5. Designed improvements (prioritized by leverage)

Sort key: impact / effort, where impact = (number of personas served + report-claim count served + truth-engine grade lift). Each item maps to file paths and at-least-one report paragraph reference.

### 5.1 Wire 3-axis source scoring into the credibility math

- **Why it matters:** Both reports name this. Schema exists (mig 041 + mig 045 fence) but `compute_weighted_score()` only uses the rolled-up `prior_bonus`. The single biggest "schema lands, math ignores" gap on the truth surface. TruthMachine P39 + P157.
- **What it touches:**
  - `src/backend/app/domains/intelligence/bayesian_credibility.py:84-141` (`compute_weighted_score` — extend signature with `editorial_score, factcheck_score, transparency_score`, average them into the prior with documented weights).
  - `src/backend/app/domains/trust/source_tier_service.py:68-104` (return three-axis dict, not just `(prior_bonus, tier)`).
  - `src/backend/shared/reliability_scorer.py:96-187` (consume the three-axis prior).
  - Frontend article card hover state (`src/frontend/src/components/ArticleCard.tsx`) — surface the three axes alongside the rolled-up chip.
- **Effort:** **2 days** (matches TruthMachine §6.2 estimate).
- **Dependencies:** None — mig 045 already fenced the data.
- **Acceptance criteria:**
  - Unit test: hand-curated source with editorial=90 / factcheck=70 / transparency=80 produces a different score than uniform=80 baseline.
  - Article cards expose the three axes in hover/expand.
  - `/methodology/source-tiers` endpoint surfaces all three per source.
  - Existing reliability test cases continue to pass within ±2 points.

### 5.2 Entity grounding via NER (cheapest H-Neuron upgrade)

- **Why it matters:** Today only numeric tokens are grounded. Hallucinated names ("the Helsinki Climate Accord of 2024") slip past unchallenged. CARF §13 item #1 + TruthMachine P159 both demand. Cheapest CARF upgrade on the list.
- **What it touches:**
  - `src/backend/app/domains/intelligence/hallucination_detector.py:97-130` (replace `_extract_simple_entities` with spaCy NER; en_core_web_sm + multilingual fallback).
  - `src/backend/app/domains/intelligence/numeric_grounding.py` (no change; entity grounding is a sibling module — possibly add `entity_grounding.py` parallel to it).
  - `src/backend/app/domains/intelligence/services.py:577-725` (call the entity grounder in the verdict pipeline; rejection → record_negative_finding).
- **Effort:** **2-3 days**.
- **Dependencies:** spaCy + en_core_web_sm download (~50 MB; add to Dockerfile).
- **Acceptance criteria:**
  - Synthetic claim "Reuters reported that the Helsinki Climate Accord of 2024 lowered emissions by 12%" passed against a Reuters article that contains the 12% number but not the accord name → returns `entity_grounded=False` and triggers `record_negative_finding`.
  - p95 latency added < 200ms per claim (spaCy is fast).
  - 100-claim sample: precision/recall both ≥ 0.85 against hand-labelled set.

### 5.3 External (Perplexity) citation credibility annotation

- **Why it matters:** TruthMachine P46: "External web citations (Perplexity) have no credibility tier — they are surfaced raw. A reader sees Reuters [Tier 1 chip] next to some-blog.example.com [no chip] and the chip's absence is silent." Erodes the credibility chip's meaning across the whole deep-search surface.
- **What it touches:**
  - `src/backend/app/domains/intelligence/deep_search_service.py` (per external citation: call `_extract_domain(url)` → `get_source_tier_prior(db, domain)` → annotate citation dict with `tier` + `bonus`).
  - `src/frontend/src/app/deep-search/page.tsx` external-citations rendering — show the same chip as internal articles, with "unknown" tier surfaced explicitly (not silently).
  - `src/backend/app/domains/trust/source_tier_service.py` cache should already handle the volume.
- **Effort:** **4-6 hours**.
- **Dependencies:** None.
- **Acceptance criteria:**
  - External citation from `reuters.com` shows T1 chip; from `randomblog.example.com` shows "Unknown source" chip with tooltip explaining it's not in the registered tier table.
  - Deep-search response payload includes `source_tier` on every external citation.
  - Frontend test: rendering test asserts no external citation renders without a chip.

### 5.4 Honesty rename: `bayesian_credibility` → `weighted_credibility` + real MCMC mode

- **Why it matters:** Both reports call out the naming dishonesty. The cheap version is a rename + a deprecation note. The expensive version is a real `mode="mcmc"` branch using PyMC. CARF §13 item #3 lists this as 3 days for the MCMC path; the rename is 1 hour. Doing both in one PR is what the reports want.
- **What it touches:**
  - Rename `src/backend/app/domains/intelligence/bayesian_credibility.py` → `weighted_credibility.py`.
  - Update imports: search for `from app.domains.intelligence.bayesian_credibility` and replace.
  - Add `mode: str = "weighted_average"` parameter; document that `"mcmc"` runs a real PyMC posterior.
  - Implement `mode="mcmc"` (Beta-Binomial conjugate, returns 90% credible interval, splits epistemic-from-data vs aleatoric-from-prior).
  - Update `/methodology` page copy.
- **Effort:** **3 days** for both (1 hour rename + 2.5 days MCMC).
- **Dependencies:** PyMC dependency (~50 MB; needs requirements.txt entry).
- **Acceptance criteria:**
  - All call sites updated. CI green.
  - `mode="mcmc"` returns `{posterior_mean, credible_interval_90: [lo, hi], epistemic_uncertainty, aleatoric_uncertainty}`.
  - Methodology page documents both modes with the contract for each.

### 5.5 Cynefin-domain engine routing (label → route)

- **Why it matters:** CARF §3.4: "we label Cynefin domains; we do not yet route into different engines based on them. A Clear question goes through the same multi-source analysis pipeline as a Complicated one today." This is the CARF idea that has the largest delivered-vs-architectural gap.
- **What it touches:**
  - `src/backend/app/domains/intelligence/cynefin_router.py:124-133` (the `STRATEGY_MAP` exists; nothing consumes it).
  - New `src/backend/app/domains/intelligence/strategy_dispatcher.py` that takes (query, classify_result) → routes to: Clear → cache + direct lookup; Complicated → multi-source-analysis (current default); Complex → causal_claim_analyzer path; Chaotic → rapid_assessment (lightweight); Disorder → human-escalation queue or "clarify your question" frontend prompt.
  - `api/chat_routes.py:100+` consume the dispatcher before running the heavy pipeline.
  - `api/deep_search_routes.py` similarly.
- **Effort:** **3-5 days** (router-conditional engine selection; needs a small frontend "clarify" affordance for Disorder).
- **Dependencies:** None.
- **Acceptance criteria:**
  - Query "what is the current temperature in Berlin" (Clear) → direct lookup, p95 < 500ms, no LLM call.
  - Query "predict Norway's emissions under SSP3" (Complex) → routes through causal_claim_analyzer + scenario interpolation.
  - Disorder routing: frontend modal asks one clarifying question rather than guessing.
  - Per-domain latency dashboard at `/api/admin/cynefin/metrics`.

### 5.6 Audit-grade CSRD verification rule (one chip becomes real)

- **Why it matters:** TruthMachine P166 + Gap-audit v2 item 18: "compliance chips are metadata stamps without verification rules. An enterprise procurement review will surface this within minutes." Converting at least one chip into a real verification rule is the wedge into B2B credibility.
- **What it touches:**
  - New `src/backend/app/domains/trust/csrd_e1_verifier.py` (rule walker: given a company's disclosure ledger, check ESRS E1-6 quantitative targets — Scope 1+2+3 absolute, near-term + long-term, base year, target year, % reduction).
  - `api/company_routes.py:143-180` (`_analyze_claim`) — when claim is a CSRD E1 net-zero claim, call the rule walker.
  - Frontend chip rendering: chip becomes interactive on company detail; click shows the rule + the disclosure rows checked + the verdict.
- **Effort:** **3-5 days**.
- **Dependencies:** SBTi adapter (live).
- **Acceptance criteria:**
  - For Microsoft (MSFT), the chip clicks to show "ESRS E1-6: Scope 1+2 targets present (validated by SBTi 2026-01-15); Scope 3 target present; base year 2020; target year 2050; -100% reduction → PASS."
  - For a company with no SBTi validation, the same chip click shows "ESRS E1-6: no Scope 3 target detected → INSUFFICIENT."
  - Pin test asserts the rule output shape never drifts.

### 5.7 Sentinel signal expansion: H-Neuron 3 → 8

- **Why it matters:** CARF §13 item #1 explicitly: "1 day to extend our detector with the 5 missing signals; direct numeric port. It is the cheapest CARF upgrade on the list and would specifically catch the 'fluent but vague' hallucinations our entity/statistic check misses."
- **What it touches:**
  - `src/backend/app/domains/intelligence/hallucination_detector.py:27-92` — add five signals: semantic NLI (claim ↔ source), citation density, calibration consistency, drift signal (matches prior verdict pattern), KG support (entity-graph backed).
- **Effort:** **1-2 days** (port + tune weights).
- **Dependencies:** PR 5.2 (entity grounding) for the KG-support signal.
- **Acceptance criteria:**
  - 8 signals reported in `hallucination_detector.check()` output.
  - Composite weight pattern matches CARF upstream within ±0.05.
  - Existing 3-signal test cases keep their verdicts within ±0.1.

### 5.8 Bias auditor (chi-squared)

- **Why it matters:** CARF §10.2 + §13 item #2: "Climate corpora inherit ideological skew from source mix; without this auditor, that skew is invisible." Two days of work, large-blast-radius "we audit ourselves" claim.
- **What it touches:**
  - New `src/backend/app/domains/intelligence/bias_auditor.py` (chi-squared on claim-type × verdict; chi-squared on source tier × verdict; chi-squared on country × verdict).
  - `/api/admin/bias/report` endpoint returning the three chi-squared results with verdicts.
  - `/methodology` page section.
- **Effort:** **2 days**.
- **Dependencies:** None.
- **Acceptance criteria:**
  - `/api/admin/bias/report` returns `{claim_type_x_verdict: {chi2, p, verdict}, source_tier_x_verdict: {...}, country_x_verdict: {...}}`.
  - At least one of the three reports p < 0.05 on the current production seed (otherwise the test is suspect).
  - Methodology page surfaces the latest verdict per audit.

### 5.9 EpistemicState uncertainty split

- **Why it matters:** CARF P118: "CARF's EpistemicState splits uncertainty into epistemic ... and aleatoric ... climatenews collapses both into a single 'confidence' float." Once the rename in 5.4 lands, splitting the confidence is the natural next step and unlocks better per-claim UI ("we don't know enough" vs "the world is noisy here").
- **What it touches:**
  - `infrastructure/database/migrations/versions/048_provenance_uncertainty_split.sql` (mig 048) — add `epistemic_uncertainty FLOAT` + `aleatoric_uncertainty FLOAT` to `claim_provenance`, keep `confidence` for backward compat.
  - `src/backend/app/domains/intelligence/provenance.py:62-86` — `ProvenanceRecord` adds the two fields.
  - `src/backend/app/domains/intelligence/services.py:728-1118` (verdict adjudication) — split the single decomposed_confidence into the two new fields.
- **Effort:** **2-3 days**.
- **Dependencies:** PR 5.4 (renaming + MCMC path generates the split natively).
- **Acceptance criteria:**
  - Mig 048 applies cleanly with @notolerate.
  - Every new provenance row carries both fields when the verdict pipeline produces them.
  - Audit-trail endpoint exposes them.

### 5.10 Live editor workflow for source scoring + Guardian YAML

- **Why it matters:** Today every score change is a SQL migration (TruthMachine P53). CARF §9.2 + Gap-audit item 10 both call for either an editor UI or YAML externalisation. The YAML path is the cheaper one and matches CARF Guardian.
- **What it touches:**
  - New `config/source_tier_overrides.yaml` and `config/editorial_rules.yaml`.
  - `src/backend/app/domains/trust/source_tier_service.py` — extend to read from YAML override at startup.
  - `src/backend/app/domains/intelligence/editorial_gate.py:1-114` — replace `if`-branches with YAML rules + a thin evaluator.
  - Admin endpoint `/api/admin/source-tier/{domain}` (PATCH) for live edits that write back to the YAML (or DB).
- **Effort:** **3-4 days**.
- **Dependencies:** None.
- **Acceptance criteria:**
  - Editing the YAML and restarting the API picks up new tier scores (or hot-reloads).
  - PATCH endpoint validates and persists changes.
  - Admin UI page lists current editorial rules from YAML.

---

## 6. Honest assessment

### 6.1 What's genuinely hard / out of scope

- **Real scenario simulation (FaIR / MAGICC).** TruthMachine P169 + Gap-audit item 14: a real climate-model backend is multi-week build that requires science-domain expertise we don't have in-house. The interpolation endpoint we shipped (`/api/scenario/country/{cc}`) is the honest short path; pretending otherwise would dilute the deterministic-verdict contract.
- **Knowledge-graph canonicalisation at the entity level.** TruthMachine P86 calls out "EU / European Union / Brussels all live as separate strings on different claims." Building real entity resolution (Wikidata anchoring, embeddings-based dedup, manual editor workflow) is 2-3 sprints and the value compounds slowly. Worth deferring until §5.2 entity grounding lands and we have NER outputs to canonicalise.
- **External benchmark grading at the speed the reports imply.** TruthMachine P176 + CARF report: ClimateFEVER, ClimateX, IPCC AR6 statement set. The CI harness is 3-5 days; running it on enough samples to publish stable F1 is weeks of compute even on the GX10. Worth doing, but the published number will lag.
- **MAP / PRICE / RESOLVE governance modules.** CARF lists these as upstream components. They are organisational frameworks for an enterprise R&D function, not algorithmic primitives. Porting them at our scale is over-engineering.

### 6.2 Report demands that contradict the platform's existing trust contract

- **The "8-signal H-Neuron" demand is compatible** with the deterministic-verdict contract because it strengthens rather than dilutes the grounding check. Direct port, no contradiction.
- **The "DoWhy causal refutation" demand is compatible** because it is deterministic statistical machinery, not LLM judgement. Strengthens the "LLMs extract candidate claims; pure code decides truth" contract (TruthMachine P18).
- **The "MCMC Bayesian credibility" demand is compatible** in principle, but care needed: a real posterior carries the temptation to surface the distribution as a "confidence" that the user reads as truth-probability. Mitigation: surface the 90% credible interval explicitly with the disclaimer "this is the spread of plausible scores given current evidence, not the probability the claim is true."
- **The "Cynefin engine routing" demand is partially in tension** with the current architecture: today every claim goes through the same multi-source pipeline, which is consistent and auditable. Routing into different engines per domain means the same query in two different framings (Clear vs Complicated phrasing) gets different evidence — that's a reproducibility cost. Mitigation: log the routing decision in `claim_provenance.retrieval_strategy` so an auditor can see which engine ran.
- **The "human-escalation queue for Disorder" demand contradicts the current zero-headcount-editor model.** Today there is no editor seat to escalate to. Either the platform stays self-service (no escalation) and acknowledges Disorder routes to a "clarify your question" frontend prompt, or the platform commits to a paid editor tier. **This is a product decision, not an engineering one.** The reports lean toward escalation but don't reckon with the staffing cost.

### 6.3 Where the reports are aspirational vs achievable

- **"Truth machine for climate data"** is aspirational. The reports themselves agree (TruthMachine P22, P242). The honest framing is "climate-data verification platform with an unusually defensible provenance layer." The reports are correct that the architecture deserves the label and the data does not yet.
- **"7 personas served"** is aspirational. The reports and the audit converge: reality is two view modes. The right move is to update the docx to "Public + Business view modes (with persona-flavoured copy and quota tiers)" and stop claiming the rest.
- **"Audit-grade compliance"** is aspirational across all four regimes (CSRD, IFRS S2, TCFD, TNFD). Becoming audit-grade on **one** chip (5.6) within a sprint is achievable; becoming audit-grade on all four is multi-quarter regulatory + engineering work.
- **"89.5% F1 Cynefin router"** is a CARF upstream number on a different corpus. Our claim should be "router correctly labels keyword-clear queries with high confidence; LLM-fallback path is unbenchmarked on our climate-news mix." Publishing our own F1 is the §5.5 deliverable.
- **"1138× MSE accuracy ratio over raw LLM" for causal claims** is a CARF upstream claim. Until we actually run the DoWhy refutation battery on the temperature/CO2 series (§5.x), we cannot claim it. Adopting the framework is one thing; inheriting the benchmark number is another.

### 6.4 Recommended next-session ordering

If the goal is the largest visible truth-grade lift with smallest engineering cost:

1. **5.3 External citation credibility chips** (4-6 hours; closes the "silent missing chip" leak across deep-search; visible to every user immediately).
2. **5.1 Wire 3-axis source scoring into the credibility math** (2 days; closes the "schema lands, math ignores" gap that both reports flag).
3. **5.4 Honesty rename `bayesian_credibility` + MCMC path** (3 days; the naming dishonesty is the most expensive falseness on the truth surface).
4. **5.2 Entity grounding** (2-3 days; cheapest hallucination signal we don't have).
5. **5.7 H-Neuron 3 → 8 signals** (1-2 days, after 5.2).

If the goal is the biggest single B2B sales unblock:

1. **5.6 Audit-grade CSRD verification rule pilot** (3-5 days; converts one decorative chip into a real verifier — opens the procurement-review conversation).
2. **5.10 Live editor workflow + Guardian YAML** (3-4 days; lets the editorial team mutate scoring without code review).
3. **3.3.2 CDP coverage path A (manual ingest)** (2-3 days; closes the ESG buyer's "no CDP" cliff).

If the goal is the truth-engine architectural depth lift (matches the CARF report's ranked list):

1. **5.8 Bias auditor** (2 days; the cheapest CARF-grade depth win).
2. **5.5 Cynefin engine routing** (3-5 days; converts a label-only router into a real router).
3. **5.9 EpistemicState uncertainty split** (2-3 days; only after 5.4).
4. **3.4.1 DoWhy refutation battery** (4 days; the most defensible falsifiable-causal-number win).

---

## 7. Cross-references for follow-up sessions

- `docs/improvementplans/Honest-Gap-Audit-v2-2026-05-25.md` — the 22-item gap audit; slices 1-7 already shipped this session.
- `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md` — per-LLM-call inventory + migration order. Migration 1 (`enrichment` → local-gx10) is the highest-leverage independent flip and the prerequisite for the SFT distillation flywheel.
- `docs/improvementplans/Phase-10-Session-Summary-2026-05-25.md` — the commit ledger for the Phase-10 routing foundation + the still-deferred backlog.
- `.claude/Climatefacts-TruthMachine-Sources-Semantics-2026-05-25_extract.txt` — companion truth-engine report (244 paragraphs).
- `.claude/Climatefacts-CARF-CYNEPIC-Mapping-2026-05-25_extract.txt` — companion CARF mapping report (193 paragraphs).

---

End of design doc — `docs/improvementplans/TruthEngine-PersonaFit-Design-2026-05-25.md`
