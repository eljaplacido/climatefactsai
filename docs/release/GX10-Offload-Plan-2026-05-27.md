# GX10 Offload Plan — 2026-05-27 (post-audit consolidation)

Single source of truth for what runs on the **GX10 (Asus DGX Spark,
128 GB unified memory, qwen2.5 / nemotron-3 model family)** vs. what
stays on **Cloud Run + cloud LLM** vs. what is a **hybrid with
fallback**.

Builds on:
- `docs/reports/asusgx10inferencestrategy.md` (the original 3-lane model)
- `docs/improvementplans/GX10-Workload-Audit-2026-05-25.md` (32-call inventory)
- This release audit's findings on what actually shipped

---

## 1. Current state (verified live)

| Service | Location | Model | Status |
|---|---|---|---|
| `clilens-lane-a` (article enrichment) | GX10 systemd user | qwen2.5:7b-instruct via Ollama | ✅ live, ~21s per article |
| `clilens-lane-a-entity` (KG entity extraction) | GX10 systemd user | qwen2.5:7b-instruct | ✅ live |
| `clilens-golden-daemon` (selection + queueing + validation) | GX10 systemd user | n/a (orchestrator only) | ✅ live |
| Article claim extraction | Cloud Run | DeepSeek (cloud) | ✅ live, hybrid OK |
| Article verification (evidence + adjudication) | Cloud Run | DeepSeek + secondary multi-LLM | ✅ live |
| Deep search synthesis | Cloud Run | Claude Sonnet | ✅ live (per master-prompt: keep cloud) |
| Perplexity Sonar (news discovery) | Cloud Run | Perplexity | ✅ live (web search, not inference) |
| Research report analysis | Cloud Run | DeepSeek | ✅ live |
| Corporate claim verification | Cloud Run | DeepSeek + ECGT adjudicator | ✅ live |
| Hallucination detection | Cloud Run | spaCy NER + multi-LLM grounding | ✅ live |

**128 GB unified memory available on GX10** — currently using ~14 GB for the running services (qwen2.5:7b Q4 + qwen2.5:14b warm + bge-m3). **~114 GB headroom** for additional models.

**Models loaded but not yet routed**:
- `nemotron-3-super:120b-a12b-q4_K_M` — for batch reasoning
- `deepseek-r1:32b-qwen-distill-q4_K_M` — for reasoning
- `nemotron-3-nano:30b-a3b-q4_K_M` — for medium tasks
- `nemotron-3-nano:4b` — for speed-critical tasks
- `bge-m3:latest` — embeddings

---

## 2. The 3-lane decision matrix (refreshed)

### Lane A — Overnight batch (latency hours OK, GX10 always)

| Workload | Status | Notes |
|---|---|---|
| Article enrichment | ✅ ON GX10 | qwen2.5:7b. Could upgrade to 14b for higher quality if pass rate stalls. |
| Entity extraction → KG | ✅ ON GX10 | qwen2.5:7b. Schema validation built in. |
| Full-corpus backfills | ✅ ON GX10 | Brief-from-excerpt + tier-rescoring already use this path. |
| **Off-topic article relabel** (916 articles from mig 053 feeds) | 🆕 MOVE TO GX10 | Use qwen2.5:7b to classify each: is_climate / is_off_topic / borderline. Drop result into `topic_feedback`. |
| **Calibration reviewer-assist labels** | 🆕 MOVE TO GX10 | Use nemotron-3-super:120b for higher-confidence labels. Human reviewer audits, signs off. Gets n_labels > 30 in days, not months. |
| **Eval / regression harness** | 🆕 MOVE TO GX10 | Prompt-engineering iteration loop. Free vs. $X per cloud API call. |
| LoRA distillation training | 🚀 v1.5 | Once 20k+ SFT pairs captured in `CLILENS_TRAINING_DATASET_PATH`, train climate-claim-extractor-7B + climate-context-summarizer-7B + verdict-adjudicator-7B. |

### Lane B — Background recent (seconds-minutes, GX10 primary + cloud fallback)

| Workload | Status | Notes |
|---|---|---|
| URL analysis post-trigger | ⚠️ HYBRID PARTIAL | Currently cloud DeepSeek. Move primary to GX10 qwen2.5:14b; fallback cloud on stall. |
| Hallucination check | ⚠️ HYBRID PARTIAL | spaCy NER local; LLM-grounding sub-check cloud. Move LLM-grounding to GX10. |
| Verdict adjudication | ⚠️ KEEP HYBRID | Master-prompt says: don't collapse multi-LLM diversity. Keep cloud primary + GX10 secondary. |
| Numeric grounding check | ✅ pure-Python | No LLM, no decision. |
| Semantic explainer (`/api/semantic/explain`) | ⚠️ CURRENTLY HYBRID | Routes through `ArticleEnrichmentService._call_llm` chain — GX10 first if pinned, cloud fallback. **Working as intended.** |

### Lane C — User-facing streaming (sub-5s, cloud primary today)

| Workload | Status | Notes |
|---|---|---|
| Article chat Q&A | ⚠️ CLOUD ONLY | Move to GX10 qwen2.5:7b with token streaming, p95 < 3s. v1.5. |
| Deep-search synthesis | ✅ KEEP CLOUD | Sonnet for per-sentence grounding — too strict for local. |
| Comparison views | ⚠️ CLOUD ONLY | Could move to nemotron-3-nano:30b for medium complexity. v1.5. |

