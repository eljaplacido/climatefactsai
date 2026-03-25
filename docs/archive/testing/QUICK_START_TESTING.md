# Quick Start Testing Guide

**Get started testing the Claude Code/Flow platform in 5 minutes!**

---

## 🚀 One-Command Setup

```bash
# Run automated setup
./scripts/automation/setup-test-env.sh
```

This will:
- ✅ Check prerequisites (Node.js, Python, jq)
- ✅ Install dependencies (pytest, Claude Flow)
- ✅ Create directory structure
- ✅ Generate sample data
- ✅ Validate templates and scripts
- ✅ Run quick tests
- ✅ Generate metrics dashboard

---

## 📊 View Metrics Dashboard

**Option 1: Enhanced Dashboard (Recommended)**
```bash
# Open in browser
open docs/metrics/enhanced-dashboard.html

# Windows
start docs/metrics/enhanced-dashboard.html

# Linux
xdg-open docs/metrics/enhanced-dashboard.html
```

**Option 2: Generate Fresh Dashboard**
```bash
./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/live-dashboard.html
open docs/metrics/live-dashboard.html
```

---

## ✅ Run Tests

### Quick Test (2 minutes)
```bash
# Run all automated tests
./tests/integration/test_automation_scripts.sh all
```

### Comprehensive Test (5 minutes)
```bash
# Python template tests
pytest tests/integration/test_templates.py -v

# Bash automation tests
./tests/integration/test_automation_scripts.sh all

# View results
cat .claude/terminal/history/test-automation-*.log
```

---

## 🎯 Test Scenarios

### Scenario 1: Checkpoint Creation (30 seconds)
```bash
# Create a test checkpoint
./scripts/automation/checkpoint-manager.sh create test-1 "My first test checkpoint" medium

# List all checkpoints
./scripts/automation/checkpoint-manager.sh list

# Generate rollback instructions
./scripts/automation/checkpoint-manager.sh rollback-instructions $(./scripts/automation/checkpoint-manager.sh list | head -1 | awk '{print $1}')
```

**Expected Output:**
- Checkpoint created in `.claude/memory/checkpoints/`
- Rollback instructions in `.claude/memory/checkpoints/rollback-*.md`

### Scenario 2: Metrics Tracking (30 seconds)
```bash
# Log some test usage
./scripts/automation/metrics-dashboard.sh log checkpoints test-session used "Testing checkpoints"
./scripts/automation/metrics-dashboard.sh log agent-booster test-session used "Testing booster"

# View metrics
./scripts/automation/metrics-dashboard.sh adoption .claude/memory/metrics/test-adoption.json
cat .claude/memory/metrics/test-adoption.json | jq '.'

# Generate dashboard
./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/test-metrics.html
```

**Expected Output:**
- Metrics logged to `.claude/memory/metrics/usage.jsonl`
- Dashboard generated with current data

### Scenario 3: Vectal Todo Sync (1 minute)
```bash
# Import test tasks
./scripts/automation/sync-vectal-todos.sh import tests/data/sample-vectal-tasks.json sprint-test

# Create TodoWrite batch
./scripts/automation/sync-vectal-todos.sh create-batch tests/data/sample-vectal-tasks.json tests/output/todos.json

# View batch
cat tests/output/todos.json | jq '.todos[]'

# Update task status
./scripts/automation/sync-vectal-todos.sh sync-status T-001 completed "Test completed"

# Generate report
./scripts/automation/sync-vectal-todos.sh report sprint-test tests/output/sprint-report.md
cat tests/output/sprint-report.md
```

**Expected Output:**
- Tasks imported successfully
- TodoWrite batch created with valid structure
- Sprint report generated

---

## 🎨 UX Testing

### Test 1: Dashboard UX (2 minutes)

**Open:** `docs/metrics/enhanced-dashboard.html`

**Evaluate:**
- [ ] Dashboard loads in <2 seconds
- [ ] All 8 metric cards visible
- [ ] Charts render correctly
- [ ] Feature cards show data
- [ ] Refresh button works
- [ ] Mobile responsive
- [ ] Color scheme is readable

### Test 2: Template Discovery (3 minutes)

**Steps:**
1. List templates: `ls .claude/templates/`
2. Read README: `cat .claude/templates/README.md`
3. View specific template: `cat .claude/templates/checkpoint-refactor.json | jq '.'`
4. Check variables: `cat .claude/templates/checkpoint-refactor.json | jq '.variables'`

**Evaluate:**
- [ ] Templates easy to find
- [ ] Documentation is clear
- [ ] Variables are documented
- [ ] Examples are helpful
- [ ] Purpose is obvious

### Test 3: Script Usability (3 minutes)

**Test each script:**
```bash
./scripts/automation/checkpoint-manager.sh help
./scripts/automation/sync-reasoningbank.sh help
./scripts/automation/sync-vectal-todos.sh help
./scripts/automation/metrics-dashboard.sh help
```

**Evaluate:**
- [ ] Help text is comprehensive
- [ ] Commands are intuitive
- [ ] Examples are provided
- [ ] Error messages are helpful
- [ ] Output is well-formatted

---

## 📝 Manual Testing with Templates

### Test Refactoring Template

```javascript
// In Claude Code
Task("Test refactoring template",
     "Apply checkpoint-refactor.json with module_name='test_module', session_id='test-001', project='climatenews', coverage_target=90. This is a validation test.",
     "planner")
```

**What to Check:**
- [ ] Template loads without errors
- [ ] Variables are replaced correctly
- [ ] Todos appear in list
- [ ] Checkpoints are created
- [ ] Agent coordination works
- [ ] Pre/post tasks execute

