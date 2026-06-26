# Claude Code Configuration - SPARC Development Environment

> ⚠️ **Scope note (audit AGSK-01):** The sections below describing the
> claude-flow ecosystem — ReasoningBank Core Memory, AgentDB, Agent Booster, the
> OpenRouter proxy, Flow-Nexus, and the 54-agent / hive-mind tooling — are
> **aspirational developer-tooling notes, NOT wired into this product.** The
> shipping app is a Python (FastAPI) + Next.js climate platform; its real agentic
> layer is the intelligence domain (`src/backend/app/domains/intelligence/`) plus
> the 22-action `SKILLS_REGISTRY`. Do NOT write application code against
> ReasoningBank / AgentDB / OpenRouter APIs — they do not exist in this repo. For
> ground truth see `.claude/skills/clilens-development/SKILL.md` and
> `docs/CURRENT_STATE.md`.

## 🚨 CRITICAL: CONCURRENT EXECUTION & FILE MANAGEMENT

**ABSOLUTE RULES**:
1. ALL operations MUST be concurrent/parallel in a single message
2. **NEVER save working files, text/mds and tests to the root folder**
3. ALWAYS organize files in appropriate subdirectories
4. **USE CLAUDE CODE'S TASK TOOL** for spawning agents concurrently, not just MCP

### ⚡ GOLDEN RULE: "1 MESSAGE = ALL RELATED OPERATIONS"

**MANDATORY PATTERNS:**
- **TodoWrite**: ALWAYS batch ALL todos in ONE call (5-10+ todos minimum)
- **Task tool (Claude Code)**: ALWAYS spawn ALL agents in ONE message with full instructions
- **File operations**: ALWAYS batch ALL reads/writes/edits in ONE message
- **Bash commands**: ALWAYS batch ALL terminal operations in ONE message
- **Memory operations**: ALWAYS batch ALL memory store/retrieve in ONE message

### 🎯 CRITICAL: Claude Code Task Tool for Agent Execution

**Claude Code's Task tool is the PRIMARY way to spawn agents:**
```javascript
// ✅ CORRECT: Use Claude Code's Task tool for parallel agent execution
[Single Message]:
  Task("Research agent", "Analyze requirements and patterns...", "researcher")
  Task("Coder agent", "Implement core features...", "coder")
  Task("Tester agent", "Create comprehensive tests...", "tester")
  Task("Reviewer agent", "Review code quality...", "reviewer")
  Task("Architect agent", "Design system architecture...", "system-architect")
```

**MCP tools are ONLY for coordination setup:**
- `mcp__claude-flow__swarm_init` - Initialize coordination topology
- `mcp__claude-flow__agent_spawn` - Define agent types for coordination
- `mcp__claude-flow__task_orchestrate` - Orchestrate high-level workflows

### 📁 File Organization Rules

**NEVER save to root folder. Use these directories:**
- `/src` - Source code files
- `/tests` - Test files
- `/docs` - Documentation and markdown files
- `/config` - Configuration files
- `/scripts` - Utility scripts
- `/examples` - Example code

## Project Overview

This project uses SPARC (Specification, Pseudocode, Architecture, Refinement, Completion) methodology with Claude-Flow orchestration for systematic Test-Driven Development.

## SPARC Commands

### Core Commands
- `npx claude-flow sparc modes` - List available modes
- `npx claude-flow sparc run <mode> "<task>"` - Execute specific mode
- `npx claude-flow sparc tdd "<feature>"` - Run complete TDD workflow
- `npx claude-flow sparc info <mode>` - Get mode details

### Batchtools Commands
- `npx claude-flow sparc batch <modes> "<task>"` - Parallel execution
- `npx claude-flow sparc pipeline "<task>"` - Full pipeline processing
- `npx claude-flow sparc concurrent <mode> "<tasks-file>"` - Multi-task processing

### Build Commands
- `cd src/frontend && npm run build` - Build frontend
- `cd src/frontend && npm run test` - Run frontend tests
- `cd src/frontend && npm run lint` - Linting
- `cd src/frontend && npm run typecheck` - Type checking
- `pytest tests/` - Run backend tests
- `docker compose -f docker-compose.simple.yml up` - Start platform locally

