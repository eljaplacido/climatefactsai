#!/usr/bin/env bash
# dev-db.sh - Manage PostgreSQL database for local development
# Usage: ./scripts/dev-db.sh [migrate|rollback|seed|reset|backup|restore|shell|status]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database configuration
DB_CONTAINER="climatenews-postgres"
DB_NAME="${POSTGRES_DB:-climatenews}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5433}"

# Directories
MIGRATIONS_DIR="database/migrations"
SEEDS_DIR="scripts/sql"
BACKUPS_DIR="backups"

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

    if ! docker ps | grep -q "$DB_CONTAINER"; then
        error "PostgreSQL container is not running"
        info "Start with: ./scripts/dev-start.sh infra"
        exit 1
    fi

    success "Dependencies checked"
}

# Run migrations
run_migrations() {
    info "Running database migrations..."

    if [ ! -d "$MIGRATIONS_DIR" ]; then
        warning "Migrations directory not found: $MIGRATIONS_DIR"
        info "Creating migrations directory..."
        mkdir -p "$MIGRATIONS_DIR"
    fi

    # Check if there are migration files
    if [ -z "$(ls -A $MIGRATIONS_DIR/*.sql 2>/dev/null)" ]; then
        warning "No migration files found in $MIGRATIONS_DIR"
        return
    fi

    # Apply migrations in order
    for migration in "$MIGRATIONS_DIR"/*.sql; do
        if [ -f "$migration" ]; then
            local filename=$(basename "$migration")
            info "Applying migration: $filename"

            docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$migration"
            success "Applied: $filename"
        fi
    done

    success "All migrations applied"
}

# Rollback last migration
rollback_migration() {
    info "Rolling back last migration..."

    if [ ! -d "$MIGRATIONS_DIR/rollback" ]; then
        error "Rollback directory not found: $MIGRATIONS_DIR/rollback"
        exit 1
    fi

    # Find the latest rollback script
    local latest_rollback=$(ls -t "$MIGRATIONS_DIR/rollback"/*.sql 2>/dev/null | head -1)

    if [ -z "$latest_rollback" ]; then
        warning "No rollback scripts found"
        return
    fi

    local filename=$(basename "$latest_rollback")
    info "Applying rollback: $filename"

    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$latest_rollback"
    success "Rollback applied: $filename"
}

# Seed database
seed_database() {
    info "Seeding database with test data..."

    if [ ! -d "$SEEDS_DIR" ]; then
        warning "Seeds directory not found: $SEEDS_DIR"
        info "Creating seeds directory..."
        mkdir -p "$SEEDS_DIR"
    fi

    # Check if there are seed files
    if [ -z "$(ls -A $SEEDS_DIR/*.sql 2>/dev/null)" ]; then
        warning "No seed files found in $SEEDS_DIR"
        return
    fi

    # Apply seeds in order
    for seed in "$SEEDS_DIR"/*.sql; do
        if [ -f "$seed" ]; then
            local filename=$(basename "$seed")
            info "Applying seed: $filename"

            docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$seed"
            success "Applied: $filename"
        fi
    done

    success "Database seeded"
}

# Reset database
reset_database() {
    local force=${1:-}

    if [ "$force" != "--force" ]; then
        warning "This will DROP the database and recreate it!"
        read -p "Are you sure? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
            info "Reset cancelled"
            exit 0
        fi
    fi

    info "Resetting database..."

    # Drop database
    info "Dropping database..."
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"

    # Create database
    info "Creating database..."
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

    success "Database reset"

    # Run migrations
    run_migrations

    # Seed database
    seed_database

    success "Database reset complete"
}

# Backup database
backup_database() {
    info "Creating database backup..."

    # Create backups directory if it doesn't exist
    mkdir -p "$BACKUPS_DIR"

    # Generate backup filename with timestamp
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUPS_DIR/${DB_NAME}_${timestamp}.sql"

    # Create backup
    docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" > "$backup_file"

    success "Backup created: $backup_file"

    # Compress backup
    gzip "$backup_file"
    success "Backup compressed: ${backup_file}.gz"

    # Show backup size
    local size=$(du -h "${backup_file}.gz" | cut -f1)
    info "Backup size: $size"
}

# Restore database from backup
restore_database() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        error "Backup file path required"
        echo "Usage: ./scripts/dev-db.sh restore backups/climatenews_20251121.sql.gz"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
        exit 1
    fi

    warning "This will restore the database from: $backup_file"
    read -p "Are you sure? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        info "Restore cancelled"
        exit 0
    fi

    info "Restoring database from backup..."

    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        info "Decompressing backup..."
        gunzip -k "$backup_file"
        backup_file="${backup_file%.gz}"
    fi

    # Drop and recreate database
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

    # Restore backup
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$backup_file"

    success "Database restored from: $backup_file"
}

# Open psql shell
open_shell() {
    info "Opening PostgreSQL shell..."
    info "Database: $DB_NAME"
    info "User: $DB_USER"
    info "(Type \\q to exit)"
    echo ""

    docker exec -it "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
}

# Show database status
show_status() {
    info "Database Status"
    echo ""

    # Connection info
    echo "Connection:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    echo ""

    # Database size
    echo "Size:"
    docker exec -t "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME')) AS size;"
    echo ""

    # Table count
    echo "Tables:"
    docker exec -t "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
    echo ""

    # List tables
    echo "Table List:"
    docker exec -t "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
}

# Main script
main() {
    check_dependencies

    local command=${1:-status}

    case $command in
        migrate)
            run_migrations
            ;;
        rollback)
            rollback_migration
            ;;
        seed)
            seed_database
            ;;
        reset)
            reset_database ${2:-}
            ;;
        backup)
            backup_database
            ;;
        restore)
            restore_database "$2"
            ;;
        shell)
            open_shell
            ;;
        status)
            show_status
            ;;
        *)
            error "Unknown command: $command"
            echo "Usage: ./scripts/dev-db.sh [migrate|rollback|seed|reset|backup|restore|shell|status]"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
