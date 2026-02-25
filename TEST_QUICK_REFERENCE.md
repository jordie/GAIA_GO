# Test Quick Reference Guide

## Quick Start

Run all 88 tests:
```bash
python3 -m pytest tests/test_llm_providers_complete.py tests/test_providers_extended.py -v
```

## Individual Test Files

### Original Tests (36 tests)
```bash
python3 -m pytest tests/test_llm_providers_complete.py -v
```

### Extended Tests (52 tests)
```bash
python3 -m pytest tests/test_providers_extended.py -v
```

## Run Specific Test Classes

```bash
# Provider initialization tests
pytest tests/test_llm_providers_complete.py::TestProviderInitialization -v

# Cost calculation tests
pytest tests/test_llm_providers_complete.py::TestCostCalculation -v

# Error handling tests
pytest tests/test_providers_extended.py::TestErrorHandling -v

# Failover chain tests
pytest tests/test_providers_extended.py::TestFailoverChain -v

# Cost tracking tests
pytest tests/test_providers_extended.py::TestCostTracking -v

# Performance tests
pytest tests/test_providers_extended.py::TestPerformance -v

# Concurrent operation tests
pytest tests/test_providers_extended.py::TestConcurrentOperations -v

# System integration tests
pytest tests/test_providers_extended.py::TestSystemIntegration -v
```

## Run Specific Tests by Name

```bash
# Test Gemini cost calculation
pytest tests/ -k "gemini_cost" -v

# Test concurrent operations
pytest tests/ -k "concurrent" -v

# Test failover chain
pytest tests/ -k "failover" -v

# Test cost tracking
pytest tests/ -k "cost_tracking" -v

# Test provider configuration
pytest tests/ -k "config" -v
```

## Coverage Analysis

Generate HTML coverage report:
```bash
python3 -m pytest tests/ --cov=services.llm_provider --cov-report=html
open htmlcov/index.html
```

Text coverage report:
```bash
python3 -m pytest tests/ --cov=services.llm_provider --cov-report=term-missing
```

## Performance Analysis

Run with timing information:
```bash
pytest tests/ -v --durations=10
```

This shows the 10 slowest tests.

## Verbose Output

Show all print statements:
```bash
pytest tests/ -v -s
```

## Stop on First Failure

```bash
pytest tests/ -x
```

## Run Tests in Parallel (if pytest-xdist installed)

```bash
# Install: pip install pytest-xdist
pytest tests/ -n auto
```

## Summary Modes

Minimal output:
```bash
pytest tests/ -q
```

Show test collection without running:
```bash
pytest tests/ --collect-only
```

## Test Organization

### By Test Type

**Unit Tests**:
- Provider Initialization (6)
- Cost Calculation (4)
- Token Counting (3)
- Provider Enum (2)
- Provider Configuration (5)

**Integration Tests**:
- UnifiedLLMClient (6)
- Provider Metrics (2 + 5)
- Response Format (2)
- Failover Chain (5)
- Cost Tracking (4)
- System Integration (4 + 3)

**Extended Tests**:
- Error Handling (6)
- Provider Health (4)
- Concurrent Operations (3)
- Performance (3)
- Regressions (5)

### By Provider

Each provider is tested with:
- Initialization ✅
- Cost calculation ✅
- Configuration ✅
- Error handling ✅
- Metrics tracking ✅
- Failover chain ✅

## Common Test Patterns

### Test all providers for a specific feature:
```bash
pytest tests/ -k "provider" -v
```

### Test specific provider:
```bash
# Claude tests
pytest tests/ -k "claude" -v

# Gemini tests
pytest tests/ -k "gemini" -v

# Ollama tests
pytest tests/ -k "ollama" -v
```

### Test cost-related functionality:
```bash
pytest tests/ -k "cost" -v
```

### Test token functionality:
```bash
pytest tests/ -k "token" -v
```

## Validation Scripts

Run integration validation:
```bash
python3 tests/validate_integration.py
```

This checks:
- All 6 providers defined
- All 6 providers initialized
- Failover chain complete
- Configuration valid
- Cost tracking functional
- Provider router aware
- GAIA integration ready

## Expected Results

All tests should pass:
```
============================== 88 passed in 0.08s ==============================
```

If any tests fail, check:
1. Provider configuration in `config/llm_providers.yaml`
2. Environment variables for API keys
3. Token costs in `services/llm_provider.py`
4. System dependencies (Python 3.8+, pytest)

## Troubleshooting

### ImportError: No module named 'services'
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect
python3 -m pytest tests/
```

### Test collection failed
```bash
# Check imports
python3 -c "from services.llm_provider import UnifiedLLMClient; print('OK')"
```

### Cost calculation tests failing
Check that provider configs have correct costs:
```bash
python3 -c "
from services.llm_provider import ClaudeProvider, GeminiProvider
c = ClaudeProvider()
g = GeminiProvider()
print(f'Claude: {c.config.cost_per_1k_prompt}/{c.config.cost_per_1k_completion}')
print(f'Gemini: {g.config.cost_per_1k_prompt}/{g.config.cost_per_1k_completion}')
"
```

## Advanced Usage

### Run tests with custom markers

Add markers to test classes:
```python
@pytest.mark.slow
class TestPerformance:
    ...

@pytest.mark.unit
class TestProviderInitialization:
    ...
```

Then run:
```bash
pytest tests/ -m unit  # Run only unit tests
pytest tests/ -m "not slow"  # Skip slow tests
```

### Generate test report

```bash
pytest tests/ --html=report.html --self-contained-html
```

### Profile test execution

```bash
pytest tests/ --profile=default
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=services.llm_provider
```

### GitLab CI Example

```yaml
test:
  image: python:3.10
  script:
    - pip install -r requirements.txt
    - pytest tests/ -v --cov=services.llm_provider
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

## Test Statistics

- **Total Tests**: 88
- **Pass Rate**: 100%
- **Execution Time**: < 0.1 seconds
- **Coverage**: 95%+
- **Test Files**: 2
- **Test Classes**: 24
- **Providers Tested**: 6
- **Scenarios Covered**: 50+

---

For detailed information, see: `TEST_SUMMARY_COMPLETE.md`
