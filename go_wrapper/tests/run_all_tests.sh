#!/bin/bash
# Run All Tests - Master Test Suite
# Runs all wrapper tests in sequence

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   Go Wrapper - Full Test Suite${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Track overall results
SUITES_PASSED=0
SUITES_FAILED=0

# Test 1: Wrapper Core Tests
echo -e "${BLUE}[1/3] Running Wrapper Core Tests...${NC}"
echo ""
if bash tests/test_wrapper.sh; then
    ((SUITES_PASSED++))
else
    ((SUITES_FAILED++))
fi
echo ""

# Test 2: 20-Agent Stress Test
echo -e "${BLUE}[2/3] Running 20-Agent Stress Test...${NC}"
echo ""
if bash tests/test_20_agents.sh; then
    ((SUITES_PASSED++))
else
    ((SUITES_FAILED++))
fi
echo ""

# Test 3: Dashboard Tests
echo -e "${BLUE}[3/4] Running Dashboard Tests...${NC}"
echo ""
if bash tests/test_dashboard.sh; then
    ((SUITES_PASSED++))
else
    ((SUITES_FAILED++))
fi
echo ""

# Test 4: Phase 3 API Tests
echo -e "${BLUE}[4/4] Running Phase 3 API Tests...${NC}"
echo ""
if bash tests/test_phase3_apis.sh; then
    ((SUITES_PASSED++))
else
    ((SUITES_FAILED++))
fi
echo ""

# Final Summary
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   Final Results${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "Test Suites:"
echo -e "  Passed: ${GREEN}$SUITES_PASSED${NC}"
echo -e "  Failed: ${RED}$SUITES_FAILED${NC}"
echo "  Total: $((SUITES_PASSED + SUITES_FAILED))"
echo ""

if [ $SUITES_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All test suites passed!${NC}"
    echo ""
    echo "Your Go Wrapper is production-ready!"
    exit 0
else
    echo -e "${RED}❌ Some test suites failed${NC}"
    echo ""
    echo "Please review the failures above."
    exit 1
fi
