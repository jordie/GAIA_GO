# Chrome Extension Management & Control Center

**Status**: QUEUED FOR FUTURE WORK
**Priority**: 7
**Type**: Infrastructure Enhancement
**Target**: GAIA Dashboard

---

## Overview

Build a comprehensive **Chrome Extension Management System** in GAIA Dashboard that:

1. **Manage internal extensions** across multiple machines (Pink Laptop, Mac Mini, others)
2. **Deploy extension updates** from dashboard without manual file transfers
3. **Monitor extension health** - WebSocket status, message queues, errors
4. **Control extension behavior** - enable/disable scripts, adjust settings
5. **View extension logs** - real-time service worker console output
6. **Manage permissions** - visual permission editor

---

## Architecture

### Components

```
GAIA Dashboard
    ├── Extension Manager Panel
    │   ├── Machine selector (Pink Laptop, Mac Mini, etc.)
    │   ├── Extension status/health
    │   ├── Real-time logs viewer
    │   ├── Permission editor
    │   └── Settings configurator
    │
    ├── Extension Registry
    │   ├── Track all extensions on all machines
    │   ├── Version management
    │   ├── Deployment history
    │   └── Rollback capability
    │
    └── Extension Deployment System
        ├── File sync to target machines
        ├── Automatic reload on updates
        ├── Pre-deployment validation
        └── Post-deployment verification
```

### Data Model

```json
{
  "extension_id": "architect-internal",
  "name": "Architect Browser Agent",
  "machines": [
    {
      "hostname": "pink-laptop",
      "ip": "100.108.134.121",
      "installed": true,
      "version": "1.0.0",
      "status": "active",
      "websocket_connected": true,
      "last_heartbeat": "2026-02-21T15:30:00Z",
      "message_queue_depth": 0,
      "permissions": ["tabs", "tabGroups", "scripting", "storage"],
      "last_updated": "2026-02-21T14:22:00Z"
    }
  ],
  "files": [
    {
      "name": "manifest.json",
      "size": 1042,
      "hash": "abc123def456",
      "updated": "2026-02-21T14:22:00Z"
    },
    {
      "name": "background.js",
      "size": 25674,
      "hash": "xyz789uvw012",
      "updated": "2026-02-21T14:22:00Z"
    }
  ]
}
```

---

## Core Features

### 1. Extension Status Dashboard

**Display per machine**:
- ✅/❌ Extension installed
- 🟢/🔴 WebSocket connection status
- 📊 Message queue depth
- 📈 Last heartbeat timestamp
- 🔧 Active permissions
- 📝 Version number

**Real-time updates** via WebSocket from extension's background service worker.

### 2. File Management & Deployment

```
Developer updates code locally
        ↓
Commits to GAIA_HOME
        ↓
GAIA Dashboard detects changes
        ↓
Shows "Updates available" notification
        ↓
Click "Deploy to Pink Laptop"
        ↓
SCP files to target machine
        ↓
Send reload command via WebSocket
        ↓
Extension reloads with new code
        ↓
Dashboard shows "✓ Deployed v1.0.1"
```

**Features**:
- Drag-drop file updates
- Batch deploy to multiple machines
- Version control with rollback
- Pre-deployment validation (manifest check, syntax)
- Deploy only changed files (hash-based)

### 3. Real-time Logs Viewer

**Show service worker console output**:

```
[14:22:33] 🟢 CONNECTED TO SERVER 🟢
[14:22:34] ✓ Queued message sent
[14:22:35] [Architect] Received from server: GAIA_MESSAGE
[14:22:36] >>> Message queued (ws state: 1)
[14:22:37] ✓ Message sent successfully
```

**Features**:
- Live streaming from service worker
- Filter by level (error, warn, info, debug)
- Search/grep logs
- Export log transcript
- Timestamp every entry
- Color-coded output

### 4. Permission Editor

**Visual permission management**:

```
☑ tabs               - Control browser tabs
☑ tabGroups         - Manage tab groups
☑ scripting         - Inject scripts into pages
☑ storage           - Local/sync storage
☑ activeTab         - Access active tab
☑ webNavigation     - Track page navigation
☑ offscreen         - Offscreen documents
☐ cookies           - Access cookies
☐ history           - Access browsing history
```

