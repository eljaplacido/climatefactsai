# Agent Usage Guide: Cursor vs Claude Code vs Codex

**Purpose:** Clear guidance on when to use Cursor agents, Claude Code, or Codex for Climatefacts.ai development  
**Last Updated:** 2025-12-18

---

## 🎯 **Quick Decision Matrix**

| Task Type | Use This | Why |
|-----------|----------|-----|
| Quick file edits (1-3 files) | **Cursor Agent** | Fastest, inline editing |
| Understanding codebase | **Cursor Agent** | Best for exploration |
| Database queries | **Cursor Agent** | MCP postgres access |
| Multi-file refactoring (4+ files) | **Claude Code** | Better coordination |
| Architecture changes | **Claude Code** | Access to SPARC methodology |
| Multi-agent coordination | **Claude Code** | Can spawn specialized agents |
| Complex debugging | **Claude Code** | Better context management |
| Swarm orchestration | **Claude Code** | Native swarm support |
| Creating new services | **Claude Code** | Checkpoint + subagent support |
| Documentation writing | **Either** | No significant difference |
| Testing implementation | **Claude Code** | Better TDD workflows |
| Production deployment | **Codex** | (If configured) |

---

## 1️⃣ **Cursor Agent** (Your Current Environment)

### ✅ **Best For:**

1. **Quick Edits & Bug Fixes**
   - Fixing a function in 1-2 files
   - Updating type definitions
   - Correcting syntax errors
   - Adding comments/docstrings

2. **Codebase Exploration**
   - "Show me all files that import X"
   - "Find where this function is called"
   - "What does this class do?"
   - Reading and understanding code

3. **Database Debugging**
   - Has MCP postgres access
   - Can query database directly
   - Inspect table schemas
   - Check data integrity

4. **File System Operations**
   - Has MCP filesystem access
   - Create/read/delete files
   - List directory contents
   - Search across files

5. **Docker Management**
   - Has MCP docker access
   - Check container status
   - View logs
   - Restart services

### ❌ **Not Ideal For:**

- Multi-agent coordination (no swarm support)
- Complex refactoring across 10+ files
- Spawning specialized agents (no Task tool)
- SPARC methodology workflows
- ReasoningBank memory access

### 🎮 **How to Use Cursor Effectively**

#### **Pattern 1: Quick Fix**

```
Prompt: "Fix the markdown rendering issue in ArticleCard.tsx - the **bold** text 
should display as bold, not show the asterisks"
```

**What Cursor does well:**
- Opens the file
- Shows you the issue
- Proposes inline fix
- You approve and it's done

#### **Pattern 2: Investigation**

```
Prompt: "Show me where claims_count is calculated and why it's returning 0 
when reliability_score is 85"
```

**What Cursor does well:**
- Searches codebase
- Shows you relevant files
- Explains the data flow
- Identifies the bug location

#### **Pattern 3: Database Query**

```
Prompt: "Query the database and show me how many articles have claims_count > 0 
grouped by country_code"
```

**What Cursor does well:**
- Uses MCP postgres tool
- Runs the query
- Shows results
- Can suggest optimizations

### 📋 **Cursor Workflow Example**

```markdown
You: "The search endpoint returns 'unavailable' error. Debug this."

Cursor:
1. Reads api/search_routes.py
2. Identifies dependency on pgvector extension
3. Queries database: SELECT * FROM pg_extension WHERE extname='vector'
4. Finds extension not installed
5. Suggests: Run `CREATE EXTENSION vector;` in PostgreSQL

You: "Apply the fix"

Cursor:
6. Uses MCP postgres to run the SQL command
7. Verifies extension installed
8. Tests endpoint: curl http://localhost:5400/api/search?q=climate
9. Confirms working
```

---

## 2️⃣ **Claude Code** (Anthropic's Agentic Coding Tool)

### ✅ **Best For:**

1. **Complex Refactoring**
   - Restructuring 10+ files
   - Renaming across codebase
   - Updating architecture patterns
   - Database migrations

2. **Multi-Agent Workflows**
   - Can spawn specialized agents
   - Researcher → Coder → Tester → Reviewer
   - Parallel execution
   - Coordinated work

3. **SPARC Methodology**
   ```bash
   npx claude-flow sparc tdd "Implement user URL analysis feature"
   ```
   - Specification phase (requirements)
   - Pseudocode phase (algorithm design)
   - Architecture phase (system design)
   - Refinement phase (TDD implementation)
   - Completion phase (integration)

