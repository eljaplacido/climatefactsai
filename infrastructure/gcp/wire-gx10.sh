#!/usr/bin/env bash
#
# wire-gx10.sh — one-shot script to connect Cloud Run to the on-prem
# ASUS GX10 vLLM endpoint over Tailscale.
#
# Discovered 2026-05-27 by deep-scan probe:
#   * Tailscale hostname: gx10-cd1b
#   * Tailscale IP:       100.86.231.23
#   * LAN IP:             192.168.50.216 (MAC 30-C5-99-40-CD-1B)
#   * OS:                 Linux
#   * Only port 3000 open (Next.js / OpenWebUI) — vLLM NOT running yet
#
# What this script does:
#   1. Asks you to confirm GX10 URL + API key + model
#   2. Creates 3 GCP secrets (clilens-local-gx10-{base-url,api-key,model})
#   3. Grants the API service account access to those secrets
#   4. Patches the running climatenews-api Cloud Run service with
#      --update-secrets so the new env vars take effect without rebuild
#   5. Flips CLILENS_ENRICHMENT_PROVIDER=local-gx10 on the same service
#   6. Optionally prints the Tailscale sidecar config you need to add
#      so Cloud Run can actually reach 100.86.231.23
#
# PRE-FLIGHT (do these on the GX10 first — this script can't):
#   ssh gx10
#   pip install vllm
#   huggingface-cli download Qwen/Qwen2.5-14B-Instruct   # ~28 GB
#   API_KEY="clilens-gx10-$(date +%s)"
#   echo "API_KEY=$API_KEY" > /tmp/gx10.env
#   vllm serve Qwen/Qwen2.5-14B-Instruct \
#       --host 0.0.0.0 --port 8000 \
#       --max-model-len 8192 --gpu-memory-utilization 0.85 \
#       --api-key "$API_KEY"
#   # Confirm reachable: curl -H "Authorization: Bearer $API_KEY" \
#   #                       http://localhost:8000/v1/models
#   # From this Windows machine: curl http://gx10-cd1b:8000/v1/models
#
# Then run this script:
#   bash infrastructure/gcp/wire-gx10.sh                  # interactive
#   GX10_API_KEY=xyz GX10_MODEL=Qwen/Qwen2.5-14B-Instruct \
#       bash infrastructure/gcp/wire-gx10.sh --non-interactive

set -euo pipefail

# --- Defaults (override via env vars or --flags) ----------------------------
PROJECT_ID="${PROJECT_ID:-climatenews-495412}"
REGION="${REGION:-europe-west4}"
API_SERVICE="${API_SERVICE:-climatenews-api}"

# Discovered endpoint defaults. Tailscale is preferred because Cloud Run
# can reach it via the sidecar; LAN only works for local dev.
GX10_BASE_URL_DEFAULT="http://gx10-cd1b:8000/v1"
GX10_BASE_URL="${GX10_BASE_URL:-$GX10_BASE_URL_DEFAULT}"
GX10_API_KEY="${GX10_API_KEY:-}"
GX10_MODEL="${GX10_MODEL:-Qwen/Qwen2.5-14B-Instruct}"
INTERACTIVE=1

for arg in "$@"; do
    case "$arg" in
        --non-interactive) INTERACTIVE=0 ;;
        --help|-h)
            sed -n '2,30p' "$0"
            exit 0 ;;
    esac
done

if [[ $INTERACTIVE -eq 1 ]]; then
    echo "============================================================"
    echo "GX10 wire-up — Cloud Run → on-prem vLLM over Tailscale"
    echo "============================================================"
    echo "Project ID:   $PROJECT_ID"
    echo "Region:       $REGION"
    echo "API service:  $API_SERVICE"
    echo "GX10 URL:     $GX10_BASE_URL"
    echo "GX10 model:   $GX10_MODEL"
    if [[ -z "$GX10_API_KEY" ]]; then
        echo
        read -r -p "Paste GX10 vLLM API key: " GX10_API_KEY
        if [[ -z "$GX10_API_KEY" ]]; then
            echo "Empty API key — aborting"; exit 1
        fi
    fi
    echo
    read -r -p "Proceed? [y/N] " yn
    [[ "$yn" =~ ^[yY] ]] || { echo "Aborted"; exit 0; }
fi

if [[ -z "$GX10_API_KEY" ]]; then
    echo "GX10_API_KEY env var is required in --non-interactive mode" >&2
    exit 1
