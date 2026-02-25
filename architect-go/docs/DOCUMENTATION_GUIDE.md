# API Documentation Guide

## Overview

This guide explains the Architect Dashboard API documentation structure, tools, and how to use the generated documentation files.

## Documentation Structure

```
docs/
├── API_SPECIFICATION.md          # Comprehensive API reference (this file)
├── DOCUMENTATION_GUIDE.md         # This guide
├── SECURITY_REVIEW.md             # Security best practices and OWASP guidance
├── PERFORMANCE_OPTIMIZATION.md    # Performance tuning and optimization
├── DATABASE_OPTIMIZATION.md       # Database optimization strategies
└── generated/                     # Auto-generated documentation
    ├── index.html                # Documentation portal index
    ├── openapi.json              # OpenAPI 3.0 specification
    ├── swagger-ui.html           # Interactive Swagger UI
    ├── redoc.html                # Beautiful ReDoc documentation
    └── postman-collection.json   # Postman API collection
```

## Generating Documentation

### Automated Generation

The documentation is automatically generated using the `docs_generator` CLI tool:

```bash
# Generate documentation to docs/generated/
go build -o docs_gen ./cmd/docs_generator
./docs_gen -output docs/generated

# Or use the provided script
./scripts/generate_docs.sh
```

### What Gets Generated

| File | Purpose | Format |
|------|---------|--------|
| `index.html` | Portal index with links to all tools | HTML |
| `openapi.json` | Complete OpenAPI 3.0 specification | JSON |
| `swagger-ui.html` | Interactive API explorer with Try It Out | HTML |
| `redoc.html` | Beautiful responsive API docs | HTML |
| `postman-collection.json` | Importable Postman collection | JSON |

## Using the Documentation

### Quick Start: Web Interface

1. **Open the Documentation Portal**
   ```
   file:///path/to/architect-go/docs/generated/index.html
   ```

2. **Choose Your Tool:**
   - **Swagger UI**: Try out API calls in real-time
   - **ReDoc**: Browse API documentation beautifully
   - **OpenAPI Spec**: Machine-readable API definition
   - **Postman**: Import for API testing

### Swagger UI

**Best for:** Interactive exploration and testing

1. Open `swagger-ui.html` in your browser
2. Select an endpoint from the left sidebar
3. Click "Try it out" to test the endpoint
4. Fill in required parameters and request body
5. Click "Execute" to send the request
6. View the response with status code, headers, and body

**Features:**
- Live API testing without leaving the browser
- Request/response syntax highlighting
- Authentication support
- Request/response history
- Model schema exploration

**Example:**
```
1. Navigate to GET /events
2. Set limit=10, offset=0
3. Click Try it out
4. Click Execute
5. View paginated event list
```

### ReDoc

**Best for:** Reading and understanding the API

1. Open `redoc.html` in your browser
2. Browse endpoints by category using the left sidebar
3. Click an endpoint to expand and view details
4. Scroll down to see request/response examples
5. Use search (Ctrl+F) to find specific endpoints

**Features:**
- Responsive mobile-friendly design
- Fast search across all endpoints
- Automatic code highlighting
- Schema references
- Request/response examples

### Postman

**Best for:** Comprehensive API testing and automation

1. Import `postman-collection.json` into Postman
2. Set the `base_url` variable in the collection:
   - Development: `http://localhost:8080/api`
   - Staging: `https://staging.architect.example.com/api`
   - Production: `https://api.architect.example.com`
3. Authenticate by running the Login request
4. Access endpoints organized by category
5. Run requests and create test scripts

**Example Collection Structure:**
```
Architect Dashboard API
├── Authentication
│   ├── Login
│   └── Logout
├── Events
│   ├── List Events
│   ├── Create Event
│   └── Get Event
├── Errors
│   ├── List Errors
│   └── Create Error
└── ... (more categories)
```

### OpenAPI JSON

**Best for:** Programmatic API access and code generation

The `openapi.json` file contains the complete OpenAPI 3.0 specification and can be used with:

**Code Generation:**
```bash
# Generate Go client
openapi-generator generate -i docs/generated/openapi.json -g go -o generated/go-client

# Generate Python client
openapi-generator generate -i docs/generated/openapi.json -g python -o generated/python-client

# Generate TypeScript client
openapi-generator generate -i docs/generated/openapi.json -g typescript-axios -o generated/ts-client
```

**Server Validation:**
```bash
# Validate OpenAPI spec
npx @openapi-validator/openapi-validator docs/generated/openapi.json
```

**Documentation Hosting:**
```bash
# Serve documentation with docker
docker run -p 8080:8080 -v $(pwd)/docs/generated:/usr/share/nginx/html:ro nginx
```

## API Documentation Files

### API_SPECIFICATION.md

Comprehensive markdown documentation covering:
- API overview and base URLs
- Authentication methods
- Error handling and status codes
- Rate limiting
- Request/response formats
- Complete endpoint reference
- Common schemas
- Best practices
- SDK examples

### SECURITY_REVIEW.md

Security guidance including:
- OWASP Top 10 vulnerability mitigations
- Credential management patterns
- Input validation strategies
- API security headers
- Rate limiting implementation
- Audit logging
- Incident response procedures

### PERFORMANCE_OPTIMIZATION.md

Performance tuning covering:
- Database query optimization
- Index strategies
- Caching patterns
- API response optimization
- Load testing infrastructure
- Monitoring and profiling

### DOCUMENTATION_GUIDE.md

This file! Explains:
- Documentation structure
- How to generate documentation
- How to use each documentation tool
- Best practices
- Troubleshooting

