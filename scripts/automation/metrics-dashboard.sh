#!/bin/bash

# Metrics Dashboard - Adoption tracking and cost monitoring
# Part of Claude Code/Flow automation suite

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
METRICS_DIR=".claude/memory/metrics"
COSTS_DIR=".claude/memory/costs"
REPORTS_DIR="docs/metrics"
LOG_FILE=".claude/terminal/history/metrics-dashboard.log"

# Ensure directories exist
mkdir -p "$METRICS_DIR" "$COSTS_DIR" "$REPORTS_DIR" "$(dirname "$LOG_FILE")"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Log feature usage
log_usage() {
    local feature="$1"
    local session="${2:-default}"
    local status="${3:-used}"
    local notes="${4:-}"

    log "${BLUE}Logging usage: $feature${NC}"

    local timestamp=$(date -Iseconds)
    local log_entry=$(jq -n \
        --arg feature "$feature" \
        --arg session "$session" \
        --arg status "$status" \
        --arg notes "$notes" \
        --arg timestamp "$timestamp" \
        '{feature: $feature, session: $session, status: $status, notes: $notes, timestamp: $timestamp}')

    echo "$log_entry" >> "$METRICS_DIR/usage.jsonl"

    log "${GREEN}Usage logged for: $feature${NC}"
}

# Log Agent Booster metrics
log_agent_booster() {
    local result="${1:-success}"
    local files="${2:-0}"
    local duration="${3:-0}"

    log "${BLUE}Logging Agent Booster metrics${NC}"

    local timestamp=$(date -Iseconds)
    local log_entry=$(jq -n \
        --arg result "$result" \
        --arg files "$files" \
        --arg duration "$duration" \
        --arg timestamp "$timestamp" \
        '{feature: "agent-booster", result: $result, files: ($files|tonumber), duration: $duration, timestamp: $timestamp}')

    echo "$log_entry" >> "$METRICS_DIR/agent-booster.jsonl"

    log "${GREEN}Agent Booster metrics logged${NC}"
}

# Track OpenRouter cost savings
log_proxy_costs() {
    local window="${1:-7d}"

    log "${BLUE}Tracking OpenRouter proxy costs for window: $window${NC}"

    npx claude-flow@alpha proxy metrics --window "$window" --output "$COSTS_DIR/proxy-costs-$(date +'%Y%m%d').json" 2>&1 | tee -a "$LOG_FILE"

    log "${GREEN}Proxy costs tracked${NC}"
}

# Generate adoption metrics
generate_adoption_metrics() {
    local output_file="${1:-$REPORTS_DIR/adoption-$(date +'%Y%m%d').json}"

    log "${BLUE}Generating adoption metrics${NC}"

    local features=(
        "checkpoints"
        "subagents"
        "vs-code-extension"
        "web-interface"
        "enhanced-terminal"
        "reasoningbank"
        "agent-booster"
        "openrouter-proxy"
    )

    local metrics_json="{"

    for feature in "${features[@]}"; do
        local count=$(grep -c "\"feature\":\"$feature\"" "$METRICS_DIR/usage.jsonl" 2>/dev/null || echo "0")
        metrics_json+="\"$feature\":$count,"
    done

    metrics_json="${metrics_json%,}}"

    echo "$metrics_json" | jq '.' > "$output_file"

    log "${GREEN}Adoption metrics generated: $output_file${NC}"
}

