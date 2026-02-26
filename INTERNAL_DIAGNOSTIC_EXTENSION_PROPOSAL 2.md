# Internal Diagnostic Extension for Architect System

**Status**: ARCHITECTURE PROPOSAL
**Priority**: MEDIUM-HIGH
**Complexity**: MEDIUM
**Created**: 2026-02-21

## Overview

Create an internal component extension (similar to Web Store, PDF Viewer, Hangouts shown in `comet://extensions-internals`) that provides:
- System-level visibility into Architect extension state
- Internal metrics & performance monitoring
- Cross-extension communication hub
- Debugging dashboard at `chrome://architect-internals`
- No user-facing UI (purely internal)

## Why Internal Extension?

### Advantages of Component/Internal Extension

```
Regular Extension (Current Setup)          Internal Extension (Proposed)
├─ User-facing UI                         ├─ Hidden from user view
├─ Can be disabled by user                ├─ System critical (can't disable)
├─ Permission constraints                 ├─ Full system access
├─ Limited cross-extension comms          ├─ Direct internal messaging
└─ Visible in extensions list             └─ Only in chrome://extensions

Benefits:
✓ Complete visibility into state
✓ Can't be accidentally disabled
✓ Access to internals (e.g., comet://extensions-internals)
✓ Can coordinate between machines
✓ Performance monitoring without overhead
✓ System-level debugging
```

## Proposed Architecture

### Component Structure

```
Location: COMPONENT (like PDF Viewer, Hangouts)
Manifest Version: 3
Permissions:
  - management (see all extensions)
  - system.display, system.storage, system.cpu, system.memory, system.network
  - extensionTypes (access internal APIs)
  - debugger (for debugging capabilities)

Entry Points:
  - chrome://architect-internals (diagnostic dashboard)
  - Internal messaging API (for Architect extension to report data)
  - System metrics collection
  - Cross-machine sync coordination
```

### Core Capabilities

#### 1. **Real-time Extension Monitoring**
```javascript
// Can see all installed extensions and their status
chrome.management.getAll((extensions) => {
  // Monitor:
  // - Architect extension health
  // - Tab Group Manager state
  // - Perplexity capture stats
  // - Service worker status
  // - Event listener counts
  // - Memory usage per extension
})
```

#### 2. **System Metrics Collection**
```javascript
// Access system-level APIs
chrome.system.display.getInfo()      // Display metrics
chrome.system.storage.getInfo()      // Storage state
chrome.system.cpu.getInfo()          // CPU usage
chrome.system.memory.getInfo()       // Memory pressure
chrome.system.network.getNetworkInterfaces()  // Network state
```

#### 3. **Internal Messaging Hub**
```javascript
// Enable communication between:
// - Pink Laptop Architect extension
// - Mac Mini Architect extension
// - Queue system
// - GAIA dashboard
// - Internal diagnostic extension

chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  // Log and coordinate cross-extension messages
})
```

#### 4. **Diagnostic Dashboard**
```
chrome://architect-internals shows:
├─ Extension Health
│  ├─ Architect: running (12 event listeners)
│  ├─ Tab Group Manager: idle (5 active)
│  └─ Perplexity capture: capturing (3 conversations/min)
├─ System State
│  ├─ CPU: 42%
│  ├─ Memory: 8.2GB / 16GB (51%)
│  ├─ Network: Online
│  └─ Storage: 256GB / 512GB (50%)
├─ Queue Status
│  ├─ Pending: 5
│  ├─ In Progress: 12
│  ├─ Failed: 2
│  └─ Throughput: 2.3 prompts/sec
├─ Performance Metrics
│  ├─ Service worker uptime: 24h 32m
│  ├─ Last error: None
│  ├─ Message latency: 12ms avg
│  └─ Storage usage: 8.4MB
└─ Cross-Machine Sync
   ├─ Pink Laptop: Connected (last sync 2s ago)
   ├─ Mac Mini: Connected (last sync 3s ago)
   └─ Queue depth distribution: 50/50
```

