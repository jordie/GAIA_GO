# PyTest Failures - Action Plan & Remediation

## Executive Summary
Out of 58 tests, 45 passed (77.6%) and 13 failed (22.4%). The failures stem from 6 distinct root causes:
1. Database schema mismatch (tmux_sessions missing column)
2. SQL generation errors (tasks endpoint malformed query)
3. CSRF token handling (login endpoint)
4. Test isolation issues (secrets API cascading failures)
5. Feature workflow validation not implemented
6. API response format inconsistencies

**Total Time to Fix**: ~2-3 hours

---

## Failure #1: test_list_tmux_sessions (CRITICAL)

**Error**: `sqlite3.OperationalError: no such column: ts.milestone_id`

**Location**: `/Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/app.py:16171`

**Root Cause**: Query references column that doesn't exist in the database schema

**Fix**:
1. Check the current schema of `tmux_sessions` table:
   ```bash
   sqlite3 data/architect.db ".schema tmux_sessions"
   ```

2. Either:
   a. Add the missing column if it should exist:
   ```sql
   ALTER TABLE tmux_sessions ADD COLUMN milestone_id INTEGER;
   ```
   
   b. Or remove the column reference from the query if it's not needed
   
**Test**: Run after fix
```bash
python3 -m pytest tests/test_api.py::TestTmuxAPI::test_list_tmux_sessions -v
```

**Time Estimate**: 15 minutes

---

## Failure #2: test_list_tasks (CRITICAL)

**Error**: `sqlite3.OperationalError: unrecognized token: "{"`

**Location**: `/Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO/app.py:17771`

**Root Cause**: SQL query building logic is injecting malformed JSON or special characters

**Investigation Steps**:
1. Add debug logging to see what query is being built:
   ```python
   # In app.py around line 17771
   print(f"Query: {query}")
   print(f"Params: {params}")
   ```

2. Check what filters are being passed in the test:
   - Look at `tests/test_api.py::TestTasksAPI::test_list_tasks`
   - See what query parameters are being sent

**Likely Causes**:
- Filter value contains unescaped JSON object
- Query concatenation instead of parameterized queries
- Filter building logic has a bug

**Fix**:
1. Use parameterized queries (already done - check params)
2. Sanitize filter values
3. Handle JSON/dict values properly in query builder

**Test**:
```bash
python3 -m pytest tests/test_api.py::TestTasksAPI::test_list_tasks -v --tb=long
```

**Time Estimate**: 30 minutes

---

## Failure #3: test_login_success (HIGH PRIORITY)

**Error**: `500 INTERNAL SERVER ERROR` with CSRF-related warnings

**Location**: Login endpoint (`/login`)

**Root Cause**: CSRF token handling issue during test

**Investigation**:
1. Check if test is getting CSRF token from login page first
2. Verify token is being sent in POST request
3. Check session management in tests

**Fix Options**:
1. If CSRF is optional in testing, add environment variable:
   ```python
   app.config['WTF_CSRF_ENABLED'] = False  # In test config only
   ```

2. If CSRF is required, ensure test fixtures:
   ```python
   def test_login_success(self, client):
       # Get CSRF token first
       login_page = client.get('/login')
       csrf_token = extract_csrf_from_html(login_page.data)
       
       # Send login with token
       response = client.post('/login', data={
           'username': 'test',
           'password': 'test',
           'csrf_token': csrf_token
       })
   ```

**Test**:
```bash
python3 -m pytest tests/test_api.py::TestAuthEndpoints::test_login_success -v
```

**Time Estimate**: 20 minutes

---

## Failure #4: test_create_project (HIGH PRIORITY)

**Error**: `500 INTERNAL SERVER ERROR`

**Root Cause**: Unclear from error logs - likely missing field or database constraint

**Investigation**:
1. Run test with verbose traceback:
   ```bash
   python3 -m pytest tests/test_api.py::TestProjectsAPI::test_create_project -vv --tb=long
   ```

2. Check the error logs from the test run
3. Verify test data matches all required fields
4. Check if there's a unique constraint being violated

**Fix**:
1. Add missing required fields to test data
2. Use unique names to avoid conflicts
3. Check database constraints

**Time Estimate**: 20 minutes

---

## Failure #5: test_feature_status_workflow_invalid_transition

**Error**: Expected 400, Got 200

**Root Cause**: No validation of invalid status transitions

**Fix**: Add validation logic in app.py feature status update endpoint:

```python
@app.route('/api/features/<int:feature_id>/status', methods=['PUT'])
def update_feature_status(feature_id):
    # ... existing code ...
    
    # ADD THIS VALIDATION:
    valid_transitions = {
        'pending': ['in_progress'],
        'in_progress': ['completed', 'pending'],
        'completed': ['pending'],
        # etc.
    }
    
    current_status = get_current_status(feature_id)
    new_status = request.json.get('status')
    
    if new_status not in valid_transitions.get(current_status, []):
        return jsonify({'error': 'Invalid status transition'}), 400
    
    # ... rest of code ...
```

**Test**:
```bash
python3 -m pytest tests/test_api.py::TestFeaturesAPI::test_feature_status_workflow_invalid_transition -v
```

**Time Estimate**: 15 minutes

---

## Failure #6: test_feature_status_history

**Error**: History list is empty

**Root Cause**: Status changes not being recorded in history table

**Fix**:
1. Ensure status change endpoint records history:
   ```python
   # When updating status:
   db.execute('''
       INSERT INTO feature_status_history (feature_id, old_status, new_status, timestamp)
       VALUES (?, ?, ?, datetime('now'))
   ''', (feature_id, old_status, new_status))
   ```

2. Or use a trigger on the features table to auto-record changes

**Test**:
```bash
python3 -m pytest tests/test_api.py::TestFeaturesAPI::test_feature_status_history -v
```

