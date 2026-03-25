#!/usr/bin/env bash
# dev-kafka.sh - Manage Kafka topics and messages for local development
# Usage: ./scripts/dev-kafka.sh [list|create|delete|describe|send|consume|lag|reset-offset]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Kafka configuration
KAFKA_CONTAINER="climatenews-kafka"
KAFKA_INTERNAL_PORT="9092"
KAFKA_EXTERNAL_PORT="5092"

# Functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check dependencies
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi

    if ! docker ps | grep -q "$KAFKA_CONTAINER"; then
        error "Kafka container is not running"
        info "Start with: ./scripts/dev-start.sh infra"
        exit 1
    fi

    success "Dependencies checked"
}

# List topics
list_topics() {
    info "Listing Kafka topics..."
    echo ""

    docker exec -t "$KAFKA_CONTAINER" kafka-topics \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --list
}

# Create topic
create_topic() {
    local topic=$1

    if [ -z "$topic" ]; then
        error "Topic name required"
        echo "Usage: ./scripts/dev-kafka.sh create <topic-name>"
        exit 1
    fi

    info "Creating topic: $topic"

    docker exec -t "$KAFKA_CONTAINER" kafka-topics \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --create \
        --topic "$topic" \
        --partitions 3 \
        --replication-factor 1

    success "Topic created: $topic"
}

# Delete topic
delete_topic() {
    local topic=$1

    if [ -z "$topic" ]; then
        error "Topic name required"
        echo "Usage: ./scripts/dev-kafka.sh delete <topic-name>"
        exit 1
    fi

    warning "This will DELETE the topic: $topic"
    read -p "Are you sure? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        info "Delete cancelled"
        exit 0
    fi

    info "Deleting topic: $topic"

    docker exec -t "$KAFKA_CONTAINER" kafka-topics \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --delete \
        --topic "$topic"

    success "Topic deleted: $topic"
}

# Describe topic
describe_topic() {
    local topic=$1

    if [ -z "$topic" ]; then
        error "Topic name required"
        echo "Usage: ./scripts/dev-kafka.sh describe <topic-name>"
        exit 1
    fi

    info "Describing topic: $topic"
    echo ""

    docker exec -t "$KAFKA_CONTAINER" kafka-topics \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --describe \
        --topic "$topic"
}

# Send message to topic
send_message() {
    local topic=$1
    local message=$2

    if [ -z "$topic" ] || [ -z "$message" ]; then
        error "Topic name and message required"
        echo "Usage: ./scripts/dev-kafka.sh send <topic-name> '<json-message>'"
        exit 1
    fi

    info "Sending message to topic: $topic"

    echo "$message" | docker exec -i "$KAFKA_CONTAINER" kafka-console-producer \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --topic "$topic"

    success "Message sent to: $topic"
}

# Consume messages from topic
consume_messages() {
    local topic=$1
    local from_beginning=${2:-}

    if [ -z "$topic" ]; then
        error "Topic name required"
        echo "Usage: ./scripts/dev-kafka.sh consume <topic-name> [--from-beginning]"
        exit 1
    fi

    info "Consuming messages from topic: $topic"

    if [ "$from_beginning" = "--from-beginning" ]; then
        info "Reading from beginning (Ctrl+C to stop)..."
        echo ""

        docker exec -it "$KAFKA_CONTAINER" kafka-console-consumer \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --topic "$topic" \
            --from-beginning
    else
        info "Reading new messages (Ctrl+C to stop)..."
        echo ""

        docker exec -it "$KAFKA_CONTAINER" kafka-console-consumer \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --topic "$topic"
    fi
}

# Check consumer group lag
check_lag() {
    local group=$1

    if [ -z "$group" ]; then
        info "Showing all consumer groups..."
        echo ""

        docker exec -t "$KAFKA_CONTAINER" kafka-consumer-groups \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --list

        echo ""
        info "Use './scripts/dev-kafka.sh lag <group-name>' to see specific group lag"
        return
    fi

    info "Checking consumer group lag: $group"
    echo ""

    docker exec -t "$KAFKA_CONTAINER" kafka-consumer-groups \
        --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
        --describe \
        --group "$group"
}

# Reset consumer group offset
reset_offset() {
    local group=$1
    local topic=${2:-}

    if [ -z "$group" ]; then
        error "Consumer group name required"
        echo "Usage: ./scripts/dev-kafka.sh reset-offset <group-name> [topic-name]"
        exit 1
    fi

    warning "This will RESET consumer group offsets: $group"
    if [ -n "$topic" ]; then
        warning "Topic: $topic"
    else
        warning "All topics"
    fi

    read -p "Are you sure? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        info "Reset cancelled"
        exit 0
    fi

    info "Resetting consumer group offset..."

    if [ -n "$topic" ]; then
        docker exec -t "$KAFKA_CONTAINER" kafka-consumer-groups \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --group "$group" \
            --topic "$topic" \
            --reset-offsets \
            --to-earliest \
            --execute
    else
        docker exec -t "$KAFKA_CONTAINER" kafka-consumer-groups \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --group "$group" \
            --all-topics \
            --reset-offsets \
            --to-earliest \
            --execute
    fi

    success "Consumer group offset reset"
}

# Create default topics
create_default_topics() {
    info "Creating default CliLens.AI topics..."

    local topics=(
        "orchestrator_commands"
        "orchestrator_responses"
        "discovery_queue"
        "fact_checking_queue"
        "content_creation_queue"
        "video_queue"
        "publication_queue"
        "workflow_events"
    )

    for topic in "${topics[@]}"; do
        if docker exec -t "$KAFKA_CONTAINER" kafka-topics \
            --bootstrap-server localhost:$KAFKA_INTERNAL_PORT \
            --list | grep -q "^$topic$"; then
            info "Topic already exists: $topic"
        else
            create_topic "$topic"
        fi
    done

    success "All default topics created"
}

# Main script
main() {
    check_dependencies

    local command=${1:-list}

    case $command in
        list)
            list_topics
            ;;
        create)
            create_topic "$2"
            ;;
        delete)
            delete_topic "$2"
            ;;
        describe)
            describe_topic "$2"
            ;;
        send)
            send_message "$2" "$3"
            ;;
        consume)
            consume_messages "$2" "$3"
            ;;
        lag)
            check_lag "$2"
            ;;
        reset-offset)
            reset_offset "$2" "$3"
            ;;
        init|setup)
            create_default_topics
            ;;
        *)
            error "Unknown command: $command"
            echo "Usage: ./scripts/dev-kafka.sh [list|create|delete|describe|send|consume|lag|reset-offset|init]"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
