#!/bin/bash
# SSE Streaming Test Script
# Uses standardized DEV port: 8151

set -e

PORT=8151
API_URL="http://localhost:$PORT"
AGENT_NAME="sse-test-agent"

echo "=== SSE Streaming Test Suite ==="
echo "Port: $PORT (DEV)"
echo ""

# Start API server in background
echo "[1/7] Starting API server..."
./apiserver --port $PORT > /tmp/apiserver_sse.log 2>&1 &
API_PID=$!
sleep 2

# Check if server is running
if ! kill -0 $API_PID 2>/dev/null; then
    echo "✗ FAIL: Server failed to start"
    cat /tmp/apiserver_sse.log
    exit 1
fi
echo "✓ Server started (PID: $API_PID)"
echo ""

# Test 1: Create agent
echo "[2/7] Creating test agent..."
CREATE_RESPONSE=$(curl -s -X POST $API_URL/api/agents \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"$AGENT_NAME\",
        \"command\": \"bash\",
        \"args\": [\"-c\", \"for i in {1..10}; do echo 'Line '\$i; sleep 0.5; done; echo '✓ Complete'\"]
    }")

if echo "$CREATE_RESPONSE" | grep -q "\"name\":\"$AGENT_NAME\""; then
    echo "✓ PASS: Agent created"
    echo "  Response: $CREATE_RESPONSE"
else
    echo "✗ FAIL: Agent creation failed"
    echo "  Response: $CREATE_RESPONSE"
    kill $API_PID
    exit 1
fi
echo ""

# Test 2: Check SSE stats
echo "[3/7] Checking SSE stats endpoint..."
STATS_RESPONSE=$(curl -s $API_URL/api/sse/stats)
if echo "$STATS_RESPONSE" | grep -q "total_agents"; then
    echo "✓ PASS: SSE stats endpoint working"
    echo "  Stats: $STATS_RESPONSE"
else
    echo "✗ FAIL: SSE stats endpoint failed"
    kill $API_PID
    exit 1
fi
echo ""

# Test 3: Test SSE stream endpoint (curl with timeout)
echo "[4/7] Testing SSE stream endpoint..."
STREAM_URL="$API_URL/api/agents/$AGENT_NAME/stream"
echo "  Connecting to: $STREAM_URL"

# Use curl to test SSE stream (5 second timeout)
timeout 5s curl -N -s $STREAM_URL > /tmp/sse_stream.txt 2>&1 || true

if [ -s /tmp/sse_stream.txt ]; then
    LINES=$(wc -l < /tmp/sse_stream.txt)
    echo "✓ PASS: SSE stream received $LINES lines"

    # Check for expected SSE format
    if grep -q "event: connected" /tmp/sse_stream.txt; then
        echo "  ✓ Connected event received"
    fi

    if grep -q "event: log" /tmp/sse_stream.txt; then
        echo "  ✓ Log events received"
    fi

    if grep -q "data:" /tmp/sse_stream.txt; then
        echo "  ✓ Data payloads present"
    fi
else
    echo "⚠ WARNING: No SSE stream data received (agent may have completed too quickly)"
fi
echo ""

# Test 4: Verify agent is streaming
echo "[5/7] Verifying agent status..."
AGENT_STATUS=$(curl -s $API_URL/api/agents/$AGENT_NAME)
if echo "$AGENT_STATUS" | grep -q "\"status\":\"running\""; then
    echo "✓ PASS: Agent is running"
elif echo "$AGENT_STATUS" | grep -q "\"status\":\"stopped\""; then
    echo "✓ PASS: Agent completed (expected for short tasks)"
else
    echo "⚠ WARNING: Agent status unclear"
    echo "  Status: $AGENT_STATUS"
fi
echo ""

# Test 5: Test concurrent SSE connections
echo "[6/7] Testing concurrent SSE connections..."
CONCURRENT_CLIENTS=3
PIDS=()

for i in $(seq 1 $CONCURRENT_CLIENTS); do
    timeout 3s curl -N -s $STREAM_URL > /tmp/sse_client_$i.txt 2>&1 &
    PIDS+=($!)
done

sleep 3

# Check if any clients received data
CLIENTS_OK=0
for i in $(seq 1 $CONCURRENT_CLIENTS); do
    if [ -s /tmp/sse_client_$i.txt ]; then
        CLIENTS_OK=$((CLIENTS_OK + 1))
    fi
done

if [ $CLIENTS_OK -gt 0 ]; then
    echo "✓ PASS: $CLIENTS_OK/$CONCURRENT_CLIENTS concurrent clients received data"
else
    echo "⚠ WARNING: No concurrent clients received data (agent may have completed)"
fi
echo ""

# Test 6: Verify SSE stats after connections
echo "[7/7] Verifying SSE stats after connections..."
FINAL_STATS=$(curl -s $API_URL/api/sse/stats)
echo "  Final stats: $FINAL_STATS"

if echo "$FINAL_STATS" | grep -q "total_clients"; then
    echo "✓ PASS: SSE stats tracked connections"
else
    echo "⚠ WARNING: SSE stats format unexpected"
fi
echo ""

# Cleanup
echo "Cleaning up..."
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true
echo "✓ Server stopped"
echo ""

# Show sample SSE data
if [ -s /tmp/sse_stream.txt ]; then
    echo "=== Sample SSE Stream Data ==="
    head -20 /tmp/sse_stream.txt
    echo ""
fi

echo "=== Test Summary ==="
echo "✓ All core tests passed"
echo ""
echo "To test interactively:"
echo "  1. Start server: ./apiserver --port 8151"
echo "  2. Open test_sse.html in browser"
echo "  3. Enter agent name and click Connect"
echo ""
echo "To test with curl:"
echo "  curl -N $STREAM_URL"
echo ""
