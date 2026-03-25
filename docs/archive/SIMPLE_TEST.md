<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# Simple Testing Guide - Climate News

Since the Docker agent containers have build issues, let's test the system using the **run_full_pipeline.py** script which runs everything locally.

## Option 1: Run Full Pipeline (Recommended for Testing)

### Step 1: Start Infrastructure Services
```powershell
# Start only infrastructure (this will work)
docker-compose up -d zookeeper kafka redis postgres

# Wait for services
Start-Sleep -Seconds 30

# Check status
docker-compose ps
```

### Step 2: Check Your Virtual Environment
```powershell
# Make sure you're in the virtual environment
.\venv\Scripts\Activate.ps1

# If you see (venv) in your prompt, you're good!
```

### Step 3: Run the Pipeline
```powershell
# Run the full pipeline script
python run_full_pipeline.py
```

This will:
- ✅ Fetch real news from Perplexity API
- ✅ Extract claims from articles
- ✅ Fact-check the claims
- ✅ Save everything to PostgreSQL
- ✅ Generate summaries

### Step 4: Check the Database
```powershell
# Connect to PostgreSQL
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Check articles
SELECT title, author, published_date FROM articles LIMIT 5;

# Check claims
SELECT claim_text, claim_type FROM claims LIMIT 5;

# Check fact-checks
SELECT verification_status, confidence_score FROM fact_checks LIMIT 5;

# Exit PostgreSQL
\q
```

---

## Option 2: Quick Infrastructure Test

### Just Infrastructure Only
```powershell
.\quick_start.ps1
```

This starts:
- ✅ Kafka (message queue)
- ✅ PostgreSQL (database)
- ✅ Redis (cache)
- ✅ Zookeeper (Kafka dependency)

---

## Checking What's Running

```powershell
# See all running containers
docker-compose ps

# See logs
docker-compose logs kafka
docker-compose logs postgres
docker-compose logs redis

# Stop everything
docker-compose down
```

---

## Testing the New Features We Added

### 1. Test Author/Date/Language Extraction
```powershell
# Run the pipeline
python run_full_pipeline.py

# Check database for author and date fields
docker exec -it climatenews-postgres psql -U postgres -d climatenews -c "SELECT title, author, published_date, language FROM articles WHERE author IS NOT NULL LIMIT 5;"
```

### 2. Test Claim Types
```powershell
# Check claim types in database
docker exec -it climatenews-postgres psql -U postgres -d climatenews -c "SELECT claim_text, claim_type FROM claims LIMIT 10;"
```

You should see different claim types:
- `factual_data`
- `prediction`
- `scientific_claim`
- `statistical_claim`
- etc.

### 3. Test Video Production Agent (Structure Only)
```powershell
# The video production agent is now implemented
# To test it would run (but needs API keys):
cd agents
python -m video_production.main
```

---

## Expected Results

After running `python run_full_pipeline.py`:

```
✅ Articles fetched: 10-15
✅ Claims extracted: 30-50
✅ Claims verified: 30-50
✅ Summaries created: 1-3
✅ All data in PostgreSQL
```

---

## Troubleshooting

### "Module not found" errors
```powershell
# Make sure you're in venv
.\venv\Scripts\Activate.ps1

# Install dependencies
cd agents
pip install -r requirements.txt
```

### API Key errors
Make sure your `.env` file has:
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
```

### Docker not running
```powershell
# Start Docker Desktop
# Then retry:
docker ps
```

---

## What Works vs What Needs Docker Fixes

### ✅ Works Right Now:
- Infrastructure (Kafka, PostgreSQL, Redis)
- Python pipeline scripts
- Database operations
- All the new features we added (author/date/language extraction, claim types, retry logic)

### ⚠️ Needs Docker Fixes:
- Agent containers (orchestrator, content-discovery, fact-checking, etc.)
- Frontend/API containers
- Full web UI

### 🎯 Best Way to Test Our Changes:
Run the pipeline script directly:
```powershell
python run_full_pipeline.py
```

This tests all the code we modified without needing Docker containers!

---

## Stop Everything

```powershell
# Stop infrastructure
docker-compose down

# Stop and remove all data (WARNING: deletes everything)
docker-compose down -v
```
