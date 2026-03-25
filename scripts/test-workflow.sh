#!/bin/bash

# =============================================================================
# Climate News MAS - Workflow-testiskripti
# =============================================================================
# Lähettää test-käskyn Orchestrator-agentille manuaalisen workflow:n käynnistämiseksi

set -e

echo "========================================="
echo "Climate News MAS - Workflow Test"
echo "========================================="
echo ""

# Luo test task ID
TIMESTAMP=$(date +%Y%m%d)
TASK_ID="task-$TIMESTAMP-999"

echo "Sending manual workflow trigger..."
echo "Task ID: $TASK_ID"
echo ""

# Lähetä viesti Kafkaan
docker exec climatenews-kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic orchestrator_commands \
  <<EOF
{"command": "manual_trigger", "taskId": "$TASK_ID", "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF

echo ""
echo "✓ Workflow trigger sent!"
echo ""
echo "Monitor progress with:"
echo "  docker-compose logs -f orchestrator"
echo ""
echo "Check task state in Redis:"
echo "  docker exec -it climatenews-redis redis-cli GET task:$TASK_ID"
echo ""

