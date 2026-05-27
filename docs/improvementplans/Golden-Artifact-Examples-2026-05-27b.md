# Golden Artifact Examples — 2026-05-27 (audit run 2)

Per master prompt §7 — one live ID per artifact type, with the populated /
missing target-field breakdown.

## 1. Golden article enrichment

**ID**: `07371b0c-e049-40ae-84f5-c98c07b461eb` ("After Belém: The legacy of
COP30 for defenders of the Amazon and the Global South" — InfoAmazonia, BR)

URL: <https://climatenews-frontend-srzwxdzmaq-ez.a.run.app/articles/07371b0c-e049-40ae-84f5-c98c07b461eb>

| Field | Populated? | Notes |
|---|---|---|
| `executive_brief` | ✅ 520 chars | from GX10 Lane A worker (qwen2.5:7b) |
| `enriched_excerpt` | ✅ 2073 chars | LLM-generated with credibility + weather + 5-yr trend context |
| `climate_context_summary` | ✅ 463 chars | "Current temperature 24.9°C in Brazil reflects ongoing need to address climate change impacts…" |
| `enrichment_metadata.weather` | ⚠️ not in this row | enrichment happened BEFORE the M2 metadata extension shipped; new enrichments will store it |
| `enrichment_metadata.temperature_trend` | ⚠️ not in this row | same |
| `claims` | ✅ 6 | climate-relevant |
| KG `/api/carf/entity-graph/{id}` | ✅ 200 | 5 entities (COP30, Amazon, Global South, peoples and movements, UN agreements) + relationships + connected articles |
| `source_credibility_score` | ⏳ NULL pre-fix → expected 75 (T2) once `a387bd5` deploys and backfill runs | mig 049 has InfoAmazonia at T2 |
| Visible component: Executive Brief card | ✅ HTML marker confirmed |
| Visible component: In-Depth Analysis card | ✅ HTML marker confirmed |
| Visible component: Local Climate Context | ✅ HTML marker confirmed |
| Visible component: Knowledge Graph mini-view | ✅ HTML marker confirmed |
| Visible component: Mark off-topic button | ✅ HTML marker confirmed |
| Visible component: WeatherTrendCard | ⚠️ won't render (no .weather metadata) — degrades gracefully |
| Visible component: SDG chips | ⚠️ requires JS render (not in static HTML) |

## 2. Golden deep search

**Status**: not exercised this run. The /api/deep-search/* endpoints are
authenticated/Pro-only and a fresh deep-search would have cost budget
unavailable in this pass. Next pass should:

1. Authenticate as test user
2. POST /api/deep-search with a topic like "COP30 outcomes Amazon"
3. Verify response contains `weather_context`, citations with credibility
   chips, `methodology` block, hallucination check fields
4. Record the response shape here as the golden reference

## 3. Golden research analysis

**Endpoint added this pass**: `GET /api/research/analyses` (`f2ab296`)
returns the list of all completed url_analyses runs.

**Current state**: 5 rows in url_analyses with status='completed'. None
have `fact_checks` or `evidence` rows yet (gap-ledger item §4-5 still
open). The new RecentResearchAnalyses panel surfaces them on /research
with credibility badge + reliability score + audit-trail link.

**Target shape** (gap to close next pass):
- `methodology_score` ≥ 30
- `citation_score` ≥ 40
- `data_transparency_score` ≥ 30
- `climate_relevance` in {high, medium, low}
- `key_claims` ≥ 5
- Bayesian credibility posterior + CI

## 4. Golden company verdict

**ID**: Microsoft Corporation (MSFT)
URL: <https://climatenews-frontend-srzwxdzmaq-ez.a.run.app/companies/MSFT>

API response shape (verified live):
```json
{
  "company": { "name": "Microsoft Corporation", "ticker": "MSFT", "sbti_validated": true, ... },
  "disclosures": [ {"source": "cdp", "scope1_tco2e": 55400, "scope3_tco2e": 14800000, ...} ],
  "standards_compliance": [
    { "id": "CSRD", "status": "aligned", "covered_points": 5, "missing_points": 0 },
    { "id": "SBTi", "status": "aligned", "covered_points": 5, "missing_points": 0 },
    { "id": "TCFD", "status": "partial", "covered_points": 2, "missing_points": 2 },
    { "id": "IFRS_S2", "status": "partial", "covered_points": 3, "missing_points": 2 },
    { "id": "GRI", "status": "aligned", "covered_points": 4, "missing_points": 0 }
  ]
}
```

The per-standard verdicts are defensible:
- CSRD/SBTi/GRI aligned because Microsoft has Scope 1+2+3, SBTi-validated targets, assurance, no offset claims
- TCFD partial because the structured disclosure data doesn't include the governance disclosure or scenario analysis (those are narrative in the actual sustainability report — needs PDF parse)
- IFRS_S2 partial because scenario analysis + SASB industry metrics aren't in structured data

## What's NOT yet golden

- No article has the new `enrichment_metadata.weather` + `.temperature_trend` data points yet — needs a re-enrichment pass after the metadata extension lands in production
- No research analysis has populated `fact_checks` rows — gap §4-5 unfixed
- Map cross-artifact coverage at 19.7% of UN-193 — still far from 95% target

## Verification commands (for next-pass replay)

```bash
# Article golden — confirm enrichment + KG + SDG
curl -sS "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/v2/articles/07371b0c-e049-40ae-84f5-c98c07b461eb"
curl -sS "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/carf/entity-graph/07371b0c-e049-40ae-84f5-c98c07b461eb"

# Research analyses
curl -sS "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/research/analyses?limit=5"

# Company standards
curl -sS "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/companies/MSFT" | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['standards_compliance'], indent=2))"
```
