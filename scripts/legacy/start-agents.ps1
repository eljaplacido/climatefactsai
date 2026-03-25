# Climate News MAS - Käynnistä agentit
# PowerShell-skripti Windows-ympäristöön

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "  CLIMATE NEWS MAS - KÄYNNISTÄ AGENTIT" -ForegroundColor Yellow
Write-Host ("=" * 80) -ForegroundColor Cyan

# 1. Tarkista että Docker-palvelut ovat käynnissä
Write-Host "`n1. Tarkistetaan Docker-palvelut..." -ForegroundColor Yellow
$services = docker-compose ps --services --filter "status=running"
$requiredServices = @("kafka", "zookeeper", "redis", "postgres")
$running = $true

foreach ($service in $requiredServices) {
    if ($services -contains $service) {
        Write-Host "   OK: $service" -ForegroundColor Green
    } else {
        Write-Host "   PUUTTUU: $service" -ForegroundColor Red
        $running = $false
    }
}

if (-not $running) {
    Write-Host "`nKäynnistetään puuttuvat palvelut..." -ForegroundColor Yellow
    docker-compose up -d zookeeper kafka redis postgres
    Write-Host "Odotetaan 20 sekuntia että palvelut käynnistyvät..." -ForegroundColor Gray
    Start-Sleep -Seconds 20
}

# 2. Tarkista Python virtual environment
Write-Host "`n2. Tarkistetaan Python-ympäristö..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "   OK: Virtual environment löydetty" -ForegroundColor Green
} else {
    Write-Host "   Luodaan virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# 3. Aseta ympäristömuuttujat
$env:PYTHONPATH = "agents"
$env:LOG_LEVEL = "INFO"

# 4. Käynnistä agentit omissa PowerShell-ikkunoissaan
Write-Host "`n3. Käynnistetään agentit..." -ForegroundColor Yellow

Write-Host "   Käynnistetään Orchestrator..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:PYTHONPATH='agents'; python agents\orchestrator\main.py"

Start-Sleep -Seconds 2

Write-Host "   Käynnistetään Content Discovery..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:PYTHONPATH='agents'; python agents\content_discovery\main.py"

Start-Sleep -Seconds 2

Write-Host "   Käynnistetään Fact-Checking..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:PYTHONPATH='agents'; python agents\fact_checking\main.py"

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "  AGENTIT KÄYNNISTETTY!" -ForegroundColor Green
Write-Host ("=" * 80) -ForegroundColor Cyan

Write-Host "`nKolme uutta PowerShell-ikkunaa avautui:" -ForegroundColor White
Write-Host "  1. Orchestrator (Koordinaattori)" -ForegroundColor Cyan
Write-Host "  2. Content Discovery (Sisällön etsintä)" -ForegroundColor Cyan
Write-Host "  3. Fact-Checking (Faktojen tarkistus)" -ForegroundColor Cyan

Write-Host "`nSeuraavaksi voit:" -ForegroundColor Yellow
Write-Host "  - Suorittaa: python demo.py" -ForegroundColor White
Write-Host "  - Seurata agenttiesi lokeja avautuneissa ikkunoissa" -ForegroundColor White

Write-Host "`nPysäytä agentit painamalla Ctrl+C jokaisessa ikkunassa" -ForegroundColor Gray


