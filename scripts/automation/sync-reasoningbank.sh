#!/bin/bash

# ReasoningBank Sync - Automated memory synchronization
# Part of Claude Code/Flow automation suite

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
MEMORY_DIR=".claude/memory"
REASONINGBANK_DIR="$MEMORY_DIR/reasoningbank"
LOG_FILE=".claude/terminal/history/reasoningbank-sync.log"

# Ensure directories exist
mkdir -p "$REASONINGBANK_DIR" "$(dirname "$LOG_FILE")"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Connect to ReasoningBank
connect_reasoningbank() {
    local context="$1"
    local labels="${2:-}"

    log "${BLUE}Connecting to ReasoningBank context: $context${NC}"

    npx claude-flow@alpha memory connect --provider reasoningbank --context "$context" 2>&1 | tee -a "$LOG_FILE"

    if [ -n "$labels" ]; then
        log "${BLUE}Syncing with labels: $labels${NC}"
        npx claude-flow@alpha memory sync --context "$context" --labels "$labels" 2>&1 | tee -a "$LOG_FILE"
    fi

    log "${GREEN}Connected to ReasoningBank: $context${NC}"
}

# Fetch from ReasoningBank
fetch_memory() {
    local context="$1"
    local labels="${2:-}"
    local output_file="${3:-$REASONINGBANK_DIR/fetch-$(date +'%Y%m%d-%H%M%S').json}"

    log "${BLUE}Fetching memory from context: $context${NC}"

    local fetch_cmd="npx claude-flow@alpha memory fetch --context '$context'"
    [ -n "$labels" ] && fetch_cmd="$fetch_cmd --labels '$labels'"
    fetch_cmd="$fetch_cmd --output '$output_file'"

    eval "$fetch_cmd" 2>&1 | tee -a "$LOG_FILE"

    log "${GREEN}Memory fetched to: $output_file${NC}"
    echo "$output_file"
}

# Push to ReasoningBank
push_memory() {
    local context="$1"
    local file="$2"
    local confidence="${3:-0.90}"
    local summary="${4:-}"

    log "${BLUE}Pushing memory to context: $context${NC}"

    if [ ! -f "$file" ]; then
        log "${RED}File not found: $file${NC}"
        return 1
    fi

    local push_cmd="npx claude-flow@alpha memory push --provider reasoningbank --context '$context' --file '$file' --confidence $confidence"
    [ -n "$summary" ] && push_cmd="$push_cmd --summary '$summary'"

    eval "$push_cmd" 2>&1 | tee -a "$LOG_FILE"

    # Store push metadata
    cat > "$REASONINGBANK_DIR/push-$(basename "$file" .md).json" <<EOF
{
  "context": "$context",
  "file": "$file",
  "confidence": $confidence,
  "timestamp": "$(date -Iseconds)",
  "summary": "$summary"
}
EOF

    log "${GREEN}Memory pushed successfully${NC}"
}

# Sync compliance data
sync_compliance() {
    local audit_id="$1"
    local audit_year="${2:-2025q1}"

    log "${BLUE}Syncing compliance data for audit: $audit_id${NC}"

    # Connect to compliance context
    connect_reasoningbank "compliance/$audit_year" "security,audit,compliance"

    # Push security findings
    if [ -f "docs/compliance/$audit_id/security.md" ]; then
        push_memory "compliance/$audit_year" "docs/compliance/$audit_id/security.md" "0.95" "Security audit findings for $audit_id"
    fi

    # Push compliance report
    if [ -f "docs/compliance/$audit_id/report.md" ]; then
        push_memory "compliance/$audit_year" "docs/compliance/$audit_id/report.md" "0.93" "Compliance report for $audit_id"
    fi

    # Fetch prior audits for reference
    fetch_memory "compliance/$audit_year" "audit,security" "$REASONINGBANK_DIR/compliance-history-$audit_id.json"

    log "${GREEN}Compliance sync complete for: $audit_id${NC}"
}

