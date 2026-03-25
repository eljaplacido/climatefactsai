# 🚀 CliLens.AI Development Guide

**Quick Reference for Starting Development**  
**Last Updated:** 2025-12-18

---

## 📖 **MANDATORY READING (30 minutes)**

Before writing any code, read these documents in order:

### 1. **[docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)** (10 min) ⭐
**What it covers:**
- What's actually implemented vs what's documented
- Known bugs and issues
- Architecture reality vs vision
- API endpoints that work
- Database schema
- Environment requirements

**Why it matters:**
- Prevents implementing features that assume non-existent infrastructure (Kafka)
- Avoids adding mock data fallbacks (known anti-pattern)
- Clarifies what "done" means for this project

### 2. **[.claude/skills/clilens-development/SKILL.md](.claude/skills/clilens-development/SKILL.md)** (5 min) ⭐
**What it covers:**
- Domain-specific development patterns
- Code quality rules (no mock fallbacks!)
- Testing requirements
- Security patterns
- Common pitfalls to avoid

**Why it matters:**
- Enforces project-specific constraints
- Prevents repeating past mistakes
- Defines "definition of done" for features

### 3. **[docs/AGENT_USAGE_GUIDE.md](docs/AGENT_USAGE_GUIDE.md)** (10 min) ⭐
**What it covers:**
- When to use Cursor vs Claude Code
- How to prompt each tool effectively
- Tool capability differences
- Session handoff protocol

**Why it matters:**
- Saves time by choosing the right tool for the job
- Prevents using Cursor for complex multi-agent tasks
- Avoids using Claude Code for simple edits

### 4. **[New_plan.md](New_plan.md)** (20 min)
**What it covers:**
- Future vision and architecture goals
- Planned features not yet implemented
- Technical decisions and rationale
- Compliance and legal considerations

**Why it matters:**
- Understand long-term direction
- See what's planned but not yet built
- Context for architectural decisions

---

## 🎯 **QUICK DECISION TREE**

```
What are you doing?
├─ Reading/understanding code?
│  └─ Use: Cursor
│     Reason: Fast exploration, good for investigation
│
├─ Quick fix (1-3 files)?
│  └─ Use: Cursor
│     Reason: Fastest for simple edits
│
├─ Querying database?
│  └─ Use: Cursor
│     Reason: Has MCP postgres access
│
├─ Debugging Docker containers?
│  └─ Use: Cursor
│     Reason: Has MCP docker access
│
├─ New feature (multiple components)?
│  └─ Use: Claude Code
│     Reason: Can spawn multiple specialized agents
│
├─ Refactoring 4+ files?
│  └─ Use: Claude Code
│     Reason: Better coordination, checkpoint safety
│
├─ Architecture change?
│  └─ Use: Claude Code
│     Reason: Has SPARC methodology support
│
└─ Complex debugging?
   └─ Use: Claude Code
      Reason: Better context management, can spawn debugger agent
```

---

## ⚡ **5-MINUTE QUICK START**

### **For Cursor Users**

```markdown
1. Read docs/CURRENT_STATE.md (skim the "What Works" section)
2. Verify setup:
   - docker ps  # Should show 4 containers
   - curl http://localhost:5200/healthz  # Should return {"status":"ok"}
3. Start coding:
   - "Show me where claims_count is calculated"
   - "Fix the bug in ArticleCard.tsx line 45"
   - "Query the database for articles with reliability_score > 80"
```

### **For Claude Code Users**

```bash
# 1. Install if not already done
npm install -g claude-flow@alpha

# 2. Verify installation
npx claude-flow features-detect

# 3. Read context
cat docs/CURRENT_STATE.md  # Skim key sections

# 4. Start feature development
npx claude-flow sparc tdd "Implement URL analysis feature"
```

---

## 🛠️ **DEVELOPMENT WORKFLOW**

### **Step 1: Choose Your Tool**

| Task Type | Tool | Command/Prompt |
|-----------|------|----------------|
| Quick edit | Cursor | "Fix typo in line 45" |
| Investigation | Cursor | "Show me where X is used" |
| DB query | Cursor | "SELECT * FROM articles WHERE..." |
| New feature | Claude Code | `npx claude-flow sparc tdd "feature"` |
| Refactoring | Claude Code | Spawn coder + tester + reviewer agents |
| Architecture | Claude Code | `npx claude-flow sparc run architect "..."` |

