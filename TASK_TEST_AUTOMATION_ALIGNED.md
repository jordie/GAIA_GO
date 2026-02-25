# TEST AUTOMATION: Align Test Suite with Implementation

**Branch:** feature/align-test-suite-0217
**Assigned to:** Comet Worker
**Priority:** 9 (High - Critical for reliability)
**Effort:** 30-35 hours (7-8 dev-days)
**Status:** Ready for implementation

---

## 🎯 Objectives

1. Fix Selenium test selectors to match actual HTML templates
2. Update test fixtures for new validation rules
3. Add integration tests for data persistence
4. Automate full test suite execution
5. Set up CI/CD integration for continuous testing

---

## 📋 TASK 1: Fix Selenium Test Selectors (Days 1-2)

### Current Issues
- Tests use outdated selector names
- Template uses: `word`, `inputWord`, `addButton`
- Tests expect: different naming conventions
- Brittle XPath selectors fail on minor template changes

### Actual Template IDs (From Application)
```html
<input id="word" type="text" placeholder="Enter a word">
<input id="inputWord" type="text" placeholder="Input word here">
<button id="addButton" class="btn btn-primary">Add Word</button>
```

### Required Selector Updates

**Find all Selenium selectors in test files:**
```bash
grep -r "find_element" tests/ | grep -E "(By\.|XPATH|CSS_SELECTOR|ID)"
```

**Update selector references:**

| Old Selector | New Selector | Element |
|--------------|--------------|---------|
| `find_element_by_id('word_input')` | `find_element(By.ID, 'word')` | Word input |
| `find_element_by_xpath('//input[@name="word"]')` | `find_element(By.ID, 'inputWord')` | Input field |
| `find_element_by_css_selector('button.add')` | `find_element(By.ID, 'addButton')` | Add button |

**Add WebDriverWait for reliability:**
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Instead of:
# button = driver.find_element(By.ID, 'addButton')

# Use:
wait = WebDriverWait(driver, 10)
button = wait.until(EC.element_to_be_clickable((By.ID, 'addButton')))
```

### Checklist
- [ ] Inventory all Selenium selectors in test suite
- [ ] Map current selectors to actual template IDs
- [ ] Update all `find_element_by_*` calls to new Selenium API
- [ ] Replace with `By.ID`, `By.CSS_SELECTOR`, `By.XPATH`
- [ ] Add `WebDriverWait` for dynamic elements
- [ ] Add `expected_conditions` checks
- [ ] Test each update locally
- [ ] Verify selectors don't break on template changes
- [ ] Document selector mapping in test file headers

---

## 📋 TASK 2: Update Test Fixtures (Days 2-3)

### Validation Rules (From Application)
- **Word**: Alphanumeric + underscore, 1-50 chars, case-insensitive
- **Duplicates**: Rejected (case-insensitive comparison)
- **Empty**: Rejected (whitespace only fails)
- **Special chars**: Rejected except underscore
- **Length**: Min 1, Max 50 characters

### Create/Update `conftest.py` Fixtures

```python
@pytest.fixture
def valid_word():
    """Valid word input"""
    return 'python'

@pytest.fixture
def invalid_words():
    """Invalid word inputs"""
    return [
        '',                    # Empty
        '  ',                  # Whitespace only
        'a' * 51,              # Too long
        'word!',               # Special chars
        'test@word',           # Special chars
        'word#',               # Special chars
    ]

@pytest.fixture
def edge_case_words():
    """Edge case inputs"""
    return [
        'a',                   # Min length
        'a' * 50,              # Max length
        'word_with_underscore',
        'UPPERCASE',
        'MixedCase',
        'word123',
    ]

@pytest.fixture
def duplicate_word(browser, db_session):
    """Create a word, return for duplicate test"""
    # Create first word
    browser.find_element(By.ID, 'inputWord').send_keys('python')
    browser.find_element(By.ID, 'addButton').click()
    return 'python'

@pytest.fixture
def clean_database(db_session):
    """Clean database before each test"""
    from models import Word
    db_session.query(Word).delete()
    db_session.commit()
    yield
    db_session.query(Word).delete()
    db_session.commit()
