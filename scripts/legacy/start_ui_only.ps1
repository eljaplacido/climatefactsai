# Start just the UI (assumes infrastructure is already running)

Write-Host ""
Write-Host "=========================================="
Write-Host " Starting Web UI (Frontend + API)"
Write-Host "=========================================="
Write-Host ""

# Check if infrastructure is running
Write-Host "Checking infrastructure..." -ForegroundColor Yellow
$containers = docker ps --format "{{.Names}}"

if ($containers -match "postgres") {
    Write-Host "OK: PostgreSQL is running" -ForegroundColor Green
} else {
    Write-Host "WARNING: PostgreSQL not running. Start it with: docker-compose up -d postgres" -ForegroundColor Yellow
}

# Step 1: Start API
Write-Host ""
Write-Host "Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Cyan

$apiWindow = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$PWD\api'; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
) -PassThru

Start-Sleep -Seconds 3

# Step 2: Check frontend dependencies
Write-Host ""
Write-Host "Checking frontend dependencies..." -ForegroundColor Cyan

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies (one-time setup)..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
    Write-Host "Dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "OK: Dependencies already installed" -ForegroundColor Green
}

# Step 3: Start Frontend
Write-Host ""
Write-Host "Starting React frontend on http://localhost:5173 ..." -ForegroundColor Cyan

$frontendWindow = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$PWD\frontend'; npm run dev"
) -PassThru

Write-Host ""
Write-Host "=========================================="
Write-Host " Web UI is starting..."
Write-Host "=========================================="
Write-Host ""

Write-Host "Services:" -ForegroundColor Green
Write-Host "  Backend API:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  Frontend UI:  http://localhost:5173" -ForegroundColor Yellow
Write-Host ""

Write-Host "Opening browser in 8 seconds..." -ForegroundColor Gray
Write-Host "(Waiting for frontend to build...)" -ForegroundColor Gray
Start-Sleep -Seconds 8

start http://localhost:5173

Write-Host ""
Write-Host "To stop: Close the API and Frontend PowerShell windows" -ForegroundColor Gray
Write-Host ""
