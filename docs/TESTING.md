# Testing Framework

Comprehensive testing infrastructure to ensure quality and prevent broken deployments.

## Overview

The Architect Dashboard uses multiple layers of automated testing:
- **Happy Path Tests** - Critical user flows and health checks
- **HAR Analysis** - Frontend performance and error detection
- **Pre-commit Hooks** - Automatic testing before commits
- **GitHub Actions** - CI/CD testing on every push/PR
- **Pre-deployment Checks** - Tests run before starting the dashboard

## Test Types

### 1. Happy Path Tests

**Location:** `scripts/test_happy_paths.sh`

Tests critical functionality:
1. **Health Check** - Dashboard is responsive
2. **Login Page** - Authentication page loads
3. **Static Assets** - CSS/JS files load correctly
4. **API Endpoints** - Core APIs respond
5. **Database Connection** - Database is accessible and fast
6. **Migration Status** - All migrations applied
7. **Log Analysis** - No critical errors in logs
8. **Port Availability** - Dashboard listening on correct port

**Run manually:**
```bash
./scripts/test_happy_paths.sh
```

**Environment variables:**
```bash
DASHBOARD_URL=http://localhost:8080 ./scripts/test_happy_paths.sh
```

**Output:**
- Console output with ✅/❌/⚠️ indicators
- Test report saved to `test_results/har_files/{timestamp}/test_report.txt`
- Exit code 0 = success, 1 = failure

### 2. HAR File Analysis

**Location:** `scripts/analyze_har.py`

Analyzes HTTP Archive (HAR) files for:
- **HTTP Errors** - 4xx/5xx status codes
- **Performance** - Slow requests (>3s) and very slow requests (>10s)
- **Security** - Insecure resources, missing headers
- **Resource Sizes** - Large files (>1MB)
- **Performance Metrics** - Total requests, size, time

**Capture HAR files:**
1. Open Chrome DevTools (F12)
2. Go to Network tab
3. Perform user flow (login, navigation, etc.)
4. Right-click → "Save all as HAR with content"
5. Save to `test_results/har_files/{timestamp}/`

**Analyze HAR file:**
```bash
# Basic analysis
python3 scripts/analyze_har.py my_flow.har

# JSON output
python3 scripts/analyze_har.py my_flow.har --json

# Save report
python3 scripts/analyze_har.py my_flow.har --output report.json
```

**Exit codes:**
- 0 = PASSED (no issues)
- 1 = FAILED (critical issues found)
- 2 = WARNING (warnings present)

## Automated Testing

### Pre-commit Hooks

Tests automatically run before commits.

**Setup:**
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

**What runs:**
- Code formatting (Black)
- Linting (flake8)
- Import sorting (isort)
- YAML/JSON validation
- Happy path tests

**Skip hooks temporarily:**
```bash
git commit --no-verify -m "Emergency fix"
```

### GitHub Actions

Tests run automatically on every push/PR to main, dev, or qa branches.

**Workflow:** `.github/workflows/tests.yml`

**Actions:**
1. Checkout code
2. Set up Python
3. Install dependencies
4. Start dashboard in background
5. Run happy path tests
6. Upload test results as artifacts
7. Stop dashboard
8. Display logs on failure

**View results:**
- Go to repository → Actions tab
- Click on workflow run
- View logs and download artifacts

### Pre-deployment Testing

Tests run automatically before starting the dashboard (unless `--skip-tests` is used).

**Default behavior:**
```bash
./deploy.sh  # Runs tests, then starts dashboard
```

**Skip tests (NOT RECOMMENDED):**
```bash
./deploy.sh --skip-tests
```

**What happens:**
1. Python and dependencies checked
2. Happy path tests run
3. If tests pass → Dashboard starts
4. If tests fail → Deployment blocked with error message

## Test Development

### Adding New Happy Path Tests

Edit `scripts/test_happy_paths.sh`:

```bash
# Test N: Description
echo -e "\n[TEST N] My Test..."
if my_test_condition; then
    echo "✅ Test passed"
else
    echo "❌ Test failed"
    exit 1
fi
```

**Guidelines:**
- Use exit code 0 for success, 1 for failure
- Use ✅ for pass, ❌ for fail, ⚠️ for warnings
- Keep tests fast (<5 seconds each)
- Test critical paths only (not edge cases)

