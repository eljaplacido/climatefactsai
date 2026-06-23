#!/usr/bin/env bash
#
# setup-lane-a-worker.sh — install + run the Lane A enrichment worker on
# the GX10 (NVIDIA DGX Spark, Ubuntu 24).
#
# What it does (idempotent, safe to re-run):
#   1. Clones the climatenews repo to ~/climatenews if missing, otherwise
#      pulls the latest main.
#   2. Creates ~/clilens/venv (Python 3.12, PEP-668 safe) and installs the
#      minimal dependency set the worker needs.
#   3. Writes ~/clilens/lane-a.env if missing — you fill in DATABASE_URL.
#   4. Creates a user-level systemd unit at ~/.config/systemd/user/clilens-lane-a.service
#      so the worker survives SSH disconnect + reboot.
#   5. Enables loginctl lingering so user services run without you logged in.
#   6. Starts the unit + tails the first 30 lines so you can see it work.
#
# DATABASE_URL — the worker needs this to talk to Cloud SQL. Two options:
#   a) Public IP with the GX10's egress IP added to authorized_networks.
#      Get the URL from `gcloud secrets versions access latest --secret=database-url`
#      and paste into ~/clilens/lane-a.env.
#   b) cloud-sql-proxy on GX10 + connect via 127.0.0.1.
#      The script installs cloud-sql-proxy if a service-account JSON is at
#      ~/clilens/sa-key.json. Falls back to method (a) if not.
#
# Once ~/clilens/lane-a.env has DATABASE_URL, re-run this script to start.

set -e

REPO_URL="${REPO_URL:-https://github.com/eljaplacido/climatefactsai.git}"
REPO_DIR="${REPO_DIR:-$HOME/climatenews}"
VENV_DIR="${VENV_DIR:-$HOME/clilens/venv}"
ENV_FILE="${ENV_FILE:-$HOME/clilens/lane-a.env}"
SERVICE_NAME="clilens-lane-a"
SYSTEMD_UNIT="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
ENTITY_SERVICE_NAME="clilens-lane-a-entity"
ENTITY_SYSTEMD_UNIT="$HOME/.config/systemd/user/${ENTITY_SERVICE_NAME}.service"
SOURCE_SERVICE_NAME="clilens-lane-a-source"
SOURCE_SYSTEMD_UNIT="$HOME/.config/systemd/user/${SOURCE_SERVICE_NAME}.service"

# --- 1. Clone or update the repo ------------------------------------------
if [[ ! -d "$REPO_DIR/.git" ]]; then
    echo "Cloning $REPO_URL → $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
else
    echo "Pulling latest main in $REPO_DIR"
    (cd "$REPO_DIR" && git fetch origin && git checkout main && git pull origin main) | tail -3
fi

# --- 2. Create venv + install dependencies -------------------------------
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
echo "Installing worker dependencies (api/requirements.txt covers the shared.* chain)"
# Use api/requirements.txt which is the focused subset the backend's
# shared.* modules need (~30 packages, no Scrapy/Playwright/transformers).
# Plus a couple of extras the enrichment service uses directly.
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/api/requirements.txt"
"$VENV_DIR/bin/pip" install --quiet \
    'openai>=1.40' \
    'beautifulsoup4>=4.12' \
    'httpx>=0.27' \
    'tenacity>=8.2' \
    'feedparser>=6.0' \
    'langdetect>=1.0' \
    'anthropic>=0.39' \
    'markdown>=3.5' \
    'svgwrite>=1.4'

# --- 3. Write env template if missing ------------------------------------
mkdir -p "$(dirname "$ENV_FILE")"
if [[ ! -f "$ENV_FILE" ]]; then
    cat > "$ENV_FILE" <<EOF
# Cloud SQL Postgres URL for the live climatenews database. Get via:
#   gcloud secrets versions access latest \\
#     --secret=database-url --project=climatenews-495412
# Format: postgresql+psycopg://user:pass@host:5432/dbname
DATABASE_URL=

# Ollama endpoint (default = localhost on the GX10)
CLILENS_LOCAL_GX10_BASE_URL=http://localhost:11434/v1
CLILENS_LOCAL_GX10_API_KEY=ollama
CLILENS_LOCAL_GX10_MODEL=qwen2.5:14b-instruct
CLILENS_ENRICHMENT_PROVIDER=local-gx10

# Worker tuning
GX10_WORKER_BATCH_SIZE=10
GX10_WORKER_IDLE_SLEEP_SEC=60
GX10_WORKER_MAX_BATCHES=0

