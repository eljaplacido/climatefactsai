# CliLens / Climatefacts.ai — Pre-Release Data-Layer Audit (Authoritative Synthesis)

**Auditor:** Multi-agent audit (7 subsystem audits → 42 adversarial gap-verifications → synthesis) · **Date:** 2026-06-09 · **Prod API:** `https://climatenews-api-srzwxdzmaq-ez.a.run.app` · **Scope:** ingestion → enrichment/scoring → metrics/surfaces, plus GX10 offload economics.

> **Note:** ratings reflect *verified* state — every high-severity gap was adversarially re-checked. Result: **21 confirmed, 18 overstated, 3 false** out of 42 high-severity gaps (77 total gaps found). ~40% of the alarming claims were downgraded or dropped — the §6 "Claims DROPPED" list records them so we don't chase ghosts.

---

## 1. Executive Summary

**Overall data-layer health: 3.0 / 5** — the *pipes and transparency scaffolding are production-grade, but the data flowing through them is geographically lopsided, partially unscored, and uncalibrated.*

Adversarial verification overturned several alarming claims: ingestion **is** scheduled (Celery beat + 13 Cloud Scheduler jobs, prod freshness ≤1–2 days); the off-topic filter **is** wired end-to-end; the 3-axis source scores **are** consumed in URL-analysis + reliability-update paths; URL-analysis claims **are** mirrored to the corpus; and "~30% at fallback-50" / "~99% unverified" are contradicted by prod (6/100 at 50; 42% HIGH / 58% MEDIUM).

**The 3–5 things that matter most before first release:**

1. **Country attribution is corrupting prod data (P0, CONFIRMED).** `XX-AF`/`XX-LA`/`XX-AS`/`XX-ME` pan-regional feed codes are CHAR(2)-truncated to `AF`/`LA`/`AS`/`ME`, so 161 "Afghanistan" / 119 "Botswana" articles are mislabeled. The heat-map is *visibly wrong* at launch. **(This is the root cause of the map `XX`/`AF`/`BW` anomaly.)**
2. **"~95-country coverage" is fiction at 103 countries; AU, ZA, NG, EG, SA (+KE) have ZERO coverage** despite feeds defined in `eu_feeds_registry.py` — the dict was never seeded into `rss_feed_registry`.
3. **Trust engine produces low-signal verdicts:** claim extraction stuck at 2.24 claims/article (0% reach the 6-claim full-credit threshold), calibration on ~0 labels, multi-LLM "agreement" shares one prompt.
4. **GX10 offload works for 3 batch workloads but has no promotion gate** — shadow/eval tables exist but nothing populates them (P2, not a blocker).
5. **Scoring is now a documentation/transparency gap, not a wiring gap:** ≥4 credibility scales with a canonical internal module but no `/api/methodology/credibility-scale` endpoint.

---

## 2. Subsystem Scorecard

| Subsystem | Health | One-line state |
|---|---|---|
| Ingestion & Geographic Coverage | **2.5** | Pipes work and are scheduled; aimed at the wrong 103 countries — 6 high-impact nations at zero. |
| Data & Semantic Layer (core) | **2.5–3.0** | Coherent + scheduled; country-code corruption + ada-002 unpopulated + a claims backlog. |
| Trust & Scoring Engine | **3.55** | Strong transparency; weak verification yield, ~0 calibration labels, same-prompt multi-LLM. |
| Agentic Features & Chat Actions | **3.5** | 22 skills live and pinned; quota enforcement inconsistent, verify-claim heuristic, thin e2e. |
| External Integrations & Reliability | **3.5** | 4 LLM providers + adapters with fallbacks; CDP gated (no Scope-3), silent Perplexity failures. |
| GX10 Offload & Cost Routing | **3.8** | 3 batch workloads live on GX10; no promotion-gate harness, entity-extraction env-spoofed. |
| Metrics/KPI Surfacing & Coherence | **2.5–3.0** | Live queries, no stale hardcodes; ≥4 undocumented credibility scales, soft CI guards. |

---

## 3. Key Incoherences (prod evidence)

- **A — Country misclassification (CONFIRMED, P0).** `eu_feeds_registry.py:186-191` defines `XX-AF`/`XX-LA`/`XX-AS`/`XX-ME`; CHAR(2) truncation → ISO-valid-but-wrong codes (`AF=161`, `BW=119`, `LA`/`AS`/`ME` artifacts). Feeds are actively polled.
- **B — Two embedding columns, one empty.** `articles.embedding` (ada-002, paid) is orphaned/near-empty; the *live* semantic path is `embedding_bge_m3` (GX10, free) via `embedding_worker.py`. **Correction:** semantic search is NOT down — chat/deep-search use HybridRAG over bge-m3 with FTS fallback.
- **C — Source scoring divergence is documentation, not wiring.** 3-axis scores ARE consumed in `reliability_scorer.update_article_reliability` + `url_analysis_routes`, but NOT in the discovery/ingest stamp path.
- **D — Sparse scope data.** `fully_disclosed=9` because CDP is gated; SBTi (3,960) carries targets, no Scope 1/2/3. Coverage ceiling, not a bug.
- **E — Claims backlog.** Recent sample 97% completed, but some rows `pending` 14+ days — the 2-hourly auto-verify (batch=10) can't keep pace with ~965 articles/day.