fi

command -v gcloud >/dev/null 2>&1 || {
    echo "gcloud CLI not found in PATH — install + run 'gcloud auth login' first" >&2
    exit 1
}

# --- 1. Create / update the 3 secrets ---------------------------------------
ensure_secret () {
    local name="$1" value="$2"
    if gcloud secrets describe "$name" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "$value" | gcloud secrets versions add "$name" \
            --project="$PROJECT_ID" --data-file=- >/dev/null
        echo "✓ Updated secret $name (new version)"
    else
        echo "$value" | gcloud secrets create "$name" \
            --project="$PROJECT_ID" --replication-policy=automatic \
            --data-file=- >/dev/null
        echo "✓ Created secret $name"
    fi
}

ensure_secret "clilens-local-gx10-base-url" "$GX10_BASE_URL"
ensure_secret "clilens-local-gx10-api-key"  "$GX10_API_KEY"
ensure_secret "clilens-local-gx10-model"    "$GX10_MODEL"

# --- 2. Grant the API runtime service account access to the secrets --------
RUNTIME_SA="$(gcloud run services describe "$API_SERVICE" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format='value(spec.template.spec.serviceAccountName)')" || true
if [[ -z "$RUNTIME_SA" ]]; then
    # Falls back to default compute SA when service doesn't pin one
    RUNTIME_SA="$(gcloud projects describe "$PROJECT_ID" \
        --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
fi
echo "Runtime SA: $RUNTIME_SA"

for s in clilens-local-gx10-base-url clilens-local-gx10-api-key clilens-local-gx10-model; do
    gcloud secrets add-iam-policy-binding "$s" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:$RUNTIME_SA" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None \
        --quiet >/dev/null
    echo "✓ Granted secretAccessor on $s"
done

# --- 3. Mount the secrets + flip the provider env var on Cloud Run ----------
echo "Updating Cloud Run service $API_SERVICE …"
gcloud run services update "$API_SERVICE" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --update-secrets="CLILENS_LOCAL_GX10_BASE_URL=clilens-local-gx10-base-url:latest,CLILENS_LOCAL_GX10_API_KEY=clilens-local-gx10-api-key:latest,CLILENS_LOCAL_GX10_MODEL=clilens-local-gx10-model:latest" \
    --update-env-vars="CLILENS_ENRICHMENT_PROVIDER=local-gx10" \
    --quiet

echo "✓ Cloud Run updated with GX10 secrets + provider env"
echo

# --- 4. Tailscale sidecar reminder ------------------------------------------
cat <<'EOM'
================================================================
NEXT STEP — Tailscale sidecar on Cloud Run
================================================================
The secrets + env var are mounted, but Cloud Run still can't REACH
100.86.231.23 unless a Tailscale sidecar is attached to the service.
See https://tailscale.com/kb/1326/cloud-run for the canonical pattern.

  1. Create a one-time tagged Tailscale auth key for Cloud Run:
       https://login.tailscale.com/admin/settings/keys
     (tag: tag:cloud-run, ephemeral, reusable, expires in 90 days)

  2. Store it in Secret Manager:
     gcloud secrets create tailscale-authkey \
       --project=climatenews-495412 \
       --data-file=<(echo -n "<paste-the-tskey>")
     gcloud secrets add-iam-policy-binding tailscale-authkey \
       --member="serviceAccount:RUNTIME_SA" \
       --role="roles/secretmanager.secretAccessor"

  3. Re-deploy the API with the sidecar container. The cleanest way is
     to switch from cloudbuild.yaml's `gcloud run deploy` to a YAML
     service manifest that includes both containers — see the runbook
     at docs/improvementplans/GX10-Deployment-Runbook-2026-05-25.md
     §3.4. Sidecar image: tailscale/tailscale:stable

  4. Smoke test:
     curl -H "X-Scheduler-Secret: $SCHEDULER_SECRET" \
       https://<api-url>/api/admin/scheduler/enrich-pending?batch_size=1
     Then check the Cloud Run logs for 'local-gx10' attribution.

If the sidecar is too much complexity for the first pass, you can also
expose vLLM via a Cloudflare Tunnel or Ngrok to the GX10 and store the
public HTTPS URL in clilens-local-gx10-base-url instead. Slower but
fewer moving parts.

================================================================
DONE — GX10 secrets + provider env wired
================================================================
EOM
