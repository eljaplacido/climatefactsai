#!/usr/bin/env bash
# =============================================================================
# ClimateNews GCP Deployment Script — LEAN / Tiny Launch Edition
# =============================================================================
# Idempotent script that builds Docker images and deploys Cloud Run services.
# No Redis, no VPC, no Celery. Cloud Scheduler posts directly to API endpoints.
#
# Usage:
#   ./infrastructure/gcp/deploy.sh [TAG]
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Docker running locally
#   - provision-infra.sh already run (creates SQL, secrets, artifact registry)
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

API_SERVICE="climatenews-api"
FRONTEND_SERVICE="climatenews-frontend"

API_DOCKERFILE="${SCRIPT_DIR}/api-prod.Dockerfile"
FRONTEND_DOCKERFILE="${SCRIPT_DIR}/frontend-prod.Dockerfile"

TAG="${1:-$(date +%Y%m%d-%H%M%S)}"

API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/api:${TAG}"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/frontend:${TAG}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

ensure_artifact_registry() {
    log "Ensuring Artifact Registry repository exists..."
    if ! gcloud artifacts repositories describe "${ARTIFACT_REGISTRY_REPO}" \
        --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        gcloud artifacts repositories create "${ARTIFACT_REGISTRY_REPO}" \
            --repository-format=docker \
            --location="${REGION}" \
            --description="ClimateNews container images" \
            --project="${PROJECT_ID}"
        log "Created Artifact Registry repository: ${ARTIFACT_REGISTRY_REPO}"
    else
        log "Artifact Registry repository already exists."
    fi
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
}

build_and_push() {
    local image_tag="$1"
    local dockerfile="$2"
    local context_dir="$3"

    log "Building image: ${image_tag}"
    docker build \
        --platform=linux/amd64 \
        -f "${dockerfile}" \
        -t "${image_tag}" \
        "${context_dir}"

    log "Pushing image: ${image_tag}"
    docker push "${image_tag}"
}

update_scheduler_urls() {
    local api_url="$1"
    log "Updating Cloud Scheduler jobs to point to ${api_url}..."

    # Get scheduler secret value
    SCHEDULER_SECRET="$(gcloud secrets versions access latest \
        --secret="scheduler-secret" \
        --project="${PROJECT_ID}" 2>/dev/null || echo "")"

    local jobs=(
        "cn-discover:/api/scheduler/ingestion/discover"
        "cn-rss-poll:/api/scheduler/ingestion/rss"
        "cn-verify:/api/scheduler/processing/verify-pending"
        "cn-retry:/api/scheduler/processing/retry-failed"
        "cn-feeds:/api/scheduler/feeds/update"
        "cn-translate:/api/scheduler/translation/batch"
    )

    for entry in "${jobs[@]}"; do
        local name="${entry%%:*}"
        local path="${entry##*:}"
        if gcloud scheduler jobs describe "${name}" \
            --location="${REGION}" \
            --project="${PROJECT_ID}" >/dev/null 2>&1; then
            gcloud scheduler jobs update http "${name}" \
                --location="${REGION}" \
                --project="${PROJECT_ID}" \
                --uri="${api_url}${path}" \
                --headers="X-Scheduler-Secret=${SCHEDULER_SECRET}" \
                --quiet || true
            log "Updated scheduler: ${name} -> ${api_url}${path}"
        fi
    done
}