## SPARC Workflow Phases

1. **Specification** - Requirements analysis (`sparc run spec-pseudocode`)
2. **Pseudocode** - Algorithm design (`sparc run spec-pseudocode`)
3. **Architecture** - System design (`sparc run architect`)
4. **Refinement** - TDD implementation (`sparc tdd`)
5. **Completion** - Integration (`sparc run integration`)

## Code Style & Best Practices

- **Modular Design**: Files under 500 lines
- **Environment Safety**: Never hardcode secrets
- **Test-First**: Write tests before implementation
- **Clean Architecture**: Separate concerns
- **Documentation**: Keep updated

## 🚀 Available Agents (54 Total)

### Core Development
`coder`, `reviewer`, `tester`, `planner`, `researcher`

### Swarm Coordination
`hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`, `collective-intelligence-coordinator`, `swarm-memory-manager`

### Consensus & Distributed
`byzantine-coordinator`, `raft-manager`, `gossip-coordinator`, `consensus-builder`, `crdt-synchronizer`, `quorum-manager`, `security-manager`

### Performance & Optimization
`perf-analyzer`, `performance-benchmarker`, `task-orchestrator`, `memory-coordinator`, `smart-agent`

### GitHub & Repository
`github-modes`, `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`, `workflow-automation`, `project-board-sync`, `repo-architect`, `multi-repo-swarm`

### SPARC Methodology
`sparc-coord`, `sparc-coder`, `specification`, `pseudocode`, `architecture`, `refinement`

### Specialized Development
`backend-dev`, `mobile-dev`, `ml-developer`, `cicd-engineer`, `api-docs`, `system-architect`, `code-analyzer`, `base-template-generator`

### Testing & Validation
`tdd-london-swarm`, `production-validator`

### Migration & Planning
`migration-planner`, `swarm-init`

## 🎯 Claude Code vs MCP Tools

### Claude Code Handles ALL EXECUTION:
- **Task tool**: Spawn and run agents concurrently for actual work
- File operations (Read, Write, Edit, MultiEdit, Glob, Grep)
- Code generation and programming
- Bash commands and system operations
- Implementation work
- Project navigation and analysis
- TodoWrite and task management
- Git operations
- Package management
- Testing and debugging

### MCP Tools ONLY COORDINATE:
- Swarm initialization (topology setup)
- Agent type definitions (coordination patterns)
- Task orchestration (high-level planning)
- Memory management
- Neural features
- Performance tracking
- GitHub integration

**KEY**: MCP coordinates the strategy, Claude Code's Task tool executes with real agents.

## 🚀 Quick Setup

```bash
# Add MCP servers (Claude Flow required, others optional)
claude mcp add claude-flow npx claude-flow@alpha mcp start
claude mcp add ruv-swarm npx ruv-swarm mcp start  # Optional: Enhanced coordination
claude mcp add flow-nexus npx flow-nexus@latest mcp start  # Optional: Cloud features
```

## MCP Tool Categories

### Coordination
`swarm_init`, `agent_spawn`, `task_orchestrate`

### Monitoring
`swarm_status`, `agent_list`, `agent_metrics`, `task_status`, `task_results`

### Memory & Neural
`memory_usage`, `neural_status`, `neural_train`, `neural_patterns`

### GitHub Integration
`github_swarm`, `repo_analyze`, `pr_enhance`, `issue_triage`, `code_review`

### System
`benchmark_run`, `features_detect`, `swarm_monitor`

### Flow-Nexus MCP Tools (Optional Advanced Features)
Flow-Nexus extends MCP capabilities with 70+ cloud-based orchestration tools:

