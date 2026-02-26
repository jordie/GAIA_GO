#!/bin/bash
# Stop Foundation Session Monitor

PID_FILE="/tmp/foundation_monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Foundation monitor is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping Foundation monitor (PID: $PID)..."
    kill "$PID"
    sleep 1

    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Force stopping..."
        kill -9 "$PID"
    fi

    rm "$PID_FILE"
    echo "✓ Foundation monitor stopped"
else
    echo "Foundation monitor is not running (stale PID file)"
    rm "$PID_FILE"
fi
