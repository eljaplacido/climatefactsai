# Climatefacts.ai — Strategic Analysis & Best-in-Category Roadmap

**Analysis date:** 18 May 2026
**Subject:** Platform report v 2026-05-18 (branch `main` @ `edb0a23`; rebrand `1b96d3a`)
**Owner:** CISU Regen
**Scope:** Positioning vs. 2026 climate/sustainability/AI-transparency landscape, mission fit, and feature/UX recommendations to establish the platform as the category standard for climate data reliability, transparency, and traceability.

---

## 0. How to read this analysis

This is not a re-audit of what your own audits already cover. Your in-house auditing is unusually honest — the 4.78/5 vs. 3.6/5 gap is exactly the kind of self-correction most platforms don't do, and you've already itemised most of the technical debt. What I'm adding is:

1. **External fit** — does what you've built map onto where the climate-data market and regulation are actually moving in 2026?
2. **Standard-setting features** — what does "best in category" look like, beyond closing your known gaps?
3. **Sequencing** — given a fixed amount of build capacity, what compounds.

Where I disagree with the report's framing, I say so directly.

---

## 1. The 2026 context the platform is launching into

Five regulatory and market currents are converging in the back half of 2026. Climatefacts.ai is closer to being on the right side of all five than almost any platform I can see — but it has to act deliberately on each one.

### 1.1 ECGT (Empowering Consumers for the Green Transition) — applies 27 September 2026

This is the single most important regulatory event for your platform's relevance. The EU adopted the ECGT in February 2024; member states must transpose by 27 March 2026 and the rules apply from 27 September 2026 — about four months after this report's date. The Green Claims Directive (the ex-ante verification regime) was withdrawn in June 2025, but ECGT was *already* law and is unaffected.

What ECGT does is:

- Bans generic environmental claims ("eco-friendly", "green", "sustainable") without substantiation
- Bans offset-based product-level "climate neutral" labels
- Adds these to the EU blacklist of unfair commercial practices, with penalties up to 4% of annual turnover or €2M

The UK's CMA published parallel "Green Claims" guidance in January 2026 that *expands liability up the supply chain* — companies are now legally responsible for misleading environmental claims made anywhere in their supply chain, not just claims they make directly.

**Why this matters for Climatefacts.ai:** Your platform is structurally a verification engine for environmental claims. From 27 September 2026, every European company making a climate-related marketing statement needs an *audit-ready substantiation trail* — exactly what your `claim_provenance` table records. Your enterprise tier (governments & partners) has just been handed a regulatory tailwind. There's a B2B SaaS product here ("claim substantiation as a service") that the current pricing page doesn't reflect.

### 1.2 EU AI Act Article 50 — applies 2 August 2026

The transparency obligations of the EU AI Act enter into force two months before ECGT. Two clauses bite directly:

1. **AI-system interaction disclosure** — users must be informed when they are interacting with an AI system (your chat, deep-search, URL analysis all fall under this).
2. **AI-generated content labelling for "text published with the purpose to inform the public on matters of public interest"** — this is *exactly* what Climatefacts.ai produces. Deep-search synthesis, agentic chat answers, country briefs and (planned) auto-produced videos are squarely in scope.

The Commission published a second draft Code of Practice on Marking and Labelling of AI-generated content on 5 March 2026; a third final draft is expected by June 2026. From 2 August 2026 the Commission's enforcement powers enter into application.

**Why this matters:** Your methodology surface and provenance trail are already 80% of the way to an Article 50-compliant disclosure regime. The gap is presentation: every AI-produced surface needs an unambiguous, machine-readable, persistent label (not buried in a drawer). Done right, this becomes a *visible competitive differentiator* — most consumer-facing climate apps will be scrambling to retrofit this in August.

### 1.3 ISSB / IFRS S2 globalisation — accelerating through 2026/27

As of January 2026, 21 jurisdictions have adopted IFRS S2 on a voluntary or mandatory basis, including Chile, Qatar and Mexico mandating from 1 January 2026. The ISSB published targeted IFRS S2 amendments in December 2025 (effective for periods beginning on or after 1 January 2027) and is preparing an exposure draft for nature-related disclosures (October 2026), drawing on the TNFD framework.

CDP's 2026 questionnaire is structurally aligned with IFRS S2 and is the de facto delivery channel for IFRS S2-aligned data (10,413 disclosures in 2025, two-thirds of global market cap). EFRAG and CDP published the official ESRS E1 ↔ CDP "Correspondence Mapping" in March 2025.