**Key MCP Tool Categories:**
- **Swarm & Agents**: `swarm_init`, `swarm_scale`, `agent_spawn`, `task_orchestrate`
- **Sandboxes**: `sandbox_create`, `sandbox_execute`, `sandbox_upload` (cloud execution)
- **Templates**: `template_list`, `template_deploy` (pre-built project templates)
- **Neural AI**: `neural_train`, `neural_patterns`, `seraphina_chat` (AI assistant)
- **GitHub**: `github_repo_analyze`, `github_pr_manage` (repository management)
- **Real-time**: `execution_stream_subscribe`, `realtime_subscribe` (live monitoring)
- **Storage**: `storage_upload`, `storage_list` (cloud file management)

**Authentication Required:**
- Register: `mcp__flow-nexus__user_register` or `npx flow-nexus@latest register`
- Login: `mcp__flow-nexus__user_login` or `npx flow-nexus@latest login`
- Access 70+ specialized MCP tools for advanced orchestration

## 🚀 Agent Execution Flow with Claude Code

### The Correct Pattern:

1. **Optional**: Use MCP tools to set up coordination topology
2. **REQUIRED**: Use Claude Code's Task tool to spawn agents that do actual work
3. **REQUIRED**: Each agent runs hooks for coordination
4. **REQUIRED**: Batch all operations in single messages

### Example Full-Stack Development:

```javascript
// Single message with all agent spawning via Claude Code's Task tool
[Parallel Agent Execution]:
  Task("Backend Developer", "Build REST API with Express. Use hooks for coordination.", "backend-dev")
  Task("Frontend Developer", "Create React UI. Coordinate with backend via memory.", "coder")
  Task("Database Architect", "Design PostgreSQL schema. Store schema in memory.", "code-analyzer")
  Task("Test Engineer", "Write Jest tests. Check memory for API contracts.", "tester")
  Task("DevOps Engineer", "Setup Docker and CI/CD. Document in memory.", "cicd-engineer")
  Task("Security Auditor", "Review authentication. Report findings via hooks.", "reviewer")
  
  // All todos batched together
  TodoWrite { todos: [...8-10 todos...] }
  
  // All file operations together
  Write "backend/server.js"
  Write "frontend/App.jsx"
  Write "database/schema.sql"
```

## 📋 Agent Coordination Protocol

### Every Agent Spawned via Task Tool MUST:

**1️⃣ BEFORE Work:**
```bash
npx claude-flow@alpha hooks pre-task --description "[task]"
npx claude-flow@alpha hooks session-restore --session-id "swarm-[id]"
```

**2️⃣ DURING Work:**
```bash
npx claude-flow@alpha hooks post-edit --file "[file]" --memory-key "swarm/[agent]/[step]"
npx claude-flow@alpha hooks notify --message "[what was done]"
```

**3️⃣ AFTER Work:**
```bash
npx claude-flow@alpha hooks post-task --task-id "[task]"
npx claude-flow@alpha hooks session-end --export-metrics true
```

### Checkpoints Integration

**Checkpoints are automatically enabled** (see `.claude/settings.json`):
- Automatic saves before each code change
- Instant rollback capability via checkpoint system
- Checkpoint directory: `.claude/checkpoints/`
- Use checkpoints for complex refactoring or experimental changes

### Subagents Pattern

**Subagents** enable modular, task-specific workflows:
```javascript
// Create specialized subagent for specific task
Task("Security Subagent", "Review authentication code for vulnerabilities", "security-manager", {
  context: "authentication-module",
  tools: ["code-analyzer", "security-scanner"],
  prompt: "Focus on OAuth2 and JWT implementation"
})

Task("Testing Subagent", "Generate comprehensive test suite", "tester", {
  context: "api-endpoints",
  coverage: "90%",
  framework: "pytest"
})
```

**Benefits:**
- Independent context per subagent
- Specialized tool access
- Modular workflow composition
- Reduced token usage through focused contexts

### VS Code Extension Workflow

**Setup**
1. Install the Claude Code VS Code extension (Flow-Nexus release channel).
2. Open `clilens.code-workspace` so every service/doc folder stays mounted.
3. Run the command palette action `Claude Code: Connect Workspace` and point it at this repo root.
4. Sign in with the same credentials configured in `.claude/settings.json` so checkpoints and hooks stay in sync.

