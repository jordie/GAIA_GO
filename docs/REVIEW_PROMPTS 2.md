# Code Review Prompts and Checklists

Comprehensive prompts and checklists for conducting thorough code reviews and system audits.

## Table of Contents

1. [Code Review Prompts](#code-review-prompts)
2. [Architecture Review](#architecture-review)
3. [Security Review](#security-review)
4. [Performance Review](#performance-review)
5. [Database Review](#database-review)
6. [API Review](#api-review)
7. [Documentation Review](#documentation-review)

---

## Code Review Prompts

### General Code Review

**Prompt for AI-Assisted Review**:
```
Review the following code for:
1. Correctness and logic errors
2. Code style and readability
3. Performance issues
4. Security vulnerabilities
5. Error handling
6. Test coverage
7. Documentation quality

Code:
[INSERT CODE HERE]

For each issue found, provide:
- Severity (critical/high/medium/low)
- Line number(s)
- Description
- Suggested fix
```

### Python Code Review

**Focused Prompt**:
```
Review this Python code following PEP 8 and best practices:

1. Type hints: Are they present and correct?
2. Error handling: Try/except blocks appropriate?
3. Resource management: Context managers used?
4. Imports: Organized and no unused imports?
5. Docstrings: Complete and accurate?
6. Performance: Any obvious bottlenecks?
7. Security: SQL injection, XSS, command injection risks?

Code:
[INSERT CODE HERE]

Provide specific line-by-line feedback.
```

### JavaScript/TypeScript Review

**Focused Prompt**:
```
Review this JavaScript/TypeScript code:

1. Async/await: Proper error handling?
2. Memory leaks: Event listeners cleaned up?
3. Dependencies: Minimal and secure?
4. Type safety: TypeScript types used correctly?
5. React patterns: Hooks used properly?
6. Performance: Unnecessary re-renders?
7. Accessibility: ARIA labels, keyboard nav?

Code:
[INSERT CODE HERE]
```

---

## Architecture Review

### System Design Review

**Prompt**:
```
Review this system architecture:

[INCLUDE ARCHITECTURE DIAGRAM OR DESCRIPTION]

Evaluate:
1. Scalability: Can it handle 10x growth?
2. Reliability: Single points of failure?
3. Maintainability: How easy to modify?
4. Security: Attack surface analysis?
5. Performance: Bottlenecks identified?
6. Cost: Resource usage optimized?
7. Observability: Monitoring and logging adequate?

For each concern, provide:
- Impact assessment
- Risk level
- Mitigation strategy
```

### Database Schema Review

**Prompt**:
```
Review this database schema:

[INSERT SCHEMA OR DDL]

Check for:
1. Normalization: Appropriate normal form?
2. Indexes: Proper indexes on query columns?
3. Foreign keys: Referential integrity enforced?
4. Data types: Optimal choices?
5. Constraints: NOT NULL, UNIQUE, CHECK constraints?
6. Migrations: Safe to apply incrementally?
7. Performance: Query patterns supported?

Suggest improvements with reasoning.
```

### API Design Review

**Prompt**:
```
Review this REST API design:

[INSERT API SPECIFICATION]

Evaluate:
1. RESTful principles: Resources properly modeled?
2. Versioning: Strategy in place?
3. Authentication: Secure and appropriate?
4. Rate limiting: Implemented?
5. Error responses: Consistent and helpful?
6. Documentation: OpenAPI/Swagger spec?
7. Pagination: Implemented for collections?
8. Filtering: Query params well-designed?

Rate each aspect 1-5 and explain issues.
```

---

## Security Review

### Security Audit Checklist

**Comprehensive Prompt**:
```
Perform a security audit of this codebase/feature:

[CONTEXT]

OWASP Top 10 Analysis:

1. **Injection**
   - SQL injection risks? Parameterized queries used?
   - Command injection? User input sanitized?
   - LDAP/NoSQL injection? Input validated?

2. **Broken Authentication**
   - Password storage: Bcrypt/Argon2 used?
   - Session management: Secure cookies, timeouts?
   - Multi-factor auth: Available for sensitive operations?

3. **Sensitive Data Exposure**
   - Encryption at rest? (database, files)
   - Encryption in transit? (TLS/HTTPS)
   - API keys/secrets: Stored securely?
   - PII handling: Compliance with regulations?

4. **XML External Entities (XXE)**
   - XML parsing: External entities disabled?
   - Document uploads: Validated and scanned?

5. **Broken Access Control**
   - Authorization checks: On every endpoint?
   - Horizontal privilege escalation: Prevented?
   - Vertical privilege escalation: Role checks?

6. **Security Misconfiguration**
   - Default credentials: Changed?
   - Debug mode: Disabled in production?
   - Error messages: No sensitive info exposed?
   - Security headers: CSP, X-Frame-Options, etc?

7. **Cross-Site Scripting (XSS)**
   - User input: Escaped/sanitized for HTML context?
   - Content-Type headers: Properly set?
   - CSP: Content Security Policy configured?

8. **Insecure Deserialization**
   - Pickle/YAML: Untrusted data deserialized?
   - JSON: Input validated before processing?

9. **Using Components with Known Vulnerabilities**
   - Dependencies: Up to date?
   - Security advisories: Monitored?
   - CVE scanning: Automated?

10. **Insufficient Logging & Monitoring**
    - Sensitive operations: Logged?
    - Log retention: Appropriate?
    - Alerting: Critical events trigger alerts?
    - Audit trail: Immutable?

For each finding, provide:
- CWE ID (if applicable)
- Severity (Critical/High/Medium/Low)
- Exploit scenario
- Remediation steps
```

### Secrets Detection

**Prompt**:
```
Scan this code for exposed secrets:

[INSERT CODE OR FILE PATHS]

Look for:
- API keys (AWS, Anthropic, OpenAI, etc.)
- Database credentials
- Private keys (SSH, TLS, JWT signing keys)
- Passwords in plaintext
- OAuth tokens
- Webhooks/callback URLs with secrets
- .env file contents in code

For each finding:
- Location (file:line)
- Type of secret
- Risk level
- Remediation (environment vars, secrets manager)
```

---

## Performance Review

### Performance Audit

**Prompt**:
```
Analyze this code/system for performance issues:

[CONTEXT]

1. **Database Performance**
   - N+1 queries: Any ORM anti-patterns?
   - Missing indexes: Slow query analysis?
   - Full table scans: Can be optimized?
   - Connection pooling: Configured?

2. **Algorithm Complexity**
   - Time complexity: O(n²) or worse?
   - Space complexity: Memory intensive?
   - Can be optimized with better algorithms/data structures?

3. **Caching**
   - Cache hits/misses: Monitored?
   - Cache invalidation: Strategy correct?
   - Redis/Memcached: Properly utilized?

4. **Network**
   - API calls: Can be batched?
   - Payload size: Can be reduced?
   - Compression: Enabled?
   - CDN: Static assets cached?

5. **Frontend Performance**
   - Bundle size: Optimized?
   - Code splitting: Implemented?
   - Lazy loading: For images/components?
   - Re-renders: Minimized (React.memo, useMemo)?

6. **Resource Usage**
   - CPU: Any hot spots?
   - Memory: Leaks or excessive usage?
   - Disk I/O: Optimized?
   - Network bandwidth: Efficient use?

For each issue:
- Quantify impact (latency, throughput, cost)
- Suggest optimization
- Estimate effort (hours)
- Expected improvement (%)
```

### Query Optimization

**Prompt**:
```
Optimize this database query:

```sql
[INSERT QUERY HERE]
```

Schema:
[INSERT RELEVANT SCHEMA]

Provide:
1. EXPLAIN ANALYZE output interpretation
2. Missing indexes to add
3. Query rewrite suggestions
4. Estimated performance improvement
5. Trade-offs of each optimization
```

---

## Database Review

### Migration Review

**Prompt**:
```
Review this database migration for safety:

```sql
[INSERT MIGRATION SQL]
```

Check for:
1. **Backwards compatibility**: Can old code still run?
2. **Locking**: Will it lock tables? Duration?
3. **Data loss risks**: Any DROP/DELETE without backup?
4. **Rollback plan**: Can it be reverted safely?
5. **Performance**: Impact on production queries?
6. **Validation**: Constraints validated before adding?

Rate risk level (Low/Medium/High) and suggest improvements.
```

### Data Model Review

**Prompt**:
```
Review this data model design:

[INSERT ERD OR SCHEMA]

Evaluate:
1. **Normalization**: 3NF achieved? Denormalization justified?
2. **Relationships**: Cardinality correct? Foreign keys?
3. **Naming**: Clear and consistent?
4. **Types**: Appropriate data types chosen?
5. **Constraints**: Business rules enforced at DB level?
6. **Indexes**: Query patterns supported?
7. **Partitioning**: Large tables partitioned?
8. **Archival strategy**: Old data handling plan?

Suggest improvements with examples.
```

---

## API Review

### REST API Review

**Detailed Prompt**:
```
Review this REST API:

Endpoints:
[LIST ENDPOINTS WITH METHODS, PATHS, PARAMS]

For each endpoint, evaluate:

1. **HTTP Methods**: Correct method used?
   - GET: Idempotent, no side effects
   - POST: Creating resources
   - PUT: Full replacement
   - PATCH: Partial update
   - DELETE: Resource deletion

2. **Status Codes**: Appropriate responses?
   - 200: Success
   - 201: Created
   - 204: No content
   - 400: Bad request
   - 401: Unauthorized
   - 403: Forbidden
   - 404: Not found
   - 409: Conflict
   - 429: Rate limited
   - 500: Server error

3. **Naming**: RESTful resource naming?
   - Plural nouns for collections (/users, not /user)
   - Hierarchical relationships (/users/123/posts)
   - No verbs in URLs

4. **Versioning**: Version strategy?
   - URL path: /v1/users
   - Header: Accept: application/vnd.api.v1+json
   - Query param: ?version=1

5. **Authentication**: Secure?
   - JWT, OAuth, API keys?
   - Expiration, refresh tokens?

6. **Rate Limiting**: Implemented?
   - Per user, per IP?
   - Headers: X-RateLimit-*

7. **Pagination**: For collections?
   - Cursor-based or offset-based?
   - Page size limits?

8. **Filtering/Sorting**: Query params?
   - ?filter[status]=active
   - ?sort=-created_at

9. **Error Responses**: Consistent format?
   ```json
   {
     "error": {
       "code": "validation_error",
       "message": "Invalid input",
       "details": [...]
     }
   }
   ```

10. **Documentation**: OpenAPI spec?

Provide score (1-10) and improvement suggestions.
```

### GraphQL API Review

**Prompt**:
```
Review this GraphQL schema:

```graphql
[INSERT SCHEMA]
```

Check for:
1. **Schema design**: Types well-structured?
2. **N+1 problem**: DataLoader used?
3. **Depth limiting**: Query depth restricted?
4. **Complexity analysis**: Query cost calculated?
5. **Pagination**: Relay cursor pagination?
6. **Error handling**: Errors vs null fields?
7. **Documentation**: Field descriptions present?
8. **Deprecation**: Old fields marked deprecated?

Suggest improvements.
```

---

## Documentation Review

### Documentation Completeness

**Prompt**:
```
Review documentation for this system/feature:

[PROVIDE LINKS OR DOCS]

Evaluate:

1. **README**
   - Clear project description?
   - Installation instructions?
   - Quick start guide?
   - Prerequisites listed?
   - Links to detailed docs?

2. **Architecture Docs**
   - System diagram present?
   - Component descriptions?
   - Data flow diagrams?
   - Deployment architecture?

3. **API Documentation**
   - All endpoints documented?
   - Request/response examples?
   - Authentication described?
   - Error codes explained?

4. **Code Comments**
   - Complex logic explained?
   - Public APIs documented?
   - TODOs tracked?
   - No commented-out code?

5. **Runbooks**
   - Deployment process documented?
   - Rollback procedure?
   - Monitoring and alerting?
   - Troubleshooting guides?

6. **User Guides**
   - Feature usage explained?
   - Screenshots included?
   - Common workflows documented?
   - FAQ section?

7. **Change Log**
   - Version history maintained?
   - Breaking changes highlighted?
   - Migration guides?

Rate completeness (0-100%) and identify gaps.
```

### Code Comment Quality

**Prompt**:
```
Review comments in this code:

[INSERT CODE]

Check for:
1. **WHY not WHAT**: Comments explain reasoning, not obvious code?
2. **Accuracy**: Comments match actual code behavior?
3. **Completeness**: Public APIs have docstrings?
4. **Format**: Follows style guide (JSDoc, docstring, etc.)?
5. **Examples**: Complex functions have usage examples?
6. **TODOs**: Tracked in issue tracker, not just comments?
7. **Clarity**: Comments add value, not noise?

Bad example:
```python
# increment counter
counter += 1  # WHY increment?
```

Good example:
```python
# Increment retry counter to trigger exponential backoff
# after 3 attempts, preventing rate limit errors
counter += 1
```

Provide feedback with examples.
```

---

## Pre-Deployment Checklist

### Production Readiness Review

**Comprehensive Prompt**:
```
Is this system ready for production deployment?

Check each category:

## 1. Functionality ✓
- [ ] All features implemented per spec
- [ ] Edge cases handled
- [ ] Error states tested
- [ ] Acceptance criteria met

## 2. Testing ✓
- [ ] Unit tests: >80% coverage
- [ ] Integration tests: Critical paths covered
- [ ] E2E tests: User workflows tested
- [ ] Performance tests: Load tested
- [ ] Security tests: Pen test completed

## 3. Security ✓
- [ ] OWASP Top 10: All mitigated
- [ ] Secrets: No hardcoded credentials
- [ ] Authentication: Properly implemented
- [ ] Authorization: Role checks in place
- [ ] Input validation: All user input sanitized
- [ ] Dependency scan: No high/critical CVEs

## 4. Performance ✓
- [ ] Load tested: 10x expected traffic
- [ ] Latency: p95 < 200ms
- [ ] Database: Indexes optimized
- [ ] Caching: Implemented where needed
- [ ] CDN: Static assets cached

## 5. Reliability ✓
- [ ] Failover: Tested and works
- [ ] Backup: Automated and tested
- [ ] Monitoring: All critical metrics
- [ ] Alerting: On-call notified
- [ ] Rollback: Procedure documented

## 6. Observability ✓
- [ ] Logging: Structured and searchable
- [ ] Metrics: Key metrics tracked
- [ ] Tracing: Distributed tracing enabled
- [ ] Dashboards: Created and accessible
- [ ] Alerts: Configured for anomalies

## 7. Documentation ✓
- [ ] Architecture: Documented
- [ ] API: OpenAPI spec exists
- [ ] Runbook: Deployment & rollback
- [ ] Troubleshooting: Common issues
- [ ] User guide: Feature usage

## 8. Operational ✓
- [ ] Deployment: Automated
- [ ] Rollback: Tested and quick
- [ ] Scaling: Auto-scaling configured
- [ ] Cost: Estimated and approved
- [ ] On-call: Team briefed

## 9. Compliance ✓
- [ ] GDPR: Personal data handling compliant
- [ ] SOC 2: Controls in place
- [ ] License: Dependencies reviewed
- [ ] Terms of Service: Updated if needed

## 10. Communication ✓
- [ ] Stakeholders: Notified
- [ ] Changelog: Updated
- [ ] Release notes: Published
- [ ] Training: Team trained if needed

For each unchecked item, explain why it's not ready.
Overall readiness score: ___%
Recommended action: [ ] Deploy  [ ] Hold  [ ] Need improvements
```

---

**Last Updated**: 2026-02-10
**Version**: 1.0
**Maintainer**: Architect Team
