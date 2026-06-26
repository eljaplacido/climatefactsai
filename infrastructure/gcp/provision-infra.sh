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
SQL_TIER="db-g1-small"     # regional HA; upgrade later via gcloud sql instances patch
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
        --availability-type=regional \
        --backup-start-time=03:00 \
        --enable-point-in-time-recovery \
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
OAUTH_STATE_SECRET="$(openssl rand -hex 32)"
CLILENS_CALIBRATION_ADMIN_SECRET="$(openssl rand -hex 32)"

ensure_secret "database-url" "${DATABASE_URL}"
ensure_secret "scheduler-secret" "${SCHEDULER_SECRET}"
ensure_secret "oauth-state-secret" "${OAUTH_STATE_SECRET}"
ensure_secret "clilens-calibration-admin-secret" "${CLILENS_CALIBRATION_ADMIN_SECRET}"
ensure_secret "microsoft-client-id" ""
ensure_secret "microsoft-client-secret" ""
ensure_secret "stripe-price-enterprise" ""

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
            # 2026-06-11 audit: these were created elsewhere (wire-gx10.sh) and
            # mounted by cloudbuild, but a fresh provision-infra run never made
            # them — closing the 3-way secret drift.
            CORPORATE_SYNC_TOKEN) secret_name="corporate-sync-token" ;;
            CLILENS_LOCAL_GX10_BASE_URL) secret_name="clilens-local-gx10-base-url" ;;
            CLILENS_LOCAL_GX10_API_KEY) secret_name="clilens-local-gx10-api-key" ;;
            CLILENS_LOCAL_GX10_MODEL) secret_name="clilens-local-gx10-model" ;;
            # 2026-06-14 — Stripe Basic ($10) and Pro ($20) subscription price IDs.
            STRIPE_PRICE_ID_BASIC) secret_name="stripe-price-basic" ;;
            STRIPE_PRICE_ID_PRO) secret_name="stripe-price-pro" ;;
            STRIPE_PRICE_ID_ENTERPRISE) secret_name="stripe-price-enterprise" ;;
            MICROSOFT_CLIENT_ID) secret_name="microsoft-client-id" ;;
            MICROSOFT_CLIENT_SECRET) secret_name="microsoft-client-secret" ;;
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
    local attempt_deadline="${5:-}"  # optional; e.g. "1800s" for long-running wait=true syncs

    local api_url="${API_BASE_URL}${api_path}"

    # Only HTTP targets that run long (e.g. the synchronous SBTi sync) need an
    # extended attempt deadline; everything else keeps the gcloud 180s default.
    local extra_args=()
    if [[ -n "${attempt_deadline}" ]]; then
        extra_args+=(--attempt-deadline="${attempt_deadline}")
    fi

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
            ${extra_args[@]+"${extra_args[@]}"} \
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
            ${extra_args[@]+"${extra_args[@]}"} \
            --quiet || true
        log "Created scheduler: ${scheduler_name}"
    fi
}

# Lightweight schedules for tiny launch
ensure_scheduler_job "cn-discover"      "/api/scheduler/ingestion/discover"   "0 */6 * * *"  "Article discovery every 6 hours"
ensure_scheduler_job "cn-rss-poll"      "/api/scheduler/ingestion/rss"       "0 */3 * * *"  "RSS polling every 3 hours"
ensure_scheduler_job "cn-verify"        "/api/scheduler/processing/verify-pending" "0 * * * *"    "Auto-verify pending hourly (batch via FACT_CHECK_BATCH_SIZE, default 25)"
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
# KG Phase 1 (2026-05-27): NER entity extraction — populates the canonical
# knowledge_graph schema from mig 049. Hourly cadence to catch up the
# 1664-row corpus quickly; can drop to nightly once converged.
ensure_scheduler_job "cn-ner-extract"        "/api/admin/scheduler/extract-entities"          "0 * * * *"    "EntityExtractionService batch_extract — KG Phase 1, mig 049"

# Monthly corporate SBTi re-sync (roadmap seq-7, 2026-06-04). SBTi publishes its
# validated-targets dashboard roughly monthly; this re-pulls the ~3,960 validated
# companies. wait=true runs the (batched, ~1-2min) sync to completion in a worker
# thread rather than the CPU-throttled background path, so it needs an attempt
# deadline above the 180s gcloud default — bound it to the API's 1800s request
# timeout. Auth via X-Scheduler-Secret (dual-gate added in a37813f). 1st of month,
# 06:00 UTC, off-peak and after the daily backfills have settled.
ensure_scheduler_job "cn-sbti-sync"          "/api/companies/admin/sync/sbti?wait=true"       "0 6 1 * *"    "Monthly SBTi validated-targets re-sync — POST /api/companies/admin/sync/sbti (seq-7)" "1800s"