**Live Usage**
- Use `Claude Code: Spawn Agents` to issue a single batched instruction set; the extension forwards the one-message payload directly to the Task tool.
- Inline diff mode mirrors checkpoints; every edit is pre-saved to `.claude/checkpoints/` so VS Code rollbacks match CLI rollbacks.
- The Claude panel exposes TodoWrite batching and hook triggers, so keep todos, Bash commands, and file edits grouped just like the CLI flow.

```javascript
Task("VS Code Extension Session", "Parallel refactor of ingestion + docs with checkpoints enabled.", "coder", {
  workspace: "clilens.code-workspace",
  editor: "vscode",
  checkpoint: true,
  hooks: ["post-edit", "notify"]
})
TodoWrite { todos: [
  {id: "vs-1", content: "Refactor ingestion service adapters", status: "in_progress"},
  {id: "vs-2", content: "Sync docs after refactor", status: "pending"}
] }
```

**Tips**
- Keep the VS Code Claude terminal pinned; it shows hook output plus checkpoint IDs for quick rollback.
- Use multi-root search to pre-load context before running a Task; this cuts down on extension token usage.
- Rely on VS Code tasks (`Run Tests`, `Start All Services`, etc.) from `clilens.code-workspace` to keep tooling identical between CLI and extension.

### ReasoningBank Core Memory Workflow

**Connect**
```bash
npx claude-flow@alpha memory connect --provider reasoningbank --context "codex/climatenews"
npx claude-flow@alpha memory sync --context "codex/climatenews" --labels "sprint-2025q1,refactor"
```

**Usage Pattern**
- Tag each Task with a `memoryKey` (e.g., `reasoningbank://climatenews/refactor-ingestion`) so decisions get anchored.
- Before coding, run `memory fetch` to pull prior architectural choices and open todos; load those into the Task instruction payload.
- After coding, call `memory push` with summaries + file lists so ReasoningBank can surface them in future sessions with confidence scores.

```javascript
Task("API Hardening", "Harden ingestion endpoints; replay prior security decisions from ReasoningBank.", "security-manager", {
  memoryKey: "reasoningbank://climatenews/security/ingestion",
  recall: ["auth-policy", "rate-limits"],
  checkpoint: true
})
Bash "npx claude-flow@alpha memory push --provider reasoningbank --context codex/climatenews --file docs/security/hardening.md --confidence 0.92"
```

**Best Practices**
- Keep contexts narrow (service/module level) so semantic search stays precise.
- Store conclusions, not logs—ReasoningBank rewards short summaries plus the file references needed for replay.
- Use the reported confidence score to decide whether to treat suggestions as hints or requirements.

### Agent Booster Usage Pattern

**When to Enable**
- Bulk or repetitive edits across multiple directories.
- Large refactors where diff previews are critical.
- Tight feedback loops (tests, lint, formatting) that need faster round-trips.

**Activation**
```bash
npx claude-flow@alpha agent-booster enable --task "ingestion-refactor" --diff-preview true --autosave true
```

```javascript
Task("Agent Booster Refactor", "Update ingestion + orchestration services and regenerate tests.", "coder", {
  agentBooster: {
    mode: "turbo",
    diffPreview: true,
    autosave: true
  },
  hooks: ["post-edit", "notify"]
})
```

**Tips**
- Pair Agent Booster with checkpoints to keep rollback parity.
- Keep each Task under 10 files so diff previews stay readable; spawn subagents if scope grows.
- Run tests right after Booster sessions using the VS Code tasks or CLI to verify changes before checkpoint promotion.

### OpenRouter Proxy Configuration

**Why**: Routes Claude Flow traffic through OpenRouter for 85-98% cost savings while keeping Claude Code as the execution engine.

**Setup**
1. Add the API key to `.env` (and `.env.example` if you want to document the variable):
   ```env
   OPENROUTER_API_KEY=sk-or-***
   CLAUDE_FLOW_ROUTER=openrouter
   ```
