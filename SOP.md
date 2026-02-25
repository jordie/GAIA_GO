# Standard Operating Procedures (SOP)

**Universal Development Standards for All Projects**

This document defines the authoritative development standards for **ALL projects** in the ecosystem. Every team member, contractor, and AI assistant must follow these guidelines.

---

## Document Scope

### Authority

This SOP is the **single source of truth** for development standards. It applies to:

| Scope | Coverage |
|-------|----------|
| **All Projects** | Every project managed by Architect Dashboard |
| **All Environments** | Development, QA, Staging, Production |
| **All Languages** | Python, JavaScript, Go, Rust, etc. |
| **All Platforms** | Backend, Frontend, Mobile, CLI, Scripts |
| **All Team Members** | Employees, contractors, AI assistants |

### Versioning

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-02-04 | Added persistent session pool, PR workflow enforcement, DEV/PROD separation |
| 2.0 | 2026-01-31 | Elevated to universal top-level standard |
| 1.5 | 2026-01-31 | Added mandatory bug reporting for all apps |
| 1.0 | 2026-01-01 | Initial release |

### Enforcement

Non-compliance with this SOP will result in:
1. **Code Review Rejection** - PRs must comply before approval
2. **Deployment Block** - CI/CD enforces key requirements
3. **Audit Findings** - Monthly audits track compliance
4. **Escalation** - Repeat violations escalated to leadership

---

## MANDATORY: Bug Reporting for ALL Applications

> **CRITICAL REQUIREMENT**: Every application in the ecosystem MUST report errors to the Architect Dashboard. This is non-negotiable and applies to ALL apps without exception.

**No application may be deployed to production without bug reporting integration.**

