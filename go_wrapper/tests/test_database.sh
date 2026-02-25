#!/bin/bash
# Database Integration Tests for Go Wrapper
# Tests database persistence, extraction/session stores, and query operations

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
DB_PATH="/tmp/test_go_wrapper.db"
TEST_RESULTS_FILE="/tmp/db_test_results.json"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_test() {
    echo -e "\n${YELLOW}[TEST $((TESTS_RUN + 1))]${NC} $1"
    TESTS_RUN=$((TESTS_RUN + 1))
}

pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# Cleanup function
cleanup() {
    rm -f "$DB_PATH" 2>/dev/null || true
    rm -f "$TEST_RESULTS_FILE" 2>/dev/null || true
}

# Setup
cleanup
trap cleanup EXIT

# Test 1: Check data package exists
print_test "Data package structure"
if ls data/extraction_store.go data/session_store.go > /dev/null 2>&1; then
    pass "Database store files exist"
else
    fail "Database store files missing"
fi

# Test 2: Run Go unit tests for data package
print_test "Run data package unit tests"
if go test -v github.com/architect/go_wrapper/data -run TestExtractionStore_SaveAndRetrieve > /tmp/db_unit_test.log 2>&1; then
    pass "Extraction store save/retrieve works"
else
    fail "Extraction store tests failed"
    cat /tmp/db_unit_test.log | head -10
fi

# Test 3: Session store tests
print_test "Run session store tests"
if go test -v github.com/architect/go_wrapper/data -run TestSessionStore_CreateAndGet > /tmp/session_test.log 2>&1; then
    pass "Session store create/get works"
else
    fail "Session store tests failed"
    cat /tmp/session_test.log | head -10
fi

# Test 4: Batch insertion performance
print_test "Batch insertion performance test"
if go test -bench=BenchmarkExtractionStore_SaveBatch -benchtime=100x github.com/architect/go_wrapper/data > /tmp/bench.log 2>&1; then
    # Extract timing from bench results
    TIME=$(grep "BenchmarkExtractionStore_SaveBatch" /tmp/bench.log | awk '{print $3}')
    pass "Batch insertion benchmark completed: $TIME"
else
    fail "Batch insertion benchmark failed"
fi

# Test 5: Code block deduplication
print_test "Code block deduplication"
if go test -v github.com/architect/go_wrapper/data -run TestCodeBlock_Deduplication > /tmp/dedup_test.log 2>&1; then
    pass "Code block deduplication works"
else
    fail "Code block deduplication failed"
    cat /tmp/dedup_test.log | head -10
fi

# Test 6: Session lifecycle tracking
print_test "Session lifecycle state tracking"
if go test -v github.com/architect/go_wrapper/data -run TestSessionStore_StateTrackingLifecycle > /tmp/lifecycle_test.log 2>&1; then
    pass "Session lifecycle tracking works"
else
    fail "Session lifecycle tracking failed"
    cat /tmp/lifecycle_test.log | head -10
fi

# Test 7: Database persistence across restarts
print_test "Database persistence verification"
if go test -v github.com/architect/go_wrapper/data -run TestExtractionStore_Persistence > /tmp/persist_test.log 2>&1; then
    pass "Data persists across store reconnections"
else
    fail "Persistence test failed"
    cat /tmp/persist_test.log | head -10
fi

# Test 8: Query filtering and pagination
print_test "Query filtering (by type, pattern, session)"
if go test -v github.com/architect/go_wrapper/data -run "TestExtractionStore_GetByType|TestExtractionStore_GetByPattern|TestExtractionStore_GetBySession" > /tmp/query_test.log 2>&1; then
    pass "Query filtering works correctly"
else
    fail "Query filtering failed"
    cat /tmp/query_test.log | head -10
fi

# Test 9: Aggregate statistics
print_test "Aggregate statistics calculation"
if go test -v github.com/architect/go_wrapper/data -run TestExtractionStore_GetStats > /tmp/stats_test.log 2>&1; then
    pass "Statistics aggregation works"
else
    fail "Statistics aggregation failed"
    cat /tmp/stats_test.log | head -10
fi

# Test 10: Active sessions query
print_test "Active sessions query"
if go test -v github.com/architect/go_wrapper/data -run TestSessionStore_GetActiveSessions > /tmp/active_test.log 2>&1; then
    pass "Active sessions query works"
else
    fail "Active sessions query failed"
    cat /tmp/active_test.log | head -10
fi

# Test 11: State change history
print_test "State change history tracking"
if go test -v github.com/architect/go_wrapper/data -run TestSessionStore_RecordStateChange > /tmp/state_change_test.log 2>&1; then
    pass "State change history works"
else
    fail "State change history failed"
    cat /tmp/state_change_test.log | head -10
fi

# Test 12: All unit tests together
print_test "Run complete test suite"
if go test github.com/architect/go_wrapper/data > /tmp/all_tests.log 2>&1; then
    TEST_COUNT=$(grep -c "PASS" /tmp/all_tests.log || echo "0")
    pass "All data package tests passed (found $TEST_COUNT passes)"
else
    fail "Some tests in suite failed"
    cat /tmp/all_tests.log | tail -20
fi

# Summary
echo ""
echo "========================================"
echo "Database Integration Test Summary"
echo "========================================"
echo "Total tests: $TESTS_RUN"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
else
    echo "Failed: $TESTS_FAILED"
fi
echo "========================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Database persistence system is working correctly:"
    echo "  - Extraction events stored and queryable"
    echo "  - Code blocks deduplicated by digest"
    echo "  - Session lifecycle tracked with state changes"
    echo "  - Queries filter by type, pattern, session"
    echo "  - Aggregate statistics calculated"
    echo "  - Data persists across restarts"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