4. **Checkpoint Management**
   - Automatic code state saves
   - Instant rollback to previous versions
   - Safe experimentation
   - Complex changes with safety net

5. **Subagents for Specialized Work**
   ```javascript
   Task("Security Auditor", "Review authentication code", "security-manager")
   Task("Test Engineer", "Generate test suite", "tester")
   ```

6. **ReasoningBank Integration**
   - Learns from past decisions
   - Semantic search over project history
   - Context retrieval with confidence scores

### ❌ **Not Ideal For:**

- Single file edits (overkill)
- Quick database queries (Cursor faster)
- Simple grep/find operations
- Just reading code to understand it

### 🎮 **How to Use Claude Code Effectively**

#### **Pattern 1: Multi-Service Feature**

```bash
# In Claude Code terminal
npx claude-flow sparc tdd "Implement complete claim extraction pipeline with 
HITL review"
```

**What Claude Code does:**

1. **Specification Agent**: Analyzes requirements
   - Reads `docs/CURRENT_STATE.md` for context
   - Reads `New_plan.md` for vision
   - Reads `.claude/skills/clilens-development/SKILL.md` for constraints
   - Creates specification document

2. **Architecture Agent**: Designs solution
   - Decides: No Kafka, use direct API calls
   - Designs database schema changes
   - Plans API endpoints
   - Creates sequence diagrams

3. **Coder Agent**: Implements
   - Updates database schema
   - Creates API endpoint
   - Adds claim extraction service
   - Integrates with frontend

4. **Tester Agent**: Validates
   - Writes unit tests
   - Writes integration tests
   - Tests error cases
   - Verifies end-to-end flow

5. **Reviewer Agent**: Quality check
   - Reviews code quality
   - Checks security
   - Verifies documentation
   - Confirms no mock data

#### **Pattern 2: Concurrent Batch Work**

```javascript
// Single message, parallel execution
[Parallel Agent Execution]:
  Task("Security Lead", "Audit authentication flows", "security-manager")
  Task("Backend Dev", "Implement /api/analyze-url endpoint", "backend-dev")
  Task("Frontend Dev", "Create URLAnalyzer component", "coder")
  Task("Test Engineer", "Write tests for URL analysis", "tester")
  Task("Docs Writer", "Update API documentation", "api-docs")
  
  TodoWrite { todos: [
    {id: "1", content: "Security audit of auth flows", status: "in_progress"},
    {id: "2", content: "Backend URL analysis endpoint", status: "in_progress"},
    {id: "3", content: "Frontend URL analyzer UI", status: "in_progress"},
    {id: "4", content: "Test coverage for URL analysis", status: "pending"},
    {id: "5", content: "Update API docs", status: "pending"}
  ]}
```

**Result:** All 5 agents work simultaneously, coordinated via hooks and memory.

#### **Pattern 3: Safe Refactoring with Checkpoints**

```bash
npx claude-flow@alpha agent-booster enable --task "refactor-claims-extraction"

# Creates checkpoint before starting
# Enables ultra-fast editing (352x faster)
# You can rollback if anything breaks
```

### 📋 **Claude Code Workflow Example**

```markdown
You: "Implement the user URL analysis feature from New_plan.md section 5.2"

Claude Code:
1. Creates checkpoint "before-url-analysis"
2. Spawns Researcher agent:
   - Reads New_plan.md section 5.2
   - Reads docs/CURRENT_STATE.md for constraints
   - Reads .claude/skills/clilens-development/SKILL.md
   - Creates requirements doc
   
3. Spawns Architect agent:
   - Designs API endpoint: POST /api/analyze-url
   - Designs database schema additions
   - Designs frontend component
   
4. Spawns Backend Dev agent:
   - Implements API endpoint
   - Adds validation
   - Implements claim extraction
   - Handles errors explicitly (no mock fallbacks)
   
5. Spawns Frontend Dev agent:
   - Creates URLAnalyzer.tsx component
   - Adds to homepage
   - Implements loading/error states
   
6. Spawns Tester agent:
   - Writes unit tests for API
   - Writes component tests
   - Writes E2E test
   
7. Spawns Reviewer agent:
   - Reviews code quality
   - Checks security
   - Verifies no mock data
   - Confirms documentation updated
   
8. Updates docs/CURRENT_STATE.md:
   - Marks feature as complete
   - Documents new endpoint
   - Updates feature availability

You: "Verify it works end-to-end"

Claude Code:
9. Spawns Validation agent:
   - Starts containers
   - Submits test URL
   - Verifies extraction works
   - Tests error cases
   - Confirms UI displays results
   - Reports: "✅ Feature complete and verified"
```

