# Start Web UI Locally (without Docker containers)
# This runs Frontend + API directly on your machine

Write-Host ""
Write-Host "=========================================="
Write-Host " Climate News - Local Web UI Startup"
Write-Host "=========================================="
Write-Host ""

# Step 1: Start infrastructure
Write-Host "Step 1: Starting infrastructure (PostgreSQL, Kafka, Redis)..." -ForegroundColor Cyan
docker-compose up -d postgres kafka zookeeper redis

Write-Host "Waiting 20 seconds for services..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Step 2: Start API in background
Write-Host ""
Write-Host "Step 2: Starting FastAPI backend..." -ForegroundColor Cyan
Write-Host "API will run on http://localhost:8000" -ForegroundColor Gray
Write-Host "Note: API connects to infrastructure services on updated ports (Redis:5379, Postgres:5433, Kafka:5092)" -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd api; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 3

# Step 3: Install frontend dependencies (if needed)
Write-Host ""
Write-Host "Step 3: Setting up frontend..." -ForegroundColor Cyan

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies (this may take a few minutes)..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
} else {
    Write-Host "Frontend dependencies already installed" -ForegroundColor Green
}

# Step 4: Start frontend dev server
Write-Host ""
Write-Host "Step 4: Starting React frontend..." -ForegroundColor Cyan
Write-Host "Frontend will run on http://localhost:5173" -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host ""
Write-Host "=========================================="
Write-Host " Web UI Started Successfully!"
Write-Host "=========================================="
Write-Host ""

Write-Host "Open in browser:" -ForegroundColor Green
Write-Host "  Frontend:  http://localhost:5173" -ForegroundColor Yellow
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""

Write-Host "Note: Vite dev server runs on port 5173 (not 3000)" -ForegroundColor Gray
Write-Host ""

Write-Host "Opening browser in 5 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 5
start http://localhost:5173

Write-Host ""
Write-Host "To stop: Close the PowerShell windows and run 'docker-compose down'" -ForegroundColor Gray
Write-Host ""
