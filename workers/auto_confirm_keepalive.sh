#!/bin/bash
# Auto-Confirm Worker Keepalive
# Ensures auto_confirm_worker.py is always running

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SCRIPT="$SCRIPT_DIR/auto_confirm_worker.py"
LOG_FILE="/tmp/auto_confirm_keepalive.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

while true; do
    # Check if worker is running
    if ! pgrep -f "auto_confirm_worker.py" > /dev/null; then
        log "⚠️  Auto-confirm worker NOT running, starting..."
        nohup python3 "$WORKER_SCRIPT" > /tmp/auto_confirm_startup.log 2>&1 &
        sleep 3

        if pgrep -f "auto_confirm_worker.py" > /dev/null; then
            log "✅ Worker started successfully (PID: $(pgrep -f auto_confirm_worker.py))"
        else
            log "❌ Failed to start worker"
        fi
    fi

    # Check every 30 seconds
    sleep 30
done