# Sync refactoring decisions
sync_refactoring() {
    local session_id="$1"
    local module_name="$2"
    local project="${3:-climatenews}"

    log "${BLUE}Syncing refactoring data for: $module_name${NC}"

    connect_reasoningbank "$project/refactor" "refactor,architecture,design"

    # Push analysis
    if [ -f "$MEMORY_DIR/refactor/$session_id/analysis.json" ]; then
        push_memory "$project/refactor/$module_name" "$MEMORY_DIR/refactor/$session_id/analysis.json" "0.88" "Architecture analysis for $module_name"
    fi

    # Push design decisions
    if [ -f "$MEMORY_DIR/refactor/$session_id/design.json" ]; then
        push_memory "$project/refactor/$module_name" "$MEMORY_DIR/refactor/$session_id/design.json" "0.90" "Design decisions for $module_name"
    fi

    # Push review findings
    if [ -f "$MEMORY_DIR/refactor/$session_id/review.md" ]; then
        push_memory "$project/refactor/$module_name" "$MEMORY_DIR/refactor/$session_id/review.md" "0.85" "Code review for $module_name refactoring"
    fi

    log "${GREEN}Refactoring sync complete for: $module_name${NC}"
}

# Sync deployment data
sync_deployment() {
    local deploy_id="$1"
    local environment="${2:-dev}"
    local project="${3:-climatenews}"

    log "${BLUE}Syncing deployment data for: $deploy_id${NC}"

    connect_reasoningbank "$project/deployment" "deployment,validation,$environment"

    # Push deployment plan
    if [ -f "$MEMORY_DIR/deployment/$deploy_id/plan.json" ]; then
        push_memory "$project/deployment/$environment" "$MEMORY_DIR/deployment/$deploy_id/plan.json" "0.92" "Deployment plan for $deploy_id"
    fi

    # Push health metrics
    if [ -f "$MEMORY_DIR/deployment/$deploy_id/health.json" ]; then
        push_memory "$project/deployment/$environment" "$MEMORY_DIR/deployment/$deploy_id/health.json" "0.90" "Health metrics for $deploy_id"
    fi

    # Push deployment docs
    if [ -f "docs/deployment/$deploy_id.md" ]; then
        push_memory "$project/deployment/$environment" "docs/deployment/$deploy_id.md" "0.88" "Deployment documentation for $deploy_id"
    fi

    log "${GREEN}Deployment sync complete for: $deploy_id${NC}"
}

# Batch sync multiple contexts
batch_sync() {
    local config_file="$1"

    if [ ! -f "$config_file" ]; then
        log "${RED}Config file not found: $config_file${NC}"
        return 1
    fi

    log "${BLUE}Running batch sync from config: $config_file${NC}"

    # Read config and sync each context
    jq -c '.[]' "$config_file" | while read -r item; do
        local type=$(echo "$item" | jq -r '.type')
        local id=$(echo "$item" | jq -r '.id')

        case "$type" in
            compliance)
                sync_compliance "$id" "$(echo "$item" | jq -r '.audit_year')"
                ;;
            refactoring)
                sync_refactoring "$id" "$(echo "$item" | jq -r '.module')" "$(echo "$item" | jq -r '.project')"
                ;;
            deployment)
                sync_deployment "$id" "$(echo "$item" | jq -r '.environment')" "$(echo "$item" | jq -r '.project')"
                ;;
        esac
    done

    log "${GREEN}Batch sync complete${NC}"
}

# Main command handler
case "${1:-help}" in
    connect)
        connect_reasoningbank "$2" "${3:-}"
        ;;
    fetch)
        fetch_memory "$2" "${3:-}" "${4:-}"
        ;;
    push)
        push_memory "$2" "$3" "${4:-0.90}" "${5:-}"
        ;;
    sync-compliance)
        sync_compliance "$2" "${3:-2025q1}"
        ;;
    sync-refactoring)
        sync_refactoring "$2" "$3" "${4:-climatenews}"
        ;;
    sync-deployment)
        sync_deployment "$2" "${3:-dev}" "${4:-climatenews}"
        ;;
    batch)
        batch_sync "$2"
        ;;
    help|*)
        echo "ReasoningBank Sync - Automated memory synchronization"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  connect <context> [labels]                       Connect to ReasoningBank"
        echo "  fetch <context> [labels] [output_file]           Fetch memory"
        echo "  push <context> <file> [confidence] [summary]     Push memory"
        echo "  sync-compliance <audit_id> [audit_year]          Sync compliance data"
        echo "  sync-refactoring <session_id> <module> [project] Sync refactoring data"
        echo "  sync-deployment <deploy_id> [environment] [proj] Sync deployment data"
        echo "  batch <config_file>                              Batch sync from config"
        echo "  help                                             Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 connect compliance/2025q1 'security,audit'"
        echo "  $0 push climatenews/refactor docs/refactor.md 0.92"
        echo "  $0 sync-compliance audit-001 2025q1"
        ;;
esac
