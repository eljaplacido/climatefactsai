# Development Scripts

**Local Development Helper Scripts** | **Version:** 2.0

## Overview

This directory contains utility scripts for local development and debugging of CliLens.AI services. These scripts simplify common development tasks like starting services, running tests, managing databases, and monitoring health.

## Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ and npm
- Python 3.11+
- Bash shell (Git Bash on Windows)

## Available Scripts

### 🚀 Service Management

**`dev-start.sh`** - Start individual services or full stack

```bash
# Start full stack
./scripts/dev-start.sh all

# Start specific service
./scripts/dev-start.sh orchestration
./scripts/dev-start.sh ingestion
./scripts/dev-start.sh verification
./scripts/dev-start.sh content

# Start infrastructure only
./scripts/dev-start.sh infra

# Start with logs
./scripts/dev-start.sh all --logs
```

### 🧪 Testing

**`dev-test.sh`** - Run tests with various configurations

```bash
# Run all tests
./scripts/dev-test.sh all

# Run specific test suite
./scripts/dev-test.sh unit
./scripts/dev-test.sh integration
./scripts/dev-test.sh e2e

# Run tests for specific service
./scripts/dev-test.sh service orchestration
./scripts/dev-test.sh service ingestion

# Run with coverage
./scripts/dev-test.sh all --coverage

# Run in watch mode
./scripts/dev-test.sh unit --watch

# Run specific test file
./scripts/dev-test.sh file tests/services/test_orchestration.py
```

### 🗄️ Database Management

**`dev-db.sh`** - Manage PostgreSQL database

```bash
# Run migrations
./scripts/dev-db.sh migrate

# Rollback last migration
./scripts/dev-db.sh rollback

# Seed database with test data
./scripts/dev-db.sh seed

# Reset database (drop + migrate + seed)
./scripts/dev-db.sh reset

# Backup database
./scripts/dev-db.sh backup

# Restore from backup
./scripts/dev-db.sh restore backups/climatenews_2025-11-21.sql

# Open psql shell
./scripts/dev-db.sh shell

# Show database status
./scripts/dev-db.sh status
```

### 📨 Kafka Management

**`dev-kafka.sh`** - Manage Kafka topics and messages

```bash
# List all topics
./scripts/dev-kafka.sh list

# Create topic
./scripts/dev-kafka.sh create discovery_queue

# Delete topic
./scripts/dev-kafka.sh delete discovery_queue

# Describe topic
./scripts/dev-kafka.sh describe fact_checking_queue

# Send test message
./scripts/dev-kafka.sh send discovery_queue '{"taskId":"test-001"}'

# Consume messages (latest)
./scripts/dev-kafka.sh consume fact_checking_queue

# Consume from beginning
./scripts/dev-kafka.sh consume fact_checking_queue --from-beginning

# Check consumer group lag
./scripts/dev-kafka.sh lag climatenews_ingestion

# Reset consumer group offset
./scripts/dev-kafka.sh reset-offset climatenews_verification
```

### 🏥 Health Monitoring

**`dev-health.sh`** - Check service health status

```bash
# Check all services
./scripts/dev-health.sh all

# Check specific service
./scripts/dev-health.sh orchestration
./scripts/dev-health.sh api-gateway

# Check infrastructure
./scripts/dev-health.sh infra

# Continuous monitoring (every 5s)
./scripts/dev-health.sh all --watch

# Export health report
./scripts/dev-health.sh all --export health-report.json
```

## Common Workflows

### First-Time Setup

```bash
# 1. Start infrastructure
./scripts/dev-start.sh infra

# 2. Setup database
./scripts/dev-db.sh migrate
./scripts/dev-db.sh seed

# 3. Verify Kafka topics
./scripts/dev-kafka.sh list

# 4. Start services
./scripts/dev-start.sh all

# 5. Check health
./scripts/dev-health.sh all
```

### Daily Development

```bash
# Start what you need
./scripts/dev-start.sh ingestion --logs

# Run tests on changes
./scripts/dev-test.sh unit --watch

# Check service health
./scripts/dev-health.sh ingestion
```

### Debugging Failed Workflow

