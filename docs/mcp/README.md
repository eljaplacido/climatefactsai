# MCP (Model Context Protocol) Server Configuration

## Overview
This document describes the MCP server configuration for the Climate News Multi-Agent System, enabling AI agents to access project files, databases, and Docker containers.

## Configured MCP Servers

### 1. Filesystem MCP Server
**Status**: ✅ Configured and Operational
**Purpose**: Access project files, schemas, configs, and logs

**Configuration** (`.claude/mcp-config.json`):
```json
{
  "filesystem": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "C:/Users/35845/Desktop/DIGICISU/climatenews"
    ],
    "description": "Access project files, schemas, configs, and logs"
  }
}
```

**Capabilities**:
- ✅ Read project configuration files (docker-compose.yml, package.json, etc.)
- ✅ Access JSON schemas (orchestrator_task.json, etc.)
- ✅ List and read source code files
- ✅ Access all project directories

**Test Results** (DEV-01):
1. ✅ Successfully read `docker-compose.yml` (322 lines, all services configured)
2. ✅ Successfully read `schemas/orchestrator_task.json` (310 lines, complete workflow schema)
3. ✅ Successfully listed files in `src/backend/shared/`:
   - `__init__.py`
   - `config.py`
   - `database.py`
   - `kafka_client.py`
   - `logger.py`
   - `reliability_scorer.py`

### 2. PostgreSQL MCP Server
**Status**: ⚙️ Configured (requires database connection)
**Purpose**: Query PostgreSQL database for articles, claims, and credibility data

**Configuration**:
```json
{
  "postgres": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres"
    ],
    "env": {
      "POSTGRES_CONNECTION_STRING": "postgresql://postgres:postgres@localhost:5433/climatenews"
    },
    "description": "Query PostgreSQL database for articles, claims, and credibility data"
  }
}
```

**Note**: Requires PostgreSQL service to be running (via `docker-compose up postgres`)

### 3. Docker MCP Server
**Status**: ⚙️ Configured (requires Docker daemon)
**Purpose**: Manage Docker containers, view logs, check service health

**Configuration**:
```json
{
  "docker": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-docker"
    ],
    "description": "Manage Docker containers, view logs, check service health"
  }
}
```

**Note**: Requires Docker Desktop to be running

## Usage Examples

### Reading Project Files
```bash
# Via Claude Code with filesystem MCP
"Read the docker-compose.yml file"
"Show me the orchestrator_task.json schema"
"List all files in src/backend/shared/"
```

### Database Queries (when postgres service is running)
```bash
# Via postgres MCP
"Show me the latest 10 articles from the database"
"Query all claims with credibility score > 0.8"
"List all tables in the climatenews database"
```

### Docker Container Management
```bash
# Via docker MCP
"Show me the logs for the ingestion-service container"
"Check the health status of all running containers"
"List all Docker volumes"
```

## Troubleshooting

### Issue: MCP Server Not Found
**Symptoms**: `Server "filesystem" not found` error
**Solution**:
1. Verify MCP configuration in `.claude/mcp-config.json`
2. Restart Claude Code to reload MCP servers
3. Check that the MCP package is installed: `npm list -g @modelcontextprotocol/server-filesystem`

### Issue: Database Connection Failed
**Symptoms**: Cannot query PostgreSQL via MCP
**Solution**:
1. Start PostgreSQL service: `docker-compose up -d postgres`
2. Verify connection: `psql postgresql://postgres:postgres@localhost:5433/climatenews`
3. Check database logs: `docker logs climatenews-postgres`

### Issue: Docker MCP Not Responding
**Symptoms**: Cannot access Docker containers via MCP
**Solution**:
1. Ensure Docker Desktop is running
2. Verify Docker daemon: `docker ps`
3. Check Docker socket permissions

## Node.js Version Compatibility

**Known Issue**: Claude Flow hooks may fail with Node.js version mismatches
**Error**: `NODE_MODULE_VERSION 108 vs 115 mismatch`
**Impact**: Hooks coordination features unavailable, but MCP file access works normally
**Workaround**: Use direct Claude Code file operations (Read, Write, Edit tools)

## Next Steps

1. **DEV-02**: Configure and test PostgreSQL MCP server
2. **DEV-03**: Configure and test Docker MCP server
3. **DEV-04**: Implement sequential workflow testing with all MCP servers

## References

- MCP Specification: https://modelcontextprotocol.io/
- MCP Server Filesystem: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem
- MCP Server PostgreSQL: https://github.com/modelcontextprotocol/servers/tree/main/src/postgres
- MCP Server Docker: https://github.com/modelcontextprotocol/servers/tree/main/src/docker

---

**Last Updated**: 2025-11-22
**Task**: DEV-01 - Configure and Test Filesystem MCP
**Agent**: Developer Agent #1
**Status**: ✅ Completed