```

### Update Parametrized Tests

```python
@pytest.mark.parametrize('invalid_word', [
    '',
    '  ',
    'word!',
    'a' * 51,
])
def test_invalid_word_rejected(browser, invalid_word):
    """Test that invalid words are rejected"""
    browser.find_element(By.ID, 'inputWord').send_keys(invalid_word)
    browser.find_element(By.ID, 'addButton').click()

    error_msg = browser.find_element(By.CLASS_NAME, 'error-message').text
    assert error_msg  # Should show error
```

### Checklist
- [ ] Review actual validation logic in application code
- [ ] Create comprehensive fixture set
- [ ] Add parametrized tests for all edge cases
- [ ] Update assertion messages to match actual validation errors
- [ ] Create fixtures for different user states
- [ ] Add database cleanup fixtures with transaction rollback
- [ ] Document fixture purposes in docstrings
- [ ] Verify fixtures reset state properly
- [ ] Test fixtures with actual application
- [ ] Add fixture for concurrent user states

---

## 📋 TASK 3: Add Integration Tests for Data Persistence (Days 4-6)

### Test Database Setup
```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope='session')
def test_db():
    """Create test database"""
    engine = create_engine('sqlite:///test_words.db')
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(test_db):
    """Get database session for test"""
    connection = test_db.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### Integration Test Scenarios

#### Test 1: Word Creation & Retrieval
```python
@pytest.mark.integration
def test_word_persistence_ui_to_db(browser, db_session, clean_database):
    """Submit word via UI → verify in database"""
    # Submit word
    browser.find_element(By.ID, 'inputWord').send_keys('python')
    browser.find_element(By.ID, 'addButton').click()

    # Wait for success message
    wait = WebDriverWait(browser, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'success-message')))

    # Verify in database
    from models import Word
    word = db_session.query(Word).filter_by(text='python').first()
    assert word is not None
    assert word.text == 'python'
```

#### Test 2: Persistence Across Page Reload
```python
@pytest.mark.integration
def test_word_persistence_across_reload(browser, db_session, clean_database):
    """Create word → reload page → word still visible"""
    # Create word
    browser.find_element(By.ID, 'inputWord').send_keys('testing')
    browser.find_element(By.ID, 'addButton').click()
    wait = WebDriverWait(browser, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'word-list')))

    # Verify visible
    assert 'testing' in browser.page_source

    # Reload page
    browser.refresh()
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'word-list')))

    # Verify still visible
    assert 'testing' in browser.page_source

    # Verify database unchanged
    from models import Word
    word = db_session.query(Word).filter_by(text='testing').first()
    assert word is not None
```

#### Test 3: Duplicate Prevention
```python
@pytest.mark.integration
def test_duplicate_word_rejected(browser, db_session, clean_database):
    """Add word → try to add duplicate → rejected with error"""
    # Add first word
    browser.find_element(By.ID, 'inputWord').send_keys('python')
    browser.find_element(By.ID, 'addButton').click()
    wait = WebDriverWait(browser, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'success-message')))

    # Try to add duplicate
    browser.find_element(By.ID, 'inputWord').send_keys('python')
    browser.find_element(By.ID, 'addButton').click()

    # Should show error
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'error-message')))
    error_msg = browser.find_element(By.CLASS_NAME, 'error-message').text
    assert 'duplicate' in error_msg.lower() or 'exists' in error_msg.lower()

    # Should only have 1 in database
    from models import Word
    count = db_session.query(Word).filter_by(text='python').count()
    assert count == 1
```

#### Test 4: Concurrent Operations
```python
@pytest.mark.integration
def test_concurrent_word_submissions(browser1, browser2, db_session, clean_database):
    """Two browsers submit simultaneously → both saved"""
    import threading

    def submit_word(browser, word):
        browser.find_element(By.ID, 'inputWord').send_keys(word)
        browser.find_element(By.ID, 'addButton').click()

    # Submit in parallel
    t1 = threading.Thread(target=submit_word, args=(browser1, 'python'))
    t2 = threading.Thread(target=submit_word, args=(browser2, 'testing'))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both should be in database
    from models import Word
    words = db_session.query(Word).all()
    assert len(words) == 2
    word_texts = {w.text for w in words}
    assert word_texts == {'python', 'testing'}
```

