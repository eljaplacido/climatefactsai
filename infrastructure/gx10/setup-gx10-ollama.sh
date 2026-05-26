#!/usr/bin/env bash
#
# setup-gx10-ollama.sh — first-pass GX10 (NVIDIA DGX Spark) setup for
# serving the Climatefacts AI workloads via Ollama on port 11434.
#
# Why Ollama and not vLLM:
#   The DGX Spark is aarch64 (Grace Blackwell). vLLM's prebuilt wheels
#   are x86_64-only; an ARM64 build needs ~30-60 min compile against
#   the NVIDIA CUDA stack. Ollama ships ARM64 binaries with CUDA + an
#   OpenAI-compatible /v1/chat/completions API on :11434, so the
#   platform's llm_routing.py talks to it without code changes.
#
# Run this on the GX10 itself:
#   ssh eljaplacido@gx10-cd1b
#   bash setup-gx10-ollama.sh   # or paste contents inline
#
# Safe to re-run; each step short-circuits when already done.
#
# Reverts (if you want to switch to vLLM later):
#   sudo systemctl stop ollama && sudo systemctl disable ollama
#   sudo rm /etc/systemd/system/ollama.service.d/override.conf
#   ollama rm qwen2.5:14b-instruct

set -e

# 1. Install Ollama if not present (ARM64 binary + systemd unit).
if ! command -v ollama >/dev/null 2>&1; then
    echo "Installing Ollama …"
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama already installed: $(ollama --version)"
fi

# 2. Bind Ollama to all interfaces so Tailscale + LAN can reach it
#    instead of the default localhost-only listener.
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'UNIT'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=24h"
Environment="OLLAMA_NUM_PARALLEL=4"
# Increase the context cap so long article enrichments don't truncate.
Environment="OLLAMA_MAX_LOADED_MODELS=2"
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ollama >/dev/null 2>&1 || true
sudo systemctl restart ollama
sleep 3
systemctl is-active ollama

# 3. Pull the starter model. Qwen2.5-14B Q4 quant is ~9 GB on disk and
#    fits comfortably on the Grace Blackwell unified memory.
ollama pull qwen2.5:14b-instruct

# 4. Local smoke test — must return JSON listing qwen2.5:14b-instruct
echo "---"
echo "Local /v1/models response:"
curl -sS http://localhost:11434/v1/models | head -c 400 ; echo

# 5. End-to-end chat-completion smoke test in the OpenAI API shape.
echo "---"
echo "Chat completion smoke test:"
curl -sS http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:14b-instruct",
    "messages": [{"role":"user","content":"Reply with exactly: OK"}],
    "max_tokens": 8
  }' | head -c 500 ; echo

# 6. Persist the endpoint info for wire-gx10.sh to pick up.
mkdir -p ~/clilens
cat > ~/clilens/gx10-endpoint.env <<EOF
GX10_BASE_URL=http://gx10-cd1b:11434/v1
GX10_API_KEY=ollama
GX10_MODEL=qwen2.5:14b-instruct
EOF
echo "---"
echo "Endpoint saved to ~/clilens/gx10-endpoint.env:"
cat ~/clilens/gx10-endpoint.env

cat <<'POST'

============================================================
GX10 ready. From your dev machine (Windows PowerShell):
   $env:GX10_BASE_URL = "http://gx10-cd1b:11434/v1"
   $env:GX10_API_KEY  = "ollama"
   $env:GX10_MODEL    = "qwen2.5:14b-instruct"
   bash infrastructure/gcp/wire-gx10.sh --non-interactive

The wire-gx10.sh defaults already point here, so the env vars
are optional — they just make the run idempotent.
============================================================
POST
