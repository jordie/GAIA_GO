# CLI Testing Guide

## Overview

The wrapper-cli has comprehensive test coverage including:
- **Unit Tests** - Output formatters and utilities
- **Integration Tests** - Commands with mock API server
- **Client Tests** - HTTP client communication
- **E2E Ready** - Framework for end-to-end testing

**Test Coverage: 30+ tests across 5 test suites**

---

## Quick Test Run

```bash
# Run all tests
./scripts/test-cli.sh

# Run specific test suite
go test ./cmd/cli/output -v           # Unit tests
go test ./cmd/cli/client -run Integration -v   # Client tests
go test ./cmd/cli/commands -run Integration -v # Command tests

# Run with coverage
go test ./cmd/cli/... -cover

# Run with race detection
go test ./cmd/cli/... -race
```

---

## Test Structure

```
cmd/cli/
├── testing/
│   └── mock_server.go          # Mock API server for testing
├── output/
│   └── formatter_test.go       # Unit tests (8 tests)
├── client/
│   └── client_integration_test.go  # HTTP client tests (9 tests)
└── commands/
    ├── agents_integration_test.go  # Agent command tests (10 tests)
    ├── metrics_integration_test.go # Metrics tests (4 tests)
    └── health_integration_test.go  # Health tests (4 tests)
```

---

## Test Suites

### 1. Output Formatter Tests (8 tests)

Tests formatting and display functions:

```bash
go test ./cmd/cli/output -v
```

**Tests:**
- `TestFormatBytes` - Human-readable byte formatting
- `TestFormatDuration` - Duration formatting (1h5m30s)
- `TestFormatStatus` - Status color coding
- `TestColorize` - Terminal color codes
- `TestPrintTable` - Table output generation
- `TestPrintJSON` - JSON formatting
- `TestPrintCSV` - CSV formatting
- `TestProgressBar` - Progress bar rendering

**Coverage:** Formatting logic, color handling, NoColor mode

---

### 2. HTTP Client Tests (9 tests)

Tests HTTP communication with mock server:

```bash
go test ./cmd/cli/client -run Integration -v
```

**Tests:**
- `TestClient_Get_Integration` - GET requests
- `TestClient_GetJSON_Integration` - JSON unmarshaling
- `TestClient_Post_Integration` - POST requests
- `TestClient_PostJSON_Integration` - POST with JSON response
- `TestClient_Delete_Integration` - DELETE requests
- `TestClient_Get_NotFound_Integration` - 404 error handling
- `TestClient_Post_BadRequest_Integration` - 400 error handling
- `TestClient_ServerUnavailable_Integration` - Connection errors
- `TestClient_Timeout_Integration` - Timeout behavior

**Coverage:** HTTP methods, error handling, JSON parsing, timeouts

---

### 3. Agent Command Tests (10 tests)

Tests agent management commands:

```bash
go test ./cmd/cli/commands -run Integration -v
```

**Tests:**
- `TestAgentsListCommand_Integration` - List agents (table format)
- `TestAgentsListCommand_JSON_Integration` - List agents (JSON)
- `TestAgentsStartCommand_Integration` - Start new agent
- `TestAgentsStartCommand_MissingName_Integration` - Validation
- `TestAgentsStopCommand_Integration` - Stop agent
- `TestAgentsStopCommand_NotFound_Integration` - Error handling
- `TestAgentsStatusCommand_Integration` - Get agent status
- `TestAgentsPauseCommand_Integration` - Pause agent
- `TestAgentsResumeCommand_Integration` - Resume agent
- `TestAgentsCommand_RemoteServer_Integration` - Remote connection

**Coverage:** All agent subcommands, output formats, error scenarios

---

### 4. Metrics Command Tests (4 tests)

Tests metrics and export commands:

```bash
go test ./cmd/cli/commands -run Metrics -v
```

**Tests:**
- `TestMetricsGetCommand_Integration` - Get metrics (table)
- `TestMetricsGetCommand_JSON_Integration` - Get metrics (JSON)
- `TestMetricsExportCommand_Prometheus_Integration` - Prometheus format
- `TestMetricsExportCommand_InfluxDB_Integration` - InfluxDB format
- `TestMetricsExportCommand_InvalidFormat_Integration` - Error handling

**Coverage:** Metrics retrieval, export formats, validation

---

### 5. Health Command Tests (4 tests)

Tests health check commands:

```bash
go test ./cmd/cli/commands -run Health -v
```

**Tests:**
- `TestHealthCommand_Integration` - Health check (text format)
- `TestHealthCommand_JSON_Integration` - Health check (JSON)
- `TestHealthCommand_ServerDown_Integration` - Connection refused
- `TestHealthCommand_InvalidHost_Integration` - DNS errors

**Coverage:** Health endpoint, error scenarios, connectivity

---

## Mock Server

The mock server (`cmd/cli/testing/mock_server.go`) provides:

### Features
- In-memory agent storage
- Full REST API simulation
- Realistic response data
- Error scenario simulation
- SSE streaming support

### Endpoints Mocked
```
GET    /api/health              - Server health
GET    /api/agents              - List agents
POST   /api/agents              - Create agent
GET    /api/agents/:name        - Get agent details
DELETE /api/agents/:name        - Stop agent
POST   /api/agents/:name/command - Send command
GET    /api/agents/:name/stream - SSE stream
GET    /api/metrics             - Agent metrics
GET    /api/metrics/prometheus  - Prometheus export
GET    /api/metrics/influxdb    - InfluxDB export
```

