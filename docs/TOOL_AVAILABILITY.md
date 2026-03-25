# Tool Availability Matrix: Cursor vs Claude Code

**Purpose:** Document which tools and capabilities are available in each development environment  
**Last Updated:** 2025-12-18

---

## 📊 **Complete Feature Comparison**

| Feature | Cursor Agent | Claude Code | Notes |
|---------|--------------|-------------|-------|
| **File System Access** | ✅ MCP filesystem | ✅ Native | Identical capability |
| **PostgreSQL Queries** | ✅ MCP postgres | ✅ Via shared/database.py | Same MCP server |
| **Docker Control** | ✅ MCP docker | ✅ Via bash | Same capability |
| **Read Files** | ✅ Native | ✅ Native | Both can read any file |
| **Edit Files** | ✅ Inline editing | ✅ Native | Cursor has better inline UI |
| **Search Codebase** | ✅ grep/search | ✅ codebase_search | Similar capability |
| **Run Commands** | ✅ Terminal access | ✅ Terminal access | Identical |
| **Git Operations** | ✅ Via terminal | ✅ Via terminal | Identical |
| **Claude Flow Agents** | ❌ Not available | ✅ MCP claude-flow | **Cursor cannot spawn agents** |
| **SPARC Methodology** | ❌ Manual only | ✅ Automated | **Major difference** |
| **ReasoningBank** | ❌ Not available | ✅ MCP ruv-swarm | **Cursor cannot access** |
| **Skill Auto-Loading** | ⚠️ Manual prompting | ✅ Automatic | Cursor needs explicit instructions |
| **Multi-Agent Coordination** | ❌ Single agent only | ✅ Swarm support | **Cursor cannot coordinate** |
| **Checkpoint System** | ❌ Not available | ✅ Automatic saves | **Rollback only in Claude Code** |
| **Subagents** | ❌ Not available | ✅ Can spawn | **Cursor cannot delegate** |
| **Agent Booster** | ❌ Not available | ✅ 352x faster editing | **Cursor normal speed** |
| **OpenRouter Proxy** | ❌ Not available | ✅ 85-98% cost savings | **Cost difference** |
| **Hooks System** | ⚠️ Limited | ✅ Full integration | Pre/post task hooks |
| **Session Memory** | ⚠️ Chat history only | ✅ Persistent memory | ReasoningBank integration |
| **Task Tool** | ❌ Not available | ✅ Can spawn parallel agents | **Major capability gap** |

---

## 🔧 **MCP Server Access**

### **Shared MCP Servers (Both Have Access)**

#### 1. **Filesystem MCP**
```bash
# Connection string (both tools)
@modelcontextprotocol/server-filesystem
```

**Capabilities:**
- Read any file in workspace
- Write/create files
- Delete files
- List directories
- File search

**Usage in Cursor:**
```
"Read the file src/backend/app/main.py"
```

**Usage in Claude Code:**
```javascript
Read("src/backend/app/main.py")
```

#### 2. **PostgreSQL MCP**
```bash
# Connection string (both tools)
@modelcontextprotocol/server-postgres
# Connected to: postgresql://postgres:postgres@localhost:5433/climatenews
```

**Capabilities:**
- Execute SELECT queries
- View table schemas
- Check data integrity
- Read-only access (safe)

**Usage in Cursor:**
```
"Query the database and show me articles with claims_count = 0"
```

**Usage in Claude Code:**
```javascript
// Same MCP access
```

#### 3. **Docker MCP**
```bash
# Connection string (both tools)
@modelcontextprotocol/server-docker
```

**Capabilities:**
- List containers
- Check container status
- View logs
- Start/stop containers

**Usage in Cursor:**
```
"Show me the status of all Docker containers"
```

**Usage in Claude Code:**
```javascript
Bash("docker ps")
```

---

### **Claude Code Exclusive MCP Servers**

#### 4. **Claude Flow MCP** ❌ Cursor Cannot Access

```json
// .claude/settings.json
"enabledMcpjsonServers": ["claude-flow", "ruv-swarm"]
```

**Capabilities:**
- Spawn 54 specialized agents
- SPARC methodology automation
- Multi-agent coordination
- Swarm orchestration
- Task distribution
- Parallel execution

**Why Cursor Can't Use:**
- Requires claude-flow npm package
- Needs Task tool integration
- Cursor doesn't support swarm coordination

**Impact:**
- Cursor: Single agent, sequential work
- Claude Code: Multiple agents, parallel work