### **Step 2: Verify Requirements**

**Before coding, check:**

```bash
# 1. API keys present
cat .env | grep ANTHROPIC_API_KEY  # Should have valid key

# 2. Containers running
docker ps | grep clilens  # Should show 4 containers

# 3. Database accessible
docker exec climatenews-postgres pg_isready  # Should say "accepting connections"

# 4. Current state understood
cat docs/CURRENT_STATE.md  # Read "Known Issues" section
```

### **Step 3: Implement**

**Cursor workflow:**
```markdown
1. Prompt: "Implement X"
2. Review proposed changes
3. Accept/reject inline
4. Test manually: curl http://localhost:5200/api/...
5. Done
```

**Claude Code workflow:**
```bash
1. npx claude-flow sparc tdd "Implement X"
2. Watch agents work:
   - Specification agent writes requirements
   - Architecture agent designs solution
   - Coder agent implements
   - Tester agent writes tests
   - Reviewer agent checks quality
3. Verify: Tests pass, manual test works
4. Done
```

### **Step 4: Verify (Definition of "Done")**

✅ **Feature is complete when:**

- [ ] No mock/placeholder code added
- [ ] Tests pass: `pytest tests/` or `npm test`
- [ ] API keys tested and work
- [ ] Manual test in browser/curl works
- [ ] Error cases handled explicitly (no silent failures)
- [ ] `docs/CURRENT_STATE.md` updated if needed
- [ ] No new TODOs or FIXMEs added

### **Step 5: Document**

```bash
# Update current state if needed
# Example: Feature moved from "Planned" to "Working"
nano docs/CURRENT_STATE.md

# Commit with descriptive message
git add .
git commit -m "feat: Implement URL analysis feature

- Added POST /api/analyze-url endpoint
- Created URLAnalyzer.tsx component
- Added tests with 95% coverage
- Updated CURRENT_STATE.md

Closes #123"
```

---

## 🚫 **COMMON MISTAKES TO AVOID**

### **Mistake 1: Assuming Kafka Exists**

❌ **Wrong:**
```python
from kafka import KafkaProducer
producer.send('claims-topic', data)
```

✅ **Correct:**
```python
from shared.database import get_postgres
db.execute_query("INSERT INTO claims ...")
```

**Why:** Kafka infrastructure is not operational (see `CURRENT_STATE.md`)

---

### **Mistake 2: Adding Mock Data Fallbacks**

❌ **Wrong:**
```python
try:
    real_data = api_call()
except:
    return mock_data()  # Silent fallback - BAD!
```

✅ **Correct:**
```python
try:
    real_data = api_call()
except APIError as e:
    raise HTTPException(503, f"Service unavailable: {e}")
```

**Why:** Mock data confuses users (high reliability + 0 claims assessed)

---

### **Mistake 3: Not Reading CURRENT_STATE.md**

❌ **Wrong:**
```
Prompt: "Implement video production with Remotion"
# Wastes time - video production is 5% implemented, lots of missing pieces
```

✅ **Correct:**
```
1. Read docs/CURRENT_STATE.md section "Video Production (5% Complete)"
2. See missing: TTS, B-roll, rendering, storage, API endpoints
3. Prompt: "What should I implement first for video production?"
4. Get realistic scope: Start with placeholder video API endpoint
```

---

### **Mistake 4: Using Wrong Tool**

❌ **Wrong:**
```
# Using Cursor for 15-file refactoring
Cursor: "Refactor the entire claim extraction pipeline"
# Takes 1 hour, lots of back-and-forth
```

✅ **Correct:**
```
# Using Claude Code with SPARC
npx claude-flow sparc refactor "Claim extraction pipeline"
# Spawns multiple agents, done in 15 minutes
```

---

## 🎓 **LEARNING PATH**

### **Week 1: Learn the Codebase with Cursor**

**Day 1-2:**
```markdown
- "Show me the database schema"
- "How does an article flow from ingestion to frontend?"
- "Where is claims_count calculated?"
- "What API endpoints exist?"
```

**Day 3-4:**
```markdown
- "Query articles with high reliability but 0 claims"
- "Show me all places where mock data is used"
- "Find TODOs in the codebase"
```

**Day 5:**
```markdown
- "Fix one small bug" (practice the workflow)
- "Update one docstring"
- "Add one missing type hint"
```

### **Week 2: Simple Features with Cursor**

