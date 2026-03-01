# Phase 5 Testing Guide

**Version**: 1.0
**Last Updated**: March 1, 2026
**Status**: Complete

## Quick Start

### Run All Tests
```bash
go test -v ./pkg/services/rate_limiting
```

### Run Tests by Phase
```bash
# Phase 5a: Unit Tests (28 tests)
go test -v -run "TestCheckLimit|TestRule|TestQuota" ./pkg/services/rate_limiting -short

# Phase 5b: Integration Tests (9 tests)
go test -v -run "TestFull|TestDaily|TestMultiple" ./pkg/services/rate_limiting -short

# Phase 5c: Load Tests (5 tests)
go test -v -run "TestConcurrent|TestHigh|TestMany|TestLarge" ./pkg/services/rate_limiting -timeout 120s -short

# Phase 5d: E2E Tests (6 tests)
go test -v -run "TestFullAdmin|TestMultiTenant|TestQuota" ./pkg/services/rate_limiting -short
```

### Generate Coverage Reports
```bash
# Generate coverage file
go test -coverprofile=coverage.out ./pkg/services/rate_limiting

# View coverage summary
go tool cover -func=coverage.out

# Generate HTML report
go tool cover -html=coverage.out -o coverage.html
```

## Performance Baselines

### Latency Targets
| Operation | Target (p99) | Status |
|-----------|--------------|--------|
| CheckLimit | < 5ms | Defined |
| Rule evaluation | < 5ms | Defined |
| Query time | < 100ms | Defined |

### Throughput Targets
| Metric | Target | Status |
|--------|--------|--------|
| Requests/sec | > 10,000 req/s | Defined |
| Concurrent | 100+ goroutines | Defined |

### Memory Targets
| Scenario | Target | Status |
|----------|--------|--------|
| Rule cache | < 500MB (1K rules) | Defined |
| Sustained | < 100MB growth | Defined |

## CI/CD Integration

### GitHub Actions
```bash
cat .github/workflows/test-phase-5.yml
```

### Pre-commit Hooks
```bash
bash scripts/install-git-hooks.sh
```

## Test Development Workflow

### Adding New Tests
1. Identify test location (unit/integration/load/e2e)
2. Follow naming: `Test<Feature><Scenario>`
3. Use appropriate setup function
4. Implement using AAA pattern
5. Run tests locally before committing

## Troubleshooting

### Tests Won't Compile
```bash
go build ./pkg/services/rate_limiting
go clean -cache
go mod tidy
```

### Coverage Below Target
```bash
go test -coverprofile=coverage.out ./pkg/services/rate_limiting
go tool cover -html=coverage.out -o coverage.html
```

### Performance Analysis
```bash
# CPU profiling
go test -cpuprofile=cpu.prof ./pkg/services/rate_limiting
go tool pprof cpu.prof

# Memory profiling
go test -memprofile=mem.prof ./pkg/services/rate_limiting
go tool pprof mem.prof

# Race detection
go test -race ./pkg/services/rate_limiting -short
```

## Related Documentation

- [Phase 5 Testing Plan](./PHASE_5_TESTING_PLAN.md)
- [Phase 5 Status Reports](./PHASE_5_PROGRESS.md)
- [Rate Limiting Guide](./RATE_LIMITING_GUIDE.md)