---

## 4. Roadmap to End2End 4+/5 (per axis)

| Axis | Current | Blocker | Work to reach 4+ | Effort |
|---|---|---|---|---|
| Source credibility (3-axis) | 3.6 | 3-axis consumed only in some paths; ingest stamps single score | Call `get_source_3axis_scores(domain)` in discovery + backfill stamp; expose 3 axes in `/articles` | S |
| Claim extraction yield | 3.0 | 2.24/art, 0% ≥6 (`density_factor`≈0.37); 34% JSON parse fails | Strict-JSON + retry; v1.2 prompt (hedged/implicit claims); target ≥3.5; re-measure | M |
| Verdict meaningfulness | 3.2 | NOT "99% unverified" (42% HIGH/58% MED). The `0.5` no-claims default floors everything at MEDIUM — nothing rates LOW | Fix zero-claims default so empty-evidence can score LOW; don't lower 0.50 threshold | M |
| Calibration | 2.6 | `n_labels≈0`; no `fit_status`/margin exposed | 50+ label sprint (scientific_causal + statistical); add `fit_status`/margin to endpoint+UI | M |
| Multi-LLM independence | 2.8 | Same prompt → both providers; numerics grounded vs source not data | Deploy `auditor_persona` secondary; ground vs `country_indicators`; surface `numeric_grounded` | M |
| Sustainability score | 3.7 | ND-GAIN wired (v2, 0.15); `year_spread` dropped by DTO | Add `year_spread` to `SustainabilityScoreOut`; mixed-vintage tests | S |
| Editorial/topical gate | 3.8 | Gate IS wired; justification not persisted/documented | Persist matched keywords+score; document inclusion rule in `/methodology` | S |
| Hallucination entity check | 3.5 | spaCy NER IS default; silent regex degradation with no alert | Alert on spaCy load fail; sentence-scope regex; 20-claim precision review | M |
| Transparency / audit trail | 4.5 | Strong. No "% analyses with provenance" metric; no credibility-scale doc | Add provenance-coverage metric; ship `/api/methodology/credibility-scale` | S |

**Sequenced plan:**
- **Wave 1 (week 1, all S):** 3-axis into ingest/backfill stamp; `year_spread` + `fit_status` to DTOs/endpoints; credibility-scale doc endpoint; document gate. → ~+0.4.
- **Wave 2 (weeks 2–3, M):** strict-JSON + claim-yield A/B; fix zero-claims floor; `auditor_persona` + external numeric grounding. → ~+0.7.
- **Wave 3 (weeks 3–4):** 50-label calibration sprint + claims-backlog throughput. → ~+0.4, lands **≥4.0**.

---

## 5. GX10 Offload Plan

| Workload | Decision | $/mo | Acceptance gate |
|---|---|---|---|
| Article enrichment | MOVE — done | −$12–15 | fallback <2%, p95 <300s (met) |
| Embeddings (bge-m3) | MOVE — done | −$8–10 | bge-m3 backlog <100 (met) |
| Entity extraction + KG | MOVE — in progress (env-spoofed) | −$5–7 | `_llm_extract`→`route_chat('entity_extraction')`; remove spoof |
| Claim extraction tertiary | HYBRID (fragile) | $0 | add `('deepseek',)` fallback (1-line) |
| Hallucination/translation/insight/HTML | MOVE — future | −$5–10 | per-workload eval ≥0.95× cloud |
| Eval/shadow A/B harness | MOVE (build it) | enabler | populate `shadow_predictions`+`prompt_eval_runs`; nightly cron |
| Deep-search synthesis | KEEP-CLOUD | ~$5–10 | per-sentence citation grounding |
| Chat (user-facing) | KEEP-CLOUD | ~$10–20 | <5s SLO; GX10 may power off |
| Perplexity discovery | KEEP-CLOUD (external) | ~$20–30 | not inference |

**Net:** ~$20–25/mo already eliminated (8–10% of baseline); +$5–7 on entity promotion. Top gap: the promotion gate (`scripts/eval_prompts.py` exists but no cron/endpoint; `shadow_predictions` never written). **P2, not a blocker.**

---

## 6. Prioritized Fix Backlog (CONFIRMED gaps only)

