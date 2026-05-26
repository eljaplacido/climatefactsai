# Golden Artifact Examples — 2026-05-27

What "complete" looks like for each of the four user-facing artifact
types on Climatefacts.ai. Written so the GX10 enrichment pipeline + UI
have a concrete quality bar to hit, not just "more data."

## Why now

User feedback (2026-05-27): *"Before we REALLY nail down the GX10
workflow and enrichment, I should be able to see and we should define
the 'golden example' of a reliable news report and analysis + its data
visualizations etc. with also weather context and knowledge graph data
visible. Same with Deep Search, analysis output of research report,
PDF report and Companies."*

Today the platform has all the underlying data tables but renders
none of it as a unified "this is what verified climate intelligence
looks like" view. Live audit of the four artifact types caught:

1. **Enriched article** — best example has 3082-char enriched_excerpt
   + 21 claim rows + 0 entity links (entity worker just started).
   `climate_context_summary` for one Bulgarian article hallucinates a
   "-7.65°C cooling trend over 5 years" — calculation bug.
2. **Deep search** — endpoint is wired, hallucination check runs, but
   no recently-completed example to inspect.
3. **Research / URL analysis** — 12 total `url_analyses` rows, only 5
   `completed`. Best example (YLE Finnish, greenhouse-gas decline)
   has 14 extracted claims but **0 fact_checks + 0 evidence rows** —
   verification step isn't persisting.
4. **Company profile** — 14,797 companies in `companies`, 23,117 rows
   in `company_climate_disclosures` (16 CDP, 23,101 SBTi). Only **9
   companies** have comprehensive data (sbti_validated + net_zero +
   scope1). But `/companies` UI shows "No company data ingested" —
   the FE doesn't JOIN the two tables.

---

## 1. Golden Enriched News Article

### Header strip (always visible)
- Title (cleaned, no HTML markup — `html_cleaner` already applied)
- Source name + **3-axis source credibility chip** (ED/FC/TR pills,
  e.g. `Reuters: ED 90 / FC 92 / TR 88, Tier 1`) ← already shipped in
  `MapCountryPanel.tsx` + `SourceProfileCard.tsx`; surface on article
  card too
- Source country flag emoji
- Published date + estimated reading time
- Overall credibility band (`HIGH / MEDIUM / LOW`) + `Limited Evidence`
  badge when claim count < 3

### Body panels (top → bottom)

**Executive Brief** (100-200 words, current `executive_brief` column,
0% populated today — needs enrichment service to write it)

**Enriched Excerpt** (400-800 words, current `enriched_excerpt`
column, ✅ now being populated by Lane A worker). Should reference
specific claims by ID so the UI can scroll-link them.

**Climate Context Summary** (2-3 sentences, current
`climate_context_summary` column, ✅ being populated). **Bug to fix**:
the 5-yr temperature trend computation in
`article_enrichment_service._fetch_5year_temperature_trend` is
producing impossible values like `-7.65°C` (a small ice age). Either
the math averages incorrectly or the LLM prompt misuses the numbers.

**Weather Card**
- Current temp + humidity + precipitation + weather code
- **Anomaly badge**: `+2.3°C vs historical normal for this month`
- 7-day forecast sparkline
- Source: Open-Meteo (already fetched per article; needs UI render)

**5-Year Temperature Trend Sparkline**
- Annual averages for the article's country
- Direction arrow (warming/stable/cooling)
- Source: Open-Meteo archive API (already fetched; UI render missing)

**Claims Table** (target 5-10 verified claims; today: 1-2 avg, now
lifted to 3-8 via prompt v1.1)
- Claim text
- Type (factual / opinion / prediction)
- Category (scientific_causal / statistical / policy / anecdotal /
  predictive)
- Importance score (0.0-1.0)
- **Verdict pill** (Verified / Disputed / Partially-True / Unverified)
- Evidence preview (link to source article or external URL)
- "Why this verdict?" expand → provenance ledger walk

**Entity Pills** (5-15)
- PERSON / ORG / GPE / LOC / POLICY / TECHNOLOGY / EVENT
- Salience-sorted, top 15
- Each clickable → KG mini-view for that entity

**Knowledge Graph Mini-View** (2-hop neighborhood)
- Force-directed graph with this article in the center
- Entity nodes typed by colour
- Relationship edges typed by label
- Click any node → drill to the canonical entity profile

