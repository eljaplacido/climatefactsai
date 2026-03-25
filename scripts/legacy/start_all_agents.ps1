# Climate News - Kaynn start all agents
# PowerShell script to start all agents in separate windows

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " CLIMATE NEWS AGENTS STARTING" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

$scriptPath = $PSScriptRoot
$env:PYTHONPATH = $scriptPath

# Check venv exists
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "`nVirtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
.\venv\Scripts\pip.exe install -q python-json-logger beautifulsoup4 playwright lxml requests feedparser spacy 2>&1 | Out-Null

Write-Host "Starting Orchestrator..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$scriptPath'; cd '$scriptPath'; `$host.UI.RawUI.WindowTitle = 'Orchestrator'; Clear-Host; Write-Host '==========================================' -ForegroundColor Magenta; Write-Host ' ORCHESTRATOR AGENT' -ForegroundColor Magenta; Write-Host '==========================================' -ForegroundColor Magenta; Write-Host ''; try { python -m agents.orchestrator.main } catch { Write-Host `$_.Exception.Message -ForegroundColor Red; Read-Host 'Press Enter' }"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting Content Discovery..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$scriptPath'; cd '$scriptPath'; `$host.UI.RawUI.WindowTitle = 'Content Discovery'; Clear-Host; Write-Host '==========================================' -ForegroundColor Cyan; Write-Host ' CONTENT DISCOVERY AGENT' -ForegroundColor Cyan; Write-Host '==========================================' -ForegroundColor Cyan; Write-Host ''; try { python -m agents.content_discovery.main } catch { Write-Host `$_.Exception.Message -ForegroundColor Red; Read-Host 'Press Enter' }"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting Fact-Checking..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONPATH='$scriptPath'; cd '$scriptPath'; `$host.UI.RawUI.WindowTitle = 'Fact-Checking'; Clear-Host; Write-Host '==========================================' -ForegroundColor Yellow; Write-Host ' FACT-CHECKING AGENT' -ForegroundColor Yellow; Write-Host '==========================================' -ForegroundColor Yellow; Write-Host ''; try { python -m agents.fact_checking.main } catch { Write-Host `$_.Exception.Message -ForegroundColor Red; Read-Host 'Press Enter' }"
) -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "`n"
Write-Host "=============================================" -ForegroundColor Green
Write-Host " AGENTS STARTED!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host "`nCheck agent windows:" -ForegroundColor Cyan
Write-Host "  - Orchestrator (magenta)" -ForegroundColor White
Write-Host "  - Content Discovery (cyan)" -ForegroundColor White  
Write-Host "  - Fact-Checking (yellow)" -ForegroundColor White
Write-Host "`nGo to Admin Panel and click 'Start workflow'!" -ForegroundColor Yellow
Write-Host "   http://localhost:3000/admin" -ForegroundColor Cyan
Write-Host "`n"

# Open Admin Panel
Start-Sleep -Seconds 2
start http://localhost:3000/admin