# ---------------------------------------------------------------------------
# Main deployment flow
# ---------------------------------------------------------------------------
main() {
    log "Starting LEAN deployment for project=${PROJECT_ID} region=${REGION} tag=${TAG}"

    gcloud config set project "${PROJECT_ID}"
    ensure_artifact_registry

    # -----------------------------------------------------------------------
    # 1. Build and push API image
    # -----------------------------------------------------------------------
    build_and_push "${API_IMAGE}" "${API_DOCKERFILE}" "${ROOT_DIR}"

    # -----------------------------------------------------------------------
    # 2. Deploy API to Cloud Run (scale-to-zero, tiny resources)
    # -----------------------------------------------------------------------
    log "Deploying API service: ${API_SERVICE}"

    API_DEPLOY_ARGS=(
        --image="${API_IMAGE}"
        --region="${REGION}"
        --project="${PROJECT_ID}"
        --platform=managed
        --allow-unauthenticated
        --port=8000
        --set-secrets="DATABASE_URL=database-url:latest"
        --set-secrets="SCHEDULER_SECRET=scheduler-secret:latest"
        --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest"
        --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest"
        --set-secrets="OPENAI_API_KEY=openai-api-key:latest"
        --set-secrets="PERPLEXITY_API_KEY=perplexity-api-key:latest"
        --set-secrets="STRIPE_SECRET_KEY=stripe-secret-key:latest"
        --set-secrets="STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest"
        --set-secrets="SENDGRID_API_KEY=sendgrid-api-key:latest"
        --set-secrets="GOOGLE_CLIENT_ID=google-client-id:latest"
        --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest"
        --set-secrets="DEEPSEEK_API_KEY=deepseek-api-key:latest"
        --set-secrets="NOAA_API_TOKEN=noaa-api-token:latest"
        --set-secrets="NASA_API_KEY=nasa-api-key:latest"
        --set-env-vars="ENVIRONMENT=production"
        --set-env-vars="LOG_LEVEL=INFO"
        --set-env-vars="LOG_FORMAT=json"
        --set-env-vars="API_HOST=0.0.0.0"
        --set-env-vars="API_PORT=8000"
        --memory="512Mi"
        --cpu="1"
        --concurrency=80
        --max-instances=5
        --min-instances=0
        --timeout=300
    )

    if gcloud run services describe "${API_SERVICE}" \
        --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        gcloud run services update "${API_SERVICE}" "${API_DEPLOY_ARGS[@]}" --quiet
    else
        gcloud run deploy "${API_SERVICE}" "${API_DEPLOY_ARGS[@]}" --quiet
    fi

    # Capture API URL
    API_URL=$(gcloud run services describe "${API_SERVICE}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --format='value(status.url)')
    log "API deployed at: ${API_URL}"

    # -----------------------------------------------------------------------
    # 3. Build and push Frontend image (with real API URL baked in)
    # -----------------------------------------------------------------------
    log "Building Frontend image with NEXT_PUBLIC_API_URL=${API_URL}"
    docker build \
        --platform=linux/amd64 \
        --build-arg="NEXT_PUBLIC_API_URL=${API_URL}" \
        -f "${FRONTEND_DOCKERFILE}" \
        -t "${FRONTEND_IMAGE}" \
        "${ROOT_DIR}/src/frontend"

    docker push "${FRONTEND_IMAGE}"

    # -----------------------------------------------------------------------
    # 4. Deploy Frontend to Cloud Run (scale-to-zero, minimal resources)
    # -----------------------------------------------------------------------
    log "Deploying Frontend service: ${FRONTEND_SERVICE}"

    FRONTEND_DEPLOY_ARGS=(
        --image="${FRONTEND_IMAGE}"
        --region="${REGION}"
        --project="${PROJECT_ID}"
        --platform=managed
        --allow-unauthenticated
        --port=3000
        --set-env-vars="NODE_ENV=production"
        --set-env-vars="NEXT_TELEMETRY_DISABLED=1"
        --set-env-vars="HOSTNAME=0.0.0.0"
        --memory="256Mi"
        --cpu="1"
        --concurrency=100
        --max-instances=3
        --min-instances=0
        --timeout=60
    )

    if gcloud run services describe "${FRONTEND_SERVICE}" \
        --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        gcloud run services update "${FRONTEND_SERVICE}" "${FRONTEND_DEPLOY_ARGS[@]}" --quiet
    else
        gcloud run deploy "${FRONTEND_SERVICE}" "${FRONTEND_DEPLOY_ARGS[@]}" --quiet
    fi

    FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --format='value(status.url)')
    log "Frontend deployed at: ${FRONTEND_URL}"

    # -----------------------------------------------------------------------
    # 5. Update CORS on API to include frontend URL
    # -----------------------------------------------------------------------
    log "Updating API CORS_ORIGINS..."
    gcloud run services update "${API_SERVICE}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --set-env-vars="CORS_ORIGINS=${FRONTEND_URL}" \
        --quiet || true

    # -----------------------------------------------------------------------
    # 6. Update Cloud Scheduler jobs with real API URL
    # -----------------------------------------------------------------------
    update_scheduler_urls "${API_URL}"

    log "============================================================"
    log "LEAN deployment complete!"
    log "API URL:      ${API_URL}"
    log "Frontend URL: ${FRONTEND_URL}"
    log "============================================================"
}

main "$@"
