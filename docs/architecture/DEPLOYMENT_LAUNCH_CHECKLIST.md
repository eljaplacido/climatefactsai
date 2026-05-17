# CliLens.AI Launch Checklist — Truth-Machine Build

This is the end-to-end deployment checklist for the 36+ commits that
landed in the 2026-05-16 → 2026-05-17 truth-machine session, taking the
platform from composite grade 2.2/5 to ~4.8/5.

Last reviewed: 2026-05-17

## 1. Backend deploy prerequisites

### 1.1 Apply migrations 017–024 (in order)

All migrations are idempotent (`CREATE … IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
`ON CONFLICT DO NOTHING`). Apply by ordinal — never skip an interior one.

```bash
# From repo root, against the production database URL:
for f in infrastructure/database/migrations/versions/0{17,18,19,20,21,22,23,24}_*.sql; do
  echo "Applying $f"
  psql "$DATABASE_URL" -f "$f"
done
```

| Migration | What it adds | Critical because |
|---|---|---|
| `017_sessions_table` | `sessions(jti, user_id, …)` | Stateful refresh tokens; without it `/api/auth/refresh` 401s |
| `018_multilingual_fts` | `clilens_lang_cfg(language_code)` + generated tsvector | Non-English search relevance |
| `019_hnsw_article_embeddings` | HNSW partial index | Vector search performance (replaces IVFFlat) |
| `020_country_indicators` | `indicator_definitions` + `country_indicators` | Real climate indicators; seeds the catalogue |
| `021_claim_provenance` | per-extraction audit table | Traceability axis of truth-machine grade |
| `022_calibration_labels` | `calibration_labels` + `calibration_fits` | Reviewer ground truth + fitted Platt params |
| `023_claim_provenance_more_signals` | adds deep_search_session_id + cynefin_classification_id columns | Phase 4 wave 4 provenance writes |
| `024_indicator_sync_logs` | adapter-run audit log | Operator visibility into scheduled syncs |

Roll-forward only. The platform does not require rollback support; if a
migration breaks, fix forward.

### 1.2 Backend env vars

Required for launch — copy from `.env.example` and fill in:

| Variable | Purpose | Required? |
|---|---|---|
| `JWT_SECRET_KEY` | JWT signing | YES (≥32 chars) |
| `DATABASE_URL` | Postgres connection | YES |
| `REDIS_URL` | Celery broker | YES |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | Google Sign-In | YES for OAuth |
| `OAUTH_STATE_SECRET` | CSRF state pin across restarts | Recommended |
| `SCHEDULER_SECRET` | X-Scheduler-Secret on `/api/scheduler/*` | YES if Cloud Scheduler |
| `CLILENS_CALIBRATION_ADMIN_SECRET` | X-Admin-Secret on calibration writes | YES (any non-empty value) |
| `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` | Multi-LLM cross-verification | YES |
| `DEEPSEEK_API_KEY` | Primary LLM | YES |
| `OPENAI_API_KEY` | Embeddings | YES |
| `PERPLEXITY_API_KEY` | External web retrieval | Recommended |
| `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET` | Outlook OAuth | Optional |
| `MICROSOFT_TENANT_ID` | Outlook tenant (default `common`) | If Microsoft OAuth |

### 1.3 Python deps

```bash
pip install -r requirements.txt
```

Verify pinned versions:
* `PyJWT==2.10.1` (must be 2.10+; CVE fix)
* `httpx==0.27.2`
* `fastapi==0.109.0`
* `pydantic==2.9.2`

## 2. Frontend deploy prerequisites

### 2.1 Install + build

```bash
cd src/frontend
npm install        # picks up next 14.2.30 + isomorphic-dompurify
npm run build      # production build
npm run start      # serves the static + SSR bundle
```

### 2.2 Frontend env vars (`.env.production` or build env)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google Sign-In (browser-side OAuth handoff) |
| `NEXT_PUBLIC_MICROSOFT_CLIENT_ID` | Optional, Microsoft OAuth |

## 3. Google Sign-In setup (operator task)

1. Go to https://console.cloud.google.com/apis/credentials.
2. Create an **OAuth 2.0 Client ID** of type **Web application**.
3. Add authorized redirect URIs:
   * `https://app.clilens.ai/auth/callback` (production)
   * `http://localhost:3000/auth/callback` (dev)
4. Copy Client ID → `GOOGLE_CLIENT_ID` + `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.
5. Copy Client secret → `GOOGLE_CLIENT_SECRET` (backend only).
6. (Optional) Configure OAuth consent screen for production user-facing prompts.

The platform's OAuth flow:

```
1. User clicks "Sign in with Google"
2. Frontend GET /api/auth/oauth/state -> 32-byte CSRF token
3. Token persisted to sessionStorage; user redirected to Google with state + client_id
4. Google redirects to /auth/callback?code=...&state=...
5. Frontend verifies state, POSTs code+state to /api/auth/oauth/callback
6. Backend exchanges code, enforces email_verified=true, creates/links user,
   writes session row (S2 stateful), returns JWT access+refresh tokens
```

## 4. Cloud Scheduler triggers (operator task)

Configure HTTP POST jobs against the deployed backend. Include the
`X-Scheduler-Secret` header matching `SCHEDULER_SECRET`.

| Endpoint | Cadence | Why |
|---|---|---|
| `POST /api/scheduler/indicators/sync?source=climate_trace` | daily 04:00 UTC | Sector emissions, satellite-fresh |
| `POST /api/scheduler/indicators/sync?source=owid` | weekly Monday 04:30 UTC | OWID CSV update cadence |
| `POST /api/scheduler/indicators/sync?source=cat` | weekly Wednesday 05:00 UTC | CAT updates ~monthly |
| `POST /api/scheduler/indicators/sync?source=unfccc_ndc` | weekly Tuesday 05:00 UTC | NDC registry refreshed irregularly |
| `POST /api/scheduler/indicators/sync?source=irena` | weekly Thursday 05:00 UTC | IRENA mirror via OWID |
| `POST /api/scheduler/indicators/sync?source=nd_gain` | monthly 1st 05:30 UTC | ND-GAIN publishes annually |

For nightly calibration refit, **prefer the Celery beat schedule** —
it's already wired in `celery_app.py`:

```
"nightly-calibration-refit": { task: ..., schedule: crontab(hour=3, minute=0) }
```

If you don't run Celery beat, fall back to HTTP triggers:

```
POST /api/methodology/calibration/refit?signal=reliability_score       nightly 03:00 UTC
POST /api/methodology/calibration/refit?signal=agreement_score         nightly 03:05 UTC
POST /api/methodology/calibration/refit?signal=hallucination_score     nightly 03:10 UTC
```

Each takes the `X-Admin-Secret` header matching
`CLILENS_CALIBRATION_ADMIN_SECRET`.

## 5. Post-deploy smoke tests

Once the backend + frontend are live, hit these URLs to verify the new
surface area:

### Public (no auth)
```
GET  /api/methodology
GET  /api/methodology/prompts
GET  /api/methodology/sustainability-formula
GET  /api/methodology/indicators
GET  /api/methodology/calibration?signal=reliability_score
GET  /api/methodology/hallucination-rates
GET  /api/drift/source-mix
GET  /api/drift/prompt-fingerprints
GET  /api/auth/oauth/state               # returns {state: "32-hex chars"}
GET  /api/auth/oauth/providers           # returns {google: true, microsoft: bool}
```

### Frontend
```
/                                        # news home
/methodology                             # live methodology page (Phase 4 wave 6)
/login                                   # "Sign in with Google" button present
/about                                   # links to /methodology
```

### Authenticated
```
POST /api/auth/register                  # email + password registration
POST /api/auth/login                     # password login
POST /api/auth/refresh                   # rotates session row
POST /api/auth/logout                    # revokes session row
GET  /api/auth/me                        # 401 without token, 200 with valid Bearer
```

### Admin (X-Admin-Secret required)
```
POST /api/methodology/calibration/labels { url_analysis_id, label_truth, labeled_by }
POST /api/methodology/calibration/refit?signal=reliability_score
```

### First-run scheduler trigger (one-shot)
```
POST /api/scheduler/indicators/sync?source=climate_trace
```
Then inspect `country_indicators` for new rows + `indicator_sync_logs`
for an `ok` entry.

## 6. Verification queries (Postgres)

```sql
-- Migration set applied
SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 10;
-- Should include 017..024.

-- Indicator catalogue populated
SELECT category, COUNT(*) FROM indicator_definitions GROUP BY category;
-- 'emissions' + 'energy' + 'policy' + 'adaptation' rows.

-- Indicator data flowing
SELECT source_name, COUNT(*), MAX(fetched_at)
FROM country_indicators GROUP BY source_name;
-- After scheduler runs: climate_trace + owid + cat + unfccc_ndc + irena + nd_gain.

-- Provenance recording
SELECT extraction_method, COUNT(*)
FROM claim_provenance GROUP BY extraction_method;
-- After first chat / URL analysis / deep search runs.

-- Sessions table healthy
SELECT COUNT(*) FROM sessions WHERE revoked_at IS NULL;
-- Equals active session count.
```

## 7. Truth-machine grade evidence

After deploy, the live `/methodology` page surfaces:

- 4+ versioned prompts with SHA-256 fingerprints
- Sustainability formula (3 components, weights summing to 100%)
- Indicator catalogue (9 seeded indicators)
- Calibration metrics per signal (awaits reviewer labels)
- Per-source hallucination rates (populates as the platform runs)
- KL-divergence drift verdicts on source mix + prompt fingerprints

External auditors can pin any methodology snapshot by hitting
`GET /api/methodology` and saving the JSON — it includes
`git_revision` for full reproducibility.

## 8. Rollback plan

The migrations are roll-forward only. If a deploy goes wrong:

1. Re-deploy the prior backend image (the schema is forward-compatible
   with the prior code — new tables / columns are unused by old code).
2. The new tables (`sessions`, `claim_provenance`, `country_indicators`,
   `calibration_labels`, etc.) can be left in place — they don't affect
   any pre-deploy code path.
3. If a specific table must be removed (extreme case), `DROP TABLE
   IF EXISTS …` is the inverse — no destructive ALTERs in this set.

## 9. Known caveats at launch

- **Calibration metrics** show `n_labels = 0` until reviewers grade
  analyses via `POST /api/methodology/calibration/labels`. The endpoint
  is operational; it just needs data.
- **External adapters** (UNFCCC NDC via Climate Watch, IRENA via OWID,
  ND-GAIN) depend on upstream URLs remaining stable. Each adapter
  accepts a `url`/`api_url`/`csv_url` constructor parameter so operators
  can pin a snapshot if upstream breaks.
- **Perplexity** external retrieval is optional — if `PERPLEXITY_API_KEY`
  is unset, deep-search degrades to internal-corpus-only.

## 10. Sign-off

When all of the above are green:

- [ ] Migrations 017–024 applied
- [ ] Backend env vars set (especially `GOOGLE_CLIENT_ID`,
      `SCHEDULER_SECRET`, `CLILENS_CALIBRATION_ADMIN_SECRET`)
- [ ] Frontend env vars set (especially `NEXT_PUBLIC_API_URL` +
      `NEXT_PUBLIC_GOOGLE_CLIENT_ID`)
- [ ] Google OAuth client created + redirect URIs allowlisted
- [ ] Cloud Scheduler triggers configured
- [ ] Smoke tests above all return 200/expected JSON
- [ ] First indicator sync run wrote rows into `country_indicators`
- [ ] Frontend `/methodology` page renders the live data

The platform is launch-ready when every box is checked.