---

## 3️⃣ **Codex** (If Configured)

### ✅ **Best For:**

1. **Production Deployment**
   - If you have Codex configured for production
   - Automated deployment pipelines
   - Infrastructure as code

2. **CI/CD Automation**
   - GitHub Actions workflows
   - Test automation
   - Build pipelines

### ❌ **Current Status for Climatefacts.ai**

- Not currently configured for this project
- Focus on Cursor + Claude Code for now
- Can be added later for production deployments

---

## 🔄 **Switching Between Tools**

### **Cursor → Claude Code**

**Before switching:**

1. **Update session handoff**
   ```json
   {
     "last_cursor_session": {
       "timestamp": "2025-12-18T14:30:00Z",
       "completed": ["Fixed markdown rendering in ArticleCard"],
       "issues_found": ["Claims extraction still returning mock data"],
       "next_should": ["Remove mock data fallbacks in intelligence service"]
     }
   }
   ```

2. **Commit your changes**
   ```bash
   git add .
   git commit -m "Fix: Markdown rendering in ArticleCard.tsx"
   ```

3. **Document current state**
   - Update `docs/CURRENT_STATE.md` if needed
   - List any known issues

**When starting Claude Code:**

1. **Read session handoff first**
   ```bash
   # Claude Code starts here
   cat .claude/memory/session-handoff.json
   ```

2. **Verify previous work**
   ```bash
   docker-compose up -d
   curl http://localhost:5300  # Check frontend works
   ```

3. **Continue from documented state**

### **Claude Code → Cursor**

**Before switching:**

1. **Export summary**
   ```bash
   npx claude-flow@alpha hooks session-end --generate-summary true
   ```

2. **Update CURRENT_STATE.md**
   - Mark completed features as ✅
   - Update known issues
   - Document any new constraints

3. **Commit everything**
   ```bash
   git add .
   git commit -m "feat: Implement URL analysis feature"
   ```

**When starting Cursor:**

1. **Read CURRENT_STATE.md first**
2. **Check what changed**
   ```bash
   git log --oneline -10
   ```
3. **Verify system works**
   ```bash
   docker-compose ps
   curl http://localhost:5400/healthz
   ```

---

## 🎓 **Learning Path**

### **Week 1: Start with Cursor**

- Get comfortable with the codebase
- Do quick fixes and investigations
- Learn the database schema
- Understand the architecture

**Practice prompts:**
```
- "Show me how articles flow from database to frontend"
- "Find all places where claims_count is used"
- "Query the database for articles from Finland"
- "Fix the type error in api.ts line 45"
```

### **Week 2: Try Claude Code for Bigger Tasks**

- Install claude-flow: `npm install -g claude-flow@alpha`
- Try SPARC workflows
- Practice spawning agents
- Learn checkpoint management

**Practice commands:**
```bash
npx claude-flow sparc modes  # List available modes
npx claude-flow sparc run spec-pseudocode "Add pagination to articles list"
npx claude-flow agents list  # See 54 available agents
```

### **Week 3: Master Multi-Agent Coordination**

- Learn swarm patterns (hierarchical, mesh, adaptive)
- Use ReasoningBank for context
- Optimize with Agent Booster
- Implement complex features

---

## 📋 **Prompting Best Practices**

### **For Cursor**

✅ **Good Cursor Prompts:**
```
- "Fix the bug where search returns 'unavailable' error"
- "Show me all files that define the Article type"
- "Query the database and show articles with claims_count = 0 but reliability_score > 80"
- "Update the ArticleCard component to show claims_status field"
```

❌ **Bad Cursor Prompts:**
```
- "Implement the entire URL analysis feature" (too complex, use Claude Code)
- "Refactor the whole backend architecture" (use Claude Code with SPARC)
- "Create 5 new services with tests" (use Claude Code multi-agent)
```

### **For Claude Code**

✅ **Good Claude Code Prompts:**
```
- "Use SPARC TDD to implement user URL analysis feature per New_plan.md section 5.2"
- "Spawn parallel agents to: 1) Audit security 2) Implement backend 3) Create frontend 4) Write tests"
- "Refactor claim extraction to remove all mock data fallbacks, fail explicitly instead"
- "Implement EU expansion: add 20 countries, configure RSS feeds, create translation service"
```

