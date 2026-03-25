# Automation Scripts

Automated workflows for checkpoint management, memory synchronization, task integration, and metrics tracking.

## Scripts Overview

| Script | Purpose | Priority |
|--------|---------|----------|
| `checkpoint-manager.sh` | Automated checkpoint creation and management | High |
| `sync-reasoningbank.sh` | ReasoningBank memory synchronization | High |
| `sync-vectal-todos.sh` | Vectal/PM task integration | High |
| `metrics-dashboard.sh` | Metrics tracking and dashboard generation | Medium |

---

## 1. Checkpoint Manager

**File:** `checkpoint-manager.sh`

Automated checkpoint creation, labeling, and rollback management.

### Commands

```bash
# Create manual checkpoint
./scripts/automation/checkpoint-manager.sh create <label> <description> <risk_level>

# Auto-create labeled checkpoint
./scripts/automation/checkpoint-manager.sh auto-label <operation>

# Generate rollback instructions
./scripts/automation/checkpoint-manager.sh rollback-instructions <checkpoint_id>

# Clean old checkpoints
./scripts/automation/checkpoint-manager.sh cleanup [days]

# List all checkpoints
./scripts/automation/checkpoint-manager.sh list
```

### Examples

```bash
# Before refactoring
./scripts/automation/checkpoint-manager.sh create refactor "Before refactoring ingestion module" high

# Auto-checkpoint for deployment
./scripts/automation/checkpoint-manager.sh auto-label deploy

# Generate rollback guide
./scripts/automation/checkpoint-manager.sh rollback-instructions cp-20250101-120000-refactor

# Clean checkpoints older than 14 days
./scripts/automation/checkpoint-manager.sh cleanup 14
```

### Integration with Hooks

Add to `.claude/hooks/pre-task.sh`:

```bash
#!/bin/bash
TASK_DESC="$1"

# Auto-create checkpoint for high-risk operations
if [[ "$TASK_DESC" =~ (refactor|deploy|migration|security) ]]; then
    ./scripts/automation/checkpoint-manager.sh auto-label "$TASK_DESC"
fi
```

---

## 2. ReasoningBank Sync

**File:** `sync-reasoningbank.sh`

Automated memory synchronization with ReasoningBank for persistent context.

### Commands

```bash
# Connect to ReasoningBank
./scripts/automation/sync-reasoningbank.sh connect <context> [labels]

# Fetch memory
./scripts/automation/sync-reasoningbank.sh fetch <context> [labels] [output_file]

# Push memory
./scripts/automation/sync-reasoningbank.sh push <context> <file> [confidence] [summary]

# Sync compliance data
./scripts/automation/sync-reasoningbank.sh sync-compliance <audit_id> [audit_year]

# Sync refactoring decisions
./scripts/automation/sync-reasoningbank.sh sync-refactoring <session_id> <module> [project]

# Sync deployment data
./scripts/automation/sync-reasoningbank.sh sync-deployment <deploy_id> [environment] [project]

# Batch sync
./scripts/automation/sync-reasoningbank.sh batch <config_file>
```

### Examples

```bash
# Connect to compliance context
./scripts/automation/sync-reasoningbank.sh connect compliance/2025q1 "security,audit"

# Push refactoring decisions
./scripts/automation/sync-reasoningbank.sh push climatenews/refactor docs/refactor-analysis.md 0.92 "Analysis of ingestion refactoring"

# Sync compliance audit
./scripts/automation/sync-reasoningbank.sh sync-compliance audit-001 2025q1

# Batch sync from config
cat > sync-config.json <<EOF
[
  {
    "type": "compliance",
    "id": "audit-001",
    "audit_year": "2025q1"
  },
  {
    "type": "refactoring",
    "id": "refactor-20250101",
    "module": "ingestion",
    "project": "climatenews"
  }
]
EOF

./scripts/automation/sync-reasoningbank.sh batch sync-config.json
```

### Integration with Templates

Templates automatically call ReasoningBank sync in `postTask`:

```json
"postTask": [
  "npx claude-flow@alpha memory push --provider reasoningbank --context {{project}}/refactor --confidence 0.90"
]
```

---

## 3. Vectal Todo Sync

**File:** `sync-vectal-todos.sh`

Automated task management integration with Vectal or other PM tools.

### Commands

