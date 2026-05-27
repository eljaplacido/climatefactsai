# Security + DevOps Audit — 2026-05-27

Detailed companion to `Platform-Release-Audit-2026-05-27.md §5-6`. Goes
deeper into the auth surface, secrets handling, attack surface, CI/CD
pipeline, and operational posture. Drives the release-blocker list +
v1.1 hardening backlog.

---

## 1. Authentication surface

### 1.1 User auth
- **Token format**: JWT (HS256), claim `{user_id, subscription_tier, exp}`
- **Issuance**: `/api/auth/login`, `/api/auth/google` (OAuth), `/api/auth/github` (OAuth)
- **Storage**: Browser `localStorage` key `clilens_token`
- **Refresh**: `/api/auth/refresh` swaps short-lived access token via refresh token cookie (Strict, Secure)
- **Logout**: client-side `localStorage.removeItem` + server-side `/api/auth/logout` revokes refresh token
- **TTL**: access 1h, refresh 30d

### 1.2 Service auth
- **API key auth**: Pro+ tier users can generate API keys via `/api/api-keys/*` (mig 015)
- **Admin auth**: `X-Scheduler-Secret` OR `X-Corporate-Sync-Token` headers — never JWT
- **GX10 ↔ Cloud SQL**: pgbouncer + IP allowlist; DATABASE_URL on systemd unit env (mode 600)

### 1.3 OAuth scopes
- Google: `openid email profile` (no calendar, no drive, no plus)
- GitHub: `read:user user:email` (no repo access)

### 1.4 Known issues
- ⚠️ `clilens_token` in localStorage is exposed to XSS — mitigated by DOMPurify sanitization in render path + render-time `stripHtml` helper, but no CSP header set
- ⚠️ No 2FA on user accounts — defer to v1.1
- ⚠️ Refresh token rotation not strict — should rotate on every refresh, not just on suspicion

---

## 2. Authorization model

### 2.1 Tier matrix (see Platform-Release-Audit §4)
- Free, Standard, Pro, Enterprise
- `TIER_LIMITS` dict in `api/rate_limiter.py` governs quotas
- `check_premium_feature(user_tier, feature_name)` checks paid-feature access

### 2.2 Premium-feature enforcement gaps (release blocker 1)
**8 of 15 declared premium features have no enforcement** (audit-tracked in `tests/api/test_premium_feature_matrix.py`):
1. `url_analysis` — anonymous quota check exists but not premium-gated for paid tiers
2. `notifications` — no route exists yet (declared too early)
3. `advanced_analytics` — `/api/analytics/*` doesn't tier-check
4. `infographics` — `/api/articles/{id}/infographic` is fully public
5. `feed_customization` — user prefs (mig 010) public
6. `advanced_insights` — `/api/insights/*` doesn't tier-check
7. `source_registration` — anyone authenticated can suggest
8. `comparative_analysis` — `/api/map/compare` doesn't tier-check

**Resolution required before public v1.0**: per-feature triage. Either enforce or drop from matrix. Honest copy in marketing materials must match.

### 2.3 Rate limits (verified)
- **Anonymous**: 100 req/min global, 3 searches/day
- **Free**: 200 req/min global, 3 saves, 3 searches/day, 2 deep-searches/day
- **Standard**: 500 req/min global, ∞ saves, 10 deep-searches/day
- **Pro**: 2000 req/min, ∞ saves, ∞ deep-searches, 1000 API calls/day
- **Enterprise**: 10000 req/min, ∞ everything

Verified in `api/rate_limiter.py:TIER_LIMITS`. Anonymous rate limit is fingerprint-based (IP + UA hash); known issue: shared NATs can collide.

---

## 3. Secrets management

### 3.1 Production secrets (Google Secret Manager)
- `database-url` (Cloud SQL connection string with credentials)
- `scheduler-secret` (admin endpoint auth)
- `corporate-sync-token` (adapter sync auth)
- `jwt-secret-key` (JWT signing)
- `anthropic-api-key`
- `openai-api-key`
- `deepseek-api-key`
- `perplexity-api-key`
- `stripe-secret-key`
- `stripe-webhook-secret`
- `sendgrid-api-key`
- `google-client-id`, `google-client-secret`
- `github-client-id`, `github-client-secret`

