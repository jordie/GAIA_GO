#!/bin/bash

################################################################################
# Deploy Reputation System to Production
#
# This script handles deployment of the Phase 3 reputation system with:
# - Database migration
# - Service initialization
# - Health verification
# - Rollback capability
################################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATABASE_PATH="${DATABASE_PATH:-data/architect.db}"
BACKUP_PATH="${BACKUP_PATH:-data/backups}"
MIGRATION_DIR="${PROJECT_ROOT}/migrations"
LOG_FILE="${LOG_FILE:-/tmp/reputation_deploy.log}"
ENVIRONMENT="${ENVIRONMENT:-development}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Logging Functions
################################################################################

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

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
# Utility Functions
################################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Go installation
    if ! command -v go &> /dev/null; then
        log_error "Go not found. Please install Go 1.21+"
        exit 1
    fi

    local go_version=$(go version | awk '{print $3}' | sed 's/go//')
    log_info "Go version: $go_version"

    # Check SQLite
    if ! command -v sqlite3 &> /dev/null; then
        log_warning "SQLite3 not found. Some operations may fail."
    fi

    # Check database directory
    local db_dir=$(dirname "$DATABASE_PATH")
    if [[ ! -d "$db_dir" ]]; then
        log_info "Creating database directory: $db_dir"
        mkdir -p "$db_dir"
    fi

    # Check backup directory
    if [[ ! -d "$BACKUP_PATH" ]]; then
        log_info "Creating backup directory: $BACKUP_PATH"
        mkdir -p "$BACKUP_PATH"
    fi

    log_success "Prerequisites check passed"
}

backup_database() {
    log_info "Backing up database..."

    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_info "Database does not exist yet, no backup needed"
        return 0
    fi

    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${BACKUP_PATH}/architect_${timestamp}.db.bak"

    cp "$DATABASE_PATH" "$backup_file"
    log_success "Database backed up to: $backup_file"

    # Keep only last 10 backups
    ls -t "${BACKUP_PATH}"/architect_*.db.bak 2>/dev/null | tail -n +11 | xargs -r rm
}

run_migrations() {
    log_info "Running database migrations..."

    if [[ ! -d "$MIGRATION_DIR" ]]; then
        log_error "Migration directory not found: $MIGRATION_DIR"
        exit 1
    fi

    # Apply migrations in order
    local migration_files=(
        "056_phase3_appeals_analytics.sql"
        "057_phase3_sprint3_enhancements.sql"
        "058_phase3_sprint4_advanced_features.sql"
    )

    for migration_file in "${migration_files[@]}"; do
        local migration_path="${MIGRATION_DIR}/${migration_file}"

        if [[ ! -f "$migration_path" ]]; then
            log_warning "Migration file not found: $migration_path, skipping"
            continue
        fi

        log_info "Applying migration: $migration_file"

        if sqlite3 "$DATABASE_PATH" < "$migration_path" 2>&1 | tee -a "$LOG_FILE"; then
            log_success "Migration applied: $migration_file"
        else
            log_error "Migration failed: $migration_file"
            return 1
        fi
    done

    log_success "All migrations completed"
}

verify_schema() {
    log_info "Verifying database schema..."

    # Check critical tables exist
    local tables=(
        "appeals"
        "appeal_negotiation_messages"
        "ml_predictions"
        "reputation_scores"
    )

    for table in "${tables[@]}"; do
        if sqlite3 "$DATABASE_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" | grep -q "$table"; then
            log_success "Table verified: $table"
        else
            log_error "Table not found: $table"
            return 1
        fi
    done

    # Check indexes
    log_info "Verifying indexes..."
    local index_count=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
    log_success "Index count: $index_count"

    log_success "Schema verification passed"
}

verify_services() {
    log_info "Verifying service compilation..."

    cd "$PROJECT_ROOT"

    # Test compilation of services
    if go build -v ./pkg/services/rate_limiting/... 2>&1 | tee -a "$LOG_FILE"; then
        log_success "Service compilation successful"
    else
        log_error "Service compilation failed"
        return 1
    fi
}

