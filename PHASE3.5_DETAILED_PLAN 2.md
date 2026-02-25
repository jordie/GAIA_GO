# Phase 3.5: Complete Phase 3.2 Service Implementation & HTTP Integration

## 🎯 Phase Objective

Complete the Phase 3.2 services implementation by:
1. Fixing Go module configuration
2. Resolving type bridging issues
3. Implementing missing repository methods
4. Completing service method implementations
5. Integrating services with HTTP handlers
6. Full testing and validation

**Status**: Planning Phase
**Estimated Duration**: 18-24 hours
**Target Completion**: Week of 2026-02-24

---

## 📊 Phase Overview

### Current State (Post Phase 3.4)
- ✅ 9 Phase 3.2 services registered in registry
- ✅ Service constructors wired with dependency injection
- ⚠️ Services have compilation/type issues
- ⚠️ Go module not properly configured
- ❌ No HTTP handlers integrated
- ❌ Limited test coverage
- ❌ Some stub implementations

### Target State (End of Phase 3.5)
- ✅ All services fully implemented and tested
- ✅ Go module configured and builds cleanly
- ✅ Type bridging resolved
- ✅ All repository methods implemented
- ✅ HTTP handlers integrated with services
- ✅ Full test coverage
- ✅ Ready for production deployment

---

## 🔧 Detailed Implementation Plan

### TASK 1: Go Module Configuration & Build Setup

**Objective**: Enable clean Go builds for architect-go

**Subtasks**:

#### 1.1 Create Go Module
```bash
cd architect-go
go mod init architect-go
```
- **File to Create**: `architect-go/go.mod`
- **File to Create**: `architect-go/go.sum`
- **Dependencies Needed**:
  - gorm.io/gorm v1.25.5
  - gorm.io/driver/postgres v1.5.4
  - github.com/google/uuid v1.5.0
  - github.com/go-chi/chi/v5 v5.0.10
  - Other standard dependencies

#### 1.2 Update Import Paths
- **Files to Modify**: All imports in architect-go/pkg/**/*.go
- **Current**: `import "architect-go/pkg/..."`
- **Verify**: All internal imports work correctly

#### 1.3 Verify Build
```bash
go build ./...
go test ./...
```
- **Success Criteria**:
  - ✅ No "cannot find module" errors
  - ✅ All packages compile
  - ✅ Tests run (even if some fail)

**Effort**: 1-2 hours
**Owner**: Lead Developer
**Blocking**: All subsequent tasks depend on this

---

### TASK 2: Type Bridging & Repository Interface Fixes

**Objective**: Resolve mismatch between repository return types and service expectations

**Root Cause Analysis**:
- Repositories return `map[string]interface{}` (generic)
- Services expect/return `*models.Type` (typed)
- Causes compilation errors and type mismatches

**Subtasks**:

#### 2.1 Create Type Conversion Helpers

**File**: `architect-go/pkg/services/type_converters.go` (NEW)

```go
package services

import (
    "architect-go/pkg/models"
    "encoding/json"
)

// WebhookMap to Model
func mapToWebhook(m map[string]interface{}) *models.Webhook {
    webhook := &models.Webhook{}
    if id, ok := m["id"].(string); ok {
        webhook.ID = id
    }
    if url, ok := m["url"].(string); ok {
        webhook.URL = url
    }
    // ... more field conversions
    return webhook
}

// AuditLogMap to Model
func mapToAuditLog(m map[string]interface{}) *models.AuditLog {
    log := &models.AuditLog{}
    // ... field conversions
    return log
}

// Model to Map converters (for Create/Update)
func webhookToMap(w *models.Webhook) map[string]interface{} {
    return map[string]interface{}{
        "id":             w.ID,
        "integration_id": w.IntegrationID,
        "url":            w.URL,
        // ...
    }
}

func auditLogToMap(al *models.AuditLog) map[string]interface{} {
    return map[string]interface{}{
        "id":       al.ID,
        "action":   al.Action,
        "user_id":  al.UserID,
        // ...
    }
}
```

**Effort**: 2-3 hours
**Scope**:
- WebhookService (high priority)
- AuditLogService (high priority)
- Other services using map-based repos

#### 2.2 Update Service Implementations

**Files to Modify**:
- `webhook_service_impl.go` - Update Create/Get/List methods to use converters
- `audit_log_service_impl.go` - Update Create/Get/List methods to use converters