#### Test 5: Error Recovery
```python
@pytest.mark.integration
def test_error_recovery_after_network_error(browser, db_session, clean_database):
    """Network error during submission → graceful recovery"""
    # Simulate error, then recover
    # Try submission
    browser.find_element(By.ID, 'inputWord').send_keys('python')
    browser.find_element(By.ID, 'addButton').click()

    # Wait for potential error
    try:
        wait = WebDriverWait(browser, 5)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'error-message')))
        # Retry
        browser.find_element(By.ID, 'addButton').click()
    except:
        pass

    # Eventually should succeed
    wait = WebDriverWait(browser, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'success-message')))

    # Verify in database
    from models import Word
    word = db_session.query(Word).filter_by(text='python').first()
    assert word is not None
```

### Checklist
- [ ] Set up test database (SQLite, separate from production)
- [ ] Create database fixtures with SQLAlchemy session
- [ ] Write 5+ integration test cases
- [ ] Add concurrent browser tests using threads
- [ ] Add error scenario tests
- [ ] Test cleanup and isolation
- [ ] Verify no test pollution (one test affects another)
- [ ] Document integration test setup
- [ ] Create test data factories if needed
- [ ] Add performance benchmarks for data operations

---

## 📋 TASK 4: Automate Full Test Suite Execution (Days 6-8)

### 1. Create `pytest.ini` Configuration

```ini
[pytest]
# test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    selenium: Selenium browser tests

# test execution
addopts =
    -v
    --strict-markers
    --tb=short
    --disable-warnings

# coverage
[coverage:run]
source = src
omit = */tests/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

### 2. Create Test Runner Script

**File: `run_tests.sh`**
```bash
#!/bin/bash

set -e

echo "Starting Test Suite..."
echo "====================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Clean previous coverage
rm -f .coverage
rm -rf htmlcov/

# Run tests
echo "Running unit tests..."
pytest tests/ -m "not integration and not selenium" --cov=src --cov-report=html

echo "Running integration tests..."
pytest tests/ -m integration --cov=src --cov-append --cov-report=html

echo "Running Selenium tests..."
pytest tests/ -m selenium --cov=src --cov-append --cov-report=html

# Generate reports
echo ""
echo "Generating test report..."
pytest tests/ \
    --html=test-report.html \
    --self-contained-html \
    -v

echo ""
echo -e "${GREEN}✓ All tests passed!${NC}"
echo "Coverage report: htmlcov/index.html"
echo "Test report: test-report.html"
```

### 3. Create Parallel Test Execution

**Option A: pytest-xdist for parallel execution**
```bash
pytest tests/ -n auto  # Use all available CPU cores
```

**Option B: Custom parallel runner in Python**
```python
# scripts/run_tests_parallel.py
import subprocess
import sys
from pathlib import Path

test_dirs = [
    'tests/unit/',
    'tests/integration/',
    'tests/selenium/',
]

