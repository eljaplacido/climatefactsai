# Testing Guide - Claude Code/Flow Platform

Complete testing guide for all features, templates, automation scripts, and integrations.

**Last Updated:** 2025-01-XX

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Setup](#environment-setup)
3. [Running Tests](#running-tests)
4. [Testing Scenarios](#testing-scenarios)
5. [Manual Testing](#manual-testing)
6. [UX Testing](#ux-testing)
7. [Performance Testing](#performance-testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### One-Command Setup

```bash
# Run automated setup
./scripts/automation/setup-test-env.sh

# Run all tests
npm test
pytest tests/integration/test_templates.py -v
./tests/integration/test_automation_scripts.sh all
```

### Prerequisites

```bash
# Install dependencies
npm install
pip install -r requirements.txt

# Install Claude Flow (if not installed)
npm install -g claude-flow@alpha

# Verify installation
npx claude-flow@alpha --version
```

---

## Environment Setup

### 1. Configuration Files

**Create test environment variables:**

```bash
# Copy example env
cp .env.example .env.test

# Edit test configuration
cat > .env.test <<EOF
# Test Environment Configuration
CLAUDE_FLOW_ENV=test
CLAUDE_FLOW_LOG_LEVEL=debug

# Optional: ReasoningBank (for memory tests)
CLAUDE_FLOW_REASONINGBANK_KEY=test-key

# Optional: Metrics tracking
CLAUDE_FLOW_METRICS_ENABLED=true

# Optional: OpenRouter proxy (for cost tracking tests)
OPENROUTER_API_KEY=test-key
CLAUDE_FLOW_ROUTER=openrouter
EOF
```

### 2. Test Directories

```bash
# Create test directory structure
mkdir -p tests/{data,output,reports}
mkdir -p .claude/memory/{test-checkpoints,test-metrics,test-todos}
mkdir -p docs/metrics/test
```

### 3. Sample Data

Test data is automatically created in `tests/data/`:
- `sample-vectal-tasks.json` - PM tool task data
- Test configuration in `tests/test_config.json`

---

## Running Tests

### Python Template Tests

```bash
# Run all template tests
pytest tests/integration/test_templates.py -v

# Run specific test class
pytest tests/integration/test_templates.py::TestTemplateStructure -v

# Run with coverage
pytest tests/integration/test_templates.py --cov=.claude/templates --cov-report=html

# Generate report
pytest tests/integration/test_templates.py --html=tests/reports/template-tests.html
```

### Bash Automation Tests

```bash
# Run all automation tests
./tests/integration/test_automation_scripts.sh all

# Setup test environment only
./tests/integration/test_automation_scripts.sh setup

# Cleanup test environment
./tests/integration/test_automation_scripts.sh cleanup

# View test log
cat .claude/terminal/history/test-automation-*.log
```

### Integration Tests

```bash
# Run all integration tests
npm test

# Run specific test suite
npm test -- --grep "checkpoint"
```

---

## Testing Scenarios

### Scenario 1: Refactoring Workflow

**Goal:** Test complete refactoring workflow with checkpoints

```bash
# 1. Set variables
export MODULE_NAME="test_ingestion"
export SESSION_ID="test-refactor-$(date +%Y%m%d-%H%M%S)"
export PROJECT="climatenews"
export COVERAGE_TARGET="90"

# 2. Create checkpoint
./scripts/automation/checkpoint-manager.sh create pre-refactor "Before test refactoring" high

# 3. List checkpoints
./scripts/automation/checkpoint-manager.sh list

# 4. Generate rollback instructions
CHECKPOINT_ID=$(./scripts/automation/checkpoint-manager.sh list | head -1 | awk '{print $1}')
./scripts/automation/checkpoint-manager.sh rollback-instructions $CHECKPOINT_ID

# 5. Verify output
cat .claude/memory/checkpoints/rollback-$CHECKPOINT_ID.md
```

**Expected Results:**
- ✅ Checkpoint created in `.claude/memory/checkpoints/`
- ✅ Metadata JSON file exists
- ✅ Rollback instructions generated
- ✅ Git commit captured

### Scenario 2: ReasoningBank Sync

**Goal:** Test memory synchronization

```bash
# 1. Connect to ReasoningBank
./scripts/automation/sync-reasoningbank.sh connect climatenews/test "test,demo"

# 2. Create test file
mkdir -p tests/output
echo "# Test Documentation" > tests/output/test-doc.md
echo "This is a test document for ReasoningBank sync." >> tests/output/test-doc.md

# 3. Push to ReasoningBank
./scripts/automation/sync-reasoningbank.sh push climatenews/test tests/output/test-doc.md 0.90 "Test sync"

# 4. Verify push
cat .claude/memory/reasoningbank/push-test-doc.json

# 5. Fetch from ReasoningBank
./scripts/automation/sync-reasoningbank.sh fetch climatenews/test "test" tests/output/fetched.json
```

**Expected Results:**
- ✅ Connection successful
- ✅ Push metadata created
- ✅ Fetch returns data

### Scenario 3: Vectal Todo Sync

**Goal:** Test PM tool integration

```bash
# 1. Import sample tasks
./scripts/automation/sync-vectal-todos.sh import tests/data/sample-vectal-tasks.json sprint-2025q1

# 2. Create TodoWrite batch
./scripts/automation/sync-vectal-todos.sh create-batch tests/data/sample-vectal-tasks.json tests/output/todo-batch.json

# 3. Verify batch structure
cat tests/output/todo-batch.json | jq '.todos[]'

# 4. Update task status
./scripts/automation/sync-vectal-todos.sh sync-status T-001 completed "Test completion"

# 5. Generate report
./scripts/automation/sync-vectal-todos.sh report sprint-2025q1 tests/reports/sprint-report.md

# 6. View report
cat tests/reports/sprint-report.md
```

**Expected Results:**
- ✅ Tasks imported successfully
- ✅ TodoWrite batch created with valid JSON
- ✅ Task status updated
- ✅ Sprint report generated

### Scenario 4: Metrics Dashboard

**Goal:** Test metrics tracking and dashboard generation

```bash
# 1. Log feature usage
./scripts/automation/metrics-dashboard.sh log checkpoints test-session-001 used "Testing checkpoint feature"
./scripts/automation/metrics-dashboard.sh log agent-booster test-session-001 used "Testing Agent Booster"
./scripts/automation/metrics-dashboard.sh log reasoningbank test-session-001 used "Testing ReasoningBank"

# 2. Log Agent Booster metrics
./scripts/automation/metrics-dashboard.sh log-booster success 5 45

# 3. Generate adoption metrics
./scripts/automation/metrics-dashboard.sh adoption tests/output/adoption-metrics.json

# 4. View metrics
cat tests/output/adoption-metrics.json | jq '.'

# 5. Generate HTML dashboard
./scripts/automation/metrics-dashboard.sh dashboard tests/output/dashboard.html

# 6. Open dashboard
# Windows: start tests/output/dashboard.html
# Mac: open tests/output/dashboard.html
# Linux: xdg-open tests/output/dashboard.html
```

**Expected Results:**
- ✅ Usage logged to `.claude/memory/metrics/usage.jsonl`
- ✅ Adoption metrics JSON created
- ✅ HTML dashboard generated
- ✅ Dashboard displays metrics correctly

### Scenario 5: Template Validation

**Goal:** Validate all templates are properly structured

```bash
# 1. Run Python tests
pytest tests/integration/test_templates.py::TestTemplateStructure -v

# 2. Validate JSON syntax
for template in .claude/templates/*.json; do
    echo "Validating $template..."
    jq '.' "$template" > /dev/null && echo "✓ Valid" || echo "✗ Invalid"
done

# 3. Check template variables
pytest tests/integration/test_templates.py::TestTemplateValidation::test_variable_references -v

# 4. Verify agent types
pytest tests/integration/test_templates.py::TestTemplateAgentTypes -v
```

**Expected Results:**
- ✅ All templates have valid JSON
- ✅ All required fields present
- ✅ Variable references match definitions
- ✅ Agent types are valid

---

## Manual Testing

### Testing Templates with Claude Code

#### Test Refactoring Template

```javascript
// In Claude Code session
Task("Test refactoring workflow",
     "Apply checkpoint-refactor.json template with module_name='test_module', session_id='test-001', project='climatenews', coverage_target=90. This is a test run to validate the template structure and agent coordination.",
     "planner")
```

**What to Verify:**
- ✅ Template loads successfully
- ✅ Variables are substituted correctly
- ✅ Agents spawn in correct order
- ✅ TodoWrite items appear
- ✅ Checkpoints are created
- ✅ Pre/post tasks execute

#### Test Compliance Template

```javascript
Task("Test compliance workflow",
     "Apply compliance-sweep.json with audit_scope='test services', audit_id='test-audit-001', audit_year='2025q1', compliance_standard='OWASP Top 10 2025'. This is a test to validate compliance automation.",
     "planner")
```

### Testing Automation Scripts

#### Interactive Testing

```bash
# Start interactive session
bash

# Test checkpoint creation interactively
./scripts/automation/checkpoint-manager.sh create test-manual "Manual test checkpoint" medium

# Check result
ls -la .claude/memory/checkpoints/

# Test rollback generation
LATEST_CP=$(./scripts/automation/checkpoint-manager.sh list | head -1 | awk '{print $1}')
./scripts/automation/checkpoint-manager.sh rollback-instructions $LATEST_CP

# View instructions
cat .claude/memory/checkpoints/rollback-$LATEST_CP.md
```

---

## UX Testing

### Dashboard UX Test

**Goal:** Evaluate metrics dashboard usability

```bash
# Generate dashboard with sample data
./scripts/automation/metrics-dashboard.sh log checkpoints test-ux used "UX Test 1"
./scripts/automation/metrics-dashboard.sh log subagents test-ux used "UX Test 2"
./scripts/automation/metrics-dashboard.sh log agent-booster test-ux used "UX Test 3"
./scripts/automation/metrics-dashboard.sh log-booster success 10 120

./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/ux-test-dashboard.html
```

**UX Evaluation Checklist:**
- [ ] Dashboard loads in <2 seconds
- [ ] All metrics visible without scrolling
- [ ] Color scheme is readable
- [ ] Charts/graphs are clear
- [ ] Mobile responsive
- [ ] Data refreshes correctly
- [ ] Export functionality works

### Template UX Test

**Template Selection Process:**

```bash
# 1. User wants to refactor
echo "I want to refactor the ingestion module"

# 2. View available templates
ls -la .claude/templates/*.json
cat .claude/templates/README.md | grep "## Available Templates" -A 30

# 3. Read template documentation
cat .claude/templates/README.md | grep "checkpoint-refactor" -A 20

# 4. Understand variables needed
cat .claude/templates/checkpoint-refactor.json | jq '.variables'

# 5. Execute template
# (Via Claude Code Task tool)
```

**UX Evaluation Checklist:**
- [ ] Templates easy to discover
- [ ] Documentation clear and complete
- [ ] Variable requirements obvious
- [ ] Examples are helpful
- [ ] Error messages are clear
- [ ] Success feedback is visible

### Script UX Test

**Command-Line Experience:**

```bash
# Test help system
./scripts/automation/checkpoint-manager.sh help
./scripts/automation/sync-reasoningbank.sh help
./scripts/automation/sync-vectal-todos.sh help
./scripts/automation/metrics-dashboard.sh help

# Test error handling
./scripts/automation/checkpoint-manager.sh invalid-command
./scripts/automation/sync-reasoningbank.sh push
```

**UX Evaluation Checklist:**
- [ ] Help text is comprehensive
- [ ] Commands are intuitive
- [ ] Error messages are helpful
- [ ] Output is formatted well
- [ ] Progress indicators work
- [ ] Logs are accessible

---

## Performance Testing

### Template Performance

```bash
# Measure template loading time
time cat .claude/templates/checkpoint-refactor.json | jq '.'

# Measure variable substitution
time echo '{"module_name": "test"}' | jq '.module_name'
```

**Performance Targets:**
- Template load: <100ms
- JSON parsing: <50ms
- Variable substitution: <10ms

### Script Performance

```bash
# Measure checkpoint creation time
time ./scripts/automation/checkpoint-manager.sh create perf-test "Performance test" medium

# Measure metrics logging
time ./scripts/automation/metrics-dashboard.sh log test-feature test-session used "Perf test"

# Measure dashboard generation
time ./scripts/automation/metrics-dashboard.sh dashboard tests/output/perf-dashboard.html
```

**Performance Targets:**
- Checkpoint creation: <5 seconds
- Metrics logging: <1 second
- Dashboard generation: <3 seconds

### Memory Usage

```bash
# Monitor memory during test
./scripts/automation/metrics-dashboard.sh monitor &
PID=$!
sleep 10
ps aux | grep $PID
kill $PID
```

---

## Troubleshooting

### Common Issues

#### Issue: Template not loading

```bash
# Check JSON syntax
jq '.' .claude/templates/checkpoint-refactor.json

# Verify file permissions
ls -la .claude/templates/

# Check Claude Flow installation
npx claude-flow@alpha --version
```

#### Issue: Script not executable

```bash
# Make scripts executable
chmod +x scripts/automation/*.sh
chmod +x tests/integration/*.sh

# Verify
ls -la scripts/automation/
```

#### Issue: Tests failing

```bash
# Check test environment
./tests/integration/test_automation_scripts.sh setup

# View test logs
cat .claude/terminal/history/test-automation-*.log

# Run with verbose output
pytest tests/integration/test_templates.py -vv
```

#### Issue: Metrics not tracking

```bash
# Check metrics directory
ls -la .claude/memory/metrics/

# View metrics log
cat .claude/memory/metrics/usage.jsonl

# Test logging manually
echo '{"feature":"test","status":"used"}' >> .claude/memory/metrics/usage.jsonl
```

### Debug Mode

```bash
# Enable debug logging
export CLAUDE_FLOW_LOG_LEVEL=debug

# Run with verbose output
./scripts/automation/checkpoint-manager.sh create debug-test "Debug test" medium 2>&1 | tee debug.log

# View detailed logs
cat debug.log
```

---

## Test Reports

### Generate Comprehensive Test Report

```bash
# Create report directory
mkdir -p tests/reports

# Run all tests and capture output
{
    echo "# Test Report - $(date)"
    echo ""
    echo "## Template Tests"
    pytest tests/integration/test_templates.py -v --tb=short
    echo ""
    echo "## Automation Tests"
    ./tests/integration/test_automation_scripts.sh all
    echo ""
    echo "## Performance Metrics"
    ./scripts/automation/metrics-dashboard.sh adoption tests/output/adoption.json
    cat tests/output/adoption.json
} > tests/reports/full-test-report.md

# View report
cat tests/reports/full-test-report.md
```

### Coverage Report

```bash
# Python coverage
pytest tests/integration/test_templates.py --cov=.claude --cov-report=html
open htmlcov/index.html

# Script coverage (manual review)
# Check which scripts have been tested
grep -r "Test:" tests/integration/test_automation_scripts.sh
```

---

## Continuous Testing

### Setup Pre-Commit Hook

```bash
# Create pre-commit hook
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/bash
echo "Running tests before commit..."

# Run template tests
pytest tests/integration/test_templates.py -q || exit 1

# Run automation tests
./tests/integration/test_automation_scripts.sh all || exit 1

echo "All tests passed!"
EOF

chmod +x .git/hooks/pre-commit
```

### Daily Test Schedule

```bash
# Add to crontab (Linux/Mac)
crontab -e

# Add line:
0 2 * * * cd /path/to/climatenews && ./tests/integration/test_automation_scripts.sh all >> tests/reports/daily-$(date +\%Y\%m\%d).log 2>&1
```

---

## Success Criteria

### All Tests Must Pass

- ✅ 18+ automation tests passing
- ✅ Python template tests passing
- ✅ JSON syntax validation passing
- ✅ Script execution tests passing
- ✅ Integration tests passing

### Performance Benchmarks

- ✅ Template load <100ms
- ✅ Checkpoint creation <5s
- ✅ Dashboard generation <3s
- ✅ Metrics logging <1s

### UX Criteria

- ✅ Documentation is clear and complete
- ✅ Error messages are helpful
- ✅ Commands are intuitive
- ✅ Dashboard is responsive
- ✅ Workflow is smooth

---

## Next Steps

After successful testing:

1. **Deploy to Development**
   ```bash
   git add .
   git commit -m "Complete platform implementation with tests"
   git push origin main
   ```

2. **Train Team**
   - Share testing guide
   - Demo templates and scripts
   - Review metrics dashboard

3. **Monitor Adoption**
   ```bash
   # Weekly metrics check
   ./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/weekly-dashboard.html
   ```

4. **Gather Feedback**
   - User surveys
   - Usage analytics
   - Feature requests

---

**Test Environment Ready!** 🎯

All testing infrastructure, scenarios, and guides are complete. Start testing with:

```bash
./tests/integration/test_automation_scripts.sh all
pytest tests/integration/test_templates.py -v
```

For issues, check logs in `.claude/terminal/history/`