### Test Compliance Template

```javascript
Task("Test compliance template",
     "Apply compliance-sweep.json with audit_scope='test services', audit_id='test-001', audit_year='2025q1'. This is a validation test.",
     "planner")
```

**What to Check:**
- [ ] Security agent spawns
- [ ] Documentation is generated
- [ ] Tests are created
- [ ] ReasoningBank sync works
- [ ] Reports are produced

---

## 🔍 Validation Checklist

### Files & Structure
- [ ] All templates exist in `.claude/templates/`
- [ ] All scripts exist in `scripts/automation/`
- [ ] Documentation in `docs/`
- [ ] Test files in `tests/`
- [ ] Directory structure complete

### Functionality
- [ ] Templates have valid JSON
- [ ] Scripts are executable
- [ ] Tests pass successfully
- [ ] Metrics track correctly
- [ ] Dashboard generates

### Documentation
- [ ] CLAUDE.md is up to date
- [ ] Templates README is clear
- [ ] Scripts README is complete
- [ ] Testing guide is helpful
- [ ] Operational guardrails documented

---

## 🐛 Troubleshooting

### Issue: Setup script fails

```bash
# Check Node.js
node --version

# Check Python
python3 --version

# Check jq
jq --version

# Re-run setup with verbose output
bash -x ./scripts/automation/setup-test-env.sh
```

### Issue: Tests not passing

```bash
# Check test environment
ls -la tests/integration/

# Make scripts executable
chmod +x scripts/automation/*.sh
chmod +x tests/integration/*.sh

# Run tests individually
pytest tests/integration/test_templates.py::TestTemplateStructure -v
```

### Issue: Dashboard not loading

```bash
# Check metrics file
cat .claude/memory/metrics/current-adoption.json | jq '.'

# Regenerate dashboard
./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/new-dashboard.html

# Open with full path
open "$(pwd)/docs/metrics/enhanced-dashboard.html"
```

### Issue: Script permissions

```bash
# Fix all permissions
chmod +x scripts/automation/*.sh
chmod +x tests/integration/*.sh

# Verify
ls -la scripts/automation/
ls -la tests/integration/
```

---

## 📊 Test Results

### Success Criteria

**All Green:**
- ✅ 18+ automated tests passing
- ✅ All templates validate successfully
- ✅ All scripts execute without errors
- ✅ Dashboard generates with data
- ✅ Documentation is complete

**Ready for Production:**
- ✅ Performance metrics meet targets
- ✅ UX evaluation passes
- ✅ All workflows tested
- ✅ Error handling works
- ✅ Rollback procedures verified

---

## 🎉 Next Steps After Testing

### If All Tests Pass:

1. **Review Results**
   ```bash
   cat tests/reports/full-test-report.md
   cat .claude/memory/setup-log.txt
   ```

2. **Share Dashboard**
   ```bash
   # Send dashboard to team
   # docs/metrics/enhanced-dashboard.html
   ```

3. **Document Findings**
   ```bash
   # Create test report
   cp tests/reports/full-test-report.md docs/TEST_RESULTS_$(date +%Y%m%d).md
   ```

4. **Deploy to Development**
   ```bash
   git add .
   git commit -m "Complete platform with validated tests"
   git push origin main
   ```

5. **Train Team**
   - Share testing guide
   - Demo features
   - Review workflows
   - Answer questions

### If Issues Found:

1. **Review Logs**
   ```bash
   cat .claude/terminal/history/test-automation-*.log
   cat .test-output.log
   ```

2. **Check Prerequisites**
   ```bash
   ./scripts/automation/setup-test-env.sh
   ```

3. **Run Individual Tests**
   ```bash
   pytest tests/integration/test_templates.py -vv
   ./tests/integration/test_automation_scripts.sh setup
   ```

4. **Report Issues**
   - Document error messages
   - Include log files
   - Describe expected vs actual behavior

---

## 📚 Additional Resources

- **Full Testing Guide:** `docs/TESTING_GUIDE.md`
- **Template Documentation:** `.claude/templates/README.md`
- **Script Documentation:** `scripts/automation/README.md`
- **Platform Completion Report:** `docs/PLATFORM_COMPLETION_REPORT.md`
- **Main Configuration:** `CLAUDE.md`

---

## ⚡ Quick Commands Reference

```bash
# Setup
./scripts/automation/setup-test-env.sh

# Run all tests
./tests/integration/test_automation_scripts.sh all
pytest tests/integration/test_templates.py -v

# View dashboard
open docs/metrics/enhanced-dashboard.html

# Check logs
cat .claude/terminal/history/test-automation-*.log

# Test checkpoints
./scripts/automation/checkpoint-manager.sh list

# Test metrics
./scripts/automation/metrics-dashboard.sh adoption .claude/memory/metrics/test.json

# Test todos
./scripts/automation/sync-vectal-todos.sh import tests/data/sample-vectal-tasks.json sprint-test

# Help
./scripts/automation/checkpoint-manager.sh help
./scripts/automation/sync-reasoningbank.sh help
./scripts/automation/sync-vectal-todos.sh help
./scripts/automation/metrics-dashboard.sh help
```

---

**⏱️ Total Quick Start Time: ~5-10 minutes**

**✅ You're ready to test the platform!**

Start with the one-command setup, then run through the test scenarios. The enhanced dashboard provides real-time visualization of all metrics.

For detailed testing, see `docs/TESTING_GUIDE.md`

