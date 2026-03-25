# Claude Code/Flow Templates

Reusable templates for common workflows with automated checkpoint management, agent coordination, and ReasoningBank integration.

## Available Templates

### 1. Checkpoint Refactor (`checkpoint-refactor.json`)

Large-scale refactoring with automatic checkpoint management.

**Usage:**
```bash
# Load template variables
export MODULE_NAME="ingestion"
export PROJECT="climatenews"
export SESSION_ID="refactor-$(date +%Y%m%d-%H%M%S)"
export COVERAGE_TARGET="90"

# Use with Claude Code Task tool
Task("Refactor ingestion module using template",
     "Apply checkpoint-refactor.json template with module_name='$MODULE_NAME', project='$PROJECT', session_id='$SESSION_ID'",
     "hierarchical-coordinator")
```

**Features:**
- Automatic checkpoint creation
- Multi-agent coordination (analyzer, architect, coder, tester, reviewer)
- Agent Booster integration for speed
- ReasoningBank memory storage
- Comprehensive TodoWrite tracking
- Rollback instructions

**Best For:**
- Module refactoring
- Architecture improvements
- Large code changes (>100 lines)
- High-risk modifications

---

### 2. Compliance Sweep (`compliance-sweep.json`)

Automated compliance audit and documentation workflow.

**Usage:**
```bash
# Set variables
export AUDIT_SCOPE="ingestion + orchestration services"
export AUDIT_ID="audit-$(date +%Y%m%d)"
export AUDIT_YEAR="2025q1"
export COMPLIANCE_STANDARD="OWASP Top 10 2025"

# Execute via Claude Code
Task("Run compliance audit using template",
     "Apply compliance-sweep.json with audit_scope='$AUDIT_SCOPE', audit_id='$AUDIT_ID', audit_year='$AUDIT_YEAR'",
     "hierarchical-coordinator")
```

**Features:**
- Security audit automation
- Compliance documentation generation
- Test suite creation (95% coverage target)
- ReasoningBank integration for historical context
- Automated terminal history export

**Best For:**
- Security audits
- Compliance reviews
- Regulatory documentation
- Pre-deployment validation

---

### 3. Documentation Update (`doc-update.json`)

Comprehensive documentation update workflow with automated verification.

**Usage:**
```bash
# Configure
export DOC_SCOPE="ingestion service"
export PROJECT="climatenews"
export DOC_PATH="services/ingestion"
export SESSION_ID="docs-$(date +%Y%m%d-%H%M%S)"

# Run
Task("Update documentation using template",
     "Apply doc-update.json for doc_scope='$DOC_SCOPE', project='$PROJECT', doc_path='$DOC_PATH'",
     "hierarchical-coordinator")
```

**Features:**
- Documentation gap analysis
- API reference generation
- Working code examples
- Review and verification
- ReasoningBank storage

**Best For:**
- API documentation
- User guides
- Architecture docs
- Code examples

---

### 4. Multi-Service Deploy (`multi-service-deploy.json`)

Coordinated deployment workflow for multiple services with validation.

**Usage:**
```bash
# Setup
export SERVICES="ingestion,orchestration,verification"
export ENVIRONMENT="staging"
export PROJECT="climatenews"
export DEPLOY_ID="deploy-$(date +%Y%m%d-%H%M%S)"

# Deploy
Task("Deploy services using template",
     "Apply multi-service-deploy.json with services='$SERVICES', environment='$ENVIRONMENT', deploy_id='$DEPLOY_ID'",
     "hierarchical-coordinator")
```

**Features:**
- Multi-agent deployment coordination
- Security validation
- Integration testing
- Health monitoring
- Automated rollback planning
- Deployment documentation

**Best For:**
- Production deployments
- Staging releases
- Multi-service updates
- Coordinated releases

---

## Template Structure

All templates follow this structure:

```json
{
  "name": "Template Name",
  "description": "What it does",
  "version": "1.0.0",
  "tags": ["tag1", "tag2"],
  "workflow": {
    "preTask": ["bash commands to run before"],
    "agents": [
      {
        "type": "agent-type",
        "name": "Agent Name",
        "task": "What the agent should do",
        "memoryKey": "reasoningbank://context/key",
        "checkpoint": true,
        "hooks": ["post-edit", "notify"]
      }
    ],
    "postTask": ["bash commands to run after"]
  },
  "variables": {
    "var_name": {
      "type": "string",
      "required": true,
      "description": "What this variable controls"
    }
  },
  "todos": [
    {
      "id": "task-1",
      "content": "Task description",
      "status": "pending",
      "priority": "high"
    }
  ],
  "checkpoints": {
    "auto": true,
    "labels": ["checkpoint names"],
    "rollback_instructions": "How to rollback"
  }
}
```

