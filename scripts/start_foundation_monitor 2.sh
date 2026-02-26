#!/bin/bash
# Start Foundation Session Monitor
# This script starts the monitoring daemon for the foundation session

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="/tmp/foundation_monitor.pid"
LOG_FILE="$BASE_DIR/logs/foundation_monitor.log"

# Create logs directory
mkdir -p "$BASE_DIR/logs"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Foundation monitor is already running (PID: $PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

echo "Starting Foundation Session Monitor..."
echo "Log file: $LOG_FILE"

# Start the monitor in the background
nohup python3 "$SCRIPT_DIR/foundation_session_monitor.py" --daemon \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

sleep 2

# Verify it started
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ Foundation monitor started successfully (PID: $PID)"
    echo "✓ Monitoring session: foundation"
    echo "✓ Check interval: 2 minutes"
    echo "✓ Idle threshold: 3 minutes"
    echo ""
    echo "To check status:"
    echo "  python3 $SCRIPT_DIR/foundation_session_monitor.py --status"
    echo ""
    echo "To stop:"
    echo "  $SCRIPT_DIR/stop_foundation_monitor.sh"
else
    echo "✗ Failed to start monitor"
    rm "$PID_FILE"
    exit 1
fi
