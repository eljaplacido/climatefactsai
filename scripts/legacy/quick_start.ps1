# Quick Start - Infrastructure Only (No Agent Containers)
# This starts just the infrastructure services (Kafka, Redis, PostgreSQL, Frontend, API)

Write-Host ""
Write-Host "=========================================="
Write-Host " Climate News - Quick Start"
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
Write-Host "Starting infrastructure services only..." -ForegroundColor Yellow
Write-Host "(Kafka, Zookeeper, Redis, PostgreSQL, Frontend, API)" -ForegroundColor Gray
Write-Host ""

# Start only infrastructure services
docker-compose up -d zookeeper kafka schema-registry redis postgres

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start infrastructure!" -ForegroundColor Red
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
Write-Host "Checking service status..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "=========================================="
Write-Host " Infrastructure Started!"
Write-Host "=========================================="
Write-Host ""

Write-Host "Services running:" -ForegroundColor Cyan
Write-Host "  - Kafka:      localhost:9092" -ForegroundColor Green
Write-Host "  - PostgreSQL: localhost:5433" -ForegroundColor Green
Write-Host "  - Redis:      localhost:6379" -ForegroundColor Green
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check QUICK_START_WEB.md for frontend setup" -ForegroundColor White
Write-Host "  2. Or run: python run_full_pipeline.py" -ForegroundColor White
Write-Host ""

Write-Host "To stop services:" -ForegroundColor Gray
Write-Host "  docker-compose down" -ForegroundColor White
Write-Host ""