# Generate cost savings report
generate_cost_report() {
    local output_file="${1:-$REPORTS_DIR/cost-savings-$(date +'%Y%m%d').md}"

    log "${BLUE}Generating cost savings report${NC}"

    # Get latest proxy costs
    local latest_costs=$(ls -t "$COSTS_DIR"/proxy-costs-*.json 2>/dev/null | head -1)

    if [ -z "$latest_costs" ]; then
        log "${YELLOW}No cost data available, running proxy metrics...${NC}"
        log_proxy_costs "30d"
        latest_costs=$(ls -t "$COSTS_DIR"/proxy-costs-*.json | head -1)
    fi

    cat > "$output_file" <<EOF
# Cost Savings Report

**Generated:** $(date +'%Y-%m-%d %H:%M:%S')

## OpenRouter Proxy Savings

EOF

    if [ -f "$latest_costs" ]; then
        local total_savings=$(jq -r '.total_savings // "N/A"' "$latest_costs")
        local total_requests=$(jq -r '.total_requests // 0' "$latest_costs")
        local avg_savings_per_request=$(jq -r '.avg_savings_per_request // "N/A"' "$latest_costs")

        cat >> "$output_file" <<EOF
- **Total Savings:** \$$total_savings
- **Total Requests:** $total_requests
- **Average Savings per Request:** \$$avg_savings_per_request

### Savings Breakdown

\`\`\`json
$(jq '.' "$latest_costs")
\`\`\`
EOF
    else
        echo "No cost data available" >> "$output_file"
    fi

    log "${GREEN}Cost report generated: $output_file${NC}"
}

# Generate feature adoption dashboard
generate_dashboard() {
    local output_file="${1:-$REPORTS_DIR/dashboard-$(date +'%Y%m%d').html}"

    log "${BLUE}Generating metrics dashboard${NC}"

    # Generate metrics data
    generate_adoption_metrics "$METRICS_DIR/current-adoption.json"

    cat > "$output_file" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code/Flow Metrics Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            text-transform: uppercase;
            opacity: 0.9;
        }
        .metric-card .value {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-card .label {
            font-size: 12px;
            opacity: 0.8;
        }
        .chart {
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 8px;
        }
        .timestamp {
            text-align: right;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Claude Code/Flow Metrics Dashboard</h1>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Checkpoints</h3>
                <div class="value" id="checkpoints">-</div>
                <div class="label">Total Usage</div>
            </div>

            <div class="metric-card">
                <h3>Subagents</h3>
                <div class="value" id="subagents">-</div>
                <div class="label">Total Spawned</div>
            </div>

            <div class="metric-card">
                <h3>Agent Booster</h3>
                <div class="value" id="agent-booster">-</div>
                <div class="label">Activations</div>
            </div>

            <div class="metric-card">
                <h3>ReasoningBank</h3>
                <div class="value" id="reasoningbank">-</div>
                <div class="label">Memory Operations</div>
            </div>

            <div class="metric-card">
                <h3>VS Code Extension</h3>
                <div class="value" id="vs-code-extension">-</div>
                <div class="label">Sessions</div>
            </div>

            <div class="metric-card">
                <h3>Web Interface</h3>
                <div class="value" id="web-interface">-</div>
                <div class="label">Sessions</div>
            </div>
        </div>

        <div class="chart">
            <h2>Feature Adoption Trend</h2>
            <p>Detailed charts would be rendered here using Chart.js or similar library.</p>
        </div>

        <div class="timestamp">
            Generated: <span id="timestamp"></span>
        </div>
    </div>

    <script>
        // Load metrics data
        fetch('.claude/memory/metrics/current-adoption.json')
            .then(response => response.json())
            .then(data => {
                document.getElementById('checkpoints').textContent = data.checkpoints || 0;
                document.getElementById('subagents').textContent = data.subagents || 0;
                document.getElementById('agent-booster').textContent = data['agent-booster'] || 0;
                document.getElementById('reasoningbank').textContent = data.reasoningbank || 0;
                document.getElementById('vs-code-extension').textContent = data['vs-code-extension'] || 0;
                document.getElementById('web-interface').textContent = data['web-interface'] || 0;
            })
            .catch(err => console.error('Error loading metrics:', err));

        // Set timestamp
        document.getElementById('timestamp').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
EOF

    log "${GREEN}Dashboard generated: $output_file${NC}"
    log "${CYAN}Open in browser: file://$(pwd)/$output_file${NC}"
}

# Sprint integration report
generate_sprint_report() {
    local sprint_label="${1:-sprint-2025q1}"
    local output_file="${2:-$REPORTS_DIR/sprint-$sprint_label-metrics.md}"

    log "${BLUE}Generating sprint report for: $sprint_label${NC}"

    cat > "$output_file" <<EOF
# Sprint Metrics Report

**Sprint:** $sprint_label
**Generated:** $(date +'%Y-%m-%d %H:%M:%S')

## Feature Adoption

EOF

    # Count feature usage in this sprint
    local start_date=$(date -d "30 days ago" +%Y-%m-%d 2>/dev/null || date -v-30d +%Y-%m-%d)

    if [ -f "$METRICS_DIR/usage.jsonl" ]; then
        echo "### Adoption Summary" >> "$output_file"
        echo "" >> "$output_file"

        # Count by feature
        jq -r 'select(.timestamp >= "'$start_date'") | .feature' "$METRICS_DIR/usage.jsonl" 2>/dev/null | \
        sort | uniq -c | sort -rn | while read count feature; do
            echo "- **$feature:** $count uses" >> "$output_file"
        done
    fi

    # Add cost savings
    echo "" >> "$output_file"
    echo "## Cost Savings" >> "$output_file"
    echo "" >> "$output_file"

    local latest_costs=$(ls -t "$COSTS_DIR"/proxy-costs-*.json 2>/dev/null | head -1)
    if [ -f "$latest_costs" ]; then
        local savings=$(jq -r '.total_savings // "N/A"' "$latest_costs")
        echo "- **OpenRouter Proxy Savings:** \$$savings" >> "$output_file"
    else
        echo "- No cost data available for this sprint" >> "$output_file"
    fi

    # Add Agent Booster stats
    if [ -f "$METRICS_DIR/agent-booster.jsonl" ]; then
        echo "" >> "$output_file"
        echo "## Agent Booster Performance" >> "$output_file"
        echo "" >> "$output_file"

        local total_files=$(jq -s 'map(.files) | add' "$METRICS_DIR/agent-booster.jsonl" 2>/dev/null || echo "0")
        local avg_duration=$(jq -s 'map(.duration|tonumber) | add/length' "$METRICS_DIR/agent-booster.jsonl" 2>/dev/null || echo "0")

        echo "- **Total Files Edited:** $total_files" >> "$output_file"
        echo "- **Average Duration:** ${avg_duration}s" >> "$output_file"
    fi

    log "${GREEN}Sprint report generated: $output_file${NC}"
}

# Realtime dashboard monitoring
monitor_dashboard() {
    log "${BLUE}Starting realtime metrics monitoring${NC}"

    while true; do
        clear
        echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║      Claude Code/Flow Metrics Dashboard (Live)        ║${NC}"
        echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}Feature Usage (Last 24h):${NC}"

        # Count recent usage
        local cutoff=$(date -d "24 hours ago" +%Y-%m-%d 2>/dev/null || date -v-24H +%Y-%m-%d)

        if [ -f "$METRICS_DIR/usage.jsonl" ]; then
            jq -r 'select(.timestamp >= "'$cutoff'") | "\(.feature): \(.status)"' "$METRICS_DIR/usage.jsonl" 2>/dev/null | \
            sort | uniq -c | sort -rn | head -10
        fi

        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop monitoring${NC}"
        sleep 10
    done
}

# Main command handler
case "${1:-help}" in
    log)
        log_usage "$2" "${3:-default}" "${4:-used}" "${5:-}"
        ;;
    log-booster)
        log_agent_booster "${2:-success}" "${3:-0}" "${4:-0}"
        ;;
    track-costs)
        log_proxy_costs "${2:-7d}"
        ;;
    adoption)
        generate_adoption_metrics "${2:-}"
        ;;
    cost-report)
        generate_cost_report "${2:-}"
        ;;
    dashboard)
        generate_dashboard "${2:-}"
        ;;
    sprint-report)
        generate_sprint_report "${2:-sprint-2025q1}" "${3:-}"
        ;;
    monitor)
        monitor_dashboard
        ;;
    help|*)
        echo "Metrics Dashboard - Adoption tracking and cost monitoring"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  log <feature> [session] [status] [notes]     Log feature usage"
        echo "  log-booster [result] [files] [duration]      Log Agent Booster metrics"
        echo "  track-costs [window]                         Track OpenRouter costs"
        echo "  adoption [output_file]                       Generate adoption metrics"
        echo "  cost-report [output_file]                    Generate cost report"
        echo "  dashboard [output_file]                      Generate HTML dashboard"
        echo "  sprint-report [sprint_label] [output]        Generate sprint report"
        echo "  monitor                                      Realtime monitoring"
        echo "  help                                         Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 log checkpoints session-123 used 'Pre-refactor checkpoint'"
        echo "  $0 log-booster success 8 120"
        echo "  $0 track-costs 30d"
        echo "  $0 dashboard docs/metrics/dashboard.html"
        echo "  $0 sprint-report sprint-2025q1"
        ;;
esac
