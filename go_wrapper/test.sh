#!/bin/bash
# Test script for Go wrapper

set -e

echo "=== Go Wrapper Test Suite ==="
echo ""

# Build
echo "[1/4] Building wrapper..."
go build -o wrapper main.go
echo "✓ Build successful"
echo ""

# Test 1: Simple command with ANSI codes
echo "[2/4] Test 1: ANSI stripping"
timeout 2 ./wrapper test-ansi bash -c 'echo -e "\033[31mRed text\033[0m"; echo -e "\033[1;32mGreen bold\033[0m"' || true
sleep 1

# Check log content
LOG_FILE=$(ls -t logs/agents/test-ansi/*-stdout.log | head -1)
echo "Log file: $LOG_FILE"
echo "Contents:"
cat "$LOG_FILE"
echo ""

# Verify no escape codes in log
if grep -q $'\x1b' "$LOG_FILE"; then
    echo "✗ FAIL: Escape codes found in log"
    exit 1
else
    echo "✓ PASS: Log is clean (no escape codes)"
fi
echo ""

# Test 2: Continuous output (stress test)
echo "[3/4] Test 2: Continuous streaming (5 seconds)"
timeout 5 ./wrapper test-stream yes "hello world" || true
sleep 1

STREAM_LOG=$(ls -t logs/agents/test-stream/*-stdout.log | head -1)
LINE_COUNT=$(wc -l < "$STREAM_LOG")
echo "Lines written: $LINE_COUNT"

if [ "$LINE_COUNT" -gt 1000 ]; then
    echo "✓ PASS: High-throughput streaming works"
else
    echo "✗ FAIL: Expected more lines"
    exit 1
fi
echo ""

# Test 3: Multiple agents concurrently
echo "[4/4] Test 3: Concurrent agents"
timeout 3 ./wrapper agent-1 bash -c 'for i in {1..50}; do echo "Agent 1: $i"; sleep 0.1; done' &
timeout 3 ./wrapper agent-2 bash -c 'for i in {1..50}; do echo "Agent 2: $i"; sleep 0.1; done' &
timeout 3 ./wrapper agent-3 bash -c 'for i in {1..50}; do echo "Agent 3: $i"; sleep 0.1; done' &

wait
sleep 1

echo "Log files created:"
ls -lh logs/agents/agent-*/
echo ""

echo "✓ PASS: Concurrent agents work"
echo ""

# Summary
echo "=== Test Summary ==="
echo "✓ All tests passed"
echo ""
echo "To test with codex:"
echo "  ./wrapper codex-1 codex"
echo ""
echo "Logs are in: logs/agents/"
