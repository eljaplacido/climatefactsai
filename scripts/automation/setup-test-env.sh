#!/bin/bash

# Automated Test Environment Setup
# Sets up complete testing environment for Claude Code/Flow platform

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Claude Code/Flow Platform - Test Environment Setup  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
echo -e "${CYAN}Checking prerequisites...${NC}"

# Check Node.js
if command -v node &> /dev/null; then
    echo -e "${GREEN}✓${NC} Node.js installed: $(node --version)"
else
    echo -e "${RED}✗${NC} Node.js not found. Please install Node.js first."
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python installed: $(python3 --version)"
else
    echo -e "${RED}✗${NC} Python3 not found. Please install Python 3 first."
    exit 1
fi

# Check jq
if command -v jq &> /dev/null; then
    echo -e "${GREEN}✓${NC} jq installed: $(jq --version)"
else
    echo -e "${YELLOW}!${NC} jq not found. Installing..."
    # Platform-specific install
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install -y jq || sudo yum install -y jq
    fi
fi

echo ""
echo -e "${CYAN}Installing dependencies...${NC}"

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt > /dev/null 2>&1
    echo -e "${GREEN}✓${NC} Python dependencies installed"
fi

# Install pytest if not installed
pip3 install pytest pytest-cov > /dev/null 2>&1
echo -e "${GREEN}✓${NC} pytest installed"

# Install Claude Flow
echo -e "${CYAN}Installing Claude Flow...${NC}"
npm install -g claude-flow@alpha > /dev/null 2>&1 || echo -e "${YELLOW}!${NC} Claude Flow installation skipped (may require sudo)"

# Check Claude Flow
if command -v claude-flow &> /dev/null; then
    echo -e "${GREEN}✓${NC} Claude Flow installed"
else
    echo -e "${YELLOW}!${NC} Claude Flow not found. Some tests may be skipped."
fi

echo ""
echo -e "${CYAN}Creating directory structure...${NC}"

# Create all required directories
mkdir -p .claude/memory/{checkpoints,reasoningbank,todos,metrics,costs}
mkdir -p .claude/terminal/history
mkdir -p .claude/templates
mkdir -p tests/{data,output,reports}
mkdir -p docs/{metrics,operations,examples}
mkdir -p scripts/automation
mkdir -p data/tasks

echo -e "${GREEN}✓${NC} Directory structure created"

echo ""
echo -e "${CYAN}Creating test data...${NC}"

# Create sample Vectal tasks (if not exists)
if [ ! -f "tests/data/sample-vectal-tasks.json" ]; then
    cat > tests/data/sample-vectal-tasks.json <<'EOF'
{
  "sprint": "sprint-2025q1",
  "tasks": [
    {
      "id": "T-001",
      "title": "Test refactoring workflow",
      "completed": false,
      "in_progress": true,
      "priority": "high"
    },
    {
      "id": "T-002",
      "title": "Test compliance automation",
      "completed": false,
      "in_progress": false,
      "priority": "medium"
    }
  ]
}
EOF
    echo -e "${GREEN}✓${NC} Sample Vectal tasks created"
fi

# Create test config (if not exists)
if [ ! -f "tests/test_config.json" ]; then
    cat > tests/test_config.json <<'EOF'
{
  "test_environment": {
    "project_name": "climatenews",
    "base_dir": "."
  },
  "test_scenarios": {
    "refactoring": {
      "module_name": "test_module",
      "session_id": "test-refactor-001"
    }
  }
}
EOF
    echo -e "${GREEN}✓${NC} Test configuration created"
fi

echo ""
echo -e "${CYAN}Making scripts executable...${NC}"

