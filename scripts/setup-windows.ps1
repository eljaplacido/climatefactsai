# =============================================================================
# Climate News MAS - Windows Setup Script
# =============================================================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Climate News Multi-Agent System" -ForegroundColor Cyan
Write-Host " Windows Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Tarkista että ollaan oikeassa hakemistossa
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ Error: docker-compose.yml not found!" -ForegroundColor Red
    Write-Host "Please run this script from the project root directory." -ForegroundColor Yellow
    exit 1
}

# Tarkista Docker
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker found: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not found!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Tarkista Python
Write-Host ""
Write-Host "Step 2: Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = py -3.11 --version
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Tarkista .env-tiedosto
Write-Host ""
Write-Host "Step 3: Checking .env file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✓ .env file exists" -ForegroundColor Green
} else {
    Write-Host "⚠ .env file not found, creating from template..." -ForegroundColor Yellow
    
    # Luo .env-pohja
    @"
# LLM API Keys (REQUIRED)
ANTHROPIC_API_KEY=your-claude-api-key-here
OPENAI_API_KEY=your-openai-api-key-here

# Climate Data APIs (OPTIONAL)
CLIMATECHECK_API_KEY=
NOAA_API_TOKEN=
NASA_API_KEY=DEMO_KEY

# Database
POSTGRES_PASSWORD=  # Set your database password here

# Target Location
TARGET_LOCATION_NAME=Helsinki
TARGET_LOCATION_LATITUDE=60.1699
TARGET_LOCATION_LONGITUDE=24.9384
TARGET_LOCATION_COUNTRY=FI

# News Sources (RSS feeds)
NEWS_SOURCES=https://yle.fi/rss/uutiset.rss

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
"@ | Out-File -FilePath '.env' -Encoding UTF8
    Write-Host 'Created .env file' -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠ IMPORTANT: Please edit .env and add your API keys!" -ForegroundColor Yellow
    Write-Host "  - ANTHROPIC_API_KEY (Claude)" -ForegroundColor Yellow
    Write-Host "  - OPENAI_API_KEY (GPT-4)" -ForegroundColor Yellow
}

# Käynnistä infrastruktuuri
Write-Host ""
Write-Host "Step 4: Starting infrastructure services..." -ForegroundColor Yellow
Write-Host "  (Kafka, Redis, PostgreSQL)" -ForegroundColor Gray

docker-compose up -d zookeeper kafka schema-registry redis postgres

# Odota että palvelut ovat valmiita
Write-Host ""
Write-Host "Waiting for services to be ready (20 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Tarkista palvelut
Write-Host ""
Write-Host "Step 5: Checking service health..." -ForegroundColor Yellow

# Kafka
Write-Host -NoNewline "  Kafka: " -ForegroundColor Gray
try {
    docker exec climatenews-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Running" -ForegroundColor Green
    } else {
        Write-Host "❌ Not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Error" -ForegroundColor Red
}

# Redis
Write-Host -NoNewline "  Redis: " -ForegroundColor Gray
try {
    $redisPing = docker exec climatenews-redis redis-cli ping 2>&1
    if ($redisPing -eq "PONG") {
        Write-Host "✓ Running" -ForegroundColor Green
    } else {
        Write-Host "❌ Not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Error" -ForegroundColor Red
}

# PostgreSQL
Write-Host -NoNewline "  PostgreSQL: " -ForegroundColor Gray
try {
    docker exec climatenews-postgres pg_isready -U postgres 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Running" -ForegroundColor Green
    } else {
        Write-Host "❌ Not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Error" -ForegroundColor Red
}

# Luo Kafka-aiheet
Write-Host ""
Write-Host "Step 6: Creating Kafka topics..." -ForegroundColor Yellow

$topics = @(
    "discovery_queue",
    "fact_checking_queue",
    "creation_queue",
    "video_queue",
    "publication_queue",
    "orchestrator_commands"
)

foreach ($topic in $topics) {
    Write-Host -NoNewline "  $topic" ": " -ForegroundColor Gray
    docker exec climatenews-kafka kafka-topics `
        --bootstrap-server localhost:9092 `
        --create `
        --topic $topic `
        --partitions 3 `
        --replication-factor 1 `
        --if-not-exists 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓" -ForegroundColor Green
    } else {
        Write-Host "❌" -ForegroundColor Red
    }
}

# Asenna Python-riippuvuudet
Write-Host ""
Write-Host "Step 7: Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "  (This may take a few minutes)" -ForegroundColor Gray

if (-not (Test-Path "venv")) {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    py -3.11 -m venv venv
}

Write-Host "  Installing packages..." -ForegroundColor Gray
& ".\venv\Scripts\pip.exe" install --quiet --upgrade pip
& ".\venv\Scripts\pip.exe" install --quiet -r agents\requirements.txt
& ".\venv\Scripts\pip.exe" install --quiet pytest pytest-cov pytest-mock kafka-python

Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Yhteenveto
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Setup Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ Infrastructure is running" -ForegroundColor Green
Write-Host "✓ Kafka topics created" -ForegroundColor Green
Write-Host "✓ Python dependencies installed" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env and add your API keys" -ForegroundColor White
Write-Host "  2. Start agents: docker-compose up -d" -ForegroundColor White
Write-Host "  3. Run tests: .\venv\Scripts\activate; pytest tests/" -ForegroundColor White
Write-Host "  4. Run E2E test: .\scripts\test-e2e.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  - View logs: docker-compose logs -f [service]" -ForegroundColor White
Write-Host "  - Stop all: docker-compose down" -ForegroundColor White
Write-Host "  - Clean all: docker-compose down -v" -ForegroundColor White
Write-Host ""

