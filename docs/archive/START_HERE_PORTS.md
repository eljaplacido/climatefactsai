<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# 🚀 START HERE - Port Configuration Update

## ✅ **COMPLETED: All Docker Port Conflicts Resolved**

All ClimateNews services now use the **5xxx port range** to avoid conflicts with your other projects.

---

## 🎯 Quick Start (60 seconds)

```powershell
# 1. Stop existing services
docker-compose down

# 2. Start with new port configuration
docker-compose up -d

# 3. Wait for services to initialize (30 seconds)
Start-Sleep -Seconds 30

# 4. Open the application
start http://localhost:5300
```

**That's it!** Your ClimateNews app is now running on conflict-free ports.

---

## 🌐 New Access URLs

| What | URL | Old URL |
|------|-----|---------|
| **Web Application** | http://localhost:5300 | ~~http://localhost:3000~~ |
| **API Documentation** | http://localhost:5200/docs | ~~http://localhost:8000/docs~~ |
| **Admin Panel** | http://localhost:5300/admin | ~~http://localhost:3000/admin~~ |
| **Grafana** | http://localhost:3001 | (unchanged) |
| **Prometheus** | http://localhost:5090 | ~~http://localhost:9090~~ |
| **Jaeger UI** | http://localhost:5686 | ~~http://localhost:16686~~ |

---

## 🔌 New Connection Ports

| Service | New Port | Old Port |
|---------|----------|----------|
| PostgreSQL | 5433 | (unchanged) |
| Redis | **5379** | ~~6379~~ |
| Kafka | **5092** | ~~9092~~ |
| Schema Registry | **5081** | ~~8081~~ |
| Zookeeper | **5181** | ~~2181~~ |

---

## 📋 What Changed?

### ✅ Configuration Files Updated (10 files)
- `docker-compose.yml` - All port mappings
- `src/backend/shared/config.py` - Backend defaults
- 5 frontend files (API connections)
- 3 documentation files

### ✅ New Documentation Created (3 files)
- **PORT_MAPPINGS.md** - Complete reference
- **PORT_MIGRATION_GUIDE.md** - Troubleshooting guide  
- **PORT_UPDATE_SUMMARY.md** - Detailed summary

### ✅ Automatic Updates
- Container networking
- Frontend-to-API proxy
- Kafka advertised listeners
- Default configuration values

---

## 🎉 Benefits

✅ **No more port conflicts** with other Docker projects  
✅ **All services in 5xxx range** - easy to remember  
✅ **Fully documented** - comprehensive guides included  
✅ **Zero manual configuration** - just restart Docker Compose  
✅ **Future-proof** - room for expansion in 5xxx range

---

## 📚 Documentation Files

Read these for more details:

1. **PORT_MAPPINGS.md** - Complete port reference with connection strings
2. **PORT_MIGRATION_GUIDE.md** - Troubleshooting and testing guide
3. **PORT_UPDATE_SUMMARY.md** - Detailed change summary
4. **README.md** - Updated main documentation
5. **QUICK_START_WEB.md** - Updated quick start guide

---

## 🔍 Conflicts Resolved

The following port conflicts are now **completely resolved**:

| Port | Was Used By | Now |
|------|-------------|-----|
| 2181 | Zookeeper (conflict) | → **5181** (unique) |
| 3000 | Frontend + cynefin_grafana | → **5300** (unique) |
| 6379 | Redis (multiple projects) | → **5379** (unique) |
| 8000 | API + anomaly-detection | → **5200** (unique) |
| 8081 | Schema Registry (conflict) | → **5081** (unique) |
| 9090 | Prometheus + rs-mcp | → **5090** (unique) |
| 9092-9093 | Kafka (conflict) | → **5092-5093** (unique) |

---

## 💡 Pro Tips

1. **Bookmark these URLs:**
   - App: http://localhost:5300
   - API: http://localhost:5200/docs

2. **Update your browser bookmarks** if you saved the old URLs

3. **No .env changes needed** - defaults are updated automatically

4. **All services work together** - internal communication unchanged

---

## 🆘 Troubleshooting

### Services won't start?

```powershell
# Full reset
docker-compose down -v
docker-compose up -d
```

### Can't connect to API?

```powershell
# Check API health
curl http://localhost:5200/health

# Check logs
docker-compose logs -f api
```

### Need detailed help?

See **PORT_MIGRATION_GUIDE.md** for comprehensive troubleshooting.

---

## 📞 Quick Reference Card

**Save this for easy reference:**

```
ClimateNews - Port Reference Card
═══════════════════════════════════
Frontend:        http://localhost:5300
API:             http://localhost:5200
API Docs:        http://localhost:5200/docs
Admin:           http://localhost:5300/admin

Database:        localhost:5433 (climatenews)
Redis:           localhost:5379
Kafka:           localhost:5092

Monitoring:
  Grafana:       http://localhost:3001
  Prometheus:    http://localhost:5090
  Jaeger:        http://localhost:5686
═══════════════════════════════════
```

---

## ✨ You're All Set!

**Everything is configured and ready to go.**

Just run:
```powershell
docker-compose up -d
```

Then visit: **http://localhost:5300**

---

**Last Updated:** November 13, 2025  
**Status:** ✅ Complete - No Action Required  
**Port Range:** 5xxx (conflict-free)

