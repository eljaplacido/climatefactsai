# Knowledge Graph Robustness Audit — 2026-05-27

Honest evaluation of whether the current KG can do multi-hop reasoning,
and sequencing for the property-graph upgrade proposed in
`Semanticgraphlayerimprovements.md`.

User question (2026-05-27): *"REALLY evaluate is it robust enough to
provide multihop reasoning capabilities for users."*

**Short answer: no.** The KG today is a 4-table relational shadow that
gives plausible "related articles" but cannot answer the multi-hop
support/contradiction questions the product promises. The right move is
the four-layer design from `Semanticgraphlayerimprovements.md`, sequenced
over 6-8 weeks. Until then the platform should stop framing the KG as a
reasoning surface and instead expose it as an entity-overlap retriever.

---

## 1. What we have today

### 1.1 Schema (legacy migration `migrations/versions/013_knowledge_graph.sql`)

Four tables exist conceptually:
- `entities (entity_id, entity_name, entity_type, ...)`
- `entity_aliases (alias, entity_id)`
- `entity_relationships (from_entity, to_entity, rel_type, strength)`
- `article_entities (article_id, entity_id, salience)`

**Critical caveat**: this migration lives ONLY in the `migrations/`
directory (legacy path). The canonical
`infrastructure/database/migrations/versions/` tree (which Cloud Build
runs on every deploy) does NOT contain it. End2End audit (2026-05-26)
verified `/api/methodology/audit-trail/article/<id>` returns `total: 0`
and the KG endpoint returns HTTP 500 in production. The schema is
defined but not deployed.

### 1.2 Retriever (`src/backend/app/domains/intelligence/graph_retriever.py`)

`GraphRetriever.retrieve()` is a 3-step BFS:
1. Match query words against `entity_name` via case-insensitive `ILIKE`.
2. Recursively traverse `entity_relationships` up to `max_hops=2`.
3. Collect articles via `article_entities` join along the path.

Each article is annotated with a path explanation
("Entity A → REL → Entity B → ABOUT → Article X").

### 1.3 What works

- The entity-overlap BFS in `hybrid_rag_service.py` (fused via RRF with
  pgvector + FTS) does improve recall vs vector-only retrieval for
  entity-anchored queries (e.g. "EU CBAM ruling 2026").
- The 2-hop walks return *plausibly related* articles for popular
  entities like "IPCC", "EU", "Germany".

### 1.4 What's broken or missing

| Gap | Impact |
|---|---|
| Migration never landed in canonical tree | `/api/articles/{id}/kg` returns 500 in prod |
| No NER worker populates `article_entities` | Even if schema deploys, the rows are empty |
| Entity dedup = ILIKE substring match | "EU" matches "European Union" *and* "Europe" *and* "deus" |
| No canonical entity store | Same real-world entity surfaces as 3-5 rows under different names |
| `entity_relationships` rows are sparse | The relationship table is populated by LLM extraction that hasn't been triggered for the live corpus |
| BFS has no relation typing | "RELATED_TO" dominates; can't distinguish SUPPORTS / CONTRADICTS / CITES |
| No claim-as-node design | Claims live as JSONB on articles, so multi-hop claim chains are structurally impossible |
| No graph DB | All traversal is recursive CTE in PG, which scales poorly past 100k entities + caps at 2-3 hops in practice |

### 1.5 Honest assessment vs the multi-hop promise

The product surfaces (chat, deep-search, methodology) frame the KG as a
reasoning layer. That framing is aspirational. What the KG *can*
actually do today:

- ✅ Find articles that share entities with a query.
- ✅ Annotate retrieved articles with which entity match drove the hit.
- ❌ Answer "what does Source X say about Topic Y, and how is it
  contradicted by Source Z?" — there's no SUPPORTS/CONTRADICTS edge.
- ❌ Path-score "EU → CBAM → steel industry → German emissions" — the
  relationship typing is too coarse and the entity dedup too weak.
- ❌ Answer time-bounded queries like "what was the IPCC position on
  CDR in 2024 vs 2026" — no validity windows on edges.
- ❌ Power "controversy maps" or "support/contradiction networks"
  surfaces — those need claim-as-node + stance edges.

The audit framing of "shadow KG" in
`Semanticgraphlayerimprovements.md` is accurate.

---

## 2. Should we build the full property graph?

Yes, but staged. The cost/benefit:

**Build (~6-8 weeks, sequenced):**
- Unlocks the truth-engine framing the platform is sold on.
- Differentiates from Climate Watch / OWID / Climate TRACE (none of
  them surface stance graphs).
- Enables board-ready / journalist-ready "show me the contradictory
  evidence" workflow that ESG + Journalist personas need.

**Don't build yet (defer 3-6 months):**
- Only justified if we can ALSO commit to operating Neo4j + a CDC
  pipeline + an NER worker fleet — that's real infra weight.
- A weak entity-resolution layer over a strong graph is worse than
  a strong entity-resolution layer over a weak graph; the prior
  audits flag entity dedup as the #1 retrieval ceiling.

**Recommended path** (3-phase, each phase ships independently):

### Phase 1 — Foundations in Postgres (2 weeks)

Land canonically, no new DB. This is the highest-leverage chunk and
unlocks Phase 2 without infra change.

1. Promote `migrations/versions/013_knowledge_graph.sql` into the
   canonical `infrastructure/database/migrations/versions/` tree as
   mig 049 with `@notolerate` and an idempotency check.
2. Add the `canonical_entities` table:
   ```sql
   canonical_entities (
     canonical_id UUID PK,
     name TEXT, type TEXT,
     aliases TEXT[], wikidata_qid TEXT, wikipedia_url TEXT,
     country_code CHAR(2),
     confidence NUMERIC(3,2)
   )
   ```
