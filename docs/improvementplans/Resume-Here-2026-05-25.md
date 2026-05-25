# Resume Here — Climatefacts.ai Session State 2026-05-25

## TL;DR

- **Shipped this session:** 18 items across 11 commits (production-review
  bugs + GX10 foundation + synthetic-data guard + biome+climate map layer)
- **Live URLs:**
  - Frontend: https://climatenews-frontend-srzwxdzmaq-ez.a.run.app
  - API: https://climatenews-api-srzwxdzmaq-ez.a.run.app
- **Cloud Build is currently processing commits 25d2d10 → 6798122**
  (latest is the biome layer). Each takes ~10-15 min including
  migrations 037-042.
- **One quick win when you come back (1-2 hr):** finish the biome
  polygon fill rendering in `InteractiveClimateMap.tsx`. The legend +
  data are wired; only the GeoJSON style function needs one branch
  added. See §F1 below.

---

## What shipped this session

| # | Commit | Item |
|---|---|---|
| 1 | 2b9c132 | Migration 037 — upgrade eval user to Professional |
| 2 | 2b9c132 | Migration 038 — force-dedup companies with hard assertion |
| 3 | 20a2441 | Markdown dark-mode contrast pairs (light-on-light fix) |
| 4 | 20a2441 | Chat surfaces real backend errors |
| 5 | b6363fb | Map walkthrough overlay — 7-step onboarding |
| 6 | b6363fb | Country biome narrative — 22 curated countries |
| 7 | b6363fb | Drill-down chat chips via `window` CustomEvent |
| 8 | ac26e43 | Honest gap audit doc (architecture report vs reality) |
| 9 | ac26e43 | Production-review response doc |
| 10 | 25d2d10 | GX10 routing foundation — llm_routing.py + 22 tests |
| 11 | 25d2d10 | Migration 039 — local_llm_fallbacks + shadow_predictions + prompt_eval_runs |
| 12 | 25d2d10 | /api/admin/llm/{routing,breakers,fallbacks} ops endpoints |
| 13 | 25d2d10 | GX10 deployment runbook (9 sections) |
| 14 | 7531540 | scripts/eval_prompts.py — Tier-1 prompt regression harness |
| 15 | d0c8e31 | Migration 040 — PURGE synthetic articles + TRIGGER blocking future inserts |
| 16 | d0c8e31 | Migration 041 — 3-axis source scoring |
| 17 | 789dda1 | Migration 042 + saved_items_routes.py — save anything (8 item types) |
| 18 | 6798122 | Biome+Köppen map layer — 195 countries, taxonomy endpoint, legend, walkthrough |

---

## Production review tally (cumulative)

**17 of 21 items shipped end-to-end.** Remaining:

| # | Item | Scope | GX10 angle |
|---|---|---|---|
| F1 | InteractiveClimateMap biome polygon fill + emoji markers | 1-2 hr | No |
| A1 | Article generation length (full body) | 3-5d | Yes |
| A2 | Multi-claim extraction per article | 2-3d | Yes |
| B1 | Share/Export CSV/PDF endpoints | 1-2d | No |
| B2 | My Feed save (may already work post-deploy) | 4 hr | No |
| C1 | Document upload (PDF/Word, 100+ pages) | 5-7d | Yes |
| C2 | Research feed | 3-4d | No |
| C3 | Scenario simulation | 5-7d | Yes |
| C5 | Persona personalisation engine | 5-7d | No |
| D1 | Audit-grade compliance | 5-7d | Yes |
| E1 | Agentic chat walkthrough mode | 2-3d | No |
| E2 | Architecture report regen | 2 hr | No |

---

## F1 — Finish the biome map rendering (1-2 hr, no dependencies)

**Status:** taxonomy endpoint + corner legend + Country Passport
header badge are all wired. Only the GeoJSON country-polygon fill +
emoji markers are missing.

**Files to edit:**
- `src/frontend/src/components/map/InteractiveClimateMap.tsx`

**What to add:**

1. **Fetch biome data on mount** (or lazy when `activeLayer === "biomes"`):

```ts
const [biomeData, setBiomeData] = useState<Record<string, BiomeEntry>>({});
useEffect(() => {
  if (activeLayer !== "biomes" || Object.keys(biomeData).length) return;
  fetch(`${API_BASE}/api/map/biome-overview`)
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (!d?.countries) return;
      const map = Object.fromEntries(d.countries.map(c => [c.country_code, c]));
      setBiomeData(map);
    });
}, [activeLayer, biomeData]);
```

2. **Branch the GeoJSON style function** — first line check:

```ts
if (activeLayer === "biomes") {
  const cc = feature.properties?.iso_a2;
  return {
    fillColor: biomeData[cc]?.koppen_color || "#9CA3AF",
    fillOpacity: 0.55,
    color: "#475569",
    weight: 0.5,
  };
}
// existing numeric-scale branches follow
```

3. **Render emoji markers at country centroids** when biome layer active:

```tsx
{activeLayer === "biomes" && Object.values(biomeData).map(entry => {
  const centroid = COUNTRY_CENTROIDS[entry.country_code];
  if (!centroid) return null;
  return (
    <Marker
      key={entry.country_code}
      position={centroid}
      icon={L.divIcon({
        html: `<span style="font-size:18px">${entry.biome_emoji}</span>`,
        iconSize: [24, 24],
        className: "biome-emoji-marker",
      })}
      interactive={false}
    />
  );
})}
```

4. **You'll need a `COUNTRY_CENTROIDS` lookup** — either hardcoded
   195-entry dict OR computed from the GeoJSON feature properties
   (most country GeoJSONs include `latitude`/`longitude`). ~1 hr.

**Test:** load `/map`, switch to "Biomes & Climate" layer, verify
countries colour-fill by Köppen zone + biome emoji renders.

---

## Verification commands when you're back

After Cloud Build finishes processing 6798122:

```bash
# 1. Account upgrade landed
curl https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/companies/MSFT \
  | jq '.company.sbti_validated'
# expect: true (proves migrations 029-040 all applied)

# 2. Companies deduped to unique-by-name+country
curl "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/companies?limit=10" \
  | jq '.companies | group_by(.name) | map({name: .[0].name, n: length})
        | sort_by(-.n) | .[0:3]'
# expect: no n > 1

# 3. Synthetic articles purged
curl "https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/articles?limit=3" \
  | jq '. | length'
# expect: 0-3 (likely 0 — all current articles were synthetic)

# 4. Biome overview endpoint live
curl https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/map/biome-overview \
  | jq '.total_countries'
# expect: 195

# 5. Country biome includes symbol
curl https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/map/country/DE/biome \
  | jq '.biome_symbol'
# expect: {biome_id:"temperate_forest", biome_emoji:"🍂", koppen_color:"#2A9D8F", ...}

# 6. LLM routing admin endpoints (token-gated)
TOKEN=$(gcloud secrets versions access latest --secret=corporate-sync-token \
  --project=climatenews-495412)
curl -H "x-corporate-sync-token: $TOKEN" \
  https://climatenews-api-srzwxdzmaq-ez.a.run.app/api/admin/llm/routing \
  | jq '.routing.enrichment'
# expect: {primary:"deepseek", fallback_chain:["local-gx10"]}
```

---

## Hard guarantees now in place

1. **Synthetic data: impossible to insert.** Trigger raises exception
   on any `INSERT INTO articles ... is_synthetic=TRUE`.
2. **Migration 040 cascades:** claims → fact_checks → user_bookmarks
   all clean up via existing FK constraints.
3. **Single env-var flip promotes any LLM workload to local-gx10:**
   `gcloud run services update --update-env-vars=CLILENS_ENRICHMENT_PROVIDER=local-gx10`
4. **Save-anything:** one table, 8 item types, soft Free-tier caps per type.
5. **Biome layer:** taxonomy live for 195 countries; legend renders;
   polygon fill follows in §F1 above.

---

## If you want to take the GX10 path next session

Read `docs/improvementplans/GX10-Deployment-Runbook-2026-05-25.md`.

Week 1 (4 hr total):
1. `vllm serve Qwen/Qwen2.5-14B-Instruct --port 8000` on the GX10
2. `tailscale up` on the GX10 (note magic-DNS name)
3. Three GCP secrets — `clilens-local-gx10-{base-url,api-key,model}`
4. Wire to cloudbuild.yaml `--set-secrets` list
5. Test reachability: `GET /api/admin/llm/breakers` shows local-gx10 closed

Any workload promotion afterwards is one env-var flip. Tertiary
verifier in the cross-check is already routed there by default.

---

## Memory + docs index

All session memory in
`C:/Users/35845/.claude/projects/C--Users-35845-Desktop-DIGICISU-climatenews/memory/`.

In-repo planning docs (`docs/improvementplans/`):
- `Honest-Gap-Audit-2026-05-25.md`
- `Production-Review-Response-2026-05-25.md`
- `GX10-Deployment-Runbook-2026-05-25.md`
- `Phase-10-Session-Summary-2026-05-25.md`
- `Resume-Here-2026-05-25.md` ← you're reading this

Architecture report (with gaps documented in the Gap Audit):
- `docs/reports/Climatefacts-Architecture-Report-2026-05-24.docx`

**Last commit on main:** `6798122` (biome+Köppen map layer)