**Pattern**:
```go
// OLD: Directly pass models.Webhook
// err := ws.repo.Create(ctx, webhook)

// NEW: Convert to map first
webhookMap := webhookToMap(webhook)
if err := ws.repo.Create(ctx, webhookMap); err != nil {
    return nil, err
}
```

**Effort**: 2-3 hours
**Testing**: Unit tests for converters

---

### TASK 3: Implement Missing Repository Methods

**Objective**: Ensure all repository interfaces have implementations

**Current Status**: EventLogRepository has impl, others may be missing

**Subtasks**:

#### 3.1 Audit All Repository Interfaces

**File**: `architect-go/pkg/repository/interfaces.go`

Create a checklist:
```
✓ EventLogRepository - Complete
✗ ErrorLogRepository - Missing impl file?
✗ NotificationRepository - Missing impl file?
✗ IntegrationRepository - Needs extension?
✗ WebhookRepository - Needs extension?
✗ SessionRepository - Needs extension?
✗ AuditLogRepository - Missing impl file?
✗ RealTimeRepository - Missing impl file?
✗ IntegrationHealthRepository - Missing impl file?
```

#### 3.2 Create Missing Repository Implementations

For each missing repository, create:

**Example: error_log_repository_impl.go**
```go
package repository

import (
    "context"
    "architect-go/pkg/models"
)

type ErrorLogRepositoryImpl struct {
    // db connection, etc
}

func (r *ErrorLogRepositoryImpl) Create(ctx context.Context, errorLog *models.ErrorLog) error {
    // Implementation
    return nil
}

func (r *ErrorLogRepositoryImpl) Get(ctx context.Context, id string) (*models.ErrorLog, error) {
    // Implementation
    return nil, nil
}

// ... implement all interface methods
```

**Files to Create**:
- `error_log_repository_impl.go`
- `notification_repository_impl.go`
- `audit_log_repository_impl.go`
- `realtime_repository_impl.go`
- `integration_health_repository_impl.go`

**Effort**: 3-4 hours
**Testing**: Integration tests with services

---

### TASK 4: Complete Service Method Implementations

**Objective**: Fill in stub implementations with real business logic

**Current Status**: Many methods return empty/default values

**Subtasks**:

#### 4.1 Audit Service Methods

For each of 9 services, identify stub methods:
```
EventLogService:
  ✓ CreateEvent - Implemented
  ✓ GetEvent - Implemented
  ⚠️ SearchEvents - Stub
  ⚠️ ArchiveEvents - Partial
  ⚠️ ExportEvents - Stub
  ...
```

#### 4.2 Implement High-Priority Methods

**Priority 1** (Core CRUD):
- Create*
- Get*
- List*
- Update*
- Delete*

**Priority 2** (Search/Filter):
- Search*
- GetBy*
- Filter*

**Priority 3** (Advanced):
- Export*
- Archive*
- Analyze*
- Trend*

**Pattern for Implementation**:
```go
func (s *EventLogServiceImpl) ExportEvents(ctx context.Context, format string, filters *EventFilterRequest) (*EventExportResponse, error) {
    // 1. Build filter map from request
    filterMap := make(map[string]interface{})

    // 2. Call repository with filters
    events, _, err := s.repo.List(ctx, filterMap, 10000, 0)
    if err != nil {
        return nil, fmt.Errorf("failed to fetch events for export: %w", err)
    }

    // 3. Format data based on format type
    var exportData interface{}
    switch format {
    case "json":
        exportData = events
    case "csv":
        exportData = s.eventsToCSV(events)
    default:
        return nil, fmt.Errorf("unsupported format: %s", format)
    }

    // 4. Return response
    return &EventExportResponse{
        Format:    format,
        Data:      exportData,
        ExportedAt: time.Now(),
        Size:      int64(len(events)),
    }, nil
}
```

**Effort**: 4-5 hours
**Files to Modify**:
- `event_log_service_impl.go`
- `error_log_service_impl.go`
- `notification_service_impl.go`
- `integration_service_impl.go`
- `webhook_service_impl.go`
- `session_tracking_service_impl.go`
- `audit_log_service_impl.go`
- `realtime_event_service_impl.go`
- `integration_health_service_impl.go`

---

### TASK 5: HTTP Handler Integration

**Objective**: Wire services into HTTP endpoints

**Subtasks**:

#### 5.1 Create HTTP Handler Files

For each service, create handlers file:

**File**: `architect-go/pkg/http/handlers/event_log_handlers.go` (NEW)