### Adding HAR Analysis Checks

Edit `scripts/analyze_har.py`:

```python
def _check_my_issue(self):
    """Check for my specific issue"""
    entries = self.data.get('log', {}).get('entries', [])

    problems = []
    for entry in entries:
        # Check for issue
        if issue_detected:
            problems.append({'details': 'issue info'})

    if problems:
        self.issues.append({  # or self.warnings, self.info
            'type': 'My Issue Type',
            'severity': 'critical',  # or 'high', 'medium', 'low'
            'count': len(problems),
            'details': problems[:5]
        })
```

Call from `analyze()` method:
```python
def analyze(self) -> Dict[str, Any]:
    # ...existing checks...
    self._check_my_issue()
    return self._generate_report()
```

## Best Practices

### For Developers

1. **Always run tests locally** before committing
2. **Never skip tests** on main/qa branches
3. **Fix failing tests immediately** - don't accumulate technical debt
4. **Add tests for new features** - update test scripts
5. **Capture HAR files** for complex UI changes
6. **Review test output** - don't ignore warnings

### For QA

1. **Capture HAR files** for all major user flows:
   - Login flow
   - Project creation
   - Feature/bug tracking
   - Dashboard navigation
   - API interactions

2. **Analyze HAR files** after capturing:
   ```bash
   python3 scripts/analyze_har.py flow.har --output results.json
   ```

3. **Review analysis results**:
   - 🔴 Critical issues → Block deployment
   - ⚠️ Warnings → Investigate and document
   - 💡 Info → Note for optimization

4. **Document issues** found in test reports

### For Deployment

1. **Never deploy without tests passing**
2. **Only use --skip-tests** in emergencies
3. **Monitor logs** after deployment:
   ```bash
   tail -f /tmp/architect_dashboard.log
   ```
4. **Run smoke tests** manually after deployment
5. **Keep test reports** for audit trail

## Troubleshooting

### Tests Fail Locally

1. **Check dashboard is running:**
   ```bash
   curl http://localhost:8080/health
   ```

2. **Check logs:**
   ```bash
   tail -50 /tmp/architect_dashboard.log
   ```

3. **Check database:**
   ```bash
   python3 -m migrations.manager status --db data/prod/architect.db
   ```

4. **Run tests with verbose output:**
   ```bash
   bash -x scripts/test_happy_paths.sh
   ```

### GitHub Actions Fail

1. **View workflow logs** in Actions tab
2. **Download test artifacts** for detailed results
3. **Check environment differences** (Python version, dependencies)
4. **Reproduce locally** with same Python version

### HAR Analysis Issues

1. **HAR file format error:**
   - Ensure file is valid JSON
   - Re-export from Chrome DevTools

2. **No issues found but problems visible:**
   - HAR may not capture console errors
   - Check browser console manually
   - Update analyzer to detect pattern

3. **Too many false positives:**
   - Adjust thresholds in `analyze_har.py`
   - Add filtering logic for known issues

## Metrics

Track test metrics over time:

- **Pass rate** - % of tests passing
- **Failure rate** - % of tests failing
- **Average test time** - Time to run all tests
- **Issues found** - Count by severity
- **Deployment blocks** - Times tests prevented bad deployment

## Future Enhancements

### Planned Features

- [ ] Unit tests for Python modules
- [ ] Integration tests for API endpoints
- [ ] Load testing with locust
- [ ] Visual regression testing
- [ ] Automated HAR capture with Selenium
- [ ] Test coverage reporting
- [ ] Performance benchmarking
- [ ] Accessibility testing

### Nice to Have

- Test result dashboard
- Historical test metrics
- Automated issue creation from test failures
- Slack/email notifications on test failures
- Parallel test execution
- Test result caching

## References

- [HAR Format Specification](http://www.softwareishard.com/blog/har-12-spec/)
- [Chrome DevTools Network](https://developer.chrome.com/docs/devtools/network/)
- [pre-commit Documentation](https://pre-commit.com/)
- [GitHub Actions](https://docs.github.com/en/actions)

## Support

For questions or issues:
1. Check this documentation
2. Review test output and logs
3. Check GitHub Issues
4. Ask in project Slack/Discord
