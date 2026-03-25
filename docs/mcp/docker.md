# Docker MCP Server

**Purpose:** Manage Docker containers, view logs, and monitor CliLens service health via Model Context Protocol.

## Installation

```bash
# Install Docker MCP server
npx -y @modelcontextprotocol/server-docker
```

## Configuration

The Docker server is configured in `.claude/mcp-config.json`:

```json
{
  "mcpServers": {
    "docker": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-docker"],
      "description": "Manage Docker containers and view logs"
    }
  }
}
```

**Requirements:**
- Docker daemon running on localhost
- Docker CLI accessible via `docker` command
- User has permissions to run Docker commands

## Available Operations

### Container Management
```
"Show status of all CliLens containers"
"List running containers"
"Check health of PostgreSQL container"
```

### View Logs
```
"Show logs for ingestion service (last 50 lines)"
"View error logs from orchestration service"
"Follow logs for Kafka in real-time"
```

### Inspect Containers
```
"Inspect climatenews-postgres container"
"Show environment variables for API gateway"
"Get container stats for all services"
```

### Service Health
```
"Check which services are healthy"
"Show resource usage for all containers"
"List containers that have restarted"
```

## Example Queries

**Debugging:**
```
"Show error logs from verification-service"
"Why did ingestion-service restart?"
"Check Kafka broker logs for connection issues"
```

**Monitoring:**
```
"What's the memory usage of all containers?"
"Show CPU usage for the API gateway"
"List containers with high restart counts"
```

**Operations:**
```
"Show PostgreSQL container configuration"
"View Redis connection settings"
"Check Kafka topic configuration"
```

## Container Names

CliLens uses standardized container names:

| Container | Service |
|-----------|---------|
| `climatenews-postgres` | PostgreSQL database |
| `climatenews-redis` | Redis cache |
| `climatenews-kafka` | Kafka broker |
| `climatenews-zookeeper` | Zookeeper coordinator |
| `climatenews-api-gateway` | FastAPI gateway |
| `climatenews-frontend` | Next.js web app |
| `climatenews-orchestration-service` | Orchestrator agent |
| `climatenews-ingestion-service` | Ingestion agent |
| `climatenews-verification-service` | Verification agent |
| `climatenews-content-service` | Content creation agent |
| `climatenews-grafana` | Grafana monitoring |
| `climatenews-prometheus` | Prometheus metrics |
| `climatenews-jaeger` | Jaeger tracing |

## Log Analysis

**View specific log lines:**
```bash
# Last 100 lines
docker logs climatenews-api-gateway --tail 100

# Follow logs in real-time
docker logs -f climatenews-ingestion-service

# Logs since timestamp
docker logs climatenews-kafka --since 2025-11-21T10:00:00

# Filter by grep
docker logs climatenews-api-gateway 2>&1 | grep ERROR
```

**Common log patterns to search:**
- `ERROR` - Application errors
- `WARN` - Warnings
- `Connection refused` - Network issues
- `Out of memory` - Resource exhaustion
- `Failed to` - Operation failures

## Health Checks

**Container health status:**
```bash
# Check health of all containers
docker-compose ps

# Inspect health check configuration
docker inspect climatenews-postgres | jq '.[0].State.Health'

# View health check logs
docker inspect climatenews-api-gateway | jq '.[0].State.Health.Log'
```

**Manual health checks:**
```bash
# PostgreSQL
docker exec climatenews-postgres pg_isready

# Redis
docker exec climatenews-redis redis-cli ping

# Kafka
docker exec climatenews-kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

## Troubleshooting

### Container Not Running

**Problem:** Container in exited state

**Solutions:**
1. Check exit code and reason:
   ```bash
   docker ps -a | grep climatenews
   docker inspect climatenews-<service> | jq '.[0].State'
   ```

2. View logs for errors:
   ```bash
   docker logs climatenews-<service> --tail 100
   ```

3. Restart container:
   ```bash
   docker-compose restart <service>
   ```

### Container Keeps Restarting

**Problem:** Container in restart loop

**Solutions:**
1. Check restart count:
   ```bash
   docker inspect climatenews-<service> | jq '.[0].RestartCount'
   ```

2. View startup logs:
   ```bash
   docker logs climatenews-<service> --tail 200
   ```

3. Common causes:
   - Missing environment variables
   - Port conflicts
   - Dependency not ready (e.g., DB not initialized)
   - Configuration errors

### High Resource Usage

**Problem:** Container consuming excessive resources

**Solutions:**
1. Check resource stats:
   ```bash
   docker stats climatenews-<service>
   ```

2. Set resource limits in `docker-compose.yml`:
   ```yaml
   services:
     service-name:
       mem_limit: 512m
       cpus: 0.5
   ```

3. Analyze container logs for issues

### MCP Server Connection Failed

**Problem:** Cannot connect to Docker daemon

**Solutions:**
1. Verify Docker is running:
   ```bash
   docker info
   ```

2. Check Docker socket permissions:
   ```bash
   # Linux/macOS
   ls -la /var/run/docker.sock

   # Windows (WSL)
   docker context list
   ```

3. Test Docker CLI access:
   ```bash
   docker ps
   ```

## Security

**Permissions:**
- Read-only operations (list, inspect, logs)
- No container start/stop/delete via MCP
- Limited to localhost Docker daemon

**Production:**
- Use Docker context for remote access
- Restrict MCP to specific container names
- Audit log access permissions

## Integration with Claude Code

The Docker MCP integrates with Claude Code for:

- **Debugging:** "Why is the verification service failing?"
- **Monitoring:** "Check health of all CliLens services"
- **Troubleshooting:** "Show error logs from Kafka"
- **Operations:** "What containers are consuming most memory?"

## Related MCPs

- **Filesystem MCP:** [filesystem.md](filesystem.md) - Code and configuration access
- **PostgreSQL MCP:** [postgres.md](postgres.md) - Database queries

---

**Configured:** 2025-11-21
**Docker Version:** Check with `docker --version`
**Next Review:** 2026-11-21
