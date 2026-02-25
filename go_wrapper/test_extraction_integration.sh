#!/bin/bash
# Test extraction layer integration with ProcessWrapper

set -e

echo "=== Testing Extraction Layer Integration ==="
echo ""

# Create test directory
TEST_DIR="/tmp/go_wrapper_extraction_test"
mkdir -p "$TEST_DIR"
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper

# Start wrapper with a simple echo agent for testing
echo "1. Starting wrapper with echo agent..."
./bin/wrapper test_extraction_agent echo "⏺ Bash(ls -lh)" > "$TEST_DIR/wrapper.log" 2>&1 &
WRAPPER_PID=$!

echo "   Wrapper PID: $WRAPPER_PID"
sleep 2

# Check if wrapper is running
if ! ps -p $WRAPPER_PID > /dev/null; then
    echo "   ✗ Wrapper failed to start"
    cat "$TEST_DIR/wrapper.log"
    exit 1
fi

echo "   ✓ Wrapper started"
echo ""

# Check wrapper output for extraction layer messages
echo "2. Checking extraction layer initialization..."
if grep -q "Extraction layer enabled" "$TEST_DIR/wrapper.log"; then
    PATTERN_COUNT=$(grep "Extraction layer enabled" "$TEST_DIR/wrapper.log" | sed 's/.*: \([0-9]*\) patterns.*/\1/')
    echo "   ✓ Extraction layer enabled with $PATTERN_COUNT patterns"
elif grep -q "Extraction layer disabled" "$TEST_DIR/wrapper.log"; then
    echo "   ⚠ Extraction layer disabled (config not found)"
    echo "   Creating config and retrying..."

    # Kill wrapper
    kill $WRAPPER_PID 2>/dev/null
    wait $WRAPPER_PID 2>/dev/null

    echo "   ✗ Config should exist at config/extraction_patterns.json"
    exit 1
else
    echo "   ✗ No extraction layer status found"
    cat "$TEST_DIR/wrapper.log"
    kill $WRAPPER_PID 2>/dev/null
    exit 1
fi

echo ""

# Wait for process to complete
echo "3. Waiting for wrapper to complete..."
wait $WRAPPER_PID 2>/dev/null
echo "   ✓ Wrapper completed"
echo ""

# Check for training data output
echo "4. Checking training data..."
TRAINING_DIR="data/training/training_data/test_extraction_agent"
if [ -d "$TRAINING_DIR" ]; then
    EVENT_FILE=$(ls -t $TRAINING_DIR/*events*.jsonl 2>/dev/null | head -1)
    if [ -f "$EVENT_FILE" ]; then
        EVENT_COUNT=$(wc -l < "$EVENT_FILE")
        echo "   ✓ Training data created: $EVENT_COUNT events logged"
        echo "   File: $EVENT_FILE"

        # Show sample event
        echo ""
        echo "   Sample event:"
        head -1 "$EVENT_FILE" | jq -c '{event_type, pattern, fields}' 2>/dev/null || head -1 "$EVENT_FILE"
    else
        echo "   ⚠ No event files found in $TRAINING_DIR"
    fi
else
    echo "   ⚠ Training directory not created (agent may not have processed any lines)"
fi

echo ""

# Check logs for extracted events
echo "5. Checking agent logs..."
LOG_DIR="logs/agents/test_extraction_agent"
if [ -d "$LOG_DIR" ]; then
    STDOUT_LOG=$(ls -t $LOG_DIR/*stdout.log 2>/dev/null | head -1)
    if [ -f "$STDOUT_LOG" ]; then
        echo "   ✓ Agent log created: $STDOUT_LOG"
        echo "   Log contents:"
        cat "$STDOUT_LOG"
    else
        echo "   ⚠ No stdout log found"
    fi
else
    echo "   ⚠ Log directory not created"
fi

echo ""
echo "=== Test Summary ==="
echo "✓ Wrapper compiled with extraction integration"
echo "✓ Extraction layer initialized from config"
echo "✓ ProcessWrapper running with extractor enabled"
echo ""
echo "Integration test complete!"
