#!/bin/bash

################################################################################
# Database Migration Management Tool
#
# Comprehensive tool for managing reputation system database migrations:
# - Apply migrations
# - Rollback migrations
# - Validate schema
# - Generate migration reports
# - Backup and restore
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATABASE_PATH="${DATABASE_PATH:-data/architect.db}"
MIGRATION_DIR="${PROJECT_ROOT}/migrations"
BACKUP_DIR="${BACKUP_DIR:-data/backups}"
LOG_FILE="${LOG_FILE:-/tmp/migrations.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

################################################################################
# Logging
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $@" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $@" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $@" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $@" >&2 | tee -a "$LOG_FILE"
}

################################################################################
# Migration Operations
################################################################################

list_migrations() {
    log_info "Available migrations:"
    echo ""

    if [[ ! -d "$MIGRATION_DIR" ]]; then
        log_error "Migration directory not found: $MIGRATION_DIR"
        return 1
    fi

    local count=0
    for migration in $(ls -1 "$MIGRATION_DIR"/*_phase3*.sql 2>/dev/null | sort); do
        local filename=$(basename "$migration")
        local filesize=$(stat -f%z "$migration" 2>/dev/null || stat -c%s "$migration" 2>/dev/null)
        local lines=$(wc -l < "$migration")

        echo "  [$((++count))] $filename"
        echo "      Size: $(numfmt --to=iec $filesize 2>/dev/null || echo $filesize bytes)"
        echo "      Lines: $lines"
        echo ""
    done

    if [[ $count -eq 0 ]]; then
        log_warning "No migrations found in $MIGRATION_DIR"
        return 1
    fi

    log_success "Found $count migrations"
}

check_applied_migrations() {
    log_info "Checking applied migrations..."

    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_warning "Database does not exist: $DATABASE_PATH"
        return 0
    fi

    # Check if migration tracking table exists
    if ! sqlite3 "$DATABASE_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';" | grep -q "schema_migrations"; then
        log_info "Migration tracking table does not exist, creating..."
        sqlite3 "$DATABASE_PATH" << 'EOF'
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF
    fi

    # Show applied migrations
    echo ""
    log_info "Applied migrations:"
    sqlite3 "$DATABASE_PATH" << EOF
SELECT
    ROW_NUMBER() OVER (ORDER BY applied_at) as id,
    name,
    applied_at
FROM schema_migrations
ORDER BY applied_at;
EOF

    # Show migration count
    local count=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM schema_migrations")
    log_success "Total applied migrations: $count"
}

validate_schema() {
    log_info "Validating database schema..."

    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_error "Database not found: $DATABASE_PATH"
        return 1
    fi

    # Check critical tables
    local tables=(
        "appeals"
        "appeal_negotiation_messages"
        "ml_predictions"
        "reputation_scores"
        "user_analytics_summary"
        "appeal_status_changes"
        "appeal_notifications"
    )

    local missing=0
    for table in "${tables[@]}"; do
        if sqlite3 "$DATABASE_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" | grep -q "$table"; then
            local columns=$(sqlite3 "$DATABASE_PATH" "PRAGMA table_info($table)" | wc -l)
            log_success "✓ Table: $table ($columns columns)"
        else
            log_error "✗ Missing table: $table"
            ((missing++))
        fi
    done

    # Check critical indexes
    log_info ""
    log_info "Checking indexes..."
    local index_count=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    log_success "Total indexes: $index_count"

    # Check for orphaned indexes
    local orphaned=$(sqlite3 "$DATABASE_PATH" "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name NOT IN (SELECT name FROM sqlite_master WHERE type='table')")
    if [[ -z "$orphaned" ]]; then
        log_success "✓ No orphaned indexes"
    else
        log_warning "Orphaned indexes detected: $orphaned"
    fi

    # Check database integrity
    log_info ""
    log_info "Running integrity check..."
    local integrity=$(sqlite3 "$DATABASE_PATH" "PRAGMA integrity_check")
    if [[ "$integrity" == "ok" ]]; then
        log_success "✓ Database integrity check passed"
    else
        log_error "✗ Integrity issues: $integrity"
        return 1
    fi

    if [[ $missing -eq 0 ]]; then
        log_success "Schema validation passed"
        return 0
    else
        log_error "Schema validation failed ($missing missing tables)"
        return 1
    fi
}

backup_before_migration() {
    log_info "Creating backup before migration..."

    mkdir -p "$BACKUP_DIR"

    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_info "Database does not exist, no backup needed"
        return 0
    fi

    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${BACKUP_DIR}/migration_backup_${timestamp}.db"

    cp "$DATABASE_PATH" "$backup_file"
    log_success "Backup created: $backup_file"

    # Keep only last 20 migration backups
    find "$BACKUP_DIR" -name "migration_backup_*.db" -type f | sort -r | tail -n +21 | xargs -r rm -v
}

apply_migration() {
    local migration_file=$1

    if [[ ! -f "$migration_file" ]]; then
        log_error "Migration file not found: $migration_file"
        return 1
    fi

    local filename=$(basename "$migration_file")

    log_info "Applying migration: $filename"

    # Create database if it doesn't exist
    mkdir -p "$(dirname "$DATABASE_PATH")"
    touch "$DATABASE_PATH"

    # Apply migration
    if sqlite3 "$DATABASE_PATH" < "$migration_file" 2>&1 | tee -a "$LOG_FILE"; then
        # Record migration
        sqlite3 "$DATABASE_PATH" "INSERT INTO schema_migrations (name) VALUES ('$filename') ON CONFLICT DO NOTHING"
        log_success "✓ Migration applied: $filename"
        return 0
    else
        log_error "✗ Migration failed: $filename"
        return 1
    fi
}

apply_all_migrations() {
    log_info "Applying all pending migrations..."

    backup_before_migration

    # Ensure migration table exists
    if [[ ! -f "$DATABASE_PATH" ]]; then
        mkdir -p "$(dirname "$DATABASE_PATH")"
        touch "$DATABASE_PATH"
    fi

    sqlite3 "$DATABASE_PATH" << 'EOF'
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

    local applied_count=0
    local failed=0

    # Apply migrations in order
    for migration_file in $(ls -1 "$MIGRATION_DIR"/*_phase3*.sql 2>/dev/null | sort); do
        local filename=$(basename "$migration_file")

        # Check if already applied
        if sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM schema_migrations WHERE name = '$filename'" | grep -q "^1$"; then
            log_warning "⊘ Already applied: $filename"
            continue
        fi

        if apply_migration "$migration_file"; then
            ((applied_count++))
        else
            ((failed++))
            log_error "Failed to apply migration: $filename"
            return 1
        fi
    done

    echo ""
    if [[ $failed -eq 0 ]]; then
        log_success "All migrations applied successfully ($applied_count new)"
        return 0
    else
        log_error "Some migrations failed ($failed failed)"
        return 1
    fi
}

rollback_migration() {
    log_warning "Rolling back is not implemented in this version"
    log_warning "To rollback, restore from backup:"
    log_warning "  cp $BACKUP_DIR/migration_backup_XXXX.db $DATABASE_PATH"
}

generate_migration_report() {
    log_info "Generating migration report..."

    local report_file="${PROJECT_ROOT}/MIGRATION_REPORT.md"

    cat > "$report_file" << EOF
# Database Migration Report

Generated: $(date)

## Applied Migrations

EOF

    if [[ -f "$DATABASE_PATH" ]]; then
        sqlite3 "$DATABASE_PATH" >> "$report_file" << 'EOSQL'
.mode markdown
SELECT
    ROW_NUMBER() OVER (ORDER BY applied_at) as "Migration #",
    name as "Migration Name",
    datetime(applied_at, 'localtime') as "Applied At"
FROM schema_migrations
ORDER BY applied_at;
EOSQL
    else
        echo "No database found" >> "$report_file"
    fi

    cat >> "$report_file" << EOF

## Schema Summary

EOF

    if [[ -f "$DATABASE_PATH" ]]; then
        sqlite3 "$DATABASE_PATH" >> "$report_file" << 'EOSQL'
.mode markdown
SELECT
    'Tables' as Type,
    COUNT(*) as Count
FROM sqlite_master
WHERE type='table' AND name NOT LIKE 'sqlite_%'
UNION ALL
SELECT
    'Indexes',
    COUNT(*)
FROM sqlite_master
WHERE type='index' AND name NOT LIKE 'sqlite_%'
UNION ALL
SELECT
    'Views',
    COUNT(*)
FROM sqlite_master
WHERE type='view';
EOSQL
    fi

    cat >> "$report_file" << EOF

## Table Breakdown

EOF

    if [[ -f "$DATABASE_PATH" ]]; then
        sqlite3 "$DATABASE_PATH" >> "$report_file" << 'EOSQL'
.mode markdown
SELECT
    name as "Table Name",
    (SELECT COUNT(*) FROM sqlite_master WHERE type='column' AND tbl_name = m.name) as "Columns",
    (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name = m.name) as "Indexes"
FROM sqlite_master m
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
EOSQL
    fi

    log_success "Migration report generated: $report_file"
}

get_db_stats() {
    log_info "Database Statistics:"
    echo ""

    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_warning "Database not found: $DATABASE_PATH"
        return 0
    fi

    # Database size
    local db_size=$(stat -f%z "$DATABASE_PATH" 2>/dev/null || stat -c%s "$DATABASE_PATH" 2>/dev/null)
    echo "Database Size: $(numfmt --to=iec $db_size 2>/dev/null || echo $db_size bytes)"

    # Table stats
    echo ""
    echo "Table Statistics:"
    sqlite3 "$DATABASE_PATH" << 'EOF'
.mode column
.headers on
SELECT
    name as "Table",
    (SELECT COUNT(*) FROM sqlite_master WHERE type='column' AND tbl_name = t.name) as "Columns",
    (SELECT COUNT(*) FROM pragma_table_info(t.name)) as "Fields"
FROM sqlite_master t
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
EOF

    # Total record counts
    echo ""
    echo "Record Counts:"
    sqlite3 "$DATABASE_PATH" << 'EOF'
.mode column
.headers on
SELECT
    name as "Table",
    COUNT(*) as "Records"
FROM (
    SELECT 'appeals' as name FROM appeals
    UNION ALL SELECT 'appeal_negotiation_messages' FROM appeal_negotiation_messages
    UNION ALL SELECT 'ml_predictions' FROM ml_predictions
    UNION ALL SELECT 'reputation_scores' FROM reputation_scores
    UNION ALL SELECT 'appeals' FROM appeals
)
GROUP BY name
ORDER BY name;
EOF
}

################################################################################
# Main
################################################################################

main() {
    case "${1:-help}" in
        list)
            list_migrations
            ;;
        status)
            check_applied_migrations
            ;;
        validate)
            validate_schema
            ;;
        apply)
            apply_all_migrations
            ;;
        apply-one)
            if [[ -z "${2:-}" ]]; then
                log_error "Migration file required: migrate apply-one <file>"
                exit 1
            fi
            apply_migration "$MIGRATION_DIR/$2"
            ;;
        backup)
            backup_before_migration
            ;;
        rollback)
            rollback_migration
            ;;
        report)
            generate_migration_report
            ;;
        stats)
            get_db_stats
            ;;
        *)
            cat << 'EOF'
Database Migration Management Tool

Usage: ./manage_migrations.sh <command> [options]

Commands:
    list              List available migrations
    status            Show applied migrations
    validate          Validate database schema
    apply             Apply all pending migrations
    apply-one <file>  Apply specific migration
    backup            Create database backup
    rollback          Rollback instructions
    report            Generate migration report
    stats             Show database statistics

Examples:
    ./manage_migrations.sh list
    ./manage_migrations.sh apply
    ./manage_migrations.sh validate
    ./manage_migrations.sh report
    ./manage_migrations.sh stats

Environment Variables:
    DATABASE_PATH     Path to database (default: data/architect.db)
    MIGRATION_DIR     Migration directory (default: migrations)
    BACKUP_DIR        Backup directory (default: data/backups)
    LOG_FILE          Log file path (default: /tmp/migrations.log)

EOF
            exit 1
            ;;
    esac
}

main "$@"
