#!/usr/bin/env bash
# =============================================================================
# ClimateNews GCP Infrastructure — LEAN / Tiny Launch Edition
# =============================================================================
# Run this ONCE per project to create the long-lived infrastructure:
#   - APIs, Cloud SQL (PostgreSQL 16 + pgvector, public IP),
#     Artifact Registry, Secret Manager, Cloud Scheduler.
#
# NO Redis, NO VPC, NO Cloud Run Jobs. Cloud Scheduler POSTs directly to API.
# Target cost: ~$7-15/month for small traffic.
#
# Usage:
#   ./infrastructure/gcp/provision-infra.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with Owner/Editor role
#   - .env file populated with real values in repo root
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ID="climatenews-495412"
REGION="europe-west4"
ARTIFACT_REGISTRY_REPO="climatenews"

# Cloud SQL — public IP, no VPC needed for tiny launch
SQL_INSTANCE="climatenews-postgres"
SQL_TIER="db-f1-micro"     # cheapest; upgrade later via gcloud sql instances patch
SQL_DB_NAME="climatenews"
SQL_USER="climatenews_user"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

ensure_secret() {
    local name="$1"
    local value="$2"

    if ! gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        printf '%s' "${value}" | gcloud secrets create "${name}" \
            --data-file=- \
            --replication-policy="automatic" \
            --project="${PROJECT_ID}"
        log "Created secret: ${name}"
    else
        printf '%s' "${value}" | gcloud secrets versions add "${name}" \
            --data-file=- \
            --project="${PROJECT_ID}"
        log "Updated secret: ${name}"
    fi
}

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------
log "Enabling GCP APIs (this may take a few minutes)..."

gcloud services enable run.googleapis.com \
    sqladmin.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

log "APIs enabled."

# ---------------------------------------------------------------------------
# 2. Cloud SQL — PostgreSQL 16 with PUBLIC IP (no VPC cost)
# ---------------------------------------------------------------------------
log "Ensuring Cloud SQL instance exists..."

if ! gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud sql instances create "${SQL_INSTANCE}" \
        --database-version=POSTGRES_16 \
        --tier="${SQL_TIER}" \
        --region="${REGION}" \
        --storage-size=10GB \
        --storage-auto-increase \
        --availability-type=zonal \
        --assign-ip \
        --project="${PROJECT_ID}"
    log "Created Cloud SQL instance: ${SQL_INSTANCE}"
else
    log "Cloud SQL instance already exists."
fi

# Allow Cloud Run service account to connect (we'll add the specific SA later)
# For tiny launch, we rely on SSL + strong password rather than VPC.

# ---------------------------------------------------------------------------
# 3. Cloud SQL Database + User
# ---------------------------------------------------------------------------
log "Ensuring database and user exist..."

SQL_PASSWORD="$(openssl rand -base64 32)"

if ! gcloud sql databases describe "${SQL_DB_NAME}" \
    --instance="${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud sql databases create "${SQL_DB_NAME}" \
        --instance="${SQL_INSTANCE}" \
        --project="${PROJECT_ID}"
    log "Created database: ${SQL_DB_NAME}"
else
    log "Database already exists."
fi

if ! gcloud sql users describe "${SQL_USER}" \
    --instance="${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud sql users create "${SQL_USER}" \
        --instance="${SQL_INSTANCE}" \
        --password="${SQL_PASSWORD}" \
        --project="${PROJECT_ID}"
    log "Created SQL user: ${SQL_USER}"
else
    gcloud sql users set-password "${SQL_USER}" \
        --instance="${SQL_INSTANCE}" \
        --password="${SQL_PASSWORD}" \
        --project="${PROJECT_ID}"
    log "Updated SQL user password."
fi

# ---------------------------------------------------------------------------
# 4. Enable pgvector
# ---------------------------------------------------------------------------
log "Enabling pgvector extension..."
gcloud sql connect "${SQL_INSTANCE}" \
    --database="${SQL_DB_NAME}" \
    --user="${SQL_USER}" \
    --project="${PROJECT_ID}" \
    --quiet <<EOF || true
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF
log "pgvector extension enabled."