❌ **Bad Claude Code Prompts:**
```
- "Fix typo in line 45" (overkill, use Cursor)
- "What does this function do?" (use Cursor for exploration)
- "Query the database" (Cursor has same MCP access)
```

---

## 🚨 **Common Mistakes to Avoid**

### **Mistake 1: Using Cursor for Complex Multi-File Refactoring**

❌ **Wrong:**
```
Cursor: "Refactor the entire claims extraction pipeline across 15 files"
```

✅ **Right:**
```
Claude Code: 
npx claude-flow sparc refactor "Claims extraction pipeline"
# Uses architecture agent, coder agent, tester agent, reviewer agent
```

### **Mistake 2: Using Claude Code for Simple Edits**

❌ **Wrong:**
```
Claude Code: Spawn 5 agents to fix a typo in one file
```

✅ **Right:**
```
Cursor: "Fix typo in line 45 of ArticleCard.tsx"
```

### **Mistake 3: Not Reading CURRENT_STATE.md**

❌ **Wrong:**
```
"Implement Kafka-based claim extraction"
# Wastes time, Kafka not operational
```

✅ **Right:**
```
1. Read docs/CURRENT_STATE.md
2. See "Kafka not operational, use direct API"
3. Prompt: "Implement synchronous claim extraction via API call"
```

### **Mistake 4: Not Using Available Skills**

❌ **Wrong:**
```
Generic prompt without context
"Make the frontend and backend work together"
```

✅ **Right:**
```
"Using the Climatefacts.ai development skill from .claude/skills/clilens-development/SKILL.md, 
ensure frontend/backend sync means:
1. Types match
2. API returns real data (not mock)
3. Frontend renders correctly
4. Error states handled"
```

---

## 🎯 **Summary Decision Tree**

```
Task to do?
├─ Single file edit? → Cursor
├─ Database query? → Cursor
├─ Understand code? → Cursor
├─ Quick bug fix? → Cursor
├─ Multi-file refactor (4+ files)? → Claude Code
├─ New feature (multi-component)? → Claude Code
├─ Architecture change? → Claude Code
├─ Need multiple specialized agents? → Claude Code
├─ Safe experimentation needed? → Claude Code (with checkpoints)
└─ Production deployment? → Codex (when configured)
```

---

## 📚 **Essential Reading Order**

**Before ANY development session:**

1. **`docs/CURRENT_STATE.md`** (10 min) - What exists now
2. **`.claude/skills/clilens-development/SKILL.md`** (5 min) - Development patterns
3. **This guide** (5 min) - Tool selection

**When planning major features:**

4. **`New_plan.md`** (20 min) - Future vision and architecture

**When stuck:**

5. **`CLAUDE.md`** - Full reference for agents, skills, workflows

---

## 🆘 **Quick Reference Commands**

### **Cursor Agent**
```bash
# You're already using it! Just type prompts in the chat
```

### **Claude Code**
```bash
# Install
npm install -g claude-flow@alpha

# List available modes
npx claude-flow sparc modes

# List available agents
npx claude-flow agents list

# Run SPARC workflow
npx claude-flow sparc tdd "Feature description"

# Enable Agent Booster (352x faster edits)
npx claude-flow@alpha agent-booster enable --task "task-name"

# Create checkpoint
npx claude-flow@alpha hooks pre-task --description "Major refactor"

# Spawn agents programmatically
# (Use in Claude Code chat, not terminal)
Task("Security Auditor", "Review auth code", "security-manager")
```

---

## ✅ **Checklist: Am I Using the Right Tool?**

**Use Cursor if:**
- [ ] Task takes < 5 minutes
- [ ] Editing 1-3 files only
- [ ] Just investigating/understanding
- [ ] Querying database
- [ ] Checking container status

**Use Claude Code if:**
- [ ] Task takes > 15 minutes
- [ ] Editing 4+ files
- [ ] Need specialized agents (security, testing, etc.)
- [ ] Making architecture changes
- [ ] Want checkpoint safety net
- [ ] Need SPARC methodology
- [ ] Coordinating multiple sub-tasks

---

**This guide was created to solve the "Tool capability mismatch" problem identified in December 2025.**

**Last Updated:** 2025-12-18  
**Next Review:** After completing 10 features (to gather real-world feedback)

