# Filesystem MCP Server

**Purpose:** Access project files and directories via Model Context Protocol for AI-assisted development.

## Installation

```bash
# Install filesystem MCP server
npx -y @modelcontextprotocol/server-filesystem
```

## Configuration

The filesystem server is configured in `.claude/mcp-config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
      "description": "Access project files and directories"
    }
  }
}
```

**Root Directory:** Project root

## Available Operations

### Read Files
```
"Read the docker-compose.yml file"
"Show me the orchestrator_task.json schema"
"What's in the main API file?"
```

### List Directories
```
"List files in src/backend/shared/"
"Show me all Python files in the services directory"
"What schemas are available?"
```

## Example Queries

**Review Configuration:**
```
"What database settings are in src/backend/shared/config.py?"
```

**Analyze Architecture:**
```
"Show me the orchestrator service structure"
"What agents are defined in the services directory?"
```

## Security

**Permissions:**
- Read-only access to project files
- No write/delete operations
- Sandbox scope: Project root only

## Integration with Claude Code

- **Code Reviews:** "Review the shared/kafka_client.py file"
- **Documentation:** "What does GETTING_STARTED.md cover?"
- **Debugging:** "Show me the test failures in tests/"

## Related MCPs

- **PostgreSQL MCP:** [postgres.md](postgres.md)
- **Docker MCP:** [docker.md](docker.md)

---

**Configured:** 2025-11-21