# ---------------------------------------------------------------------------
# 5. Artifact Registry Repository
# ---------------------------------------------------------------------------
log "Ensuring Artifact Registry repository exists..."

if ! gcloud artifacts repositories describe "${ARTIFACT_REGISTRY_REPO}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${ARTIFACT_REGISTRY_REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="ClimateNews container images" \
        --project="${PROJECT_ID}"
    log "Created Artifact Registry repository: ${ARTIFACT_REGISTRY_REPO}"
else
    log "Artifact Registry repository already exists."
fi

# ---------------------------------------------------------------------------
# 6. Secret Manager Secrets
# ---------------------------------------------------------------------------
log "Creating/updating Secret Manager secrets..."

# Get the Cloud SQL public IP
SQL_IP="$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --format='value(ipAddresses[0].ipAddress)')"

DATABASE_URL="postgresql+psycopg2://${SQL_USER}:${SQL_PASSWORD}@${SQL_IP}:5432/${SQL_DB_NAME}"
SCHEDULER_SECRET="$(openssl rand -hex 32)"

ensure_secret "database-url" "${DATABASE_URL}"
ensure_secret "scheduler-secret" "${SCHEDULER_SECRET}"

# Ingest remaining secrets from .env if available
ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    log "Reading additional secrets from ${ENV_FILE}..."
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        key="$(echo "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        value="$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [[ -z "$key" || "$key" =~ ^# ]] && continue

        secret_name=""
        case "$key" in
            JWT_SECRET_KEY) secret_name="jwt-secret-key" ;;
            ANTHROPIC_API_KEY) secret_name="anthropic-api-key" ;;
            OPENAI_API_KEY) secret_name="openai-api-key" ;;
            PERPLEXITY_API_KEY) secret_name="perplexity-api-key" ;;
            STRIPE_SECRET_KEY) secret_name="stripe-secret-key" ;;
            STRIPE_WEBHOOK_SECRET) secret_name="stripe-webhook-secret" ;;
            SENDGRID_API_KEY) secret_name="sendgrid-api-key" ;;
            GOOGLE_CLIENT_ID) secret_name="google-client-id" ;;
            GOOGLE_CLIENT_SECRET) secret_name="google-client-secret" ;;
            DEEPSEEK_API_KEY) secret_name="deepseek-api-key" ;;
            NOAA_API_TOKEN) secret_name="noaa-api-token" ;;
            NASA_API_KEY) secret_name="nasa-api-key" ;;
        esac

        if [[ -n "$secret_name" && -n "$value" ]]; then
            ensure_secret "${secret_name}" "${value}"
        fi
    done < "${ENV_FILE}"
else
    log "WARNING: No .env file found at ${ENV_FILE}."
fi

# ---------------------------------------------------------------------------
# 7. Cloud Scheduler — POST to API scheduler endpoints (no Celery, no Redis)
# ---------------------------------------------------------------------------
log "Ensuring Cloud Scheduler jobs exist..."

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

API_BASE_URL="https://not-yet-deployed.a.run.app"  # Will be updated after first deploy

ensure_scheduler_job() {
    local scheduler_name="$1"
    local api_path="$2"
    local schedule="$3"
    local description="$4"

    local api_url="${API_BASE_URL}${api_path}"

    if gcloud scheduler jobs describe "${scheduler_name}" \
        --location="${REGION}" \
        --project="${PROJECT_ID}" >/dev/null 2>&1; then
        gcloud scheduler jobs update http "${scheduler_name}" \
            --location="${REGION}" \
            --project="${PROJECT_ID}" \
            --schedule="${schedule}" \
            --time-zone=UTC \
            --uri="${api_url}" \
            --http-method=POST \
            --headers="X-Scheduler-Secret=SECRET_WILL_BE_SET_AFTER_DEPLOY" \
            --oauth-service-account-email="${SA_EMAIL}" \
            --description="${description}" \
            --quiet || true
        log "Updated scheduler: ${scheduler_name}"
    else
        gcloud scheduler jobs create http "${scheduler_name}" \
            --location="${REGION}" \
            --project="${PROJECT_ID}" \
            --schedule="${schedule}" \
            --time-zone=UTC \
            --uri="${api_url}" \
            --http-method=POST \
            --headers="X-Scheduler-Secret=SECRET_WILL_BE_SET_AFTER_DEPLOY" \
            --oauth-service-account-email="${SA_EMAIL}" \
            --description="${description}" \
            --quiet || true
        log "Created scheduler: ${scheduler_name}"
    fi
}

