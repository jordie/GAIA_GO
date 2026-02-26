# GAIA_HOME to GAIA_GO Migration Guide

Complete guide for migrating applications from deprecated GAIA_HOME (Python) to GAIA_GO (Go).

---

## Table of Contents

1. [Before You Start](#before-you-start)
2. [Migration Strategies](#migration-strategies)
3. [API Endpoint Mapping](#api-endpoint-mapping)
4. [Authentication Migration](#authentication-migration)
5. [Testing Procedures](#testing-procedures)
6. [Deployment Checklist](#deployment-checklist)
7. [Troubleshooting](#troubleshooting)
8. [Support Resources](#support-resources)

---

## Before You Start

### Prerequisites

- ✅ GAIA_GO cluster operational and tested
- ✅ Access to GAIA_GO documentation
- ✅ Staging environment available for testing
- ✅ GAIA_HOME application source code available
- ✅ Database credentials and connection strings

### Timing Estimation

| Application Type | Complexity | Effort | Timeline |
|------------------|-----------|--------|----------|
| **Simple** (1-2 endpoints) | Low | 1-2 days | 1 week |
| **Medium** (3-10 endpoints) | Medium | 3-5 days | 2-3 weeks |
| **Complex** (10+ endpoints) | High | 2-4 weeks | 1-2 months |

---

## Migration Strategies

### Strategy 1: Big Bang (Not Recommended)

Migrate all traffic at once.

**Pros**: Quick, simple
**Cons**: High risk, hard to debug, can't rollback easily

**Best For**: Simple applications with minimal data

### Strategy 2: Dual-Write (Recommended)

Write to both GAIA_HOME and GAIA_GO simultaneously.

```
Phase 1: Dual-write (GAIA_GO writes only)
  ├─ All new data written to both systems
  ├─ Reads still from GAIA_HOME
  └─ Data consistency verified

Phase 2: Gradual Read Migration
  ├─ Shift 10% of reads to GAIA_GO
  ├─ Monitor error rates
  ├─ Gradually increase to 50%
  └─ Monitor latency and errors

Phase 3: Complete Migration
  ├─ 100% of reads from GAIA_GO
  ├─ Continue dual-writes for safety
  ├─ Run in parallel for 1-2 weeks
  └─ Verify data consistency

Phase 4: Cutover
  ├─ Stop dual-writes
  ├─ Monitor for issues
  └─ GAIA_HOME kept as fallback
```

**Pros**: Low risk, easy rollback, high confidence
**Cons**: Takes longer, requires code changes

**Best For**: Production applications with data consistency requirements

### Strategy 3: Database Migration + Code Repoint

Migrate data first, then update code to use new API.

**Pros**: Clear separation of concerns
**Cons**: Requires more coordination

---

## API Endpoint Mapping

### Legacy API → GAIA_GO API Mapping

All endpoints remain the same! The legacy API compatibility layer ensures backward compatibility.

```
GAIA_HOME                       GAIA_GO (via compatibility layer)
POST   /api/sessions      →     POST   /api/sessions
GET    /api/sessions      →     GET    /api/sessions
GET    /api/sessions/{id} →     GET    /api/sessions/{id}
PUT    /api/sessions/{id} →     PUT    /api/sessions/{id}
DELETE /api/sessions/{id} →     DELETE /api/sessions/{id}

POST   /api/lessons       →     POST   /api/lessons
GET    /api/lessons       →     GET    /api/lessons
GET    /api/lessons/{id}  →     GET    /api/lessons/{id}
PUT    /api/lessons/{id}  →     PUT    /api/lessons/{id}
DELETE /api/lessons/{id}  →     DELETE /api/lessons/{id}
```

### No Endpoint Changes Needed

Your code works unchanged:

```python
# GAIA_HOME code
import requests

session = {
    'session_name': 'session-123',
    'status': 'active',
    'user_id': 'user-456'
}

response = requests.post('http://gaia-home:5000/api/sessions', json=session)
```

```python
# GAIA_GO code - EXACTLY THE SAME
import requests

session = {
    'session_name': 'session-123',
    'status': 'active',
    'user_id': 'user-456'
}

# Just change the URL, everything else is identical
response = requests.post('http://gaia-go:8080/api/sessions', json=session)
```

---

## Authentication Migration

### Currently Supported Auth Methods

GAIA_GO legacy compatibility layer supports 6 authentication methods:

#### 1. Bearer Token (JWT)
```python
headers = {
    'Authorization': 'Bearer eyJhbGc...'
}
response = requests.get('http://gaia-go:8080/api/sessions', headers=headers)
```

#### 2. API Key
```python
headers = {
    'X-API-Key': 'gaia_user-456_a1b2c3d4'
}
response = requests.get('http://gaia-go:8080/api/sessions', headers=headers)
```

#### 3. Session ID
```python
headers = {
    'X-Session-ID': 'session-123-uuid'
}
response = requests.get('http://gaia-go:8080/api/sessions', headers=headers)
```

#### 4. Basic Auth
```python
import requests

response = requests.get(
    'http://gaia-go:8080/api/sessions',
    auth=('username', 'password')
)
```

#### 5. Legacy Token Header
```python
headers = {
    'X-Legacy-Token': 'legacy_token_value'
}
response = requests.get('http://gaia-go:8080/api/sessions', headers=headers)
```

#### 6. Cookie
```python
cookies = {
    'gaia_token': 'token_value'
}
response = requests.get('http://gaia-go:8080/api/sessions', cookies=cookies)
```

### Migration Steps

1. **Identify your current auth method**:
   - Check requests for `Authorization`, `X-API-Key`, or other auth headers
   - Look for cookies in request handling

2. **Use the same method with GAIA_GO**:
   - Your existing auth works unchanged
   - No code modifications required

3. **Optional: Upgrade to new JWT tokens** (recommended):
   - New JWT format provides better security
   - Longer expiration times (vs legacy tokens)
   - Better integration with Kubernetes

---

## Testing Procedures

### 1. Local Testing

```bash
# Start GAIA_GO locally
docker-compose up -d

# Run your application against GAIA_GO
GAIA_URL=http://localhost:8080 pytest tests/
```

### 2. Staging Testing

```bash
# Point to staging GAIA_GO
export GAIA_HOME_URL=https://gaia-staging.example.com

# Run full test suite
pytest tests/ -v

# Test each endpoint
pytest tests/test_sessions.py -v
pytest tests/test_lessons.py -v

# Load testing
locust -f locustfile.py --host=https://gaia-staging.example.com
```

### 3. Data Validation

```python
# Verify data consistency after migration
import requests

# Get data from both systems
gaia_home_data = requests.get('http://gaia-home:5000/api/sessions').json()
gaia_go_data = requests.get('http://gaia-go:8080/api/sessions').json()

# Compare
assert len(gaia_home_data) == len(gaia_go_data)
for home, go in zip(gaia_home_data, gaia_go_data):
    assert home['session_name'] == go['session_name']
    assert home['status'] == go['status']
    assert home['user_id'] == go['user_id']
```

### 4. Performance Testing

```bash
# Compare latency
ab -n 1000 -c 10 http://gaia-home:5000/api/sessions
ab -n 1000 -c 10 http://gaia-go:8080/api/sessions

# Expected results
GAIA_HOME: Requests per second: ~500
GAIA_GO:   Requests per second: ~2000+ (4x faster)
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Staging testing complete (all tests passing)
- [ ] Performance testing shows acceptable results
- [ ] Data validation successful
- [ ] Rollback procedure documented and tested
- [ ] Team trained on new system
- [ ] Customer communication sent
- [ ] Monitoring dashboards configured
- [ ] Support team briefed

### Deployment Phase

- [ ] Monitoring dashboard open
- [ ] Team on standby for issues
- [ ] Update application configuration (if needed)
- [ ] Deploy updated client library (if applicable)
- [ ] Monitor for errors and issues (30 minutes minimum)
- [ ] Verify all functionality working
- [ ] Check application logs for errors
- [ ] Confirm customer reports no issues

### Post-Deployment

- [ ] Monitor for 24 hours
- [ ] Check daily performance metrics
- [ ] Review error logs
- [ ] Gather team feedback
- [ ] Document any issues encountered
- [ ] Plan remediation if needed

---

## Troubleshooting

### Issue: 401 Unauthorized

**Cause**: Authentication token not recognized
**Solution**:
```python
# Check your auth header format
headers = {
    'Authorization': 'Bearer YOUR_TOKEN'  # Correct
    # OR
    'X-API-Key': 'YOUR_API_KEY'  # Correct
}
```

### Issue: Session Not Found After Migration

**Cause**: Session ID format changed
**Solution**:
```python
# Check session exists in GAIA_GO
response = requests.get(f'http://gaia-go:8080/api/sessions/{session_id}')
if response.status_code == 404:
    # Session wasn't migrated, create it
    requests.post('http://gaia-go:8080/api/sessions', json=session_data)
```

### Issue: Timeouts or Slow Performance

**Cause**: Network or load issue
**Solution**:
```python
# Increase timeout
import requests

requests.get(
    'http://gaia-go:8080/api/sessions',
    timeout=30  # Increase from default 5 to 30 seconds
)

# Check GAIA_GO cluster health
curl http://gaia-go:8080/health | jq .

# Monitor system resources
kubectl top nodes
kubectl top pods -n default
```

### Issue: Data Inconsistency Between Systems

**Cause**: Dual-write not synchronized
**Solution**:
```python
# Check sync status
response = requests.get('http://gaia-go:8080/api/migration/metrics')
metrics = response.json()

# If conflicts exist, resolve manually
if metrics['total_writes'] != metrics['successful_writes']:
    # Investigate and resync data
```

### Issue: "Legacy API no longer supported" Error

**Cause**: GAIA_HOME has been shut down
**Solution**:
```
This error occurs after August 25, 2026.
All applications must be migrated to GAIA_GO by then.

If you see this error before the deadline, contact support.
```

---

## Support Resources

### Documentation

- [GAIA_GO API Documentation](./API.md)
- [Legacy API Compatibility Guide](./LEGACY_API_COMPATIBILITY.md)
- [Deprecation Notice](../DEPRECATION_NOTICE.md)
- [Sunset Timeline](../SUNSET_TIMELINE.md)

### Community

- **Slack**: #gaia-migration
- **Email**: gaia-migration@example.com
- **GitHub Issues**: [GAIA_GO Issues](https://github.com/example/gaia-go/issues)
- **Office Hours**: Wed & Fri 10 AM - 12 PM PT

### Examples & Samples

```python
# Python client example
from gaia import Client

# GAIA_HOME old way
# client = Client(base_url='http://gaia-home:5000')

# GAIA_GO new way
client = Client(base_url='http://gaia-go:8080')

# Everything else is identical
sessions = client.sessions.list()
session = client.sessions.create(name='session-123', status='active')
```

---

## FAQ

**Q: Do I have to migrate?**
A: Yes, by August 25, 2026, GAIA_HOME will be shut down.

**Q: What if my application breaks during migration?**
A: The legacy compatibility layer ensures backward compatibility. If issues occur, rollback to GAIA_HOME and contact support.

**Q: Will my data be lost?**
A: No, all data is automatically migrated and validated.

**Q: How long will migration take?**
A: 1 day to 2 months depending on complexity. See timing estimation above.

**Q: Can I test without affecting GAIA_HOME?**
A: Yes, use the staging environment. Legacy compatibility layer ensures zero impact on production GAIA_HOME.

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| Feb 25, 2026 | 1.0 | Initial migration guide |

---

## Next Steps

1. Review this guide
2. Identify your application type (simple/medium/complex)
3. Choose migration strategy (dual-write recommended)
4. Set up staging environment
5. Test thoroughly
6. Plan deployment
7. Execute migration
8. Celebrate!

Questions? Contact gaia-migration@example.com
