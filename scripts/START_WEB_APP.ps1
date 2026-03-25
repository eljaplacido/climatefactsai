# =============================================================================
# Climate News Web-sovelluksen käynnistys
# =============================================================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " 🌍 Climate News Web-sovellus" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Tarkista Docker
Write-Host "Tarkistetaan Docker..." -ForegroundColor Yellow
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker ei ole käynnissä!" -ForegroundColor Red
        Write-Host "Käynnistä Docker Desktop ja yritä uudelleen." -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Docker toimii" -ForegroundColor Green
} catch {
    Write-Host "❌ Dockeria ei löytynyt!" -ForegroundColor Red
    exit 1
}

# Tarkista .env
Write-Host ""
Write-Host "Tarkistetaan .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env-tiedostoa ei löydy" -ForegroundColor Yellow
    Write-Host "Luodaan .env .env.example-pohjasta..." -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✓ .env luotu" -ForegroundColor Green
        Write-Host ""
        Write-Host "⚠️  HUOM: Muista lisätä API-avaimet .env-tiedostoon!" -ForegroundColor Yellow
        Write-Host "   - ANTHROPIC_API_KEY" -ForegroundColor White
        Write-Host "   - OPENAI_API_KEY" -ForegroundColor White
        Write-Host ""
        
        $continue = Read-Host "Jatka silti? (Y/N)"
        if ($continue -ne "Y" -and $continue -ne "y") {
            exit 0
        }
    } else {
        Write-Host "❌ .env.example ei löydy!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ .env löytyy" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Käynnistetään palvelut..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Käynnistä kaikki palvelut
Write-Host "📦 Käynnistetään Docker-palvelut..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Virhe käynnistettäessä palveluita!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "⏳ Odotetaan että palvelut käynnistyvät (30 sekuntia)..." -ForegroundColor Yellow

for ($i = 30; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r   $i sekuntia jäljellä..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
}

Write-Host "`r   ✓ Odotus valmis!          " -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Tarkistetaan palveluiden tila..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Tarkista palvelut
$services = docker-compose ps --services --filter "status=running"
$requiredServices = @("api", "frontend", "postgres", "redis", "kafka")

$allRunning = $true
foreach ($service in $requiredServices) {
    if ($services -contains $service) {
        Write-Host "   ✓ $service käynnissä" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $service EI käynnissä!" -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Host ""
    Write-Host "⚠️  Kaikki palvelut eivät käynnistyneet!" -ForegroundColor Yellow
    Write-Host "Katso lokit: docker-compose logs" -ForegroundColor White
    Write-Host ""
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " ✅ Web-sovellus käynnistetty!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Avaa selaimessa:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  🌐 Web-sovellus:      " -NoNewline
Write-Host "http://localhost:5300" -ForegroundColor Yellow
Write-Host ""
Write-Host "  👨‍💼 Admin-paneeli:     " -NoNewline
Write-Host "http://localhost:5300/admin" -ForegroundColor Yellow
Write-Host ""
Write-Host "  📚 API-dokumentaatio: " -NoNewline
Write-Host "http://localhost:5200/docs" -ForegroundColor Yellow
Write-Host ""

Write-Host ""
Write-Host "💡 Ensimmäinen käyttökerta?" -ForegroundColor Cyan
Write-Host "   1. Mene: http://localhost:5300/admin" -ForegroundColor White
Write-Host "   2. Paina 'Käynnistä workflow'" -ForegroundColor White
Write-Host "   3. Odota 2-5 minuuttia" -ForegroundColor White
Write-Host "   4. Päivitä etusivu - artikkelit ilmestyvät!" -ForegroundColor White
Write-Host ""

Write-Host "📖 Lisätietoja: WEB_APP_GUIDE.md tai QUICK_START_WEB.md" -ForegroundColor Gray
Write-Host ""

# Avaa selain automaattisesti
Write-Host "Avataan web-sovellus selaimessa..." -ForegroundColor Gray
Start-Sleep -Seconds 2
start http://localhost:5300

Write-Host ""
Write-Host "✨ Nauti Climate News -sovelluksesta!" -ForegroundColor Green
Write-Host ""