# Set to 1 to let the service fall back to DeepSeek/OpenAI if Ollama is down.
# Default 0 keeps Lane A strictly local — the worker fails loudly instead
# of silently burning cloud tokens.
GX10_WORKER_DEEPSEEK_FALLBACK=0
EOF
    echo
    echo "⚠ Wrote env template to $ENV_FILE"
    echo "  Edit it to set DATABASE_URL, then re-run this script."
    echo
    echo "  gcloud-side command to fetch the URL:"
    echo "    gcloud secrets versions access latest \\"
    echo "      --secret=database-url --project=climatenews-495412"
    exit 0
fi

# Source so we can sanity-check DATABASE_URL is set
set -a; . "$ENV_FILE"; set +a
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "✗ DATABASE_URL is empty in $ENV_FILE — set it and re-run." >&2
    exit 1
fi

# --- 4. Systemd user unit ------------------------------------------------
mkdir -p "$(dirname "$SYSTEMD_UNIT")"
cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=Climatefacts Lane A enrichment worker (GX10)
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python infrastructure/gx10/lane_a_worker.py
Restart=on-failure
RestartSec=15
StandardOutput=append:$HOME/clilens/lane-a.log
StandardError=append:$HOME/clilens/lane-a.log

[Install]
WantedBy=default.target
EOF

# --- 5. Enable lingering so user services persist past logout -----------
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    echo "Enabling lingering for user $USER (requires sudo once)"
    sudo loginctl enable-linger "$USER" || {
        echo
        echo "⚠ sudo password not provided — without lingering, the worker"
        echo "  will stop when you log out. Run this once manually:"
        echo "    sudo loginctl enable-linger $USER"
    }
fi

# --- 4b. Entity extraction sibling unit ---------------------------------
# Per asusgx10inferencestrategy.md Lane A item #2: entity extraction
# runs alongside enrichment, sharing the same DB + Ollama backend.
cat > "$ENTITY_SYSTEMD_UNIT" <<EOF
[Unit]
Description=Climatefacts Lane A entity extraction worker (GX10)
After=network-online.target ollama.service ${SERVICE_NAME}.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python infrastructure/gx10/lane_a_entity_worker.py
Restart=on-failure
RestartSec=15
StandardOutput=append:$HOME/clilens/lane-a-entity.log
StandardError=append:$HOME/clilens/lane-a-entity.log

[Install]
WantedBy=default.target
EOF

# --- 4c. Source assessment sibling unit ---------------------------------
# Per asusgx10inferencestrategy.md Lane A item #3: 3-axis source scoring
# (editorial / factcheck / transparency) runs alongside enrichment +
# entity extraction, sharing the same DB + Ollama backend.
cat > "$SOURCE_SYSTEMD_UNIT" <<EOF
[Unit]
Description=Climatefacts Lane A source assessment worker (GX10)
After=network-online.target ollama.service ${SERVICE_NAME}.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python infrastructure/gx10/lane_a_source_worker.py
Restart=on-failure
RestartSec=15
StandardOutput=append:$HOME/clilens/lane-a-source.log
StandardError=append:$HOME/clilens/lane-a-source.log

[Install]
WantedBy=default.target
EOF

# --- 6. Reload + start ----------------------------------------------------
systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service" "${ENTITY_SERVICE_NAME}.service" "${SOURCE_SERVICE_NAME}.service"
systemctl --user restart "${SERVICE_NAME}.service" "${ENTITY_SERVICE_NAME}.service" "${SOURCE_SERVICE_NAME}.service"
sleep 3
echo "=== Enrichment worker status ==="
systemctl --user --no-pager status "${SERVICE_NAME}.service" | head -12
echo
echo "=== Entity worker status ==="
systemctl --user --no-pager status "${ENTITY_SERVICE_NAME}.service" | head -12
echo
echo "=== Source worker status ==="
systemctl --user --no-pager status "${SOURCE_SERVICE_NAME}.service" | head -12
echo
echo "Last 20 log lines (enrichment):"
tail -20 "$HOME/clilens/lane-a.log" 2>/dev/null || echo "(log empty)"
echo
echo "Last 20 log lines (entity):"
tail -20 "$HOME/clilens/lane-a-entity.log" 2>/dev/null || echo "(log empty)"
echo
echo "Last 20 log lines (source):"
tail -20 "$HOME/clilens/lane-a-source.log" 2>/dev/null || echo "(log empty)"
echo
echo "Done. Useful commands:"
echo "  systemctl --user status   clilens-lane-a clilens-lane-a-entity clilens-lane-a-source"
echo "  systemctl --user restart  clilens-lane-a clilens-lane-a-entity clilens-lane-a-source"
echo "  systemctl --user stop     clilens-lane-a clilens-lane-a-entity clilens-lane-a-source"
echo "  tail -f \$HOME/clilens/lane-a.log"
echo "  tail -f \$HOME/clilens/lane-a-entity.log"
echo "  tail -f \$HOME/clilens/lane-a-source.log"
