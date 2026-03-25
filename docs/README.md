# CliLens.AI Documentation

**Last Updated:** 2026-03-05

---

## 📚 **START HERE**

Read these documents in order when beginning development:

### 1️⃣ **[CURRENT_STATE.md](CURRENT_STATE.md)** ⭐ **MOST IMPORTANT**
- **What it is:** Single source of truth for the project's current state
- **Read time:** 10 minutes
- **When to read:** Before every development session
- **What you'll learn:** What works, what doesn't, known issues, architecture reality

### 2️⃣ **[GETTING_STARTED.md](GETTING_STARTED.md)**
- **What it is:** Quick start guide to run the platform locally
- **Read time:** 5 minutes
- **When to read:** First time setup
- **What you'll learn:** How to start containers, verify everything works

### 3️⃣ **[AGENT_USAGE_GUIDE.md](AGENT_USAGE_GUIDE.md)** ⭐ **CRITICAL FOR AI AGENTS**
- **What it is:** Guide for when to use Cursor vs Claude Code vs Codex
- **Read time:** 10 minutes
- **When to read:** Before starting any AI-assisted development
- **What you'll learn:** Tool selection, prompting patterns, handoff protocol

### 4️⃣ **[TOOL_AVAILABILITY.md](TOOL_AVAILABILITY.md)**
- **What it is:** MCP tool comparison matrix (Cursor vs Claude Code)
- **Read time:** 5 minutes
- **When to read:** When choosing development environment
- **What you'll learn:** What each tool can/cannot do, feature parity

---

## 🎯 **ESSENTIAL DOCUMENTS (Read These)**

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[CURRENT_STATE.md](CURRENT_STATE.md)** | What exists now | Every session |
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | How to run locally | First time |
| **[START_HERE_AGENT_GUIDE.md](START_HERE_AGENT_GUIDE.md)** | Entry point for AI agents | Agent session start |
| **[AGENT_USAGE_GUIDE.md](AGENT_USAGE_GUIDE.md)** | Tool selection guide | Before coding |
| **[TOOL_AVAILABILITY.md](TOOL_AVAILABILITY.md)** | MCP feature matrix | When stuck |
| **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** | Developer conventions | Starting development |
| **[TESTING_GUIDE.md](TESTING_GUIDE.md)** | How to test | Writing tests |
| **[VISION_GLOBAL_CLIMATE_PLATFORM.md](VISION_GLOBAL_CLIMATE_PLATFORM.md)** | Future vision | Planning new features |

---

## 📂 **DIRECTORY STRUCTURE**

```
docs/
├── README.md                         This file
├── CURRENT_STATE.md                  ⭐ START HERE - Single source of truth
├── GETTING_STARTED.md                Quick start guide
├── LOCAL_RUN_EN.md                   Local run instructions (English)
├── DOCKER_SETUP.md                   Docker setup reference
├── DEVELOPMENT_GUIDE.md              Developer workflow and conventions
├── QUICK_REFERENCE.md                Command and config cheat-sheet
├── START_HERE_AGENT_GUIDE.md         ⭐ Entry point guide for AI agents
├── AGENT_USAGE_GUIDE.md              ⭐ When to use Cursor vs Claude Code
├── TESTING_GUIDE.md                  Main testing guide
├── TESTING_PHASE_1_FEATURES.md       Phase 1 feature test coverage
├── TOOL_AVAILABILITY.md              ⭐ MCP tool comparison matrix
├── MVP_COMPLETION_PLAN.md            MVP scope and completion checklist
├── MVP_EUROPE_ROADMAP.md             European expansion roadmap
├── MVP_SUCCESS_REPORT.md             MVP success criteria and results
├── PHASE_1_COMPLETION_REPORT.md      Phase 1 completion summary
├── PLATFORM_HEALTH_CHECK.md          Platform health runbook
├── PROJECT_EVALUATION_REPORT.md      Comprehensive status report
├── USER_FOCUSED_REBUILD_PLAN.md      User-facing rebuild plan
├── UX_LOCATION_SOURCE_SELECTION.md   UX design: location and source selection
├── VISION_GLOBAL_CLIMATE_PLATFORM.md Long-term platform vision
├── WORKFLOW_AND_UX.md                UX workflows and interaction design
├── URL_ANALYSIS_IMPLEMENTATION.md    URL analysis feature implementation
├── url-analysis-form-implementation.md  URL analysis form implementation detail
├── search_fix_root_cause_analysis.md Search bug root cause analysis
│
├── api/                              API-specific documentation
│   └── backend.md                   Backend API reference
│
├── architecture/                     Architecture decisions and patterns
│   ├── DEPLOYMENT.md                 Deployment architecture
│   ├── adr-kafka-to-redis-celery.md  ADR: Kafka → Redis/Celery migration
│   ├── compliance-hitl.md            Human-in-the-loop compliance workflows
│   ├── data-model-trust.md           Trust scoring data model
│   └── environment-config.md         Environment variable reference
│
├── domain/                           Domain model specifications
│   ├── content.md
│   ├── identity.md
│   ├── ingestion.md
│   └── verification.md
│
├── mcp/                              MCP server documentation
│   ├── README.md                     MCP server overview
│   ├── DEV-01-TEST-RESULTS.md        MCP dev environment test results
│   ├── docker.md                     Docker MCP usage
│   ├── filesystem.md                 Filesystem MCP usage
│   └── postgres.md                   PostgreSQL MCP usage
│
├── metrics/                          Metrics and dashboard assets
│   └── enhanced-dashboard.html       Enhanced metrics dashboard (HTML)
│
├── operations/                       Operational guidelines
│   └── GUARDRAILS.md                 Safety and operational guardrails
│
├── services/                         Service-specific documentation
│   └── api-ux-alignment.md           API and UX alignment notes
│
├── testing/                          Testing documentation
│   ├── TEST_RESULTS_PHASE_0-2.md     Phase 0-2 test results
│   └── TESTING_REFACTOR.md           Testing refactor plan
│
└── archive/                          Historical documentation (reference only)
    ├── search-fixes/                 Archived search-related fix docs (4 files)
    ├── migration-docs/               Archived migration docs (4 files)
    └── [various legacy docs]
```

