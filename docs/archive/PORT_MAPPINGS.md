<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# ClimateNews Docker Port Mappings

## Updated Port Configuration (No Conflicts with Other Projects)

This document lists all Docker port mappings for the ClimateNews project, updated to avoid conflicts with other running projects.

### Port Range Strategy
All ClimateNews services use the **5xxx port range** on the host to avoid conflicts with other projects.

---

## Infrastructure Services

| Service | Host Port(s) | Container Port(s) | Old Port | Notes |
|---------|--------------|-------------------|----------|-------|
| **Zookeeper** | 5181 | 2181 | 2181 | Changed to avoid conflict |
| **Kafka** | 5092, 5093 | 9092, 9093 | 9092, 9093 | Changed to avoid conflict |
| **Schema Registry** | 5081 | 8081 | 8081 | Changed to avoid conflict |
| **Redis** | 5379 | 6379 | 6379 | Changed to avoid conflict |
| **PostgreSQL** | 5433 | 5432 | 5433 | Already unique, no change |

---

## Application Services

| Service | Host Port | Container Port | Old Port | Notes |
|---------|-----------|----------------|----------|-------|
| **API** | 5200 | 8000 | 8000 | Changed to avoid conflict |
| **Frontend** | 5300 | 80 | 3000 | Changed to avoid conflict |

---

## Monitoring & Observability

| Service | Host Port(s) | Container Port(s) | Old Port(s) | Notes |
|---------|--------------|-------------------|-------------|-------|
| **Grafana** | 3001 | 3000 | 3001 | Already unique, no change |
| **Prometheus** | 5090 | 9090 | 9090 | Changed to avoid conflict with rs-mcp |
| **Jaeger** | 5775, 5831, 5832, 5778, 5686, 5268, 5250, 5411 | 5775, 6831, 6832, 5778, 16686, 14268, 14250, 9411 | Various | Updated for consistency |

---

## Quick Access URLs

After starting the services with `docker-compose up`:

- **Frontend (Web UI)**: http://localhost:5300
- **API**: http://localhost:5200
- **API Docs**: http://localhost:5200/docs
- **Grafana**: http://localhost:3001
- **Prometheus**: http://localhost:5090
- **Jaeger UI**: http://localhost:5686
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:5379
- **Kafka**: localhost:5092

---

## Connection Strings

### PostgreSQL
```
Host: localhost
Port: 5433
Database: climatenews
User: postgres
Password: <from .env file>
```

### Redis
```
redis://localhost:5379
```

### Kafka
```
Bootstrap Servers: localhost:5092
```

---

## Environment Variable Updates

If your application code references these services via environment variables, update them as follows:

```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5433/climatenews

# Redis
REDIS_URL=redis://localhost:5379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:5092

# API (for frontend)
VITE_API_URL=http://localhost:5200
```

---

## Conflicts Resolved

The following port conflicts were resolved:

- **Port 2181** (Zookeeper) → **5181** - Was conflicting with another Zookeeper instance
- **Ports 9092, 9093** (Kafka) → **5092, 5093** - Were conflicting with another Kafka instance
- **Port 8081** (Schema Registry) → **5081** - Was conflicting with another Schema Registry
- **Port 6379** (Redis) → **5379** - Was conflicting with multiple Redis instances
- **Port 8000** (API) → **5200** - Was conflicting with clilens-api in another project
- **Port 3000** (Frontend) → **5300** - Was conflicting with cynefin_grafana
- **Port 9090** (Prometheus) → **5090** - Was conflicting with rs-mcp

---

## Notes

- All services are on the **climatenews-network** Docker network
- Internal service communication uses container names and internal ports
- Only external access requires the new host ports
- The Kafka advertised listener has been updated to use port 5092 for localhost connections
- Frontend environment variable `VITE_API_URL` has been updated to point to port 5200

---

## Testing Connectivity

To verify services are accessible:

```bash
# Test PostgreSQL
psql -h localhost -p 5433 -U postgres -d climatenews

# Test Redis
redis-cli -h localhost -p 5379 ping

# Test API
curl http://localhost:5200/health

# Test Frontend
curl http://localhost:5300
```

---

**Last Updated**: November 13, 2025

