#!/bin/bash
# Example usage script for Go wrapper with codex agents

set -e

echo "=== Go Wrapper Example Usage ==="
echo ""

# Ensure wrapper is built
if [ ! -f wrapper ]; then
    echo "Building wrapper..."
    go build -o wrapper main.go
fi

echo "[Example 1] Single codex agent (5 seconds)"
echo "Command: ./wrapper codex-1 codex"
echo ""
timeout 5 ./wrapper codex-1 codex || true
echo ""

echo "[Example 2] Background agent"
echo "Command: ./wrapper codex-bg codex &"
./wrapper codex-bg bash -c 'for i in {1..20}; do echo "Background agent: $i"; sleep 0.5; done' &
BG_PID=$!
echo "Started in background (PID: $BG_PID)"
sleep 3
echo "Stopping background agent..."
kill -TERM $BG_PID 2>/dev/null || true
wait $BG_PID 2>/dev/null || true
echo ""

echo "[Example 3] Multiple agents concurrently (3 agents for 5 seconds)"
for i in 1 2 3; do
    ./wrapper codex-$i bash -c "for j in {1..10}; do echo 'Agent $i: Message \$j'; sleep 0.5; done" &
done
sleep 5
pkill -TERM -f "wrapper codex-" || true
wait
echo ""

echo "[Example 4] Log analysis"
echo "Finding all stdout logs:"
find logs/agents -name "*-stdout.log" -type f
echo ""

echo "Checking log sizes:"
du -h logs/agents/*/
echo ""

echo "Preview first log:"
FIRST_LOG=$(find logs/agents -name "*-stdout.log" -type f | head -1)
if [ -n "$FIRST_LOG" ]; then
    echo "File: $FIRST_LOG"
    echo "---"
    head -20 "$FIRST_LOG"
    echo "---"
fi
echo ""

echo "=== Examples Complete ==="
echo ""
echo "To run codex for real:"
echo "  ./wrapper codex-1 codex"
echo ""
echo "To run in background:"
echo "  ./wrapper codex-1 codex &"
echo ""
echo "To view logs:"
echo "  tail -f logs/agents/codex-1/*-stdout.log"
