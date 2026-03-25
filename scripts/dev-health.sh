#!/usr/bin/env bash
# dev-health.sh - Check service health status for local development
# Usage: ./scripts/dev-health.sh [all|service-name|infra] [--watch|--export]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Health check configuration
API_GATEWAY_URL="http://localhost:5200"
FRONTEND_URL="http://localhost:5300"
ORCHESTRATION_URL="http://localhost:8001"
INGESTION_URL="http://localhost:8002"
VERIFICATION_URL="http://localhost:8003"
CONTENT_URL="http://localhost:8004"
VIDEO_URL="http://localhost:8005"

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

# Check if service is healthy via HTTP
check_http_health() {
    local name=$1
    local url=$2

    if curl -sf "$url/health" > /dev/null 2>&1; then
        success "$name is healthy"
        return 0
    else
        error "$name is not responding"
        return 1
    fi
}

# Check if container is running
check_container_health() {
    local name=$1
    local container=$2

    if docker ps | grep -q "$container.*Up"; then
        success "$name container is running"
        return 0
    else
        error "$name container is not running"
        return 1
    fi
}

# Check PostgreSQL
check_postgres() {
    local container="climatenews-postgres"

    if ! check_container_health "PostgreSQL" "$container"; then
        return 1
    fi

    # Check if accepting connections
    if docker exec -t "$container" pg_isready -U postgres > /dev/null 2>&1; then
        success "PostgreSQL is accepting connections"
        return 0
    else
        error "PostgreSQL is not accepting connections"
        return 1
    fi
}

# Check Redis
check_redis() {
    local container="climatenews-redis"

    if ! check_container_health "Redis" "$container"; then
        return 1
    fi

    # Check if responding to PING
    if docker exec -t "$container" redis-cli ping | grep -q "PONG"; then
        success "Redis is responding to PING"
        return 0
    else
        error "Redis is not responding to PING"
        return 1
    fi
}

# Check Kafka
check_kafka() {
    local container="climatenews-kafka"

    if ! check_container_health "Kafka" "$container"; then
        return 1
    fi

    # Try to list topics
    if docker exec -t "$container" kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; then
        success "Kafka broker is responding"
        return 0
    else
        error "Kafka broker is not responding"
        return 1
    fi
}

# Check infrastructure
check_infra() {
    info "Checking infrastructure services..."
    echo ""

    local healthy=true

    check_postgres || healthy=false
    check_redis || healthy=false
    check_kafka || healthy=false

    echo ""
    if [ "$healthy" = true ]; then
        success "All infrastructure services are healthy"
        return 0
    else
        error "Some infrastructure services are unhealthy"
        return 1
    fi
}

# Check API Gateway
check_api_gateway() {
    check_http_health "API Gateway" "$API_GATEWAY_URL"
}

# Check Frontend
check_frontend() {
    if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
        success "Frontend is responding"
        return 0
    else
        error "Frontend is not responding"
        return 1
    fi
}

# Check Orchestration Service
check_orchestration() {
    check_http_health "Orchestration Service" "$ORCHESTRATION_URL"
}

# Check Ingestion Service
check_ingestion() {
    check_http_health "Ingestion Service" "$INGESTION_URL"
}

# Check Verification Service
check_verification() {
    check_http_health "Verification Service" "$VERIFICATION_URL"
}

# Check Content Creation Service
check_content() {
    check_http_health "Content Creation Service" "$CONTENT_URL"
}

# Check Video Production Service
check_video() {
    check_http_health "Video Production Service" "$VIDEO_URL"
}

# Check all services
check_all() {
    info "Checking all CliLens.AI services..."
    echo ""

    local healthy=true

    # Infrastructure
    info "Infrastructure:"
    check_postgres || healthy=false
    check_redis || healthy=false
    check_kafka || healthy=false
    echo ""

    # Core services
    info "Core Services:"
    check_api_gateway || healthy=false
    check_frontend || healthy=false
    echo ""

    # Worker agents
    info "Worker Agents:"
    check_orchestration || healthy=false
    check_ingestion || healthy=false
    check_verification || healthy=false
    check_content || healthy=false
    check_video || healthy=false
    echo ""

    # Summary
    if [ "$healthy" = true ]; then
        success "All services are healthy ✨"
        return 0
    else
        error "Some services are unhealthy"
        info "Use 'docker-compose logs <service>' to investigate"
        return 1
    fi
}

# Watch mode - continuously check health
watch_health() {
    local target=$1

    while true; do
        clear
        echo "=== CliLens.AI Health Monitor ==="
        echo "Press Ctrl+C to exit"
        echo ""

        case $target in
            all)
                check_all
                ;;
            infra)
                check_infra
                ;;
            *)
                check_service "$target"
                ;;
        esac

        echo ""
        echo "Next check in 5 seconds..."
        sleep 5
    done
}

# Export health report to JSON
export_health() {
    local output_file=$1

    info "Generating health report..."

    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local report="{"
    report+="\"timestamp\":\"$timestamp\","
    report+="\"services\":{"

    # Check each service and build JSON
    local services=(
        "postgres:check_postgres"
        "redis:check_redis"
        "kafka:check_kafka"
        "api-gateway:check_api_gateway"
        "frontend:check_frontend"
        "orchestration:check_orchestration"
        "ingestion:check_ingestion"
        "verification:check_verification"
        "content:check_content"
        "video:check_video"
    )

    local first=true
    for service_check in "${services[@]}"; do
        IFS=':' read -r service check_func <<< "$service_check"

        if [ "$first" = false ]; then
            report+=","
        fi
        first=false

        if $check_func > /dev/null 2>&1; then
            report+="\"$service\":{\"status\":\"healthy\"}"
        else
            report+="\"$service\":{\"status\":\"unhealthy\"}"
        fi
    done

    report+="}}"

    # Write to file
    echo "$report" | jq '.' > "$output_file"

    success "Health report saved to: $output_file"
}

# Check specific service
check_service() {
    local service=$1

    case $service in
        postgres|postgresql)
            check_postgres
            ;;
        redis)
            check_redis
            ;;
        kafka)
            check_kafka
            ;;
        api|api-gateway)
            check_api_gateway
            ;;
        frontend|web)
            check_frontend
            ;;
        orchestration)
            check_orchestration
            ;;
        ingestion)
            check_ingestion
            ;;
        verification)
            check_verification
            ;;
        content)
            check_content
            ;;
        video)
            check_video
            ;;
        *)
            error "Unknown service: $service"
            echo "Available services: postgres, redis, kafka, api-gateway, frontend, orchestration, ingestion, verification, content, video"
            exit 1
            ;;
    esac
}

# Main script
main() {
    local target=${1:-all}
    local flag=${2:-}

    case $flag in
        --watch|-w)
            watch_health "$target"
            ;;
        --export|-e)
            local output_file=${3:-health-report.json}
            export_health "$output_file"
            ;;
        *)
            case $target in
                all)
                    check_all
                    ;;
                infra|infrastructure)
                    check_infra
                    ;;
                *)
                    check_service "$target"
                    ;;
            esac
            ;;
    esac
}

# Run main function
main "$@"
