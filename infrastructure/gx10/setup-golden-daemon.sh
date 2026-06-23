#!/usr/bin/env bash
#
# setup-golden-daemon.sh — install + enable the golden-pipeline daemon on
# the GX10 as a user-level systemd service.
#
# The daemon runs `scripts/golden_pipeline_daemon.py --resume` continuously,
# reading DATABASE_URL / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID /
# SCHEDULER_SECRET from ~/clilens/lane-a.env (created by
# setup-lane-a-worker.sh).
#
# Idempotent: safe to re-run. Requires setup-lane-a-worker.sh to have been
# run first (it creates the venv, clones the repo, and writes the env file).

set -e

REPO_DIR="${REPO_DIR:-$HOME/climatenews}"
VENV_DIR="${VENV_DIR:-$HOME/clilens/venv}"
ENV_FILE="${ENV_FILE:-$HOME/clilens/lane-a.env}"
SERVICE_NAME="clilens-golden-daemon"
SYSTEMD_UNIT="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

# --- 1. Sanity checks -----------------------------------------------------
if [[ ! -d "$REPO_DIR/.git" ]]; then
    echo "✗ Repo not found at $REPO_DIR — run setup-lane-a-worker.sh first." >&2
    exit 1
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "✗ Venv not found at $VENV_DIR — run setup-lane-a-worker.sh first." >&2
    exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "✗ Env file not found at $ENV_FILE — run setup-lane-a-worker.sh first." >&2
    exit 1
fi
if [[ ! -f "$REPO_DIR/scripts/golden_pipeline_daemon.py" ]]; then
    echo "✗ Daemon script not found at $REPO_DIR/scripts/golden_pipeline_daemon.py" >&2
    exit 1
fi

# --- 2. Write the systemd user unit ---------------------------------------
mkdir -p "$(dirname "$SYSTEMD_UNIT")"
cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=Climatefacts golden-pipeline daemon (GX10)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python scripts/golden_pipeline_daemon.py --resume
Restart=on-failure
RestartSec=30
StandardOutput=append:$HOME/clilens/golden-daemon.log
StandardError=append:$HOME/clilens/golden-daemon.log

[Install]
WantedBy=default.target
EOF

# --- 3. Enable lingering so user services persist past logout ------------
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    echo "Enabling lingering for user $USER (requires sudo once)"
    sudo loginctl enable-linger "$USER" || {
        echo
        echo "⚠ sudo password not provided — without lingering, the daemon"
        echo "  will stop when you log out. Run this once manually:"
        echo "    sudo loginctl enable-linger $USER"
    }
fi

# --- 4. Reload + start ----------------------------------------------------
systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"
systemctl --user restart "${SERVICE_NAME}.service"
sleep 3
echo "=== Golden daemon status ==="
systemctl --user --no-pager status "${SERVICE_NAME}.service" | head -12
echo
echo "Last 20 log lines:"
tail -20 "$HOME/clilens/golden-daemon.log" 2>/dev/null || echo "(log empty)"
echo
echo "Done. Useful commands:"
echo "  systemctl --user status  ${SERVICE_NAME}"
echo "  systemctl --user restart ${SERVICE_NAME}"
echo "  systemctl --user stop    ${SERVICE_NAME}"
echo "  tail -f \$HOME/clilens/golden-daemon.log"