**Practice tasks:**
- Add a new API filter parameter
- Create a new frontend component
- Write a test for existing feature
- Fix markdown rendering issue

### **Week 3: Complex Features with Claude Code**

**Practice tasks:**
```bash
# Install Claude Flow
npm install -g claude-flow@alpha

# Try SPARC workflows
npx claude-flow sparc modes  # List available modes
npx claude-flow sparc run spec-pseudocode "Add pagination to articles"

# Try multi-agent
npx claude-flow agents list  # See 54 agents
```

### **Week 4: Master Both Tools**

**Projects:**
- Implement user URL analysis (Claude Code)
- Fix search functionality bug (Cursor)
- Refactor claim extraction (Claude Code)
- Update UI styling (Cursor)

---

## 📋 **CHECKLISTS**

### **Before Starting Development**

- [ ] Read `docs/CURRENT_STATE.md`
- [ ] Read `.claude/skills/clilens-development/SKILL.md`
- [ ] Containers running: `docker ps`
- [ ] API works: `curl http://localhost:5200/healthz`
- [ ] Database accessible: `docker exec climatenews-postgres pg_isready`
- [ ] Git clean: `git status`

### **Before Marking Feature "Done"**

- [ ] No mock data added
- [ ] Tests pass: `pytest tests/`
- [ ] Manual test works (curl + browser)
- [ ] Error cases handled explicitly
- [ ] No new TODOs/FIXMEs
- [ ] Logs are informative
- [ ] Updated `CURRENT_STATE.md` if needed
- [ ] Committed with good message

### **Before Switching Tools (Cursor → Claude Code)**

- [ ] Commit current work: `git commit`
- [ ] Update `.claude/memory/session-handoff.json`
- [ ] List completed tasks
- [ ] List known issues
- [ ] Suggest next priorities

---

## 🆘 **TROUBLESHOOTING**

### **"I don't know where to start"**
→ Read `docs/CURRENT_STATE.md` section "NEXT DEVELOPMENT PRIORITIES"

### **"Containers won't start"**
→ See `docs/GETTING_STARTED.md` troubleshooting section

### **"API returns 500 errors"**
```bash
docker logs clilens-api --tail 50
# Look for error messages, missing API keys, database connection issues
```

### **"Tests fail"**
```bash
# Check if database has data
docker exec climatenews-postgres psql -U postgres -d climatenews -c "SELECT count(*) FROM articles"

# Check if API key is set
cat .env | grep ANTHROPIC_API_KEY
```

### **"Cursor can't do X"**
→ Check `docs/TOOL_AVAILABILITY.md` - might need Claude Code instead

### **"Claude Code not working"**
```bash
# Verify installation
npx claude-flow features-detect

# Check MCP servers
cat .claude/settings.json
```

---

## 🎯 **QUICK COMMANDS REFERENCE**

### **Cursor**
```markdown
# Just type in chat:
"Show me where X is defined"
"Fix the bug in file.ts line 45"
"Query the database for articles with claims_count = 0"
"What does this function do?"
```

### **Claude Code**
```bash
# SPARC workflows
npx claude-flow sparc tdd "Feature description"
npx claude-flow sparc run architect "Design X"
npx claude-flow sparc pipeline "Full pipeline"

# Agent management
npx claude-flow agents list
npx claude-flow swarm status

# Features
npx claude-flow features-detect
npx claude-flow@alpha agent-booster enable --task "task-name"
```

### **Docker**
```bash
# Status
docker ps
docker logs clilens-api --tail 50

# Restart
docker-compose restart api
docker-compose restart frontend

# Database
docker exec climatenews-postgres psql -U postgres -d climatenews
```

---

## 📚 **ESSENTIAL LINKS**

- **[docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)** - Reality check
- **[docs/AGENT_USAGE_GUIDE.md](docs/AGENT_USAGE_GUIDE.md)** - Tool selection
- **[docs/TOOL_AVAILABILITY.md](docs/TOOL_AVAILABILITY.md)** - Feature parity
- **[.claude/skills/clilens-development/SKILL.md](.claude/skills/clilens-development/SKILL.md)** - Domain rules
- **[New_plan.md](New_plan.md)** - Future vision
- **[CLAUDE.md](CLAUDE.md)** - Full reference

---

**This guide was created to give developers a fast, practical entry point to the project.**

**Next Update:** After gathering feedback from 5 developers using this guide

**Last Updated:** 2025-12-18

