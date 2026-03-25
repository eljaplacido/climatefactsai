# PostgreSQL MCP Server

**Purpose:** Query CliLens PostgreSQL database via Model Context Protocol for data analysis and debugging.

## Installation

```bash
# Install PostgreSQL MCP server
npx -y @modelcontextprotocol/server-postgres
```

## Configuration

The PostgreSQL server is configured in `.claude/mcp-config.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://postgres:postgres@localhost:5433/climatenews"
      ],
      "description": "Query CliLens PostgreSQL database"
    }
  }
}
```

**Connection String:** `postgresql://postgres:postgres@localhost:5433/climatenews`

**⚠️ Security Note:** Never commit actual database credentials to version control. Use environment variables in production.

## Available Operations

### Query Data
```sql
-- Get articles with low credibility
SELECT * FROM articles WHERE credibility_score < 50 ORDER BY published_date DESC LIMIT 10;

-- Count articles by country
SELECT country_code, COUNT(*) as article_count
FROM articles
GROUP BY country_code
ORDER BY article_count DESC;

-- Recent fact checks with low confidence
SELECT * FROM fact_checks
WHERE confidence_score < 0.5
ORDER BY created_at DESC
LIMIT 20;
```

### Analyze Data
```sql
-- Average credibility by source
SELECT source_name, AVG(credibility_score) as avg_credibility, COUNT(*) as articles
FROM articles
GROUP BY source_name
HAVING COUNT(*) > 5
ORDER BY avg_credibility DESC;

-- Verification success rate
SELECT
  COUNT(*) as total_checks,
  SUM(CASE WHEN verification_status = 'VERIFIED' THEN 1 ELSE 0 END) as verified,
  ROUND(100.0 * SUM(CASE WHEN verification_status = 'VERIFIED' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM fact_checks;
```

### Check Schema
```sql
-- List all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Describe articles table
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'articles';
```

## Example Queries

**Data Analysis:**
```
"Show me articles with credibility_score < 0.5"
"Count articles by country"
"What are the most common tags in articles?"
```

**Debugging:**
```
"Show recent workflow_logs with errors"
"Find articles without fact checks"
"Check for duplicate articles by URL"
```

**Monitoring:**
```
"How many articles were published today?"
"What's the average verification time?"
"Show me recent user feedback"
```

## Database Schema

**Core Tables:**
- `articles` - Published climate articles
- `claims` - Extracted claims from articles
- `fact_checks` - Verification results
- `countries` - Supported countries configuration
- `article_feedback` - User feedback and ratings
- `workflow_logs` - Task execution history

**Key Relationships:**
- Articles → Claims (one-to-many)
- Claims → Fact_checks (one-to-one)
- Articles → Article_feedback (one-to-many)

For complete schema, see: [docs/architecture/DATABASE_SCHEMA.md](../architecture/DATABASE_SCHEMA.md)

## Security

**Permissions:**
- Read-only access (SELECT queries only)
- No write/update/delete operations via MCP
- Connection limited to localhost development database

**Production:**
```json
{
  "postgres": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres",
      "$DATABASE_URL"
    ]
  }
}
```

Use environment variable `$DATABASE_URL` with appropriate credentials.

## Troubleshooting

### Connection Failed

**Problem:** Cannot connect to PostgreSQL

**Solutions:**
1. Check PostgreSQL is running:
   ```bash
   docker ps | grep postgres
   docker-compose ps postgres
   ```

2. Verify connection string:
   ```bash
   psql postgresql://postgres:postgres@localhost:5433/climatenews
   ```

3. Check port availability:
   ```bash
   # Windows
   netstat -ano | findstr :5433

   # macOS/Linux
   lsof -i :5433
   ```

### Permission Denied

**Problem:** "permission denied for table X"

**Solution:**
- Ensure user has SELECT permissions
- Check role grants: `\dp tablename` in psql
- Verify connection uses correct database user

### Slow Queries

**Problem:** Queries take too long

**Solutions:**
1. Add indexes:
   ```sql
   CREATE INDEX idx_articles_credibility ON articles(credibility_score);
   CREATE INDEX idx_articles_country ON articles(country_code);
   ```

2. Use EXPLAIN to analyze query plans:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM articles WHERE credibility_score < 50;
   ```

3. Limit result sets:
   ```sql
   SELECT * FROM articles LIMIT 100;
   ```

## Integration with Claude Code

The PostgreSQL MCP integrates with Claude Code for:

- **Data Analysis:** "Analyze article credibility distribution"
- **Debugging:** "Find articles that failed verification"
- **Monitoring:** "Show system health metrics from workflow_logs"
- **Testing:** "Verify test data in articles table"

## Related MCPs

- **Filesystem MCP:** [filesystem.md](filesystem.md) - Code and file access
- **Docker MCP:** [docker.md](docker.md) - Container management

---

**Configured:** 2025-11-21
**Connection:** postgresql://localhost:5433/climatenews
**Next Review:** 2026-11-21