### P0 — Block first release
1. **Pan-regional feed codes corrupt country attribution** (`XX-AF`→`AF`) — **M** — set those feeds to `XX`/per-country; add `^[A-Z]{2}$|XX` validation before INSERT; re-stamp corrupted rows.
2. **Zero coverage for AU, ZA, NG, EG, SA (+KE)** — **M** — migration seeding `eu_feeds_registry` → `rss_feed_registry`; verify ingestion.
3. **Claim extraction yield 2.24/art, 0% ≥6** — **M** — strict-JSON + retry on the 34% parse failures; v1.2 yield prompt; re-measure.

### P1 — Required for credible launch
4. Calibration ~0 labels, no `fit_status`/margin — M
5. Multi-LLM same-prompt sycophancy; numeric grounding vs source not data — M
6. ada-002 embeddings orphaned — S (decide: deprecate vs backfill)
7. Claims backlog (pending 14+ days; batch=10/2h) — M
8. No per-country coverage SLO; fixed max=5; 116 single-source countries — L
9. Verify-corporate-claim is keyword heuristic, no confidence/provenance — L
10. Quota enforcement inconsistent (5 confirm-mode skills ungated) — M
11. Credibility-scale mapping undocumented (≥4 scales) — M
12. Region↔geography drift guard not in default CI — S
13. Explain-connection depends on async KG with no gating — L
14. `sustainability_score.year_spread` dropped by DTO — S
15. Entity extraction env-spoofed (silent cloud fallback) — M
16. Perplexity silent failure (down vs no-results indistinguishable) — M
17. CDP gated → no Scope-3; `fully_disclosed=9` — M (framing overstated; real)
18. 7 Slice-3 skills lack e2e tests — L

### P2 — Hardening
19. Claim-tertiary no fallback — S · 20. GX10 promotion gate unbuilt — L · 21. Action-click telemetry may silently fail — M · 22. `save_item` no server-side type whitelist — S · 23. company-stats no test; analytics monolithic try/except — M · 24. spaCy→regex silent — M · 25. credibility string-normalization fragility (use ENUMs) — M · 26. CrossRef no 429/backoff — M

### Claims DROPPED (verification = false/overstated)
off-topic enforcement (FALSE — fully wired) · ingestion-not-scheduled (FALSE — Celery+13 crons) · "30% at fallback-50" (OVERSTATED — 6/100) · "99% unverified" (OVERSTATED — 42/58 HIGH/MED) · 3-axis never called (OVERSTATED — consumed in reliability+URL paths) · ND-GAIN unused (STALE — wired since 2026-05-18) · URL-analysis invisible to corpus (STALE — mirror shipped) · embeddings/semantic-search down (OVERSTATED — bge-m3 live) · analyze-report ungated (FALSE — tier-gated) · E.Europe code bias (OVERSTATED — data outcome, not code) · Platt at N≥5 (OVERSTATED — floor 50 enforced) · reliability ignores calibration (OVERSTATED — applied in URL path).

---

## 7. Path to ~95% Country Coverage

Current: **103/193 with data (~53%)**, ~116 single-source (GNews only) → *robust* coverage far below 53%. Target: ≥184/193 with ≥2 independent sources each.

1. **Stop the bleeding (wk1, P0):** fix pan-regional codes (#1) + seed the 6 absent nations (#2).
2. **Seed the registry (wk1–2):** migrate full `eu_feeds_registry.py` (~215 feeds, 87 countries) → `rss_feed_registry` with a deploy-time sync check + `feed_registry_audit` table.
3. **Per-country SLO + balancing (wk2–4, #8):** `country_coverage_targets` table; weekly auditor; boost max 5→10 for deficits; pan-regional backup feeds.
4. **News breadth (wk3–6):** widen `INGESTION_COUNTRIES` (currently only 20); ensure Perplexity discovery covers all 193; native-language sources + translate-at-ingest.
5. **Research + local-context (wk4–8):** promote CrossRef/DOI to `content_type='research_paper'` with author-institution→country mapping; per-country "supporting research" panel.

**Acceptance gate for "95%":** ≥184 countries each with ≥2 active independent sources AND ≥1 article in last 30 days AND correct ISO code (no `XX-*`). Add `/api/map/coverage-status`; wire `test_country_coverage.py` into CI.

---

**Bottom line:** infrastructure is largely production-grade (3.0, rising); the original audits over-indexed on alarming claims that verification dismantled. The honest blockers are narrower but real: a visible map-corruption bug, an indefensible country footprint, an under-yielding/uncalibrated trust engine, a missing GX10 promotion gate. **Waves 1–2 (~3 weeks, mostly S/M) move the composite 3.0 → ~4.0 and make first release defensible.**
