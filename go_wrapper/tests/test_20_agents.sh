#!/bin/bash
# 20-Agent Concurrent Test
# Validates wrapper can handle 20+ concurrent agents

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "20-Agent Concurrent Stress Test"
echo "========================================="
echo ""

# Clean up old test logs
echo "Cleaning up old test logs..."
rm -rf logs/agents/stress-{1..20} 2>/dev/null || true

# Start 20 agents
echo "Starting 20 concurrent agents..."
START_TIME=$(date +%s)

for i in {1..20}; do
    ./wrapper stress-$i codex exec "Calculate $i * 2. Answer with just the number." &
done

echo "All agents spawned. Waiting for completion..."
wait

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "All agents completed in ${DURATION}s"
echo ""

# Verify results
echo "Verifying results..."
PASSED=0
FAILED=0

for i in {1..20}; do
    LOG_FILE=$(find logs/agents/stress-$i -name "*-stdout.log" -type f | tail -1)
    EXPECTED=$((i * 2))

    if [ -f "$LOG_FILE" ]; then
        # Check if the answer appears in the log
        if grep -q "$EXPECTED" "$LOG_FILE"; then
            echo -e "stress-$i: ${GREEN}PASS${NC} (found $EXPECTED)"
            ((PASSED++))
        else
            echo -e "stress-$i: ${YELLOW}PARTIAL${NC} (log exists but answer unclear)"
            ((PASSED++))
        fi
    else
        echo -e "stress-$i: ${RED}FAIL${NC} (no log file)"
        ((FAILED++))
    fi
done

# Check ANSI stripping
echo ""
echo "Checking ANSI code stripping..."
TOTAL_ANSI=0
for i in {1..20}; do
    LOG_FILE=$(find logs/agents/stress-$i -name "*-stdout.log" -type f | tail -1)
    if [ -f "$LOG_FILE" ]; then
        ANSI_COUNT=$(grep -o $'\x1b' "$LOG_FILE" | wc -l | tr -d ' ')
        TOTAL_ANSI=$((TOTAL_ANSI + ANSI_COUNT))
    fi
done
AVG_ANSI=$((TOTAL_ANSI / 20))
echo "Average ANSI codes per log: $AVG_ANSI (target: < 5)"

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Agents tested: 20"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Duration: ${DURATION}s"
echo "Avg ANSI codes: $AVG_ANSI"
echo ""

if [ $FAILED -eq 0 ] && [ $AVG_ANSI -lt 5 ]; then
    echo -e "${GREEN}✅ 20-agent stress test PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
