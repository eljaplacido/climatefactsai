# CliLens.AI Backend API Reference

## Base URL
- **Development**: `http://localhost:5400`
- **Production**: `https://api.clilens.ai`

## Authentication

### JWT Bearer Token
```http
Authorization: Bearer <access_token>
```

### API Key (for B2B)
```http
X-API-Key: clilens_<key>
```

## Core Endpoints

### Articles

#### List Articles
```http
GET /api/articles?q=climate&country=US&limit=20&offset=0
```

**Query Parameters:**
- `q` (optional): Search query
- `country` (optional): ISO country code
- `credibility` (optional): high, medium, low
- `tags` (optional): Comma-separated tags
- `date_from` (optional): ISO date
- `date_to` (optional): ISO date
- `limit` (default: 20, max: 100)
- `offset` (default: 0)

**Response:**
```json
[
  {
    "id": 1,
    "title": "Arctic Ice Decline Accelerates",
    "url": "https://example.com/article",
    "source": "BBC",
    "published_at": "2025-01-15T10:00:00Z",
    "excerpt": "New data shows...",
    "credibility_score": 0.89,
    "credibility_level": "high",
    "country": "US",
    "tags": ["arctic", "ice", "climate"],
    "created_at": "2025-01-15T11:00:00Z"
  }
]
```

#### Get Article Detail
```http
GET /api/articles/{id}
```

**Response:**
```json
{
  "id": 1,
  "title": "Arctic Ice Decline Accelerates",
  "url": "https://example.com/article",
  "source": "BBC",
  "full_text": "...",
  "credibility_score": 0.89,
  "credibility_level": "high",
  "claims": [
    {
      "id": "claim-uuid",
      "claim_text": "Arctic ice extent decreased by 13% per decade",
      "claim_type": "factual",
      "verification_status": "verified",
      "confidence_score": 0.92,
      "evidence": [...]
    }
  ]
}
```

### Search

#### Semantic Search (Professional+)
```http
POST /api/search/semantic
Content-Type: application/json

{
  "query": "renewable energy investments",
  "limit": 10,
  "country": "FI"
}
```

### URL Analysis

#### Submit URL for Verification (Basic+)
```http
POST /api/analyze-url
Content-Type: application/json

{
  "url": "https://example.com/article",
  "priority": "normal"
}
```

**Response:**
```json
{
  "id": "analysis-uuid",
  "user_id": "user-uuid",
  "url": "https://example.com/article",
  "status": "pending",
  "progress": 0,
  "created_at": "2025-01-15T12:00:00Z"
}
```

#### Get Analysis Result
```http
GET /api/analyze-url/{analysis_id}
```

### User & Auth

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Get User Profile
```http
GET /api/user/profile
Authorization: Bearer <token>
```

#### Get Usage Stats
```http
GET /api/user/usage?period=monthly
Authorization: Bearer <token>
```

**Response:**
```json
{
  "tier": "professional",
  "period": "monthly",
  "articles_viewed": 127,
  "articles_limit": -1,
  "url_analyses": 8,
  "url_analyses_limit": 20,
  "api_calls": 342,
  "api_calls_limit": 1000
}
```

#### Refresh Access Token (stateful sessions)
```http
POST /api/auth/refresh
Content-Type: application/json

{ "refresh_token": "eyJ..." }
```

Each refresh rotates the token and revokes the prior `jti`. Reuse of an
already-rotated token is detected and triggers cascade-revocation of
every active session for the user (see `sessions` table — migration 017).

#### Logout (revoke session)
```http
POST /api/auth/logout
Authorization: Bearer <token>
Content-Type: application/json

{ "refresh_token": "eyJ..." }
```

Marks the matching `sessions` row revoked. Idempotent.

#### Google / Microsoft OAuth
```http
GET  /api/auth/oauth/state                 # opaque CSRF state, store in sessionStorage
POST /api/auth/oauth/google { code, state, redirect_uri }
POST /api/auth/oauth/microsoft { code, state, redirect_uri }
```

The `state` parameter must match what `/state` issued; the OAuth callback
rejects mismatches. Google's `email_verified=false` is treated as an
unverified identity and refused with `403`.

### Subscriptions

#### Create Subscription
```http
POST /api/subscription/create
Content-Type: application/json
Authorization: Bearer <token>

{
  "tier": "professional",
  "payment_method_id": "pm_xxx"
}
```

#### Get Current Subscription
```http
GET /api/subscription/current
Authorization: Bearer <token>
```

### API Keys

#### Create API Key (Professional+)
```http
POST /api/api-keys
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Production API Key",
  "scopes": ["read", "write"],
  "expires_in_days": 90
}
```

**Response:**
```json
{
  "id": "key-uuid",
  "name": "Production API Key",
  "api_key": "clilens_abc123...",
  "scopes": ["read", "write"],
  "expires_at": "2025-04-15T00:00:00Z",
  "warning": "Save this key securely. It will not be shown again!"
}
```

#### List API Keys
```http
GET /api/api-keys
Authorization: Bearer <token>
```

#### Revoke API Key
```http
DELETE /api/api-keys/{key_id}
Authorization: Bearer <token>
```

### Export (Professional+)

#### Export Article to PDF
```http
POST /api/export/article/{article_id}/pdf
Authorization: Bearer <token>
```

**Response:** PDF file download

#### Export Search Results to CSV
```http
POST /api/export/search/csv?country=US&credibility=high
Authorization: Bearer <token>
```

**Response:** CSV file download

