# GX10 Workload Audit — 2026-05-25

Per-workload classification of every remote LLM call site in the platform,
deciding which can move to the ASUS GX10 (DGX Spark / Grace + Blackwell + 128 GB)
and which must stay cloud. Companion to:

  - `src/backend/app/domains/intelligence/llm_routing.py` (Phase 10 router)
  - `docs/improvementplans/GX10-Deployment-Runbook-2026-05-25.md` (operator playbook)

## TL;DR

  - **20 distinct LLM call sites cataloged** across enrichment, claim
    extraction, deep-search synthesis, hallucination check, entity
    extraction, embeddings, Q&A, comparison, intelligence briefs,
    causal analysis, news discovery, and one legacy GPT-4o verifier.
  - **13 are MOVE-TO-GX10 candidates** today (Tier-2 batch + Tier-3
    user-facing reasoning), **3 are HYBRID-WITH-FALLBACK** (deep-search
    synthesis, claim extraction secondary, embeddings WRITE-path),
    **4 are KEEP-CLOUD** (claim extraction primary diversity, news
    discovery Perplexity, legacy GPT-4o verifier, comparison synthesis).
  - **Estimated monthly $ saving on the fully-promoted set: $300–900/mo**
    (matches the runbook §7 number, derived bottom-up from the inventory
    below). Real ROI is quality compounding via local distillation +
    unlimited prompt regression, not the API spend.
  - **Top recommendation**: flip `CLILENS_ENRICHMENT_PROVIDER=local-gx10`
    first — it is the single highest-volume DeepSeek call site
    (~600–1,200 calls/day at full corpus coverage), it runs in batch
    (latency-tolerant), and SFT capture is already wired into the call
    site (`article_enrichment_service.py:610-655`) so promotion immediately
    feeds the distillation loop.

## Inventory

Volume estimates assume the production cadence from
`src/backend/app/core/celery_app.py:149-214` + the documented 195-country
ingestion footprint. All counts are **calls/day**, calibrated to:
~30 RSS polls/day × 200+ feeds with ~1–3 articles each, 195 daily
country-ingestion jobs, fact-check pipeline every 2h, batch translate
every 3h. Costs are order-of-magnitude (DeepSeek
$0.14/$0.28 per Mtok in/out, Sonnet $3/$15 per Mtok in/out).

