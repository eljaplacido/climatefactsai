# Golden Examples Corpus

Curated "best of" set across all artifact kinds the platform generates.
Two purposes:

1. **Quality reference** — clickable index of the best examples per
   artifact kind. Internal QA + external explainer of "what does a great
   X look like?"
2. **LoRA training-data seeds** — feeds the GX10 specialist fine-tunes
   described in `docs/reports/asusgx10inferencestrategy.md`:
     - `climate-claim-extractor-7B` LoRA
     - `climate-context-summarizer-7B` LoRA
     - `verdict-adjudicator-7B` LoRA

The exporter at `GET /api/golden-examples/export?kind=...&min_score=4`
returns JSONL ready to feed into a LoRA training script.

## Artifact kinds

| Kind | What | Source pipeline |
|---|---|---|
| `article_enrichment` | Best brief + excerpt + climate-context outputs | GX10 Lane A worker (qwen2.5:7b on Ollama) |
| `research_analysis` | Best research-paper analysis runs (methodology + citation + transparency scores) | Cloud Run + DeepSeek |
| `company_verdict` | Best corporate-claim verdict + flag-reason pairs | Cloud Run + DeepSeek + ECGT/SBTi adjudicator |
| `semantic_explanation` | Best "why connected" outputs from /api/semantic/explain | GX10 Lane A LLM |
| `map_insight` | Best map-derived systemic insight (M8 — not yet built) | Future |
| `kg_drill_down` | Best /explore/entity/{id} traversal | GX10 entity worker → semantic_routes |

## API

```
POST /api/golden-examples
  {artifact_kind, artifact_ref, why_golden, quality_score?, domain_tag?}
  → idempotent per (kind, ref); auth required

GET  /api/golden-examples?kind=...&min_score=...&limit=...
  → list, grouped by kind

GET  /api/golden-examples/export?kind=...&min_score=4
  → JSONL one record per line: {ref, why, score, tag, promoted_at}
```

## Curation workflow

For now, manual via the `promote_golden_example` agentic skill or
direct POST. The next pass adds:

- Auto-nomination of the top N passing artifacts per wave from the
  golden pipeline daemon (filtered to `quality_score >= 4`).
- A "Mark as golden" button on the article detail / company detail /
  semantic explain results pages.
- A `/explore/golden` browse page that surfaces the index.

## Initial golden picks (2026-05-27)

These four articles passed all gates in the first golden pipeline
review and were verified as genuinely climate-relevant:

| ID | Title | Source | Why |
|---|---|---|---|
| `07371b0c-e049-40ae-84f5-c98c07b461eb` | After Belém: COP30 legacy for Amazon defenders | InfoAmazonia | Strong narrative on COP30 outcomes; 520-char brief; KG entities link to broader COP30 coverage |
| `41d56ccf-dd41-4a45-9228-0de356513d46` | Eneva drilling Indigenous Amazon gas block | InfoAmazonia | Specific fossil-fuel encroachment story; 558-char brief; verifiable claim count |
| `dd9d57ac-4cf5-4349-b442-6a07db599fd5` | Colombian Amazon oil tensions | InfoAmazonia | Conservation-vs-extraction framing; 512-char brief; 5 claims |
| `e5734bfc-4907-42ea-8d9f-676f9659cb1b` | COP31 Murat Kurum resilient cities | Climatica La Marea | COP31 agenda preview; policy-relevant; 4 claims |

## Negative-set training (anti-slop)

The `topic_feedback` table (mig 050) is the *negative* counterpart —
articles flagged off-topic by users. Future LoRA training should
include both:

- Golden examples → desired generation behavior
- Off-topic articles → contrastive training (don't enrich these the
  same way; flag them at category-classification time)