# Lightweight schedules for tiny launch
ensure_scheduler_job "cn-discover"      "/api/scheduler/ingestion/discover"   "0 */6 * * *"  "Article discovery every 6 hours"
ensure_scheduler_job "cn-rss-poll"      "/api/scheduler/ingestion/rss"       "0 */3 * * *"  "RSS polling every 3 hours"
ensure_scheduler_job "cn-verify"        "/api/scheduler/processing/verify-pending" "0 */4 * * *"  "Auto-verify pending articles every 4 hours"
ensure_scheduler_job "cn-retry"         "/api/scheduler/processing/retry-failed"   "0 3 * * *"    "Retry failed verifications daily at 03:00 UTC"
ensure_scheduler_job "cn-feeds"         "/api/scheduler/feeds/update"        "0 */8 * * *"  "Update feeds every 8 hours"
ensure_scheduler_job "cn-translate"     "/api/scheduler/translation/batch"   "0 */12 * * *" "Batch translate every 12 hours"

# End2End audit gap (2026-05-27 §1.4): 3 production-relevant admin
# endpoints had NO scheduler trigger so they never fired in prod.
ensure_scheduler_job "cn-link-check"    "/api/admin/link-check"              "0 2 * * *"    "Link-rot detection daily at 02:00 UTC (mig 046 source_url_status)"
ensure_scheduler_job "cn-research-poll" "/api/admin/research-poll"           "30 3 * * *"   "CrossRef research feed polling daily at 03:30 UTC (mig 047 research_feed_items)"
ensure_scheduler_job "cn-aoi-poll"      "/api/scheduler/aoi-poll"            "0 5 * * *"    "Area-of-interest poll daily at 05:00 UTC"

# 2026-05-27 follow-up: enrichment + backfill crons. The enrichment
# service was wired but never fired in prod; the credibility backfill
# converges historical rows that ingested before the tier-driven path.
ensure_scheduler_job "cn-enrich"             "/api/admin/scheduler/enrich-pending"           "*/30 * * * *" "ArticleEnrichmentService batch_enrich every 30 minutes — was 0% populated"
ensure_scheduler_job "cn-credibility-backfill" "/api/admin/backfill/source-credibility-score" "15 4 * * *"   "Re-stamp articles.source_credibility_score via tier service daily at 04:15 UTC"
ensure_scheduler_job "cn-html-backfill"      "/api/admin/backfill/extracted-text-html"        "45 4 * * *"   "Re-clean extracted_text HTML pollution daily at 04:45 UTC"

# ---------------------------------------------------------------------------
# 8. Grant Cloud Scheduler permission to invoke Cloud Run
# ---------------------------------------------------------------------------
log "Granting Cloud Run invoker permission to Compute service account..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker" \
    --condition=None \
    --quiet || true

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "============================================================"
log "LEAN infrastructure provisioning complete!"
log "------------------------------------------------------------"
log "Cloud SQL instance:    ${SQL_INSTANCE}"
log "Cloud SQL IP:          ${SQL_IP}"
log "Cloud SQL database:    ${SQL_DB_NAME}"
log "Cloud SQL user:        ${SQL_USER}"
log "Artifact Registry:     ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}"
log "------------------------------------------------------------"
log "NOTE: Scheduler jobs use a placeholder API URL."
log "      Run deploy.sh to get the real API URL, then re-run:"
log "        ./infrastructure/gcp/provision-infra.sh"
log "      to update scheduler endpoints with the correct URL."
log "------------------------------------------------------------"
log "NEXT STEPS:"
log "  1) Run deploy.sh to build images and deploy Cloud Run services."
log "  2) Re-run provision-infra.sh to update scheduler URLs."
log "  3) Connect to Cloud SQL and run DB migrations / init.sql."
log "============================================================"
