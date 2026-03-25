# Climate News - Simple Startup Script

Write-Host ""
Write-Host "=========================================="
Write-Host " Climate News Web Application"
Write-Host "=========================================="
Write-Host ""

# Check Docker
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: Docker is running" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker not found!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting Docker services..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start services!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for services to start (30 seconds)..." -ForegroundColor Yellow

for ($i = 30; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r   $i seconds remaining..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
}

Write-Host "`r   Done!                    " -ForegroundColor Green

Write-Host ""
Write-Host "=========================================="
Write-Host " Web Application Started!"
Write-Host "=========================================="
Write-Host ""

Write-Host "Open in browser:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Web App:      http://localhost:3000" -ForegroundColor Yellow
Write-Host "  Admin Panel:  http://localhost:3000/admin" -ForegroundColor Yellow
Write-Host "  API Docs:     http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""

Write-Host "First time using?" -ForegroundColor Cyan
Write-Host "  1. Go to: http://localhost:3000/admin" -ForegroundColor White
Write-Host "  2. Click 'Start workflow' button" -ForegroundColor White
Write-Host "  3. Wait 2-5 minutes" -ForegroundColor White
Write-Host "  4. Refresh homepage - articles will appear!" -ForegroundColor White
Write-Host ""

# Open browser
Write-Host "Opening browser..." -ForegroundColor Gray
Start-Sleep -Seconds 2
start http://localhost:3000

Write-Host ""
Write-Host "Enjoy Climate News!" -ForegroundColor Green
Write-Host ""