2. Mirror the router flag inside `.claude/settings.json` if you want it enforced for every session.
3. Prime credentials before running tasks:
   ```bash
   npx claude-flow@alpha proxy use openrouter --model claude-3.5-sonnet --region global
   ```

**Usage**
- The proxy auto-falls back to Anthropic if OpenRouter is unavailable; check the CLI status line for the active route.
- Keep long-running tasks on OpenRouter, but fall back to Anthropic for latency-sensitive swarms if needed.
- Track savings via `npx claude-flow@alpha proxy metrics --window 7d` and store results in `.claude/memory/costs.json`.

**Best Practices**
- Rotate keys the same time you rotate Anthropic keys; store them in the existing secret manager.
- Gate new projects through the proxy by default unless compliance says otherwise.
- Document any router overrides inside the Task instruction payload so reviewers know which provider executed the change set.

### Web Interface Workflow

**Access**
1. Browse to the Flow-Nexus web portal and choose **Claude Code Workspace**.
2. Authenticate with the same org SSO used for CLI sessions; approve repo access for `climatenews`.
3. Select the `clilens.code-workspace` template so folder mappings mirror the IDE/CLI setup.
4. Enable **Checkpoint Sync** when prompted to ensure `.claude/checkpoints/` stays consistent.

**Usage**
- Use the sidebar Task composer to batch agents/TodoWrite/Bash exactly like the CLI; every submission becomes a single Task tool payload.
- Files are edited through the browser diff view; checkpoints trigger automatically before each save, and rollbacks are shared with VS Code/CLI.
- The metrics panel surfaces the same status line and proxy routing info from `.claude/settings.json`.

```javascript
Task("Web Workspace Sprint", "Implement ingestion updates directly from the browser IDE.", "hierarchical-coordinator", {
  interface: "web",
  workspace: "clilens.code-workspace",
  checkpoint: true,
  hooks: ["post-edit", "notify"]
})
Bash "npx claude-flow@alpha web status --workspace clilens.code-workspace"
```

**Tips**
- Keep the browser workspace limited to one concurrent swarm to avoid context conflicts with VS Code sessions.
- Use the built-in Todo board to drag/drop TodoWrite items; syncing pushes changes back to `.claude/memory/todos.json`.
- Export transcripts after each web session so ReasoningBank receives the same summary artifacts as CLI runs.

### Enhanced Terminal Workflow

**Launch**
```bash
npx claude-flow@alpha terminal open --session climatenews --history on --status-line true
npx claude-flow@alpha terminal attach --session climatenews --checkpoint-stream true
```

**Features**
- `Ctrl+K` opens searchable prompt history; reuse entire batched commands without retyping.
- `status` command shows active agents, checkpoint IDs, proxy routing, and hook activity in one view.
- `history export --since 2h` writes searchable logs to `.claude/terminal/history/*.log` for audit trails.

**Flow**
1. Launch the enhanced terminal before spawning agents so every Task inherits the same session metadata.
2. Use `prompt search "<keyword>"` to find prior Task payloads and rerun them with updated parameters.
3. Trigger checkpoints manually with `checkpoint create --label "pre-migration"` during risky refactors.

### Multi-Agent Collaboration 2025 Pattern

```javascript
Task("Compliance Swarm", "Audit ingestion + orchestration against 2025 guidelines.", "hierarchical-coordinator", {
  agents: [
    {name: "Security Lead", type: "security-manager", hooks: ["post-edit", "notify"], reasoningBank: "security/2025"},
    {name: "Documentation Subagent", type: "api-docs", context: "docs/compliance"},
    {name: "Testing Subagent", type: "tester", coverage: "95%", framework: "pytest"},
    {name: "Deployment Reviewer", type: "cicd-engineer", hooks: ["post-edit"]}
  ],
  checkpoint: true,
  hooks: ["pre-task", "post-task"]
})
TodoWrite { todos: [
  {id: "comp-1", content: "Review auth flows", status: "in_progress"},
  {id: "comp-2", content: "Document findings in docs/compliance/report.md", status: "pending"}
] }
```