```go
package handlers

import (
    "github.com/go-chi/chi/v5"
    "architect-go/pkg/services"
)

type EventLogHandlers struct {
    service services.EventLogService
}

func NewEventLogHandlers(service services.EventLogService) *EventLogHandlers {
    return &EventLogHandlers{service: service}
}

func (h *EventLogHandlers) RegisterRoutes(router chi.Router) {
    router.Post("/events", h.CreateEvent)
    router.Get("/events/{id}", h.GetEvent)
    router.Get("/events", h.ListEvents)
    router.Put("/events/{id}", h.UpdateEvent)
    router.Delete("/events/{id}", h.DeleteEvent)
    router.Get("/events/search", h.SearchEvents)
    // ... more routes
}

func (h *EventLogHandlers) CreateEvent(w http.ResponseWriter, r *http.Request) {
    var req services.CreateEventRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    event, err := h.service.CreateEvent(r.Context(), &req)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(event)
}

// ... implement other handlers
```

**Files to Create**:
- `event_log_handlers.go`
- `error_log_handlers.go`
- `notification_handlers.go`
- `integration_handlers.go`
- `webhook_handlers.go`
- `session_tracking_handlers.go`
- `audit_log_handlers.go`
- `realtime_event_handlers.go`
- `integration_health_handlers.go`

#### 5.2 Register Handlers in Router

**File to Modify**: `architect-go/pkg/http/server.go` (or equivalent)

```go
func SetupRoutes(registry *services.Registry) chi.Router {
    r := chi.NewRouter()

    // Phase 3.1 routes
    setupProjectRoutes(r, registry.ProjectService)
    setupTaskRoutes(r, registry.TaskService)

    // Phase 3.2 routes
    setupEventLogRoutes(r, registry.EventLogService)
    setupErrorLogRoutes(r, registry.ErrorLogService)
    setupNotificationRoutes(r, registry.NotificationService)
    // ... all 9 services

    return r
}
```

**Effort**: 3-4 hours
**Scope**: Basic CRUD endpoints for all 9 services

---

### TASK 6: Testing & Validation

**Objective**: Comprehensive testing at all levels

**Subtasks**:

#### 6.1 Unit Tests

**Files to Create/Modify**:
- `*_service_impl_test.go` for each service

**Coverage Target**: 80%+

**Example Test**:
```go
func TestEventLogServiceCreateEvent(t *testing.T) {
    // Setup
    mockRepo := &MockEventLogRepository{}
    service := NewEventLogService(mockRepo)

    // Test
    req := &CreateEventRequest{
        Type: "user_action",
        Source: "api",
        Description: "Test event",
    }

    event, err := service.CreateEvent(context.Background(), req)

    // Assert
    assert.NoError(t, err)
    assert.NotNil(t, event)
    assert.Equal(t, "user_action", event.EventType)
}
```

**Effort**: 2-3 hours

#### 6.2 Integration Tests

**File**: `architect-go/pkg/services/integration_test.go`

Test service + repository interaction:
```go
func TestEventLogServiceWithRepository(t *testing.T) {
    // Setup real repository
    repo := setupTestRepository(t)
    defer teardownTestRepository(t, repo)

    service := NewEventLogService(repo)

    // Create event
    event, err := service.CreateEvent(ctx, &CreateEventRequest{...})
    assert.NoError(t, err)

    // Retrieve event
    retrieved, err := service.GetEvent(ctx, event.ID)
    assert.NoError(t, err)
    assert.Equal(t, event.ID, retrieved.ID)
}
```

**Effort**: 2-3 hours

#### 6.3 End-to-End Tests

**File**: `architect-go/pkg/http/handlers/handlers_test.go`

Test HTTP endpoint → service → repository flow:
```go
func TestEventLogHTTPEndpoints(t *testing.T) {
    router := setupTestRouter(t)

    // POST /events
    req := httptest.NewRequest("POST", "/events", strings.NewReader(`{...}`))
    w := httptest.NewRecorder()
    router.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)

    var event EventResponse
    json.NewDecoder(w.Body).Decode(&event)
    assert.NotEmpty(t, event.ID)
}
```

**Effort**: 2-3 hours

#### 6.4 Run Full Test Suite

```bash
go test ./... -v -cover
```

**Success Criteria**:
- ✅ All tests pass
- ✅ Coverage > 75%
- ✅ No race conditions detected
- ✅ No memory leaks

**Effort**: 1 hour

---

### TASK 7: Build & Verification

