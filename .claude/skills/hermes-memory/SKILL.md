---
name: Hermes Memory & Source of Truth
description: Recursive long-term memory agent for storing project history, lessons learned, insights, and acting as a blueprint for agentic workflows.
version: 1.0.0
author: opencode
tags: [memory, coordination, long-term, source-of-truth, hermes]
---

# Hermes Memory Agent

Hermes serves as the recursive long-term memory and source of truth for the project. It ensures that no architectural decision, lesson learned, or critical insight is lost across agentic sessions, acting as the foundational blueprint for all workflows.

## 🎯 When to Use
- **Post-Task Debriefing**: At the end of a significant feature implementation or refactor to record lessons learned.
- **Workflow Initialization**: When starting a new major task to retrieve the project blueprint and architectural context.
- **Recursive Scanning**: During periodic syncs (e.g., end of sprint/day) to recursively scan the codebase and update the source of truth to match the latest reality.
- **Incident Post-Mortems**: When a critical bug is resolved to document the root cause and prevention strategy.

## 🧠 Core Workflows

### 1. The Blueprint Synchronization (Periodic Scan)
Hermes should be invoked periodically to scan for undocumented changes and update the source of truth.

```javascript
Task("Hermes Sync", "Scan recent commits and updated files to extract new features and architectural changes. Update the project blueprint.", "researcher", {
  memoryKey: "hermes://blueprint/sync",
  hooks: ["post-task"]
})
```

### 2. Memory Ingestion (Recording Insights)
After completing a task, invoke Hermes to distill and store the progress.

```bash
npx claude-flow@alpha memory push --provider reasoningbank --context "hermes/lessons-learned" --file docs/hermes/lessons_learned.md --confidence 0.95
```

### 3. Context Retrieval (Blueprint Provisioning)
Before a new agent begins work, it should consult Hermes to pull the latest conventions.

```bash
npx claude-flow@alpha memory fetch --context "hermes/blueprint"
```

## 📁 Directory Structure
Hermes maintains its physical markdown records in the `docs/hermes` directory:
- `docs/hermes/blueprint.md` - The current state of the system, architecture, and core agent instructions.
- `docs/hermes/lessons_learned.md` - Historical log of bugs, refactoring insights, and decisions.

## 🔄 Recursive Memory Protocol
When Hermes is activated to "scan and update", it follows this protocol:
1. **Read**: Hermes reads the existing `blueprint.md` and `lessons_learned.md`.
2. **Scan**: Hermes uses codebase search tools to check recently modified files and structural changes.
3. **Synthesize**: Hermes identifies discrepancies between the code and the current blueprint.
4. **Update**: Hermes rewrites the blueprint and logs new insights, ensuring continuous alignment.