# Source-health canary (seq-9, 2026-06-04). Probes every rss_feed_registry feed
# (HTTP status + entry count), records last-success, and auto-disables a feed
# after N consecutive failures — dead feeds were polled forever. Network-bound
# across ~50 feeds, so wait=true (keep the instance alive) + a deadline above the
# 180s gcloud default. Daily at 07:00 UTC, after the overnight backfills settle.
ensure_scheduler_job "cn-source-health"      "/api/admin/scheduler/source-health?wait=true"   "0 7 * * *"    "Daily RSS feed-liveness canary + auto-disable dead feeds (seq-9)" "1800s"

# 2026-06-21 (audit): indicators and feed-registry sync were never
# wired as scheduler jobs so the endpoints never fired in production.
ensure_scheduler_job "cn-indicators-sync"   "/api/scheduler/indicators/sync"              "30 4 * * *"   "Daily indicators sync at 04:30 UTC"
ensure_scheduler_job "cn-feed-registry-sync" "/api/admin/scheduler/sync-feed-registry"    "0 6 * * *"    "Daily feed registry sync at 06:00 UTC"

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
# 9. Cloud Monitoring Alert Policies
# ---------------------------------------------------------------------------
# Defaults — cloudbuild.yaml / deploy.sh own the canonical service names and
# frontend host; mirror them here so a fresh provision run can create alerts
# without sourcing deploy.sh. Override by exporting API_SERVICE /
# FRONTEND_DOMAIN before invoking this script.
API_SERVICE="${API_SERVICE:-climatenews-api}"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-}"

log "Creating monitoring alert policies..."

# Resolve (or create) an email notification channel so alerts actually PAGE
# someone. Without this the policies were created with --no-notification-channel
# and fired into the void (audit DEVOPS-03). Set CLILENS_ALERT_EMAIL to enable.
ALERT_EMAIL="${CLILENS_ALERT_EMAIL:-}"
NOTIFICATION_FLAG="--no-notification-channel"
if [[ -n "${ALERT_EMAIL}" ]]; then
  CHANNEL_ID="$(gcloud beta monitoring channels list --project="${PROJECT_ID}" \
    --filter="type='email' AND labels.email_address='${ALERT_EMAIL}'" \
    --format='value(name)' 2>/dev/null | head -n1)"
  if [[ -z "${CHANNEL_ID}" ]]; then
    CHANNEL_ID="$(gcloud beta monitoring channels create --project="${PROJECT_ID}" \
      --display-name="CliLens Alerts (${ALERT_EMAIL})" \
      --type=email \
      --channel-labels=email_address="${ALERT_EMAIL}" \
      --format='value(name)' 2>/dev/null || true)"
  fi
  if [[ -n "${CHANNEL_ID}" ]]; then
    NOTIFICATION_FLAG="--notification-channels=${CHANNEL_ID}"
    log "  Alerts will notify ${ALERT_EMAIL} (${CHANNEL_ID})"
  else
    log "  WARNING: could not resolve/create a notification channel for ${ALERT_EMAIL}; alerts will be SILENT."
  fi
else
  log "  WARNING: CLILENS_ALERT_EMAIL not set — alert policies will have NO notification channel (silent). Set it and re-run to enable paging."
fi

# 1. API 5xx error rate alert
gcloud monitoring policies create --project="${PROJECT_ID}" \
  --display-name="API High 5xx Rate" \
  --condition-filter='resource.type="cloud_run_revision" AND resource.label.service_name="'"${API_SERVICE}"'" AND metric.type="run.googleapis.com/request_count" AND metric.label.response_code_class="5xx"' \
  --condition-threshold-val-comparison=COMPARISON_GT \
  --condition-threshold-value=0.05 \
  --condition-duration=300s \
  ${NOTIFICATION_FLAG} 2>/dev/null || log "  (alert policy may already exist)"

# 2. Cloud SQL CPU utilization alert
gcloud monitoring policies create --project="${PROJECT_ID}" \
  --display-name="Cloud SQL High CPU" \
  --condition-filter='resource.type="cloudsql_database" AND metric.type="cloudsql.googleapis.com/database/cpu/utilization"' \
  --condition-threshold-val-comparison=COMPARISON_GT \
  --condition-threshold-value=0.8 \
  --condition-duration=600s \
  ${NOTIFICATION_FLAG} 2>/dev/null || log "  (alert policy may already exist)"

# 3. Uptime check on frontend (skip if FRONTEND_DOMAIN is unset — the frontend
#    is not deployed yet during first provision).
if [[ -n "${FRONTEND_DOMAIN}" ]]; then
  gcloud monitoring uptime-check-configs create "frontend-uptime" \
    --project="${PROJECT_ID}" \
    --display-name="Frontend Uptime" \
    --resource-type=uptime-url \
    --resource-labels=host="${FRONTEND_DOMAIN}" \
    --http-check-path=/ \
    --period=60s \
    --timeout=10s 2>/dev/null || log "  (uptime check may already exist)"
else
  log "  Skipping frontend uptime check (FRONTEND_DOMAIN not set; set it and re-run after first deploy)."
fi

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
