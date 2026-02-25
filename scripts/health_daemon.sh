#!/bin/bash
#
# Health Daemon for Architect Dashboard (Port 8085)
# Monitors https://100.112.58.92:8085/health and auto-restarts if down
#
# Usage:
#   ./health_daemon.sh start    # Start daemon in background
#   ./health_daemon.sh stop     # Stop daemon
#   ./health_daemon.sh status   # Show status
#   ./health_daemon.sh check    # Run single check
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="/tmp/health_daemon_8085.pid"
LOG_FILE="/tmp/health_daemon_8085.log"

# Configuration
PORT=8085
HEALTH_URL="https://100.112.58.92:8085/health"
CHECK_INTERVAL=30  # seconds
MAX_FAILURES=3     # consecutive failures before restart
STARTUP_WAIT=5     # seconds to wait after restart

# Start command for the service
START_CMD="cd $APP_DIR && nohup python3 app.py --port $PORT --ssl > /tmp/architect_${PORT}.log 2>&1 &"

log() {
    local level="$1"
    local msg="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $msg" | tee -a "$LOG_FILE"
}

check_health() {
    local http_code
    http_code=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$HEALTH_URL" 2>/dev/null)

    if [[ "$http_code" == "200" ]]; then
        return 0
    else
        return 1
    fi
}

restart_service() {
    log "WARN" "Restarting service on port $PORT..."

    # Kill existing process
    local pid=$(lsof -ti:$PORT 2>/dev/null)
    if [[ -n "$pid" ]]; then
        log "INFO" "Killing existing process (PID: $pid)"
        kill -9 $pid 2>/dev/null
        sleep 2
    fi

    # Start service
    log "INFO" "Starting service: $START_CMD"
    eval "$START_CMD"

    # Wait for startup
    sleep $STARTUP_WAIT

    # Verify
    if check_health; then
        log "INFO" "Service restarted successfully on port $PORT"
        return 0
    else
        log "ERROR" "Service failed to start on port $PORT"
        return 1
    fi
}

run_daemon() {
    local failure_count=0

    log "INFO" "=========================================="
    log "INFO" "Health Daemon started for port $PORT"
    log "INFO" "Monitoring: $HEALTH_URL"
    log "INFO" "Check interval: ${CHECK_INTERVAL}s"
    log "INFO" "Max failures before restart: $MAX_FAILURES"
    log "INFO" "=========================================="

    while true; do
        if check_health; then
            if [[ $failure_count -gt 0 ]]; then
                log "INFO" "Service recovered (was at $failure_count failures)"
            fi
            failure_count=0
        else
            ((failure_count++))
            log "WARN" "Health check failed ($failure_count/$MAX_FAILURES)"

            if [[ $failure_count -ge $MAX_FAILURES ]]; then
                log "ERROR" "Max failures reached, triggering restart"
                if restart_service; then
                    failure_count=0
                else
                    log "ERROR" "Restart failed, will retry on next check"
                    failure_count=$((MAX_FAILURES - 1))  # Allow one more check before retry
                fi
            fi
        fi

        sleep $CHECK_INTERVAL
    done
}

start_daemon() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Health daemon already running (PID: $pid)"
            return 1
        fi
        rm -f "$PID_FILE"
    fi

    # Fork to background
    nohup "$0" _run >> "$LOG_FILE" 2>&1 &
    local daemon_pid=$!
    echo $daemon_pid > "$PID_FILE"

    echo "Health daemon started (PID: $daemon_pid)"
    echo "Log file: $LOG_FILE"
    echo "Monitoring: $HEALTH_URL"
}

stop_daemon() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            rm -f "$PID_FILE"
            echo "Health daemon stopped (PID: $pid)"
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    echo "Health daemon is not running"
}

show_status() {
    echo "=========================================="
    echo "Health Daemon Status (Port $PORT)"
    echo "=========================================="

    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Daemon: RUNNING (PID: $pid)"
        else
            echo "Daemon: STALE PID (not running)"
            rm -f "$PID_FILE"
        fi
    else
        echo "Daemon: NOT RUNNING"
    fi

    echo ""
    echo "Service Status:"
    if check_health; then
        echo "  Port $PORT: HEALTHY"
        curl -sk "$HEALTH_URL" 2>/dev/null | python3 -m json.tool 2>/dev/null || curl -sk "$HEALTH_URL"
    else
        echo "  Port $PORT: DOWN or UNHEALTHY"
    fi

    echo ""
    echo "Last 10 log entries:"
    echo "------------------------------------------"
    if [[ -f "$LOG_FILE" ]]; then
        tail -10 "$LOG_FILE"
    else
        echo "(no log file)"
    fi
    echo "=========================================="
}

single_check() {
    echo "Checking $HEALTH_URL..."
    if check_health; then
        echo "HEALTHY"
        curl -sk "$HEALTH_URL" 2>/dev/null
        echo ""
    else
        echo "UNHEALTHY or DOWN"
        echo "Attempting restart..."
        restart_service
    fi
}

# Main
case "${1:-status}" in
    start)
        start_daemon
        ;;
    stop)
        stop_daemon
        ;;
    status)
        show_status
        ;;
    check)
        single_check
        ;;
    restart)
        stop_daemon
        sleep 1
        start_daemon
        ;;
    _run)
        # Internal: run the actual daemon loop
        echo $$ > "$PID_FILE"
        trap "rm -f $PID_FILE; exit 0" SIGTERM SIGINT
        run_daemon
        ;;
    *)
        echo "Usage: $0 {start|stop|status|check|restart}"
        exit 1
        ;;
esac
