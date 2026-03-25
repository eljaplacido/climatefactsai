<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# 🚀 Pikaopas - Climate News Web-sovellus

## Käynnistä 3 minuutissa

### 1. Käynnistä kaikki palvelut

```powershell
# PowerShell (Windows)
docker-compose up -d

# Odota 30 sekuntia
Start-Sleep -Seconds 30
```

### 2. Avaa selaimessa

- 🌐 **Web-sovellus:** http://localhost:5300
- 🔧 **API-dokumentaatio:** http://localhost:5200/docs  
- 👨‍💼 **Admin-paneeli:** http://localhost:5300/admin

### 3. Ensimmäinen käyttökerta

Jos ei vielä ole artikkeleita:

1. Mene → http://localhost:5300/admin
2. Paina **"Käynnistä workflow"**
3. Odota 2-5 minuuttia
4. Päivitä etusivu → Artikkelit ilmestyvät!

---

## Mitä näet

### Etusivu (http://localhost:3000)

```
┌──────────────────────────────────────────┐
│ 🌍 Climate News Finland                 │
│ Todennetut Ilmastouutiset Suomesta      │
├──────────────────────────────────────────┤
│                                          │
│ 📊 Tilastot:                             │
│  [10 Artikkelia] [3 Tänään] [28 Faktaa] │
│                                          │
│ 🔍 Suodata: [Kaikki][Korkea][Keskitaso] │
│                                          │
│ ┌────────────────────────────────────┐   │
│ │ 📰 Helsinki lämpötila nousi...     │   │
│ │ YLE • ✅ Korkea luotettavuus       │   │
│ │ "Helsinki saavutti uuden lämpö..." │   │
│ │ ────────────────────────────────   │   │
│ │ 3 väitettä tarkistettu  [████] 100%│   │
│ └────────────────────────────────────┘   │
│                                          │
│ [Lisää artikkeleita...]                  │
└──────────────────────────────────────────┘
```

**Klikkaa artikkelia** → Näet faktatarkistukset!

---

### Artikkelin yksityiskohdat

```
┌──────────────────────────────────────────┐
│ ← Takaisin                               │
│                                          │
│ Helsinki lämpötila nousi ennätyslukemiin │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                          │
│ 📅 15.10.2024 • ✍️ Kirjoittaja           │
│ 🔗 Avaa alkuperäinen →                   │
│                                          │
│ [Koko artikkelin teksti...]              │
│                                          │
│ ✅ Faktatarkistukset (3)                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                          │
│ 📌 "Helsinki saavutti 28°C lämpötilan"   │
│    ✅ Todennettu (95%)                   │
│    Perustelu: NOAA-data vahvistaa...     │
│    ClimateCheck: Heat Risk 7.5           │
│                                          │
│ 📌 "Lämpötila oli korkein 50 vuoteen"    │
│    ⚠️ Osittain todennettu (73%)          │
│    Perustelu: Historiallinen data...     │
│                                          │
│ 📊 Yhteenveto                            │
│    Kokonaisluotettavuus: KORKEA          │
│    Todennettuja: 2/3                     │
└──────────────────────────────────────────┘
```

---

### Admin-paneeli (http://localhost:3000/admin)

```
┌──────────────────────────────────────────┐
│ 🎛️ Hallintapaneeli                       │
│                                          │
│ 📊 Tilastot (sama kuin etusivulla)       │
│                                          │
│ ⚙️ Workflow-hallinta                     │
│ ┌────────────────────────────────────┐   │
│ │ Käynnistä workflow manuaalisesti   │   │
│ │                       [Käynnistä]  │   │
│ └────────────────────────────────────┘   │
│                                          │
│ 📜 Workflow-historia                     │
│ ┌────────────────────────────────────┐   │
│ │ Task ID      | Status | Aloitettu  │   │
│ │ task-001     | ✅ DONE | 14:30     │   │
│ │ task-002     | 🟡 RUN  | 15:00     │   │
│ └────────────────────────────────────┘   │
│                                          │
│ 🖥️ Järjestelmä                           │
│    Orchestrator      🟢 Aktiivinen       │
│    Content Discovery 🟢 Aktiivinen       │
│    Fact-Checking     🟢 Aktiivinen       │
└──────────────────────────────────────────┘
```

---

## Workflow - Mitä tapahtuu kun painat "Käynnistä"

```
1. [API] Lähettää käskyn Kafka → orchestrator_commands
         ↓
2. [Orchestrator] Vastaanottaa käskyn
         ↓
3. [Content Discovery] Scannaa YLE, HS RSS-feedit
         → Löytää 5-10 artikkelia
         ↓
4. [Content Discovery] Tunnistaa väitteet NLP:llä
         → 15-30 väitettä tunnistettu
         ↓
5. [Fact-Checking] Todentaa väitteet:
         → ClimateCheck API
         → NOAA climate data
         → GPT-4o analyysi
         ↓
6. [PostgreSQL] Tallennetaan kaikki
         ↓
7. ✅ VALMIS! Päivitä etusivu
```

**Kesto:** 2-5 minuuttia riippuen artikkelien määrästä

---

## Testaa heti

### 1. Avaa web-sovellus

```powershell
# Windowsissa
start http://localhost:3000

# TAI selaimessa kirjoita osoitepalkkiin
http://localhost:3000
```

### 2. Jos ei artikkeleita

```powershell
# Mene admin-paneeliin
start http://localhost:3000/admin

# Paina "Käynnistä workflow"
# Odota 3 min
# Päivitä etusivu
```

### 3. Testaa API suoraan

```powershell
# Hae artikkelit
curl http://localhost:5200/api/articles

# Hae tilastot
curl http://localhost:5200/api/stats

# API-dokumentaatio (selaimessa)
start http://localhost:5200/docs
```

---

## Pysäytä järjestelmä

```powershell
# Pysäytä kaikki
docker-compose down

# Pysäytä JA poista kaikki data (VAROITUS!)
docker-compose down -v
```

---

## Ongelmat?

### Artikkelit eivät näy

```powershell
# Tarkista tietokanta
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Suorita:
SELECT COUNT(*) FROM articles;

# Jos 0 → Käynnistä workflow admin-paneelista
```

### Palvelu ei käynnisty

```powershell
# Katso lokit
docker-compose logs api
docker-compose logs frontend

# Käynnistä uudelleen
docker-compose restart api frontend
```

### Port jo käytössä

```powershell
# Jos 3000 tai 8000 on varattu:
# Muokkaa docker-compose.yml:
# api: ports: - "8001:8000"
# frontend: ports: - "3001:80"
```

---

## Teknologiat

- **Frontend:** React 18 + TypeScript + Tailwind CSS + Vite
- **Backend:** FastAPI + Python 3.11
- **Database:** PostgreSQL 16
- **Hosting:** Docker + Nginx

---

## Loistava! 🎉

Sinulla on nyt:
- ✅ Moderni web-sovellus
- ✅ Admin-hallintapaneeli
- ✅ REST API
- ✅ Automaattinen faktatarkistus
- ✅ Kaunis, responsiivinen UI

**Seuraavat askeleet:**
1. Kokeile eri suodattimia
2. Klikkaa artikkeleita ja tutki faktatarkistuksia
3. Käynnistä workflow admin-paneelista
4. Tutustu API-dokumentaatioon

**Lisätietoja:** Katso [WEB_APP_GUIDE.md](WEB_APP_GUIDE.md)