processes = []
for test_dir in test_dirs:
    p = subprocess.Popen(
        [sys.executable, '-m', 'pytest', test_dir, '-v'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    processes.append((test_dir, p))

# Wait for all
failures = []
for test_dir, p in processes:
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        failures.append(test_dir)
        print(f"FAILED: {test_dir}")

if failures:
    sys.exit(1)
```

### 4. Pre-commit Hook

**File: `.pre-commit-config.yaml`**
```yaml
repos:
  # Quick tests before commit
  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest quick
        entry: bash -c 'pytest tests/ -m "not slow and not selenium" --co -q'
        language: system
        pass_filenames: false
        stages: [commit]

      - id: black
        name: black
        entry: black
        language: system
        types: [python]

      - id: flake8
        name: flake8
        entry: flake8
        language: system
        types: [python]
```

### 5. GitHub Actions Workflow

**File: `.github/workflows/test.yml`**
```yaml
name: Test Suite

on:
  push:
    branches: [dev, feature/*, main]
  pull_request:
    branches: [dev, main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-test.txt

      - name: Run tests
        run: |
          bash run_tests.sh

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: true
          flags: unittests
          name: codecov-umbrella

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-report-${{ matrix.python-version }}
          path: test-report.html
```

### Checklist
- [ ] Create `pytest.ini` with proper configuration
- [ ] Create `run_tests.sh` automation script
- [ ] Test script locally (should pass all tests)
- [ ] Configure pytest discovery patterns
- [ ] Set coverage thresholds (target: 80%+)
- [ ] Generate HTML coverage reports
- [ ] Create parallel test execution option
- [ ] Add `.pre-commit-config.yaml` hooks
- [ ] Create GitHub Actions workflow
- [ ] Test CI/CD workflow in GitHub
- [ ] Add test timeout settings
- [ ] Create requirements-test.txt for test dependencies
- [ ] Document test execution in README
- [ ] Add test results to .gitignore

---

## 📊 Implementation Timeline

| Phase | Days | Tasks |
|-------|------|-------|
| **1: Assessment** | 1 | Inventory, mapping, validation review |
| **2: Selector Fixes** | 2 | Update all selectors, add waits, test |
| **3: Fixture Updates** | 1-2 | Create fixtures, parametrize, edge cases |
| **4: Integration Tests** | 2-3 | Persistence tests, concurrent, errors |
| **5: Automation** | 2 | Runners, CI/CD, pre-commit, documentation |
| **Total** | 8-9 | |

---

## ✅ Success Criteria

### Selector Fixes
- [x] All Selenium selectors work with actual templates
- [x] No failed selectors due to incorrect IDs/XPaths
- [x] WebDriverWait used for dynamic elements
- [x] No brittle locators

### Fixtures
- [x] Fixtures match all validation rules
- [x] Edge cases covered (empty, long, special chars, duplicates)
- [x] Parametrized tests for all scenarios
- [x] Clean test isolation (no pollution between tests)

### Integration Tests
- [x] 5+ integration tests for data persistence
- [x] Tests pass 100% with clean database
- [x] Concurrent operations tested
- [x] Error recovery tested
- [x] Database state verified after each test

### Automation
- [x] Full test suite runs with single command
- [x] Coverage report generated (≥80% target)
- [x] GitHub Actions workflow active
- [x] Pre-commit hook blocks bad code
- [x] Test execution <5 minutes locally
- [x] CI/CD pipeline working

### Overall
- [x] All tests passing (100% pass rate)
- [x] No test flakiness
- [x] Documentation complete
- [x] Branch ready for PR review
- [x] Code review checklist prepared

---

## 📦 Deliverables

1. ✅ Updated test files with correct selectors
2. ✅ Comprehensive `conftest.py` with fixtures
3. ✅ Integration test suite (`tests/test_integration.py`)
4. ✅ `run_tests.sh` automation script
5. ✅ `pytest.ini` configuration
6. ✅ `.github/workflows/test.yml` GitHub Actions
7. ✅ Updated `.pre-commit-config.yaml`
8. ✅ `TEST_ALIGNMENT_SUMMARY.md` (summary of changes)
9. ✅ `TESTING_GUIDE.md` (how to run tests)
10. ✅ All tests passing (100% pass rate)
11. ✅ Coverage report (≥80%)

---

## 🔧 Technical Requirements

### Dependencies
```bash
# requirements-test.txt
pytest>=7.0
pytest-cov>=3.0
pytest-html>=3.1
pytest-xdist>=3.0  # For parallel execution
pytest-timeout>=2.1
selenium>=4.0
webdriver-manager>=3.8
sqlalchemy>=1.4
```

### Environment
- Python 3.8+
- Chrome/Firefox for Selenium tests
- SQLite for test database
- Separate test DB config from production

---

## 📝 Notes

- Use `WebDriverWait` consistently for reliability
- Keep tests independent (no shared state)
- Use descriptive test names
- Document complex test logic
- Run tests frequently during development
- Aim for high coverage (80%+) but focus on critical paths
- Consider test performance (slow tests fail often)
- Use fixtures for common setup/teardown

---

**Ready for Comet implementation via Prompt 38**