**Why this matters:** The corporate-disclosure data layer you don't yet have (Sprint B in §8.4 of the platform report — CDP + SBTi + Net Zero Tracker) is the *commercial* moat. Six country-level indicator adapters are the right foundation, but country-level signal cannot anchor company-level claim verification, which is where the regulatory bite of ECGT and CSRD lands. Wave 1 CSRD reports (300+ analysed) showed massive variation in structure, scope and double-materiality interpretation — there's a genuine market opening for a *neutral, audit-trail-first* comparison surface that no existing platform fills well.

### 1.4 COP30 Declaration on Information Integrity on Climate Change

Launched in Belém in November 2025 and EU-backed. It commits signatories to factual debate, evidence-based policymaking, and a "firm commitment" to climate-science integrity in public discourse. This is a *political tailwind* rather than a regulation, but it shifts the funding and procurement environment: governments, IGOs and journalism foundations now have an explicit mandate to back climate-truth infrastructure.

**Why this matters:** Your tagline ("Trust as a Service") and your mission ("anyone, anywhere, in any language, fact-checked climate news") map almost word-for-word onto the Declaration's text. You have a credible application story for EU Horizon, climate journalism foundations (e.g. European Climate Foundation, Earth Journalism Network), and the rapidly growing pool of foundation funders backing climate-information infrastructure post-COP30.

### 1.5 The generative-AI-disinformation feedback loop

Three reinforcing dynamics in 2026:

- **AI chatbots themselves spread climate disinformation** — Global Witness's COP30 testing found mainstream chatbots proactively sharing climate-contrarian framings to "susceptible" users.
- **AI sycophancy** is now a recognised failure mode — generative systems agreeing with their users' priors, including conspiracy framings.
- **Deepfakes have crossed a usability threshold in 2026** — accessible to anyone with a smartphone, eliminated earlier tell-tale glitches. The WEF flagged this as 2026's defining cognitive-manipulation vector.