**Objective**: Clean build and verification

**Subtasks**:

#### 7.1 Clean Build
```bash
go clean ./...
go build ./...
go test ./...
```

**Effort**: 0.5 hours

#### 7.2 Linting
```bash
go vet ./...
golint ./...
```

**Effort**: 0.5 hours

#### 7.3 Generate Documentation
```bash
go doc -all > docs/api.txt
```

**Effort**: 0.5 hours

---

## 📅 Implementation Timeline

### Week 1 (Days 1-3)
- **Day 1**: Task 1 (Go Module Setup) - 2 hours
- **Day 1**: Task 2.1 (Type Converters) - 3 hours
- **Day 2**: Task 2.2 (Update Services) - 3 hours
- **Day 2**: Task 3.1 (Audit Repos) - 1 hour
- **Day 3**: Task 3.2 (Implement Repos) - 4 hours

### Week 1 (Days 4-5)
- **Day 4**: Task 4 (Complete Methods) - 5 hours
- **Day 5**: Task 5 (HTTP Handlers) - 4 hours

### Week 2 (Days 6-8)
- **Day 6**: Task 6.1-6.3 (Testing) - 6 hours
- **Day 7**: Task 6.4 (Test Suite) - 2 hours
- **Day 8**: Task 7 (Build & Verify) - 1.5 hours

**Total**: 18-24 hours

---

## 🎯 Success Criteria

### Must Have ✅
- [x] Go module builds cleanly
- [x] All services compile without errors
- [x] Type bridging resolved
- [x] All repository methods implemented
- [x] Core CRUD endpoints working
- [x] 75%+ test coverage
- [x] No compilation warnings

### Should Have ✅
- [x] Advanced methods implemented
- [x] Comprehensive error handling
- [x] Input validation
- [x] API documentation
- [x] Integration tests passing

### Nice to Have
- [ ] Performance optimizations
- [ ] Caching layer
- [ ] Rate limiting
- [ ] Advanced analytics

---

## 🔄 Dependency Order

```
Task 1 (Go Module)
    ↓
Task 2 (Type Bridging) + Task 3 (Repository Methods) [Parallel]
    ↓
Task 4 (Complete Implementations)
    ↓
Task 5 (HTTP Handlers)
    ↓
Task 6 (Testing) + Task 7 (Verification) [Parallel]
    ↓
✅ Phase 3.5 Complete
```

---

## ⚠️ Risk Mitigation

### Risk 1: Go Module Conflicts
- **Mitigation**: Test builds early, use vendoring if needed
- **Backup**: Use docker container with go environment

### Risk 2: Type Conversion Complexity
- **Mitigation**: Create comprehensive test suite for converters
- **Backup**: Keep original models, create adapters

### Risk 3: Repository Interface Changes
- **Mitigation**: Maintain backward compatibility
- **Backup**: Version interfaces if needed

### Risk 4: Test Coverage Gaps
- **Mitigation**: Use mutation testing, code coverage tools
- **Backup**: Manual code review

---

## 📋 Deliverables

1. ✅ Fully working Go module (architect-go)
2. ✅ All services with complete implementations
3. ✅ All repository methods implemented
4. ✅ Type converters for map/model bridging
5. ✅ HTTP handlers for all 9 services
6. ✅ Comprehensive test suite (75%+ coverage)
7. ✅ Clean builds and linting
8. ✅ Updated documentation
9. ✅ Ready for production deployment

---

## 📚 Related Files Reference

### Services Layer
- `architect-go/pkg/services/*_service.go` - Interfaces
- `architect-go/pkg/services/*_service_impl.go` - Implementations

### Repository Layer
- `architect-go/pkg/repository/interfaces.go` - Interface definitions
- `architect-go/pkg/repository/*_repository.go` - Implementations

### Models
- `architect-go/pkg/models/models.go` - Data models

### HTTP Layer
- `architect-go/pkg/http/handlers/` - HTTP handlers
- `architect-go/pkg/http/server.go` - Router setup

### DTOs
- `architect-go/pkg/services/phase3_2_dtos.go` - Request/Response types

---

## 🚀 Phase Completion

Upon completion of Phase 3.5:
- ✅ All Phase 3.2 services fully operational
- ✅ HTTP API endpoints working end-to-end
- ✅ Comprehensive test coverage
- ✅ Production-ready code
- ✅ Ready for Phase 3.6+ or production deployment

---

**Phase 3.5 Plan Ready for Approval** ✨
