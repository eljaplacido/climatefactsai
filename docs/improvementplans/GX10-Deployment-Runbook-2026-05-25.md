# ASUS GX10 Deployment Runbook — Climatefacts.ai
**Phase 10 (2026-05-25)**

This runbook turns the strategic GX10 plan into a sequenced operator
playbook. Every step is reversible (env-var flip) and every promotion
is gated on a measurable threshold from the eval harness.

## 1. Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│ Cloud Run (API)     │         │ ASUS GX10 (LAN)     │
│ - FastAPI workers   │ ◄──► │ - vLLM :8000        │
│ - llm_routing.py    │  Tail- │ - Qwen-2.5-14B      │
│ - Circuit breaker   │  scale │ - Llama-3.3-70B FP4 │
│                     │        │ - BGE-M3 embeddings │
└──────────┬──────────┘        └─────────────────────┘
           │
           ▼
  ┌──────────────────┐
  │ Cloud SQL        │
  │ - shadow_preds   │
  │ - llm_fallbacks  │
  │ - eval_runs      │
  └──────────────────┘
```

Every LLM call site goes through `route_chat(prompt, workload=...)`.
The router consults `WORKLOAD_DEFAULTS` + the `CLILENS_{WORKLOAD}_PROVIDER`
env var, tries the primary, falls back through the chain on failure.

## 2. Per-workload routing matrix

| Workload | Default primary | Fallback chain | Tier |
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
| deep_search_synthesis | anthropic | deepseek | 4 (do not move) |
| claim_extraction_primary | deepseek | — | 4 |
| claim_extraction_secondary | anthropic | — | 4 |
| claim_extraction_tertiary | local-gx10 | — | NEW |

Tier-4 entries are diversity-preserving. Moving them defeats the
cross-check.

## 3. Pre-flight checklist (one-time setup)

### 3.1 On the GX10

```bash
# 1. Install vLLM (already on the GX10 if you've used it for any model)
pip install vllm

# 2. Pick a starter model (Qwen-2.5-14B is ~28 GB, fits comfortably)
huggingface-cli download Qwen/Qwen2.5-14B-Instruct

# 3. Serve it on :8000
vllm serve Qwen/Qwen2.5-14B-Instruct \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --api-key clilens-gx10-$(date +%s)

# 4. Confirm reachable locally
curl http://localhost:8000/v1/models
```

### 3.2 On the GX10 — Tailscale

```bash
# Install + auth Tailscale so Cloud Run can reach the box without
# opening a public port.
sudo tailscale up
tailscale ip -4   # note the IP
tailscale status  # confirm magic-DNS name (e.g. gx10.tail-abcd.ts.net)
```

### 3.3 On GCP (climatenews-495412)

```bash
# 1. Install Tailscale on Cloud Run via the sidecar pattern
#    (https://tailscale.com/kb/1326/cloud-run). One-time setup.

# 2. Add LLM routing env vars to Cloud Run as secrets (so they survive
#    deploys via cloudbuild.yaml --set-secrets)
gcloud secrets create clilens-local-gx10-base-url \
  --project=climatenews-495412 \
  --data-file=<(echo -n "http://gx10.tail-abcd.ts.net:8000/v1")

gcloud secrets create clilens-local-gx10-api-key \
  --project=climatenews-495412 \
  --data-file=<(echo -n "clilens-gx10-TIMESTAMP")  # whatever you set in 3.1

gcloud secrets create clilens-local-gx10-model \
  --project=climatenews-495412 \
  --data-file=<(echo -n "Qwen/Qwen2.5-14B-Instruct")

# 3. Wire to Cloud Run (add to cloudbuild.yaml --set-secrets list:
#    CLILENS_LOCAL_GX10_BASE_URL=clilens-local-gx10-base-url:latest
#    CLILENS_LOCAL_GX10_API_KEY=clilens-local-gx10-api-key:latest
#    CLILENS_LOCAL_GX10_MODEL=clilens-local-gx10-model:latest
```

### 3.4 Confirm reachability from Cloud Run

```bash
# Sanity: GET /api/admin/llm/breakers shows local-gx10 closed (i.e. OK)
TOKEN=$(gcloud secrets versions access latest --secret=corporate-sync-token \
  --project=climatenews-495412)

curl -H "x-corporate-sync-token: $TOKEN" \
  https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/admin/llm/breakers
```

## 4. Promotion sequence (weeks 1-4 from strategy doc)

### Week 1 — Shadow mode on entity extraction
```bash
# No env var change yet. Just observe local model latency + quality
# by enabling shadow writes in the router (TODO: add SHADOW_MODE flag).
```

### Week 2 — Prompt eval harness (Tier 1 win)
```bash
# Run the harness against the current DeepSeek baseline:
python scripts/eval_prompts.py --provider deepseek --sample 500