### 3.2 Wiring
Each secret bound to Cloud Run via `--set-secrets=NAME=secret-name:latest` in `cloudbuild.yaml`. Verified surviving across deploys.

### 3.3 GX10 secrets
`~/clilens/lane-a.env`:
```
DATABASE_URL=postgresql+psycopg://...
CLILENS_LOCAL_GX10_BASE_URL=http://localhost:11434/v1
CLILENS_LOCAL_GX10_MODEL=qwen2.5:7b-instruct
DEEPSEEK_API_KEY=...  # ← wiped at process start when fallback disabled
```
File is mode 600, owned by `eljaplacido`, on systemd user unit.

### 3.4 In-repo (sanitized)
- `.env.example` documents every required env var with placeholder values
- `.gitignore` excludes `.env`, `.env.local`, `.env.*.local`, `data/golden_pipeline/`

### 3.5 Rotation policy
**Currently**: manual on incident.
**Recommended for v1.0**: document 90-day rotation cadence in `docs/operations/secret-rotation.md` (TODO).

---

## 4. Input validation + attack surface

### 4.1 SSRF
- `_validate_safe_url` in `api/url_analysis_routes.py` and `api/research_routes.py`
- Rejects: private IPs (10/8, 172.16/12, 192.168/16, 127/8), link-local (169.254/16), metadata services (Google/AWS/Azure metadata IPs)
- ✅ Verified test in `tests/api/test_url_analysis.py`

### 4.2 XSS
- All user input rendered via React (no `dangerouslySetInnerHTML` except sanitized analysis HTML)
- Sanitized via `DOMPurify` with strict allowlist (`SAFE_TAGS`, `SAFE_ATTRS`)
- Defensive `stripHtml` helper (`src/frontend/src/lib/stripHtml.ts`) applied to article excerpt + full_text render paths
- Audit-shipped in slice S1 (`8800067`)

### 4.3 SQL injection
- All endpoints use SQLAlchemy `text()` with `:param` bindings
- Spot-checked: 0 user-input string interpolation found
- ⚠️ Exception: 2 places use f-string for `placeholders = ", ".join(f":eid{i}"...)` — bound names are int indexes, not user input — safe.

### 4.4 Prompt injection
- Article text is fed to LLMs with length cap (4000-30000 chars per workload)
- System prompts use server-side templates; user-provided URL/text never replaces system prompt
- `provenance_ledger` table captures every (system, user) pair for forensic audit

### 4.5 CSRF
- JWT in `Authorization: Bearer` header (NOT cookie) → cross-site CSRF mitigated for the auth surface
- ⚠️ `clilens_token` localStorage — if XSS exfiltrates it, attacker gets full account → mitigation = strict DOMPurify (already done) + CSP header (TODO)
- Refresh token cookie is `SameSite=Strict; Secure; HttpOnly` ✓

### 4.6 CORS
- `CORS_ORIGINS` env-driven, prod is locked to `https://climatenews-frontend-srzwxdzmaq-ez.a.run.app` + localhost dev
- `allow_credentials=True` (refresh token cookie requires it)
- `allow_methods` and `allow_headers` properly scoped

### 4.7 Content Security Policy (CSP)
- ⚠️ **NOT SET** in current Cloud Run response headers
- **Recommendation v1.0**: add via Next.js `headers()` in `next.config.js`:
  ```javascript
  {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://climatenews-api-srzwxdzmaq-ez.a.run.app; frame-ancestors 'none';"
  }
  ```
- Then audit any inline `<script>` tags or third-party widget loads

---

## 5. CI/CD pipeline

### 5.1 GitHub Actions (`.github/workflows/ci.yml`)
On every PR + push to main:
- `cd src/frontend && npm ci && npm run lint && npm run typecheck && npm test`
- `pytest tests/ -q --tb=short`
- Lint must pass; tests must pass; otherwise PR blocked

### 5.2 Cloud Build (`cloudbuild.yaml`)
On push to main, 9 sequential steps:
1. `run-migrations` — `scripts/run_migrations.py` against Cloud SQL
2. `build-api` — docker build
3. `push-api` — docker push to Artifact Registry
4. `deploy-api` — `gcloud run deploy climatenews-api`
5. `get-api-url` — capture URL for frontend env
6. `build-frontend` — `npm run build`
7. `push-frontend` — docker push
8. `deploy-frontend` — `gcloud run deploy climatenews-frontend`
9. `update-schedulers` — refresh Cloud Scheduler crons

