#!/bin/bash

# Checkpoint Manager - Automated checkpoint creation and management
# Part of Claude Code/Flow automation suite

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CHECKPOINT_DIR=".claude/checkpoints"
MEMORY_DIR=".claude/memory/checkpoints"
LOG_FILE=".claude/terminal/history/checkpoint-manager.log"

# Ensure directories exist
mkdir -p "$CHECKPOINT_DIR" "$MEMORY_DIR" "$(dirname "$LOG_FILE")"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create automatic checkpoint with label
create_checkpoint() {
    local label="$1"
    local description="$2"
    local risk_level="${3:-medium}"

    log "${BLUE}Creating checkpoint: $label${NC}"

    # Generate checkpoint ID
    local checkpoint_id="cp-$(date +'%Y%m%d-%H%M%S')-${label}"

    # Create checkpoint using Claude Flow
    npx claude-flow@alpha checkpoint create --label "$label" --id "$checkpoint_id" 2>&1 | tee -a "$LOG_FILE"

    # Store metadata
    cat > "$MEMORY_DIR/$checkpoint_id.json" <<EOF
{
  "id": "$checkpoint_id",
  "label": "$label",
  "description": "$description",
  "risk_level": "$risk_level",
  "timestamp": "$(date -Iseconds)",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'N/A')",
  "git_branch": "$(git branch --show-current 2>/dev/null || echo 'N/A')",
  "rollback_command": "npx claude-flow@alpha checkpoint rollback --id $checkpoint_id"
}
EOF

    log "${GREEN}Checkpoint created: $checkpoint_id${NC}"
    echo "$checkpoint_id"
}

# Auto-label checkpoints based on context
auto_label_checkpoint() {
    local operation="$1"

    case "$operation" in
        refactor)
            create_checkpoint "refactor" "Automated checkpoint before refactoring" "high"
            ;;
        deploy)
            create_checkpoint "pre-deploy" "Automated checkpoint before deployment" "critical"
            ;;
        security)
            create_checkpoint "security-audit" "Automated checkpoint before security changes" "high"
            ;;
        migration)
            create_checkpoint "pre-migration" "Automated checkpoint before migration" "critical"
            ;;
        test)
            create_checkpoint "pre-test" "Automated checkpoint before test changes" "low"
            ;;
        *)
            create_checkpoint "auto" "Automated checkpoint for $operation" "medium"
            ;;
    esac
}

# Generate rollback instructions
generate_rollback_instructions() {
    local checkpoint_id="$1"
    local output_file="${2:-.claude/memory/checkpoints/rollback-${checkpoint_id}.md}"

    log "${BLUE}Generating rollback instructions for $checkpoint_id${NC}"

    # Load checkpoint metadata
    if [ ! -f "$MEMORY_DIR/$checkpoint_id.json" ]; then
        log "${RED}Checkpoint metadata not found: $checkpoint_id${NC}"
        return 1
    fi

    local metadata=$(cat "$MEMORY_DIR/$checkpoint_id.json")
    local label=$(echo "$metadata" | jq -r '.label')
    local timestamp=$(echo "$metadata" | jq -r '.timestamp')
    local git_commit=$(echo "$metadata" | jq -r '.git_commit')
    local git_branch=$(echo "$metadata" | jq -r '.git_branch')

    cat > "$output_file" <<EOF
# Rollback Instructions

## Checkpoint Information
- **ID:** $checkpoint_id
- **Label:** $label
- **Created:** $timestamp
- **Git Commit:** $git_commit
- **Git Branch:** $git_branch

## Rollback Methods

### Method 1: Claude Flow Checkpoint Rollback
\`\`\`bash
npx claude-flow@alpha checkpoint rollback --id $checkpoint_id
\`\`\`

### Method 2: Git Rollback
\`\`\`bash
git checkout $git_commit
# Or create a new branch from this commit
git checkout -b rollback-$checkpoint_id $git_commit
\`\`\`

### Method 3: File-level Rollback
\`\`\`bash
# Restore specific files from checkpoint
cp -r $CHECKPOINT_DIR/$checkpoint_id/* .
\`\`\`

## Verification Steps

1. Check git status: \`git status\`
2. Verify services: \`docker-compose ps\`
3. Run tests: \`npm run test\`
4. Check logs: \`tail -f .claude/terminal/history/checkpoint-manager.log\`

## Additional Notes

- Review changes before committing rollback
- Update ReasoningBank with rollback decision
- Document lessons learned in project memory
EOF

    log "${GREEN}Rollback instructions generated: $output_file${NC}"
}

# Cleanup old checkpoints
cleanup_checkpoints() {
    local keep_days="${1:-30}"

    log "${BLUE}Cleaning up checkpoints older than $keep_days days${NC}"

    # Find and remove old checkpoint metadata
    find "$MEMORY_DIR" -name "cp-*.json" -mtime +$keep_days -type f | while read -r file; do
        local checkpoint_id=$(basename "$file" .json)
        log "${YELLOW}Removing old checkpoint: $checkpoint_id${NC}"
        rm -f "$file"
        rm -rf "$CHECKPOINT_DIR/$checkpoint_id"
    done

    log "${GREEN}Checkpoint cleanup complete${NC}"
}

# List all checkpoints
list_checkpoints() {
    log "${BLUE}Available checkpoints:${NC}"

    for file in "$MEMORY_DIR"/cp-*.json; do
        if [ -f "$file" ]; then
            local metadata=$(cat "$file")
            local id=$(echo "$metadata" | jq -r '.id')
            local label=$(echo "$metadata" | jq -r '.label')
            local timestamp=$(echo "$metadata" | jq -r '.timestamp')
            local risk=$(echo "$metadata" | jq -r '.risk_level')

            echo -e "${GREEN}$id${NC} [$risk] - $label ($timestamp)"
        fi
    done
}

# Main command handler
case "${1:-help}" in
    create)
        create_checkpoint "${2:-auto}" "${3:-Manual checkpoint}" "${4:-medium}"
        ;;
    auto-label)
        auto_label_checkpoint "${2:-default}"
        ;;
    rollback-instructions)
        generate_rollback_instructions "$2"
        ;;
    cleanup)
        cleanup_checkpoints "${2:-30}"
        ;;
    list)
        list_checkpoints
        ;;
    help|*)
        echo "Checkpoint Manager - Automated checkpoint management"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  create <label> <description> <risk_level>  Create manual checkpoint"
        echo "  auto-label <operation>                     Auto-create labeled checkpoint"
        echo "  rollback-instructions <checkpoint_id>      Generate rollback guide"
        echo "  cleanup [days]                             Clean old checkpoints (default: 30 days)"
        echo "  list                                       List all checkpoints"
        echo "  help                                       Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 create refactor 'Before major refactoring' high"
        echo "  $0 auto-label deploy"
        echo "  $0 rollback-instructions cp-20250101-120000-refactor"
        echo "  $0 cleanup 14"
        ;;
esac
