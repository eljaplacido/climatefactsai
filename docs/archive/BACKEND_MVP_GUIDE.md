<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# Backend MVP Complete Guide

## ✅ Completed Features

### 1. Multi-Country Support (31+ EU Countries)
- ✅ Countries table with 31 EU/EEA countries
- ✅ Country metadata (name, native name, flag emoji, language, EU status)
- ✅ Foreign key constraint on articles table
- ✅ API endpoint `/api/countries` to list all available countries
- ✅ Country filter on `/api/articles?country=XX`

### 2. News Discovery with Country-Specific Targeting
- ✅ Perplexity AI integration for country-specific news discovery
- ✅ Automatic country_code population in articles
- ✅ Multi-lingual support (Finnish, Swedish, German, French, Spanish, etc.)
- ✅ Credibility scoring per country's known sources

### 3. Comprehensive Reliability Scoring
- ✅ Multi-factor reliability algorithm:
  - Source credibility (50%)
  - Verified claims ratio (30%)
  - Content relevance (20%)
- ✅ Categorization: HIGH (≥80), MEDIUM (50-79), LOW (<50)
- ✅ Penalty system for false/misleading claims
- ✅ Automatic content relevance calculation with multi-lingual keywords
- ✅ Integration into fact-checking pipeline

### 4. Complete Backend Pipeline
- ✅ Ingestion Service: News discovery with Perplexity
- ✅ Verification Service: Fact-checking with reliability scoring
- ✅ Content Creation Service: Article summarization
- ✅ Orchestration Service: Workflow coordination
- ✅ API Service: RESTful endpoints for frontend

## 🚀 Quick Start

### Prerequisites
```bash
# 1. Ensure PostgreSQL is running
docker-compose up -d postgres

# 2. Run database migrations
psql -h localhost -p 5433 -U postgres -d climatenews -f infrastructure/database/init.sql
# Password: climatenews123

# 3. Set environment variables
# Ensure .env file has:
# - ANTHROPIC_API_KEY
# - OPENAI_API_KEY
# - PERPLEXITY_API_KEY
# - POSTGRES_PASSWORD
```

### Running the Backend

#### Option 1: Full Stack with Docker
```bash
docker-compose up -d
```

#### Option 2: Local Development
```bash
# Terminal 1: Start API server
cd climatenews
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start ingestion service
cd src/backend/services/ingestion_service
python src/main.py

# Terminal 3: Start verification service
cd src/backend/services/verification_service
python src/main.py

# Terminal 4: Start orchestration service
cd src/backend/services/orchestration_service
python src/main.py
```

## 🧪 Testing the Backend

### Run Comprehensive Test Suite
```bash
python test_backend_mvp.py
```

This tests:
1. ✅ Database connection and countries table
2. ✅ Perplexity news discovery from multiple countries
3. ✅ Article storage with country_code
4. ✅ Reliability scoring algorithm
5. ✅ API endpoints

### Manual Testing

#### 1. Test Countries API
```bash
curl http://localhost:8000/api/countries
```

Expected: List of 31 countries with metadata

#### 2. Test Article Filtering by Country
```bash
# Get articles from Finland
curl "http://localhost:8000/api/articles?country=FI&limit=10"

# Get articles from Germany
curl "http://localhost:8000/api/articles?country=DE&limit=10"

# Get high-credibility articles from Sweden
curl "http://localhost:8000/api/articles?country=SE&credibility=HIGH&limit=10"
```

#### 3. Test Reliability Scoring
```python
from src.backend.shared.reliability_scorer import ReliabilityScorer

# Calculate score
score, level = ReliabilityScorer.calculate_reliability_score(
    source_credibility_score=85,
    total_claims=10,
    verified_claims=8,
    false_claims=1,
    misleading_claims=1,
    content_relevance_score=0.75
)

print(f"Score: {score}, Level: {level}")
# Expected: Score around 75-80, Level: HIGH or MEDIUM
```

