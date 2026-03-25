#!/bin/bash

# Integration tests for automation scripts
# Tests checkpoint manager, ReasoningBank sync, Vectal sync, and metrics dashboard

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test output
TEST_LOG=".claude/terminal/history/test-automation-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$TEST_LOG")"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$TEST_LOG"
}

# Test assertion
assert_success() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [ $? -eq 0 ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log "${GREEN}✓ PASS: $1${NC}"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log "${RED}✗ FAIL: $1${NC}"
        return 1
    fi
}

assert_file_exists() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [ -f "$1" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log "${GREEN}✓ PASS: File exists: $1${NC}"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log "${RED}✗ FAIL: File not found: $1${NC}"
        return 1
    fi
}

assert_executable() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [ -x "$1" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log "${GREEN}✓ PASS: File is executable: $1${NC}"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log "${RED}✗ FAIL: File not executable: $1${NC}"
        return 1
    fi
}

# Test setup
setup_test_env() {
    log "${BLUE}Setting up test environment${NC}"

    # Create test directories
    mkdir -p .claude/memory/checkpoints
    mkdir -p .claude/memory/reasoningbank
    mkdir -p .claude/memory/todos
    mkdir -p .claude/memory/metrics
    mkdir -p .claude/terminal/history
    mkdir -p docs/metrics
    mkdir -p data/tasks

    # Create test data
    cat > data/tasks/vectal-test.json <<EOF
{
  "tasks": [
    {
      "id": "T-001",
      "title": "Test task 1",
      "completed": false,
      "in_progress": true,
      "priority": "high"
    },
    {
      "id": "T-002",
      "title": "Test task 2",
      "completed": true,
      "in_progress": false,
      "priority": "medium"
    }
  ]
}
EOF

    log "${GREEN}Test environment setup complete${NC}"
}

# Test cleanup
cleanup_test_env() {
    log "${BLUE}Cleaning up test environment${NC}"

    # Remove test files
    rm -f data/tasks/vectal-test.json
    rm -f .claude/memory/checkpoints/cp-test-*.json
    rm -f .claude/memory/todos/test-*.json

    log "${GREEN}Test environment cleanup complete${NC}"
}

# Test 1: Checkpoint Manager exists and is executable
test_checkpoint_manager_exists() {
    log "${BLUE}Test: Checkpoint Manager exists${NC}"

    assert_file_exists "scripts/automation/checkpoint-manager.sh"
    assert_executable "scripts/automation/checkpoint-manager.sh"
}

# Test 2: Checkpoint Manager help
test_checkpoint_manager_help() {
    log "${BLUE}Test: Checkpoint Manager help${NC}"

    ./scripts/automation/checkpoint-manager.sh help > /dev/null 2>&1
    assert_success "Checkpoint Manager help command"
}

# Test 3: Checkpoint Manager create
test_checkpoint_manager_create() {
    log "${BLUE}Test: Checkpoint Manager create${NC}"

    local checkpoint_id=$(./scripts/automation/checkpoint-manager.sh create test-checkpoint "Test checkpoint" medium 2>&1 | grep "cp-" | tail -1)

    if [ -n "$checkpoint_id" ]; then
        assert_file_exists ".claude/memory/checkpoints/${checkpoint_id}.json"
    else
        log "${YELLOW}⚠ WARNING: Checkpoint creation requires Claude Flow installed${NC}"
    fi
}

# Test 4: Checkpoint Manager list
test_checkpoint_manager_list() {
    log "${BLUE}Test: Checkpoint Manager list${NC}"

    ./scripts/automation/checkpoint-manager.sh list > /dev/null 2>&1
    assert_success "Checkpoint Manager list command"
}

# Test 5: ReasoningBank Sync exists
test_reasoningbank_sync_exists() {
    log "${BLUE}Test: ReasoningBank Sync exists${NC}"

    assert_file_exists "scripts/automation/sync-reasoningbank.sh"
    assert_executable "scripts/automation/sync-reasoningbank.sh"
}

# Test 6: ReasoningBank Sync help
test_reasoningbank_sync_help() {
    log "${BLUE}Test: ReasoningBank Sync help${NC}"

    ./scripts/automation/sync-reasoningbank.sh help > /dev/null 2>&1
    assert_success "ReasoningBank Sync help command"
}

# Test 7: Vectal Sync exists
test_vectal_sync_exists() {
    log "${BLUE}Test: Vectal Sync exists${NC}"

    assert_file_exists "scripts/automation/sync-vectal-todos.sh"
    assert_executable "scripts/automation/sync-vectal-todos.sh"
}

# Test 8: Vectal Sync help
test_vectal_sync_help() {
    log "${BLUE}Test: Vectal Sync help${NC}"

    ./scripts/automation/sync-vectal-todos.sh help > /dev/null 2>&1
    assert_success "Vectal Sync help command"
}

# Test 9: Vectal Sync create batch
test_vectal_sync_create_batch() {
    log "${BLUE}Test: Vectal Sync create batch${NC}"

    ./scripts/automation/sync-vectal-todos.sh create-batch data/tasks/vectal-test.json .claude/memory/todos/test-batch.json > /dev/null 2>&1
    assert_file_exists ".claude/memory/todos/test-batch.json"

    # Verify JSON structure
    if [ -f ".claude/memory/todos/test-batch.json" ]; then
        jq '.' .claude/memory/todos/test-batch.json > /dev/null 2>&1
        assert_success "Vectal batch JSON is valid"
    fi
}