Academic infrastructure has caught up faster than it usually does. The CARDS classifier (John Cook's Augmented CARDS detects climate misinformation roughly 90% of the time) and the ClimateCheck 2026 shared task (scientific fact-checking + disinformation narrative classification, second iteration with tripled training data) are now publishable, citable assets you can build on.

**Why this matters:** Your hallucination detector, multi-LLM verifier and KL drift detection are genuinely on the frontier *for the platforms that have them at all*. The category as a whole is conspicuously absent. There is no household-name "climate Snopes." You are competing against AI-generated slop on one side and traditional media on the other, both with structurally weaker provenance than yours.

---

## 2. Mission fit — honest assessment

The platform's stated mission is to act as a global source of truth for climate data, where every claim ships with evidence, calibrated confidence, and per-call provenance. Three dimensions of fit:

### 2.1 What the platform delivers on today (genuinely)

- **Per-LLM-call provenance with model + prompt + version + SHA-256 fingerprint** is rare. Most "AI-powered fact-checking" platforms cannot tell you which model produced which sentence with which retrieval strategy at which date. You can.
- **Versioned prompt registry** with public methodology surface — this is the single hardest thing to retrofit and you've already done it. It is the only structural defence against silent prompt drift, and it's what makes your platform auditable in the EU AI Act sense.
- **Calibration math (Platt scaling, Brier, ECE)** with a refit pipeline is, again, frontier for the category. Almost no public climate-information platform exposes calibration metrics at all.
- **Domain-driven backend** with the intelligence/ layer cleanly separated from content/ — this matters because the truth-machine logic is the licensable asset. Partners can buy "trust as a service" without buying the whole news aggregator.
- **Indicator adapter framework with idempotent upsert + sync logs** — this is the right shape for a regulatory data platform. Most ESG-data platforms hide their ingestion pipelines.

### 2.2 Where the mission is undermined by current state

I'll be blunter than the in-house audit:

1. **The RSS-summaries-not-bodies gap is a credibility-bombing risk.** Every downstream signal (claims, hallucination, embeddings, search) runs on title + 500-char summary. If this leaks externally before it's fixed, the platform's truth-machine framing becomes its biggest reputational liability. This is *the* P0 — the 3–4-hour fix the report mentions should ship before any external launch, before any pitch deck, and before any of the agentic-chat or video-pipeline work. Nothing else competes with this.

2. **Synthetic seed articles visible on user-facing surfaces** is a related credibility risk in a different shape. Migration 025 added the flag; without the frontend filter the flag is invisible to the user. Same priority as #1 — finish the job.

3. **Calibration `min_labels=5` is not honest calibration**, and the audit is right. With <50 labels Platt parameters are noise; the worst version of this is that the platform displays a calibrated number that's actually less informative than the raw score, with a UI affordance that implies extra rigour. Until labels grow, *don't apply* the fit and badge it as preview — the platform should be honest about its own limits in exactly the way it asks news sources to be.

4. **Multi-LLM verification with a shared prompt is a known anti-pattern.** The report flags this honestly. Two models with the same prompt fail correlatedly; agreement is no longer independent evidence. Either run *different* prompts for the verifier (paraphrased to vary surface form but preserve intent) or, better, add a *numeric grounding check* against `country_indicators` as the audit recommends — corroboration without numeric grounding should not bump confidence.

5. **Hallucination check semantics are not what the name implies.** Set-intersection on capitalised n-grams is going to over-flag legitimate numeric synthesis (numbers don't appear as entities) and under-flag entity hallucination (a fictional NGO with a plausible capitalised name will pass). NER + structured-fact alignment is the standard the platform is implicitly claiming. Until that lands, consider re-labelling this internally as "grounding signal" rather than "hallucination detector" so the methodology page doesn't oversell.

6. **The score gap (claimed 4.78 vs. audited 3.6)** is the right number to fix, but it should be surfaced *publicly* on `/methodology`, not just in `docs/audits/`. Showing the world both numbers and the remediation roadmap is the most powerful trust signal the platform can send — it is the perfect inversion of what greenwashers do. Treat the audit gap as marketing, not embarrassment.

### 2.3 The mission gap nobody on the team has named yet

The platform is built to verify *news* about climate. The 2026 regulatory environment (ECGT, CSRD, IFRS S2) is overwhelmingly about verifying *corporate climate claims*. These are different objects with different signals, and the platform currently treats them as similar enough to share the same pipeline.

A corporate net-zero claim has structured features a news article doesn't: a stated target year, a baseline year, a scope (1/2/3), a verification body, a methodology version, an assurance level, and a track record of restatements. The platform's six indicator adapters are country-level — they don't anchor corporate claims at all.

This is the largest strategic gap. Sprint B in the roadmap names it (CDP + SBTi + Net Zero Tracker adapters, `company_climate_disclosures` schema), but it's framed as "Wave 7 future" — i.e. after the cloud cut-over. Given ECGT goes live in September 2026, **this should be the next major phase after the data-integrity P0s, not a deferred sprint.**

---

## 3. Competitive positioning

Other platforms occupy adjacent space but none occupy this exact one.

| Platform | What they do | What they don't | Climatefacts.ai overlap |
|---|---|---|---|
| **Climate Action Tracker** | Country-level policy assessment | No article verification, no claim-level provenance | You consume their ratings |
| **Carbon Brief / DeSmog** | Editorial climate journalism + databases | Human-curated, not real-time, no API | Source-tier overlap |
| **Climate Feedback** | Scientist-network article ratings | Manual, slow, English-only | Directly competitive on news verification (but tiny scale) |
| **CDP / ISSB-aligned platforms** | Corporate disclosure ingestion | Not consumer-facing, not provenance-first | Sprint B competes |
| **Ground News / NewsGuard** | Source reliability scoring, cross-publisher comparison | Not climate-specific, no scientific grounding | Source-tiering overlap |
| **AFP/Reuters fact-check** | Authoritative case-by-case checks | Not algorithmic, no methodology surface | Editorial competitor |
| **Perplexity / general AI search** | Multi-source synthesis | No calibration, no domain grounding, no public methodology | You wrap them |

Where Climatefacts.ai uniquely sits: *consumer-accessible, full-stack, methodology-transparent, multilingual, with both country-level and (eventually) corporate-level verification + the entire audit trail exposed via API.* No other player covers all of those dimensions. The competitive question is whether the platform takes the standard-setting position before someone better-resourced (Google, Bloomberg Green, FT Moral Money) fills it with a closed system.

---

## 4. Recommendations — tiered by sequence and compounding

I'm going to depart from the platform report's phase numbering and re-cluster by what compounds. Five tiers; each prerequisites the previous.

### Tier A — Credibility floor (1–2 weeks). Do not launch externally until these are done.

**A1. Ship RSS full-body extraction.** The 3–4-hour `trafilatura` fix the report names. Until this ships, claim extraction, hallucination, embeddings, and search are all running on stubs. This is the single highest leverage commit in the entire backlog.

**A2. Frontend filter on `is_synthetic = FALSE` everywhere users see articles.** Map, search, compare, feed, country panels, similar-article suggestions, and the chat panel's grounding. Until this ships, the platform is showing 3,588 fake articles to real users.

**A3. Down-grade the calibration display.** Raise `min_labels_for_inference` to 50 in `calibration_store.py` *now*; tag fits as preview when `n_labels < 50` and refuse to apply them in `apply_latest_to_reliability`. Display `n_labels` and `is_preview=true/false` on every surface that shows a calibrated score. Better to look modest than to look calibrated when you're not.

**A4. Surface the audit gap on /methodology.** Publish both the 4.78 self-claim and the 3.6 audited composite, with the remediation roadmap. Same logic as #3 — the most powerful trust move is to show the gap.

**A5. Fix the `articles.id` ↔ `article_id` join bug in hallucination-rates** (P2 in your functional audit). It's a one-line schema correction that silently makes everything bucket as "unknown" — which is the worst-possible state for a methodology endpoint.

**A6. Harden `/api/scheduler/*` failure modes.** Cloud Scheduler currently reports 200 OK on a dead pipeline. This will silently hide problems in production exactly when you need to see them.

**Total estimated effort:** 1 to 1.5 weeks of focused work. Everything in Tier B is at risk until this is done.

### Tier B — Standard-setting features (3–6 weeks). What makes the platform best-in-category.

**B1. Article 50 / AI Act compliance layer.** Add an unambiguous, persistent, machine-readable label to every AI-produced surface (chat answers, deep-search synthesis, URL-analysis verdicts, future videos). Spec: `data-ai-generated="true"` HTML attribute + visible badge + `aria-label` + structured JSON-LD payload at the bottom of the page exposing model, prompt version, retrieval strategy, timestamp. This is also a great differentiating UX move — most platforms will retrofit ugly banners; you can build it elegantly because you already have the data. Frame it on `/methodology` as your **AI Transparency Standard** and publish the schema so others can adopt.

**B2. The agentic chat actions protocol** (Phase 8 in the platform roadmap). The report itself names this as the single biggest UX uplift. Don't ship more than the minimum nine action types first — `navigate`, `analyze_url`, `apply_search_filters`, `apply_map_filters`, `open_methodology_section`, `open_country`, `start_deep_search`, `bookmark_article`, `start_calibration_label`. Each click is a confirmed-by-user action; the LLM never acts directly. The pattern is well-trodden now (Claude/OpenAI tool-use, Cursor's diff-apply); it's mostly product work, not novel research.

**B3. Corporate claim verification — minimum viable.** This is the Sprint B that the report defers to "Wave 7 future." Pull this forward. The minimum viable shape:

- `company_climate_disclosures` schema seeded with CDP open data (CDP publishes a public subset annually) + SBTi commitments dataset (publicly available) + Net Zero Tracker (also public)
- A new entity type alongside `country` with the same audit-trail UX
- Verdicts on three claim types: net-zero target validity (SBTi-validated yes/no), scope coverage (1/2/3 disclosed yes/no), claim recency (last disclosure year)
- A new `/companies/[ticker]` route mirroring `/country/[cc]`
- ECGT-aligned warning surface for offset-based "climate neutral" product claims

This is 2–3 weeks of focused work with public datasets only — no new API integrations needed. It positions the platform for the September 2026 ECGT moment, which the company-claim adapter trio (CDP/SBTi/NZT) is otherwise too late to catch.

**B4. NER-based hallucination + numeric grounding.** Replace the regex-on-capitalised-n-grams with spaCy or transformer NER (en_core_web_trf, multilingual ner). Add a `numeric_grounded` check in `multi_llm_verifier.py` against `country_indicators` for emissions and renewable-share claims — halve confidence when corroborated but not numerically grounded, as your in-house audit recommends. This single change closes the loudest failure mode (both LLMs hallucinate the same number).

**B5. ND-GAIN into the sustainability composite + year-spread band widening + methodology version bump.** Already itemised; just sequence it here so it ships in the same release as B4 and gets one combined methodology version bump (`sustainability_v2_2026_05`) rather than two.

### Tier C — Category leadership (2–3 months). What makes the platform a published standard.

**C1. Publish the Climatefacts Reliability Standard (CFRS) as an open specification.** Take what you've built — the provenance schema, the prompt registry contract, the calibration data plane, the drift detection thresholds — and write it up as a public methodology specification with a versioned URI (e.g. `https://climatefacts.ai/standard/v1`). Submit it to the Open Source Initiative or a journalism-tech foundation (Knight, ICFJ, Earth Journalism Network) for community review. This positions Climatefacts.ai not as *a platform with strong methodology* but as *the methodology that platforms can adopt*. The economics of this are strong: every news organisation, NGO, or government that adopts CFRS becomes a downstream data consumer.

**C2. Source-tier database (replace the 8-publisher venue whitelist).** The in-house audit is right that 8 publishers is not a source-tiering apparatus. Build out a proper `source_credibility_tiers` table seeded with:

- Scimago Journal Rankings (Q1–Q4) for academic sources
- Retracted-paper flags (RetractionWatch / Crossref retraction data)
- MBFC (Media Bias Fact Check) bias scores for news outlets — caveat that this is itself contested
- IFCN (International Fact-Checking Network) verified status
- Self-declared correction policies (yes/no + URL)

Each source's tier flows into a `source_confidence_prior` that the calibration layer combines with model output. This is *the* missing piece to honestly score reliability and the biggest reason the in-house audit dropped Reliability from 4.4–4.8 to 3.5.

**C3. Cross-language hallucination — the gap nobody else has solved.** Your Postgres FTS is multilingual; your embeddings are not language-aware (ada-002 collapses languages but blunts intra-language signal). The hardest problem in climate misinformation in 2026 is *multilingual narrative laundering* — a denialist claim debunked in English keeps spreading in Portuguese, Polish, Indonesian. A genuine solution requires: per-language embedding models (e.g. `bge-m3`, `multilingual-e5-large`), cross-language claim clustering (a hash-key that maps the same proposition across languages), and a narrative-tracking dashboard that shows a debunked claim's lifecycle across languages. This is original research territory — and the right scale of moat for a category-leading platform.

**C4. Continuous external audit / "audit on rails".** Generalise what `docs/audits/2026-05-18-*` already does. Schedule it: a monthly automated audit run that re-grades the platform against a public rubric, with the result published to `/methodology/grade-history`. Tie this to a public bug bounty for methodology issues (modest payouts; the PR value dwarfs the cost). This is the structural way to keep the 1.18-point gap between claim and code from re-opening over time.

**C5. The fact-check microcontent layer.** This is the lighter version of the Phase 9 video pipeline that the report defers indefinitely. Before the full TikTok/Reels pipeline, ship:

- One-claim fact-check cards (1080×1080 + 1080×1920) auto-generated from any URL-analysis result, with the verdict, two-source citation, methodology link, and a QR/short-URL back to the full audit trail
- An embed widget that newsrooms and NGOs can drop into their own articles (`<iframe>` with versioned URL)
- A Slack/Teams app that lets internal teams paste a URL and get back a verdict card

This is 80% of the impact of the video pipeline at 20% of the engineering and zero of the social-platform-API risk surface.

### Tier D — Commercial expansion (3–6 months). Best-in-category needs revenue durability.

**D1. Two new SKUs.**

- **"Claim Substantiation"** — Enterprise. Audit-ready provenance trail for any environmental claim a customer wants to make publicly. Output: PDF + URL + ESRS-citation table mapping the claim to the underlying data points. Priced per claim per year, with SLA on regeneration when underlying indicators update. ECGT-driven demand.
- **"CSRD Companion"** — Professional/Enterprise. Maps a company's CSRD ESRS E1 disclosure against the platform's external indicators (Climate TRACE for facility-level emissions, OWID for sector benchmarks). Flags mismatches; produces a reviewer-ready commentary. CSRD-driven demand.

These don't require new core technology — they require productisation of what's already there. The Stripe webhooks are wired; the tier scaffolding exists.

**D2. White-label methodology surface.** Already in the audience matrix as Enterprise but undefined. Make it concrete: a tenant-scoped `/methodology` page with the partner's logo, calibration labels they've contributed, and their custom indicator weights — backed by the same audit-trail substrate. A government or large NGO can run their *own* "truth machine" on Climatefacts.ai infrastructure.

**D3. The "evidence API" for journalists.** A grant-funded tier (free for verified newsrooms) that gives one-call access to: claim verdict, audit trail, related articles, indicator context, source-tier. The point is not to monetise — the point is to make Climatefacts.ai the default infrastructure layer for climate journalism, which is then the audience that grows the platform virally. Coordinate with Earth Journalism Network / ICFJ / Knight for distribution.

### Tier E — Long horizon (6–18 months).

**E1. Nature disclosures.** The ISSB's nature-related exposure draft lands October 2026. TNFD framework already exists. Build adapters for TNFD-aligned disclosures the same way you built the country indicators. The platform's "sustainability" today is overwhelmingly climate-and-emissions; the next regulatory wave is biodiversity-and-nature, and being early matters.

**E2. Physical climate risk overlay.** Your map already has temperature anomalies; the next step is OS-Climate / Climate Impact Explorer / NASA NEX-DCP30 integration for forward-looking physical risk scenarios at country and sub-national scale. This is the layer that connects "what happened" (news verification) to "what's coming" (forecast-grounded) for the same user.

**E3. The video pipeline — but selectively.** When it ships, treat it as the social-content extension of an authoritative platform, not the primary product. Constrain to *only* publishing video for URL-analyses scoring above a calibrated threshold (e.g. calibrated reliability > 0.8, hallucination < 0.1), with the audit-trail QR code burned into the frame. The platform's reputation should never depend on a video; videos should depend on the platform's reputation.

---

## 5. UI/UX recommendations specifically

The platform's UI/UX audit already names most of the P1/P2 fixes. I'll add the strategic ones the in-house audit doesn't:

### 5.1 Trust UX is currently invisible until you tap into it

The MethodologyDrawer and `/methodology` page do the heavy lifting, but the front door doesn't signal what makes the platform different. Most users will never tap. Recommended:

- **Persistent trust ribbon** on article and analysis surfaces showing four icons (provenance | calibration | hallucination | methodology version) each click-expanding to the relevant detail. Always visible, never modal.
- **An "evidence preview" hover state** on every article card — surface the source tier and the headline calibration number without requiring a click.
- **Methodology-version badge** stamped on every page footer (`v2026.05.18+sustainability_v2`). Builds the perception of a versioned, reproducible product.

### 5.2 The credibility gauge is the wrong primitive

A single 0–100 gauge collapses dimensions that ECGT, CSRD and EU AI Act all require to be reported separately. Replace with a four-bar decomposed view (reliability, agreement, grounding, calibration confidence) — each bar a small width, all four together no taller than the current gauge. Same screen real estate, four times the information density. Use the existing `DecomposedConfidenceChart` for this; it's already in the codebase.

### 5.3 The chat needs to *show* its reasoning, not hide it

The HallucinationDetector runs; the user almost never sees it. Add a fold-out "Reasoning" section under every chat response that shows: (1) the Cynefin classification, (2) the retrieval strategy chosen, (3) the prompt name + version, (4) the hallucination sub-scores, (5) the source IDs (linked to titles, not opaque UUIDs — fix the audit-trail join while you're there). Default-collapsed but one tap away. This is the visible counterpart to your AI Act compliance work in B1.

### 5.4 The map's most powerful affordance is not exposed

The country drill-down has temperature anomalies, sustainability score and articles. What it doesn't have is the *most journalistically valuable* view: a per-country **claim ledger** — a chronological list of every climate-related claim made by or about that country in the last 12 months, with verdicts. Surfacing this turns the map from a comparison tool into a research tool. This is small backend work (it's a query on `claims` joined to `countries`) and large UX impact.

### 5.5 Mobile is mentioned but not specified

PWA is the right answer (the report defers React Native indefinitely). The PWA work itself is small (Next.js 14 supports it well); the design work is choosing what to keep. A draft mobile information architecture:

- **Today** (default home) — five most-checked claims today + one trending country
- **Map** — same as web but with bottom-sheet country panel
- **Check a URL** — paste-and-go; results streamed
- **Saved** — bookmarks + saved queries
- **Methodology** — the front door for trust

Defer: dashboards (web-only), admin (web-only), submit (web with mobile-warn).

### 5.6 Accessibility is below the floor for an EU platform

Icon-only buttons without aria-labels, missing `<main>` landmark, no skip-link, no documented WCAG conformance level. The EU Web Accessibility Directive requires WCAG 2.1 AA for public-sector and is becoming a de facto procurement requirement for any platform serving EU institutions. WCAG 2.2 AA is the realistic 2026 target. Run axe-core in CI; publish the conformance statement. This is small work with large reach (it gates institutional sales).

### 5.7 The methodology page should have a "Reproduce this result" button

For any past URL analysis or deep search, the methodology audit trail records everything needed to re-run it. A "Reproduce" button that re-runs the analysis with the *same prompt version + same retrieval strategy* and shows the diff (calibration shifted, new indicator data, etc.) is the strongest possible demonstration that the platform is what it says it is. It's also, structurally, the audit feature regulators will eventually require.

---

## 6. Data layer recommendations specifically

Beyond what the in-house audits cover:

### 6.1 Adopt the "report once" philosophy explicitly

CDP, EFRAG, ISSB, and GRI are converging on shared schemas (ESRS E1 ↔ CDP correspondence mapping; IFRS S2 ↔ CDP integration; GRI ↔ CDP alignment). The platform's `company_climate_disclosures` schema (when it exists) should *not* be a fresh shape — it should mirror the CDP 2026 questionnaire structure (which is already IFRS S2-aligned), with views that project to ESRS E1, GRI 305, and SBTi commitment shapes. Build once, project everywhere.

### 6.2 Indicator-confidence is currently binary; make it Bayesian

Each `country_indicators` row knows when it was ingested but not how confident the platform is in *the upstream source's number itself.* OWID per-capita-emissions for, say, Eritrea in 2023 is plausibly ±30%; for Germany in 2023 plausibly ±2%. The composite sustainability score treats both as point estimates. Add an `uncertainty` column (or sigma + distribution shape) to each indicator record; propagate through the composite. This is the same logic as your Platt scaling, applied one layer earlier in the pipeline.

### 6.3 The drift thresholds should be learned, not hard-coded

The in-house audit names this. The standard fix is: collect 60 days of post-launch baseline data, fit a Gaussian to each drift signal's null distribution, set thresholds at 2σ / 3σ / 4σ rather than 0.10 / 0.25 / 0.50 nats absolute. This is also a public-methodology moment — publishing the learned thresholds with their fit windows is strong evidence of the platform's metrology.

### 6.4 Add provenance for *negative* findings

Today, `claim_provenance` records what was produced. There is no record of *what was looked for and not found.* For a truth platform, negative space is information. When the multi-LLM verifier rejects a claim, when the hallucination check fires, when an indicator was unavailable for a country, when no contradicting source was found — each should be a provenance row of its own type. This turns the audit trail from "here's what we said" into "here's everything we considered."

### 6.5 The synthetic flag is the start of a broader provenance category

`is_synthetic` is one bit. The richer model is `article_provenance.source_type` with values like `rss_ingested`, `user_submitted_url`, `user_uploaded_document`, `synthetic_seed`, `partner_api_ingested`, `ground_truth_label`. Each carries different downstream-trust semantics; today they're all conflated. This is small schema work that unlocks future filters and source-tier features.

---

## 7. Risks the report names lightly that I'd weight more heavily

**R1. Provider dependency on DeepSeek.** DeepSeek is the primary LLM. Geopolitical and regulatory volatility around Chinese AI providers is non-trivial in 2026 (EU AI Act, US Commerce restrictions, data-residency concerns). The cost-first preference is rational *today*; the resilience story requires a documented fallback to Anthropic as primary, with the primary/secondary swap testable monthly and load-balanceable per-customer. Enterprise customers (especially government) will ask.

**R2. The 30-day baseline window for drift is too short and the platform knows it.** Re-flagging because: this isn't just a tuning issue. With 30 days, a *real* drift event (e.g. one indicator source changes methodology mid-month) is statistically indistinguishable from baseline noise. The platform may be silently miscalibrated during exactly the periods it most needs to detect change.

**R3. The "swarm of 54 agents" copy in CLAUDE.md is a marketing liability.** The report clarifies internally that this is development-workflow only, not runtime. But the README/CLAUDE.md surface this prominently, and any technical due-diligence reader (acquirer, partner, regulator) will mis-read it as a deployed feature. Rewrite the public-facing dev-process docs to say "the runtime is a deterministic FastAPI service" up front. Reserve the multi-agent narrative for development-process documentation that lives where dev process documentation lives.

**R4. Translation quietly degrading without observable signal.** `/api/translate` returns 503 when keys are missing; that's a known P2. The deeper risk is *bad* translation — a Polish or Indonesian article rendered into English by a small LLM with no quality control becomes a confident-looking but subtly wrong source. Add a back-translation BLEU check or a separate translation-quality signal to the provenance row. Multilingual is one of the platform's biggest distinguishers; it's also the biggest under-monitored risk.

**R5. OAuth coverage gap.** Google and Microsoft are good for enterprise; they exclude a meaningful share of journalists, researchers and NGO users globally. Add at minimum Sign in with Apple (iOS users + EU privacy posture) and consider WorkOS or similar for SAML/SSO at the Enterprise tier — government and large NGO procurement will require it.

**R6. The platform has no public security disclosure programme.** A security.txt, a documented `vuln@climatefacts.ai`, a Hall of Thanks page. For a platform that frames itself as trustworthy infrastructure, the absence of a `.well-known/security.txt` is a perception gap. Cheap to fix.

---

## 8. Suggested next-sprint shape — re-ordered

The platform report's "Recommended next-sprint shape" (§10.5) is the right list; I'd re-order it slightly:

1. **Week 1, days 1–3 — Tier A credibility floor.** Items A1–A6 above. Nothing else ships before this.
2. **Week 1, days 4–5 — AI Act prep (B1, partial).** Add the persistent AI-labelled badge + JSON-LD payload to every AI surface. This is the cheapest tier-B win and the most regulatory-relevant.
3. **Week 2 — Sustainability v2 + calibration honesty (B5 + A3 reinforcement).** Ship in one combined release with one combined methodology-version bump.
4. **Weeks 3–4 — Agentic chat actions (B2).** Backend payload + nine action types. Ship visibly; this is the headline UX feature.
5. **Weeks 5–6 — NER hallucination + numeric grounding (B4).** Ships as `methodology_v2026_06`. This closes the loudest failure mode.
6. **Weeks 7–10 — Corporate claims MVP (B3).** Pulled forward from "Wave 7 future." Ships in time for the September 2026 ECGT enforcement window.
7. **Weeks 11–12 — Coverage Sprint A** (Pacific SIDS, francophone Africa, Caribbean, Central America, Central Asia — already in the platform report). Same shape as the report describes.
8. **Quarter 2 — Tier C, in this order: C2 (source-tier DB), C1 (publish CFRS), C5 (microcontent), C4 (audit on rails).**
9. **Quarter 3 — Tier D commercial expansion (D1, D2, D3).**
10. **Quarter 4 — Tier E long horizon.**

Note what *isn't* on this list: the httpOnly cookie migration (S5) and the migration directory schism (D1) — both are real and both should slot into the first quiet week, but neither blocks anything in the sequence above.

---

## 9. The single most important thing

If only one recommendation is taken from this document, take this one:

**Ship Tier A this week, then publicly publish the audited 3.6/5 composite score and the remediation roadmap on `/methodology` alongside the 4.78 self-claim.**

The act of doing this is itself the most powerful evidence the platform exists for. It is the inverse of every greenwashing pattern; it is the embodiment of "Trust as a Service"; it is the move that no competitor will copy. And it costs nothing but courage.

Everything else in this document compounds from that act.

---

## 10. Appendix — quick-reference scoring of the platform vs. category standard

A complementary scoring to the in-house audit, on dimensions I'd argue are more aligned with what 2026 buyers/users will actually grade on.

| Dimension | Current state | Best-in-category target | Gap closeable by |
|---|---|---|---|
| Provenance depth | 4.5 / 5 | 5 / 5 (audit trail joins titles+URLs; negative findings recorded) | Tier B + C |
| Methodology transparency | 4.5 / 5 | 5 / 5 (CFRS published; reproduce button; audit cadence) | Tier C |
| Calibration honesty | 2.8 / 5 | 4 / 5 (preview tag + n_labels; ≥50 labels in production) | Tier A + ongoing labelling |
| Hallucination detection | 3.2 / 5 | 4.5 / 5 (NER + numeric grounding + cross-language) | Tier B + C |
| Corporate-claim coverage | 1 / 5 | 4 / 5 (CDP+SBTi+NZT MVP) | Tier B (B3) |
| Multilingual integrity | 3 / 5 | 4.5 / 5 (per-language embeddings + back-translation QA) | Tier C |
| Regulatory readiness (ECGT + Art 50) | 3 / 5 | 5 / 5 (label layer + claim substantiation SKU) | Tier B (B1) + D |
| Accessibility / EU procurement | 2.5 / 5 | 4.5 / 5 (WCAG 2.2 AA + published statement) | Tier B (in 5.6) |
| Source-tier rigour | 1.5 / 5 | 4 / 5 (DB-backed tiers, Scimago + retraction + IFCN) | Tier C (C2) |
| Distribution / category position | 2 / 5 | 4 / 5 (CFRS adopted; evidence API; embed widget) | Tier C + D |
| **Weighted composite** | **~3.4** | **~4.6** | **~6 months focused execution** |

The honest 3.6/5 the in-house audit reached and the 3.4 I reach above are within auditor-noise of each other. The 4.6 target is realistic by Q4 2026 if Tier A ships in the next two weeks.

---

*End of analysis. The platform is closer to category-defining than the team's self-grading suggests, but only if Tier A ships before any external launch and Tier B is sequenced to ride the September 2026 ECGT and August 2026 EU AI Act enforcement moments.*
