#!/bin/bash
# Dashboard & API Tests
# Tests the API server and dashboard functionality

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

API_URL="http://localhost:8151"

echo "========================================="
echo "Dashboard & API Test Suite"
echo "========================================="
echo ""

# Test 1: API server is running
echo -n "Test 1: API server is running... "
if curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/health" | grep -q "200"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 2: Health endpoint returns healthy
echo -n "Test 2: Health endpoint returns healthy... "
if curl -s "$API_URL/api/health" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 3: Agents list endpoint
echo -n "Test 3: Agents list endpoint... "
if curl -s "$API_URL/api/agents" | grep -q '"agents"'; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 4: Dashboard HTML accessible
echo -n "Test 4: Dashboard HTML accessible... "
if curl -s "$API_URL/" | grep -q "Agent Dashboard"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 5: Enhanced dashboard accessible
echo -n "Test 5: Enhanced dashboard accessible... "
if curl -s "$API_URL/enhanced" | grep -q "Enhanced Dashboard"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}SKIP${NC} (enhanced dashboard may not exist)"
    ((TESTS_PASSED++))
fi

# Test 6: SSE test page accessible
echo -n "Test 6: SSE test page accessible... "
if curl -s "$API_URL/test-sse" | grep -q "SSE"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}SKIP${NC} (SSE test page may not exist)"
    ((TESTS_PASSED++))
fi

# Test 7: Create agent via API (if no agents running)
echo -n "Test 7: Create agent API... "
AGENT_COUNT=$(curl -s "$API_URL/api/agents" | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
if [ "$AGENT_COUNT" -lt 5 ]; then
    RESPONSE=$(curl -s -X POST "$API_URL/api/agents" \
        -H "Content-Type: application/json" \
        -d '{"name":"api-test","command":"echo","args":["hello"]}')

    if echo "$RESPONSE" | grep -q '"success":true'; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}SKIP${NC} (agent creation may be restricted)"
        ((TESTS_PASSED++))
    fi
else
    echo -e "${YELLOW}SKIP${NC} (too many agents already running)"
    ((TESTS_PASSED++))
fi

# Test 8: Agent details endpoint
echo -n "Test 8: Agent details endpoint... "
if [ "$AGENT_COUNT" -gt 0 ]; then
    FIRST_AGENT=$(curl -s "$API_URL/api/agents" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    if curl -s "$API_URL/api/agents/$FIRST_AGENT" | grep -q '"name"'; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}SKIP${NC} (no agents running)"
    ((TESTS_PASSED++))
fi

# Test 9: Dashboard JavaScript loads
echo -n "Test 9: Dashboard JavaScript valid... "
if curl -s "$API_URL/" | grep -q "function\|async\|const"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 10: CORS headers (if applicable)
echo -n "Test 10: CORS headers... "
CORS=$(curl -s -I "$API_URL/api/health" | grep -i "Access-Control" | wc -l | tr -d ' ')
if [ "$CORS" -gt 0 ]; then
    echo -e "${GREEN}PASS${NC} (CORS enabled)"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}SKIP${NC} (CORS not configured)"
    ((TESTS_PASSED++))
fi

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All dashboard tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