```bash
# 1. Check service health
./scripts/dev-health.sh all

# 2. Check Kafka topics
./scripts/dev-kafka.sh describe fact_checking_queue
./scripts/dev-kafka.sh lag climatenews_verification

# 3. Consume error messages
./scripts/dev-kafka.sh consume workflow_events --from-beginning

# 4. Check database state
./scripts/dev-db.sh shell
# > SELECT * FROM workflow_logs WHERE task_id = 'task-xxx';

# 5. View service logs
docker-compose logs verification-service --tail=100
```

### Database Reset After Breaking Changes

```bash
# Full reset
./scripts/dev-db.sh reset

# Or step-by-step
./scripts/dev-db.sh backup  # Safety first
./scripts/dev-db.sh rollback
./scripts/dev-db.sh migrate
./scripts/dev-db.sh seed
```

### Integration Testing Workflow

```bash
# 1. Start fresh environment
docker-compose down -v
./scripts/dev-start.sh infra

# 2. Setup database
./scripts/dev-db.sh reset

# 3. Start services
./scripts/dev-start.sh all

# 4. Run integration tests
./scripts/dev-test.sh integration

# 5. Check results
./scripts/dev-health.sh all
```

## Script Details

### Configuration

Scripts use these default configurations (can be overridden with environment variables):

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=climatenews
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=5379

# Kafka
KAFKA_HOST=localhost
KAFKA_PORT=5092

# API Gateway
API_GATEWAY_URL=http://localhost:5200

# Frontend
FRONTEND_URL=http://localhost:5300
```

### Output Formatting

Scripts use colored output for readability:
- 🟢 **Green** - Success messages
- 🔴 **Red** - Error messages
- 🟡 **Yellow** - Warning messages
- 🔵 **Blue** - Info messages

### Error Handling

All scripts include:
- Dependency checks (Docker, Docker Compose, etc.)
- Service availability checks
- Graceful error messages
- Exit codes (0 = success, 1 = error)

## Troubleshooting

### Script Permission Denied

```bash
# Make scripts executable
chmod +x scripts/*.sh
```

### Docker Not Found

```bash
# Install Docker Desktop
# Windows: https://docs.docker.com/desktop/install/windows-install/
# Mac: https://docs.docker.com/desktop/install/mac-install/
# Linux: https://docs.docker.com/engine/install/
```

### Port Already in Use

```bash
# Check what's using the port
lsof -i :5433  # macOS/Linux
netstat -ano | findstr :5433  # Windows

# Kill the process or change port in .env
```

### Kafka Topics Not Created

```bash
# Wait for Kafka to be ready (takes ~30s)
./scripts/dev-health.sh infra --wait

# Manually create topics
./scripts/dev-kafka.sh create discovery_queue
./scripts/dev-kafka.sh create fact_checking_queue
./scripts/dev-kafka.sh create content_creation_queue
```

### Database Migration Failed

```bash
# Check database is running
./scripts/dev-health.sh infra

# View migration logs
docker-compose logs postgres --tail=50

# Reset if corrupted
./scripts/dev-db.sh reset --force
```

## Integration with IDE

### VS Code Tasks

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start All Services",
      "type": "shell",
      "command": "./scripts/dev-start.sh all",
      "problemMatcher": []
    },
    {
      "label": "Run Unit Tests",
      "type": "shell",
      "command": "./scripts/dev-test.sh unit",
      "problemMatcher": []
    },
    {
      "label": "Check Health",
      "type": "shell",
      "command": "./scripts/dev-health.sh all",
      "problemMatcher": []
    }
  ]
}
```

### PyCharm Run Configurations

1. Go to **Run** → **Edit Configurations**
2. Add **Shell Script** configuration
3. Set **Script path**: `scripts/dev-test.sh`
4. Set **Script options**: `unit --watch`

## Related Documentation

- **Getting Started:** [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md)
- **Development Guide:** [docs/architecture/DEVELOPMENT.md](../docs/architecture/DEVELOPMENT.md)
- **Services:** [docs/services/README.md](../docs/services/README.md)
- **Docker Compose:** [docker-compose.yml](../docker-compose.yml)

---

**Last Updated:** 2025-11-21
**Maintainer:** Platform Team