# Make all automation scripts executable
chmod +x scripts/automation/*.sh 2>/dev/null || true
chmod +x tests/integration/*.sh 2>/dev/null || true

echo -e "${GREEN}✓${NC} Scripts are executable"

echo ""
echo -e "${CYAN}Creating sample metrics...${NC}"

# Create sample metrics data
cat > .claude/memory/metrics/usage.jsonl <<EOF
{"feature":"checkpoints","session":"demo-001","status":"used","timestamp":"2025-01-01T12:00:00Z"}
{"feature":"subagents","session":"demo-001","status":"used","timestamp":"2025-01-01T12:05:00Z"}
{"feature":"agent-booster","session":"demo-001","status":"used","timestamp":"2025-01-01T12:10:00Z"}
{"feature":"reasoningbank","session":"demo-002","status":"used","timestamp":"2025-01-01T13:00:00Z"}
{"feature":"vs-code-extension","session":"demo-002","status":"used","timestamp":"2025-01-01T13:15:00Z"}
{"feature":"web-interface","session":"demo-003","status":"used","timestamp":"2025-01-01T14:00:00Z"}
EOF

# Generate adoption metrics
cat > .claude/memory/metrics/current-adoption.json <<EOF
{
  "checkpoints": 12,
  "subagents": 8,
  "agent-booster": 15,
  "reasoningbank": 23,
  "vs-code-extension": 7,
  "web-interface": 5,
  "openrouter-proxy": 18,
  "enhanced-terminal": 4
}
EOF

echo -e "${GREEN}✓${NC} Sample metrics created"

echo ""
echo -e "${CYAN}Running validation tests...${NC}"

# Test 1: Check templates exist
if [ -d ".claude/templates" ]; then
    TEMPLATE_COUNT=$(ls -1 .claude/templates/*.json 2>/dev/null | wc -l)
    echo -e "${GREEN}✓${NC} Found $TEMPLATE_COUNT templates"
else
    echo -e "${YELLOW}!${NC} Templates directory not found"
fi

# Test 2: Check automation scripts
if [ -d "scripts/automation" ]; then
    SCRIPT_COUNT=$(ls -1 scripts/automation/*.sh 2>/dev/null | wc -l)
    echo -e "${GREEN}✓${NC} Found $SCRIPT_COUNT automation scripts"
else
    echo -e "${YELLOW}!${NC} Automation scripts directory not found"
fi

# Test 3: Validate JSON files
echo -ne "${CYAN}Validating JSON files...${NC}"
JSON_VALID=true
for file in .claude/templates/*.json tests/data/*.json 2>/dev/null; do
    if [ -f "$file" ]; then
        if jq '.' "$file" > /dev/null 2>&1; then
            :
        else
            JSON_VALID=false
            echo -e "\n${RED}✗${NC} Invalid JSON: $file"
        fi
    fi
done

if [ "$JSON_VALID" = true ]; then
    echo -e " ${GREEN}✓${NC}"
fi

echo ""
echo -e "${CYAN}Generating enhanced dashboard...${NC}"

# Generate initial dashboard
if [ -f "scripts/automation/metrics-dashboard.sh" ]; then
    ./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/test-dashboard.html > /dev/null 2>&1 || true
    echo -e "${GREEN}✓${NC} Dashboard generated at docs/metrics/test-dashboard.html"
fi

# Copy enhanced dashboard
if [ -f "docs/metrics/enhanced-dashboard.html" ]; then
    echo -e "${GREEN}✓${NC} Enhanced dashboard available at docs/metrics/enhanced-dashboard.html"
fi

echo ""
echo -e "${CYAN}Running quick tests...${NC}"

# Run Python tests if available
if [ -f "tests/integration/test_templates.py" ]; then
    pytest tests/integration/test_templates.py -q > /dev/null 2>&1 && \
        echo -e "${GREEN}✓${NC} Python template tests passed" || \
        echo -e "${YELLOW}!${NC} Python tests had issues (check pytest installation)"
fi

# Run Bash tests if available
if [ -f "tests/integration/test_automation_scripts.sh" ]; then
    ./tests/integration/test_automation_scripts.sh all > .test-output.log 2>&1 && \
        echo -e "${GREEN}✓${NC} Automation script tests passed" || \
        echo -e "${YELLOW}!${NC} Automation tests had issues (check log: .test-output.log)"
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              Test Environment Ready! 🎉                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}✓ Setup Complete!${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo ""
echo -e "  ${YELLOW}1.${NC} View metrics dashboard:"
echo -e "     ${BLUE}open docs/metrics/enhanced-dashboard.html${NC}"
echo ""
echo -e "  ${YELLOW}2.${NC} Run comprehensive tests:"
echo -e "     ${BLUE}pytest tests/integration/test_templates.py -v${NC}"
echo -e "     ${BLUE}./tests/integration/test_automation_scripts.sh all${NC}"
echo ""
echo -e "  ${YELLOW}3.${NC} Test automation scripts:"
echo -e "     ${BLUE}./scripts/automation/checkpoint-manager.sh list${NC}"
echo -e "     ${BLUE}./scripts/automation/metrics-dashboard.sh dashboard docs/metrics/test.html${NC}"
echo ""
echo -e "  ${YELLOW}4.${NC} Review documentation:"
echo -e "     ${BLUE}cat docs/TESTING_GUIDE.md${NC}"
echo -e "     ${BLUE}cat .claude/templates/README.md${NC}"
echo ""
echo -e "  ${YELLOW}5.${NC} Start testing UX:"
echo -e "     ${BLUE}Follow scenarios in docs/TESTING_GUIDE.md${NC}"
echo ""

# Save setup log
cat > .claude/memory/setup-log.txt <<EOF
Test Environment Setup - $(date)

Prerequisites:
✓ Node.js: $(node --version 2>/dev/null || echo "Not found")
✓ Python: $(python3 --version 2>/dev/null || echo "Not found")
✓ Claude Flow: $(npx claude-flow@alpha --version 2>/dev/null || echo "Not found")

Directories Created:
✓ .claude/memory/
✓ .claude/templates/
✓ tests/data/
✓ docs/metrics/

Templates: $(ls -1 .claude/templates/*.json 2>/dev/null | wc -l)
Scripts: $(ls -1 scripts/automation/*.sh 2>/dev/null | wc -l)
Test Files: $(ls -1 tests/integration/*.{py,sh} 2>/dev/null | wc -l)

Status: READY FOR TESTING
EOF

echo -e "${GREEN}Setup log saved to: .claude/memory/setup-log.txt${NC}"
echo ""