3. Split `EntityMention` from `CanonicalEntity` — mentions point at
   the article + offset, canonical owns the dedup'd identity. Use
   `pg_trgm` GIN index on `name` + `aliases` for fuzzy match.
4. Wire an NER worker (the spaCy `en_core_web_sm` we just installed in
   the API Dockerfile) into a new Celery task
   `intelligence.extract_entities_for_article`. Backfill via the
   admin/scheduler pattern we used for enrichment.
5. Add `claim_entity_mentions` join so claims become first-class
   participants in entity-anchored retrieval without moving them out
   of `claims`.

**Outcome:** entity-overlap retrieval becomes 5-10× more precise, KG
endpoint returns real data, NER is real in prod. No new infra.

### Phase 2 — Property graph plane (3 weeks)

After Phase 1 settles for 2 weeks.

1. Deploy Neo4j Community (or Memgraph / KuzuDB if we want embedded).
   Cloud Run sidecar in the same VPC. Single instance with snapshots
   to GCS daily.
2. Build a CDC sync from Postgres → Neo4j via Debezium or a
   periodic batch job (every 15 min). Nodes:
   `Article, Claim, EvidenceSpan, CanonicalEntity, Source, Country,
   Company, Metric, ProjectionSeries, Regulation, Event,
   AnalysisRun, PromptFingerprint`.
   Edges:
   `ASSERTED_IN, SUPPORTED_BY, CONTRADICTED_BY, MENTIONS, SAME_AS,
   ABOUT_COUNTRY, ABOUT_COMPANY, REGULATED_BY, PROJECTS, CITES,
   DERIVED_FROM, GENERATED_BY` — each with `valid_from / valid_to /
   confidence / provenance_id / extraction_method` properties.
3. Switch `graph_retriever.py` to a Cypher driver instead of recursive
   CTE. Keep the Postgres path as a feature-flagged fallback for
   safety during cutover.
4. Add `/api/graph/path` endpoint that returns a Cypher-shortest-path
   between two entities + the supporting evidence per edge.

**Outcome:** real multi-hop traversal, stance-typed edges, validity
windows, sub-100ms p50 for 3-hop walks at the current corpus size.

### Phase 3 — Stance-aware retrieval + agent integration (2-3 weeks)

After Phase 2 settles for 1 week.

1. Train (or fine-tune) a small stance classifier on
   `ClimateFEVER + ClimateX` to label `SUPPORTED_BY / CONTRADICTED_BY`
   edges between claims and evidence spans. Use the GX10 for batch
   inference once that's wired.
2. Add a `Reasoning` agentic skill that takes a claim, walks the
   graph for SUPPORTED_BY + CONTRADICTED_BY edges across N hops,
   ranks evidence by source-tier + freshness + agreement, and
   returns a structured "support / contradiction / data gap" view.
3. Surface "Controversy map" + "Support network" + "Time-evolution"
   visualisations on the article + claim detail pages using the
   graph topology directly (D3 or React-Flow).

**Outcome:** claim-first retrieval, the agentic surface for journalist
+ ESG personas, the visualisation layer that differentiates the
product.

---

## 3. What we should ship THIS week to make the gap honest

Independent of Phase 1, three small honest-framing changes:

1. **Soft-fail KG endpoint** (similar to what we just did for weather):
   `/api/articles/{id}/kg` should return `200` with `{nodes: [],
   edges: [], status: "kg_not_populated"}` instead of 500. The
   frontend already handles the empty-state branch (commit `3e01649`).
2. **Methodology page section**: add a "Knowledge graph status" block
   that honestly says "shadow graph today, property graph in
   roadmap" with a link to this doc.
3. **Stop the chat skill from offering KG walks** for now — gate it
   behind a `CLILENS_KG_LIVE` env flag, default off, until Phase 1
   lands.

---

## 4. Per-persona blast radius of NOT building the graph

| Persona | Workaround works today? |
|---|---|
| Consumer | Yes — they don't need multi-hop, just credibility chips. |
| Journalist | Partial — provenance ledger + multi-LLM agreement covers most workflows; "show me contradictions" is the gap. |
| ESG Officer | Yes — SBTi + ECGT are deterministic per-company, not graph-bound. |
| Researcher | Partial — research feed + uploaded reports work; cross-paper "X cites Y who contradicts Z" doesn't. |
| Policymaker | Yes — country passport + scenario explorer are non-graph. |
| Financial Analyst | Partial — per-company works; portfolio "find common transition-risk exposure across my 50 holdings" needs graph. |
| Business Decision-maker | Partial — country/company snapshots work; supply-chain "find my Tier 2 suppliers with greenwashing flags" needs graph. |

The gap concentrates on the high-value B2B personas (Journalist, ESG,
Analyst, Business) — which is exactly where the willingness-to-pay
sits. That justifies the 6-8 week investment whenever resourcing
permits.

---

## 5. Bottom line

The current KG can power *entity-overlap retrieval* with honest
framing. It cannot power *multi-hop reasoning* in a way that holds up
to journalistic or audit scrutiny. The right move is:

1. This week: soft-fail the broken endpoint, update methodology copy,
   ship the canonical NER worker + mig 049 promotion. (1-2 days.)
2. This month: Phase 1 (Postgres property-graph foundations + entity
   resolution). (2 weeks.)
3. This quarter: Phase 2 (Neo4j plane + Cypher traversal). (3 weeks.)
4. Next quarter: Phase 3 (stance classifier + claim-first retrieval +
   visualisation). (2-3 weeks.)

Until Phase 2 lands, do NOT market the platform as a "multi-hop
reasoning" system. Frame it as "entity-anchored hybrid retrieval with
deterministic verification" — which is what it actually is.

---

End of doc — `docs/improvementplans/KG-Robustness-Audit-2026-05-27.md`
