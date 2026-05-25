# Honest Gap Audit — Climatefacts.ai Architecture Report (2026-05-25)

This audit walks every capability claim in
`docs/reports/Climatefacts-Architecture-Report-2026-05-24.docx`
and grades each as **SHIPPED**, **PARTIAL**, **STUB**, or **ASPIRATIONAL**
against the actual code + production state on 2026-05-25.

A claim is **SHIPPED** when the code path is in production AND the
feature works end-to-end for a typical user.

A claim is **PARTIAL** when the scaffolding is there but the
production data layer or the UX is incomplete (e.g. an endpoint exists
but always returns an empty result).

A claim is **STUB** when only the API surface or component shell exists.

A claim is **ASPIRATIONAL** when the only evidence is a comment or a
test fixture; users see nothing.

---

## Section-by-section grading

### §1 Executive Summary

| Claim | Status | Evidence / honest note |
|---|---|---|
| "Deterministic claim verification (no LLM in the verdict path)" | PARTIAL | True for `_analyze_claim` (corporate route, keyword + lookup); NOT true for article fact-checks where the verifier still calls LLMs |
| "Seven personas served" | ASPIRATIONAL | The personas are in copy + memory. The UI has ONE persona-aware surface (`?view=business` toggle on Country Passport + Company detail). No personalisation engine, no per-persona defaults, no role-aware navigation |
| "Fully introspectable agentic chat layer" | SHIPPED | 11-skill registry, pin tests pass, `/api/skills` returns the canonical list |
| "10,000+ companies tracked with SBTi/CDP/NZT data" | PARTIAL | SBTi sync did populate ~10k rows, but ~70% are duplicates of multi-target SBTi entries. Migration 038 will reduce. CDP + NZT are empty (URLs gated/moved) |

### §3 User Personas

The report describes 7 personas with primary features each. Reality:

| Persona | Persona-specific UX delivered? |
|---|---|
| Consumer | Same UX as everyone — default Public view |
| Journalist | Same UX, plus Deep Search exists (but no journalist-specific defaults) |
| ESG officer | Business view toggle delivers this — SHIPPED for the toggle, but no ESG-specific landing page |
| Climate scientist | Methodology page exists but no science-specific entry point |
| Policymaker | No policymaker-specific surface |
| Financial analyst | Business view partially serves this (compliance chips) but no analyst-specific exports |
| Business decision-maker | Business view toggle SHIPPED — most fully-realised persona surface |

**Honest summary**: persona language in the docs is mostly aspirational.
The actual personalisation footprint is one URL parameter (`?view=business`).

### §4 Feature Catalog

