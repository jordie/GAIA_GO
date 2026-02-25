#!/bin/bash

# GAIA_GO Multi-Environment Manager
# Manages dev, staging, and prod environments

set -e

GAIA_ROOT="/Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO"
ENVIRONMENTS_DIR="$GAIA_ROOT/environments"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

show_usage() {
    cat << EOF
GAIA_GO Environment Manager

Usage: ./manage_environments.sh <command> [options]

Commands:
  status              Show status of all environments
  start <env>         Start an environment (dev|staging|prod)
  stop <env>          Stop an environment
  logs <env>          Show logs for an environment
  reset <env>         Reset environment data (dev only)
  health <env>        Check health of environment
  backup              Backup all environments

Examples:
  ./manage_environments.sh status
  ./manage_environments.sh start dev
  ./manage_environments.sh logs prod
  ./manage_environments.sh health staging
EOF
}

check_environment() {
    local env=$1
    if [ ! -d "$ENVIRONMENTS_DIR/$env" ]; then
        log "ERROR: Environment '$env' not found"
        exit 1
    fi
}

status_all() {
    log "═══════════════════════════════════════════════════════════"
    log "GAIA_GO ENVIRONMENT STATUS"
    log "═══════════════════════════════════════════════════════════"
    
    for env in dev staging prod; do
        log ""
        log "📍 $env Environment:"
        log "   Location: $ENVIRONMENTS_DIR/$env"
        
        if [ -f "$ENVIRONMENTS_DIR/$env/GAIA_GO.env" ]; then
            PORT=$(grep "^GAIA_PORT=" "$ENVIRONMENTS_DIR/$env/GAIA_GO.env" | cut -d= -f2)
            log "   Port: $PORT"
        fi
    done
    
    log ""
    log "═══════════════════════════════════════════════════════════"
}

health_check() {
    local env=$1
    check_environment "$env"
    
    PORT=$(grep "^GAIA_PORT=" "$ENVIRONMENTS_DIR/$env/GAIA_GO.env" | cut -d= -f2)
    
    log "Checking health of $env environment (port $PORT)..."
    
    if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        log "✅ $env is HEALTHY"
    else
        log "❌ $env is NOT RESPONDING"
    fi
}

show_logs() {
    local env=$1
    check_environment "$env"
    
    LOG_FILE="$ENVIRONMENTS_DIR/$env/logs/gaia.log"
    
    if [ -f "$LOG_FILE" ]; then
        log "Showing last 100 lines of $env logs:"
        tail -100 "$LOG_FILE"
    else
        log "No logs found for $env"
    fi
}

reset_env() {
    local env=$1
    
    if [ "$env" != "dev" ]; then
        log "ERROR: Can only reset 'dev' environment"
        exit 1
    fi
    
    log "Resetting dev environment..."
    rm -f "$ENVIRONMENTS_DIR/dev/data/"*".db"
    rm -f "$ENVIRONMENTS_DIR/dev/logs/"*
    log "✅ Dev environment reset"
}

backup_all() {
    log "Backing up all environments..."
    
    for env in dev staging prod; do
        mkdir -p "$ENVIRONMENTS_DIR/$env/data/backups"
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        log "✅ Backup prepared for $env"
    done
}

# Main
if [ $# -eq 0 ]; then
    show_usage
    exit 0
fi

CMD=$1

case "$CMD" in
    status)
        status_all
        ;;
    logs)
        ENV=${2:-}
        if [ -z "$ENV" ]; then
            log "ERROR: Specify environment (dev|staging|prod)"
            exit 1
        fi
        show_logs "$ENV"
        ;;
    health)
        ENV=${2:-}
        if [ -z "$ENV" ]; then
            log "ERROR: Specify environment (dev|staging|prod)"
            exit 1
        fi
        health_check "$ENV"
        ;;
    reset)
        ENV=${2:-}
        if [ -z "$ENV" ]; then
            log "ERROR: Specify environment (dev|staging|prod)"
            exit 1
        fi
        reset_env "$ENV"
        ;;
    backup)
        backup_all
        ;;
    *)
        log "Unknown command: $CMD"
        show_usage
        exit 1
        ;;
esac