# This populates prompt_eval_runs with the baseline scores. Every
# subsequent prompt edit can be regression-checked against it.
```

### Week 3 — Promote entity extraction + embeddings
```bash
# Flip ONE workload at a time. Verify p95 latency + breaker status.
gcloud run services update climatenews-api \
  --region=europe-west4 --project=climatenews-495412 \
  --update-env-vars=CLILENS_ENTITY_EXTRACTION_PROVIDER=local-gx10

# Check fallback rate over 24h. If < 5%, promote the next workload.
curl -H "x-corporate-sync-token: $TOKEN" \
  "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/admin/llm/fallbacks?workload=entity_extraction"
```

### Week 4 — Promote translation + add tertiary verifier
```bash
gcloud run services update climatenews-api \
  --region=europe-west4 --project=climatenews-495412 \
  --update-env-vars=CLILENS_TRANSLATION_PROVIDER=local-gx10,\
CLILENS_CLAIM_EXTRACTION_TERTIARY_PROVIDER=local-gx10
```

## 5. Rollback protocol

If anything goes wrong, single env-var flip reverts:

```bash
gcloud run services update climatenews-api \
  --region=europe-west4 --project=climatenews-495412 \
  --remove-env-vars=CLILENS_ENTITY_EXTRACTION_PROVIDER
```

The router falls back to the WORKLOAD_DEFAULTS default (deepseek
primary). No code change needed.

## 6. Health-check endpoints (operator use)

| Endpoint | Use |
|---|---|
| `GET /api/admin/llm/routing` | Effective workload→provider table |
| `GET /api/admin/llm/breakers` | Circuit-breaker snapshot per provider |
| `GET /api/admin/llm/fallbacks?workload=enrichment&limit=100` | Recent fallback events |

All token-gated via `CORPORATE_SYNC_TOKEN` header.

## 7. Cost model (honest)

From the strategy doc + current measured calls:

| Workload | Daily volume | Cloud cost | Local cost (electricity + amortised) |
|---|---|---|---|
| Enrichment | 200-500 | $5-15/day | ~$1/day |
| Entity extraction | 100-300 | $2-8/day | ~$0.50/day |
| Embeddings (write) | 1,200 | $1-2/day | ~$0.20/day |
| Translation | 50-200 | $3-8/day | ~$0.50/day |
| Chat | 100-500 | $4-12/day | ~$1/day |
| **Subtotal** | — | **$15-45/day** | **~$3/day** |

Pure savings: ~$300-900/mo. GX10 payback period at retail: ~12-18 months.

The real ROI is **not cost reduction**. It's:
- Quality compounding via continuous distillation of captured SFT data
- Tertiary verifier added to cross-check (free quality win)
- Prompt regression harness running unlimited (cloud cost prohibitive at scale)
- Sovereignty for corporate-claim verification (no data exfil to LLM providers)
- Unlimited red-team / adversarial probing during model evaluation

## 8. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-25 | local-gx10 added as 3rd verifier in cross-check (different model family) | Diversity is the cross-check's whole value |
| 2026-05-25 | deep_search_synthesis kept on Anthropic | Frontier reasoning + citation grounding; local 70B won't match |
| 2026-05-25 | Embeddings WRITE path moves to BGE-M3 on GX10; QUERY stays on ada-002 until parity proven | Asymmetric risk — write errors invisible until query-time mismatch |
| 2026-05-25 | Per-workload env-var routing (CLILENS_*_PROVIDER) chosen over global flag | Enables one-workload-at-a-time rollout + rollback |
| 2026-05-25 | Failure tracking via local_llm_fallbacks table, not metrics-only | Replay + offline scoring of failed calls |

## 9. Open questions

1. **Tailscale on Cloud Run** — sidecar pattern is documented but I haven't validated reachability from the climatenews-495412 service yet. First deploy needs a smoke test.
2. **vLLM cold start** — the GX10 needs ~30-60s to warm; the circuit breaker handles this but the first request after a GX10 restart will trigger fallback. Acceptable for batch; user-facing chat might want a `min-warm: 1` strategy.
3. **Cost of GX10 itself** — ~$3,000 retail. Worth it for the quality compounding even if pure cost savings take 12-18 months to recoup.
4. **Continuous distillation schedule** — weekly seems right. Track when training set has >10% new rows vs. last training; auto-trigger then.

This runbook is a living doc. Update after each promotion or rollback.
