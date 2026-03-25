<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# Quick Testing Guide

**Purpose:** Fast verification that the system is working

---

## 1. Start Services (First Time - 5-10 min)

```powershell
# Start all services
docker-compose up -d

# This will:
# - Build 5 microservice images
# - Pull infrastructure images (Postgres, Kafka, Redis, etc.)
# - Start all containers
```

**Wait for:** "✔ Container climatenews-xxx Started" messages for all services

---

## 2. Quick Health Checks (2 min)

### Check All Containers Running
```powershell
docker-compose ps
```

**Expected:** All services showing "Up" status

### Check API Health
```powershell
curl http://localhost:8000/health
```

**Expected:** `{"status": "healthy", "timestamp": "..."}`

### Check Frontend
Open browser: http://localhost:3000

**Expected:** Page loads (even if empty, no errors)

---

## 3. Trigger Workflow (3 min)

### Via Browser (Easiest)
1. Go to http://localhost:3000/admin
2. Click "Käynnistä workflow" or "Trigger Workflow" button
3. Wait for confirmation message

### Via Command Line
```powershell
curl -X POST http://localhost:8000/api/admin/trigger-workflow `
  -H "Content-Type: application/json" `
  -d '{}'
```

---

## 4. Monitor Execution (2 min)

### Watch Logs
```powershell
# All services
docker-compose logs -f

# Or specific service
docker-compose logs -f orchestration-service
docker-compose logs -f ingestion-service
```

**Look for:**
- ✅ "Orchestrator agent initialized"
- ✅ "Starting daily workflow"
- ✅ "Delegating to Content Discovery agent"
- ✅ "Processing..." messages
- ❌ Any ERROR or exception messages

---

## 5. Verify Results (1 min)

### Check Database
```powershell
docker exec -it climatenews-postgres psql -U postgres -d climatenews
```

```sql
-- Count articles
SELECT COUNT(*) FROM articles;

-- View latest articles
SELECT id, title, created_at
FROM articles
ORDER BY created_at DESC
LIMIT 5;

-- Exit
\q
```

### Check Frontend
Refresh http://localhost:3000

**Expected:** Articles visible (if workflow completed)

---

## Troubleshooting

### Services Won't Start
```powershell
# Check logs for errors
docker-compose logs

# Restart from scratch
docker-compose down -v
docker-compose up -d
```

### Port Already in Use
```powershell
# Find what's using the port
netstat -ano | findstr "8000"
netstat -ano | findstr "3000"

# Kill the process or change ports in docker-compose.yml
```

### Workflow Not Executing
```powershell
# Check orchestrator logs
docker-compose logs orchestration-service

# Check Kafka is running
docker-compose ps kafka

# Verify API keys in .env
cat .env | findstr API_KEY
```

---

## Expected Timeline

| Step | Duration | Total Time |
|------|----------|------------|
| First build | 5-10 min | 5-10 min |
| Services start | 30-60 sec | 6-11 min |
| Trigger workflow | 10 sec | 6-11 min |
| Workflow execution | 2-5 min | 8-16 min |
| Verify results | 1 min | 9-17 min |

**Total First Run:** ~10-20 minutes
**Subsequent Runs:** ~3-5 minutes (no rebuild needed)

---

## Success Criteria

✅ **System is working if:**
1. All 15 containers are running
2. API health check returns 200
3. Frontend loads without errors
4. Workflow trigger returns success
5. Logs show workflow progression
6. Database contains articles/claims

❌ **System has issues if:**
- Any container status shows "Exited" or "Restarting"
- API returns 500 errors
- Frontend shows "Cannot connect to server"
- Logs show Python exceptions or errors
- Database is empty after workflow

---

## Quick Commands Reference

```powershell
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# View logs
docker-compose logs -f [service-name]

# List containers
docker-compose ps

# Remove everything (fresh start)
docker-compose down -v

# Rebuild single service
docker-compose up -d --build [service-name]
```

---

## Monitoring URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:3000 | Main UI |
| **API** | http://localhost:8000 | REST API |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Admin** | http://localhost:3000/admin | Admin Panel |
| **Grafana** | http://localhost:3001 | Monitoring |
| **Prometheus** | http://localhost:9090 | Metrics |
| **Jaeger** | http://localhost:16686 | Tracing |

---

**Last Updated:** 2025-10-23