run_tests() {
    log_info "Running tests..."

    cd "$PROJECT_ROOT"

    # Run quick tests
    if [[ "$ENVIRONMENT" != "production" ]]; then
        if go test -short -v ./pkg/services/rate_limiting/... 2>&1 | tee -a "$LOG_FILE"; then
            log_success "Tests passed"
        else
            log_error "Tests failed"
            return 1
        fi
    fi
}

generate_config() {
    log_info "Generating configuration files..."

    # Create config directory if it doesn't exist
    local config_dir="${PROJECT_ROOT}/config"
    mkdir -p "$config_dir"

    # Generate reputation system config
    local config_file="${config_dir}/reputation_${ENVIRONMENT}.yml"

    if [[ ! -f "$config_file" ]]; then
        log_info "Generating reputation config: $config_file"
        cat > "$config_file" << 'EOF'
# Reputation System Configuration

reputation:
  # Appeal Configuration
  appeal_window_days: 30
  appeal_max_per_user_per_month: 10

  # Negotiation Configuration
  negotiation_timeout_hours: 72
  max_negotiation_messages: 1000

  # ML Prediction Configuration
  ml_model_version: "v1.0"
  ml_min_history_for_accuracy: 5
  ml_confidence_threshold: 0.60

  # Notification Configuration
  notification_enabled: true
  notification_channels:
    - email
    - in_app
    - sms

  # Analytics Configuration
  analytics_trend_days: 30
  analytics_cache_ttl_seconds: 3600

  # Performance Configuration
  batch_size: 100
  cache_enabled: true
  cache_ttl_minutes: 60

database:
  path: "data/architect.db"
  max_connections: 10
  wal_mode: true

logging:
  level: "info"
  format: "json"

monitoring:
  metrics_enabled: true
  metrics_port: 9090
  health_check_interval_seconds: 60
EOF
        log_success "Configuration generated: $config_file"
    else
        log_warning "Configuration file already exists, skipping: $config_file"
    fi
}

