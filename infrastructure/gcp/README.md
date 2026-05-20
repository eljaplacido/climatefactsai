# ClimateNews GCP Infrastructure — Lean / Tiny Launch

Production deployment for Google Cloud project `climatenews-495412`, region `europe-west4`.

**Goal:** Get the platform live for <$15/month with scale-to-zero, no persistent workers, and no unnecessary managed services.

---

## Architecture (Lean)

| Component | GCP Service | Why This Choice | Cost Impact |
|---|---|---|---|
| **API** | Cloud Run | Serverless, auto-scales to zero when idle | $0 when idle |
| **Frontend** | Cloud Run | Same container as API, static + SSR | $0 when idle |
| **Database** | Cloud SQL (db-f1-micro) | PostgreSQL 16 + pgvector. Public IP + SSL. | ~$7/month |
| **Scheduled Tasks** | Cloud Scheduler → API endpoints | POSTs directly to lightweight `/api/scheduler/*` routes. No Celery, no Redis, no workers. | ~$0.30/month |
| **Secrets** | Secret Manager | API keys, DB password, JWT secret | ~$0 (within free tier) |
| **Container Registry** | Artifact Registry | Stores Docker images | ~$0.10/month |

### What Was Deliberately Removed (vs. the "full" architecture)

| Removed | Original Cost | Why It's Gone |
|---|---|---|
| Memorystore Redis | $35-40/mo | Not needed. Rate-limiter falls back to DB; caching is nice-to-have at small scale. |
| VPC + Serverless VPC Access | $15-20/mo | Not needed. Cloud SQL uses public IP + strong auth. Cloud Run services are public anyway. |
| Cloud Run Jobs | $5-10/mo | Replaced by Cloud Scheduler HTTP POST to API endpoints. Same code, no extra containers. |
| Celery Beat Worker | $ (part of min-instance cost) | No queue = no worker. FastAPI `BackgroundTasks` handles async work inline. |
| Always-on min instances | $30-50/mo | Both services scale to zero. Cold start is 2-5s — acceptable for a small launch. |

### Network Layout

```
Internet ──► Cloud Run Frontend (Next.js, port 3000)
                │
                ├─── HTTP ──► Cloud Run API (FastAPI, port 8000)
                │                 │
                │                 ├─── Cloud SQL (public IP, SSL)
                │                 │
                │                 └─── Cloud Scheduler POSTs to /api/scheduler/*
                │
Internet ──► Cloud Run API directly (for mobile apps, etc.)
```

No VPC. No private networking. The attack surface is managed by:
- Strong random PostgreSQL password (32 bytes via openssl)
- Cloud SQL SSL enforcement
- Cloud IAM + Secret Manager for all API keys
- Scheduler endpoints protected by `X-Scheduler-Secret` header

---

## Prerequisites

1. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project climatenews-495412
   ```
2. **Docker** installed and running.
3. **Sufficient IAM** on the GCP project (`roles/editor` minimum).
4. **`.env` file** at repo root with real values (copied from `.env.example`).

---

## File Reference

| File | Purpose |
|---|---|
| `api-prod.Dockerfile` | Production Docker image for FastAPI backend |
| `frontend-prod.Dockerfile` | Production Docker image for Next.js frontend |
| `provision-infra.sh` | **One-time** script: creates SQL, secrets, Artifact Registry, Cloud Scheduler jobs |
| `deploy.sh` | **Repeatable** script: builds, pushes, deploys both Cloud Run services |
| `cloudbuild.yaml` | Cloud Build CI/CD pipeline (same as deploy.sh but fully in GCP) |

---

## Deployment Steps

### 1. Provision Infrastructure (run once)

```bash
./infrastructure/gcp/provision-infra.sh
```

**What it creates:**
* Enables APIs (`run`, `sqladmin`, `secretmanager`, `scheduler`, `artifactregistry`, `cloudbuild`)
* Cloud SQL PostgreSQL 16 (`db-f1-micro`, public IP, 10 GB storage)
* `climatenews` database + app user
* Artifact Registry Docker repository
* Secret Manager secrets (from your `.env` file)
* Cloud Scheduler jobs (with placeholder URLs — updated after first deploy)

### 2. Build & Deploy Services

```bash
# Deploy with a custom tag, or omit for timestamp
./infrastructure/gcp/deploy.sh v1.0.0
```

**What it does:**
1. Builds API image from repo root → pushes to Artifact Registry
2. Deploys API Cloud Run service (512 MiB, 1 CPU, scale-to-zero)
3. Captures live API URL
4. Builds Frontend image with `NEXT_PUBLIC_API_URL` baked in
5. Deploys Frontend Cloud Run service (256 MiB, 1 CPU, scale-to-zero)
6. Updates API CORS origins to allow Frontend domain
7. Updates all Cloud Scheduler job URLs with the real API endpoint

### 3. Database Setup

After first deploy, connect to Cloud SQL and initialize the schema:

```bash
# Get the Cloud SQL public IP
SQL_IP=$(gcloud sql instances describe climatenews-postgres \
  --project=climatenews-495412 \
  --format='value(ipAddresses[0].ipAddress)')

# Connect and run migrations
psql "postgresql://climatenews_user:<PASSWORD>@${SQL_IP}:5432/climatenews" \
  -f infrastructure/database/init.sql
```

For pgAdmin or local psql via Cloud SQL Auth Proxy:
```bash
gcloud sql connect climatenews-postgres --user=climatenews_user --database=climatenews
```

### 4. Verify Deployment

```bash
# Check API health
curl https://YOUR-API-URL.a.run.app/health

# Check scheduler health (no auth needed)
curl https://YOUR-API-URL.a.run.app/api/scheduler/health

# Check frontend
curl https://YOUR-FRONTEND-URL.a.run.app
```

---

## Scaling Up Later

When traffic grows, upgrade in this order:

1. **Cloud SQL**: `gcloud sql instances patch climatenews-postgres --tier=db-g1-small` (~$25/mo)
2. **Cloud Run min instances**: Set `--min-instances=1` on both services to eliminate cold starts (~$15-30/mo)
3. **Add Redis**: Only when you actually hit performance limits. Re-provision with Memorystore + VPC connector.
4. **Add dedicated worker**: Only when background tasks take too long inline. Re-introduce Celery + Redis.

---

## Cost Estimate

### Tiny Launch (current setup)

| Component | Monthly Cost |
|---|---|
| Cloud SQL db-f1-micro | **~$7** |
| Cloud Run API (scale-to-zero, low traffic) | **~$0-3** |
| Cloud Run Frontend (scale-to-zero, low traffic) | **~$0-2** |
| Cloud Scheduler (6 jobs) | **~$0.30** |
| Artifact Registry (~1 GB) | **~$0.10** |
| **TOTAL** | **~$8-12/month** |

With Cloud Run's generous free tier, you may pay **$0 for compute** and only **~$7 for the database** for the first few months.

### Medium Traffic Upgrade

| Component | Change | New Monthly Cost |
|---|---|---|
| Cloud SQL db-g1-small | Upgrade tier | ~$25 |
| Cloud Run min-instances=1 | Keep warm | ~$15-25 |
| **TOTAL** | | **~$45-55/month** |

---

## Security Notes

- Cloud SQL password is a 32-byte random string. It lives only in Secret Manager.
- Scheduler endpoints require `X-Scheduler-Secret` header (also in Secret Manager).
- API keys (Anthropic, OpenAI, etc.) are never baked into images — injected at runtime from Secret Manager.
- Cloud Run services are public (required for the frontend). API routes that need auth already use JWT validation.