#### 5. **Ruv-Swarm MCP** ❌ Cursor Cannot Access

**Capabilities:**
- ReasoningBank memory integration
- Neural pattern training
- Collective intelligence coordination
- Advanced swarm features

**Why Cursor Can't Use:**
- Requires ruv-swarm package
- Not in Cursor's MCP configuration

---

## 🎯 **Capability Breakdown**

### **What Cursor Does Better**

1. **Inline Editing UI**
   - Shows diffs directly in editor
   - Click to accept/reject changes
   - Visual feedback

2. **Quick Exploration**
   - Fast file navigation
   - Immediate feedback
   - Lower latency for simple queries

3. **Learning Curve**
   - Simpler interface
   - No command line needed
   - Easier for beginners

### **What Claude Code Does Better**

1. **Complex Orchestration**
   ```javascript
   // Spawn 5 agents to work in parallel
   Task("Security Auditor", "...", "security-manager")
   Task("Backend Dev", "...", "backend-dev")
   Task("Frontend Dev", "...", "coder")
   Task("Tester", "...", "tester")
   Task("Reviewer", "...", "reviewer")
   ```

2. **SPARC Methodology**
   ```bash
   npx claude-flow sparc tdd "Implement feature"
   # Automatically:
   # 1. Specification phase
   # 2. Pseudocode phase
   # 3. Architecture phase
   # 4. Refinement phase (TDD)
   # 5. Completion phase
   ```

3. **Safety Features**
   ```bash
   # Automatic checkpoints before changes
   npx claude-flow@alpha hooks pre-task --description "..."
   # Can rollback if something breaks
   ```

4. **Performance**
   ```bash
   # Agent Booster: 352x faster than traditional LLM APIs
   npx claude-flow@alpha agent-booster enable
   ```

5. **Cost Optimization**
   ```bash
   # OpenRouter proxy: 85-98% cost savings
   CLAUDE_FLOW_ROUTER=openrouter
   ```

---

## 🔄 **Feature Equivalence Table**

| Task | Cursor Command | Claude Code Command | Notes |
|------|----------------|---------------------|-------|
| Read file | "Read api/main.py" | `Read("api/main.py")` | Identical |
| Edit file | "Fix bug in api/main.py" | `Edit("api/main.py", ...)` | Cursor has better UI |
| Query DB | "Select count(*) from articles" | Same via MCP postgres | Identical |
| Docker logs | "Show logs for clilens-api" | `Bash("docker logs clilens-api")` | Identical |
| Git status | "Show git status" | `Bash("git status")` | Identical |
| Spawn agents | ❌ Cannot do | `Task("agent", "...", "type")` | **Only Claude Code** |
| SPARC workflow | ❌ Cannot do | `npx claude-flow sparc tdd` | **Only Claude Code** |
| Checkpoints | ❌ Cannot do | `npx claude-flow hooks pre-task` | **Only Claude Code** |
| ReasoningBank | ❌ Cannot do | `npx claude-flow memory connect` | **Only Claude Code** |

---

## 🎓 **Skill System Access**

### **Cursor: Manual Skill Loading**

```
Prompt: "Using the development patterns from .claude/skills/clilens-development/SKILL.md, 
fix the claims extraction to never return mock data"
```

**How it works:**
- You manually reference the skill
- Cursor reads the file
- Applies patterns from skill
- No automatic context loading

### **Claude Code: Automatic Skill Loading**

```javascript
// Claude Code automatically:
1. Reads all skills in .claude/skills/
2. Loads clilens-development skill
3. Applies constraints (no Kafka, no mock data)
4. Uses patterns without you asking
```

**Impact:**
- Cursor: Need to explicitly mention skills
- Claude Code: Skills always active

---

## 📊 **Performance Comparison**

### **Single File Edit (< 100 lines)**

| Metric | Cursor | Claude Code | Winner |
|--------|--------|-------------|--------|
| Time to first response | 2-3 seconds | 3-5 seconds | Cursor |
| Edit UI quality | Excellent (inline) | Good (file-based) | Cursor |
| Context awareness | Good | Excellent (skill-based) | Claude Code |

**Recommendation:** Use Cursor for quick single-file edits

### **Multi-File Refactor (10+ files)**

| Metric | Cursor | Claude Code | Winner |
|--------|--------|-------------|--------|
| Time to complete | 30-45 minutes (sequential) | 10-15 minutes (parallel agents) | Claude Code |
| Coordination quality | Manual (you coordinate) | Automatic (swarm) | Claude Code |
| Safety (rollback) | Git only | Git + checkpoints | Claude Code |
| Testing coverage | You must prompt | Automatic (tester agent) | Claude Code |

