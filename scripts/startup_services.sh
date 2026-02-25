#!/bin/bash
#
# Startup Services Script
# Starts all Architect services and health daemon on login
#
# Add to Login Items:
#   System Settings > General > Login Items > Add this script
#
# Or run manually: ./startup_services.sh
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/tmp/architect_startup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Starting Architect Services"
log "=========================================="

cd "$APP_DIR"

# Start Architect Dashboard (8080)
if ! lsof -ti:8080 >/dev/null 2>&1; then
    log "Starting Architect Dashboard on port 8080..."
    nohup python3 app.py --port 8080 --host 0.0.0.0 > /tmp/architect_8080.log 2>&1 &
    sleep 2
fi

# Start Architect Dashboard SSL (8085)
if ! lsof -ti:8085 >/dev/null 2>&1; then
    log "Starting Architect Dashboard (SSL) on port 8085..."
    nohup python3 app.py --port 8085 --ssl > /tmp/architect_8085.log 2>&1 &
    sleep 2
fi

# Start Browser Automation (6085)
BROWSER_DIR="/Users/jgirmay/Desktop/gitrepo/pyWork/claude_browser_agent"
if ! lsof -ti:6085 >/dev/null 2>&1; then
    log "Starting Browser Automation on port 6085..."
    cd "$BROWSER_DIR" && nohup python3 webapp/app.py --port 6085 --host 0.0.0.0 > /tmp/browser_agent_6085.log 2>&1 &
    cd "$APP_DIR"
    sleep 2
fi

# Start Health Daemon
if ! pgrep -f "health_daemon.py" >/dev/null 2>&1; then
    log "Starting Health Daemon..."
    python3 "$SCRIPT_DIR/health_daemon.py" --daemon
fi

# Start Health Monitor
if ! pgrep -f "health_monitor.py" >/dev/null 2>&1; then
    log "Starting Health Monitor..."
    python3 "$SCRIPT_DIR/health_monitor.py" --daemon
fi

log "=========================================="
log "Startup complete"
log "=========================================="

# Show status
sleep 3
echo ""
echo "Service Status:"
echo "---------------"
for port in 8080 8085 5051 5063 6085; do
    if curl -sk --connect-timeout 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1 || \
       curl -sk --connect-timeout 2 "https://127.0.0.1:$port/health" >/dev/null 2>&1 || \
       curl -sk --connect-timeout 2 "http://127.0.0.1:$port/" >/dev/null 2>&1; then
        echo "  Port $port: UP"
    else
        echo "  Port $port: DOWN"
    fi
done