```bash
# Import from Vectal
./scripts/automation/sync-vectal-todos.sh import [file] [label]

# Export to Vectal
./scripts/automation/sync-vectal-todos.sh export [label] [output_file]

# Update task status
./scripts/automation/sync-vectal-todos.sh sync-status <task_id> <status> [notes]

# Create TodoWrite batch
./scripts/automation/sync-vectal-todos.sh create-batch [vectal_file] [output]

# Bi-directional sync
./scripts/automation/sync-vectal-todos.sh bidirectional [sprint_label]

# Handle webhook
./scripts/automation/sync-vectal-todos.sh webhook <webhook_data>

# Generate report
./scripts/automation/sync-vectal-todos.sh report [sprint_label] [output_file]
```

### Examples

```bash
# Import tasks for sprint
./scripts/automation/sync-vectal-todos.sh import data/tasks/vectal-export.json sprint-2025q1

# Update task status
./scripts/automation/sync-vectal-todos.sh sync-status T-204 completed "Finished implementation"

# Create TodoWrite batch from Vectal
./scripts/automation/sync-vectal-todos.sh create-batch data/tasks/vectal-export.json

# Bi-directional sync
./scripts/automation/sync-vectal-todos.sh bidirectional sprint-2025q1

# Generate sync report
./scripts/automation/sync-vectal-todos.sh report sprint-2025q1 docs/reports/sprint-report.md
```

### Webhook Integration

Set up webhook endpoint to automatically sync task updates:

```bash
# Example webhook handler
curl -X POST http://localhost:3000/vectal-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "T-204",
    "status": "in_progress",
    "title": "Implement ingestion retry logic"
  }' | ./scripts/automation/sync-vectal-todos.sh webhook -
```

---

## 4. Metrics Dashboard

**File:** `metrics-dashboard.sh`

Adoption tracking, cost monitoring, and metrics dashboard generation.

### Commands

```bash
# Log feature usage
./scripts/automation/metrics-dashboard.sh log <feature> [session] [status] [notes]

# Log Agent Booster metrics
./scripts/automation/metrics-dashboard.sh log-booster [result] [files] [duration]

# Track OpenRouter costs
./scripts/automation/metrics-dashboard.sh track-costs [window]

# Generate adoption metrics
./scripts/automation/metrics-dashboard.sh adoption [output_file]

# Generate cost report
./scripts/automation/metrics-dashboard.sh cost-report [output_file]

# Generate HTML dashboard
./scripts/automation/metrics-dashboard.sh dashboard [output_file]

# Generate sprint report
./scripts/automation/metrics-dashboard.sh sprint-report [sprint_label] [output]

# Realtime monitoring
./scripts/automation/metrics-dashboard.sh monitor
```

### Examples

```bash
# Log checkpoint usage
./scripts/automation/metrics-dashboard.sh log checkpoints session-123 used "Pre-refactor checkpoint"

# Log Agent Booster session
./scripts/automation/metrics-dashboard.sh log-booster success 8 120

# Track 30-day costs
./scripts/automation/metrics-dashboard.sh track-costs 30d

# Generate HTML dashboard
./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/dashboard.html

# Generate sprint report
./scripts/automation/metrics-dashboard.sh sprint-report sprint-2025q1

# Live monitoring
./scripts/automation/metrics-dashboard.sh monitor
```

### Integration with Workflows

Add to end of tasks:

```bash
# In postTask hooks
npx claude-flow@alpha metrics log --feature "web-interface" --session climatenews --status used
./scripts/automation/metrics-dashboard.sh log web-interface session-123 success "Documentation update sprint"
```

---

## Automated Workflows

### Complete Refactoring Workflow

```bash
#!/bin/bash
# Complete refactoring with all automation

MODULE="ingestion"
SESSION_ID="refactor-$(date +%Y%m%d-%H%M%S)"

# 1. Create checkpoint
./scripts/automation/checkpoint-manager.sh auto-label refactor

# 2. Connect to ReasoningBank
./scripts/automation/sync-reasoningbank.sh connect climatenews/refactor "refactor,architecture"

# 3. Fetch prior decisions
./scripts/automation/sync-reasoningbank.sh fetch climatenews/refactor "refactor,$MODULE"

# 4. Execute refactoring (using Claude Code Task tool)
Task("Refactor module using template",
     "Apply checkpoint-refactor.json for module_name='$MODULE', session_id='$SESSION_ID'",
     "hierarchical-coordinator")

# 5. Push results to ReasoningBank
./scripts/automation/sync-reasoningbank.sh sync-refactoring "$SESSION_ID" "$MODULE"

# 6. Update task status
./scripts/automation/sync-vectal-todos.sh sync-status "T-204" completed "Refactoring complete"

# 7. Log metrics
./scripts/automation/metrics-dashboard.sh log refactoring "$SESSION_ID" success "Completed $MODULE refactoring"

# 8. Generate rollback instructions
./scripts/automation/checkpoint-manager.sh rollback-instructions "$(./scripts/automation/checkpoint-manager.sh list | grep refactor | head -1 | awk '{print $1}')"
```

