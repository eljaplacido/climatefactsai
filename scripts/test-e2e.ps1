# =============================================================================
# Climate News MAS - End-to-End Test Script (PowerShell)
# =============================================================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Climate News Multi-Agent System" -ForegroundColor Cyan
Write-Host " End-to-End Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Tarkista että Docker on käynnissä
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    $dockerCheck = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker is not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not found!" -ForegroundColor Red
    exit 1
}

# Tarkista että palvelut ovat käynnissä
Write-Host ""
Write-Host "Checking services..." -ForegroundColor Yellow
$services = docker-compose ps --services --filter "status=running"
$requiredServices = @("kafka", "redis", "postgres")

foreach ($service in $requiredServices) {
    if ($services -contains $service) {
        Write-Host "✓ $service is running" -ForegroundColor Green
    } else {
        Write-Host "❌ $service is NOT running!" -ForegroundColor Red
        Write-Host "Start it with: docker-compose up -d $service" -ForegroundColor Yellow
        exit 1
    }
}

# Generoi task ID
$timestamp = Get-Date -Format "yyyyMMdd"
$taskId = "task-$timestamp-e2e"

Write-Host ""
Write-Host "Test Task ID: $taskId" -ForegroundColor Cyan

# Tarkista Python ja kafka-python
Write-Host ""
Write-Host "Checking Python dependencies..." -ForegroundColor Yellow
try {
    python -c "import kafka" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ kafka-python not installed!" -ForegroundColor Red
        Write-Host "Install with: pip install kafka-python" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "✓ kafka-python is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    exit 1
}

# Lähetä workflow-käsky
Write-Host ""
Write-Host "Sending workflow trigger..." -ForegroundColor Yellow

$pythonScript = @"
from kafka import KafkaProducer
import json
from datetime import datetime
import sys

try:
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    message = {
        'command': 'manual_trigger',
        'taskId': '$taskId',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    producer.send('orchestrator_commands', message)
    producer.flush()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"@

$result = python -c $pythonScript
if ($result -eq "SUCCESS") {
    Write-Host "✓ Workflow trigger sent!" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to send workflow trigger!" -ForegroundColor Red
    Write-Host "Error: $result" -ForegroundColor Red
    exit 1
}

# Odota prosessointia
Write-Host ""
Write-Host "Waiting for processing (30 seconds)..." -ForegroundColor Yellow
for ($i = 30; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r  $i seconds remaining..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
}
Write-Host "`r  ✓ Wait complete!          " -ForegroundColor Green

# Tarkista tulokset
Write-Host ""
Write-Host "Checking results..." -ForegroundColor Yellow
Write-Host ""

# Redis state
Write-Host "  Redis State:" -ForegroundColor Cyan
$redisState = docker exec climatenews-redis redis-cli GET "task:$taskId" 2>&1
if ($redisState) {
    Write-Host "  ✓ Task state found in Redis" -ForegroundColor Green
    # Parse JSON and show status
    try {
        $stateJson = $redisState | ConvertFrom-Json
        Write-Host "    Status: $($stateJson.status)" -ForegroundColor White
    } catch {
        Write-Host "    $redisState" -ForegroundColor White
    }
} else {
    Write-Host "  ❌ Task state NOT found in Redis" -ForegroundColor Red
}

Write-Host ""

# PostgreSQL - Articles
Write-Host "  PostgreSQL - Articles:" -ForegroundColor Cyan
$articleCount = docker exec climatenews-postgres psql -U postgres -d climatenews -t -c "SELECT COUNT(*) FROM articles WHERE task_id='$taskId';" 2>&1
if ($articleCount -match '\d+') {
    $count = [int]($articleCount -replace '\D', '')
    if ($count -gt 0) {
        Write-Host "  ✓ Found $count articles" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ No articles found yet" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ Failed to query articles" -ForegroundColor Red
}

Write-Host ""

# PostgreSQL - Fact-checks
Write-Host "  PostgreSQL - Fact-checks:" -ForegroundColor Cyan
$factCheckCount = docker exec climatenews-postgres psql -U postgres -d climatenews -t -c "SELECT COUNT(*) FROM fact_checks WHERE task_id='$taskId';" 2>&1
if ($factCheckCount -match '\d+') {
    $count = [int]($factCheckCount -replace '\D', '')
    if ($count -gt 0) {
        Write-Host "  ✓ Found $count fact-checks" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ No fact-checks found yet" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ Failed to query fact-checks" -ForegroundColor Red
}

Write-Host ""

# Workflow logs
Write-Host "  Workflow Logs (last 5):" -ForegroundColor Cyan
docker exec climatenews-postgres psql -U postgres -d climatenews -c "SELECT stage, event_type, status, timestamp FROM workflow_logs WHERE task_id='$taskId' ORDER BY timestamp DESC LIMIT 5;" 2>&1 | ForEach-Object {
    if ($_ -match '\w') {
        Write-Host "    $_" -ForegroundColor White
    }
}

# Yhteenveto
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Test Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Task ID: $taskId" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check logs: docker-compose logs -f orchestrator" -ForegroundColor White
Write-Host "  2. Monitor Redis: docker exec -it climatenews-redis redis-cli" -ForegroundColor White
Write-Host "  3. Query database: docker exec -it climatenews-postgres psql -U postgres -d climatenews" -ForegroundColor White
Write-Host ""
Write-Host "✓ End-to-End test complete!" -ForegroundColor Green
Write-Host ""

