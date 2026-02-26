# Port Standardization Scheme

## Current State

### Architect App
- DEV: 5051
- QA: 5052
- PROD: 5063

### Basic Edu Apps (Unified App)
- DEV: 5051
- QA: 5052
- PROD: 5063

### Go Wrapper API
- Current: 9090 (single instance)

---

## Proposed Standardized Port Scheme

### Pattern Rules

1. **Port Ranges by App Type**:
   - Main Apps: 5000-5999
   - API Services: 8000-8999
   - Worker Services: 9000-9999

2. **Environment Suffix Pattern**:
   - DEV:  +1  (e.g., 5051, 6051, 7051)
   - QA:   +2  (e.g., 5052, 6052, 7052)
   - PROD: +63 (e.g., 5063, 6063, 7063)

3. **App Base Port**:
   - Architect: 5000 → DEV: 5051, QA: 5052, PROD: 5063 ✓
   - Basic Edu: 5000 → DEV: 5051, QA: 5052, PROD: 5063 ✓
   - Future App 1: 6000 → DEV: 6051, QA: 6052, PROD: 6063
   - Future App 2: 7000 → DEV: 7051, QA: 7052, PROD: 7063

---

## Standardized Port Allocations

### Main Applications (5000-5999)

| Application | Base | DEV | QA | PROD |
|-------------|------|-----|-----|------|
| Architect Dashboard | 5000 | 5051 | 5052 | 5063 |
| Basic Edu Apps (Unified) | 5000 | 5051 | 5052 | 5063 |
| Reserved App Slot 1 | 6000 | 6051 | 6052 | 6063 |
| Reserved App Slot 2 | 7000 | 7051 | 7052 | 7063 |
| Reserved App Slot 3 | 5100 | 5151 | 5152 | 5163 |
| Reserved App Slot 4 | 5200 | 5251 | 5252 | 5263 |

### API Services (8000-8999)

| Service | Base | DEV | QA | PROD |
|---------|------|-----|-----|------|
| Main API Gateway | 8000 | 8051 | 8052 | 8063 |
| Go Wrapper API | 8100 | 8151 | 8152 | 8163 |
| Reserved API 1 | 8200 | 8251 | 8252 | 8263 |
| Reserved API 2 | 8300 | 8351 | 8352 | 8363 |

### Worker Services (9000-9999)

| Service | Base | DEV | QA | PROD |
|---------|------|-----|-----|------|
| Task Workers | 9000 | 9051 | 9052 | 9063 |
| Message Queue | 9100 | 9151 | 9152 | 9163 |
| Reserved Worker 1 | 9200 | 9251 | 9252 | 9263 |
| Reserved Worker 2 | 9300 | 9351 | 9352 | 9363 |

---

## Environment Variables

### Standard Format

```bash
# Application ports
export DEV_PORT=5051
export QA_PORT=5052
export PROD_PORT=5063

# API ports
export API_DEV_PORT=8151
export API_QA_PORT=8152
export API_PROD_PORT=8163

# Worker ports
export WORKER_DEV_PORT=9051
export WORKER_QA_PORT=9052
export WORKER_PROD_PORT=9063
```

### Usage Example

```bash
# Start app in DEV
APP_ENV=dev PORT=${DEV_PORT} python3 unified_app.py

# Start app in QA
APP_ENV=qa PORT=${QA_PORT} python3 unified_app.py

# Start app in PROD
APP_ENV=prod PORT=${PROD_PORT} python3 unified_app.py
```

---

## Configuration Files

### .env.dev
```
APP_ENV=dev
PORT=5051
API_PORT=8151
WORKER_PORT=9051
```

### .env.qa
```
APP_ENV=qa
PORT=5052
API_PORT=8152
WORKER_PORT=9052
```

### .env.prod
```
APP_ENV=prod
PORT=5063
API_PORT=8163
WORKER_PORT=9063
```

---

## Docker Compose Example