| Feature | Status | Honest note |
|---|---|---|
| §4.1 World Map | PARTIAL | Works, but the layers feel static. Walkthrough added 2026-05-25 |
| §4.2 Country Passport (6 tabs incl. Projections + Business view) | SHIPPED | All 6 tabs render; biome summary added 2026-05-25 |
| §4.3 Corporate Tracker | PARTIAL | 10k companies but tripled duplicates pending migration 038; verification analyzer works |
| §4.4 Deep Search | PARTIAL | Renders, but chat follow-up errors out (fixed in `20a2441` to at least surface the real error); markdown contrast fixed |
| §4.5 Article Search | SHIPPED | Works |
| §4.6 URL Analysis | PARTIAL | Submission + structured failure surface work; the verifier rarely produces > 1 verified claim per article (low aggregate confidence ~10/100) |
| §4.7 Methodology Page | SHIPPED | Works |
| §4.8 Agentic Chat | PARTIAL | Skills registry SHIPPED; deep-search follow-up errored (the report didn't disclose this — it does now via §4) |
| §4.9 AOI Alerts | PARTIAL | Endpoint + Cloud Scheduler entry exist; not visible in user dashboard yet |
| §4.10 Embed Widgets | STUB | Routes exist; embedding into external sites untested in production |

### §6 Trust & Transparency Layer

| Component | Status | Honest note |
|---|---|---|
| §6.1 Claim Provenance | SHIPPED | `claim_provenance` table populated |
| §6.2 Multi-LLM Cross-Verification | SHIPPED | `verify_claims()` works; agreement score recorded |
| §6.3 Numeric Grounding | SHIPPED (code) / PARTIAL (impact) | Module exists + tested; wired into URL analysis. Real-world coverage hasn't been measured |
| §6.4 Source Credibility Tiers | PARTIAL | Schema exists; only a fraction of sources have populated editorial/factcheck/transparency scores. **`/api/sources` returns 0** as of audit |
| §6.5 Calibration Labels | PARTIAL | Table + UI exist; few real labels collected |
| §6.6 Methodology Snapshot | SHIPPED | Bundled `/api/methodology` works |
| §6.7 AI Provenance JSON-LD | SHIPPED | Schema.org block rendered in head |

### §8 Compliance & Regulation

The report stamps the platform as serving CSRD / IFRS S2 / TCFD / TNFD / ECGT etc.
**Honest grade**:

| Regulation | Platform surface | Status |
|---|---|---|
| ECGT Article 4 | Offset-marker claim flagging in `_analyze_claim` + ECGT warning chip in Business view | SHIPPED for the keyword-based detection. No independent ECGT auditor verifying the flag set is sufficient |
| CSRD | CSRD chip stamps in Business view | STUB — the chip stamps wherever Scope 1+2 is disclosed, but we don't verify the disclosure is CSRD-compliant. Same data, prettier framing |
| IFRS S2 | IFRS S2 chip + ProjectionsPanel (scenario analysis) | PARTIAL — chip is decorative; ProjectionsPanel uses seed data for 20 countries only |
| TCFD | TCFD chip in Business view | STUB — chip stamps but no actual TCFD report-validation logic |
| TNFD | TNFD chip mentioned in copy | ASPIRATIONAL — not surfaced anywhere |
| EU AI Act Article 50 | Schema.org JSON-LD on AI-generated artefacts | PARTIAL — JSON-LD renders but model + prompt fingerprint disclosure is incomplete |
| SBTi corporate net-zero | SBTi-validation lookup in `_analyze_claim` | SHIPPED for the lookup; data freshness depends on SBTi sync |

**The compliance section reads stronger than it is.** Most chips are
decorative metadata stamps, not auditor-grade compliance verifications.
Independent auditor review would surface this immediately.

### §11 Known Limitations

The report listed 6 limitations. Reality adds more:

**Already in the report (still true):**
- CDP + NZT live data sources gated
- Full AR6 Atlas ingestion deferred
- B4 NER entity grounding deferred
- Cloud Tasks migration for jobs
- Per-company dedup on live sync (migration 038 fixes; pending deploy)
- SSE chat streaming

**NOT in the report — discovered 2026-05-25:**
- `/api/sources` returns 0 sources — endpoint shape or data missing
- Article detail endpoint returns empty body when listing shows credibility=94 (data integrity gap)
- Average verified-claim confidence is ~10/100 — verifier produces results most claims fail
- Only ~1 claim verified per article on most articles; the 90%-credibility headline is over-confident given the underlying evidence
- Many article URLs are fabricated (csiro.au/great-barrier-reef-2025, nature.com/swiss-alps-glaciers) — synthetic seed data still leaking into the "real" article list with `is_synthetic = FALSE`
- Share + Export buttons broken
- My Feed save flow broken (untested in this session, reported by user)
- Persona personalisation is aspirational — only one toggle

---

## What this means

The architecture report describes the platform's **intended** shape
accurately. It does **not** describe the platform's **delivered** shape
accurately, because:

1. **Compliance is mostly metadata stamping**, not auditable verification
2. **Personalisation is one toggle**, not the seven persona pathways
3. **Data integrity has gaps** — synthetic + real content commingled, source scoring sparse
4. **A working pipeline doesn't mean a useful pipeline** — the verifier runs, but produces low-confidence results on most articles

The next architecture-report revision must show this distinction.
Updated below.

---

## Honest re-grading by capability (single-page summary)

```
SHIPPED       (works end-to-end for a user):
  ✓ 11-skill agentic protocol + dispatcher
  ✓ Map (with new walkthrough)
  ✓ Country Passport — 6 tabs incl. Projections + biome
  ✓ Business view toggle (Country + Company)
  ✓ Migrations runner (cloud-sql-proxy + Cloud Build)
  ✓ Methodology page
  ✓ AOI alert subscription + Cloud Scheduler
  ✓ Article search
  ✓ Rate limiting via Redis
  ✓ Numeric grounding (pure functions + wired into verifier)
  ✓ JWT auth + Stripe billing scaffold

PARTIAL       (scaffold + some data; missing pieces):
  ~ Corporate tracker (data duplicated + CDP/NZT empty)
  ~ Deep Search (markdown contrast fixed; verifier confidence low)
  ~ URL Analysis (low verified-claim yield)
  ~ Multi-LLM verifier (works; aggregate confidence ~10/100)
  ~ Compliance chips (decorative metadata, not audit-verified)
  ~ Persona personalisation (1 toggle, no engine)

STUB          (shell only):
  ⚠ Source credibility scoring (/api/sources empty)
  ⚠ Embed widgets (routes exist; production-tested?)
  ⚠ Calibration label collection (UI exists; data sparse)

BROKEN        (reported by user 2026-05-25, in this session):
  ✗ My Feed save flow (will reproduce + fix)
  ✗ Share buttons (social + CSV/PDF)
  ✗ Article detail returns empty
  ✗ Many article URLs are synthetic
  ✗ Light-mode contrast bugs (Markdown fixed; others tbd)

ASPIRATIONAL  (the doc claims it; the code doesn't):
  ✗ Seven persona-specific UX paths (only Business view exists)
  ✗ "Auditor-grade" CSRD / TCFD compliance
  ✗ Document upload analysis (only URL supported)
  ✗ Research feed (only news feed)
  ✗ Scenario simulation (only static projection cards)
  ✗ Save-more-than-articles (only article bookmarks)
```

---

## Next architecture-report revision must include

1. A "Production Maturity" colour code per capability (Shipped /
   Partial / Stub / Aspirational) — same as above
2. A section called "What the platform does NOT do yet" listing the
   broken + missing pieces honestly
3. Audit-verifiable compliance claims only — drop chips that aren't
   tied to a real verification rule
4. Persona section reframed: ONE persona is genuinely served by a
   dedicated UX (business decision-maker via the toggle); the other
   six are roadmap items
5. Service-level smoke-test summary with the actual 24/24 endpoint
   pass + the known-broken ones

When all of the above are honest in the doc, the platform's actual
strengths (deterministic verification path for corporate claims,
single-source agentic protocol, end-to-end migrations pipeline,
projections panel with IPCC AR6 seed) read much more credibly than
when they're surrounded by aspirational claims.