setup_monitoring() {
    log_info "Setting up monitoring and alerting..."

    local monitoring_dir="${PROJECT_ROOT}/config/monitoring"
    mkdir -p "$monitoring_dir"

    # Create metrics config
    local metrics_config="${monitoring_dir}/reputation_metrics.yml"
    cat > "$metrics_config" << 'EOF'
# Reputation System Metrics

metrics:
  appeal_submission_rate:
    description: "Appeals submitted per minute"
    alert_threshold: 100

  appeal_approval_rate:
    description: "Approval rate percentage"
    alert_threshold: 0.3

  negotiation_avg_duration:
    description: "Average negotiation duration in minutes"
    alert_threshold: 1440

  ml_prediction_latency:
    description: "ML prediction latency in milliseconds"
    alert_threshold: 500

  api_error_rate:
    description: "API error rate percentage"
    alert_threshold: 0.01

alerts:
  - name: "high_error_rate"
    condition: "error_rate > 0.05"
    severity: "critical"

  - name: "slow_predictions"
    condition: "ml_latency_p99 > 1000"
    severity: "warning"

  - name: "database_size"
    condition: "db_size > 1000000000"  # 1GB
    severity: "warning"

  - name: "high_appeal_volume"
    condition: "appeals_per_minute > 100"
    severity: "info"
EOF

    log_success "Monitoring configuration created: $metrics_config"

    # Create alerting rules
    local alerts_config="${monitoring_dir}/reputation_alerts.yml"
    cat > "$alerts_config" << 'EOF'
# Alert Rules for Reputation System

groups:
  - name: reputation_system
    interval: 60s
    rules:
      - alert: HighAppealErrorRate
        expr: rate(appeals_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High appeal processing error rate"

      - alert: SlowPredictionLatency
        expr: ml_prediction_latency_p99 > 1000
        for: 5m
        annotations:
          summary: "ML prediction latency exceeds threshold"

      - alert: DatabaseConnections
        expr: db_connections_active > 8
        for: 5m
        annotations:
          summary: "Database connection pool nearly full"

      - alert: NegotiationQueueBacklog
        expr: negotiation_queue_size > 1000
        for: 10m
        annotations:
          summary: "Negotiation processing queue backlog detected"
EOF

    log_success "Alert rules created: $alerts_config"
}

setup_systemd() {
    log_info "Setting up systemd service (if applicable)..."

    if [[ "$ENVIRONMENT" == "production" ]]; then
        local service_file="/etc/systemd/system/reputation-system.service"

        if [[ ! -f "$service_file" ]]; then
            log_info "Creating systemd service file..."
            # This would need sudo, so we create a template
            local template_file="${PROJECT_ROOT}/config/reputation-system.service"
            cat > "$template_file" << 'EOF'
[Unit]
Description=GAIA_GO Reputation System
After=network.target

[Service]
Type=simple
User=gaia
WorkingDirectory=/opt/gaia_go
Environment="ENVIRONMENT=production"
Environment="DATABASE_PATH=/var/lib/gaia_go/architect.db"
ExecStart=/usr/local/bin/reputation_service
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
            log_success "Systemd service template created: $template_file"
            log_warning "To install as systemd service, run: sudo cp $template_file $service_file && sudo systemctl daemon-reload"
        fi
    fi
}

health_check() {
    log_info "Performing health check..."

    # Check database connectivity
    if sqlite3 "$DATABASE_PATH" "SELECT 1" &>/dev/null; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
        return 1
    fi

    # Check critical tables have data
    local appeals_count=$(sqlite3 "$DATABASE_PATH" "SELECT COUNT(*) FROM appeals" 2>/dev/null || echo "0")
    log_success "Appeals in database: $appeals_count"

    # Check indexes are valid
    local invalid_indexes=$(sqlite3 "$DATABASE_PATH" "PRAGMA integrity_check" 2>/dev/null)
    if [[ "$invalid_indexes" == "ok" ]]; then
        log_success "Database integrity check passed"
    else
        log_warning "Database integrity check issues detected: $invalid_indexes"
    fi

    log_success "Health check passed"
}

rollback() {
    log_error "Deployment failed, initiating rollback..."

    # Find latest backup
    local latest_backup=$(ls -t "${BACKUP_PATH}"/architect_*.db.bak 2>/dev/null | head -1)

    if [[ -z "$latest_backup" ]]; then
        log_error "No backup found for rollback"
        exit 1
    fi

    log_info "Rolling back to backup: $latest_backup"
    cp "$latest_backup" "$DATABASE_PATH"

    log_success "Rollback completed"
}

################################################################################
# Main Deployment Flow
################################################################################

main() {
    log_info "========================================="
    log_info "Reputation System Deployment Started"
    log_info "========================================="
    log_info "Environment: $ENVIRONMENT"
    log_info "Database: $DATABASE_PATH"
    log_info "Log file: $LOG_FILE"

    # Track if we need to rollback
    local deployment_failed=0

    # Run deployment steps
    if check_prerequisites; then
        log_success "✓ Prerequisites verified"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && backup_database; then
        log_success "✓ Database backed up"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && run_migrations; then
        log_success "✓ Migrations applied"
    else
        deployment_failed=1
        rollback
    fi

    if [[ $deployment_failed -eq 0 ]] && verify_schema; then
        log_success "✓ Schema verified"
    else
        deployment_failed=1
        rollback
    fi

    if [[ $deployment_failed -eq 0 ]] && verify_services; then
        log_success "✓ Services compiled"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && run_tests; then
        log_success "✓ Tests passed"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && generate_config; then
        log_success "✓ Configuration generated"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && setup_monitoring; then
        log_success "✓ Monitoring setup"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && setup_systemd; then
        log_success "✓ Systemd service configured"
    else
        deployment_failed=1
    fi

    if [[ $deployment_failed -eq 0 ]] && health_check; then
        log_success "✓ Health check passed"
    else
        deployment_failed=1
        rollback
    fi

    # Final status
    if [[ $deployment_failed -eq 0 ]]; then
        log_info "========================================="
        log_success "Deployment completed successfully!"
        log_info "========================================="
        return 0
    else
        log_info "========================================="
        log_error "Deployment failed and rolled back"
        log_info "========================================="
        return 1
    fi
}

################################################################################
# Script Entry Point
################################################################################

# Handle signals for cleanup
trap 'log_error "Deployment interrupted"; rollback; exit 130' INT TERM

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --database)
            DATABASE_PATH="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            set -x
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --environment ENV        Set deployment environment (development/staging/production)"
            echo "  --database PATH          Set database path"
            echo "  --verbose               Enable verbose output"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main deployment
main
exit $?
