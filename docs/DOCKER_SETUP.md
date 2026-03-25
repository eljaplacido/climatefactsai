# Docker Setup Guide

## Quick Start (Essential Services Only)

The platform now runs with **4 essential containers** by default:

```bash
# Start essential services
docker-compose up -d

# Verify running containers
docker ps

# Expected containers:
# - clilens-api (FastAPI backend)
# - clilens-frontend (Next.js frontend)
# - climatenews-postgres (PostgreSQL database)
# - climatenews-redis (Redis cache)
```

## Container Architecture

### ✅ Essential Services (Always Running)

| Service | Container Name | Ports | Purpose |
|---------|---------------|-------|---------|
| API | clilens-api | 5200:8000 | FastAPI backend |
| Frontend | clilens-frontend | 5300:3000 | Next.js UI |
| PostgreSQL | climatenews-postgres | 5433:5432 | Main database |
| Redis | climatenews-redis | 5379:6379 | Cache & sessions |

### ❌ Disabled Services (Profiles Required)

These services are **not operational** and disabled by default via `docker-compose.override.yml`:

**Kafka Infrastructure** (Profile: `kafka`)
- zookeeper
- kafka
- schema-registry

**Microservices** (Profile: `microservices`)
- orchestration-service
- ingestion-service
- verification-service
- content-creation-service
- video-production-service

**Workers** (Profile: `workers`)
- celery-worker

**Monitoring** (Profile: `monitoring`)
- grafana
- prometheus
- jaeger

## Advanced Usage

### Enable Specific Service Groups

```bash
# Enable monitoring tools
docker-compose --profile monitoring up -d

# Enable all services (experimental - may crash)
docker-compose --profile full up -d

# Enable only Kafka infrastructure
docker-compose --profile kafka up -d
```

### Why Are Services Disabled?

According to `docs/CURRENT_STATE.md`:

1. **Kafka Infrastructure** - Not properly configured, microservices expect wrong Redis connection
2. **Microservices** - Crash loop due to Kafka dependency
3. **Celery Workers** - Configured but not used in current architecture
4. **Monitoring** - Optional for development

## Troubleshooting

### Container Cleanup

```bash
# Remove all stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Reset everything (WARNING: deletes data)
docker-compose down -v
docker system prune -a --volumes
```

### Check Logs

```bash
# API logs
docker logs clilens-api

# Frontend logs
docker logs clilens-frontend

# Database logs
docker logs climatenews-postgres

# All logs (follow mode)
docker-compose logs -f
```

### Health Checks

```bash
# API health
curl http://localhost:5200/healthz

# Database connection
docker exec climatenews-postgres psql -U postgres -d climatenews -c "SELECT 1"

# Redis connection
docker exec climatenews-redis redis-cli PING

# Frontend (browser)
open http://localhost:5300
```

## Container Resource Usage

With essential services only:
- **CPU**: ~5-10% idle, ~30% under load
- **Memory**: ~500MB total
- **Disk**: ~2GB (including volumes)

With all services (not recommended):
- **CPU**: ~30% idle, ~80%+ under load
- **Memory**: ~2GB+
- **Disk**: ~5GB+

## Migration Path

To enable disabled services:

1. **Fix Kafka Configuration** (infrastructure/kafka/)
2. **Update Microservice Configs** (Redis connection strings)
3. **Test Services Individually** (`docker-compose up service-name`)
4. **Remove from Override** (edit docker-compose.override.yml)
5. **Update CURRENT_STATE.md** (mark as operational)

## References

- Main config: `docker-compose.yml`
- Override config: `docker-compose.override.yml`
- Port mappings: `PORT_MAPPINGS.md`
- Current state: `docs/CURRENT_STATE.md`

---

**Last Updated:** 2025-12-26
**Change:** Streamlined to 4 essential containers using profiles