#### 5. **Performance Monitoring**
```javascript
// Track without impacting user experience
class InternalMetricsCollector {
  constructor() {
    this.metrics = {
      messageLatencies: [],
      extensionMemory: {},
      errorRates: {},
      eventLoopLag: 0
    }
  }

  trackMessage(extensionId, latencyMs) {
    // Aggregate latency data
    // Alert on anomalies (>100ms)
  }

  trackMemory() {
    // Poll memory usage per extension
    // Alert on leaks (>50MB increase/hour)
  }

  trackErrors() {
    // Catch uncaught errors from all extensions
    // Rate limit: alert if >5 errors/minute
  }
}
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Create manifest.json as COMPONENT extension
- [ ] Register internal messaging APIs
- [ ] Basic system metrics collection
- [ ] Dashboard skeleton

### Phase 2: Core Monitoring (Week 2)
- [ ] Extension health monitoring
- [ ] Queue status tracking
- [ ] Performance metrics collection
- [ ] Real-time dashboard

### Phase 3: Cross-Machine (Week 3)
- [ ] Sync state between machines
- [ ] Aggregate metrics across Pink Laptop + Mac Mini
- [ ] Central coordination point
- [ ] Alerting system

### Phase 4: Integration (Week 4)
- [ ] Connect with intelligent auto-confirm
- [ ] Connect with interrupt prevention
- [ ] Connect with assigner worker
- [ ] Production deployment

## Manifest Structure

```json
{
  "manifest_version": 3,
  "name": "Architect System Internals",
  "version": "1.0.0",
  "description": "Internal diagnostic extension for Architect system",
  "type": "COMPONENT",

  "permissions": [
    "management",
    "system.display",
    "system.storage",
    "system.cpu",
    "system.memory",
    "system.network",
    "storage",
    "offscreen"
  ],

  "host_permissions": [
    "<all_urls>"
  ],

  "action": {
    "default_title": "Architect Internals",
    "default_icon": {
      "16": "images/icon-16.png",
      "48": "images/icon-48.png",
      "128": "images/icon-128.png"
    }
  },

  "background": {
    "service_worker": "service-worker.js"
  },

  "chrome_url_overrides": {
    "newtab": "internals.html"
  },

  "externally_connectable": {
    "ids": [
      "bfgimnlbnmeeehlhognndagnicfcbjjk"  # Architect extension ID
    ],
    "matches": [
      "https://localhost:8080/*",
      "https://pink-laptop.local:8080/*",
      "https://mac-mini.local:8080/*"
    ]
  }
}
```

## API Endpoints (chrome://architect-internals)

### Extension Info
```
GET /api/extensions
Returns: [{id, name, status, listeners, memory, lastError}]

GET /api/extensions/{id}/detail
Returns: Full extension metadata including permissions, contexts, etc.

GET /api/extensions/{id}/errors
Returns: Recent errors from specific extension
```

### System Metrics
```
GET /api/system/metrics
Returns: {cpu, memory, storage, network, display}

GET /api/system/performance
Returns: {serviceWorkerUptime, messageLatency, eventLoopLag}

GET /api/system/health
Returns: {overallHealth, warnings, criticalIssues}
```

### Queue Status
```
GET /api/queue/status
Returns: {pending, inProgress, completed, failed, throughput}

GET /api/queue/distribution
Returns: Per-machine queue depth for load balancing

GET /api/queue/performance
Returns: Latency stats, throughput trends, bottlenecks
```

### Cross-Machine Sync
```
GET /api/sync/machines
Returns: [{machine, status, lastSync, queueDepth, health}]

GET /api/sync/conflicts
Returns: Any data inconsistencies between machines

POST /api/sync/force
Manually trigger sync between machines
```

## Dashboard Features

### Real-Time Graphs
```
Memory Usage Over Time
├─ Architect extension
├─ Tab Group Manager
└─ System total

Message Latency
├─ P50: 8ms
├─ P95: 24ms
└─ P99: 89ms