**Time Estimate**: 15 minutes

---

## Failure #7: test_rebalance_tasks

**Error**: Response format mismatch

**Expected**: Response with 'error', 'suggestions', or 'success' key
**Actual**: Response has 'moved', 'moves', 'message' keys

**Fix**: Update test to match actual response format:

```python
def test_rebalance_tasks(self, authenticated_client):
    response = authenticated_client.post('/api/loadbalancer/rebalance')
    
    # Change from:
    # assert 'error' in response.json or 'suggestions' in response.json
    
    # To:
    assert response.status_code == 200
    data = response.json
    assert 'moved' in data or 'message' in data
    assert 'dry_run' in data
```

**OR** if the test is correct, update the endpoint to match expected format.

**Time Estimate**: 10 minutes

---

## Failure #8-13: Secrets API Cascading Failures

**Error**: Multiple KeyError: 'id' and Status 409 Conflict

**Root Cause**: Test isolation issue - first secret creation fails (409 Conflict), subsequent tests can't get the 'id'

**Why Conflict?**: Duplicate secret from previous test run not cleaned up

**Fix**: Update test fixtures to use unique names:

```python
import uuid
import time

@pytest.fixture
def secret_name():
    """Generate unique secret name for each test"""
    return f"test_secret_{int(time.time())}_{uuid.uuid4().hex[:8]}"

def test_create_secret(self, authenticated_client, secret_name):
    response = authenticated_client.post('/api/secrets',
        json={
            'name': secret_name,  # Use unique name
            'value': 'test_value',
            'category': 'token'
        })
    assert response.status_code == 200  # Or 201
    return response.json['id']

def test_view_secret(self, authenticated_client, secret_name):
    # First create
    create_response = authenticated_client.post('/api/secrets',
        json={
            'name': f"{secret_name}_view",
            'value': 'test_value'
        })
    secret_id = create_response.json['id']
    
    # Then view
    response = authenticated_client.get(f'/api/secrets/{secret_id}')
    assert response.status_code == 200
```

**Also** add cleanup in teardown:
```python
@pytest.fixture(autouse=True)
def cleanup_secrets(self, authenticated_client):
    yield
    # Clean up test secrets after each test
    response = authenticated_client.get('/api/secrets')
    for secret in response.json:
        if secret['name'].startswith('test_secret_'):
            authenticated_client.delete(f"/api/secrets/{secret['id']}")
```

**Alternative**: Use pytest-sqlite with in-memory database for tests:
```python
@pytest.fixture
def test_db():
    """In-memory database for tests"""
    db = sqlite3.connect(':memory:')
    # Initialize schema
    with open('schema.sql') as f:
        db.executescript(f.read())
    yield db
    db.close()
```

**Tests**:
```bash
python3 -m pytest tests/test_api.py::TestSecretsAPI -v
```

**Time Estimate**: 45 minutes (1-1.5 hours for full refactor)

---

## Implementation Priority

### Phase 1 (Critical - Do First) - ~45 minutes
1. Fix tmux_sessions schema (15 min)
2. Fix tasks endpoint SQL generation (30 min)

### Phase 2 (High Priority) - ~60 minutes  
3. Fix CSRF token handling (20 min)
4. Fix create_project endpoint (20 min)
5. Add feature status validation (15 min)
6. Add feature status history recording (15 min)

### Phase 3 (Medium Priority) - ~35 minutes
7. Fix test_rebalance_tasks expectations (10 min)
8. Fix secrets API test isolation (25 min)

**Total Time**: ~2.5-3 hours

---

## Quick Fix Checklist

- [ ] Check tmux_sessions schema for milestone_id column
- [ ] Fix SQL generation in tasks endpoint
- [ ] Fix CSRF handling in login test
- [ ] Debug create_project 500 error
- [ ] Add feature status transition validation
- [ ] Add feature status history recording
- [ ] Update test_rebalance_tasks expectations
- [ ] Refactor secrets tests with unique names
- [ ] Re-run full test suite
- [ ] Verify all 58 tests pass

---

## Testing After Fixes

After implementing each fix, run the specific test:
```bash
# Test individual failures
python3 -m pytest tests/test_api.py::TestTmuxAPI::test_list_tmux_sessions -v
python3 -m pytest tests/test_api.py::TestTasksAPI::test_list_tasks -v
python3 -m pytest tests/test_api.py::TestAuthEndpoints::test_login_success -v
python3 -m pytest tests/test_api.py::TestProjectsAPI::test_create_project -v
python3 -m pytest tests/test_api.py::TestFeaturesAPI -v
python3 -m pytest tests/test_api.py::TestLoadBalancerAPI::test_rebalance_tasks -v
python3 -m pytest tests/test_api.py::TestSecretsAPI -v

# Run full suite
python3 -m pytest tests/test_api.py -v --tb=short
```

---

## Database Lock Issues

The warnings about "database is locked" may indicate:
1. Multiple processes accessing database concurrently
2. Tests not properly closing connections
3. No timeout on locks

**Potential Fix**:
```python
# In conftest.py or test fixtures
import sqlite3
import os

@pytest.fixture(scope='session', autouse=True)
def db_config():
    # Set longer timeout for locked database
    sqlite3.register_adapter(lambda x: x.isoformat(), datetime)
    os.environ['SQLITE_TMPDIR'] = '/tmp'
```

Or in app.py:
```python
# Connection with timeout
db = sqlite3.connect('data/architect.db', timeout=30.0)
```

---

## Notes for Next Session

- Database migration may be needed - check migrations/ directory
- Consider adding database constraints to prevent future issues
- Tests need better isolation (fixtures, cleanup, unique names)
- API response formats should be consistent across endpoints
- Feature status transitions need documented valid paths
