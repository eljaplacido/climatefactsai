# Climate News - Käynnistä oikeilla API-avaimilla
# Kerää oikeita uutisia YLE:stä ja tekee faktatarkistuksia

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " CLIMATE NEWS - REAL DATA MODE" -ForegroundColor Green  
Write-Host "=============================================" -ForegroundColor Green

# Aseta API-avaimet ympäristömuuttujiksi
Write-Host "`n1️⃣ Asetetaan API-avaimet..." -ForegroundColor Yellow

# Perplexity (fact-checking)
# Set these in your .env file or export before running
if (-not $env:PERPLEXITY_API_KEY) { Write-Host "WARNING: PERPLEXITY_API_KEY not set" -ForegroundColor Red }
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = $env:POSTGRES_PASSWORD }
$env:POSTGRES_PORT = "5433"

# Python path
$env:PYTHONPATH = $PWD

Write-Host "  Perplexity API key set" -ForegroundColor Green
Write-Host "  Database config set" -ForegroundColor Green

# Pysäytä vanhat prosessit
Write-Host "`n2️⃣ Pysäytetään vanhat prosessit..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>&1 | Out-Null
taskkill /F /IM python3.13.exe 2>&1 | Out-Null
Start-Sleep -Seconds 2
Write-Host "  Vanhat prosessit pysäytetty" -ForegroundColor Green

# Käynnistä agentit
Write-Host "`n3️⃣ Käynnistetään agentit..." -ForegroundColor Yellow

# Orchestrator
Write-Host "  Käynnistetään Orchestrator..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$PWD'; `$env:PERPLEXITY_API_KEY='$env:PERPLEXITY_API_KEY'; `$env:POSTGRES_PASSWORD=$env:POSTGRES_PASSWORD; `$env:POSTGRES_PORT='5433'; `$host.UI.RawUI.WindowTitle='Orchestrator'; Clear-Host; Write-Host '==========================================' -ForegroundColor Magenta; Write-Host ' ORCHESTRATOR AGENT' -ForegroundColor Magenta; Write-Host '==========================================' -ForegroundColor Magenta; Write-Host ''; python -m agents.orchestrator.main"
) -WindowStyle Normal

Start-Sleep -Seconds 3

# Content Discovery
Write-Host "  Käynnistetään Content Discovery..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$PWD'; `$env:PERPLEXITY_API_KEY='$env:PERPLEXITY_API_KEY'; `$env:POSTGRES_PASSWORD=$env:POSTGRES_PASSWORD; `$env:POSTGRES_PORT='5433'; `$host.UI.RawUI.WindowTitle='Content Discovery'; Clear-Host; Write-Host '==========================================' -ForegroundColor Cyan; Write-Host ' CONTENT DISCOVERY AGENT' -ForegroundColor Cyan; Write-Host '==========================================' -ForegroundColor Cyan; Write-Host ''; python -m agents.content_discovery.main"
) -WindowStyle Normal

Start-Sleep -Seconds 3

# Fact-Checking
Write-Host "  Käynnistetään Fact-Checking (with Perplexity)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$PWD'; `$env:PERPLEXITY_API_KEY='$env:PERPLEXITY_API_KEY'; `$env:POSTGRES_PASSWORD=$env:POSTGRES_PASSWORD; `$env:POSTGRES_PORT='5433'; `$host.UI.RawUI.WindowTitle='Fact-Checking + Perplexity'; Clear-Host; Write-Host '==========================================' -ForegroundColor Yellow; Write-Host ' FACT-CHECKING AGENT (Perplexity)' -ForegroundColor Yellow; Write-Host '==========================================' -ForegroundColor Yellow; Write-Host ''; python -m agents.fact_checking.main"
) -WindowStyle Normal

Write-Host "`n4️⃣ Odotetaan että agentit käynnistyvät..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "`n"
Write-Host "=============================================" -ForegroundColor Green
Write-Host " AGENTIT KÄYNNISSÄ!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

Write-Host "`nKäynnissä olevat agentit:" -ForegroundColor Cyan
Write-Host "  Orchestrator (magenta)" -ForegroundColor Magenta
Write-Host "  Content Discovery (cyan)" -ForegroundColor Cyan
Write-Host "  Fact-Checking with Perplexity (yellow)" -ForegroundColor Yellow

Write-Host "`nSEURA AGENTTIIKKUNOITA!" -ForegroundColor White
Write-Host "Ne näyttävät mitä tapahtuu reaaliajassa.`n" -ForegroundColor Gray

Write-Host "Nyt mene Admin Paneliin ja paina 'Käynnistä workflow'!" -ForegroundColor Yellow
Write-Host "http://localhost:3000/admin`n" -ForegroundColor Cyan

# Avaa Admin Panel
Start-Sleep -Seconds 2
start http://localhost:3000/admin