## Documentation Components

### Endpoints by Category

**Authentication (5 endpoints)**
- User login/logout
- Session management
- Authentication state

**Events (45+ endpoints)**
- List/get/create events
- Event filtering and searching
- Event type management
- Bulk operations

**Errors (40+ endpoints)**
- List/get/create errors
- Error filtering and aggregation
- Error resolution
- Error statistics

**Notifications (35+ endpoints)**
- List/get/create notifications
- Notification delivery
- Read status tracking
- Notification preferences

**Sessions (30+ endpoints)**
- Session management
- Session tracking
- Session validation
- Session history

**Integrations (50+ endpoints)**
- Integration configuration
- Provider management
- Integration testing
- Health monitoring

**Webhooks (40+ endpoints)**
- Webhook management
- Event subscription
- Delivery tracking
- Retry policies

**Health & Monitoring (15+ endpoints)**
- Health checks
- Metrics collection
- Component status
- Performance metrics

## Best Practices

### API Documentation Maintenance

1. **Keep Synchronized**: When API changes occur, regenerate documentation
   ```bash
   ./scripts/generate_docs.sh
   git add docs/generated/
   git commit -m "docs: Regenerate API documentation"
   ```

2. **Version Control**: Commit generated documentation to repository
   - Enables API history tracking
   - Facilitates code review of API changes
   - Provides documentation snapshots per version

3. **Update Manual Docs**: When adding new endpoints
   - Update `API_SPECIFICATION.md` with descriptions
   - Add examples and use cases
   - Document error scenarios

### Using with Client Libraries

**Go**
```go
import openapi "github.com/architect-team/openapi-go"
client := openapi.NewClient("https://api.architect.example.com")
```

**Python**
```python
from architect_sdk import ApiClient, Configuration
config = Configuration(host="https://api.architect.example.com")
api_client = ApiClient(config)
```

**JavaScript**
```javascript
const ArchitectApi = require('architect-sdk');
const api = new ArchitectApi.DefaultApi();
```

### Testing the API

**With curl:**
```bash
# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"architect", "password":"peace5"}'

# List events
curl -X GET "http://localhost:8080/api/events?limit=10" \
  -H "Cookie: session=sess_xxx"
```

**With httpie:**
```bash
# Login
http POST http://localhost:8080/api/auth/login \
  username=architect password=peace5

# List events
http GET http://localhost:8080/api/events limit==10 \
  Cookie:"session=sess_xxx"
```

**With Postman:**
- Import the `postman-collection.json`
- Set collection variables
- Run requests

## OpenAPI Schema Reference

### Server Configuration

```json
"servers": [
  {
    "url": "https://api.architect.example.com",
    "description": "Production"
  },
  {
    "url": "https://staging.architect.example.com",
    "description": "Staging"
  },
  {
    "url": "http://localhost:8080",
    "description": "Development"
  }
]
```

### Security Schemes

```json
"securitySchemes": {
  "sessionCookie": {
    "type": "apiKey",
    "name": "session",
    "in": "cookie"
  },
  "bearerToken": {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT"
  }
}
```

### Response Schemas

Common response types:

**Success Response**
```json
{
  "data": {},
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 100,
    "pages": 5
  }
}
```

**Error Response**
```json
{
  "code": "ERROR_CODE",
  "message": "Error description",
  "details": {}
}
```

## Troubleshooting

### Swagger UI Won't Load

**Issue**: Swagger UI shows blank page

**Solution**:
1. Check browser console for errors
2. Verify `openapi.json` path is correct
3. Ensure CORS headers are set properly
4. Try a different browser

### ReDoc Not Displaying

**Issue**: ReDoc page shows error

**Solution**:
1. Verify `openapi.json` is valid JSON
2. Check OpenAPI spec with validator
3. Clear browser cache and reload
4. Check browser network tab for 404s

### Postman Collection Not Importing

**Issue**: Postman can't import collection

**Solution**:
1. Verify JSON is valid: `jq . postman-collection.json`
2. Ensure file isn't corrupted
3. Regenerate with `docs_generator`
4. Update Postman to latest version

### API Spec Validation Errors

**Issue**: Generated spec has validation errors

**Solution**:
1. Run OpenAPI validator:
   ```bash
   npx @openapi-validator/openapi-validator docs/generated/openapi.json
   ```
2. Fix errors in `internal/openapi/spec_registry.go`
3. Regenerate documentation
4. Re-validate

## CI/CD Integration

### GitHub Actions

```yaml
name: Generate API Docs
on:
  push:
    paths:
      - 'pkg/http/handlers/**'
      - 'internal/openapi/**'
      - 'cmd/docs_generator/**'

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-go@v2
      - run: go build -o docs_gen ./cmd/docs_generator
      - run: ./docs_gen -output docs/generated
      - uses: actions/upload-artifact@v2
        with:
          name: api-docs
          path: docs/generated/
```

## Additional Resources

- **OpenAPI Specification**: https://spec.openapis.org/oas/v3.0.3
- **Swagger Editor**: https://editor.swagger.io/
- **OpenAPI Generator**: https://openapi-generator.tech/
- **API Documentation Best Practices**: https://swagger.io/resources/articles/best-practices-in-api-documentation/

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.2.0 | Feb 2024 | Initial comprehensive documentation |
| 3.1.0 | Jan 2024 | Basic API documentation |
| 3.0.0 | Dec 2023 | API release |

---

**Last Updated**: February 2024
**API Version**: 3.2.0
**Documentation Version**: 1.0.0