**Recommendation:** Use Claude Code for complex refactoring

### **New Feature Development**

| Metric | Cursor | Claude Code | Winner |
|--------|--------|-------------|--------|
| Planning | Manual | SPARC automated | Claude Code |
| Implementation | Good | Excellent (multiple agents) | Claude Code |
| Testing | Manual prompting | Automatic | Claude Code |
| Documentation | Manual prompting | Automatic | Claude Code |
| Quality assurance | Manual | Reviewer agent | Claude Code |

**Recommendation:** Use Claude Code for feature development

---

## 🔌 **Adding New MCP Servers**

### **For Cursor**

1. **Check if server is standard MCP**
   - Must be from @modelcontextprotocol org
   - Or compatible third-party

2. **Add to `.claude/mcp-config.json`**
   ```json
   {
     "mcpServers": {
       "new-server": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-name"],
         "description": "What it does"
       }
     }
   }
   ```

3. **Restart Cursor**

### **For Claude Code**

1. **Install MCP package**
   ```bash
   npm install -g @modelcontextprotocol/server-name
   ```

2. **Add to `.claude/settings.json`**
   ```json
   {
     "enabledMcpjsonServers": ["claude-flow", "ruv-swarm", "new-server"]
   }
   ```

3. **Verify**
   ```bash
   npx claude-flow features-detect
   ```

---

## 🎯 **Practical Decision Making**

### **Example 1: Bug Fix**

**Task:** Fix markdown rendering in ArticleCard.tsx

**Analysis:**
- Single file edit ✓
- Quick fix ✓
- No coordination needed ✓

**Use:** **Cursor** ✅

### **Example 2: New Feature**

**Task:** Implement user URL analysis with claim extraction, UI, tests, docs

**Analysis:**
- Multi-component (backend, frontend, tests, docs)
- Requires coordination
- Needs SPARC planning
- Benefits from parallel agents
- Needs safety (checkpoints)

**Use:** **Claude Code** ✅

### **Example 3: Database Investigation**

**Task:** Find why claims_count is 0 for most articles

**Analysis:**
- Requires database queries ✓
- Single-agent investigation ✓
- Both have postgres MCP ✓

**Use:** **Cursor** ✅ (Faster for exploration)

### **Example 4: Architecture Refactor**

**Task:** Remove all Kafka dependencies and simplify to REST + Celery

**Analysis:**
- 15+ files affected
- Requires architecture planning
- Needs testing across all services
- High risk (needs checkpoints)
- Benefits from specialized agents

**Use:** **Claude Code** ✅

---

## 📚 **Reference Documentation**

### **Cursor-Specific Docs**
- Official: https://cursor.sh/docs
- MCP Config: `.claude/mcp-config.json`

### **Claude Code-Specific Docs**
- Official: https://www.anthropic.com/claude-code
- GitHub: https://github.com/ruvnet/claude-flow
- Settings: `.claude/settings.json`
- Skills: `.claude/skills/`
- Agents: `.claude/agents/`

### **Shared Docs**
- MCP Protocol: https://modelcontextprotocol.io
- PostgreSQL MCP: @modelcontextprotocol/server-postgres
- Docker MCP: @modelcontextprotocol/server-docker
- Filesystem MCP: @modelcontextprotocol/server-filesystem

---

## ✅ **Quick Reference**

**"Can I do X in Cursor?"**

```
✅ Yes, both have it:
- Read/write files
- Query PostgreSQL  
- Control Docker
- Run bash commands
- Git operations

❌ No, only Claude Code:
- Spawn multiple agents
- SPARC workflows
- Checkpoints/rollback
- ReasoningBank memory
- Agent Booster
- Parallel execution
```

**"Should I use Cursor or Claude Code?"**

```
Use Cursor if task is:
- Single file edit
- < 5 minutes work
- Just investigating
- Database query
- Reading code

Use Claude Code if task is:
- Multi-file refactor
- > 15 minutes work
- New feature
- Architecture change
- Needs specialized agents
- High risk (needs checkpoint)
```

---

**This document was created to answer: "Are the same MCP tools available for Cursor agents and Claude Code?"**

**Answer:** Partially. Shared MCPs (filesystem, postgres, docker) work in both. Advanced MCPs (claude-flow, ruv-swarm) only work in Claude Code.

**Last Updated:** 2025-12-18

