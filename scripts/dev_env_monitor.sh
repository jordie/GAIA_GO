#!/bin/bash

#################################################################################
# Phase 7: Development Environment Monitoring Script
#
# Monitors health and status of all 5 development environments:
# - Process status (running/stopped)
# - Database sizes
# - Git status (ahead/behind/dirty)
# - Port availability
# - Resource usage
# - Output summary report
#
# Usage:
#   ./dev_env_monitor.sh              # Full health check
#   ./dev_env_monitor.sh --quick      # Quick status only
#   ./dev_env_monitor.sh --watch      # Live updating dashboard
#   ./dev_env_monitor.sh <env_num>    # Check specific environment
#   ./dev_env_monitor.sh --report     # Detailed report
#################################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BASE_DIR="$(dirname "$PROJECT_ROOT")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Helper functions
port_is_listening() {
    local port=$1
    nc -z localhost "$port" 2>/dev/null && return 0 || return 1
}

get_process_status() {
    local env_num=$1
    local sub_env="${2:-dev}"
    local pid_file="/tmp/architect_dashboard_dev${env_num}_${sub_env}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "running"
            return 0
        else
            echo "stopped (stale pid)"
            return 1
        fi
    else
        echo "stopped"
        return 1
    fi
}

# Initialize counters
total_dirs=0
healthy_dirs=0
unhealthy_dirs=0
total_running=0
total_stopped=0
total_dirty=0
total_size=0

quick_status() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Development Environment Quick Status                          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    for i in $(seq 1 5); do
        env_name="dev$i"
        env_dir="$BASE_DIR/architect-$env_name"

        if [ ! -d "$env_dir" ]; then
            echo -e "${CYAN}${env_name}${NC}: ${RED}NOT CREATED${NC}"
            continue
        fi

        cd "$env_dir" 2>/dev/null || continue
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

        port=$((8080 + i))
        if port_is_listening "$port"; then
            status="${GREEN}RUNNING${NC}"
        else
            status="${YELLOW}STOPPED${NC}"
        fi

        echo -e "${CYAN}${env_name}${NC}: $status [${MAGENTA}${branch}${NC}]"
    done
    echo ""
}