### Sprint Automation Workflow

```bash
#!/bin/bash
# Automated sprint workflow

SPRINT="sprint-2025q1"

# 1. Import tasks from PM tool
./scripts/automation/sync-vectal-todos.sh import data/tasks/vectal-export.json "$SPRINT"

# 2. Create TodoWrite batch
./scripts/automation/sync-vectal-todos.sh create-batch data/tasks/vectal-export.json .claude/memory/todos/sprint-batch.json

# 3. Execute sprint tasks
# (Tasks executed via Claude Code Task tool with templates)

# 4. Export completed tasks
./scripts/automation/sync-vectal-todos.sh export "$SPRINT" data/tasks/vectal-completed.json

# 5. Generate sprint report
./scripts/automation/metrics-dashboard.sh sprint-report "$SPRINT" docs/metrics/sprint-$SPRINT-report.md

# 6. Bi-directional sync
./scripts/automation/sync-vectal-todos.sh bidirectional "$SPRINT"
```

---

## Cron Jobs / Scheduled Tasks

### Daily Maintenance

```bash
# Add to crontab
0 2 * * * cd /path/to/project && ./scripts/automation/checkpoint-manager.sh cleanup 30
0 3 * * * cd /path/to/project && ./scripts/automation/metrics-dashboard.sh track-costs 7d
```

### Weekly Reports

```bash
# Generate weekly dashboard
0 9 * * 1 cd /path/to/project && ./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/dashboard-$(date +\%Y-\%U).html
```

### Sprint Sync

```bash
# Bi-directional sync every 4 hours during sprint
0 */4 * * * cd /path/to/project && ./scripts/automation/sync-vectal-todos.sh bidirectional sprint-2025q1
```

---

## Configuration

### Environment Variables

```bash
# .env or export in shell
export CLAUDE_FLOW_REASONINGBANK_KEY="your-key"
export CLAUDE_FLOW_VECTAL_API_KEY="your-vectal-key"
export CLAUDE_FLOW_METRICS_ENABLED="true"
```

### Script Configuration

Edit variables at top of each script:

```bash
# checkpoint-manager.sh
CHECKPOINT_DIR=".claude/checkpoints"
MEMORY_DIR=".claude/memory/checkpoints"
LOG_FILE=".claude/terminal/history/checkpoint-manager.log"
```

---

## Troubleshooting

### Permission Errors

```bash
# Make scripts executable
chmod +x scripts/automation/*.sh

# Check file ownership
ls -la scripts/automation/
```

### Command Not Found

```bash
# Ensure dependencies installed
npm install -g claude-flow@alpha

# Check PATH
echo $PATH | grep node_modules
```

### Log Files

All scripts log to `.claude/terminal/history/`:

```bash
# View checkpoint manager logs
tail -f .claude/terminal/history/checkpoint-manager.log

# View ReasoningBank logs
tail -f .claude/terminal/history/reasoningbank-sync.log

# View metrics logs
tail -f .claude/terminal/history/metrics-dashboard.log
```

---

## Best Practices

1. **Always test in dev first** - Test automation scripts in development before production
2. **Use checkpoints for safety** - Create checkpoints before running automation
3. **Monitor logs** - Tail log files during script execution
4. **Version control configs** - Commit automation configs to git
5. **Document customizations** - Add comments to modified scripts
6. **Regular cleanup** - Run checkpoint cleanup weekly
7. **Validate outputs** - Check generated files before committing

---

## Contributing

To add new automation scripts:

1. Create script in `scripts/automation/`
2. Follow existing naming convention
3. Add comprehensive help text
4. Include logging functionality
5. Document in this README
6. Add examples
7. Test thoroughly

---

## Support

For issues or questions:
- Check script help: `./script-name.sh help`
- Review logs in `.claude/terminal/history/`
- See main documentation: `CLAUDE.md`
- Open issue in repository

---

**Last Updated:** 2025-01-XX
**Scripts Version:** 1.0.0