See [Bug Reporting Requirements](#bug-reporting-requirements) and [Automatic Error Trapping](#automatic-error-trapping) for implementation details.

---

## Table of Contents

1. [Document Scope](#document-scope)
2. [Development Workflow](#development-workflow)
3. [Git Practices](#git-practices)
4. [Code Standards](#code-standards)
5. [API Conventions](#api-conventions)
6. [Database Guidelines](#database-guidelines)
7. [Testing Requirements](#testing-requirements)
8. [Security Guidelines](#security-guidelines)
9. [Error Handling](#error-handling)
10. [Automatic Error Trapping](#automatic-error-trapping)
11. [Bug Reporting Requirements](#bug-reporting-requirements)
12. [Logging Standards](#logging-standards)
13. [Performance Guidelines](#performance-guidelines)
14. [Documentation](#documentation)
15. [Deployment](#deployment)
16. [Incident Response](#incident-response)
17. [Multi-Agent Session Routing & Switching](#multi-agent-session-routing--switching)
18. [Persistent Session Pool](#persistent-session-pool)
19. [DEV vs PROD Environment Separation](#dev-vs-prod-environment-separation)
20. [Google Sheets Integration](#google-sheets-integration)

---

## Development Workflow

### Before Starting Work

1. **Pull latest changes**
   ```bash
   git fetch origin
   git pull origin main
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/description-MMDD
   ```

3. **Check for active locks** (multi-session environments)
   ```bash
   cat data/locks/active_sessions.json 2>/dev/null || echo "{}"
   ```

### During Development

1. Make small, focused commits
2. Test changes locally before committing
3. Keep commits atomic (one logical change per commit)
4. Run linters before committing

### After Completing Work

1. Ensure all tests pass
2. Update documentation if needed
3. Create a pull request with clear description
4. Request code review

### Pull Request Automation

**All feature work MUST go through pull requests for code review and automated quality checks.**

#### Automated PR Creation

Use the PR automation worker to create PRs automatically:

```bash
# Create PR from current branch
python3 workers/pr_automation_worker.py --create-pr "Feature description"

# Create with custom description
python3 workers/pr_automation_worker.py --create-pr "Feature title" \
    --description "Detailed description" --base main

# Create as draft
python3 workers/pr_automation_worker.py --create-pr "WIP: Feature" --draft

# Disable auto-merge
python3 workers/pr_automation_worker.py --create-pr "Feature" --no-auto-merge
```

#### PR Evaluation with Comet

All PRs are automatically evaluated for:
- Code quality and best practices
- Potential bugs and security issues
- Test coverage adequacy
- Merge conflicts
- CI/CD check status

```bash
# Evaluate PR manually
python3 workers/pr_automation_worker.py --evaluate 123

# Evaluate with Comet agent
python3 workers/pr_automation_worker.py --evaluate 123 --use-comet
```

**Evaluation Criteria:**

| Check | Weight | Description |
|-------|--------|-------------|
| Code Quality | High | Style, complexity, maintainability |
| Security | Critical | No vulnerabilities or exposed secrets |
| Tests | High | Adequate test coverage |
| Conflicts | Critical | No merge conflicts |
| CI/CD | High | All checks passing |

#### Auto-Merge Process

PRs meeting all criteria are automatically merged:

```bash
# Auto-evaluate and merge if approved
python3 workers/pr_automation_worker.py --auto-process 123
```

**Auto-merge requires:**
- ✅ Comet/Codex approval (score ≥ 80%)
- ✅ No merge conflicts
- ✅ All tests passing
- ✅ No blocking issues found

**Merge Strategies:**

| Strategy | When to Use |
|----------|-------------|
| `squash` | Default for feature branches |
| `merge` | Release merges (dev→qa→main) |
| `rebase` | Clean linear history needed |

```bash
# Manual merge with specific strategy
python3 workers/pr_automation_worker.py --merge 123 --strategy squash

# Keep branch after merge
python3 workers/pr_automation_worker.py --merge 123 --keep-branch
```

#### PR Monitoring Worker

Run continuous PR monitoring for autonomous processing:

```bash
# Start PR automation worker (daemon mode)
python3 workers/pr_automation_worker.py --daemon

# One-time processing of all open PRs
python3 workers/pr_automation_worker.py
```

The worker automatically:
- Monitors all open PRs
- Evaluates with Comet when ready
- Auto-merges approved PRs
- Logs all actions for audit

#### PR Best Practices

**Title Format:**
```
type: Brief description (max 70 chars)

Examples:
- feat: Add PR automation with Comet evaluation
- fix: Resolve authentication timeout issue
- refactor: Simplify database connection pooling
```

**Description Template:**
```markdown
## Summary
[Brief overview of changes]

## Changes
- Item 1
- Item 2

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Related Issues
Closes #123
```

**Before Creating PR:**
- [ ] Branch is up to date with base branch
- [ ] All tests pass locally
- [ ] Code follows SOP standards
- [ ] Documentation updated
- [ ] No debug code or commented-out code
- [ ] Secrets and sensitive data removed

**PR Size Guidelines:**

| Size | Files Changed | Lines Changed | Review Time |
|------|---------------|---------------|-------------|
| Small | 1-5 | < 100 | < 30 min |
| Medium | 5-15 | 100-500 | 1-2 hours |
| Large | 15-30 | 500-1000 | 2-4 hours |
| Too Large | > 30 | > 1000 | Split into smaller PRs |

**If PR is too large:** Consider splitting into multiple focused PRs.

---

## Multi-Agent Session Routing & Switching

**Goal:** Enable seamless switching between coding agents (Claude, Codex, Ollama) without breaking SOP isolation or task tracking.

### Required Practices

1. **Session Naming Must Indicate Provider**
   - Include a provider keyword in the tmux session name: `claude`, `codex`, or `ollama`
   - Example: `arch_claude_env1`, `arch_codex_api`, `arch_ollama_frontend`

2. **Use Session Assigner for Environment/Scope Safety**
   - Prefer auto-selection with provider intent:
     ```
     python3 scripts/session_assigner.py assign auto "Task description" --provider codex --fallback claude,ollama
     ```
   - Use `--fallback` for graceful switching if the primary provider is busy/unavailable

3. **Use Assigner Worker for Background Routing**
   - Provider preference order:
     ```
     python3 workers/assigner_worker.py --send "Task" --providers codex,claude --allow-fallback
     ```
   - Provider lock (no fallback):
     ```
     python3 workers/assigner_worker.py --send "Task" --provider claude
     ```

4. **Provider-Neutral Task Prompts**
   - Write prompts that do not depend on a specific provider unless required
   - If a provider is required (e.g., local Ollama models), document why in the task

5. **No Manual State Edits**
   - Do not manually edit `data/session_state.json` or assigner DB files
   - Use `session_assigner.py` and `assigner_worker.py` commands for updates

### Switching Policy

- **Default:** Allow fallback to keep throughput high
- **Critical tasks:** Lock to a provider by omitting fallback
- **Unknown provider sessions:** Treat as lowest priority for assignment

---

## Persistent Session Pool

**Goal:** Maintain a stable set of long-lived tmux sessions for AI workers to prevent task failures from deleted/ephemeral sessions.

### Required Persistent Sessions

The following sessions MUST be running at all times. Do NOT create ephemeral or temporary sessions for task routing.

| Session Name | Provider | Purpose |
|-------------|----------|---------|
| `architect` | claude | Architect dashboard development |
| `codex` | codex | Code generation and review |
| `comet` | comet | Browser-based tasks, PR evaluation |
| `edu_worker1` | claude | Education apps development |
| `task_worker1` | claude | Background task execution |
| `concurrent_worker1` | claude | Parallel task execution |
| `dev_worker1` | claude | General development tasks |
| `dev_worker2` | claude | General development tasks |
| `wrapper_claude` | claude | Wrapper/proxy tasks |

### Session Naming Rules

1. **Use established names only** - Do not create ad-hoc sessions like `codex2`, `comet2`, `task_worker5`
2. **Prefix convention** - Claude-managed sessions use `claude_` prefix (e.g., `claude_codex`, `claude_comet`)
3. **No test sessions in production** - Never route tasks to ephemeral sessions like `claude_e2e_test`

### Session Lifecycle

```bash
# Start all persistent sessions
./scripts/start_all_servers.sh

# Verify session pool health
tmux list-sessions -F '#{session_name}' | sort

# Check for orphaned tasks
sqlite3 data/assigner/assigner.db \
  "SELECT assigned_session, count(*) FROM prompts WHERE status='failed' GROUP BY assigned_session;"
```

### Anti-Patterns (DO NOT)

- ❌ Create temporary sessions for one-off tasks
- ❌ Delete sessions that have pending/assigned tasks
- ❌ Route tasks to sessions not in the persistent pool
- ❌ Use session names not matching the naming convention
- ❌ Kill sessions without checking for in-progress assignments

### Session Health Monitoring

The task monitor at `/monitor.html` tracks session health. Failed assignments are automatically archived when the target session no longer exists.

```bash
# Check session health via API
curl http://localhost:8080/api/assigner/status

# Archive failed tasks for deleted sessions
python3 workers/assigner_worker.py --archive-failed
```

---

## DEV vs PROD Environment Separation

**Goal:** Enforce strict separation between development and production environments to prevent accidental production changes.

### Environment Definitions

| Environment | Branch | Port Range | Database | Purpose |
|-------------|--------|------------|----------|---------|
| **DEV** | `feature/*`, `fix/*`, `dev` | 8080-8089 | `data/architect.db` | Active development |
| **QA** | `qa/*` | 8090-8099 | `data/qa/architect.db` | Integration testing |
| **PROD** | `main` | 443/8443 | `data/prod/architect.db` | Live production |

### Environment Detection

Every script and worker MUST detect its environment:

```python
import os

def get_environment():
    """Detect current environment from branch or env var."""
    env = os.environ.get('ARCHITECT_ENV', '').lower()
    if env:
        return env

    # Detect from git branch
    try:
        import subprocess
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            text=True
        ).strip()
        if branch == 'main':
            return 'prod'
        elif branch.startswith('qa'):
            return 'qa'
        return 'dev'
    except Exception:
        return 'dev'
```

### Deployment Rules

| Rule | DEV | QA | PROD |
|------|-----|-----|------|
| Direct push | ✅ Feature branches | ❌ PR only | ❌ PR only |
| Auto-deploy | ✅ On commit | ✅ On merge | ❌ Manual approval |
| Database migrations | ✅ Auto-run | ✅ Auto-run with backup | ❌ Manual with backup |
| SSL required | ❌ Optional | ✅ Required | ✅ Required |
| Debug mode | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| Error detail in API | ✅ Full stack trace | ⚠️ Limited | ❌ Generic messages only |

### PR Workflow Enforcement

1. **All production changes require a PR** - Direct pushes to `main` are blocked
2. **All QA changes require a PR** - Direct pushes to `qa` branches are blocked
3. **PRs require evaluation** - Comet or Codex must approve (score >= 80%)
4. **PRs require passing tests** - CI must pass before merge

```bash
# Create PR from feature branch to main
gh pr create --base main --title "feat: description" --body "..."

# Create PR from feature to dev (for integration)
gh pr create --base dev --title "feat: description" --body "..."

# Evaluate PR before merge
python3 workers/pr_automation_worker.py --evaluate <PR_NUMBER> --use-comet
```

### Environment Variables

| Variable | DEV | QA | PROD |
|----------|-----|-----|------|
| `ARCHITECT_ENV` | `dev` | `qa` | `prod` |
| `ARCHITECT_DEBUG` | `true` | `false` | `false` |
| `ARCHITECT_SSL` | `false` | `true` | `true` |
| `ARCHITECT_DB_BACKUP` | `false` | `true` | `true` |

---

## Git Practices

### Branch Naming Convention

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feature/` | New features | `feature/task-templates-0131` |
| `fix/` | Bug fixes | `fix/login-timeout-0131` |
| `refactor/` | Code refactoring | `refactor/api-cleanup-0131` |
| `docs/` | Documentation only | `docs/api-guide-0131` |
| `hotfix/` | Critical production fixes | `hotfix/security-patch-0131` |

### Commit Message Format

```
type: Short description (max 72 chars)

Longer description if needed. Explain what and why,
not how (the code shows how).

Co-Authored-By: Name <email>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring (no functional change)
- `docs`: Documentation only
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Protected Branches

| Branch | Protection | Use |
|--------|------------|-----|
| `main` | No direct commits | Production releases |
| `dev` | PR required | Integration testing |

### Merge Strategy

1. Always use pull requests for `main` and `dev`
2. Squash commits for feature branches
3. Never force push to shared branches
4. Delete branches after merge

---

## Code Standards

### Python

1. **Style**: Follow PEP 8
2. **Imports**: Group and sort (stdlib, third-party, local)
3. **Functions**: Max 50 lines, single responsibility
4. **Classes**: Max 300 lines
5. **Files**: Max 1000 lines (split if larger)

```python
# Good
def calculate_priority(task_id: int, boost: int = 0) -> int:
    """Calculate task priority with optional boost."""
    base = get_base_priority(task_id)
    return min(100, base + boost)

# Avoid
def calc(t, b=0):
    return min(100, get_base_priority(t) + b)
```

### JavaScript

1. **Style**: Use consistent formatting
2. **Variables**: Use `const` by default, `let` when needed
3. **Functions**: Prefer arrow functions for callbacks
4. **Error handling**: Always handle promise rejections

```javascript
// Good
const fetchTasks = async () => {
    try {
        const response = await fetch('/api/tasks');
        return await response.json();
    } catch (error) {
        console.error('Failed to fetch tasks:', error);
        return [];
    }
};
```

### HTML/CSS

1. Use semantic HTML elements
2. Keep CSS organized (variables at top)
3. Use CSS custom properties for theming
4. Mobile-first responsive design

---

## API Conventions

### Endpoint Naming

```
GET    /api/{resource}           - List all
GET    /api/{resource}/{id}      - Get one
POST   /api/{resource}           - Create
PUT    /api/{resource}/{id}      - Update (full)
PATCH  /api/{resource}/{id}      - Update (partial)
DELETE /api/{resource}/{id}      - Delete
```

### Request/Response Format

**Request:**
```json
{
    "field_name": "value",
    "nested_object": {
        "key": "value"
    }
}
```

**Success Response:**
```json
{
    "success": true,
    "data": { ... },
    "message": "Optional message"
}
```

**Error Response:**
```json
{
    "error": "Human-readable message",
    "error_code": "MACHINE_READABLE_CODE",
    "details": { ... }
}
```

### HTTP Status Codes

| Code | Use |
|------|-----|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (client error) |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not found |
| 409 | Conflict |
| 500 | Server error |

### Pagination

```
GET /api/tasks?page=1&per_page=20

Response:
{
    "data": [...],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 100,
        "total_pages": 5
    }
}
```

### Filtering

```
GET /api/tasks?status=pending&priority_gte=5&sort=-created_at
```

---

## Database Guidelines

### Schema Changes

1. Create migration file in `migrations/`
2. Name format: `NNN_description.sql`
3. Include both UP and DOWN migrations
4. Test migration on copy of production data

```sql
-- migrations/015_add_story_points.sql

-- UP
ALTER TABLE task_queue ADD COLUMN story_points INTEGER;

-- DOWN
ALTER TABLE task_queue DROP COLUMN story_points;
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Tables | snake_case, plural | `task_queue`, `users` |
| Columns | snake_case | `created_at`, `task_type` |
| Indexes | `idx_{table}_{column}` | `idx_tasks_status` |
| Foreign keys | `fk_{table}_{ref}` | `fk_tasks_project` |

### Query Guidelines

1. Always use parameterized queries (prevent SQL injection)
2. Use transactions for multi-statement operations
3. Add indexes for frequently queried columns
4. Limit result sets to prevent memory issues

```python
# Good - parameterized
conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))

# Bad - SQL injection risk
conn.execute(f"SELECT * FROM tasks WHERE id = {task_id}")
```

---

## Testing Requirements

### Test Coverage

- **Minimum**: 70% code coverage
- **Critical paths**: 100% coverage (auth, payments, data mutations)

### Test Types

1. **Unit tests**: Individual functions/methods
2. **Integration tests**: API endpoints
3. **Smoke tests**: Critical user flows

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=app tests/

# Run specific test file
python -m pytest tests/test_api.py
```

### Test Naming

```python
def test_create_task_with_valid_data_returns_201():
    ...

def test_create_task_without_type_returns_400():
    ...
```

---

## Security Guidelines

### Authentication

1. All API endpoints require authentication (except `/health`, `/login`)
2. Use session-based auth with secure cookies
3. Implement session timeout (default: 30 minutes)
4. Rate limit login attempts

### Data Protection

1. **Never log sensitive data** (passwords, tokens, keys)
2. **Sanitize all user input** before database operations
3. **Encrypt sensitive data** at rest (use vault for secrets)
4. **Use HTTPS** in production

### Security Headers

**MANDATORY**: All responses must include security headers to protect against common web vulnerabilities.

#### Headers Applied Automatically

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer info |
| `Content-Security-Policy` | (see below) | Control resource loading |
| `Permissions-Policy` | Restrictive | Disable unused browser features |
| `Strict-Transport-Security` | `max-age=31536000` | Enforce HTTPS (when secure) |

#### Content Security Policy (CSP)

Default CSP allows:
- Scripts: `'self'`, Socket.IO CDN, inline (for compatibility)
- Styles: `'self'`, Google Fonts, inline
- Fonts: `'self'`, Google Fonts
- Images: `'self'`, data:, blob:
- Connections: `'self'`, WebSocket (wss:, ws:)
- Frames: `'self'` only

#### Configuration

```python
from security_headers import SecurityHeaders, SecurityLevel

# Initialize with Flask app (done automatically)
security = SecurityHeaders(app)

# Add custom CSP source
security.add_csp_source('script-src', 'https://cdn.example.com')

# Update header
security.update_header('X-Frame-Options', 'DENY')

# Exempt paths from caching headers
security.add_cache_exempt_path('/static/')
```

#### Environment Variables

```bash
SECURITY_HEADERS_ENABLED=true    # Enable/disable all headers
SECURITY_CSP_ENABLED=true        # Enable/disable CSP
SECURITY_HSTS_ENABLED=true       # Enable/disable HSTS
SECURITY_CSP_REPORT_ONLY=false   # CSP in report-only mode
SECURITY_CSP_REPORT_URI=/api/csp-report  # CSP violation reports
```

#### Security Levels

Use pre-configured security levels:
- **strict**: No unsafe-inline/eval, X-Frame-Options: DENY
- **moderate**: Default, balanced security and compatibility
- **relaxed**: More permissive for development

#### API Endpoints

- `GET /api/security/headers` - View current configuration
- `GET /api/security/headers/test` - Test headers applied to response

### XSS Prevention (Cross-Site Scripting)

**MANDATORY**: All user input MUST be sanitized before rendering in HTML or storing in the database.

#### Backend Sanitization (Python/Flask)

```python
from utils import sanitize_string, sanitize_dict, sanitize_html

# Option 1: Use get_sanitized_json() instead of request.get_json()
data = get_sanitized_json()

# Option 2: Manually sanitize specific fields
data = request.get_json()
data['name'] = sanitize_string(data.get('name', ''), max_length=255)
data['description'] = sanitize_string(data.get('description', ''), max_length=5000)

# Option 3: Sanitize entire dict
data = sanitize_request_data(data, fields=['name', 'description'])
```

#### Frontend Sanitization (JavaScript)

```javascript
// Always use the Sanitize utilities (loaded from sanitize.js)

// Escaping for HTML content
const safeHtml = Sanitize.escapeHtml(userInput);

// Setting text content (inherently safe)
element.textContent = userInput;

// Building HTML strings
const html = Sanitize.html`<span class="content">${userInput}</span>`;

// Setting attributes safely
Sanitize.safeSetAttribute(element, 'title', userInput);

// Validating URLs
const safeUrl = Sanitize.sanitizeUrl(userProvidedUrl);
```

#### What MUST Be Sanitized

| Data Type | Backend Function | Frontend Function |
|-----------|-----------------|-------------------|
| Text content | `sanitize_string()` | `escapeHtml()` or `textContent` |
| HTML attributes | `sanitize_html()` | `escapeAttribute()` |
| URLs | `sanitize_url()` | `sanitizeUrl()` |
| JSON data | `sanitize_dict()` | N/A (escape on render) |

#### Forbidden Patterns

```javascript
// NEVER do this:
element.innerHTML = userInput;  // XSS vulnerability!
element.setAttribute('onclick', userInput);  // XSS vulnerability!
element.href = 'javascript:' + userInput;  // XSS vulnerability!

// ALWAYS do this instead:
element.textContent = userInput;  // Safe
Sanitize.safeSetHtml(element, userInput);  // Escapes then sets
Sanitize.safeSetAttribute(element, 'href', sanitizeUrl(url));  // Validates URL
```

#### Compliance Checklist

Before deploying any code that handles user input:

- [ ] All `innerHTML` assignments use escaped content
- [ ] All URL handling uses `sanitizeUrl()`
- [ ] All API endpoints sanitize input with `sanitize_request_data()` or `get_sanitized_json()`
- [ ] No direct string concatenation for SQL (use parameterized queries)
- [ ] Event handler attributes never contain user data
- [ ] Template literals escape interpolated user data

### CSRF Protection (Cross-Site Request Forgery)

**MANDATORY**: All state-changing operations (POST, PUT, DELETE, PATCH) MUST include a valid CSRF token.

#### How CSRF Protection Works

1. Server generates a unique token per session stored in `session['csrf_token']`
2. Token is embedded in pages via `<meta name="csrf-token">` tag
3. Frontend includes token in `X-CSRF-Token` header for all modifying requests
4. Server validates token before processing any state-changing request

#### Backend Implementation

```python
# CSRF protection is automatically applied via before_request handler
# All routes with @require_auth are protected unless explicitly exempted

# To exempt a specific endpoint (e.g., webhooks):
from csrf_protection import CSRF_EXEMPT_ENDPOINTS
CSRF_EXEMPT_ENDPOINTS.add('/api/webhooks/my-webhook')

# To rotate token after sensitive operation (password change, etc.):
from csrf_protection import rotate_csrf_token
rotate_csrf_token()

# Get CSRF token for custom templates:
from csrf_protection import generate_csrf_token
token = generate_csrf_token()
```

#### Frontend Implementation

```javascript
// CSRF protection is automatic when using the api() function

// For custom fetch requests, include the token:
const csrfToken = CSRF.getToken();
fetch('/api/resource', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
    },
    body: JSON.stringify(data)
});

// For forms, add hidden input:
CSRF.addToForm(formElement);

// Or use the HTML helper:
const inputHtml = CSRF.htmlField();
```

#### Exempt Endpoints

The following endpoints are exempt from CSRF validation:
- `/login` - Pre-authentication endpoint
- `/api/errors` - Error logging from nodes (uses API key auth)
- `/api/nodes` - Node registration (uses API key auth)
- `/health` - Health check endpoints
- `/api/webhooks/*` - Incoming webhook handlers

#### CSRF Error Handling

When CSRF validation fails:
1. Server returns `403` with `code: 'CSRF_INVALID'`
2. Frontend `api()` function automatically refreshes token
3. User is shown a "Please try again" notification

#### Compliance Checklist

Before deploying any new forms or API endpoints:
- [ ] State-changing endpoint uses `@require_auth` (CSRF auto-applied)
- [ ] Custom forms include CSRF hidden input or header
- [ ] Webhook endpoints are added to `CSRF_EXEMPT_ENDPOINTS`
- [ ] API key-authenticated endpoints handle their own security

### Log Correlation IDs

**MANDATORY**: All requests must have a correlation ID for distributed tracing and debugging.

#### How Correlation IDs Work

1. Each request gets a unique ID (format: `timestamp-shortuuid`, e.g., `1706745600-a1b2c3d4`)
2. ID is stored in Flask's `g` object and context variables
3. All log messages automatically include the correlation ID
4. Response headers include `X-Correlation-ID` for client-side tracking
5. Error responses include `correlation_id` field for support references

#### Backend Usage

```python
from correlation_id import (
    get_correlation_id, correlation_context, propagate_correlation_id
)

# Get current request's correlation ID
cid = get_correlation_id()

# Include in error messages
logger.error(f"Failed to process: {error}")  # ID added automatically

# For background tasks
with correlation_context("task-123"):
    do_background_work()
    logger.info("Task completed")  # Logs with [task-123]

# Propagate to outgoing requests
headers = propagate_correlation_id({'Authorization': 'Bearer token'})
requests.get('http://other-service/api', headers=headers)
```

#### Frontend Usage

```javascript
// Get current correlation ID
const id = Correlation.getId();

// Format error with correlation ID
const message = Correlation.formatError(error);

// Get error context for support tickets
const context = Correlation.getErrorContext(error);

// Copy correlation ID to clipboard
await Correlation.copyToClipboard();
```

#### Log Format

All logs now include correlation ID in brackets:
```
2025-01-31 10:30:45 [1706745600-a1b2c3d4] app - INFO - Request completed: GET /api/projects -> 200 (45.23ms)
```

#### Response Headers

All responses include:
```
X-Correlation-ID: 1706745600-a1b2c3d4
```

#### Error Responses

Error JSON includes correlation ID for support:
```json
{
    "error": "Resource not found",
    "status_code": 404,
    "correlation_id": "1706745600-a1b2c3d4"
}
```

#### Compliance Checklist

- [ ] All log messages use the standard logger (correlation ID auto-added)
- [ ] Background tasks use `correlation_context()` for tracing
- [ ] Outgoing requests use `propagate_correlation_id()` for distributed tracing
- [ ] Error notifications display correlation ID to users

### Distributed Tracing (OpenTelemetry)

**RECOMMENDED**: Use OpenTelemetry for distributed tracing across services.

#### Overview

OpenTelemetry provides standardized distributed tracing with:
- Automatic request span creation
- Context propagation across services
- Multiple exporter support (Jaeger, Zipkin, OTLP)
- Integration with correlation IDs
- Performance monitoring

#### Configuration

```bash
# Environment variables
OTEL_ENABLED=true                    # Enable/disable tracing
OTEL_SERVICE_NAME=architect          # Service name in traces
OTEL_EXPORTER=console                # Exporter: console, otlp, jaeger, zipkin
OTEL_ENDPOINT=http://localhost:4317  # OTLP collector endpoint
OTEL_SAMPLE_RATE=1.0                 # Sampling rate (0.0 to 1.0)
```

#### Backend Usage

```python
from tracing import trace_span, trace_function, add_span_event

# Create custom spans
with trace_span("process_data", {"item_count": 100}) as span:
    span.set_attribute("status", "processing")
    process_data()
    add_span_event("checkpoint", {"processed": 50})

# Use decorator for function tracing
@trace_function(name="fetch_user", record_args=True)
def fetch_user(user_id):
    return db.get_user(user_id)

# Trace database operations
with trace_database("select", "users") as span:
    cursor.execute("SELECT * FROM users")
```

#### Context Propagation

```python
from tracing import get_trace_context, trace_http_client

# Get trace context for outgoing requests
context = get_trace_context()

# Prepare headers for HTTP client
headers = trace_http_client("GET", "http://api.example.com/data")
response = requests.get(url, headers=headers)
```

#### API Endpoints

- `GET /api/tracing/config` - View tracing configuration
- `GET /api/tracing/context` - Get current trace context
- `GET /api/tracing/test` - Test tracing functionality

#### Exporters

| Exporter | Use Case | Endpoint Env Var |
|----------|----------|------------------|
| `console` | Development/debugging | N/A |
| `otlp` | OpenTelemetry Collector | `OTEL_ENDPOINT` |
| `jaeger` | Jaeger backend | `JAEGER_HOST`, `JAEGER_PORT` |
| `zipkin` | Zipkin backend | `ZIPKIN_ENDPOINT` |

#### Fallback Mode

When OpenTelemetry SDK is not installed, the system uses a lightweight fallback:
- Basic span tracking with timing
- Attributes and events support
- No external export (logs only)

#### Installation

```bash
# Install OpenTelemetry (optional, for production)
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-otlp  # For OTLP
pip install opentelemetry-exporter-jaeger  # For Jaeger
```

### API Documentation (OpenAPI/Swagger)

The Architect Dashboard provides comprehensive API documentation using OpenAPI 3.0 specification.

#### Documentation Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/docs` | Swagger UI - Interactive API explorer |
| `/api/docs/redoc` | ReDoc - Alternative documentation view |
| `/api/docs/openapi.json` | Raw OpenAPI 3.0 specification |
| `/api/docs/openapi.yaml` | YAML format specification |

#### Swagger UI Features

- **Interactive Testing**: Try API endpoints directly from the browser
- **Authentication**: Test with session cookies or API keys
- **Request/Response Examples**: See expected formats
- **Schema Validation**: View required fields and data types

#### Using the API Documentation

1. **Access Swagger UI**:
   ```
   https://your-dashboard:8080/api/docs
   ```

2. **Authenticate**: Click "Authorize" and enter credentials

3. **Explore Endpoints**: Browse by category (Projects, Features, Bugs, etc.)

4. **Try It Out**: Click "Try it out" to test any endpoint

#### API Categories

| Category | Description |
|----------|-------------|
| Projects | Create and manage projects |
| Milestones | Track project milestones |
| Features | Feature specifications and tracking |
| Bugs | Bug reports and resolution |
| Tasks | Background task queue management |
| tmux | Terminal session management |
| Nodes | Cluster node monitoring |
| Errors | Aggregated error tracking |
| Workers | Worker registration and status |

#### Client Code Generation

The OpenAPI spec can be used to generate client libraries:

```bash
# Generate Python client
openapi-generator generate -i /api/docs/openapi.json -g python -o ./client

# Generate JavaScript client
openapi-generator generate -i /api/docs/openapi.json -g javascript -o ./client

# Generate TypeScript client
openapi-generator generate -i /api/docs/openapi.json -g typescript-fetch -o ./client
```

#### Programmatic Access

```python
import requests
import json

# Fetch OpenAPI spec
response = requests.get('http://localhost:8080/api/docs/openapi.json')
spec = response.json()

# List all endpoints
for path, methods in spec['paths'].items():
    for method in methods:
        print(f"{method.upper()} {path}")
```

```javascript
// JavaScript
fetch('/api/docs/openapi.json')
    .then(r => r.json())
    .then(spec => {
        console.log('API Title:', spec.info.title);
        console.log('Endpoints:', Object.keys(spec.paths).length);
    });
```

### Database Connection Pooling

All services should use connection pooling for database operations to improve performance and resource management.

#### Overview

The connection pooling system provides:
- Thread-safe connection management
- Automatic connection recycling
- Health checking and validation
- Background maintenance
- Comprehensive metrics

#### Configuration

Default pool settings in `db.py`:

```python
POOL_CONFIG = {
    'min_connections': 2,        # Minimum connections to maintain
    'max_connections': 10,       # Maximum connections allowed
    'max_overflow': 5,           # Extra connections for burst traffic
    'pool_timeout': 30.0,        # Seconds to wait for connection
    'recycle_time': 3600,        # Recycle connections after 1 hour
    'health_check_interval': 60, # Seconds between health checks
    'enabled': True,             # Enable/disable pooling
}
```

#### Usage - Context Manager (Preferred)

```python
from db import get_connection

# Simple usage - automatic pooling
with get_connection() as conn:
    result = conn.execute("SELECT * FROM projects").fetchall()

# Specify database type
with get_connection(db_type='delegator') as conn:
    conn.execute("INSERT INTO tasks ...")
```

#### Usage - Service Connection Pool

For services with custom database paths:

```python
from db import ServiceConnectionPool

class MyService:
    def __init__(self, db_path: str):
        self._pool = ServiceConnectionPool.get_or_create(
            db_path,
            min_connections=1,
            max_connections=5
        )

    def do_something(self):
        with self._pool.connection() as conn:
            conn.execute("SELECT * FROM table")

    def close(self):
        self._pool.close()
```

#### Usage - Drop-in Replacement

For migrating existing code:

```python
from db import create_pooled_connection, close_pooled_connection

# Instead of: conn = sqlite3.connect(db_path)
conn = create_pooled_connection(db_path)

try:
    conn.execute("SELECT 1")
finally:
    # Instead of: conn.close()
    close_pooled_connection(conn)
```

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/db/pool/stats` | GET | Get pool statistics |
| `/api/db/pool/metrics` | GET | Get comprehensive metrics |
| `/api/db/pool/summary` | GET | Get simple status summary |
| `/api/db/pool/health` | POST | Run health check |
| `/api/db/pool/config` | GET/PUT | Get or update config |
| `/api/db/pool/warmup` | POST | Pre-create connections |
| `/api/db/pool/reset` | POST | Reset all pools |
| `/api/db/pool/initialize` | POST | Full initialization |
| `/api/db/pool/health-checker` | GET/POST/DELETE | Manage health checker |

#### Initialization at Startup

```python
from db import initialize_pools

# In app.py or startup script
initialize_pools(
    warmup=True,          # Pre-create connections
    health_checker=True,  # Start background health checker
    db_types=['main', 'delegator']  # Specific databases
)
```

#### Monitoring

```python
from db import get_pool_metrics, get_pool_summary

# Get full metrics
metrics = get_pool_metrics()
print(f"Active: {metrics['summary']['total_active']}")
print(f"Available: {metrics['summary']['total_available']}")

# Simple summary
summary = get_pool_summary()
if summary['active_connections'] > 8:
    logger.warning("High connection usage")
```

#### Best Practices

1. **Use context managers** - Always use `with` statements for automatic cleanup
2. **Avoid long-held connections** - Release connections promptly
3. **Use ServiceConnectionPool** - For services with custom database files
4. **Enable health checker** - For production environments
5. **Monitor metrics** - Set up alerts for pool exhaustion
6. **Initialize at startup** - Use `initialize_pools()` for best performance

### Graceful Shutdown for Workers

All workers and services must implement graceful shutdown to ensure clean termination.

#### Overview

The graceful shutdown module provides:
- Signal handling (SIGTERM, SIGINT, SIGHUP)
- In-progress task completion before exit
- Configurable shutdown timeout
- Cleanup hooks for resource cleanup
- Dashboard notification on shutdown

#### Usage

```python
from graceful_shutdown import GracefulShutdown, ShutdownReason

# Create shutdown handler
shutdown = GracefulShutdown(
    worker_id="my-worker",
    shutdown_timeout=30,       # Max time for shutdown
    drain_timeout=60,          # Max time to wait for tasks
    on_shutdown=my_cleanup,    # Callback on shutdown
    notify_dashboard=True
)

# Use as context manager
with shutdown:
    while shutdown.should_run:
        task = get_next_task()
        if task:
            with shutdown.task_context(task.id):
                process_task(task)
```

#### Decorator Usage

```python
from graceful_shutdown import shutdown_handler

@shutdown_handler(timeout=30)
def main(shutdown):
    while shutdown.should_run:
        process_work()

if __name__ == '__main__':
    main()
```

#### Shutdown Phases

| Phase | Description |
|-------|-------------|
| `RUNNING` | Normal operation |
| `STOPPING` | Shutdown signal received |
| `DRAINING` | Waiting for in-progress tasks |
| `CLEANUP` | Running cleanup hooks |
| `TERMINATED` | Shutdown complete |

#### Task Tracking

Track in-progress tasks to ensure they complete before shutdown:

```python
# Context manager approach
with shutdown.task_context("task-123"):
    process_task()

# Manual approach
task_id = shutdown.start_task("task-123")
try:
    process_task()
finally:
    shutdown.finish_task(task_id)
```

#### Cleanup Hooks

Register cleanup hooks for resource cleanup:

```python
def cleanup_database():
    db.close()

def cleanup_connections():
    pool.shutdown()

shutdown.add_cleanup_hook(cleanup_database)
shutdown.add_cleanup_hook(cleanup_connections)
# Hooks run in LIFO order (last added, first run)
```

#### Coordinator for Multiple Workers

Use `ShutdownCoordinator` to manage shutdown of multiple workers:

```python
from graceful_shutdown import ShutdownCoordinator

coordinator = ShutdownCoordinator(shutdown_timeout=60)
coordinator.register_worker(worker1._shutdown)
coordinator.register_worker(worker2._shutdown)
coordinator.start()

# Later, to stop all workers
coordinator.stop()
```

#### Signals Handled

| Signal | Action |
|--------|--------|
| `SIGTERM` | Initiate graceful shutdown |
| `SIGINT` | Initiate graceful shutdown (Ctrl+C) |
| `SIGHUP` | Initiate graceful shutdown |

#### Best Practices

1. **Always track in-progress tasks** - Use `task_context()` or `start_task()/finish_task()`
2. **Set appropriate timeouts** - Balance between graceful completion and timely shutdown
3. **Register cleanup hooks** - Release resources (connections, files, locks)
4. **Notify dashboard** - Enable `notify_dashboard=True` for visibility
5. **Test shutdown paths** - Verify workers shut down cleanly under load

### Real-Time Collaboration Indicators

Multi-user editing awareness with typing indicators, presence tracking, and conflict detection.

#### Overview

The collaboration system provides:
- Real-time presence tracking (who's online)
- Typing indicators (who's editing what)
- Entity viewing awareness (who's looking at what)
- Edit conflict warnings
- Avatar-based user identification

#### Backend Components

**TypingIndicatorManager** (`typing_indicators.py`):
- Manages typing state across entities and fields
- Tracks viewer presence per entity
- Background cleanup of stale indicators

**WebSocket Events** (handled in `app.py`):
- `typing_start` - User starts typing
- `typing_stop` - User stops typing
- `view_entity` - User opens an entity for viewing/editing
- `leave_entity` - User closes an entity
- `presence_heartbeat` - Keep-alive for presence tracking
- `get_entity_activity` - Request current activity for an entity

#### Frontend Components

**CollaborationManager** (`dashboard.html`):
```javascript
// Track entity viewing
CollaborationManager.viewEntity('feature', featureId);

// Typing indicators on form fields
input.addEventListener('input', () => CollaborationManager.startTyping(fieldId));
input.addEventListener('blur', () => CollaborationManager.stopTyping(fieldId));

// Leave when closing
CollaborationManager.leaveCurrentEntity();
```

#### UI Elements

| Component | Description |
|-----------|-------------|
| Collaboration Bar | Shows viewers and typing users for current entity |
| Avatar Stack | Overlapping avatars with presence dots |
| Typing Indicator | Animated dots with user names |
| Online Users | Header indicator + dropdown panel |
| Conflict Warning | Alert when others are editing same entity |

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/collaboration/presence` | POST | Update user presence |
| `/api/collaboration/presence` | DELETE | Remove user presence |
| `/api/collaboration/presence` | GET | List online users |
| `/api/collaboration/presence/heartbeat` | POST | Send heartbeat |
| `/api/collaboration/entity/<type>/<id>` | GET | Get entity activity |

#### Configuration

Timeouts configured in `typing_indicators.py`:
```python
TYPING_TIMEOUT = 5      # Seconds until typing indicator expires
PRESENCE_TIMEOUT = 60   # Seconds until presence expires
```

#### Best Practices

1. **Call viewEntity on modal open** - Track when users open edit dialogs
2. **Call leaveCurrentEntity on modal close** - Clean up when users leave
3. **Add typing listeners to text inputs** - Show who's editing which fields
4. **Check for conflicts before saving** - Warn users of concurrent edits
5. **Maintain heartbeat** - Keep presence alive with periodic heartbeats

### File Handling

1. Validate file types and sizes
2. Store uploads outside web root
3. Generate random filenames
4. Scan for malware if accepting uploads

### Environment Variables

```bash
# Required for production
SECRET_KEY=<random-32-char-string>
ARCHITECT_USER=<admin-username>
ARCHITECT_PASSWORD=<strong-password>
```

**Never commit:**
- `.env` files
- API keys
- Passwords
- Private keys

---

## Error Handling

### Python Exceptions

```python
try:
    result = perform_operation()
except SpecificError as e:
    logger.warning(f"Expected error: {e}")
    return handle_gracefully()
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### API Error Responses

```python
def api_error(message, status_code=400, error_code=None):
    return jsonify({
        'error': message,
        'error_code': error_code
    }), status_code

# Usage
return api_error("Task not found", 404, "TASK_NOT_FOUND")
```

### Logging Levels

| Level | Use |
|-------|-----|
| DEBUG | Detailed diagnostic info |
| INFO | General operational events |
| WARNING | Unexpected but handled events |
| ERROR | Errors that need attention |
| CRITICAL | System failures |

---

## Automatic Error Trapping

**All applications MUST implement automatic error trapping** to ensure errors are captured and reported to the Architect Dashboard without manual intervention.

### Backend (Python/Flask) Automatic Trapping

#### 1. Global Exception Handler

Install at application startup to catch ALL unhandled exceptions:

```python
import sys
import traceback
import requests
from functools import wraps

DASHBOARD_URL = "http://dashboard:8080"
APP_NODE_ID = "myapp-prod-01"

def report_to_dashboard(error, source=None, context=None):
    """Send error to Architect Dashboard."""
    try:
        requests.post(
            f"{DASHBOARD_URL}/api/errors",
            json={
                "node_id": APP_NODE_ID,
                "error_type": "error",
                "message": str(error),
                "source": source or "unknown",
                "stack_trace": traceback.format_exc(),
                "context": context or {}
            },
            timeout=5
        )
    except Exception:
        pass  # Never let reporting crash the app

# Install global exception hook
_original_excepthook = sys.excepthook

def global_exception_handler(exc_type, exc_value, exc_tb):
    """Trap all unhandled exceptions."""
    source = traceback.extract_tb(exc_tb)[-1].filename if exc_tb else "unknown"
    report_to_dashboard(exc_value, source=source)
    _original_excepthook(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_handler
```

#### 2. Flask Error Handler Middleware

Trap errors at the Flask application level:

```python
from flask import Flask, request, g
import time

app = Flask(__name__)

@app.before_request
def before_request():
    """Track request context for error reporting."""
    g.request_start_time = time.time()
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

@app.errorhandler(Exception)
def handle_exception(error):
    """Catch all unhandled exceptions in routes."""
    context = {
        "request_path": request.path,
        "request_method": request.method,
        "request_id": getattr(g, 'request_id', None),
        "user_agent": request.headers.get('User-Agent'),
        "duration_ms": (time.time() - getattr(g, 'request_start_time', time.time())) * 1000
    }

    report_to_dashboard(error, source=request.endpoint, context=context)

    # Return appropriate error response
    if isinstance(error, HTTPException):
        return jsonify({"error": error.description}), error.code
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    """Log 404s for monitoring."""
    report_to_dashboard(error, source=request.path, context={"type": "not_found"})
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    """Always report 500 errors."""
    report_to_dashboard(error, source=request.endpoint, context={"severity": "critical"})
    return jsonify({"error": "Internal server error"}), 500
```

#### 3. Decorator for Function-Level Trapping

```python
def trap_errors(func):
    """Decorator to trap and report errors from any function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            report_to_dashboard(e, source=func.__name__, context={
                "args": str(args)[:200],
                "kwargs": str(kwargs)[:200]
            })
            raise
    return wrapper

# Usage
@trap_errors
def process_critical_task(task_id):
    # Any error here is automatically reported
    ...
```

#### 4. Database Error Trapping

```python
from contextlib import contextmanager

@contextmanager
def safe_db_connection():
    """Context manager with automatic error reporting."""
    conn = None
    try:
        conn = get_db_connection()
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        report_to_dashboard(e, source="database", context={
            "error_type": "database_error",
            "severity": "high"
        })
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
```

### Frontend (JavaScript) Automatic Trapping

#### 1. Global Error Handlers

Install at page load to catch ALL JavaScript errors:

```javascript
// Error trapping configuration
const ERROR_CONFIG = {
    dashboardUrl: '/api/errors',  // Use relative URL or full dashboard URL
    nodeId: 'webapp-frontend',
    maxErrorsPerMinute: 10,       // Rate limiting
    ignorePatterns: [             // Errors to skip
        /ResizeObserver loop/,
        /Script error\./
    ]
};

// Rate limiting
let errorCount = 0;
setInterval(() => { errorCount = 0; }, 60000);

// Core reporting function
async function reportError(error, context = {}) {
    // Rate limiting
    if (errorCount++ > ERROR_CONFIG.maxErrorsPerMinute) return;

    // Check ignore patterns
    const message = error?.message || String(error);
    if (ERROR_CONFIG.ignorePatterns.some(p => p.test(message))) return;

    try {
        await fetch(ERROR_CONFIG.dashboardUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: ERROR_CONFIG.nodeId,
                error_type: context.severity || 'error',
                message: message,
                source: context.source || error?.stack?.split('\n')[1] || 'unknown',
                stack_trace: error?.stack || new Error().stack,
                context: {
                    url: window.location.href,
                    userAgent: navigator.userAgent,
                    timestamp: new Date().toISOString(),
                    ...context
                }
            })
        });
    } catch (e) {
        console.error('Failed to report error:', e);
    }
}

// Trap synchronous errors
window.onerror = (message, source, lineno, colno, error) => {
    reportError(error || new Error(message), {
        source: `${source}:${lineno}:${colno}`,
        type: 'uncaught_error'
    });
    return false; // Let default handler run too
};

// Trap unhandled promise rejections
window.onunhandledrejection = (event) => {
    reportError(event.reason, {
        type: 'unhandled_rejection',
        severity: 'error'
    });
};

// Trap resource loading errors
window.addEventListener('error', (event) => {
    if (event.target !== window) {
        reportError(new Error(`Failed to load: ${event.target.src || event.target.href}`), {
            type: 'resource_error',
            severity: 'warning',
            element: event.target.tagName
        });
    }
}, true);
```

#### 2. Fetch/API Error Wrapper

Automatically trap all API call errors:

```javascript
// Wrap fetch for automatic error reporting
const originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    const startTime = performance.now();

    try {
        const response = await originalFetch(url, options);

        // Report server errors (5xx)
        if (response.status >= 500) {
            reportError(new Error(`API Error: ${response.status} ${response.statusText}`), {
                type: 'api_error',
                severity: 'error',
                url: url,
                method: options.method || 'GET',
                status: response.status,
                duration: performance.now() - startTime
            });
        }

        // Report client errors (4xx) as warnings
        if (response.status >= 400 && response.status < 500) {
            reportError(new Error(`API Warning: ${response.status}`), {
                type: 'api_warning',
                severity: 'warning',
                url: url,
                status: response.status
            });
        }

        return response;
    } catch (error) {
        // Network errors, timeouts, etc.
        reportError(error, {
            type: 'network_error',
            severity: 'error',
            url: url,
            method: options.method || 'GET',
            duration: performance.now() - startTime
        });
        throw error;
    }
};
```

#### 3. React Error Boundary

For React applications, wrap components:

```javascript
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        reportError(error, {
            type: 'react_error',
            severity: 'critical',
            componentStack: errorInfo.componentStack,
            component: this.props.name || 'Unknown'
        });
    }

    render() {
        if (this.state.hasError) {
            return this.props.fallback || <div>Something went wrong.</div>;
        }
        return this.props.children;
    }
}

// Usage
<ErrorBoundary name="TaskList" fallback={<ErrorFallback />}>
    <TaskList />
</ErrorBoundary>
```

#### 4. Vue.js Error Handler

```javascript
// In main.js or app initialization
app.config.errorHandler = (error, instance, info) => {
    reportError(error, {
        type: 'vue_error',
        severity: 'error',
        component: instance?.$options?.name,
        lifecycleHook: info
    });
};

app.config.warnHandler = (msg, instance, trace) => {
    reportError(new Error(msg), {
        type: 'vue_warning',
        severity: 'warning',
        component: instance?.$options?.name,
        trace: trace
    });
};
```

### Error Trapping Compliance Checklist

Before deploying any application:

#### Backend
- [ ] Global `sys.excepthook` installed
- [ ] Flask `@app.errorhandler(Exception)` configured
- [ ] Database operations wrapped with error trapping
- [ ] Background tasks/workers have error handlers
- [ ] Logging configured to capture errors

#### Frontend
- [ ] `window.onerror` handler installed
- [ ] `window.onunhandledrejection` handler installed
- [ ] Fetch/API wrapper with error reporting
- [ ] Error boundaries for component trees (React/Vue)
- [ ] Resource loading errors captured

#### Both
- [ ] Rate limiting prevents error floods
- [ ] Sensitive data stripped from reports
- [ ] Error reporting doesn't crash the app
- [ ] Unique node_id configured
- [ ] Dashboard URL configured correctly

---

## Bug Reporting Requirements

### Universal Mandate: ALL Applications

**EVERY application in the ecosystem MUST integrate with the Architect Dashboard bug reporting system.** This is a **mandatory, non-negotiable requirement** with zero exceptions.

#### Scope of Requirement

This mandate applies to:
- **Backend services** (Python, Node.js, Go, etc.)
- **Frontend applications** (React, Vue, vanilla JS, etc.)
- **Mobile applications** (iOS, Android, React Native, Flutter)
- **CLI tools and scripts**
- **Background workers and cron jobs**
- **Microservices and APIs**
- **Third-party integrations**
- **Development and staging environments**

#### Enforcement

| Check | Requirement |
|-------|-------------|
| **Code Review** | PR must include error reporting integration |
| **Pre-Deploy** | Deployment blocked if error reporting not verified |
| **Audit** | Monthly audit of all apps for compliance |
| **Incident Response** | Apps without reporting face immediate remediation |

#### Non-Compliance Consequences

1. **Development**: PR will not be approved without error reporting
2. **QA**: App will not pass QA without verified integration
3. **Production**: Non-compliant apps will be flagged for immediate fix
4. **Audit**: Repeat offenses escalated to engineering leadership

### Implementation Requirements

1. **Automatic Error Reporting**
   - All unhandled exceptions must be reported to the dashboard
   - Include stack trace, error type, and context
   - Report within 5 seconds of occurrence

2. **API Endpoint**
   ```
   POST /api/errors

   {
       "node_id": "app-name-instance",
       "error_type": "error|warning|critical",
       "message": "Human-readable error message",
       "source": "module_or_file.py",
       "stack_trace": "Full stack trace",
       "context": {
           "user_id": "optional",
           "request_path": "/api/endpoint",
           "additional": "metadata"
       }
   }
   ```

3. **Required Fields**
   | Field | Required | Description |
   |-------|----------|-------------|
   | `node_id` | Yes | Unique identifier for the app instance |
   | `error_type` | Yes | Severity level |
   | `message` | Yes | Error description |
   | `source` | Yes | File or module where error occurred |
   | `stack_trace` | No | Full stack trace (recommended) |
   | `context` | No | Additional metadata |

### Python Integration Example

```python
import requests
import traceback
import sys

DASHBOARD_URL = "http://dashboard:8080"
APP_NODE_ID = "myapp-prod-01"

def report_error(error, context=None):
    """Report error to Architect Dashboard."""
    try:
        requests.post(
            f"{DASHBOARD_URL}/api/errors",
            json={
                "node_id": APP_NODE_ID,
                "error_type": "error",
                "message": str(error),
                "source": traceback.extract_tb(sys.exc_info()[2])[-1].filename,
                "stack_trace": traceback.format_exc(),
                "context": context or {}
            },
            timeout=5
        )
    except Exception:
        pass  # Don't let reporting fail the app

# Usage with exception handler
def global_exception_handler(exc_type, exc_value, exc_tb):
    report_error(exc_value)
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_handler
```

### JavaScript Integration Example

```javascript
const DASHBOARD_URL = 'http://dashboard:8080';
const APP_NODE_ID = 'webapp-prod-01';

async function reportError(error, context = {}) {
    try {
        await fetch(`${DASHBOARD_URL}/api/errors`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: APP_NODE_ID,
                error_type: 'error',
                message: error.message,
                source: error.stack?.split('\n')[1] || 'unknown',
                stack_trace: error.stack,
                context
            })
        });
    } catch (e) {
        console.error('Failed to report error:', e);
    }
}

// Global error handler
window.onerror = (msg, source, line, col, error) => {
    reportError(error || new Error(msg), { source, line, col });
};

// Promise rejection handler
window.onunhandledrejection = (event) => {
    reportError(event.reason);
};
```

### Error Severity Levels

| Level | Use Case | Dashboard Action |
|-------|----------|------------------|
| `warning` | Non-critical issues, deprecations | Log only |
| `error` | Application errors, failed operations | Alert + Log |
| `critical` | System failures, data corruption | Immediate alert |

### Compliance Checklist

**DEPLOYMENT GATE**: Before deploying ANY application, verify:

#### Integration Requirements
- [ ] Error reporting endpoint configured (`/api/errors` on Architect Dashboard)
- [ ] Global exception handler installed (Python: `sys.excepthook`, JS: `window.onerror`)
- [ ] Unhandled promise rejections captured (JS: `window.onunhandledrejection`)
- [ ] Node ID is unique and descriptive (format: `appname-env-instance`)
- [ ] Stack traces included for all errors
- [ ] Timeout configured (max 5 seconds for reporting)
- [ ] Reporting failures don't crash the app

#### Testing Requirements
- [ ] Verify error reaches dashboard (throw test error, check dashboard)
- [ ] Confirm deduplication works (same error doesn't flood dashboard)
- [ ] Test from each environment (dev, QA, prod)

#### Documentation Requirements
- [ ] Node ID registered in app inventory
- [ ] Error reporting documented in app's README
- [ ] Team notified of app's dashboard integration

### Deployment Gate Enforcement

**CI/CD pipelines MUST include a bug reporting verification step:**

```yaml
# Example CI/CD step
- name: Verify Bug Reporting Integration
  run: |
    # Send test error to dashboard
    curl -X POST $DASHBOARD_URL/api/errors \
      -H "Content-Type: application/json" \
      -d '{"node_id":"'$APP_NODE_ID'","error_type":"test","message":"CI deployment verification","source":"ci-pipeline"}'

    # Verify it arrived (check for 200 response)
    if [ $? -ne 0 ]; then
      echo "ERROR: Bug reporting integration failed. Deployment blocked."
      exit 1
    fi
```

### Monitoring

The Architect Dashboard provides:
- Error aggregation and deduplication
- Trend analysis and alerting
- One-click bug creation from errors
- Cross-application error correlation

Access error reports at: `/api/errors` or via the dashboard UI.

---

## Logging Standards

### Universal Logging Requirements

All applications MUST implement structured logging that integrates with centralized log aggregation.

### Log Format

Use JSON-structured logs for machine parseability:

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        return json.dumps(log_obj)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)
```

### Log Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| `DEBUG` | Detailed diagnostic info | Variable values, loop iterations |
| `INFO` | Normal operations | Request received, task completed |
| `WARNING` | Unexpected but handled | Retry attempt, deprecated usage |
| `ERROR` | Failures requiring attention | API error, database timeout |
| `CRITICAL` | System-level failures | Service crash, data corruption |

### Required Context Fields

All log entries SHOULD include:

| Field | Description | Example |
|-------|-------------|---------|
| `request_id` | Unique request identifier | `uuid4()` |
| `user_id` | Current user (if applicable) | `user_123` |
| `service` | Service/app name | `auth-service` |
| `environment` | Current environment | `prod`, `qa`, `dev` |
| `duration_ms` | Operation duration | `145` |

### Logging Don'ts

- **Never log sensitive data**: passwords, tokens, API keys, PII
- **Never log full request bodies**: may contain secrets
- **Never use print()**: use proper logging framework
- **Never log at DEBUG in production**: performance impact

### JavaScript Logging

```javascript
const logger = {
    _log(level, message, context = {}) {
        const entry = {
            timestamp: new Date().toISOString(),
            level,
            message,
            service: process.env.SERVICE_NAME || 'webapp',
            ...context
        };
        console.log(JSON.stringify(entry));
    },

    debug: (msg, ctx) => logger._log('DEBUG', msg, ctx),
    info: (msg, ctx) => logger._log('INFO', msg, ctx),
    warn: (msg, ctx) => logger._log('WARNING', msg, ctx),
    error: (msg, ctx) => logger._log('ERROR', msg, ctx)
};

// Usage
logger.info('User logged in', { user_id: '123', ip: '10.0.0.1' });
```

---

## Performance Guidelines

### Response Time Standards

| Endpoint Type | Target | Maximum |
|---------------|--------|---------|
| Health check | < 50ms | 100ms |
| Simple read | < 100ms | 500ms |
| Complex query | < 500ms | 2s |
| Write operation | < 200ms | 1s |
| Batch operation | < 5s | 30s |
| Background task | N/A | 10min |

### Database Performance

#### Query Optimization

1. **Use indexes** for frequently queried columns
2. **Limit result sets** - never `SELECT *` without LIMIT
3. **Avoid N+1 queries** - use JOINs or batch fetching
4. **Profile slow queries** - log queries > 100ms

```python
# Bad - N+1 query pattern
for task in tasks:
    subtasks = db.query("SELECT * FROM subtasks WHERE task_id = ?", task.id)

# Good - batch fetch
task_ids = [t.id for t in tasks]
subtasks = db.query("SELECT * FROM subtasks WHERE task_id IN (?)", task_ids)
```

#### Connection Management

```python
# Use connection pooling
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30
)
```

### Caching Strategy

| Cache Level | TTL | Use Case |
|-------------|-----|----------|
| In-memory | 1-5 min | Hot data, computed values |
| Redis | 5-60 min | Session data, API responses |
| CDN | 1-24 hr | Static assets, public content |

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Simple in-memory cache with TTL
cache = {}

def cached(ttl_seconds=300):
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            if key in cache:
                value, expiry = cache[key]
                if datetime.now() < expiry:
                    return value
            result = func(*args, **kwargs)
            cache[key] = (result, datetime.now() + timedelta(seconds=ttl_seconds))
            return result
        return wrapper
    return decorator

@cached(ttl_seconds=60)
def get_project_stats(project_id):
    # Expensive operation
    return calculate_stats(project_id)
```

### API Rate Limiting

All APIs MUST implement rate limiting:

| Client Type | Requests/min | Burst |
|-------------|--------------|-------|
| Authenticated user | 100 | 20 |
| API key | 1000 | 100 |
| Public/anonymous | 20 | 5 |
| Internal service | 10000 | 500 |

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

@app.route("/api/resource")
@limiter.limit("20 per minute")
def resource():
    return jsonify(data)
```

### Resource Limits

| Resource | Development | Production |
|----------|-------------|------------|
| Max request body | 10MB | 5MB |
| Max file upload | 50MB | 25MB |
| Request timeout | 60s | 30s |
| Max concurrent connections | 100 | 1000 |
| Memory per process | 512MB | 1GB |

### Performance Monitoring

All applications MUST report performance metrics:

```python
import time
from functools import wraps

def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = (time.perf_counter() - start) * 1000
            if duration > 100:  # Log slow operations
                logger.warning(f"Slow operation: {func.__name__}", {
                    "duration_ms": duration,
                    "threshold_ms": 100
                })
    return wrapper
```

---

## Documentation

### Code Documentation

1. **Docstrings**: All public functions and classes
2. **Comments**: Complex logic only (code should be self-documenting)
3. **Type hints**: All function signatures

```python
def calculate_velocity(
    tasks: List[Dict],
    period_days: int = 14
) -> Dict[str, float]:
    """Calculate team velocity from completed tasks.

    Args:
        tasks: List of completed task dictionaries
        period_days: Number of days to calculate velocity over

    Returns:
        Dictionary with velocity metrics:
        - story_points_per_day
        - tasks_per_day
        - average_completion_time
    """
    ...
```

### API Documentation

Document all endpoints with:
- HTTP method and path
- Required/optional parameters
- Request body format
- Response format
- Error codes
- Example requests

### README Updates

Update README.md when:
- Adding new features
- Changing configuration
- Modifying deployment process
- Adding dependencies

---

## Deployment

### Environment Flow

All code changes must follow this promotion path:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Feature │───▶│   Dev   │───▶│   QA    │───▶│  Prod   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
   Local        Integration     Testing       Production
```

### Environment Definitions

| Environment | Purpose | Branch | URL Pattern |
|-------------|---------|--------|-------------|
| **Feature** | Local development | `feature/*` | `localhost:8080` |
| **Dev** | Integration testing | `dev` | `dev.architect.local:8080` |
| **QA** | Quality assurance | `qa` | `qa.architect.local:8080` |
| **Prod** | Production | `main` | `architect.local:8080` |

### Promotion Process

#### 1. Feature → Dev

```bash
# Complete feature development
git checkout feature/my-feature-0131

# Ensure tests pass
python -m pytest tests/

# Create PR to dev branch
gh pr create --base dev --title "Feature: Description"

# After PR approval, merge
gh pr merge --squash
```

**Requirements:**
- [ ] All unit tests pass
- [ ] Code review approved
- [ ] No merge conflicts

#### 2. Dev → QA

```bash
# Checkout dev branch
git checkout dev
git pull origin dev

# Create PR to qa branch
gh pr create --base qa --title "Release: Dev to QA $(date +%Y-%m-%d)"

# After approval, merge
gh pr merge --merge
```

**Requirements:**
- [ ] All integration tests pass
- [ ] Dev environment stable for 24 hours
- [ ] No critical bugs open
- [ ] Database migrations tested

#### 3. QA → Prod

```bash
# Checkout qa branch
git checkout qa
git pull origin qa

# Create PR to main (prod)
gh pr create --base main --title "Release: v$(date +%Y.%m.%d)"

# After approval, merge
gh pr merge --merge

# Tag the release
git checkout main
git pull origin main
git tag -a "v$(date +%Y.%m.%d)" -m "Production release"
git push origin --tags
```

**Requirements:**
- [ ] Full QA sign-off
- [ ] QA environment stable for 48 hours
- [ ] All smoke tests pass
- [ ] Rollback plan documented
- [ ] Stakeholder approval

### Environment Configuration

Each environment uses a separate configuration:

```bash
# Feature (local development)
export FLASK_ENV=development
export DATABASE_PATH=data/architect_dev.db
export LOG_LEVEL=DEBUG

# Dev
export FLASK_ENV=development
export DATABASE_PATH=data/architect_dev.db
export LOG_LEVEL=DEBUG
export DASHBOARD_URL=http://dev.architect.local:8080

# QA
export FLASK_ENV=testing
export DATABASE_PATH=data/architect_qa.db
export LOG_LEVEL=INFO
export DASHBOARD_URL=http://qa.architect.local:8080

# Prod
export FLASK_ENV=production
export DATABASE_PATH=data/architect.db
export LOG_LEVEL=WARNING
export DASHBOARD_URL=https://architect.local:8080
```

### Branch Protection Rules

| Branch | Direct Push | PR Required | Approvals | Status Checks |
|--------|-------------|-------------|-----------|---------------|
| `feature/*` | ✅ | No | 0 | None |
| `dev` | ❌ | Yes | 1 | Unit tests |
| `qa` | ❌ | Yes | 1 | Integration tests |
| `main` | ❌ | Yes | 2 | All tests + QA sign-off |

### Hotfix Process

For critical production issues:

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix-0131

# Make fix and test
# ...

# Create PR directly to main
gh pr create --base main --title "Hotfix: Critical issue"

# After emergency approval, merge
gh pr merge --squash

# Backport to qa and dev
git checkout qa && git merge main
git checkout dev && git merge qa
```

**Hotfix Requirements:**
- [ ] Issue is production-critical
- [ ] Fix is minimal and focused
- [ ] Emergency approval obtained
- [ ] Backported to all environments

### Pre-Deployment Checklist

- [ ] All tests pass
- [ ] No linter warnings
- [ ] Database migrations ready
- [ ] Environment variables configured
- [ ] Backup current production data

### Deployment Steps

```bash
# 1. Pull latest code
git pull origin main

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python migrate.py

# 4. Restart service
./deploy.sh restart
```

### Rollback Procedure

#### Automated Rollback on Health Check Failure

The system provides **automated rollback** when health checks fail after deployment.

**How it works:**
1. Before deployment, a snapshot is created (git commit + database backup)
2. After deployment, health monitoring starts automatically
3. If health checks fail consecutively (default: 3 times), automatic rollback triggers
4. System restores to the pre-deployment snapshot

**Using the Automated Rollback System:**

```bash
# 1. Create snapshot BEFORE deployment
python3 rollback_manager.py snapshot -m "Pre-deployment: Adding feature X"
# Returns: snapshot_id (e.g., 20260131_143052)

# 2. Deploy your changes
./deploy.sh restart

# 3. Start health monitoring (auto-rollback if failures detected)
python3 rollback_manager.py monitor 20260131_143052 -d 300
# Monitors for 5 minutes, rolls back if 3 consecutive failures
```

**API Endpoints for Rollback:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rollback/snapshots` | GET | List available snapshots |
| `/api/rollback/snapshots` | POST | Create new snapshot |
| `/api/rollback/execute` | POST | Execute manual rollback |
| `/api/rollback/monitor/start` | POST | Start health monitoring |
| `/api/rollback/monitor/stop` | POST | Stop health monitoring |
| `/api/rollback/monitor/status` | GET | Get monitoring status |
| `/api/rollback/history` | GET | Get rollback history |

**Example: Create Snapshot via API:**
```bash
curl -X POST http://localhost:8080/api/rollback/snapshots \
  -H "Content-Type: application/json" \
  -d '{"description": "Before feature deployment"}'
```

**Example: Start Monitoring via API:**
```bash
curl -X POST http://localhost:8080/api/rollback/monitor/start \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "20260131_143052",
    "duration": 300,
    "failure_threshold": 3
  }'
```

#### Manual Rollback

```bash
# Option 1: Using rollback_manager CLI
python3 rollback_manager.py list  # Show available snapshots
python3 rollback_manager.py rollback 20260131_143052

# Option 2: Using API
curl -X POST http://localhost:8080/api/rollback/execute \
  -H "Content-Type: application/json" \
  -d '{"snapshot_id": "20260131_143052"}'

# Option 3: Manual git rollback (last resort)
git log --oneline -10
git checkout <commit-hash>
./deploy.sh restart
```

#### Rollback Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `HEALTH_CHECK_INTERVAL` | 10s | Time between health checks |
| `CONSECUTIVE_FAILURES_THRESHOLD` | 3 | Failures before auto-rollback |
| `POST_DEPLOY_MONITORING_DURATION` | 300s | Default monitoring duration |
| `ROLLBACK_COOLDOWN` | 600s | Minimum time between rollbacks |

#### Rollback Checklist

Before deploying critical changes:
- [ ] Create pre-deployment snapshot
- [ ] Verify snapshot created successfully
- [ ] Start health monitoring after deployment
- [ ] Monitor rollback status during deployment window
- [ ] Verify service health manually

### Health Monitoring

**Health Endpoint:** `/health`

The health endpoint returns:
```json
{
  "status": "healthy|degraded|unhealthy",
  "database": "connected|slow|critical",
  "db_response_ms": 45,
  "cpu": 15.2,
  "memory": 62.5,
  "tmux_sessions": 3
}
```

**Automated Monitoring Features:**
- Continuous health checks at configurable intervals
- Automatic service restart on failures
- Automatic rollback when restart threshold exceeded
- Error ticket creation for investigation
- State persistence across restarts

**Monitoring Best Practices:**
- Set up alerts for degraded/unhealthy status
- Configure appropriate thresholds for your environment
- Review rollback history regularly
- Test rollback procedure before critical deployments

---

## Incident Response

---

## System Integration Overview

How the main components work together for autonomous development and tracking:

1. **AI Agents in tmux (Claude/Codex/Ollama)**
   - Work is routed into tmux sessions via the assigner or direct send.
   - Sessions are monitored for idle/busy state and task completion.

2. **Assigner + Session Coordination**
   - `scripts/session_assigner.py`: SOP-compliant assignment with environment and scope locks.
   - `workers/assigner_worker.py`: Generic queue that auto-hands off to idle tmux AI sessions.
   - `scripts/session_terminal.py`: Interactive CLI for queuing tasks (os: prefix).

3. **Comet/Browser Research**
   - Research tasks are handled via Perplexity/Comet flows and recorded back to Sheets.
   - Orchestrator can combine research + implementation for end-to-end tasks.

4. **Google Sheets (Two-way Sync)**
   - `workers/sheets_sync.py` keeps DevTasks/Tasks/Bugs/etc. in sync with the dashboard.
   - tmux sessions can pull tasks from DevTasks and update status/results.

5. **Architect Dashboard**
   - Central view of sessions, tasks, bugs, and system status.
   - API endpoints expose assigner state and tmux session health.

If unsure, route work through the SOP-compliant session assigner or the generic assigner worker.

### Severity Levels

| Severity | Definition | Response Time | Examples |
|----------|------------|---------------|----------|
| **SEV-1** | Complete outage, data loss risk | 15 min | Production down, security breach |
| **SEV-2** | Major functionality impaired | 1 hour | Payment failures, auth broken |
| **SEV-3** | Minor functionality impaired | 4 hours | Feature broken, performance degraded |
| **SEV-4** | Cosmetic or low-impact | 24 hours | UI glitch, minor bug |

### Incident Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Detect    │───▶│   Triage    │───▶│   Resolve   │───▶│   Review    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
  Monitoring        Assess severity    Fix & deploy      Post-mortem
  Alerts            Assign owner       Verify fix        Document
  User reports      Communicate        Monitor           Improve
```

### On-Call Responsibilities

1. **Monitor alerts** - Check Architect Dashboard for errors
2. **Acknowledge incidents** - Respond within SLA
3. **Triage severity** - Classify using severity matrix
4. **Communicate status** - Update stakeholders
5. **Resolve or escalate** - Fix or hand off appropriately
6. **Document resolution** - Create incident report

### Incident Communication Template

```markdown
## Incident: [Brief Description]

**Severity**: SEV-[1-4]
**Status**: Investigating | Identified | Monitoring | Resolved
**Started**: YYYY-MM-DD HH:MM UTC
**Resolved**: YYYY-MM-DD HH:MM UTC (if applicable)

### Impact
[What users/systems are affected]

### Current Status
[What we know, what we're doing]

### Updates
- HH:MM - [Update message]
- HH:MM - [Update message]
```

### Post-Incident Review

Required for all SEV-1 and SEV-2 incidents within 48 hours:

#### Template

```markdown
## Post-Incident Review: [Incident Title]

**Date**: YYYY-MM-DD
**Duration**: X hours Y minutes
**Severity**: SEV-X
**Author**: [Name]

### Summary
[1-2 sentence summary of what happened]

### Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | [Event description] |

### Root Cause
[What caused the incident]

### Impact
- Users affected: [number]
- Duration: [time]
- Revenue impact: [if applicable]

### What Went Well
- [Item 1]
- [Item 2]

### What Went Wrong
- [Item 1]
- [Item 2]

### Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| [Action 1] | [Name] | YYYY-MM-DD |

### Lessons Learned
[Key takeaways to prevent recurrence]
```

### Escalation Path

| Level | Contact | When to Escalate |
|-------|---------|------------------|
| L1 | On-call engineer | First responder |
| L2 | Team lead | > 30 min unresolved or SEV-1 |
| L3 | Engineering manager | > 1 hour or SEV-1 confirmed |
| L4 | Director/VP | Major outage, data breach |

### Runbooks

Maintain runbooks for common incidents:

- **Service restart**: How to restart each service
- **Database recovery**: Backup restore procedures
- **Cache invalidation**: How to clear caches
- **Rollback**: Version rollback procedures
- **Scale up**: How to add capacity

Store runbooks in `/docs/runbooks/` directory.

---

## Quick Reference

### Common Commands

```bash
# Start development server
./deploy.sh

# Run tests
python -m pytest tests/

# Check code style
flake8 app.py

# View logs
tail -f /tmp/architect_dashboard.log

# Database shell
sqlite3 data/architect.db
```

### Important Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `deploy.sh` | Deployment script |
| `CLAUDE.md` | AI assistant instructions |
| `SOP.md` | This document |
| `requirements.txt` | Python dependencies |

### Contacts

- **Repository**: Check git remote
- **Issues**: GitHub Issues
- **Documentation**: `/docs` directory

---

*Last updated: 2026-01-31 - Elevated to universal top-level standard for all projects*

---

## Google Sheets Integration

### Overview

All task completions in the Architect system are automatically synced to Google Sheets through a git-based workflow. This provides project managers and stakeholders with real-time visibility into task status without needing direct database access.

### Data Flow Architecture

```
Task Completion → Write CSV → Git Commit → Comet Pulls → Updates Sheet
     (App)         (File)       (Audit)      (Browser)      (Sheets API)
```

**Key Benefits:**
- **Audit Trail**: All updates tracked in git history
- **Offline Capable**: Updates queue when services unavailable
- **Manual Review**: CSV files can be reviewed/edited before sync
- **Browser-Based**: Comet session handles all sheet updates
- **Multi-Project**: Each project can have its own sheet

### Step-by-Step Workflow

#### 1. Task Completion Triggers Update

When a task, feature, or bug is marked as completed:

```python
# Automatically triggered in app.py
trigger_sheets_update(task_id, status='completed', task_type='feature')
```

#### 2. Write to CSV File

System writes task data to `data/sheets_pending/`:

```
data/sheets_pending/
├── ProjectName_20260201_120530_feature_42.csv
├── ProjectName_20260201_120645_bug_15.csv
└── AnotherProject_20260201_121000_task_123.csv
```

**CSV Format:**
```csv
task_id,task_type,title,description,status,priority,project_id,project_name,assigned_to,milestone_name,created_at,completed_at,updated_at
42,feature,Add login page,Implement user authentication,completed,high,1,MyProject,john,Sprint 1,2026-02-01T10:00:00,2026-02-01T12:05:30,2026-02-01T12:05:30
```

#### 3. Git Commit

System commits the CSV file:

```bash
git add data/sheets_pending/ProjectName_20260201_120530_feature_42.csv
git commit -m "sheets: Update feature 42

Automated Google Sheets sync"
```

**Benefits:**
- Full audit trail
- Revertible if needed
- Visible in git history
- Can review before processing

#### 4. Queue Sync to Comet

System sends a prompt to the `comet` session via assigner:

```
Pull latest changes and sync Google Sheets:

1. Pull from git: git pull
2. Run sync: python3 scripts/comet_sheets_sync.py
3. Report: "Synced N updates to Google Sheets"
```

#### 5. Comet Processes Updates

The comet session (browser-based Claude):

1. **Pulls from git**
   ```bash
   cd /path/to/architect
   git pull
   ```

2. **Runs sync script**
   ```bash
   python3 scripts/comet_sheets_sync.py
   ```

3. **Script processes each CSV:**
   - Reads pending CSV files
   - For each file:
     - Opens corresponding Google Sheet
     - Finds or creates project worksheet
     - Updates or appends task row
     - Moves CSV to `data/sheets_processed/`

4. **Reports completion**
   ```
   ✨ Synced 3 update(s) to Google Sheets
   ```

### Project Configuration

#### Enable Sheets for a Project

Set Google Sheets ID in project metadata:

```python
from services.sheets_git_sync import enable_sheets_for_project

enable_sheets_for_project(
    project_id=1,
    spreadsheet_id='1ABC...XYZ',
    worksheet_name='Tasks'  # Optional, defaults to project name
)
```

**Or manually via database:**

```sql
UPDATE projects
SET metadata = json_set(metadata, '$.google_sheets', json('{
  "enabled": true,
  "spreadsheet_id": "1ABC...XYZ",
  "worksheet_name": "Tasks"
}'))
WHERE id = 1;
```

#### Project Sheet Mapping

Create `config/project_sheets.json`:

```json
{
  "MyProject": "1ABC...XYZ",
  "AnotherProject": "1DEF...UVW",
  "ThirdProject": "1GHI...RST"
}
```

**Or use environment variables:**

```bash
export SHEET_ID_MYPROJECT="1ABC...XYZ"
export SHEET_ID_ANOTHERPROJECT="1DEF...UVW"
```

### Google Sheets Format

Each project gets its own worksheet with standard columns:

| Task ID | Type | Title | Status | Priority | Assigned To | Milestone | Created | Completed | Updated |
|---------|------|-------|--------|----------|-------------|-----------|---------|-----------|---------|
| 42 | feature | Add login | completed | high | john | Sprint 1 | 2026-02-01 10:00 | 2026-02-01 12:05 | 2026-02-01 12:05 |
| 15 | bug | Fix logout | resolved | critical | jane | Sprint 1 | 2026-01-30 14:00 | 2026-02-01 09:30 | 2026-02-01 09:30 |

**Sheet Features:**
- Auto-creates worksheet if doesn't exist
- Updates existing rows (by Task ID)
- Appends new rows
- Preserves manual formatting/formulas
- Supports unlimited projects

### Manual Sync

#### Run Sync Manually

From comet session or terminal:

```bash
# Full sync
python3 scripts/comet_sheets_sync.py

# Preview without changes
python3 scripts/comet_sheets_sync.py --dry-run
```

#### Test Single Task

```bash
# Queue an update
python3 services/sheets_git_sync.py --test 42 --type feature --status completed

# Check pending
ls -la data/sheets_pending/

# Process manually
python3 scripts/comet_sheets_sync.py
```

### Monitoring & Troubleshooting

#### Check Pending Updates

```bash
# List pending files
ls -la data/sheets_pending/

# Count pending
find data/sheets_pending/ -name "*.csv" | wc -l

# View a pending file
cat data/sheets_pending/ProjectName_*.csv | head
```

#### Check Processed Updates

```bash
# List recently processed
ls -lt data/sheets_processed/ | head -20

# Check if specific task was synced
grep "task_id,42" data/sheets_processed/*.csv
```

#### Check Git History

```bash
# View recent sheet commits
git log --grep="sheets:" --oneline | head -10

# See what was synced
git show <commit-hash>
```

#### Common Issues

**Issue: Comet not processing**
- Check comet session is running: `tmux list-sessions | grep comet`
- Check assigner queue: `python3 workers/assigner_worker.py --prompts`
- Manually trigger: `python3 scripts/comet_sheets_sync.py`

**Issue: Sheet not found**
- Verify project sheet mapping in `config/project_sheets.json`
- Check project metadata has correct `spreadsheet_id`
- Ensure comet has access to the sheet

**Issue: Authentication failed**
- Check service account credentials: `~/.config/gspread/service_account.json`
- Verify sheet is shared with service account email
- Test manually: `python3 -c "import gspread; print('OK')"`

**Issue: Updates not appearing**
- Check if files are in `sheets_pending/` or already processed
- Verify git pull worked: `git log --oneline | head -5`
- Check CSV format is correct

### Security & Access

#### Service Account Setup

1. **Create service account** in Google Cloud Console
2. **Enable Google Sheets API**
3. **Download credentials** → `~/.config/gspread/service_account.json`
4. **Share sheets** with service account email (e.g., `architect@project.iam.gserviceaccount.com`)

#### Access Control

- Sheets can be shared with specific users/groups
- Service account only needs `Editor` access
- Comet session runs as your user (browser auth)
- CSV files in git have same access as repository

### Best Practices

#### 1. Project Setup
- Create one Google Sheet per major project
- Use worksheets for different task types if needed
- Share sheet with team members who need visibility

#### 2. Monitoring
- Check `sheets_pending/` daily for stuck files
- Review git commits weekly to verify syncing
- Monitor comet session is running and responsive

#### 3. Manual Review
- Before processing, can edit CSV files to correct data
- Can delete pending files to skip updates
- Can manually add rows to sheets (won't be overwritten)

#### 4. Scaling
- For 100+ tasks/day, consider batching (comet sync every hour)
- For multiple teams, use separate sheets per team
- Archive old worksheets quarterly

### Integration Examples

#### Custom Webhook

Add custom processing after sheet update:

```python
# In scripts/comet_sheets_sync.py
def update_sheet(self, task_data):
    # ... existing code ...

    # Custom webhook after update
    requests.post('https://hooks.slack.com/...', json={
        'text': f"Task {task_data['task_id']} completed!"
    })
```

#### Dashboard Widget

Show pending count on dashboard:

```python
@app.route('/api/sheets/pending-count')
def sheets_pending_count():
    count = len(list(SHEETS_PENDING_DIR.glob('*.csv')))
    return jsonify({'count': count})
```

#### Scheduled Sync

Add to crontab for automatic syncing:

```cron
# Sync sheets every hour
0 * * * * cd /path/to/architect && python3 scripts/comet_sheets_sync.py >> /tmp/sheets_sync.log 2>&1
```

---
