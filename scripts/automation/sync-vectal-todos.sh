#!/bin/bash

# Vectal Todo Sync - Automated task management integration
# Part of Claude Code/Flow automation suite

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TODO_DIR=".claude/memory/todos"
VECTAL_EXPORT="data/tasks/vectal-export.json"
LOG_FILE=".claude/terminal/history/vectal-sync.log"

# Ensure directories exist
mkdir -p "$TODO_DIR" "$(dirname "$VECTAL_EXPORT")" "$(dirname "$LOG_FILE")"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Import from Vectal
import_from_vectal() {
    local vectal_file="${1:-$VECTAL_EXPORT}"
    local label="${2:-sprint-2025q1}"

    log "${BLUE}Importing tasks from Vectal: $vectal_file${NC}"

    if [ ! -f "$vectal_file" ]; then
        log "${RED}Vectal export file not found: $vectal_file${NC}"
        return 1
    fi

    # Import using Claude Flow
    npx claude-flow@alpha todos import --file "$vectal_file" --label "$label" 2>&1 | tee -a "$LOG_FILE"

    # Copy to memory for tracking
    cp "$vectal_file" "$TODO_DIR/vectal-import-$(date +'%Y%m%d-%H%M%S').json"

    log "${GREEN}Import complete from Vectal${NC}"
}

# Export to Vectal
export_to_vectal() {
    local label="${1:-sprint-2025q1}"
    local output_file="${2:-$VECTAL_EXPORT}"

    log "${BLUE}Exporting tasks to Vectal format: $output_file${NC}"

    npx claude-flow@alpha todos export --label "$label" --format vectal --output "$output_file" 2>&1 | tee -a "$LOG_FILE"

    log "${GREEN}Export complete to: $output_file${NC}"
}

# Sync task status
sync_task_status() {
    local task_id="$1"
    local status="$2"
    local notes="${3:-}"

    log "${BLUE}Syncing task status: $task_id -> $status${NC}"

    # Update local todo
    local todo_file="$TODO_DIR/current-sprint.json"

    if [ -f "$todo_file" ]; then
        # Update status in JSON
        jq --arg id "$task_id" --arg status "$status" \
           '(.todos[] | select(.id == $id) | .status) = $status' \
           "$todo_file" > "$todo_file.tmp" && mv "$todo_file.tmp" "$todo_file"

        # Add notes if provided
        if [ -n "$notes" ]; then
            jq --arg id "$task_id" --arg notes "$notes" \
               '(.todos[] | select(.id == $id) | .notes) = $notes' \
               "$todo_file" > "$todo_file.tmp" && mv "$todo_file.tmp" "$todo_file"
        fi
    fi

    # Log update
    cat >> "$TODO_DIR/sync-log.json" <<EOF
{
  "task_id": "$task_id",
  "status": "$status",
  "notes": "$notes",
  "timestamp": "$(date -Iseconds)",
  "synced_to_vectal": false
}
EOF

    log "${GREEN}Task status updated: $task_id${NC}"
}

# Create TodoWrite batch from Vectal export
create_todowrite_batch() {
    local vectal_file="${1:-$VECTAL_EXPORT}"
    local output_file="${2:-$TODO_DIR/todowrite-batch.json}"

    log "${BLUE}Creating TodoWrite batch from: $vectal_file${NC}"

    if [ ! -f "$vectal_file" ]; then
        log "${RED}Vectal file not found: $vectal_file${NC}"
        return 1
    fi

    # Transform Vectal format to TodoWrite format
    jq '{todos: [.tasks[] | {
      id: .id,
      content: .title,
      status: (if .completed then "completed" elif .in_progress then "in_progress" else "pending" end),
      priority: (.priority // "medium"),
      link: ("vectal://" + .id),
      activeForm: (.title | gsub("^(\\w+)"; "\u0000\\1ing") | ltrimstr("\u0000"))
    }]}' "$vectal_file" > "$output_file"

    log "${GREEN}TodoWrite batch created: $output_file${NC}"
    echo "$output_file"
}