**Guidelines**
- Assign each specialist a scoped context (service folder or doc path) so prompts stay focused.
- Share ReasoningBank keys across the swarm (`reasoningbank://compliance/2025`) to reuse historical audits.
- Capture every agent decision with `hooks notify` so the enhanced terminal + ReasoningBank stay synchronized.

### Automated Compliance & Documentation Playbook

1. **Kickoff**
   - Create a checkpoint and run `npx claude-flow@alpha memory fetch --context compliance/2025`.
   - Spawn Security + Reviewer subagents with shared `memoryKey`.
2. **Execution**
   - Security subagent inspects code and writes findings to `docs/compliance/security.md`.
   - Documentation subagent summarizes changes and updates `docs/CHANGELOG.md`.
   - Testing subagent regenerates proof artifacts under `tests/compliance/`.
3. **Closeout**
   - Push summaries back to ReasoningBank with confidence scores.
   - Export enhanced-terminal history for the audit trail.
   - Update TodoWrite items to `done` and link to relevant files in the content field.

### Task Management Integration

**Vectal / PM Sync**
1. Export sprint tasks to `data/tasks/vectal-export.json`.
2. Run `npx claude-flow@alpha todos import --file data/tasks/vectal-export.json --label sprint-2025q1`.
3. Batch TodoWrite updates alongside Task instructions so every automation run keeps PM tools aligned.

```javascript
Task("Sprint Sync", "Implement tasks T-204 to T-210 and sync status back to Vectal.", "planner", {
  todoSource: "data/tasks/vectal-export.json",
  notifyChannel: "vectal-sync",
  checkpoint: true
})
TodoWrite { todos: [
  {id: "T-204", content: "Implement ingestion retry logic", status: "in_progress", link: "vectal://T-204"},
  {id: "T-205", content: "Update compliance docs", status: "pending", link: "vectal://T-205"}
] }
```

**Best Practices**
- Keep Todo IDs identical to external task IDs so updates can be mirrored automatically.
- Store sync logs under `.claude/memory/task-sync/` for auditing.
- When closing Todos, run `npx claude-flow@alpha todos export --label sprint-2025q1 --format vectal` to push results back.

### Adoption & Metrics Tracking

**Log Usage**
```bash
npx claude-flow@alpha metrics log --feature "web-interface" --session climatenews --status used --notes "Docs update sprint"
npx claude-flow@alpha metrics log --feature "agent-booster" --result success --files 8 --duration 12m
```

**Storage**
- Metrics are stored in `.claude/memory/metrics.json`; replicate to ReasoningBank weekly for long-term analytics.
- Include proxy cost savings via `npx claude-flow@alpha proxy metrics --window 7d --output .claude/memory/costs.json`.

**Reporting**
- Add a Todo item for “Metrics review” each sprint and link to the exported report.
- Reference usage metrics in pull requests to show which advanced workflows were exercised.

## 🎯 Concurrent Execution Examples

### ✅ CORRECT WORKFLOW: MCP Coordinates, Claude Code Executes

```javascript
// Step 1: MCP tools set up coordination (optional, for complex tasks)
[Single Message - Coordination Setup]:
  mcp__claude-flow__swarm_init { topology: "mesh", maxAgents: 6 }
  mcp__claude-flow__agent_spawn { type: "researcher" }
  mcp__claude-flow__agent_spawn { type: "coder" }
  mcp__claude-flow__agent_spawn { type: "tester" }

// Step 2: Claude Code Task tool spawns ACTUAL agents that do the work
[Single Message - Parallel Agent Execution]:
  // Claude Code's Task tool spawns real agents concurrently
  Task("Research agent", "Analyze API requirements and best practices. Check memory for prior decisions.", "researcher")
  Task("Coder agent", "Implement REST endpoints with authentication. Coordinate via hooks.", "coder")
  Task("Database agent", "Design and implement database schema. Store decisions in memory.", "code-analyzer")
  Task("Tester agent", "Create comprehensive test suite with 90% coverage.", "tester")
  Task("Reviewer agent", "Review code quality and security. Document findings.", "reviewer")
  
  // Batch ALL todos in ONE call
  TodoWrite { todos: [
    {id: "1", content: "Research API patterns", status: "in_progress", priority: "high"},
    {id: "2", content: "Design database schema", status: "in_progress", priority: "high"},
    {id: "3", content: "Implement authentication", status: "pending", priority: "high"},
    {id: "4", content: "Build REST endpoints", status: "pending", priority: "high"},
    {id: "5", content: "Write unit tests", status: "pending", priority: "medium"},
    {id: "6", content: "Integration tests", status: "pending", priority: "medium"},
    {id: "7", content: "API documentation", status: "pending", priority: "low"},
    {id: "8", content: "Performance optimization", status: "pending", priority: "low"}
  ]}
  
  // Parallel file operations
  Bash "mkdir -p app/{src,tests,docs,config}"
  Write "app/package.json"
  Write "app/src/server.js"
  Write "app/tests/server.test.js"
  Write "app/docs/API.md"
```

