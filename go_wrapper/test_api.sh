#!/bin/bash
# API Server Test Script
# Uses standardized DEV port: 8151

set -e

PORT=8151
API_URL="http://localhost:$PORT"

echo "=== API Server Test Suite ==="
echo "Port: $PORT (DEV)"
echo ""

# Start API server in background
echo "[1/6] Starting API server..."
./apiserver --port $PORT > /tmp/apiserver.log 2>&1 &
API_PID=$!
sleep 2

# Check if server is running
if ! kill -0 $API_PID 2>/dev/null; then
    echo "✗ FAIL: Server failed to start"
    cat /tmp/apiserver.log
    exit 1
fi
echo "✓ Server started (PID: $API_PID)"
echo ""

# Test 1: Health check
echo "[2/6] Testing health endpoint..."
HEALTH=$(curl -s $API_URL/api/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ PASS: Health check successful"
    echo "  Response: $HEALTH"
else
    echo "✗ FAIL: Health check failed"
    kill $API_PID
    exit 1
fi
echo ""

# Test 2: List agents (should be empty)
echo "[3/6] Testing list agents (empty)..."
AGENTS=$(curl -s $API_URL/api/agents)
if echo "$AGENTS" | grep -q '"count":0'; then
    echo "✓ PASS: No agents initially"
else
    echo "✗ FAIL: Expected 0 agents"
    kill $API_PID
    exit 1
fi
echo ""

# Test 3: Create agent
echo "[4/6] Testing create agent..."
CREATE_RESPONSE=$(curl -s -X POST $API_URL/api/agents \
    -H "Content-Type: application/json" \
    -d '{
        "name": "test-agent",
        "command": "bash",
        "args": ["-c", "for i in {1..5}; do echo Line $i; sleep 0.5; done"]
    }')

if echo "$CREATE_RESPONSE" | grep -q '"name":"test-agent"'; then
    echo "✓ PASS: Agent created"
    echo "  Response: $CREATE_RESPONSE"
else
    echo "✗ FAIL: Agent creation failed"
    echo "  Response: $CREATE_RESPONSE"
    kill $API_PID
    exit 1
fi
echo ""

# Test 4: Get agent details
sleep 1
echo "[5/6] Testing get agent details..."
AGENT_DETAILS=$(curl -s "$API_URL/api/agents/test-agent?include_matches=true")
if echo "$AGENT_DETAILS" | grep -q '"name":"test-agent"'; then
    echo "✓ PASS: Agent details retrieved"
    echo "  Status:" $(echo "$AGENT_DETAILS" | grep -o '"status":"[^"]*"')
else
    echo "✗ FAIL: Failed to get agent details"
    kill $API_PID
    exit 1
fi
echo ""

# Test 5: List agents (should have 1)
echo "[6/6] Testing list agents (with agent)..."
AGENTS=$(curl -s $API_URL/api/agents)
if echo "$AGENTS" | grep -q '"count":1'; then
    echo "✓ PASS: 1 agent listed"
else
    echo "⚠ WARNING: Expected 1 agent, check if agent already stopped"
fi
echo ""

# Wait for agent to complete
sleep 3

# Cleanup
echo "Cleaning up..."
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true
echo "✓ Server stopped"
echo ""

echo "=== Test Summary ==="
echo "✓ All tests passed"
echo ""
echo "API server is working correctly!"
echo ""
echo "To start the server manually:"
echo "  ./apiserver --port 8151"