# Bi-directional sync
bidirectional_sync() {
    local sprint_label="${1:-sprint-2025q1}"

    log "${BLUE}Starting bi-directional sync for: $sprint_label${NC}"

    # Export current state to Vectal format
    export_to_vectal "$sprint_label" "$VECTAL_EXPORT.out"

    # Import latest from Vectal
    if [ -f "$VECTAL_EXPORT" ]; then
        import_from_vectal "$VECTAL_EXPORT" "$sprint_label"
    fi

    # Merge and resolve conflicts (simple last-write-wins for now)
    log "${YELLOW}Merging changes...${NC}"

    # Store sync metadata
    cat > "$TODO_DIR/sync-metadata-$(date +'%Y%m%d-%H%M%S').json" <<EOF
{
  "sprint_label": "$sprint_label",
  "sync_timestamp": "$(date -Iseconds)",
  "vectal_export": "$VECTAL_EXPORT",
  "local_export": "$VECTAL_EXPORT.out",
  "sync_direction": "bidirectional"
}
EOF

    log "${GREEN}Bi-directional sync complete${NC}"
}

# Webhook handler for Vectal updates
webhook_handler() {
    local webhook_data="$1"

    log "${BLUE}Processing Vectal webhook${NC}"

    # Parse webhook data
    local task_id=$(echo "$webhook_data" | jq -r '.task_id')
    local status=$(echo "$webhook_data" | jq -r '.status')
    local title=$(echo "$webhook_data" | jq -r '.title')

    # Update local todos
    sync_task_status "$task_id" "$status" "Updated via Vectal webhook"

    # Store webhook event
    echo "$webhook_data" >> "$TODO_DIR/webhook-events.jsonl"

    log "${GREEN}Webhook processed for task: $task_id${NC}"
}

# Generate sync report
generate_sync_report() {
    local sprint_label="${1:-sprint-2025q1}"
    local output_file="${2:-$TODO_DIR/sync-report-$(date +'%Y%m%d').md}"

    log "${BLUE}Generating sync report${NC}"

    cat > "$output_file" <<EOF
# Task Sync Report

**Sprint:** $sprint_label
**Generated:** $(date +'%Y-%m-%d %H:%M:%S')

## Summary

EOF

    # Count tasks by status
    if [ -f "$TODO_DIR/current-sprint.json" ]; then
        local total=$(jq '.todos | length' "$TODO_DIR/current-sprint.json")
        local completed=$(jq '[.todos[] | select(.status == "completed")] | length' "$TODO_DIR/current-sprint.json")
        local in_progress=$(jq '[.todos[] | select(.status == "in_progress")] | length' "$TODO_DIR/current-sprint.json")
        local pending=$(jq '[.todos[] | select(.status == "pending")] | length' "$TODO_DIR/current-sprint.json")

        cat >> "$output_file" <<EOF
- **Total Tasks:** $total
- **Completed:** $completed
- **In Progress:** $in_progress
- **Pending:** $pending

## Task Details

EOF

        jq -r '.todos[] | "### \(.id): \(.content)\n- **Status:** \(.status)\n- **Priority:** \(.priority)\n- **Link:** \(.link)\n"' \
           "$TODO_DIR/current-sprint.json" >> "$output_file"
    fi

    log "${GREEN}Sync report generated: $output_file${NC}"
}

# Main command handler
case "${1:-help}" in
    import)
        import_from_vectal "${2:-$VECTAL_EXPORT}" "${3:-sprint-2025q1}"
        ;;
    export)
        export_to_vectal "${2:-sprint-2025q1}" "${3:-$VECTAL_EXPORT}"
        ;;
    sync-status)
        sync_task_status "$2" "$3" "${4:-}"
        ;;
    create-batch)
        create_todowrite_batch "${2:-$VECTAL_EXPORT}" "${3:-}"
        ;;
    bidirectional)
        bidirectional_sync "${2:-sprint-2025q1}"
        ;;
    webhook)
        webhook_handler "$2"
        ;;
    report)
        generate_sync_report "${2:-sprint-2025q1}" "${3:-}"
        ;;
    help|*)
        echo "Vectal Todo Sync - Task management integration"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  import [file] [label]                    Import tasks from Vectal"
        echo "  export [label] [output_file]             Export tasks to Vectal format"
        echo "  sync-status <task_id> <status> [notes]   Update task status"
        echo "  create-batch [vectal_file] [output]      Create TodoWrite batch"
        echo "  bidirectional [sprint_label]             Bi-directional sync"
        echo "  webhook <webhook_data>                   Handle Vectal webhook"
        echo "  report [sprint_label] [output_file]      Generate sync report"
        echo "  help                                     Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 import data/tasks/vectal-export.json sprint-2025q1"
        echo "  $0 export sprint-2025q1 data/tasks/vectal-export.json"
        echo "  $0 sync-status T-204 completed 'Finished implementation'"
        echo "  $0 bidirectional sprint-2025q1"
        ;;
esac
