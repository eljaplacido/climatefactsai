# Quick Container Fix Guide

## Problem
You have 12 containers defined, but only 4 are working. The other 8 are failing because they require Kafka infrastructure that isn't running.

## Quick Summary

### ✅ What's Working (4 containers)
- **Frontend** - User interface (port 5300)
- **API** - Backend server (port 5200)  
- **PostgreSQL** - Database (port 5433)
- **Redis** - Cache (port 5379)

### ❌ What's Broken (8 containers)
All microservices are **crash-looping** with `kafka.errors.NoBrokersAvailable`:
- orchestration-service
- ingestion-service
- verification-service
- content-creation-service
- video-production-service

Kafka infrastructure is **stopped**:
- kafka
- zookeeper
- schema-registry (running but useless without kafka)

## Option 1: Quick Fix - Stop the Failing Services (Recommended)

```bash
# Stop all failing services
docker-compose stop orchestration-service ingestion-service verification-service \
  content-creation-service video-production-service schema-registry

# Your app will continue working with just the 4 essential services
```

**Result:** Clean logs, less resource usage, same functionality

## Option 2: Use Simplified Configuration

```bash
# Stop everything
docker-compose down

# Start only working services
docker-compose -f docker-compose.simple.yml up -d

# Or if you want to see logs:
docker-compose -f docker-compose.simple.yml up
```

**Result:** Only runs the 4 containers you actually need

## Option 3: Fix Kafka (Advanced, Not Recommended)

Only do this if you actually need the microservices:

```bash
# 1. Start Kafka infrastructure
docker-compose up -d zookeeper kafka schema-registry

# 2. Wait 60 seconds for Kafka to be ready
sleep 60

# 3. Check Kafka is running
docker logs climatenews-kafka | tail -20

# 4. Start microservices
docker-compose up -d orchestration-service ingestion-service \
  verification-service content-creation-service video-production-service

# 5. Check if they start successfully
docker ps | grep climatenews
```

**Warning:** This is complex and the microservices aren't integrated with the working API anyway.

## What You Actually Need

```yaml
# Minimal working setup (4 containers):
- Frontend (Next.js)     → http://localhost:5300
- API (FastAPI)          → http://localhost:5200
- PostgreSQL             → localhost:5433
- Redis                  → localhost:5379
```

**This is all you need for the app to work!**

## Verification

### Check what's running:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Expected output (simplified setup):
```
NAMES                     STATUS
clilens-api               Up 
clilens-frontend          Up
climatenews-postgres      Up
climatenews-redis         Up
```

### Test the app:
```bash
# Frontend
curl http://localhost:5300

# API health
curl http://localhost:5200/health

# API articles
curl http://localhost:5200/api/articles
```

## Why Remove the Other Services?

1. **They don't work** - All 5 microservices are crash-looping
2. **They're not needed** - API works fine without them
3. **They waste resources** - Constant restart attempts consume CPU/RAM
4. **They pollute logs** - Errors make debugging harder
5. **They add complexity** - More containers = more things to manage

## Architecture Reality Check

**What the docs say (planned):**
```
Orchestrator → Kafka → 5 Microservices → Database
(Event-driven multi-agent system)
```

**What actually works:**
```
Frontend → API → Database + Redis
(Simple REST API)
```

The microservices were planned for automation but never completed/integrated.

## Decision Time

### Keep it Simple?
✅ Use `docker-compose.simple.yml`
- 4 containers
- Everything works
- Easy to maintain

### Go Complex?
⚠️ Fix Kafka infrastructure  
- 12+ containers
- High complexity
- Requires Kafka expertise
- No immediate value

## Recommended Action

```bash
# 1. Stop everything
docker-compose down

# 2. Use simplified config
docker-compose -f docker-compose.simple.yml up -d

# 3. Verify it works
curl http://localhost:5200/health
curl http://localhost:5300

# 4. You're done! ✅
```

---

**See also:**
- [Full Analysis](CONTAINER_ANALYSIS.md) - Detailed evaluation
- [Architecture Docs](architecture/ARCHITECTURE.md) - Planned vs actual
- [`docker-compose.simple.yml`](../docker-compose.simple.yml) - Simplified config