---

## 3. Concrete offload backlog (sequenced)

### Week 0 (this week)

1. **Off-topic relabel batch job** — new GX10 worker `clilens-lane-a-relabel` that classifies the 916 articles from the 4 deactivated feeds. **Closes release blocker 4 + gap §4-12 remainder.** ~3h.

2. **Calibration label batch job** — new GX10 worker `clilens-lane-a-calibrate` that generates LLM-confidence labels with high-confidence model (nemotron-3-super:120b). Human reviewer audits via existing `/calibration` admin UI. **Closes release blocker 3 + gap §4-11.** ~6h.

### Week 1-2

3. **Move URL analysis LLM call to GX10** — `url_analysis_routes._extract_claims_for_long_text` currently cloud DeepSeek. Pin `CLILENS_URL_ANALYSIS_PROVIDER=local-gx10` env var. Add fallback to cloud. ~4h.

4. **Move hallucination LLM-grounding to GX10** — currently the LLM sub-check in `hallucination_detector.check` is cloud. Move to qwen2.5:7b. ~3h.

5. **Eval harness scheduler cron** — nightly run of `tests/api/test_*.py` regression suite on GX10 with a "before changes" baseline; promote PR only if no regression. ~6h.

### Week 3-6

6. **LoRA training data capture verification** — confirm `CLILENS_TRAINING_DATASET_PATH` is actually receiving every LLM call's (system, user, output) tuple in production. Audit.
7. **Train `climate-claim-extractor-7B` LoRA** on captured pairs (target: 20k+ pairs, 30 days post Week 0)
8. **Train `climate-context-summarizer-7B` LoRA** (target: same)
9. **Promote LoRA to cloud serving** — once eval beats baseline DeepSeek by >5% F1 on held-out, route claim extraction through the fine-tuned model served on Cloud Run.

---

## 4. Cost + quality envelope

### Current monthly LLM cost estimate
- DeepSeek (article enrichment, claim extract, verify): ~$60-90/mo at current volume
- Claude Sonnet (deep search, secondary verify): ~$30-50/mo
- OpenAI embeddings (semantic search ada-002): ~$10-15/mo
- Perplexity Sonar: ~$20-30/mo
- **Total: ~$120-185/mo**

### Post-Week-2 offload
- Article enrichment → GX10 (already done): savings ~$30/mo
- URL analysis → GX10: savings ~$10/mo
- Hallucination grounding → GX10: savings ~$5/mo
- Eval harness → GX10: savings ~$5-15/mo (varies by iteration cadence)
- **Net savings: ~$50-60/mo at current scale**

### Quality risk
- Master-prompt rule: never trade observed quality ≥1pp for cost.
- Pre-promotion: every offload requires `eval_prompts.py` regression test → ≤1pp regression on JSON-validity OR structural correctness OR named-axis (methodology / citation / relevance).
- Post-promotion: monitor `local_llm_fallbacks` table for a week — if cloud-fallback rate exceeds 5%, roll back.

---

## 5. Operational ownership

| Component | Owner | On-call |
|---|---|---|
| GX10 hardware + Ollama runtime | User (Akeldama6) | self |
| Cloud Run + Cloud Build | User | self |
| Lane A worker | Code in repo, deployed via `infrastructure/gx10/setup-lane-a-worker.sh` | self |
| Daemon (golden_pipeline_daemon) | Code in repo, systemd unit on GX10 | self |
| Migrations | Code in repo, runs every cloudbuild deploy | self |
| Monitoring | Cloud Logging + Telegram bot updates | self |

**SLA target post-Week-2**: 99% uptime on GX10 (acceptable downtime: ~7h/month for maintenance). Cloud fallback ensures degraded-mode service when GX10 is offline.

---

## 6. Failure modes + recovery

| Failure | Detection | Recovery |
|---|---|---|
| Ollama OOM on GX10 | Stall detection in daemon → telegram alert → systemctl restart | Auto via daemon (working, verified) |
| Lane A worker crash | systemd `Restart=on-failure` | Auto |
| GX10 network partition | Cloud Run keeps serving via fallback chain | Auto via `_call_llm` provider fallback |
| Migration drift | CI test detects on next deploy | Manual hotfix via direct SQL (see loop-2 mig 049 fix) |
| Cloud Run cold start | First-request latency spike | Cloud Run min-instances=1 (cost ~$15/mo) — recommend for v1.0 |

---

## 7. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-05-26 | Lane A worker lives on GX10, not Cloud Run with tunnel | Cloud Run egress blocked Tailscale Funnel + CFTunnel from europe-west4 |
| 2026-05-26 | qwen2.5:7b-instruct as default Lane A model | Speed/quality tradeoff — 14b too slow at 30+ s/article |
| 2026-05-27 | Color-scheme pinned to light (no dark mode in v1) | Partial dark mode implementation caused user-visible bugs |
| 2026-05-27 | Keep verdict_adjudication hybrid (multi-LLM cloud) | Diversity signal too valuable to collapse to single GX10 model |
| 2026-05-27 | LoRA distillation deferred to v1.5 | Need 30 days of production SFT capture first |