---

## Creating Custom Templates

### Step 1: Copy Base Template

```bash
cp .claude/templates/checkpoint-refactor.json .claude/templates/my-template.json
```

### Step 2: Customize Variables

Update the `variables` section with your needed parameters:

```json
"variables": {
  "my_param": {
    "type": "string",
    "required": true,
    "description": "Description of parameter"
  }
}
```

### Step 3: Define Agent Workflow

Add/modify agents in the `agents` array:

```json
{
  "type": "coder",
  "name": "Implementation Agent",
  "task": "Implement {{my_param}} feature",
  "memoryKey": "reasoningbank://myproject/{{my_param}}",
  "checkpoint": true
}
```

### Step 4: Configure TodoWrite

Add todos for tracking:

```json
"todos": [
  {
    "id": "custom-1",
    "content": "My custom task",
    "status": "pending",
    "priority": "high"
  }
]
```

### Step 5: Test Template

```bash
# Validate JSON
jq '.' .claude/templates/my-template.json

# Test with Task tool
Task("Test my custom template",
     "Apply my-template.json with my_param='test-value'",
     "planner")
```

---

## Best Practices

### 1. Variable Naming
- Use lowercase with underscores: `module_name`
- Be descriptive: `audit_scope` not just `scope`
- Include defaults where reasonable

### 2. Agent Coordination
- Always specify `memoryKey` for ReasoningBank
- Enable checkpoints for high-risk operations
- Use hooks for real-time coordination
- Include `activeForm` in todos for better UX

### 3. Pre/Post Tasks
- Always include `git status` in preTask
- Run tests in postTask
- Update ReasoningBank in postTask
- Export metrics for tracking

### 4. Error Handling
- Include rollback instructions
- Document recovery procedures
- Test failure scenarios
- Validate prerequisites

### 5. Documentation
- Clear description and purpose
- Example usage commands
- Variable documentation
- Prerequisites listed

---

## Integration with Automation Scripts

Templates work seamlessly with automation scripts:

### Checkpoint Manager
```bash
# Auto-create checkpoints based on template risk level
scripts/automation/checkpoint-manager.sh auto-label refactor
```

### ReasoningBank Sync
```bash
# Sync template execution results
scripts/automation/sync-reasoningbank.sh sync-refactoring $SESSION_ID $MODULE_NAME
```

### Vectal Sync
```bash
# Import todos from template
scripts/automation/sync-vectal-todos.sh create-batch .claude/templates/my-template.json
```

### Metrics Tracking
```bash
# Log template usage
scripts/automation/metrics-dashboard.sh log my-template session-123 success
```

---

## Template Versioning

Templates follow semantic versioning:

- **Major (X.0.0):** Breaking changes to template structure
- **Minor (0.X.0):** New features, backward compatible
- **Patch (0.0.X):** Bug fixes, documentation updates

Update template version when modifying:

```json
{
  "name": "My Template",
  "version": "1.2.0",
  ...
}
```

---

## Troubleshooting

### Template Not Loading
```bash
# Validate JSON syntax
jq '.' .claude/templates/my-template.json

# Check file permissions
ls -la .claude/templates/
```

### Variables Not Expanding
- Ensure variables are defined in template
- Use correct syntax: `{{variable_name}}`
- Export variables before execution

### Agents Not Spawning
- Verify agent types exist (see CLAUDE.md for list)
- Check MCP server connection
- Review Claude Code Task tool syntax

### ReasoningBank Connection Issues
```bash
# Test connection
npx claude-flow@alpha memory connect --provider reasoningbank --context test

# Check credentials
cat .claude/settings.json | jq '.reasoningbank'
```

---

## Examples

See `docs/examples/template-usage/` for complete examples:

- `refactor-example.md` - Complete refactoring workflow
- `compliance-example.md` - Security audit walkthrough
- `deployment-example.md` - Multi-service deployment
- `custom-template.md` - Creating custom templates

---

## Contributing

To contribute new templates:

1. Create template in `.claude/templates/`
2. Add documentation section above
3. Include usage examples
4. Test thoroughly
5. Update version number
6. Submit for review

---

## Support

For questions or issues:
- Check `CLAUDE.md` for main documentation
- Review `docs/CLAUDE_CODE_FLOW_SUMMARY.md` for features
- See `docs/operations/GUARDRAILS.md` for safety procedures
- Open issue in project repository

---

**Last Updated:** 2025-01-XX
**Template Version:** 1.0.0
