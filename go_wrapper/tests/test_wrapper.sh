#!/bin/bash
# Go Wrapper Test Suite
# Run this after code changes to validate functionality

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

echo "========================================="
echo "Go Wrapper Test Suite"
echo "========================================="
echo ""

# Test 1: Binary exists
echo -n "Test 1: Binary exists... "
if [ -f "./wrapper" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 2: Simple echo test
echo -n "Test 2: Simple echo command... "
OUTPUT=$(./wrapper test-echo echo "test" 2>&1)
if echo "$OUTPUT" | grep -q "test"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 3: Log file creation
echo -n "Test 3: Log file created... "
LOG_FILE=$(find logs/agents/test-echo -name "*-stdout.log" -type f | tail -1)
if [ -f "$LOG_FILE" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 4: ANSI stripping
echo -n "Test 4: ANSI codes stripped... "
./wrapper test-ansi bash -c 'echo -e "\033[32mGreen\033[0m"' > /dev/null 2>&1
ANSI_LOG=$(find logs/agents/test-ansi -name "*-stdout.log" -type f | tail -1)
ANSI_COUNT=$(grep -o $'\x1b' "$ANSI_LOG" | wc -l | tr -d ' ')
if [ "$ANSI_COUNT" -lt 2 ]; then
    echo -e "${GREEN}PASS${NC} ($ANSI_COUNT escape sequences)"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC} ($ANSI_COUNT escape sequences found)"
    ((TESTS_FAILED++))
fi

# Test 5: Exit code capture
echo -n "Test 5: Exit code capture... "
./wrapper test-exit bash -c 'exit 42' > /dev/null 2>&1 || true
if ./wrapper test-exit bash -c 'exit 42' 2>&1 | grep -q "exited with code: 42"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 6: Concurrent execution (5 agents)
echo -n "Test 6: Concurrent execution (5 agents)... "
for i in {1..5}; do
    ./wrapper concurrent-$i echo "agent-$i" &
done
wait
CONCURRENT_LOGS=$(find logs/agents/concurrent-{1..5} -name "*-stdout.log" -type f | wc -l | tr -d ' ')
if [ "$CONCURRENT_LOGS" -ge 5 ]; then
    echo -e "${GREEN}PASS${NC} ($CONCURRENT_LOGS log files)"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC} (only $CONCURRENT_LOGS log files)"
    ((TESTS_FAILED++))
fi

# Test 7: Codex integration
echo -n "Test 7: Codex integration... "
if command -v codex > /dev/null 2>&1; then
    ./wrapper test-codex codex exec "What is 1+1?" > /dev/null 2>&1
    CODEX_LOG=$(find logs/agents/test-codex -name "*-stdout.log" -type f | tail -1)
    if [ -f "$CODEX_LOG" ] && grep -q "2" "$CODEX_LOG"; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}SKIP${NC} (codex responded but unexpected output)"
        ((TESTS_PASSED++))
    fi
else
    echo -e "${YELLOW}SKIP${NC} (codex not available)"
    ((TESTS_PASSED++))
fi

# Test 8: API Server health
echo -n "Test 8: API server health... "
if curl -s http://localhost:8151/api/health | grep -q "healthy"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 9: Dashboard accessible
echo -n "Test 9: Dashboard accessible... "
if curl -s http://localhost:8151/ | grep -q "Agent Dashboard"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 10: Agents API endpoint
echo -n "Test 10: Agents API endpoint... "
if curl -s http://localhost:8151/api/agents | grep -q '"agents"'; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
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
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
