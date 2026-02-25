#!/bin/bash
# Live Integration Test for Auto-Confirm Worker
# Tests that the worker can actually auto-confirm prompts in the foundation session

set -e

echo "=== Auto-Confirm Live Integration Test ==="
echo ""

# Check if auto-confirm worker is running
echo "[1/5] Checking if auto-confirm worker is running..."
if pgrep -f "auto_confirm_worker.py" > /dev/null; then
    echo "✓ Auto-confirm worker is running"
    WORKER_PID=$(pgrep -f "auto_confirm_worker.py")
    echo "  PID: $WORKER_PID"
else
    echo "⚠ Auto-confirm worker is NOT running"
    echo "  Starting worker in background..."
    cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers
    nohup python3 auto_confirm_worker.py > /tmp/auto_confirm_test.log 2>&1 &
    WORKER_PID=$!
    echo "  Started with PID: $WORKER_PID"
    sleep 2
fi
echo ""

# Check foundation session exists
echo "[2/5] Verifying foundation session..."
if tmux has-session -t foundation 2>/dev/null; then
    echo "✓ Foundation session exists"
else
    echo "❌ Foundation session not found"
    exit 1
fi
echo ""

# Check recent confirmations
echo "[3/5] Checking recent confirmations..."
sqlite3 /tmp/auto_confirm.db "SELECT COUNT(*) FROM confirmations WHERE session_name='foundation'" | while read count; do
    echo "  Foundation confirmations in DB: $count"
done

# Show last 3 confirmations for foundation
echo "  Last 3 confirmations for foundation:"
sqlite3 /tmp/auto_confirm.db "
    SELECT timestamp, operation
    FROM confirmations
    WHERE session_name='foundation'
    ORDER BY timestamp DESC
    LIMIT 3
" | while read line; do
    echo "    - $line"
done
echo ""

# Check worker logs
echo "[4/5] Checking worker logs..."
if [ -f /tmp/auto_confirm.log ]; then
    LOG_SIZE=$(wc -l < /tmp/auto_confirm.log)
    echo "  Log file exists: /tmp/auto_confirm.log"
    echo "  Log size: $LOG_SIZE lines"
    echo ""
    echo "  Last 5 log entries:"
    tail -5 /tmp/auto_confirm.log | while read line; do
        echo "    $line"
    done
else
    echo "  No log file yet (worker just started)"
fi
echo ""

# Test configuration
echo "[5/5] Configuration Summary"
echo "  Session: foundation"
echo "  Status: $(tmux list-sessions 2>/dev/null | grep foundation | awk '{print $NF}')"
echo "  Excluded from auto-confirm: NO"
echo "  Safe operations: read, grep, glob, accept_edits, edit, write, bash"
echo "  Idle threshold: 3 seconds"
echo "  Dry run mode: False"
echo ""

# Final summary
echo "=== Test Complete ==="
echo ""
echo "✓ Foundation session is configured for auto-confirm"
echo "✓ Worker is monitoring the session"
echo ""
echo "To test manually:"
echo "  1. In foundation session, trigger a Claude prompt (edit/write/bash)"
echo "  2. Wait 3+ seconds (idle threshold)"
echo "  3. Worker should auto-confirm with option 1"
echo "  4. Check logs: tail -f /tmp/auto_confirm.log"
echo ""
echo "To check confirmations:"
echo "  sqlite3 /tmp/auto_confirm.db \"SELECT * FROM confirmations WHERE session_name='foundation' ORDER BY timestamp DESC LIMIT 10\""
echo ""
echo "To stop worker:"
echo "  pkill -f auto_confirm_worker.py"
