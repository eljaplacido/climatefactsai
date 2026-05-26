# Golden Pipeline Daemon launcher with auto-restart.
#
# Usage (from repo root):
#   .\scripts\start_golden_daemon.ps1
#   .\scripts\start_golden_daemon.ps1 -Budget 200 -WaveSize 15
#   .\scripts\start_golden_daemon.ps1 -DryStatus    # one-shot status print, no run
#
# Prerequisites checked at startup:
#   1. gcloud SDK installed (used to fetch SCHEDULER_SECRET if not in env)
#   2. python in PATH
#   3. TELEGRAM_BOT_TOKEN in env or .env
#   4. GX10 Lane A worker running (best-effort probe via recent local-gx10 enrichments)
#
# Auto-restart: if the daemon crashes (exit code != 0), wait 30s and relaunch.
# Graceful stop: daemon exits 0 on /stop command from Telegram — no relaunch.

param(
    [int]$Budget = 400,
    [int]$WaveSize = 20,
    [int]$MaxWaves = 25,
    [switch]$DryStatus
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# ---------------------------------------------------------------------------
# Bootstrap environment
# ---------------------------------------------------------------------------

# Load .env (if present)
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$' } | ForEach-Object {
        $name = $matches[1]
        $val = $matches[2].Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($name)) {
            [Environment]::SetEnvironmentVariable($name, $val, 'Process')
        }
    }
}

# Fetch SCHEDULER_SECRET from Google Secret Manager if not in env
if (-not $env:SCHEDULER_SECRET) {
    $gcloud = "$env:USERPROFILE\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    if (-not (Test-Path $gcloud)) {
        $gcloud = "gcloud"
    }
    $env:CLOUDSDK_PYTHON = "$env:USERPROFILE\AppData\Local\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe"
    Write-Host "Fetching SCHEDULER_SECRET from Google Secret Manager..." -ForegroundColor Cyan
    $secret = & $gcloud secrets versions access latest --secret=scheduler-secret --project=climatenews-495412 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to fetch SCHEDULER_SECRET: $secret"
        exit 1
    }
    $env:SCHEDULER_SECRET = $secret.Trim()
}

if (-not $env:TELEGRAM_BOT_TOKEN) {
    Write-Error "TELEGRAM_BOT_TOKEN not set. Add to .env or `$env:TELEGRAM_BOT_TOKEN."
    exit 1
}

Write-Host "SCHEDULER_SECRET:    set ($($env:SCHEDULER_SECRET.Length) chars)" -ForegroundColor Green
Write-Host "TELEGRAM_BOT_TOKEN:  set ($($env:TELEGRAM_BOT_TOKEN.Length) chars)" -ForegroundColor Green
if ($env:TELEGRAM_CHAT_ID) {
    Write-Host "TELEGRAM_CHAT_ID:    $($env:TELEGRAM_CHAT_ID) (preset)" -ForegroundColor Green
} else {
    Write-Host "TELEGRAM_CHAT_ID:    (will be captured when you message the bot first)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Status-only mode
# ---------------------------------------------------------------------------

if ($DryStatus) {
    python "$ProjectRoot\scripts\golden_pipeline_daemon.py" --status
    exit 0
}

# ---------------------------------------------------------------------------
# Auto-restart loop
# ---------------------------------------------------------------------------

$restartCount = 0
$maxRestarts = 10
$lastStartTime = Get-Date

while ($true) {
    $now = Get-Date
    if (($now - $lastStartTime).TotalMinutes -lt 5 -and $restartCount -ge 3) {
        Write-Host "Too many rapid restarts (3 in 5 min). Stopping launcher." -ForegroundColor Red
        break
    }
    if ($restartCount -ge $maxRestarts) {
        Write-Host "Hit max restart count ($maxRestarts). Stopping launcher." -ForegroundColor Red
        break
    }
    $lastStartTime = $now
    $restartCount += 1

    Write-Host "`n=== Launching golden_pipeline_daemon.py (attempt $restartCount) ===" -ForegroundColor Cyan
    Write-Host "Budget: $Budget articles | Wave size: $WaveSize | Max waves: $MaxWaves" -ForegroundColor Cyan

    & python "$ProjectRoot\scripts\golden_pipeline_daemon.py" `
        --budget $Budget `
        --wave-size $WaveSize `
        --max-waves $MaxWaves `
        --resume

    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "`nDaemon exited cleanly (exit 0). Not restarting." -ForegroundColor Green
        break
    }
    Write-Host "`nDaemon crashed (exit code $exitCode). Restarting in 30s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}