---

## 🚀 **QUICK REFERENCE**

### **I want to...**

| Goal | Document to Read |
|------|------------------|
| Understand current project state | [CURRENT_STATE.md](CURRENT_STATE.md) |
| Run the project locally | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Run locally (detailed steps) | [LOCAL_RUN_EN.md](LOCAL_RUN_EN.md) |
| Set up Docker | [DOCKER_SETUP.md](DOCKER_SETUP.md) |
| Learn developer conventions | [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) |
| Get a command cheat-sheet | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |
| Start as an AI agent | [START_HERE_AGENT_GUIDE.md](START_HERE_AGENT_GUIDE.md) |
| Choose between Cursor and Claude Code | [AGENT_USAGE_GUIDE.md](AGENT_USAGE_GUIDE.md) |
| Know what MCP tools are available | [TOOL_AVAILABILITY.md](TOOL_AVAILABILITY.md) |
| Understand the future vision | [VISION_GLOBAL_CLIMATE_PLATFORM.md](VISION_GLOBAL_CLIMATE_PLATFORM.md) |
| Write tests | [TESTING_GUIDE.md](TESTING_GUIDE.md) |
| Check platform health | [PLATFORM_HEALTH_CHECK.md](PLATFORM_HEALTH_CHECK.md) |
| Understand architecture decisions | [architecture/](architecture/) |
| Understand domain models | [domain/](domain/) |
| Implement new features | [CURRENT_STATE.md](CURRENT_STATE.md) → [MVP_COMPLETION_PLAN.md](MVP_COMPLETION_PLAN.md) |

---

## 🎓 **FOR AI AGENTS**

If you're an AI agent (Cursor, Claude Code, or Codex):

### **Mandatory Reading (In Order)**

1. **`CURRENT_STATE.md`** - Understand what exists vs what's planned
2. **`../.claude/skills/clilens-development/SKILL.md`** - Domain-specific constraints
3. **`AGENT_USAGE_GUIDE.md`** - Understand your tool's capabilities

### **Critical Rules**

- ✅ **Read CURRENT_STATE.md first** - Know reality vs aspiration
- ❌ **Don't implement Kafka features** - Infrastructure not operational
- ❌ **Don't add mock data fallbacks** - Fail explicitly instead
- ✅ **Update CURRENT_STATE.md** - When you complete features
- ✅ **Follow skill guidelines** - `.claude/skills/clilens-development/SKILL.md`

### **Verification Checklist**