**Capability**:
- Edit permissions in manifest
- Preview impact on features
- Deploy new permissions
- Request permission rationale

### 5. Extension Settings & Configuration

**Configurable via dashboard**:

```json
{
  "websocket_url": "ws://100.112.58.92:8765",
  "reconnect_delay_ms": 2000,
  "heartbeat_interval_ms": 30000,
  "message_queue_check_interval_ms": 100,
  "max_stored_messages": 50,
  "max_conversations": 100,
  "auto_capture_enabled": false,
  "gaia_sync_enabled": true
}
```

**Deploy without code changes** - update via dashboard.

### 6. Machine Management

**Add/remove machines**:
- Hostname
- IP address
- Extension type (internal/normal)
- Auto-discovery via heartbeat
- Health checks

---

## Implementation Phases

### Phase 1: Core Status Monitoring (2 days)
- [ ] Extension status widget
- [ ] Machine registry in database
- [ ] WebSocket heartbeat from extension
- [ ] Real-time status updates

### Phase 2: File Management (3 days)
- [ ] File upload/sync to machines
- [ ] Hash-based change detection
- [ ] Deploy interface
- [ ] Version history tracking

### Phase 3: Real-time Logs (2 days)
- [ ] Service worker console streaming
- [ ] Log filtering/search
- [ ] Export functionality
- [ ] Persistent log storage

### Phase 4: Advanced Features (3 days)
- [ ] Permission editor
- [ ] Settings configurator
- [ ] Batch operations
- [ ] Rollback system

### Phase 5: Integration (2 days)
- [ ] GAIA Dashboard panels
- [ ] Permissions system
- [ ] Activity logging
- [ ] Notifications

---

## Database Schema

```sql
-- Extensions registry
CREATE TABLE extensions (
  id TEXT PRIMARY KEY,
  name TEXT,
  version TEXT,
  manifest TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Machine registrations
CREATE TABLE extension_machines (
  id INTEGER PRIMARY KEY,
  extension_id TEXT,
  hostname TEXT,
  ip_address TEXT,
  installed BOOLEAN,
  status TEXT,  -- active, inactive, error
  websocket_connected BOOLEAN,
  last_heartbeat TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (extension_id) REFERENCES extensions(id)
);

-- File versions
CREATE TABLE extension_files (
  id INTEGER PRIMARY KEY,
  extension_id TEXT,
  filename TEXT,
  content BLOB,
  hash TEXT,
  version TEXT,
  created_at TIMESTAMP,
  FOREIGN KEY (extension_id) REFERENCES extensions(id)
);

-- Deployment history
CREATE TABLE extension_deployments (
  id INTEGER PRIMARY KEY,
  extension_id TEXT,
  machine_id INTEGER,
  version TEXT,
  status TEXT,  -- pending, deployed, failed
  deployed_by TEXT,
  deployed_at TIMESTAMP,
  error_message TEXT,
  FOREIGN KEY (extension_id) REFERENCES extensions(id),
  FOREIGN KEY (machine_id) REFERENCES extension_machines(id)
);

-- Extension logs
CREATE TABLE extension_logs (
  id INTEGER PRIMARY KEY,
  machine_id INTEGER,
  log_level TEXT,  -- debug, info, warn, error
  message TEXT,
  timestamp TIMESTAMP,
  service_worker_id TEXT,
  FOREIGN KEY (machine_id) REFERENCES extension_machines(id)
);
```

---

## API Endpoints