### Usage Example
```go
func TestMyCommand(t *testing.T) {
    // Start mock server
    mock := mocktest.NewMockServer()
    defer mock.Close()

    // Add test data
    mock.AddAgent("test-agent", "codex", 1001)

    // Extract host/port
    host, port := extractHostPort(mock.Server.URL)

    // Run your test
    args := []string{"--host", host, "--port", port}
    err := yourCommand(args)
    if err != nil {
        t.Fatalf("Command failed: %v", err)
    }

    // Verify results
    agent := mock.GetAgent("test-agent")
    if agent == nil {
        t.Error("Agent not found")
    }
}
```

---

## Writing New Tests

### Unit Test Template

```go
func TestYourFunction(t *testing.T) {
    // Setup
    input := "test data"
    expected := "expected result"

    // Execute
    result := yourFunction(input)

    // Verify
    if result != expected {
        t.Errorf("Expected %s, got %s", expected, result)
    }
}
```

### Integration Test Template

```go
func TestYourCommand_Integration(t *testing.T) {
    // Start mock server
    mock := mocktest.NewMockServer()
    defer mock.Close()

    // Setup test data
    mock.AddAgent("test", "codex", 1001)

    // Disable colors for testing
    output.NoColor = true

    // Extract connection info
    host, port := extractHostPort(mock.Server.URL)

    // Run command
    args := []string{"--host", host, "--port", port}
    err := yourCommand(args)

    // Verify
    if err != nil {
        t.Fatalf("Command failed: %v", err)
    }
}
```

---

## Test Best Practices

### 1. Isolate Tests
- Each test should be independent
- Use mock server for external dependencies
- Clean up resources with `defer`

### 2. Test Output Formats
- Always test JSON format for scripting
- Test table format for human readability
- Test CSV for data export

### 3. Test Error Scenarios
- Invalid inputs (missing required flags)
- Server errors (404, 500, etc.)
- Network failures (connection refused)
- Timeout scenarios

### 4. Capture Output
```go
// Capture stdout
old := os.Stdout
r, w, _ := os.Pipe()
os.Stdout = w

// Run command that prints output
yourCommand(args)

// Restore and read
w.Close()
os.Stdout = old

var buf bytes.Buffer
buf.ReadFrom(r)
output := buf.String()

// Verify output
if !strings.Contains(output, "expected") {
    t.Error("Output missing expected content")
}
```

### 5. Disable Colors in Tests
```go
output.NoColor = true
defer func() { output.NoColor = false }()
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: CLI Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-go@v2
        with:
          go-version: '1.24'

      - name: Run Unit Tests
        run: go test ./cmd/cli/output -v

      - name: Run Integration Tests
        run: go test ./cmd/cli/... -run Integration -v

      - name: Run with Race Detection
        run: go test ./cmd/cli/... -race

      - name: Generate Coverage
        run: |
          go test ./cmd/cli/... -coverprofile=coverage.out
          go tool cover -html=coverage.out -o coverage.html

      - name: Upload Coverage
        uses: actions/upload-artifact@v2
        with:
          name: coverage
          path: coverage.html
```

---

## Test Results

```
=========================================
  CLI Integration Tests
=========================================

Running unit tests...
-----------------------------------
Testing Output Formatters... ✓ PASS

Running integration tests...
-----------------------------------
Testing HTTP Client... ✓ PASS
Testing Agent Commands... ✓ PASS
Testing Metrics Commands... ✓ PASS
Testing Health Commands... ✓ PASS

=========================================
  Test Summary
=========================================
Total:  5
Passed: 5
Failed: 0

All tests passed! ✓
```

### Coverage Breakdown

| Package | Tests | Coverage |
|---------|-------|----------|
| `cmd/cli/output` | 8 | ~90% |
| `cmd/cli/client` | 9 | ~85% |
| `cmd/cli/commands` | 18 | ~80% |
| **Total** | **35** | **~85%** |

---

## Performance Benchmarks

```bash
# Run benchmarks
go test ./cmd/cli/... -bench=. -benchmem

# Example results:
BenchmarkFormatBytes-8      10000000    120 ns/op    24 B/op    2 allocs/op
BenchmarkFormatDuration-8    5000000    280 ns/op    32 B/op    3 allocs/op
BenchmarkPrintTable-8         100000  12000 ns/op  4096 B/op   15 allocs/op
```

---

## Debugging Tests

### Verbose Output
```bash
go test ./cmd/cli/commands -v -run TestAgentsListCommand
```

### Run Single Test
```bash
go test ./cmd/cli/commands -run TestAgentsStartCommand_Integration
```

### Show Test Coverage
```bash
go test ./cmd/cli/... -cover -coverprofile=coverage.out
go tool cover -html=coverage.out
```

### Race Detection
```bash
go test ./cmd/cli/... -race -v
```

### Memory Profiling
```bash
go test ./cmd/cli/output -memprofile=mem.prof
go tool pprof mem.prof
```

---

## Future Test Additions

Planned test coverage:

- [ ] Log command integration tests
- [ ] SSE streaming tests
- [ ] Query command tests (when implemented)
- [ ] Session command tests (when implemented)
- [ ] Cluster command tests (when implemented)
- [ ] Profile command tests (when implemented)
- [ ] Bash completion tests
- [ ] E2E tests with real API server
- [ ] Performance regression tests
- [ ] Load/stress tests

---

## Troubleshooting Tests

### Tests Hang
- Check for blocking operations
- Add timeout to test: `go test -timeout 30s`
- Look for unclosed servers/connections

### Tests Flaky
- Check for race conditions: `go test -race`
- Ensure proper cleanup with `defer`
- Avoid hardcoded ports/paths

### Mock Server Issues
- Verify server.Close() is called
- Check URL parsing in extractHostPort
- Ensure endpoints match exactly

---

**Test early, test often!** 🧪