Before marking work as "done":
- [ ] Read `CURRENT_STATE.md` to understand constraints
- [ ] No mock/placeholder code added
- [ ] API keys tested and work
- [ ] Tests pass: `pytest tests/`
- [ ] Frontend tested in browser
- [ ] Error cases handled explicitly
- [ ] Updated `CURRENT_STATE.md` if needed

---

## 📖 **DETAILED DOCUMENTATION**

### **Architecture**

- **[adr-kafka-to-redis-celery.md](architecture/adr-kafka-to-redis-celery.md)** - Architecture decision record
- **[data-model-trust.md](architecture/data-model-trust.md)** - Trust scoring model
- **[compliance-hitl.md](architecture/compliance-hitl.md)** - Human-in-the-loop workflows
- **[DEPLOYMENT.md](architecture/DEPLOYMENT.md)** - Deployment architecture

### **Domain Models**

- **[content.md](domain/content.md)** - Content domain specification
- **[identity.md](domain/identity.md)** - Identity domain specification
- **[ingestion.md](domain/ingestion.md)** - Ingestion domain specification
- **[verification.md](domain/verification.md)** - Verification domain specification

### **Vision & Planning**

- **[MVP_EUROPE_ROADMAP.md](MVP_EUROPE_ROADMAP.md)** - European expansion roadmap
- **[VISION_GLOBAL_CLIMATE_PLATFORM.md](VISION_GLOBAL_CLIMATE_PLATFORM.md)** - Long-term vision
- **[WORKFLOW_AND_UX.md](WORKFLOW_AND_UX.md)** - UX workflows

### **Testing**

- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Main testing guide
- **[testing/TEST_RESULTS_PHASE_0-2.md](testing/TEST_RESULTS_PHASE_0-2.md)** - Test results
- **[testing/TESTING_REFACTOR.md](testing/TESTING_REFACTOR.md)** - Testing refactor plan

### **MCP Servers**

- **[mcp/README.md](mcp/README.md)** - MCP server overview
- **[mcp/postgres.md](mcp/postgres.md)** - PostgreSQL MCP usage
- **[mcp/docker.md](mcp/docker.md)** - Docker MCP usage
- **[mcp/filesystem.md](mcp/filesystem.md)** - Filesystem MCP usage

---

## ⚠️ **ARCHIVED DOCUMENTATION**

Documents in `docs/archive/` are **historical reference only**. They may contain:
- Outdated information
- Completed milestones
- Superseded architectural decisions
- Old completion reports

**Do not** base new development on archived documents. Always refer to the main documentation.

---

## 🔄 **DOCUMENTATION MAINTENANCE**

### **When to Update CURRENT_STATE.md**

- ✅ When completing a feature
- ✅ When discovering a new bug
- ✅ When architecture changes
- ✅ When dependencies change (API keys, services)
- ✅ When moving from "planned" to "operational"

### **When to Archive Documents**

- ✅ When information is outdated
- ✅ When a milestone is completed (completion reports)
- ✅ When superseded by newer documentation
- ❌ **Never archive:** CURRENT_STATE.md, AGENT_USAGE_GUIDE.md, GETTING_STARTED.md

---

## 📞 **NEED HELP?**

### **For Developers**

1. Read `CURRENT_STATE.md` - 90% of questions answered here
2. Check `GETTING_STARTED.md` - For setup issues
3. Review `architecture/` - For design decisions
4. Check `domain/` - For domain model questions

### **For AI Agents**

1. Read `CURRENT_STATE.md` - Understand reality
2. Read `.claude/skills/clilens-development/SKILL.md` - Domain constraints
3. Read `AGENT_USAGE_GUIDE.md` - Tool capabilities
4. Check `TOOL_AVAILABILITY.md` - MCP feature parity

---

## ✅ **QUICK HEALTH CHECK**

Before starting development, verify:

```bash
# 1. Containers running
docker ps
# Should show: clilens-api, clilens-frontend, climatenews-postgres, climatenews-redis

# 2. API works
curl http://localhost:5200/healthz
# Should return: {"status":"ok"}

# 3. Database accessible
docker exec climatenews-postgres pg_isready
# Should return: accepting connections

# 4. Frontend works
curl http://localhost:5300
# Should return: HTML content
```

If any of these fail, see `GETTING_STARTED.md` for troubleshooting.

---

**This README was created as part of the documentation restructuring initiative (December 2025) to reduce confusion and provide clear navigation.**

**Maintained by:** CliLens Development Team
**Last Major Update:** 2026-03-05
**Next Review:** After MVP completion