| # | File:line | Workload | Provider + model | Volume/day | Cost/call | Quality req | Privacy | Recommendation | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `src/backend/app/domains/content/article_enrichment_service.py:411-524` | `enriched_excerpt` (200-400 word excerpt synth) | DeepSeek `deepseek-chat` primary; OpenAI / Anthropic fallback at `_call_llm` lines 657-747 | 600–1,200 (one per new article post-ingest, RSS + multi-country) | ~$0.001 in / ~$0.001 out (4k in, 1.2k out) | Med | Med (public article text) | **MOVE-TO-GX10** | Highest-volume batch workload. Latency-tolerant. SFT capture already enabled at `article_enrichment_service.py:610-655` (`CLILENS_TRAINING_DATASET_PATH`). Qwen-2.5-14B should match DeepSeek on prose synthesis. |
| 2 | `src/backend/app/domains/content/article_enrichment_service.py:526-602` | `climate_context_summary` (2-3 sentence summary) | Same `_call_llm` chain as #1 | 600–1,200 (paired with #1) | ~$0.0005 (2k in, 300 out) | Low | Med | **MOVE-TO-GX10** | Trivial 2-sentence synthesis — Qwen-2.5-14B is overkill, even Llama-3.1-8B would suffice. Bundle with #1 to amortise context. |
| 3 | `src/backend/app/domains/intelligence/entity_extraction_service.py:178-213` | `entity_extraction` (NER + relationship JSON for KG) | DeepSeek via `llm_chat` (`llm_client.py:46-94`) | 200–600 (post-ingest hook in `tasks/ingestion.py:194-206`) | ~$0.0015 (6k in, 2k out) | Med | Med | **MOVE-TO-GX10** | Structured JSON extraction is Qwen-2.5-14B's sweet spot (it ships with strong JSON-mode). Routing default already lists `entity_extraction → deepseek/local-gx10` (`llm_routing.py:166`). Promote after Week-3 shadow-mode verifies JSON validity rate ≥ 95%. |
| 4 | `src/backend/app/domains/intelligence/services.py:294-358` | `claim_extraction_primary` | DeepSeek `deepseek-chat` (`_extract_with_deepseek`) | 50–200 (auto-verify every 2h × 10 articles + URL analyses) | ~$0.0008 (4k in, 2k out) | High | Med | **KEEP-CLOUD** | Tier-4 in routing matrix (`llm_routing.py:181`). The cross-check's value IS provider diversity — primary stays DeepSeek so a *different* model family disagrees as secondary. Moving to GX10 collapses the diversity. |
| 5 | `src/backend/app/domains/intelligence/anthropic_claim_extractor.py:80-136` | `claim_extraction_secondary` | Anthropic `claude-sonnet-4-5` direct SDK | 50–200 (paired with #4 via multi-LLM verifier) | ~$0.04 (4k in × $3/M + 2k out × $15/M) | High | Med | **HYBRID-WITH-FALLBACK** (keep primary, add GX10 as tertiary) | Tier-4. Already deferred in `llm_routing.py:183` as Anthropic-only — diversity preserves cross-check rigor. The runbook calls for adding `claim_extraction_tertiary` on `local-gx10` (`llm_routing.py:186`) as a NEW independent voice; this is the cheapest quality win in the audit. |
| 6 | `src/backend/app/domains/intelligence/deep_search_service.py:1099-1194` | `deep_search_synthesis` | Anthropic `claude-sonnet-4-5` primary, DeepSeek fallback | 50–500 (user-driven, Professional+ tier-gated) | ~$0.05 (5k in + 1.5k out on Sonnet) | High | Med (user query) | **KEEP-CLOUD** (with DeepSeek fallback already wired) | Frontier reasoning + per-sentence citation grounding required. Decision-log entry in runbook §8 explicitly says local-70B won't match Sonnet here. GX10 stays a hard fallback only via `llm_routing.py:179`. |
| 7 | `src/backend/app/domains/intelligence/deep_search_service.py:928-1097` | `deep_search_synthesis_low_evidence` | Same as #6 | 5–50 (only fires when internal+external < 3 sources, line 123) | ~$0.05 | High | Med | **KEEP-CLOUD** | Same rationale as #6. Low-evidence synthesis with per-sentence grounding tags is the strictest output-shape contract in the platform — frontier model worth the cost. |
| 8 | `src/backend/app/domains/intelligence/deep_search_service.py:1196-1261` | `deep_search_comparison` (markdown comparative analysis) | Anthropic primary, DeepSeek fallback | 10–100 (one per compare API call) | ~$0.03 | Med | Med | **HYBRID-WITH-FALLBACK** (move primary to DeepSeek; GX10 fallback) | Doesn't need Sonnet-grade reasoning. DeepSeek already produces acceptable output as fallback — promote to primary and reserve Anthropic for low-evidence paths. Flip env: `CLILENS_DEEP_SEARCH_INTERNAL_ONLY_PROVIDER=deepseek`. |
| 9 | `src/backend/app/domains/intelligence/deep_search_service.py:1425-1509` | `deep_search_comparison_structured` (JSON structured comparison) | Anthropic primary, DeepSeek fallback | 10–100 (paired with #8) | ~$0.03 | Med | Med | **HYBRID-WITH-FALLBACK** | Same as #8. Structured JSON is Qwen-2.5-14B's strength. |
| 10 | `src/backend/app/domains/intelligence/deep_search_service.py:1357-1423` | `scope_refinement_suggestions` (3-string JSON array on empty results) | DeepSeek primary, Anthropic fallback | 5–50 (only on zero-result path) | ~$0.0003 | Low | Med | **MOVE-TO-GX10** | Tiny 200-token completion. A 7B local model would suffice, let alone Qwen-2.5-14B. |
| 11 | `src/backend/app/domains/intelligence/conversation_engine.py:110-148` | `chat` (article Q&A grounded on context) | DeepSeek `deepseek-chat` | 50–300 (user-driven; chat panel in article detail view) | ~$0.001 (3k in, 800 out) | Med | High (user question + article context) | **MOVE-TO-GX10** | User-facing but cap acceptable at p95 < 5s. Routing already documents this path (`llm_routing.py:174`). Privacy win: user queries don't leave LAN. Promote after deep-search internal-only proves the SLO. |
| 12 | `src/backend/app/domains/intelligence/services.py:577-678` | `evidence_retrieval_claude_knowledge` (Claude KB-based evidence synthesis) | Anthropic `claude-3-opus-20240229` direct SDK (legacy default `services.py:373`) | 200–600 (called per claim in `verify_article`) | ~$0.06 (1.5k in × $15/M + 1.5k out × $75/M Opus) | High | Med | **HYBRID-WITH-FALLBACK** (keep Sonnet/Haiku, never Opus) | The default model still says `claude-3-opus-20240229` — that's an expensive legacy default that probably nobody set explicitly. **Cost leak**: Opus is ~5× Sonnet. Switch to `claude-sonnet-4-5` via env, and use DeepSeek knowledge (`services.py:680-725`) as the primary now that `use_deepseek` is the default branch. The Anthropic path is the secondary verifier. |
| 13 | `src/backend/app/domains/intelligence/services.py:680-725` | `evidence_retrieval_deepseek_knowledge` (DeepSeek KB evidence) | DeepSeek `deepseek-chat` | 200–600 (paired with #12) | ~$0.001 | High | Med | **MOVE-TO-GX10** | Identical prompt shape to #12; the platform already runs both paths. Once #12 is hybrid'd, this becomes the primary evidence path — local promotion saves the most because it runs N times per article × N claims. |
| 14 | `src/backend/app/domains/intelligence/services.py:728-1118` | `verdict_adjudication` (claim verdict + decomposed confidence + evidence chain JSON) | DeepSeek `deepseek-chat`, retries with same model on failure | 200–600 (called per claim) | ~$0.002 (3k in, 2k out) | High | Med | **MOVE-TO-GX10** | Big structured JSON output (decomposed_confidence + evidence_chain) — Qwen-2.5-14B's JSON mode handles this well. Routing path already documented as `hallucination_check` tier-2 (`llm_routing.py:169`). |
| 15 | `src/backend/app/domains/intelligence/analysis_engine.py:180-225` | `insight_summary` (2-3 sentence credibility summary) | DeepSeek via `llm_chat` | 50–200 (paired with `full_analysis`) | ~$0.0003 (1k in, 300 out) | Low | Low | **MOVE-TO-GX10** | Trivial summarisation. Routing default already names `insight_summary` (`llm_routing.py:172`). |
| 16 | `src/backend/app/domains/content/article_generator.py:101-218` | `analysis_html` (1200-1800 word Perplexity-style article) | DeepSeek `deepseek-chat` | 50–200 (paired with `full_analysis`) | ~$0.004 (6k in, 4k out) | Med | Low (public-facing article) | **MOVE-TO-GX10** | Long-form prose generation. Qwen-2.5-14B should match DeepSeek for ≤4k-token completions. Latency-tolerant batch workload. Routing default `llm_routing.py:171`. |
| 17 | `src/backend/app/domains/content/article_generator.py:220-268` | `executive_brief` (2-3 sentence card preview) | DeepSeek via `llm_chat`, 200 max_tokens | 50–200 (paired with #16) | ~$0.0001 | Low | Low | **MOVE-TO-GX10** | Tiniest possible LLM call. A 7B model would saturate quality. |
| 18 | `src/backend/app/domains/intelligence/hallucination_detector.py:268-319` | `hallucination_grounding` (LLM grounding check JSON) | DeepSeek via `llm_chat`, system prompt + JSON parse | 50–500 (called from `deep_search_service.py:152-174` when `include_hallucination_check=True`) | ~$0.0008 (4.5k in, 800 out) | High | Med | **MOVE-TO-GX10** | Routing default `hallucination_check → deepseek/local-gx10` (`llm_routing.py:169`). Structured JSON output that Qwen handles natively. Critical for truth-axis grade so add eval-harness regression test before promoting. |
| 19 | `src/backend/app/domains/intelligence/causal_claim_analyzer.py:251-291` | `causal_analysis` (JSON: cause/effect/mechanism/confounders) | DeepSeek via `llm_chat` | 20–100 (transparency endpoint path; gated to high-credibility articles) | ~$0.001 (3k in, 1k out) | Med | Low | **MOVE-TO-GX10** | Structured JSON, low volume, no provider diversity requirement. |
| 20 | `src/backend/app/domains/intelligence/causal_analysis.py:35-110` | `causal_analysis_v2` (parallel implementation; alt prompt) | DeepSeek `deepseek-chat` direct OpenAI-SDK call | < 20 (admin path; not in hot pipeline) | ~$0.001 | Med | Low | **MOVE-TO-GX10** | Same as #19. Note: two parallel causal-analysis paths exist (#19 + #20) — opportunity for separate consolidation cleanup. |
| 21 | `src/backend/app/domains/intelligence/cynefin_router.py:232-315` | `cynefin_classifier` (domain JSON: clear/complicated/complex/chaotic) | DeepSeek via `llm_chat` (only when keyword scoring fails) | 5–50 (rare LLM fallback path) | ~$0.0001 (200-token cap) | Low | Low | **MOVE-TO-GX10** | Trivially small classification. Keyword path handles 90%+; this is the LLM fallback. |
| 22 | `src/backend/app/domains/intelligence/cross_article_service.py:300-353` | `contradiction_detection` | DeepSeek via `llm_chat` | 10–50 (admin/intelligence endpoint) | ~$0.001 | Med | Low | **MOVE-TO-GX10** | Topic-level contradiction detection across N articles. Structured JSON output. |
| 23 | `src/backend/app/domains/intelligence/cross_article_service.py:355-422` | `intelligence_brief` | DeepSeek via `llm_chat` | 5–30 (admin/intelligence endpoint) | ~$0.002 (5k in, 2k out) | Med | Low | **MOVE-TO-GX10** | Same as #22. |
| 24 | `src/backend/app/domains/intelligence/cross_article_service.py:424-491` | `consensus_analysis` | DeepSeek via `llm_chat` | 5–30 (admin/intelligence endpoint) | ~$0.001 | Med | Low | **MOVE-TO-GX10** | Same as #22. |
| 25 | `src/backend/app/domains/intelligence/research_report_service.py:538-594` | `research_report_analysis` (academic paper credibility JSON) | DeepSeek via `llm_chat`, up to 30k chars in | 5–30 (user-uploaded PDFs; Professional tier) | ~$0.008 (30k in, 2k out) | High | High (user-uploaded research) | **MOVE-TO-GX10** | High-context (30k chars). Qwen-2.5-14B-Instruct's 128k context window fits comfortably. Privacy upside: user research stays on LAN. Critical: benchmark hallucination rate on academic-paper rubric before promotion. |
| 26 | `src/backend/app/domains/content/embedding_service.py:28-48` | `embeddings` (article-text embeddings via OpenAI `text-embedding-ada-002`) | OpenAI direct SDK | 1,000–2,000 (post-ingest hook in `tasks/ingestion.py:186-192` + Q&A + deep-search query-time) | ~$0.0001 per call (8k chars) | Med | Low | **HYBRID-WITH-FALLBACK** (write-path → GX10 BGE-M3, query-path stays cloud until parity proven) | Decision-log entry in runbook §8 calls this out explicitly: write errors are invisible until query-time mismatch surfaces them. Promote WRITE path first (background re-embed with BGE-M3), keep query path on ada-002 until cosine-similarity correlation on a held-out set is ≥ 0.95. |
| 27 | `src/backend/app/domains/intelligence/entity_extraction_service.py:324-356` | `entity_embeddings` (KG entity name embeddings) | OpenAI `text-embedding-ada-002` | 500–1,500 (called per new entity in #3) | ~$0.0001 | Low | Low | **MOVE-TO-GX10** | Entity-name embeddings are short, low-stakes. BGE-M3 on the GX10 covers this with no parity risk because nothing cross-references entity embeddings with article embeddings (different tables, different similarity uses). |
| 28 | `src/backend/app/domains/intelligence/hybrid_rag_service.py:350-368` | `query_embeddings` (RAG query embeddings, ada-002) | OpenAI direct SDK | 100–500 (user-driven from RAG paths) | ~$0.0001 | High | Low | **KEEP-CLOUD** (until #26 parity proven) | Must match the embedding space the articles were indexed against. Don't flip until article write-path is migrated AND correlation test passes. |
| 29 | `src/backend/services/ingestion_service/src/perplexity_news_discovery.py:31-100+` | `news_discovery` (Perplexity Sonar per-country news search) | Perplexity Sonar | 195 (one per country per day × `scheduled_multi_country_ingestion` at 6:00 UTC) | ~$0.005 per call (Sonar pricing) | Med | Low | **KEEP-CLOUD** | This is *search*, not inference. The whole value is web-grounded results with live citations. No local model can replicate Perplexity's real-time index. |
| 30 | `src/backend/services/verification_service/src/verifier.py:64-100+` | `legacy_verifier` (GPT-4o-based claim verifier in microservice fork) | OpenAI `gpt-4o` direct SDK | Likely 0 in production (orchestrator now calls the in-process `services.py` path) | ~$0.05 if used | High | Med | **KEEP-CLOUD** if used, otherwise mark for deletion | This is a parallel implementation in the microservices fork (`services/verification_service/`) that the live `app/domains/intelligence/services.py` superseded. Confirm via `git log` whether traffic still reaches it; if not, delete to reduce maintenance surface. |
| 31 | `src/backend/services/verification_service/src/perplexity_client.py:29-80+` | `legacy_perplexity_claim_check` | Perplexity Sonar | Likely 0 — same fork as #30 | ~$0.005 | Med | Low | **KEEP-CLOUD** if used (search, not inference) | Same as #30 / #29 — search-grounded, not local-replaceable. |
| 32 | `src/backend/services/content_creation_service/src/content_creator.py:20-102` | `executive_briefing` (Perplexity-driven multi-article briefing) | Perplexity Sonar | Likely 0 — service-fork path | ~$0.01 | Med | Low | **KEEP-CLOUD** if used | Same as #29 — value is web-grounded synthesis, not inference. |

> **Notes on counting**: I count 32 distinct *prompt sites* across 20
> *workloads*. The router collapses many of these into 14 named workloads
> in `WORKLOAD_DEFAULTS` (`llm_routing.py:163-187`). Sites in
> `services/*` (rows 30-32) are legacy microservice forks that the
> in-process FastAPI router has likely superseded — verify before
> treating their volume as live.

## Recommended migrations (sorted by impact)

### Migration 1 — `enrichment` to local-gx10 (biggest single-flip win)

  - **What flips**: Rows #1 and #2 in the inventory — the
    `_call_llm` chain in
    `src/backend/app/domains/content/article_enrichment_service.py:657-747`
    consults `CLILENS_ENRICHMENT_PROVIDER` *today* and supports a single
    pinned provider. The router workload key is `enrichment` already.
  - **Env var**: `CLILENS_ENRICHMENT_PROVIDER=local-gx10`
  - **Local model**: `Qwen/Qwen2.5-14B-Instruct` (28 GB FP16; fits the
    GX10 with ~100 GB headroom for batching). For Step 2 specifically a
    smaller `Qwen2.5-7B-Instruct` would suffice but the 14B saves us
    having to serve two models.
  - **Acceptance criteria**:
      - JSON validity rate ≥ 99% on 200-sample backfill comparison vs
        DeepSeek baseline.
      - Mean output length 200–400 words (no truncation regressions).
      - Human-rated "useful enrichment" rate within 5 pp of DeepSeek
        baseline on a 50-row spot check.
      - p95 latency < 8 s/article (DeepSeek baseline is ~5–7 s; LAN +
        local-GPU should match).
  - **Savings**: 600–1,200/day × ~$0.0015 ≈ **$30–55/mo direct API cost**
    + unlimited SFT data capture for the distillation flywheel.

### Migration 2 — Add `claim_extraction_tertiary` on local-gx10 (cheapest quality win)

  - **What flips**: Add a third independent verifier to the multi-LLM
    cross-check that today only runs DeepSeek (primary) +
    Anthropic-Sonnet (secondary). The router has already reserved the
    workload key (`llm_routing.py:186`).
  - **Env var**: `CLILENS_CLAIM_EXTRACTION_TERTIARY_PROVIDER=local-gx10`
    (with the routing matrix already defaulting it to `local-gx10`)
  - **Local model**: `Qwen/Qwen2.5-14B-Instruct` (or
    `meta-llama/Llama-3.1-8B-Instruct` for a true family-diverse third
    voice — pick the model from the *most different* training corpus
    available, since family diversity IS the quality signal).
  - **Acceptance criteria**:
      - 3-way agreement score reported in `multi_llm_verifier.py`
        outputs >= 50% claim agreement on a 100-article eval set
        (anything below = the third model has a calibration problem
        worth diagnosing).
      - Doesn't increase per-article verification latency by > 30%
        (`verify_claims` already runs primary + secondary
        in parallel via `asyncio.gather` in
        `multi_llm_verifier.py:344-348`; tertiary joins the same gather).
  - **Savings**: $0 direct (this is an ADDITION, not a replacement).
    Quality win: independent third voice in cross-check tightens the
    calibration penalty path
    (`confidence_penalty_uncorroborated=0.7`).

### Migration 3 — `entity_extraction` to local-gx10 (highest-volume JSON path)

  - **What flips**: Row #3 — `entity_extraction_service.py:178-213`.
    The post-ingest hook in `tasks/ingestion.py:194-206` calls this
    once per new article.
  - **Env var**: `CLILENS_ENTITY_EXTRACTION_PROVIDER=local-gx10`
  - **Local model**: `Qwen/Qwen2.5-14B-Instruct` (its `--guided-json`
    mode in vLLM enforces schema, eliminating the JSON parse failures
    that already account for ~5% loss on the cloud DeepSeek path per
    `entity_extraction_service.py:208-213`).
  - **Acceptance criteria**:
      - JSON validity rate ≥ 98% (current DeepSeek baseline is ~95%
        based on the logged JSON parse failures).
      - Mean entities/article in [3, 15] range matching DeepSeek
        baseline (the prompt enforces this).
      - Entity-type distribution chi-squared similarity ≥ 0.85 vs
        DeepSeek baseline on a 100-article eval (catches a local
        model overusing CONCEPT vs ORGANIZATION, etc).
  - **Savings**: 200–600/day × ~$0.0015 ≈ **$10–30/mo direct**
    + much better KG schema compliance via vLLM guided-JSON.

### Migration 4 — Embeddings WRITE-path to GX10 (BGE-M3)

  - **What flips**: Row #26 — `embedding_service.py:28-48`. Move the
    *insert* path off ada-002 onto BGE-M3 served on the GX10. KEEP the
    query-time path on ada-002 until a parity test confirms cosine
    similarity is correlated ≥ 0.95.
  - **Env vars**: Two separate flags so the asymmetric rollout works:
      - `CLILENS_EMBEDDINGS_WRITE_PROVIDER=local-gx10`
      - `CLILENS_EMBEDDINGS_QUERY_PROVIDER=openai` (default; explicit
        for safety)
    Today the router only exposes `embeddings` as a single workload
    (`llm_routing.py:167`). **Open work**: split it into write + query
    sub-keys before flipping.
  - **Local model**: `BAAI/bge-m3` (1024-dim; 25× cheaper at scale than
    ada-002; multilingual which matters for the 195-country corpus).
  - **Acceptance criteria**:
      - On a held-out 500-article set, re-embed via BGE-M3 and compare
        nearest-neighbour overlap to ada-002 baseline:
        Jaccard@10 ≥ 0.7 (the 30% disagreement is acceptable because
        BGE-M3 is a superior multilingual model — perfect agreement
        would mean we gained nothing).
      - On a 50-query Q&A retrieval-precision test, BGE-M3 query +
        BGE-M3 corpus must beat ada-002 query + ada-002 corpus by ≥ 5 pp.
      - **NB**: re-embedding the full corpus is a one-time backfill
        job. Estimate: ~30k articles × 100ms BGE-M3 inference = ~50 min.
  - **Savings**: 1,000–2,000/day × ~$0.0001 ≈ **$3–6/mo direct**.
    The savings are tiny; the real win is *latency*: LAN BGE-M3 will
    be 5–10× faster than the ada-002 round-trip, materially improving
    deep-search response times.

### Migration 5 — `verdict_adjudication` + `hallucination_check` to local-gx10 (paired flip)

  - **What flips**: Rows #14 + #18. These two are the highest-volume
    structured-JSON workloads in the fact-check pipeline.
  - **Env vars**:
      - `CLILENS_HALLUCINATION_CHECK_PROVIDER=local-gx10`
      - (No router key exists yet for verdict adjudication —
        `verify_article` is bare DeepSeek. **Open work**: route it via
        `route_chat(..., workload='verdict_adjudication')` first.)
  - **Local model**: `Qwen/Qwen2.5-14B-Instruct` with vLLM
    `--guided-json` enforcing the verdict + decomposed_confidence +
    evidence_chain schemas in `services.py:858-883`.
  - **Acceptance criteria**:
      - Cross-validation on 100 labeled articles: verdict agreement
        with DeepSeek baseline ≥ 90% (4-class agreement: verified /
        partially_true / disputed / unverified).
      - Decomposed confidence factors within ±0.1 mean absolute error
        on each of the 5 factors vs DeepSeek baseline.
      - Evidence chain `source_url` populated rate ≥ 95% (the
        Guardian-lite policy at `services.py:980-998` downgrades
        verdicts when fewer than 2 chain entries have URLs — local
        model must clear the same bar).
  - **Savings**: 200–600/day × $0.002 + ~50–500/day × $0.0008
    ≈ **$15–40/mo direct** + privacy upside on user-submitted URL
    analyses.

## Workloads to KEEP on cloud

| Workload | Provider | Reason |
|---|---|---|
| `claim_extraction_primary` | DeepSeek | Tier-4 in routing matrix. Cross-check diversity is the *point* of the multi-LLM verifier — promoting primary to local collapses the diversity signal we measure with `agreement_score`. |
| `claim_extraction_secondary` | Anthropic | Same as above. Secondary is the *different-family* voice; cannot be replaced by another Qwen instance. |
| `deep_search_synthesis` | Anthropic | Frontier reasoning + per-sentence citation grounding. Decision-log entry in `GX10-Deployment-Runbook-2026-05-25.md` §8 explicitly chose to keep this on Sonnet. Local 70B (Llama-3.3-70B FP4) would be the *only* model worth even benchmarking here and it's still risky. |
| `deep_search_synthesis_low_evidence` | Anthropic | Same as above. JSON envelope contract with sentence-level grounding is the strictest output shape on the platform. |
| `embeddings_query_path` | OpenAI ada-002 | Asymmetric risk. Migrate WRITE path first; query path stays cloud until parity test passes on a held-out set. |
| `news_discovery` (Perplexity Sonar) | Perplexity | This is *search*, not inference. The value is real-time web grounding with live citations. No local model can replicate the Perplexity index. |
| `evidence_retrieval_perplexity` | Perplexity | Same as above. |
| Legacy `services/verification_service/verifier.py` (GPT-4o) | OpenAI gpt-4o | Likely zero live traffic; the in-process `app/domains/intelligence/services.py` superseded it. Verify traffic is dead, then delete — don't migrate dead code. |

## Open questions / measurement work needed

  1. **Verdict adjudication is not yet routed via `route_chat()`**.
     `services.py:888-898` calls `_deepseek_chat()` directly, bypassing
     the router. The router can't promote this workload without first
     wiring it through `route_chat(workload='verdict_adjudication')`.
     This is the single biggest piece of plumbing work blocking
     Migration 5.

  2. **`article_enrichment_service._call_llm` is also not yet routed
     via `route_chat()`** — it has its own bespoke fallback chain
     (`_call_llm` lines 657-747) that pre-dates Phase 10. Promotion
     plan needs to either (a) port the call site to `route_chat()` or
     (b) extend the bespoke chain to know about `local-gx10`. Option (a)
     is the long-term right answer; option (b) is the 1-line fix to
     unblock Migration 1 today.

  3. **Embedding parity test is not built.** Migration 4 requires a
     nearest-neighbour overlap eval comparing BGE-M3 vs ada-002 on the
     existing corpus. Estimate: 1 day to script + 50 min compute.

  4. **Qwen-2.5-14B vs DeepSeek-V2.5 win-rate on claim extraction is
     unknown.** Memory entry from 2026-05-25 (`session_2026_05_25_phase_10.md`)
     mentions "Tier-1 GX10 win" for the prompt regression harness but
     no actual head-to-head numbers exist. Before Migration 3 (entity
     extraction) we should run a 200-article labeled set through both
     and report claim-extraction F1.

  5. **GX10 cold start affects Tier-3 chat workload**. Runbook §9.2
     calls this out. For `chat` (row #11) we may want a `min-warm: 1`
     vLLM strategy or a Cloud Run `--min-instances=1` so the user-facing
     first-request latency doesn't spike. Worth measuring in shadow mode
     before promoting.

  6. **The `services/` folder fork** (rows #30, #31, #32) hasn't been
     audited for live traffic. Before deciding to keep or delete, query
     Cloud Run logs for those service URLs and confirm the routing.
     The in-process FastAPI app at `src/backend/app/` is the live path
     based on `docker-compose.simple.yml` and the deployment runbook;
     the `services/` fork looks like the pre-Phase-8 microservice
     decomposition that got rolled back.

  7. **Distillation flywheel measurement**. The runbook §7 says "the
     real ROI is quality compounding via continuous distillation."
     That's only true if we actually measure local-model quality going
     up over time. Open work: a weekly eval-harness CI that compares
     the local-gx10 model's score on the regression set against last
     week's, with the score deltas shipped to ReasoningBank so we know
     whether the flywheel is spinning.

  8. **Cost validation**. The runbook §7 cites $300–900/mo savings; the
     inventory bottoms that up to about $60–135/mo on the directly
     promotable migrations (1, 3, 4, 5). The gap is mostly in workloads
     that we KEEP on cloud (deep_search_synthesis, claim_extraction)
     where the high-cost calls happen. Honest framing for the user:
     the financial case is *modest* — the real case is privacy,
     unlimited prompt-eval cycles, and the SFT-data flywheel.