Hard-fails on any non-zero step → no deploy.

### 5.3 Migration runner posture
- `MIGRATIONS_TOLERATE_ERRORS=true` set in cloudbuild → idempotency errors logged but don't fail deploy
- ⚠️ Caught burn this session: mig 049 effectively no-op'd due to ON CONFLICT silently masking, runner reported SUCCESS
- **Recommendation v1.0**: add post-migration assert step: `python scripts/verify_migration_state.py` checks expected row counts in critical tables (e.g. `source_credibility_tiers >= 100`, `rss_feed_registry >= 150`)

### 5.4 Test coverage
- 97 test files
- pytest config blocks the in-tree `pytest-cov` + `pytest-xdist` plugins; estimated coverage 35-50% backend, ~20% frontend
- **Recommendation v1.1**: get to 70% backend, 50% frontend before public

### 5.5 Cloud Scheduler crons
Live crons (verified via `gcloud scheduler jobs list`):
- `cn-aoi-poll` — daily 06:00 Helsinki, AOI subscription alerts
- `cn-enrich-pending` — every 4h, batch enrich pending articles
- `cn-source-tier-refresh` — daily, refresh tier cache
- `cn-source-credibility-backfill` — weekly
- ⚠️ Not in source-control YAML — provision script is `infrastructure/gcp/provision-infra.sh` shell loop. **Recommendation**: export to `infrastructure/scheduler-jobs.yaml`.

---

## 6. Observability

### 6.1 Logs
- Cloud Run structured JSON logs → Cloud Logging
- GX10 systemd journal + `~/clilens/{lane-a,golden-daemon}.log`
- Search via `gcloud logging read 'resource.type=cloud_run_revision AND ...'`

### 6.2 Metrics
- `/api/metrics/log-feature` for feature-usage tracking
- `.claude/memory/metrics.json` for session-level metrics
- ⚠️ No SLA dashboard, no error-budget tracking — v1.1 work

### 6.3 Alerting
- Telegram bot pushes daemon stalls + critical errors
- ⚠️ No PagerDuty / Slack / email alerting on Cloud Run error rate spikes — v1.1

### 6.4 Health endpoints
- `/api/health` — basic OK/error
- `/api/admin/llm/breakers` — circuit-breaker state (auth-gated)
- `/api/admin/scheduler/health` — cron last-run timestamps

---

## 7. Operational playbooks (TODO before v1.0)

| Playbook | Status |
|---|---|
| Secret rotation | TODO `docs/operations/secret-rotation.md` |
| Migration hotfix | partial — covered in audit benchmarks |
| Lane A worker debug | partial — Telegram /restart command + systemctl logs |
| Cloud Run rollback | TODO |
| Cloud SQL backup restore | TODO |
| Incident response | TODO |

---

## 8. Compliance posture

| Standard | Status |
|---|---|
| GDPR | ⚠️ partial — privacy policy at `/privacy` + data deletion via `/api/user/delete` (mig 022); DPA template not signed |
| CCPA | ⚠️ partial — same as GDPR |
| Accessibility (WCAG 2.1 AA) | ⚠️ not audited — color-scheme fix improves; full audit pending |
| Cookie banner | ⚠️ TODO if launching in EU |

---

## 9. Top 5 v1.0 hardening tasks (concrete)

1. **Add CSP header** — `next.config.js` headers config. 2h.
2. **Premium-feature triage** — 8 unenforced features. 2 days.
3. **Add `verify_migration_state.py`** to cloudbuild — assert critical table row counts. 3h.
4. **Export `scheduler-jobs.yaml`** from current crons + diff in CI. 2h.
5. **Document secret rotation playbook** in `docs/operations/secret-rotation.md`. 1h.

---

## 10. v1.1 hardening backlog (post-launch)

- 2FA on user accounts
- SLA dashboard + error-budget tracking
- PagerDuty / multi-channel alerting
- 70% backend test coverage / 50% frontend
- WCAG 2.1 AA full audit
- Cookie banner (EU launch)
- Multi-region deploy (currently europe-west4 only)
- Webhook-based ingestion (replace polling)
- Automated secret rotation