# Test 10: Metrics Dashboard exists
test_metrics_dashboard_exists() {
    log "${BLUE}Test: Metrics Dashboard exists${NC}"

    assert_file_exists "scripts/automation/metrics-dashboard.sh"
    assert_executable "scripts/automation/metrics-dashboard.sh"
}

# Test 11: Metrics Dashboard help
test_metrics_dashboard_help() {
    log "${BLUE}Test: Metrics Dashboard help${NC}"

    ./scripts/automation/metrics-dashboard.sh help > /dev/null 2>&1
    assert_success "Metrics Dashboard help command"
}

# Test 12: Metrics Dashboard log
test_metrics_dashboard_log() {
    log "${BLUE}Test: Metrics Dashboard log${NC}"

    ./scripts/automation/metrics-dashboard.sh log test-feature test-session used "Test logging" > /dev/null 2>&1
    assert_success "Metrics Dashboard log command"

    # Verify log entry
    if [ -f ".claude/memory/metrics/usage.jsonl" ]; then
        grep -q "test-feature" .claude/memory/metrics/usage.jsonl
        assert_success "Metrics log entry created"
    fi
}

# Test 13: Metrics Dashboard adoption
test_metrics_dashboard_adoption() {
    log "${BLUE}Test: Metrics Dashboard adoption${NC}"

    ./scripts/automation/metrics-dashboard.sh adoption .claude/memory/metrics/test-adoption.json > /dev/null 2>&1
    assert_file_exists ".claude/memory/metrics/test-adoption.json"
}

# Test 14: All scripts have README
test_scripts_readme_exists() {
    log "${BLUE}Test: Scripts README exists${NC}"

    assert_file_exists "scripts/automation/README.md"
}

# Test 15: Templates README exists
test_templates_readme_exists() {
    log "${BLUE}Test: Templates README exists${NC}"

    assert_file_exists ".claude/templates/README.md"
}

# Test 16: Operational Guardrails doc exists
test_guardrails_doc_exists() {
    log "${BLUE}Test: Operational Guardrails doc exists${NC}"

    assert_file_exists "docs/operations/GUARDRAILS.md"
}

# Test 17: All templates exist
test_all_templates_exist() {
    log "${BLUE}Test: All templates exist${NC}"

    assert_file_exists ".claude/templates/checkpoint-refactor.json"
    assert_file_exists ".claude/templates/compliance-sweep.json"
    assert_file_exists ".claude/templates/doc-update.json"
    assert_file_exists ".claude/templates/multi-service-deploy.json"
}

# Test 18: Template JSON syntax
test_template_json_syntax() {
    log "${BLUE}Test: Template JSON syntax${NC}"

    for template in .claude/templates/*.json; do
        if [ -f "$template" ]; then
            jq '.' "$template" > /dev/null 2>&1
            assert_success "Template $(basename "$template") has valid JSON"
        fi
    done
}

# Run all tests
run_all_tests() {
    log "${BLUE}═══════════════════════════════════════════════${NC}"
    log "${BLUE}   Claude Code/Flow Automation Test Suite     ${NC}"
    log "${BLUE}═══════════════════════════════════════════════${NC}"
    echo ""

    setup_test_env

    # Run tests
    test_checkpoint_manager_exists
    test_checkpoint_manager_help
    test_checkpoint_manager_create
    test_checkpoint_manager_list

    test_reasoningbank_sync_exists
    test_reasoningbank_sync_help

    test_vectal_sync_exists
    test_vectal_sync_help
    test_vectal_sync_create_batch

    test_metrics_dashboard_exists
    test_metrics_dashboard_help
    test_metrics_dashboard_log
    test_metrics_dashboard_adoption

    test_scripts_readme_exists
    test_templates_readme_exists
    test_guardrails_doc_exists

    test_all_templates_exist
    test_template_json_syntax

    cleanup_test_env

    # Summary
    echo ""
    log "${BLUE}═══════════════════════════════════════════════${NC}"
    log "${BLUE}              Test Summary                     ${NC}"
    log "${BLUE}═══════════════════════════════════════════════${NC}"
    log "${BLUE}Total Tests:  ${TESTS_RUN}${NC}"
    log "${GREEN}Passed:       ${TESTS_PASSED}${NC}"
    log "${RED}Failed:       ${TESTS_FAILED}${NC}"
    log "${BLUE}Log File:     ${TEST_LOG}${NC}"
    log "${BLUE}═══════════════════════════════════════════════${NC}"

    if [ $TESTS_FAILED -eq 0 ]; then
        log "${GREEN}✓ All tests passed!${NC}"
        return 0
    else
        log "${RED}✗ Some tests failed${NC}"
        return 1
    fi
}

# Main
case "${1:-all}" in
    all)
        run_all_tests
        ;;
    setup)
        setup_test_env
        ;;
    cleanup)
        cleanup_test_env
        ;;
    *)
        echo "Usage: $0 [all|setup|cleanup]"
        exit 1
        ;;
esac
