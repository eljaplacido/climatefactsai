#!/usr/bin/env bash
# dev-test.sh - Run tests with various configurations
# Usage: ./scripts/dev-test.sh [all|unit|integration|e2e|service|file] [target] [--coverage|--watch]

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
    if ! command -v pytest &> /dev/null; then
        error "pytest is not installed"
        info "Install with: pip install -r requirements.txt"
        exit 1
    fi

    success "Dependencies checked"
}

# Check infrastructure
check_infra() {
    info "Checking infrastructure services..."

    # Check if containers are running
    if ! docker-compose ps postgres | grep -q "Up"; then
        warning "PostgreSQL is not running"
        info "Start with: ./scripts/dev-start.sh infra"
        return 1
    fi

    if ! docker-compose ps redis | grep -q "Up"; then
        warning "Redis is not running"
        info "Start with: ./scripts/dev-start.sh infra"
        return 1
    fi

    if ! docker-compose ps kafka | grep -q "Up"; then
        warning "Kafka is not running"
        info "Start with: ./scripts/dev-start.sh infra"
        return 1
    fi

    success "Infrastructure is running"
    return 0
}

# Run all tests
run_all_tests() {
    local flags=$1

    info "Running all tests..."
    pytest tests/ $flags
}

# Run unit tests
run_unit_tests() {
    local flags=$1

    info "Running unit tests..."
    pytest tests/ -m "not integration and not e2e" $flags
}

# Run integration tests
run_integration_tests() {
    local flags=$1

    if ! check_infra; then
        error "Integration tests require infrastructure services"
        exit 1
    fi

    info "Running integration tests..."
    pytest tests/ -m integration $flags
}

# Run end-to-end tests
run_e2e_tests() {
    local flags=$1

    if ! check_infra; then
        error "E2E tests require infrastructure services"
        exit 1
    fi

    # Check if all services are running
    if ! docker-compose ps | grep -q "orchestration-service.*Up"; then
        warning "Orchestration service is not running"
        info "Start with: ./scripts/dev-start.sh all"
        exit 1
    fi

    info "Running end-to-end tests..."
    pytest tests/ -m e2e $flags
}

# Run tests for specific service
run_service_tests() {
    local service=$1
    local flags=$2

    case $service in
        orchestration)
            info "Running orchestration service tests..."
            pytest tests/services/test_orchestration.py $flags
            ;;
        ingestion)
            info "Running ingestion service tests..."
            pytest tests/services/test_ingestion.py $flags
            ;;
        verification)
            info "Running verification service tests..."
            pytest tests/services/test_verification.py $flags
            ;;
        content)
            info "Running content creation service tests..."
            pytest tests/services/test_content_creation.py $flags
            ;;
        video)
            info "Running video production service tests..."
            pytest tests/services/test_video_production.py $flags
            ;;
        shared)
            info "Running shared utilities tests..."
            pytest tests/shared/ $flags
            ;;
        *)
            error "Unknown service: $service"
            echo "Available services: orchestration, ingestion, verification, content, video, shared"
            exit 1
            ;;
    esac
}

# Run specific test file
run_test_file() {
    local file=$1
    local flags=$2

    if [ ! -f "$file" ]; then
        error "Test file not found: $file"
        exit 1
    fi

    info "Running test file: $file"
    pytest "$file" $flags
}

# Parse flags
parse_flags() {
    local args=("$@")
    local flags=""

    for arg in "${args[@]}"; do
        case $arg in
            --coverage|-c)
                flags="$flags --cov=src/backend --cov-report=html --cov-report=term"
                ;;
            --watch|-w)
                flags="$flags -f"
                ;;
            --verbose|-v)
                flags="$flags -v"
                ;;
            --failed|-f)
                flags="$flags --lf"  # Run last failed tests
                ;;
            --exitfirst|-x)
                flags="$flags -x"  # Exit on first failure
                ;;
        esac
    done

    echo "$flags"
}

# Main script
main() {
    check_dependencies

    local test_type=${1:-all}
    local target=${2:-}

    # Parse additional flags
    shift 1 || true
    shift 1 2>/dev/null || true
    local flags=$(parse_flags "$@")

    # Add verbose by default
    if [[ ! "$flags" =~ "-v" ]]; then
        flags="$flags -v"
    fi

    case $test_type in
        all)
            run_all_tests "$flags"
            ;;
        unit)
            run_unit_tests "$flags"
            ;;
        integration)
            run_integration_tests "$flags"
            ;;
        e2e)
            run_e2e_tests "$flags"
            ;;
        service)
            if [ -z "$target" ]; then
                error "Service name required"
                echo "Usage: ./scripts/dev-test.sh service [orchestration|ingestion|verification|content|video|shared]"
                exit 1
            fi
            run_service_tests "$target" "$flags"
            ;;
        file)
            if [ -z "$target" ]; then
                error "Test file path required"
                echo "Usage: ./scripts/dev-test.sh file path/to/test_file.py"
                exit 1
            fi
            run_test_file "$target" "$flags"
            ;;
        *)
            error "Unknown test type: $test_type"
            echo "Usage: ./scripts/dev-test.sh [all|unit|integration|e2e|service|file] [target] [--coverage|--watch|--verbose|--failed|--exitfirst]"
            exit 1
            ;;
    esac

    success "Tests completed"

    # Show coverage report if generated
    if [[ "$flags" =~ "--cov" ]]; then
        info "Coverage report saved to: htmlcov/index.html"
        info "Open with: open htmlcov/index.html (Mac) or start htmlcov/index.html (Windows)"
    fi
}

# Run main function
main "$@"