Queue Throughput
├─ Prompts/sec
└─ Success rate %

Cross-Machine Sync
├─ Last sync: 2s ago
├─ Latency: 45ms
└─ Queue balance: 50/50
```

### Alerts & Warnings
```
🟡 Warning: Memory usage at 75%
🔴 Alert: Service worker crashed 3x in last hour
🟡 Warning: Queue depth > 100
🔴 Alert: Mac Mini unreachable
✅ All systems normal
```

### Debug Tools
```
- Console for service worker logs
- Message inspector (show all internal communications)
- Performance profiler
- Memory leak detector
- Extension reload controls (emergency)
- Force sync button
- Export metrics (JSON/CSV)
```

## Deployment Strategy

### Installation Method

Since this needs to be a COMPONENT extension (not user-installable), deployment involves:

1. **Mac Mini (Comet Browser)**
   - Location: `/Applications/Comet.app/Contents/Frameworks/.../Resources/architect-internals`
   - Register in Comet configuration
   - Auto-load on browser startup

2. **Pink Laptop (Chrome/Comet)**
   - Similar installation
   - Both machines auto-sync state

### Configuration (GAIA)
```yaml
# ~/.gaia/config.json
architect:
  internal_extension:
    enabled: true
    auto_update: true
    metrics_interval_seconds: 5
    alert_thresholds:
      memory_usage_percent: 75
      error_rate_per_minute: 5
      queue_depth: 150
      sync_latency_ms: 1000
```

## Benefits

### For Development
- ✅ Real-time insight into system state
- ✅ Quick debugging of issues
- ✅ Performance profiling
- ✅ Error tracking without polluting user view

### For Operations
- ✅ Monitor both machines from one dashboard
- ✅ Automatic alerting on problems
- ✅ Performance trends & analytics
- ✅ Cross-machine load balancing visibility

### For GAIA System
- ✅ Coordinator hub for extensions
- ✅ Metrics source for intelligent decision-making
- ✅ Sync state manager
- ✅ Emergency controls (reload, restart, etc.)

## Integration Points

### With Auto-Confirm Engine
```
Auto-Confirm needs System State:
├─ Current memory pressure
├─ Service worker stability
├─ Queue depth (decide auto-approve urgency)
└─ Error rate (escalate if system unhealthy)

Internals provides: /api/system/health → Auto-Confirm uses for confidence
```

### With Interrupt Prevention
```
Interrupt Prevention needs Session State:
├─ Is session actively typing?
├─ CPU/memory pressure
├─ Service worker responsiveness
└─ Queue backlog

Internals provides: Real-time session metrics → Interrupt Prevention uses for decisions
```

### With Assigner Worker
```
Assigner needs Visibility:
├─ Session health scores
├─ Queue depth trends
├─ Cross-machine latency
└─ System resource availability

Internals provides: Centralized metrics → Assigner uses for routing decisions
```

## Success Metrics

- ✅ Dashboard accessible at `chrome://architect-internals`
- ✅ Metrics collected with <5% CPU overhead
- ✅ Message latency tracking accurate to ±5ms
- ✅ Cross-machine sync latency <100ms
- ✅ Alerts triggered within 10 seconds of issue detection
- ✅ Dashboard load time <500ms
- ✅ Zero impact on user experience

## Timeline

- **Week 1**: Foundation & basic monitoring
- **Week 2**: Full dashboard & metrics collection
- **Week 3**: Cross-machine integration
- **Week 4**: Production deployment

**Total Effort**: 40-50 hours
**Complexity**: MEDIUM

---

## Related Work

This complements:
- Auto-Confirm intelligent escalation (uses system health data)
- Interrupt prevention (uses session state)
- Assigner worker enhancement (uses metrics for routing)
- Phase 4 Claude sidecar (can report metrics)

Can be implemented in parallel with other infrastructure projects.

---

**Status**: Ready for architecture review
**Next Step**: User approval to proceed with implementation