```
GET    /api/extensions                    - List all extensions
GET    /api/extensions/:id                - Get extension details
POST   /api/extensions                    - Register new extension

GET    /api/extensions/:id/machines       - List machines for extension
GET    /api/extensions/:id/machines/:m    - Get machine status
POST   /api/extensions/:id/machines       - Register machine

GET    /api/extensions/:id/files          - List extension files
POST   /api/extensions/:id/files          - Upload file
DELETE /api/extensions/:id/files/:file    - Delete file

POST   /api/extensions/:id/deploy         - Deploy to machine(s)
GET    /api/extensions/:id/deployments    - Deployment history
POST   /api/extensions/:id/rollback       - Rollback to version

GET    /api/extensions/:id/logs           - Stream service worker logs
GET    /api/extensions/:id/logs/search    - Search logs
POST   /api/extensions/:id/logs/export    - Export logs

GET    /api/extensions/:id/manifest       - Get manifest
POST   /api/extensions/:id/manifest       - Update manifest

GET    /api/extensions/:id/settings       - Get extension settings
POST   /api/extensions/:id/settings       - Update settings

POST   /api/extensions/:id/reload         - Force reload on machine
```

---

## UI Mockup

```
┌─────────────────────────────────────────────────────────────┐
│ 🏗️ Extension Manager                          🔧 ⚙️ ↻      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Extension: Architect Browser Agent v1.0.0                   │
│  Internal Extension (Built-in)                               │
│                                                               │
│  ┌──────────────────────┬──────────────────────────────────┐ │
│  │ 🔧 Status            │ 📁 Files    📊 Logs  ⚙️ Settings│ │
│  └──────────────────────┴──────────────────────────────────┘ │
│                                                               │
│  Machines:                                                    │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ pink-laptop (100.108.134.121)                           │ │
│  │ ✅ Installed │ 🟢 Connected │ v1.0.0 │ Updated 2h ago  │ │
│  │ [📝 Logs] [🔄 Reload] [📤 Deploy] [⚙️ Edit]            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ mac-mini (100.112.58.92)                                │ │
│  │ ⚪ Not Installed │ 🔴 No Heartbeat                      │ │
│  │ [➕ Install] [🔧 Configure]                             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Available Updates:                                           │
│  • background.js (2.1 KB, modified 30 min ago)              │
│  • popup.js (4.3 KB, modified 2 hours ago)                  │
│                                                               │
│  [⬆️ Deploy to all] [⬆️ Deploy to pink-laptop only]          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

**Frontend**:
- React/Vue for dashboard panels
- Real-time updates via WebSocket
- File upload with progress
- Log streaming with virtual scroll

**Backend**:
- REST API for extension management
- WebSocket for real-time updates
- File versioning/hashing
- Deployment orchestration

**Storage**:
- SQLite for registry and history
- File system for extension files
- Local storage for machine configs

---

## Security Considerations

1. **Permission Control**:
   - Only admins can deploy extensions
   - Audit trail of all deployments
   - Rollback available for quick fixes

2. **File Integrity**:
   - Hash verification before deployment
   - Manifest syntax validation
   - Permissions whitelist

3. **Machine Verification**:
   - Heartbeat authentication
   - IP whitelisting
   - Token-based deployment auth

---

## Success Criteria

- [ ] Extension status visible for all machines in one place
- [ ] Deploy new code to machines via dashboard
- [ ] Real-time log streaming from extension
- [ ] No manual SCP/SSH needed for updates
- [ ] Automatic version history tracking
- [ ] Rollback to previous version in 1 click
- [ ] Permission management without code changes
- [ ] Settings configurable via dashboard

---

## Dependencies

- GAIA Dashboard infrastructure
- WebSocket connection from extensions
- File sync mechanism (SCP/rsync)
- Database for tracking
- Task/job queue for deployments

---

## References

- Current extension: `EXTENSION_GAIA_MESSAGING.md`
- Internal setup: `EXTENSION_INTERNAL_SETUP.md`
- Dashboard: `/app.py` in architect project
- WebSocket handler: `background.js` line 126+

---

## Notes

**Why this matters:**
- Currently managing 2 machines with extensions
- Manual updates via SSH/SCP are error-prone
- No visibility into extension health
- Hard to debug issues without console access
- Permission changes require code edits
- Version tracking is manual

**This project:**
- Automates extension deployment
- Provides central management
- Enables real-time monitoring
- Simplifies updates and rollbacks
- Scales to 10+ machines easily

---

**Status**: READY TO QUEUE
**Queue Command**: `os: Build Chrome Extension Management System for GAIA Dashboard --priority 7`