full_check() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Full Development Environment Health Check                    ║${NC}"
    echo -e "${BLUE}║  $(date '+%Y-%m-%d %H:%M:%S')                                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

    # Check each development environment
    for i in $(seq 1 5); do
        env_name="dev$i"
        env_dir="architect-$env_name"
        env_path="$BASE_DIR/$env_dir"

        echo ""
        echo -e "${MAGENTA}Environment: architect-dev${i}${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        ((total_dirs++))

        if [ ! -d "$env_path" ]; then
            log_error "Directory not found: $env_path"
            ((unhealthy_dirs++))
            continue
        fi

        log_success "Directory exists: $env_path"
        cd "$env_path"

        # Git Status
        echo ""
        echo "Git Status:"

        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        echo "  Branch: $BRANCH"

        AHEAD_BEHIND=$(git rev-list --left-right --count @{u}...HEAD 2>/dev/null || echo "0 0")
        BEHIND=$(echo $AHEAD_BEHIND | cut -d' ' -f1)
        AHEAD=$(echo $AHEAD_BEHIND | cut -d' ' -f2)

        if [ "$BEHIND" -eq 0 ] && [ "$AHEAD" -eq 0 ]; then
            log_success "Branch is up-to-date with remote"
        elif [ "$BEHIND" -gt 0 ]; then
            log_warn "Branch is behind by $BEHIND commits"
        elif [ "$AHEAD" -gt 0 ]; then
            log_warn "Branch is ahead by $AHEAD commits"
        fi

        if [ -z "$(git status --porcelain)" ]; then
            log_success "Working tree is clean"
            DIRTY=0
        else
            DIRTY_COUNT=$(git status --porcelain | wc -l)
            log_warn "Working tree has $DIRTY_COUNT uncommitted changes"
            ((total_dirty += DIRTY_COUNT))
            DIRTY=$DIRTY_COUNT
        fi

        LAST_COMMIT=$(git log -1 --format="%ar" 2>/dev/null || echo "unknown")
        echo "  Last commit: $LAST_COMMIT"

        # Sub-Environments
        echo ""
        echo "Sub-Environments:"

        for env_type in dev qa staging; do
            case $env_type in
                dev)    port=$((8080 + i));;
                qa)     port=$((8090 + i));;
                staging) port=$((8100 + i));;
            esac

            if port_is_listening "$port"; then
                log_success "$env_type (port $port) is running"
                ((total_running++))
            else
                log_warn "$env_type (port $port) is stopped"
                ((total_stopped++))
            fi

            if [ -f "data/$env_type/architect.db" ]; then
                DB_SIZE=$(du -h "data/$env_type/architect.db" 2>/dev/null | cut -f1)
                echo "    Database: $DB_SIZE"
                ((total_size++))
            fi
        done

        # Worker Session
        echo ""
        echo "Worker Session:"

        WORKER_SESSION="${env_name}_worker"

        if tmux list-sessions -F "#{session_name}" 2>/dev/null | grep -q "^${WORKER_SESSION}$"; then
            log_success "Worker session '$WORKER_SESSION' is active"
        else
            log_warn "Worker session '$WORKER_SESSION' is inactive"
        fi

        # Health Summary
        if [ "$DIRTY" -eq 0 ] && [ "$BEHIND" -eq 0 ] && [ "$AHEAD" -le 1 ]; then
            log_success "Environment is healthy"
            ((healthy_dirs++))
        else
            log_warn "Environment has issues"
            ((unhealthy_dirs++))
        fi
    done

    # Overall Summary
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Overall Health Summary                                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo "Directories:"
    echo "  Total: $total_dirs"
    echo -e "  Healthy: ${GREEN}$healthy_dirs${NC}"
    echo -e "  Issues: ${YELLOW}$unhealthy_dirs${NC}"
    echo ""

    echo "Sub-Environments:"
    echo -e "  Running: ${GREEN}$total_running${NC}"
    echo -e "  Stopped: ${YELLOW}$total_stopped${NC}"
    echo ""

    echo "Code Status:"
    echo -e "  Uncommitted Changes: ${YELLOW}$total_dirty${NC}"
    echo ""

    if [ $unhealthy_dirs -eq 0 ]; then
        echo -e "${GREEN}✓ All environments are healthy!${NC}"
        echo ""
        return 0
    else
        echo -e "${YELLOW}! $unhealthy_dirs environment(s) need attention${NC}"
        echo ""
        return 1
    fi
}

live_dashboard() {
    while true; do
        clear
        quick_status

        echo -e "${BLUE}Active tmux Sessions:${NC}"
        tmux list-sessions 2>/dev/null | grep -E "(dev|pr_)" || echo "No active sessions"

        echo ""
        echo "Press Ctrl+C to stop. Updates every 5 seconds..."
        sleep 5
    done
}

generate_report() {
    local report_file="$BASE_DIR/data/reports/dev_env_report_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p "$BASE_DIR/data/reports"

    {
        echo "Development Environment Report"
        echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "System Information:"
        echo "  Base Directory: $BASE_DIR"
        echo ""

        full_check
    } | tee "$report_file"

    log_success "Report saved to: $report_file"
}

# Main
case "${1:-full}" in
    quick|--quick)
        quick_status
        ;;
    watch|--watch)
        live_dashboard
        ;;
    report|--report)
        generate_report
        ;;
    full)
        full_check
        ;;
    *)
        if [[ "$1" =~ ^[1-5]$ ]]; then
            echo -e "${MAGENTA}Environment: architect-dev${1}${NC}"
            cd "$BASE_DIR/architect-dev$1" && full_check
        else
            echo "Usage: $0 [full|quick|watch|report|1-5]"
            echo ""
            echo "Examples:"
            echo "  $0              # Full health check"
            echo "  $0 --quick      # Quick status"
            echo "  $0 --watch      # Live dashboard"
            echo "  $0 --report     # Detailed report"
            echo "  $0 1            # Check dev1 only"
            exit 1
        fi
        ;;
esac