```yaml
version: '3.8'

services:
  app-dev:
    image: architect:latest
    ports:
      - "5051:5051"
    environment:
      - APP_ENV=dev
      - PORT=5051

  app-qa:
    image: architect:latest
    ports:
      - "5052:5052"
    environment:
      - APP_ENV=qa
      - PORT=5052

  app-prod:
    image: architect:latest
    ports:
      - "5063:5063"
    environment:
      - APP_ENV=prod
      - PORT=5063
```

---

## Nginx Proxy Configuration

```nginx
# DEV environment
upstream dev_backend {
    server 127.0.0.1:5051;
}

# QA environment
upstream qa_backend {
    server 127.0.0.1:5052;
}

# PROD environment
upstream prod_backend {
    server 127.0.0.1:5063;
}

server {
    listen 80;
    server_name dev.architect.local;
    location / {
        proxy_pass http://dev_backend;
    }
}

server {
    listen 80;
    server_name qa.architect.local;
    location / {
        proxy_pass http://qa_backend;
    }
}

server {
    listen 80;
    server_name architect.local;
    location / {
        proxy_pass http://prod_backend;
    }
}
```

---

## Makefile Targets

```makefile
.PHONY: dev qa prod

dev:
	APP_ENV=dev PORT=5051 python3 unified_app.py

qa:
	APP_ENV=qa PORT=5052 python3 unified_app.py

prod:
	APP_ENV=prod PORT=5063 python3 unified_app.py

api-dev:
	./go_wrapper/apiserver --port 8151

api-qa:
	./go_wrapper/apiserver --port 8152

api-prod:
	./go_wrapper/apiserver --port 8163
```

---

## Port Conflict Resolution

### Check for Port Usage

```bash
# Check if port is in use
lsof -nP -iTCP:5051 -sTCP:LISTEN

# Kill process on specific port
kill $(lsof -t -i:5051)

# Find available port in range
for port in {5051,5052,5063}; do
    if ! lsof -nP -iTCP:$port -sTCP:LISTEN > /dev/null; then
        echo "Port $port is available"
    fi
done
```

---

## Migration Plan

### Phase 1: Document Current State ✓
- [x] Document existing port usage
- [x] Define standardization scheme

### Phase 2: Update Configuration Files
- [ ] Update .env files
- [ ] Update docker-compose.yml
- [ ] Update Makefile
- [ ] Update deployment scripts

### Phase 3: Update Documentation
- [ ] Update README.md
- [ ] Update CLAUDE.md
- [ ] Update OPERATIONS.md
- [ ] Update deployment guides

### Phase 4: Update Code
- [ ] Update hardcoded ports in code
- [ ] Use environment variables instead
- [ ] Add validation for port configuration

### Phase 5: Testing
- [ ] Test DEV environment
- [ ] Test QA environment
- [ ] Test PROD environment
- [ ] Test port conflicts

### Phase 6: Deployment
- [ ] Deploy to DEV
- [ ] Deploy to QA
- [ ] Deploy to PROD

---

## Benefits

1. **Consistency**: Same pattern across all applications
2. **Predictability**: Easy to remember port numbers
3. **Scalability**: Room for many applications (5000-9999 range)
4. **Organization**: Clear separation by service type
5. **Documentation**: Self-documenting port scheme
6. **Automation**: Easy to script environment setup

---

## Quick Reference Card

```
Environment Suffix Pattern:
  DEV  = Base + 51  (e.g., 5000 + 51 = 5051)
  QA   = Base + 52  (e.g., 5000 + 52 = 5052)
  PROD = Base + 63  (e.g., 5000 + 63 = 5063)

Service Type Ranges:
  Main Apps:    5000-5999
  APIs:         8000-8999
  Workers:      9000-9999

Current Allocations:
  Architect/Edu:  5051 (DEV), 5052 (QA), 5063 (PROD)
  Go Wrapper:     8151 (DEV), 8152 (QA), 8163 (PROD)
```

---

## Notes

- Port 5063 for PROD established as standard (basic_edu reference)
- Pattern maintains +51/+52/+63 suffix for easy calculation
- Base ports (5000, 6000, etc.) are reserved, not used directly
- Hundreds (5100, 5200) available for more apps in same range
- All ports above 5000 to avoid privileged ports (1-1024)
- Scheme supports 40+ applications per service type
