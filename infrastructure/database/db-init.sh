#!/usr/bin/env bash
# Postgres init-script. Runs once on a fresh data volume.
# Applies the full schema in dependency order so the API has every table it needs.
# Idempotent: every migration uses IF NOT EXISTS / ON CONFLICT guards.
set -euo pipefail

DB="${POSTGRES_DB:-climatenews}"
USER="${POSTGRES_USER:-postgres}"
SQL_DIR="/docker-entrypoint-initdb.d/sql"

echo "[db-init] applying core schema + migrations to $DB"

# Required extensions before any migration that uses them
psql -v ON_ERROR_STOP=1 -U "$USER" -d "$DB" <<'EOF'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOF

apply() {
  local f="$1"
  if [ -f "$f" ]; then
    echo "[db-init] >>> $f"
    # ON_ERROR_STOP=0 so an idempotent re-run is non-fatal on duplicate-key seeds
    psql -v ON_ERROR_STOP=0 -U "$USER" -d "$DB" -f "$f"
  fi
}

# Core schema first
apply "$SQL_DIR/init.sql"
apply "$SQL_DIR/02_countries_and_translations.sql"
apply "$SQL_DIR/03_users_and_subscriptions.sql"

# Numbered migrations (chat_sessions, entities, knowledge graph, etc.)
shopt -s nullglob
for f in "$SQL_DIR/migrations"/*.sql; do
  apply "$f"
done

echo "[db-init] done"