**Calibration & Confidence**
- Reliability score (0-100) with 90% credible interval
- Calibration status: "Above platform mean" / "Below platform mean"
- Per-axis breakdown bar (source 50% / claims 30% / relevance 20%)

**Provenance Ledger Drawer** (collapsible)
- Each analytical statement linked to: model name, prompt fingerprint,
  retrieval strategy, source article IDs, multi-LLM agreement score,
  hallucination risk score
- Drives the "every verdict traceable" promise

### Current best example (audit, 2026-05-27)
`article_id=3069b470` (Carlsberg Bulgaria beer marketing) —
3082-char excerpt, 21 claims (extracted by ingest-time prompt, none
verified). **NOT a climate-relevant article** — exposes another
issue: the corpus has off-topic articles (beer marketing tagged
`climate_science`). Category misclassification needs a fix.

### Gap → "Golden" fix list
| Gap | Where | Effort |
|---|---|---|
| `executive_brief` 0% populated | enrichment service needs a 3rd LLM call OR re-purpose existing two | 2h |
| `-7.65°C` 5yr trend bug | `_fetch_5year_temperature_trend` math | 30min |
| Entity pills missing from FE | new component + endpoint join | 4h |
| Verdict pills + evidence preview | wire `fact_checks` table → article detail UI | 1d |
| KG mini-view component | new D3/React-Flow widget on article page | 1-2d |
| Calibration breakdown bar | new component + endpoint | 4h |
| Off-topic article filtering | enrichment service should flag + downrank | 1d |

---

## 2. Golden Deep Search Result

### Layout
- Query (echoed) + Cynefin domain classification
- Synthesis paragraph (markdown render)
- **Per-sentence grounding pills** (`HIGH / MEDIUM / LOW / NONE`)
  next to each sentence — backed by `sentence_grounding[]` field
  already returned by low-evidence prompt path
- **Internal citations** (top 10 articles, each with tier chip +
  credibility score)
- **External citations** (Perplexity URLs with **credibility tier
  annotation** ✅ shipped 2026-05-27 polish-3)
- **Weather context card** when locations detected
- **Hallucination check banner**: entity overlap + statistic
  accuracy + LLM grounding scores
- **Refinement suggestions** (3 queries to try next)
- **Methodology drawer**: prompts used + fingerprints + retrieval
  strategy + multi-LLM agreement score

### Current state
Deep search endpoint is fully wired (`deep_search_service.py`).
Hallucination detector now uses spaCy NER in prod (post deploy of
`api/Dockerfile` change). External citations now carry tier +
credibility_score. **Missing**: a saved + replayable "demo query"
that exercises the full chain so we have something to point at as
the golden example.

### Gap → "Golden" fix list
| Gap | Effort |
|---|---|
| Run 3-5 demo queries + save as bookmarkable URLs | 30min |
| Add screenshot to methodology page | 1h |

---

## 3. Golden Research Report Analysis

### Layout
- Document header: title + DOI (if any) + journal + authors +
  publication date + word count + reference count
- **Methodology score** (0-1.0) — does the paper describe methods?
- **Citation score** — density + reputability of references
- **Data transparency score** — open data? code? supplementary?
- **Climate relevance** — high / medium / low + topics
- **Limitations noted** (Yes/No) + **Peer-review indicators** (Yes/No)
- **Bayesian credibility posterior**: prior + posterior + evidence
  count + confidence interval `[low, high]`
- **Key claims** (5-10) with importance ratings
- **Potential biases** list (funding source, sample selection,
  conflict of interest)
- **Recommendation**: cite / use with caution / dispute

### Current state
`url_analyses` table has 12 rows, 5 `completed`, 7 `failed`. Best
example: YLE Finnish article on greenhouse-gas emissions (14 claims,
zero fact_checks). **Verification step doesn't persist fact_checks
or evidence** — this is the biggest gap.

The user's PDF upload of `NetZeroby2050-ARoadmapfortheGlobalEnergySector_CORR.pdf`
errored with "couldn't fetch" — needs investigation. Likely:
- The frontend sends the file to `/api/research/upload` (POST
  multipart) but the page logic may be hitting `/research/analyze`
  with a URL parameter only (no upload field). Code is at
  `src/frontend/src/app/research/page.tsx`. The "upload" tab is
  present but may not be wired to the correct endpoint.