#### 4. Test News Discovery for Multiple Countries
```python
from src.backend.services.ingestion_service.src.perplexity_news_discovery import PerplexityNewsDiscovery
import os

api_key = os.getenv("PERPLEXITY_API_KEY")
discovery = PerplexityNewsDiscovery(api_key)

# Test with different countries
countries = [
    ("Finland", "FI"),
    ("Sweden", "SE"),
    ("Germany", "DE"),
    ("France", "FR")
]

for country_name, country_code in countries:
    print(f"\nDiscovering news from {country_name}...")
    articles = discovery.discover_news(
        country=country_name,
        country_code=country_code,
        max_articles=5,
        days_back=3
    )
    print(f"Found {len(articles)} articles")
    for article in articles:
        print(f"  - {article['title'][:60]}...")
        print(f"    Credibility: {article['credibility_score']}/100")
```

## 📊 Database Schema Updates

### New Countries Table
```sql
CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL,
    country_name_native VARCHAR(100),
    flag_emoji VARCHAR(10),
    language_code CHAR(2) NOT NULL,
    is_eu_member BOOLEAN DEFAULT false,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Updated Articles Table Fields
- ✅ `country_code` - CHAR(2) with foreign key to countries table
- ✅ `tags` - TEXT[] for categorization
- ✅ `reliability_score` - INTEGER (0-100)
- ✅ `overall_credibility` - VARCHAR(20) (HIGH/MEDIUM/LOW/MIXED)
- ✅ `content_relevance_score` - DECIMAL(3,2) (0.00-1.00)
- ✅ `verified_claims_count` - INTEGER

## 🎯 Reliability Scoring Algorithm

### Formula
```
reliability_score = (
    source_credibility * 0.50 +
    verified_claims_ratio * 0.30 +
    content_relevance * 0.20
)
```

### Penalty System
- **False claims**: -100% per false claim
- **Misleading claims**: -50% per misleading claim
- **Mixed content**: Caps maximum credibility level

### Categorization Thresholds
- **HIGH**: ≥ 80 (no false claims)
- **MEDIUM**: 50-79
- **LOW**: < 50
- **MIXED**: Has false claims but overall score is high

### Content Relevance Calculation
Uses multi-lingual climate keywords:
- English: climate, emission, carbon, renewable, sustainability
- Finnish: ilmasto, päästö, hiili, uusiutuva, kestävyys
- Swedish: klimat, utsläpp, förnybar, hållbarhet
- German: klima, emission, nachhaltig, umwelt
- French: climat, émission, renouvelable, durabilité
- Spanish: clima, emisión, renovable, sostenibilidad

## 📡 API Endpoints

### Public Endpoints

| Endpoint | Method | Description | Query Params |
|----------|--------|-------------|--------------|
| `/api/countries` | GET | List all enabled countries | - |
| `/api/articles` | GET | List articles with filters | `country`, `credibility`, `tags`, `source`, `date_from`, `date_to`, `limit`, `offset` |
| `/api/articles/{id}` | GET | Get article detail with claims | - |
| `/api/tags` | GET | Popular tags | `country` (optional) |
| `/api/stats` | GET | Dashboard statistics | - |
| `/health` | GET | Health check | - |

### Example Requests

```bash
# Get all Finnish high-credibility articles
GET /api/articles?country=FI&credibility=HIGH&limit=20

# Get articles with specific tags from Sweden
GET /api/articles?country=SE&tags=renewable-energy,policy&limit=10

# Get articles from multiple sources
GET /api/articles?source=Reuters&limit=10

# Filter by date range
GET /api/articles?date_from=2025-01-01&date_to=2025-01-31

# Get Swedish renewable energy articles
GET /api/articles?country=SE&tags=renewable-energy
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
PERPLEXITY_API_KEY=pplx-...

# Database
POSTGRES_PASSWORD=climatenews123

# Optional Climate Data APIs
NOAA_API_TOKEN=your_token_here
NASA_API_KEY=DEMO_KEY

