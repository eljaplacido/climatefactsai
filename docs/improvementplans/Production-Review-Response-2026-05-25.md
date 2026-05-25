# Production Review Response — 2026-05-25

User raised ~20 items during production review. Status of each below,
with scope estimates for what's NOT done in this session.

## Shipped in this session

| # | Item | Commit |
|---|---|---|
| 1 | Upgrade `eljailari.suhonen@gmail.com` to Professional | migration `037`, pushed 2b9c132 |
| 2 | Force re-dedup of company duplicates with hard assertion | migration `038`, pushed 2b9c132 |
| 3 | Markdown component dark-mode contrast (light text on light bg bug) | 20a2441 |
| 4 | Chat error surfacing (replaces "Sorry, I couldn't process") | 20a2441 |
| 5 | Map walkthrough overlay (7-step onboarding) | b6363fb |
| 6 | Country biome + climate-effects narrative on Overview tab | b6363fb |
| 7 | Drill-down chat suggestion chips from country biome (event-based) | b6363fb |
| 8 | This audit + plan document | (this commit) |

## In-flight (Cloud Build deploying)

When `2b9c132` and `b6363fb` builds finish (~15 min each), the live
state changes to:

- Account `eljailari.suhonen@gmail.com` → Professional tier
- Companies dedupe completed (10k → ~3k unique)
- Markdown renders correctly in light + dark
- Chat shows real error instead of generic message
- Map walkthrough triggers on first map visit
- Country Passport Overview tab shows biome narrative (DE/US/FI/FR/BR/CN/IN/AU/GB/JP/ZA/NO/SE/DK/RU/CA/MX/SA/AE/BD/MV/TV curated; everything else generic)

## NOT done in this session (with honest scope)

### A. Data-layer gaps (must fix before adding more UX)

| # | Item | Scope | Why deferred |
|---|---|---|---|
| A1 | Article-generation length (extend from few-sentence excerpts to full-body articles) | 3-5 days | Requires re-architecting the enrichment pipeline — DeepSeek prompt + chunking + retention |
| A2 | Multi-claim extraction (currently most articles have 1 verified claim out of ~5-10 possible) | 2-3 days | Verifier prompt + Anthropic claim extractor need re-engineering; bumps cost too |
| A3 | Synthetic-vs-real article cleanup (fake URLs like `csiro.au/great-barrier-reef-2025` still flagged `is_synthetic=FALSE`) | 1-2 days | Audit ingestion pipeline + add validation gate |
| A4 | Source credibility scoring backfill (`/api/sources` returns 0; even loaded sources missing editorial/factcheck/transparency) | 2-3 days | Score every source on the 3 dimensions; expose on /sources route |
| A5 | Article detail endpoint returns empty body | 2 hours | Audit the article_id format mismatch between listing + detail |
| A6 | Broken article URLs (many 404 — same fake-URL issue as A3) | 1 day | Cleanup after A3 |

### B. UX bug fixes (user reported)

| # | Item | Scope | Plan |
|---|---|---|---|
| B1 | Share buttons broken (social + CSV/PDF export) | 1-2 days | Audit each Share/Export component; CSV needs server endpoint, PDF needs renderer |
| B2 | My Feed save broken | 4 hours | Investigate `api.createBookmark` flow + user-bookmarks table; suspect tier-gating bug |
| B3 | Visual Summary pictures too small + weather + KG context doesn't load on request | 1 day | Resize chart components + ensure lazy-load triggers on demand |
| B4 | Light text on light background (Markdown fixed; other surfaces tbd) | 2 hours | Audit remaining components for missing dark: pairs |

### C. New features

| # | Item | Scope | Plan |
|---|---|---|---|
| C1 | Document upload analysis (PDF / Word / corporate sustainability reports) | 5-7 days | New `/api/analyze/document` endpoint, multipart upload, PyPDF2 or pdfplumber, chunk + embed + verify; handle 100+ pages with proper context windowing |
| C2 | Research feed (RSS from arxiv / Nature / Science with topic filter) | 3-4 days | Extend rss_feed_registry with `feed_type='research'`; new `/research` route with topic + area selectors |
| C3 | Scenario simulation (e.g. "+1.5°C over 30y for DE") | 5-7 days | Backend: compose IPCC projections + indicator deltas + narrative LLM. Frontend: scenario picker + animated chart panel |
| C4 | Save-more-than-articles (analyses + searches + feed settings) | 2-3 days | New `saved_items` table generalises bookmarks; backend route; UI in `/dashboard/saved` |
| C5 | Persona personalisation (real, not just `?view=business`) | 5-7 days | Persona = onboarding question → tier of default surfaces + chat copy + KPI framings |

### D. Compliance + content quality (the report's biggest gap)

| # | Item | Scope | Plan |
|---|---|---|---|
| D1 | Make compliance chips audit-verifiable, not decorative | 5-7 days | Each chip = a verification rule + a public methodology link |
| D2 | Persona-specific landing pages | 3-5 days | `/for-journalists`, `/for-esg`, `/for-policymakers` with curated defaults |

### E. Cross-cutting

| # | Item | Scope | Plan |
|---|---|---|---|
| E1 | Wire agentic chat to every feature (walkthrough mode) | 2-3 days | Add `start_walkthrough` + `explain_this_page` meta-skills + persona-aware suggestions |
| E2 | Regenerate architecture report with honest gap-audit grades | 2 hours | Use the gap-audit in this directory; new report sections include the "what we don't do yet" line |
| E3 | Local model evaluation (ASUS GX10) — per-feature cost/quality matrix | 1-2 days | Document table: each agentic action's current model + alternative local model + breakeven calc |

---

## Recommended next session ordering

If priorities are user-visible + measurable, the next session should
land **A4 + B2 + B1 + E2** first — they're all <1 day each and they
remove the most embarrassing visible gaps. Then **A1 + A2** because
the article quality is the platform's central claim.

Larger items (**C1-C5**) need their own session each; they're "new
products" rather than "fixes".

---

## Verification checklist for next session start

Run these against production to confirm what's actually live:

```bash
# 1. Account upgrade landed
psql $DATABASE_URL -c "SELECT email, subscription_tier FROM users
                       WHERE email='eljailari.suhonen@gmail.com';"
# expect: subscription_tier='professional'

# 2. Companies deduped
curl https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/companies?limit=200 \
  | jq '.companies | group_by(.name) | map({name: .[0].name, n: length})
        | sort_by(-.n) | .[0:5]'
# expect: no n > 1 in top 5

# 3. Markdown contrast (manual — open /deep-search in light + dark)

# 4. Chat error surfacing (manual — trigger a 4xx, expect actual message)

# 5. Map walkthrough (manual — incognito visit to /map)

# 6. Biome summary on Country Passport (manual — visit /country/DE)
curl https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/map/country/DE/biome \
  | jq '.available, (.climate_effects | length)'
# expect: true, 5
```