### Gap → "Golden" fix list
| Gap | Effort |
|---|---|
| PDF upload "couldn't fetch" error | debug `/research/page.tsx` upload mode → /api/research/upload | 2h |
| fact_checks + evidence persistence | wire url_analysis pipeline to write rows | 1d |
| Methodology/citation/transparency scores in UI | new component | 4h |
| Bayesian posterior chart | new component (matplotlib → svg / vega) | 4h |

---

## 4. Golden Company Profile

### Layout
- Name + ticker + country flag + ISIN/LEI/sector code
- **Sources panel**: CDP / SBTi / NZT chips with last-fetched
  timestamps
- **Emissions block**:
  - Scope 1 (direct) tCO2e — with year + bar chart vs baseline
  - Scope 2 (market-based + location-based) tCO2e
  - Scope 3 (value chain) tCO2e — typically dominant
  - **Assurance level** + provider chip
- **Targets block**:
  - Net-zero target year (with countdown)
  - Interim target year + % reduction vs baseline year
  - **SBTi validation badge** (validated / committed / not committed)
- **ECGT compliance check**:
  - Any `offset_based_claims` flagged?
  - Verdict: compliant / non-compliant / unclear
  - **CSRD/IFRS S2/TCFD/TNFD compliance chips**
- **Per-claim verification log**: every corporate claim the platform
  has analyzed (from `company_claims` table — currently 0 rows)
- **Methodology disclosure**: reporting_year + methodology_version

### Current state (live DB)
14,797 companies; 23,117 disclosure rows (16 CDP + 23,101 SBTi).
**Apple, Alphabet, Microsoft, ~9 in total** have comprehensive data
(sbti_validated + net_zero + scope1/2/3). Example:

```
Apple Inc. (AAPL) [US]
  source: cdp, reporting_year: 2024
  scope1: 55,400 tCO2e, scope2_market: 0, scope3: 14,800,000 tCO2e
  scope1_2_verified: True, sbti_validated: True
  target_year: 2030, baseline: 2015, reduction: 75%
  net_zero_target_year: 2030
  assurance_level: reasonable
```

**Why `/companies` shows "No company data ingested" despite this data
existing**: the `/api/companies` endpoint queries the bare `companies`
table without joining `company_climate_disclosures`. The 14,797
companies have no climate-data columns on the master table itself.
UI joins missing.

### Gap → "Golden" fix list
| Gap | Where | Effort |
|---|---|---|
| `/api/companies` JOIN to climate_disclosures | `company_routes.py:list_companies` | 2h |
| Companies index filter "with climate data only" | FE + API | 1h |
| Emissions bar chart | new component | 4h |
| ECGT verdict surfaced | existing ECGTKeywordMatcher results need UI render | 4h |
| Per-claim verification log | populate `company_claims` via analyze flow + render | 1d |

---

## Cross-cutting fixes (small + high-impact)

1. **Companies UI shows "No company data"** — wrong query, the data exists.
   Fix `company_routes.py:list_companies` to JOIN + filter.
2. **Research PDF upload "couldn't fetch"** — `/research/page.tsx`
   upload mode wiring.
3. **Temperature trend hallucination (-7.65°C)** —
   `article_enrichment_service._fetch_5year_temperature_trend` math
   audit.
4. **fact_checks + evidence not persisted** for `url_analyses` rows —
   verification pipeline write step missing.
5. **`executive_brief` 0% populated** — enrichment service should
   write this column too.
6. **News-feed-style /research listing** — currently /research is an
   upload form + subscription panel. Add an articles-list panel
   showing the per-user feed items + default-topic items.

These six unblock 80% of the "golden example" gap. Sequence: 4-6
hours of UI/backend work each, can be done in any order.

---

## Sequence proposal

**Hour 0-4**: Fix companies UI JOIN + research PDF upload error (highest
visible impact, blocking the user from inspecting things at all).

**Hour 4-12**: Temperature trend bug + executive_brief population +
fact_checks/evidence persistence (these make the per-article golden
example real). Then re-run enrichment on a sample so the user can see
a complete example.

**Day 2**: News-feed-style /research listing + entity pills on article
page + verdict pills + ECGT chips on company page.

**Day 3-4**: KG mini-view + calibration breakdown bar + Bayesian
posterior chart (the visual-rich surfaces).

After all that, GX10 enrichment runs against a code path that
actually populates every field a Golden Example needs, and the FE
renders them. We then re-evaluate the bar.
