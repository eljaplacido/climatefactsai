<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# Port Migration Guide - ClimateNews Docker Services

## Overview

All ClimateNews Docker services have been remapped to the **5xxx port range** to avoid conflicts with other projects running on your system.

## Quick Reference - What Changed

| Service | Old Host Port | New Host Port | Status |
|---------|--------------|---------------|--------|
| Frontend | 3000 | **5300** | ✅ Updated |
| API | 8000 | **5200** | ✅ Updated |
| Zookeeper | 2181 | **5181** | ✅ Updated |
| Kafka | 9092, 9093 | **5092, 5093** | ✅ Updated |
| Schema Registry | 8081 | **5081** | ✅ Updated |
| Redis | 6379 | **5379** | ✅ Updated |
| PostgreSQL | 5433 | **5433** | ✓ No change (already unique) |
| Prometheus | 9090 | **5090** | ✅ Updated |
| Grafana | 3001 | **3001** | ✓ No change (already unique) |
| Jaeger UI | 16686 | **5686** | ✅ Updated |

## Files Updated

### 1. Docker Configuration
- ✅ `docker-compose.yml` - All port mappings updated

### 2. Application Configuration  
- ✅ `src/backend/shared/config.py` - Default port values updated:
  - Kafka: `5092` (was `9092`)
  - Schema Registry: `5081` (was `8081`)
  - Redis: `5379` (was `6379`)

### 3. Frontend Configuration
- ✅ `frontend/vite.config.ts` - Proxy target updated to `5200`
- ✅ `frontend/src/pages/URLAnalyzerPage.tsx` - API URL fallback updated
- ✅ `frontend/src/pages/DashboardPage.tsx` - API URL fallback updated
- ✅ `frontend/src/contexts/AuthContext.tsx` - API URL fallback updated
- ✅ `frontend/src/services/api.ts` - API base URL fallback updated
- ✅ `docker-compose.yml` - Frontend `VITE_API_URL` env var updated

### 4. Documentation
- ✅ `README.md` - Quick start URLs updated
- ✅ `QUICK_START_WEB.md` - All references updated
- ✅ `PORT_MAPPINGS.md` - New comprehensive reference created
- ✅ `start_web_locally.ps1` - Added infrastructure port notes

### 5. New Documentation Created
- ✅ `PORT_MAPPINGS.md` - Detailed port reference
- ✅ `PORT_MIGRATION_GUIDE.md` - This file

## What You Need to Do

### Option 1: Using Docker Compose (Recommended)

No action needed! Just restart your services:

```powershell
# Stop current services
docker-compose down

# Start with new ports
docker-compose up -d

# Wait for services to be ready
Start-Sleep -Seconds 30

# Access the application
start http://localhost:5300
```

### Option 2: Using Local Development

If you run services locally (outside Docker), update your environment variables:

```bash
# Update these in your .env file or export them

# Database
export DATABASE_URL=postgresql://postgres:password@localhost:5433/climatenews

# Redis (Docker)
export REDIS_HOST=localhost
export REDIS_PORT=5379

# Kafka (Docker)
export KAFKA_BOOTSTRAP_SERVERS=localhost:5092
export KAFKA_SCHEMA_REGISTRY_URL=http://localhost:5081

# API URL for frontend
export VITE_API_URL=http://localhost:5200
```

## Testing the Changes

### 1. Verify Infrastructure Services

```powershell
# Test PostgreSQL
docker exec -it climatenews-postgres psql -U postgres -d climatenews -c "SELECT version();"

# Test Redis
docker exec -it climatenews-redis redis-cli ping

# Test Kafka
docker exec -it climatenews-kafka kafka-topics --list --bootstrap-server localhost:9093
```

### 2. Verify Application Services

```powershell
# Test API health
curl http://localhost:5200/health

# Test API docs (open in browser)
start http://localhost:5200/docs

# Test Frontend (open in browser)
start http://localhost:5300
```

### 3. Verify Monitoring Services

```powershell
# Grafana
start http://localhost:3001

# Prometheus
start http://localhost:5090

# Jaeger UI
start http://localhost:5686
```

## Troubleshooting

### Issue: Services won't start

**Solution 1:** Stop all Docker containers and volumes
```powershell
docker-compose down -v
docker-compose up -d
```

**Solution 2:** Check if old ports are still in use
```powershell
# Check what's using a specific port
netstat -ano | findstr :8000
netstat -ano | findstr :3000
```

### Issue: Frontend can't connect to API

**Check 1:** Verify API is running
```powershell
curl http://localhost:5200/health
```

**Check 2:** Verify frontend environment variable
```powershell
docker exec -it clilens-frontend env | findstr VITE_API_URL
```

Should show: `VITE_API_URL=http://localhost:5200`

### Issue: Backend can't connect to infrastructure services

**Check:** Verify environment variables in backend containers
```powershell
# Check API service
docker exec -it clilens-api env | findstr -i "redis kafka postgres"

# Should see:
# REDIS_PORT=5379
# KAFKA_BOOTSTRAP_SERVERS=localhost:5092
# POSTGRES_PORT=5433
```

### Issue: Connection refused errors

**Cause:** Services might be using old port configurations

**Solution:** Clear Python cache and rebuild
```powershell
# Remove Python cache
Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Reverting Changes (If Needed)

If you need to revert to old ports (not recommended due to conflicts):

1. **Backup current config:**
   ```powershell
   Copy-Item docker-compose.yml docker-compose.yml.new-ports
   ```

2. **Use git to revert:**
   ```powershell
   git checkout HEAD -- docker-compose.yml
   git checkout HEAD -- src/backend/shared/config.py
   git checkout HEAD -- frontend/
   ```

3. **Or manually edit `docker-compose.yml`** and change ports back to original values

## Benefits of New Port Scheme

✅ **No Conflicts:** All ports are in the 5xxx range, avoiding conflicts with:
- Other projects' Postgres (5432, 5434)
- Other projects' Redis (6379, 6380)
- Other projects' Kafka (9092-9093)
- Other monitoring tools (9090)

✅ **Consistent Numbering:** Easy to remember - all services in 5xxx range

✅ **Future Proof:** Room for additional services in 5xxx range

✅ **Clear Separation:** ClimateNews services are clearly distinguished from other projects

## Additional Resources

- **Full Port Reference:** See `PORT_MAPPINGS.md`
- **Quick Start Guide:** See `QUICK_START_WEB.md`
- **Main README:** See `README.md`

## Support

If you encounter issues after migration:

1. Check this guide's troubleshooting section
2. Verify all services are using new ports: `docker-compose ps`
3. Check logs: `docker-compose logs -f [service-name]`
4. Ensure no other services are using ports in 5xxx range

---

**Migration Date:** November 13, 2025  
**Version:** 1.0  
**Status:** ✅ Complete