### ❌ WRONG (Multiple Messages):
```javascript
Message 1: mcp__claude-flow__swarm_init
Message 2: Task("agent 1")
Message 3: TodoWrite { todos: [single todo] }
Message 4: Write "file.js"
// This breaks parallel coordination!
```

## Performance Benefits

- **84.8% SWE-Bench solve rate**
- **32.3% token reduction**
- **2.8-4.4x speed improvement**
- **27+ neural models**

## Hooks Integration

### Pre-Operation
- Auto-assign agents by file type
- Validate commands for safety
- Prepare resources automatically
- Optimize topology by complexity
- Cache searches

### Post-Operation
- Auto-format code
- Train neural patterns
- Update memory
- Analyze performance
- Track token usage

### Session Management
- Generate summaries
- Persist state
- Track metrics
- Restore context
- Export workflows

## Advanced Features (v2.0.0+)

### Core Features
- 🚀 Automatic Topology Selection
- ⚡ Parallel Execution (2.8-4.4x speed)
- 🧠 Neural Training
- 📊 Bottleneck Analysis
- 🤖 Smart Auto-Spawning
- 🛡️ Self-Healing Workflows
- 💾 Cross-Session Memory
- 🔗 GitHub Integration

### Latest Developments (2025)

#### Claude Code Enhancements
- **VS Code Extension**: Native extension with real-time code modifications, inline diffs, and dedicated sidebar
- **Checkpoints System**: Automatic code state saves before each change, enabling instant rollback to previous versions
- **Subagents**: Independent, task-specific AI agents with their own context, tools, and prompts for modular workflows
- **Web-Based Interface**: Access Claude Code via web portal, linking directly to GitHub repositories
- **Enhanced Terminal**: Improved status visibility and searchable prompt history

#### Claude Flow v2.0+ Improvements
- **Claude Agent SDK Integration**: Transitioned to Anthropic's production-ready primitives
  - 50% code reduction
  - 30% performance improvement
  - Significantly faster memory operations
- **ReasoningBank Core Memory**: AI-powered learning system with semantic search and confidence scoring
  - 46% faster execution
  - 88% success rate
- **Agent Booster**: Ultra-fast code editing (352x faster than traditional LLM APIs at no additional cost)
- **OpenRouter Proxy**: Cost optimization feature offering 85-98% savings on API calls

#### Multi-Agent Collaboration
- Specialized agents for distinct roles (testing, documentation, deployment, security)
- Automated compliance and security checks
- AI-powered testing and validation tools
- Integration with task management tools (Vectal, etc.)

## Integration Tips

1. Start with basic swarm init
2. Scale agents gradually
3. Use memory for context
4. Monitor progress regularly
5. Train patterns from success
6. Enable hooks automation
7. Use GitHub tools first

## Support

- Documentation: https://github.com/ruvnet/claude-flow
- Issues: https://github.com/ruvnet/claude-flow/issues
- Flow-Nexus Platform: https://flow-nexus.ruv.io (registration required for cloud features)

---

Remember: **Claude Flow coordinates, Claude Code creates!**

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
Never save working files, text/mds and tests to the root folder.