### Admin

#### Trigger Workflow (Admin only)
```http
POST /api/admin/trigger-workflow
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "task_id": "optional-task-id"
}
```

#### Get Stats
```http
GET /api/stats
```

**Response:**
```json
{
  "total_articles": 1523,
  "articles_today": 12,
  "total_fact_checks": 7856,
  "verified_claims": 6234,
  "average_confidence": 0.84,
  "last_updated": "2025-01-15T14:30:00Z"
}
```

### Methodology & Transparency (public)

Every endpoint under `/api/methodology/*` is unauthenticated — designed for
external auditors and the live `/methodology` page on the frontend.

#### Methodology snapshot bundle
```http
GET /api/methodology
```
Returns versioned prompt registry + sustainability formula + indicator
catalogue + git revision in one call. Pin this response to a snapshot
for audit pinning.

#### Versioned prompts
```http
GET /api/methodology/prompts
```
Lists every LLM prompt the platform uses with name, version, and 16-hex
SHA-256 fingerprint. Template content is intentionally not exposed
(prompt-injection / IP risk) — fingerprint + version are enough to
detect deployment-vs-source drift.

#### Sustainability score formula
```http
GET /api/methodology/sustainability-formula
```
Weighted-component table + confidence-band schedule + normalizer
docs + methodology version + URL.

#### Indicator catalogue
```http
GET /api/methodology/indicators
```
Every indicator the platform defines, joined with per-indicator country
coverage counts. `available=false` when migration 020 hasn't been
applied — caller degrades gracefully.

#### Calibration metrics
```http
GET /api/methodology/calibration?signal=reliability_score
```
`signal` is one of `reliability_score`, `agreement_score`,
`hallucination_score`. Returns Brier score + ECE + reliability diagram +
fitted Platt parameters (when ≥5 labels exist).

#### Submit a reviewer label (admin)
```http
POST /api/methodology/calibration/labels
X-Admin-Secret: <secret>           # only when CLILENS_CALIBRATION_ADMIN_SECRET is set
Content-Type: application/json

{
  "url_analysis_id": "uuid",
  "label_truth": 0.8,                # 0-1 graded verdict
  "labeled_by": "reviewer-name",
  "label_method": "human_review",    # or external_factcheck | consensus_panel | …
  "label_notes": "optional"
}
```
Idempotent on `(analysis_id, labeled_by, label_method)` — duplicate
returns 409.

#### Refit calibration (admin / Cloud Scheduler)
```http
POST /api/methodology/calibration/refit?signal=reliability_score&min_labels=5
X-Admin-Secret: <secret>
```
Recomputes Brier + ECE + Platt and persists into `calibration_fits`.
Nightly Celery task (`app.tasks.calibration.nightly_calibration_refit`)
runs this at 03:00 UTC for every supported signal.

#### Hallucination-rate dashboard
```http
GET /api/methodology/hallucination-rates?window_days=30&top_sources=50
```
Mean risk + high-risk rate (>0.5) grouped by extraction method, model,
and source (article + source_article_ids JSONB unnest joined to
`articles.source_name`).

#### Audit-trail lookup
```http
GET /api/methodology/audit-trail/url-analysis/{analysis_id}
GET /api/methodology/audit-trail/article/{article_id}
GET /api/methodology/audit-trail/claim/{claim_id}
```
Returns every `claim_provenance` row for that artifact — model + prompt
fingerprint + retrieval strategy + source articles + hallucination
verdict.

### Drift monitoring (public)

KL-divergence between the recent 7-day window and the prior 30-day
baseline. Verdict buckets: `stable` (<0.10) / `minor` (<0.25) /
`notable` (<0.50) / `significant` (≥0.50).

```http
GET /api/drift/source-mix?recent_days=7&baseline_days=30
GET /api/drift/prompt-fingerprints?recent_days=7&baseline_days=30
```

`top_shifts[]` lists the biggest contributors to the divergence; the
prompt-fingerprint endpoint adds a `display` field (`name@version`) so
operators can identify the affected prompt immediately.

### Indicator sync (scheduler)

Cloud Scheduler HTTP triggers (auth via `X-Scheduler-Secret` header when
`SCHEDULER_SECRET` is set in env):

```http
POST /api/scheduler/indicators/sync?source=climate_trace   # daily
POST /api/scheduler/indicators/sync?source=owid            # weekly
POST /api/scheduler/indicators/sync?source=cat             # weekly
GET  /api/scheduler/indicators/sync/recent?limit=20        # last N sync runs
```

Each invocation upserts into `country_indicators` and logs into
`indicator_sync_logs` (fetched/upserted/skipped counts + duration).

## Error Responses

All endpoints return standard HTTP status codes:

- **200**: Success
- **201**: Created
- **400**: Bad Request (validation error)
- **401**: Unauthorized (missing/invalid token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **429**: Too Many Requests (rate limit exceeded)
- **500**: Internal Server Error

**Error Response Format:**
```json
{
  "detail": "Article not found"
}
```

## Rate Limiting

Rate limits are enforced per subscription tier. Headers included in response:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1642521600
```

## Pagination

List endpoints support cursor-based pagination:

```http
GET /api/articles?limit=20&offset=0
```

**Response includes:**
```json
{
  "items": [...],
  "total": 1523,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

## Interactive Documentation

Visit `/docs` for Swagger UI interactive documentation:
- **Development**: `http://localhost:5400/docs`
- **Production**: `https://api.clilens.ai/docs`

