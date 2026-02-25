#!/bin/bash
# Watchdog for Architect Dashboard environments
# Uses env_manager.py for start/stop operations
# Monitors all environments defined in environments.json

APP_DIR="/Users/jgirmay/Desktop/gitrepo/pyWork/architect"
ENV_MANAGER="$APP_DIR/env_manager.py"
CONFIG="$APP_DIR/data/environments.json"
LOG="/tmp/watchdog_architect.log"
ALERT_SCRIPT="$APP_DIR/scripts/alert.sh"
CHECK_INTERVAL=60  # seconds

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

alert() {
    local level="$1"
    local message="$2"
    if [ -x "$ALERT_SCRIPT" ]; then
        "$ALERT_SCRIPT" --$level "Architect" "$message"
    fi
}

check_health() {
    local port="$1"
    response=$(curl -sk --max-time 10 "https://localhost:${port}/health" 2>/dev/null)
    if echo "$response" | grep -q '"status":"healthy"'; then
        return 0
    fi
    return 1
}

restart_env() {
    local env_name="$1"
    log "Restarting $env_name via env_manager..."
    cd "$APP_DIR"
    python3 "$ENV_MANAGER" restart "$env_name"
    return $?
}

get_envs() {
    # Parse environments from JSON config
    python3 -c "
import json
with open('$CONFIG') as f:
    config = json.load(f)
for name, env in config.get('architect_envs', {}).items():
    print(f\"{name}:{env['port']}\")
"
}

run_watchdog() {
    log "=========================================="
    log "Watchdog started for all architect environments"
    log "Config: $CONFIG"
    log "Check interval: ${CHECK_INTERVAL}s"
    log "=========================================="

    # Track which envs were down
    declare -A was_down

    while true; do
        cd "$APP_DIR"

        for env_info in $(get_envs); do
            env_name="${env_info%%:*}"
            port="${env_info##*:}"

            if check_health "$port"; then
                if [ "${was_down[$env_name]}" = "true" ]; then
                    log "RECOVERED - $env_name back online (port $port)"
                    alert "recovered" "$env_name is back online"
                    was_down[$env_name]=false
                fi
            else
                log "ALERT - $env_name unresponsive on port $port"

                if [ "${was_down[$env_name]}" != "true" ]; then
                    alert "critical" "$env_name is DOWN - attempting restart"
                fi
                was_down[$env_name]=true

                if restart_env "$env_name"; then
                    sleep 3
                    if check_health "$port"; then
                        log "RECOVERED - $env_name auto-restart successful"
                        alert "recovered" "$env_name auto-restart successful"
                        was_down[$env_name]=false
                    fi
                fi
            fi
        done

        sleep $CHECK_INTERVAL
    done
}

# Handle arguments
case "${1:-}" in
    --daemon)
        if pgrep -f "watchdog.sh.*--run" > /dev/null; then
            echo "Watchdog already running"
            exit 0
        fi
        nohup "$0" --run >> "$LOG" 2>&1 &
        echo "Watchdog started in background (PID: $!)"
        echo "Log: $LOG"
        ;;
    --run)
        run_watchdog
        ;;
    --stop)
        pkill -f "watchdog.sh" 2>/dev/null && echo "Watchdog stopped" || echo "Watchdog not running"
        ;;
    --status)
        if pgrep -f "watchdog.sh" > /dev/null; then
            echo "Watchdog is running"
            pgrep -f "watchdog.sh"
        else
            echo "Watchdog is not running"
        fi
        echo ""
        echo "Environment status:"
        cd "$APP_DIR" && python3 "$ENV_MANAGER" status
        echo ""
        echo "Recent logs:"
        tail -10 "$LOG" 2>/dev/null || echo "No logs yet"
        ;;
    --check)
        cd "$APP_DIR"
        all_ok=true
        for env_info in $(get_envs); do
            env_name="${env_info%%:*}"
            port="${env_info##*:}"
            if check_health "$port"; then
                echo "$env_name (port $port): healthy"
            else
                echo "$env_name (port $port): DOWN"
                all_ok=false
            fi
        done
        $all_ok || exit 1
        ;;
    *)
        echo "Usage: $0 [--daemon|--stop|--status|--check]"
        echo "  --daemon  Start watchdog in background"
        echo "  --stop    Stop watchdog"
        echo "  --status  Show status and recent logs"
        echo "  --check   Check health of all environments"
        ;;
esac
