#!/bin/bash
# Test runner for CLI integration tests

set -e

echo "========================================="
echo "  CLI Integration Tests"
echo "========================================="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TOTAL=0
PASSED=0
FAILED=0

run_test() {
    local package=$1
    local name=$2

    echo -n "Testing $name... "
    TOTAL=$((TOTAL + 1))

    if go test $package -v -run Integration 2>&1 | grep -q "PASS"; then
        echo -e "${GREEN}✓ PASS${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ FAIL${NC}"
        FAILED=$((FAILED + 1))
        # Show error details
        go test $package -v -run Integration 2>&1 | tail -20
    fi
}

echo "Running unit tests..."
echo "-----------------------------------"

# Output formatter tests
run_test "./cmd/cli/output" "Output Formatters"

echo
echo "Running integration tests..."
echo "-----------------------------------"

# Client integration tests
run_test "./cmd/cli/client" "HTTP Client"

# Command integration tests
run_test "./cmd/cli/commands" "Agent Commands"
run_test "./cmd/cli/commands" "Metrics Commands"
run_test "./cmd/cli/commands" "Health Commands"

echo
echo "========================================="
echo "  Test Summary"
echo "========================================="
echo "Total:  $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed ✗${NC}"
    exit 1
fi