# Target Location (for legacy support)
TARGET_LOCATION_NAME=Helsinki
TARGET_LOCATION_LATITUDE=60.1699
TARGET_LOCATION_LONGITUDE=24.9384
TARGET_LOCATION_COUNTRY=FI
```

## 🌍 Supported Countries (31 total)

### Nordic Countries (5)
- 🇫🇮 FI - Finland (Suomi)
- 🇸🇪 SE - Sweden (Sverige)
- 🇩🇰 DK - Denmark (Danmark)
- 🇳🇴 NO - Norway (Norge) *EEA
- 🇮🇸 IS - Iceland (Ísland) *EEA

### Western Europe (8)
- 🇩🇪 DE - Germany (Deutschland)
- 🇫🇷 FR - France
- 🇳🇱 NL - Netherlands (Nederland)
- 🇧🇪 BE - Belgium (België)
- 🇱🇺 LU - Luxembourg
- 🇦🇹 AT - Austria (Österreich)
- 🇨🇭 CH - Switzerland (Schweiz) *EFTA
- 🇱🇮 LI - Liechtenstein *EEA

### Southern Europe (6)
- 🇪🇸 ES - Spain (España)
- 🇵🇹 PT - Portugal
- 🇮🇹 IT - Italy (Italia)
- 🇬🇷 GR - Greece (Ελλάδα)
- 🇲🇹 MT - Malta
- 🇨🇾 CY - Cyprus (Κύπρος)

### Eastern Europe (8)
- 🇵🇱 PL - Poland (Polska)
- 🇨🇿 CZ - Czech Republic (Česko)
- 🇸🇰 SK - Slovakia (Slovensko)
- 🇭🇺 HU - Hungary (Magyarország)
- 🇷🇴 RO - Romania (România)
- 🇧🇬 BG - Bulgaria (България)
- 🇸🇮 SI - Slovenia (Slovenija)
- 🇭🇷 HR - Croatia (Hrvatska)

### Baltic Countries (3)
- 🇪🇪 EE - Estonia (Eesti)
- 🇱🇻 LV - Latvia (Latvija)
- 🇱🇹 LT - Lithuania (Lietuva)

### Ireland (1)
- 🇮🇪 IE - Ireland (Éire)

## 🎉 Success Criteria

✅ **Multi-Country Support**
- All 31 countries in database
- Country filtering works
- Articles tagged with correct country_code

✅ **Reliability Scoring**
- Score calculated using multi-factor formula
- Categorization works correctly
- Penalties applied for false/misleading claims
- Content relevance calculated automatically

✅ **News Discovery**
- Perplexity discovers country-specific news
- Articles include country_code and tags
- Source credibility estimated per country

✅ **API Functionality**
- All endpoints return correct data
- Filtering by country works
- Pagination implemented
- CORS configured for frontend

## 📈 Next Steps

1. **Frontend Integration**: Connect React frontend to use country selector
2. **Workflow Testing**: Test full orchestration pipeline
3. **Performance**: Add caching for frequently accessed countries
4. **Monitoring**: Set up Grafana dashboards for reliability score distribution
5. **Expansion**: Add more countries beyond EU (UK, US, Canada, etc.)

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Connect manually
psql -h localhost -p 5433 -U postgres -d climatenews
# Password: climatenews123

# Re-run migrations
psql -h localhost -p 5433 -U postgres -d climatenews -f infrastructure/database/init.sql
```

### Perplexity API Errors
```bash
# Check API key
echo $PERPLEXITY_API_KEY

# Test manually
curl -X POST https://api.perplexity.ai/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"sonar","messages":[{"role":"user","content":"Test"}]}'
```

### Reliability Scores Not Updating
```python
# Manually trigger update
from src.backend.shared.reliability_scorer import ReliabilityScorer
from shared.database import get_postgres

db = get_postgres()
result = ReliabilityScorer.update_article_reliability(
    article_id="your-article-id",
    postgres_client=db,
    logger=None
)
print(result)
```

## 📝 Additional Resources

- [README.md](README.md) - Main project documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [API_SPECS/](docs/API_SPECS/) - OpenAPI specifications
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Comprehensive testing guide

---

**Status**: ✅ Backend MVP Complete and Functional
**Last Updated**: 2025-10-27
**Version**: 2.0.0
