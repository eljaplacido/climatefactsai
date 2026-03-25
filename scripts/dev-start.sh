#!/usr/bin/env bash
# dev-start.sh - Start services for local development
# Usage: ./scripts/dev-start.sh [service|all|infra] [--logs]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi

    success "Dependencies checked"
}

# Start infrastructure services
start_infra() {
    info "Starting infrastructure services..."
    docker-compose up -d postgres redis kafka zookeeper

    # Wait for services to be ready
    info "Waiting for infrastructure to be ready..."
    sleep 5

    # Check PostgreSQL
    until docker-compose exec -T postgres pg_isready -U postgres &> /dev/null; do
        echo -n "."
        sleep 1
    done
    echo ""
    success "PostgreSQL is ready"

    # Check Redis
    until docker-compose exec -T redis redis-cli ping &> /dev/null; do
        echo -n "."
        sleep 1
    done
    echo ""
    success "Redis is ready"

    # Check Kafka (takes longer)
    info "Waiting for Kafka (this may take 30s)..."
    sleep 30
    success "Kafka should be ready"

    success "Infrastructure services started"
}

# Start all services
start_all() {
    info "Starting all services..."
    docker-compose up -d

    success "All services started"
    info "Services available at:"
    echo "  - API Gateway: http://localhost:5200"
    echo "  - Frontend: http://localhost:5300"
    echo "  - Grafana: http://localhost:3001"
    echo "  - Prometheus: http://localhost:5090"
    echo "  - Jaeger: http://localhost:5686"
}

# Start specific service
start_service() {
    local service=$1

    case $service in
        orchestration)
            info "Starting orchestration service..."
            docker-compose up -d orchestration-service
            ;;
        ingestion)
            info "Starting ingestion service..."
            docker-compose up -d ingestion-service
            ;;
        verification)
            info "Starting verification service..."
            docker-compose up -d verification-service
            ;;
        content)
            info "Starting content creation service..."
            docker-compose up -d content-service
            ;;
        video)
            info "Starting video production service..."
            docker-compose up -d video-service
            ;;
        api|api-gateway)
            info "Starting API gateway..."
            docker-compose up -d api-gateway
            ;;
        frontend|web)
            info "Starting frontend..."
            docker-compose up -d frontend
            ;;
        monitoring)
            info "Starting monitoring stack..."
            docker-compose up -d grafana prometheus jaeger
            ;;
        *)
            error "Unknown service: $service"
            echo "Available services: orchestration, ingestion, verification, content, video, api-gateway, frontend, monitoring"
            exit 1
            ;;
    esac

    success "$service service started"
}

# Show logs
show_logs() {
    local target=$1

    if [ "$target" = "all" ]; then
        docker-compose logs -f
    elif [ "$target" = "infra" ]; then
        docker-compose logs -f postgres redis kafka
    else
        docker-compose logs -f "$target-service" 2>/dev/null || docker-compose logs -f "$target"
    fi
}

# Main script
main() {
    check_dependencies

    local target=${1:-all}
    local show_logs_flag=${2:-}

    case $target in
        infra|infrastructure)
            start_infra
            ;;
        all)
            start_infra
            start_all
            ;;
        *)
            start_infra
            start_service "$target"
            ;;
    esac

    if [ "$show_logs_flag" = "--logs" ] || [ "$show_logs_flag" = "-l" ]; then
        info "Showing logs (Ctrl+C to exit)..."
        show_logs "$target"
    else
        info "Use './scripts/dev-start.sh $target --logs' to view logs"
        info "Use 'docker-compose ps' to see running services"
        info "Use 'docker-compose logs -f [service]' to view specific service logs"
    fi
}

# Run main function
main "$@"
