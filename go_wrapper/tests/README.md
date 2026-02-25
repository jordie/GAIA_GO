# Go Wrapper Test Suite

Automated tests for the Go Wrapper system. Run these after code changes to validate functionality.

## Quick Start

```bash
# Run all tests
./tests/run_all_tests.sh

# Or run individual test suites
./tests/test_wrapper.sh      # Core wrapper tests
./tests/test_20_agents.sh    # Stress test with 20 agents
./tests/test_dashboard.sh    # Dashboard and API tests
./tests/test_phase3_apis.sh  # Phase 3 API tests
```

## Test Suites

### 1. Wrapper Core Tests (`test_wrapper.sh`)
Tests fundamental wrapper functionality:
- ✅ Binary exists
- ✅ Simple command execution
- ✅ Log file creation
- ✅ ANSI code stripping
- ✅ Exit code capture
- ✅ Concurrent execution (5 agents)
- ✅ Codex integration
- ✅ API server health
- ✅ Dashboard accessibility
- ✅ Agents API endpoint

**Run**: `./tests/test_wrapper.sh`
**Expected**: 10/10 tests pass

### 2. 20-Agent Stress Test (`test_20_agents.sh`)
Validates high concurrency:
- Spawns 20 concurrent codex agents
- Verifies all agents complete successfully
- Checks calculation accuracy
- Validates ANSI code stripping
- Measures execution time

**Run**: `./tests/test_20_agents.sh`
**Expected**: 20/20 agents pass, < 5 ANSI codes per log

**Note**: Requires `codex` command to be available

### 3. Dashboard & API Tests (`test_dashboard.sh`)
Tests API server and dashboard:
- ✅ API server running
- ✅ Health endpoint
- ✅ Agents list endpoint
- ✅ Dashboard HTML accessible
- ✅ Enhanced dashboard
- ✅ SSE test page
- ✅ Create agent API
- ✅ Agent details endpoint
- ✅ JavaScript validation
- ✅ CORS headers

**Run**: `./tests/test_dashboard.sh`
**Expected**: 10/10 tests pass

### 4. Phase 3 API Tests (`test_phase3_apis.sh`)
Tests Phase 3 features (SSE, Metrics Export):
- ✅ Health endpoint
- ✅ List agents endpoint
- ✅ JSON metrics endpoint
- ✅ Prometheus metrics endpoint
- ✅ InfluxDB metrics endpoint
- ✅ SSE stats endpoint
- ✅ Create agent via API
- ✅ Get agent details
- ✅ Get agent with extraction data
- ✅ SSE stream connection
- ✅ Metrics contain system data
- ✅ Metrics contain SSE data
- ✅ Prometheus format validation
- ✅ InfluxDB format validation
- ✅ CORS headers

**Run**: `./tests/test_phase3_apis.sh`
**Expected**: 15/15 tests pass

**Features Tested:**
- Real-time SSE streaming
- Prometheus metrics export
- JSON metrics export
- InfluxDB line protocol
- Agent management APIs
- Extraction data access

## Running Tests

### All Tests
```bash
./tests/run_all_tests.sh
```

This runs all 4 test suites in sequence and provides a comprehensive report.

### Individual Tests
```bash
# Core functionality only
./tests/test_wrapper.sh

# Stress test only (requires codex)
./tests/test_20_agents.sh

# Dashboard/API only
./tests/test_dashboard.sh
```

### During Development
Run tests frequently to catch regressions:

```bash
# Quick test after small changes
./tests/test_wrapper.sh

# Full validation before commit
./tests/run_all_tests.sh
```

## Prerequisites

### Required
- Go wrapper binary (`./wrapper`)
- API server running on port 8151
- Bash shell
- `curl` command

### Optional (for full test coverage)
- `codex` command (for codex integration tests)
- `jq` (for JSON parsing in some tests)

## Test Output

### Success
```
✅ All tests passed!
Your Go Wrapper is production-ready!
```

### Failure
```
❌ Some tests failed
Please review the failures above.
```

Tests will exit with:
- Exit code 0: All tests passed
- Exit code 1: Some tests failed

## Adding New Tests

### To `test_wrapper.sh`
Add new test after existing tests:

```bash
# Test N: Description
echo -n "Test N: Description... "
if your_test_command; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi
```

### To `test_dashboard.sh`
Follow same pattern as above, focusing on API/dashboard functionality.

### Create New Test Suite
1. Create `tests/test_new_feature.sh`
2. Make it executable: `chmod +x tests/test_new_feature.sh`
3. Add to `run_all_tests.sh`

## Continuous Integration

These tests can be integrated with CI/CD:

```bash
# In your CI pipeline
cd go_wrapper
./tests/run_all_tests.sh || exit 1
```

## Test Coverage

Current test coverage:
- Core wrapper: 10 tests
- Concurrency: 20-agent stress test
- Dashboard: 10 tests
- Phase 3 APIs: 15 tests
- **Total**: 55+ test cases

## Troubleshooting

### "Binary not found"
```bash
# Rebuild the wrapper
go build -o wrapper main.go
```

### "API server not running"
```bash
# Start the API server
./apiserver --port 8151 &
```

### "Codex not available"
Codex tests will be skipped if `codex` command is not in PATH. This is expected and won't cause test failures.

### "Permission denied"
```bash
# Make tests executable
chmod +x tests/*.sh
```

## Performance Benchmarks

Expected test execution times:
- `test_wrapper.sh`: ~10-15 seconds
- `test_20_agents.sh`: ~30-60 seconds (depends on codex API)
- `test_dashboard.sh`: ~5-10 seconds
- **Total**: ~45-85 seconds

## Test Data Cleanup

Tests create temporary data in `logs/agents/`:
- `test-*` directories (core tests)
- `concurrent-*` directories (5-agent test)
- `stress-*` directories (20-agent test)
- `api-test` directory (dashboard tests)

These can be safely deleted:
```bash
rm -rf logs/agents/test-*
rm -rf logs/agents/concurrent-*
rm -rf logs/agents/stress-*
rm -rf logs/agents/api-test
```

Or clear all logs:
```bash
rm -rf logs/agents/*
```

## License

Part of the Go Wrapper project.
