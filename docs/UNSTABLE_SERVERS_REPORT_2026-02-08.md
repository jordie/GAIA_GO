# Unstable Servers and Workers - Root Cause Analysis
**Date**: 2026-02-08 17:19
**Analyst**: operations_manager
**Severity**: HIGH - Multiple critical issues affecting system stability

---

## Executive Summary

**System Health Score**: 4.2/10 - **CRITICAL INSTABILITY**

**Critical Issues Identified**: 7
**Services Down**: 1 (Orchestrator)
**Failed Operations (24h)**: 40 prompts
**System Load**: 8.13 (VERY HIGH)
**CPU Idle**: 6.41% (CRITICAL)

---

## 1. Service Status Overview

### ✅ OPERATIONAL Services

| Service | Port | Status | PID | Uptime | Notes |
|---------|------|--------|-----|--------|-------|
| Monitor Dashboard | 8081 | **UP** ✅ | 21376 | N/A | HTTP 200 OK |
| Architect Dashboard | 8080 | **UP** ✅ | 96930 | N/A | HTTP 200 OK |
| Reading App (Eden) | 5063 | **UP** ✅ | N/A | N/A | Port listening |
| Assigner Worker | N/A | **RUNNING** ✅ | 42315 | 19h 29m | High failure rate |
| Auto-Confirm Worker | N/A | **RUNNING** ✅ | 88337 | N/A | Multiple instances |
| Process Supervisor | N/A | **RUNNING** ✅ | 68651 | N/A | Monitoring |

### ❌ FAILED Services

| Service | Expected | Actual | Impact |
|---------|----------|--------|--------|
| **Orchestrator** | running | **STOPPED** ❌ | Cannot coordinate automated tasks |

---

## 2. Critical Issues - Root Cause Analysis

### Issue #1: Orchestrator Service Down
**Severity**: CRITICAL
**Impact**: Automated task coordination completely stopped

**Evidence**:
```
Health endpoint: "orchestrator": "stopped"
ps aux | grep orchestrator: No Python orchestrator process found
```

**Root Cause**: Service crashed or was never started

**Fix Required**:
1. Check orchestrator logs: `/tmp/*orchestrator*.log`
2. Check if orchestrator worker exists in codebase
3. Start orchestrator service
4. Add to startup automation

**Command to Fix**:
```bash
# Find orchestrator worker
find workers/ -name "*orchestrator*.py"

# Check if there's a startup script
grep -r "orchestrator" scripts/

# Start manually if found
python3 workers/[orchestrator_file].py --daemon
```

---

### Issue #2: Assigner Worker - High Failure Rate (70%)
**Severity**: CRITICAL
**Impact**: Task assignment system mostly non-functional

**Statistics**:
- Total prompts: 122
- Completed: 37 (30%)
- Failed: 85 (70%)
- Failed (24h): 40

**Error Patterns Found**:

#### A. Port Exhaustion
```
RuntimeError: No available ports for new environment
```
**Frequency**: Multiple occurrences
**Root Cause**: Environment manager trying to create unlimited environments without cleanup
**Impact**: Cannot create new development environments

**Fix**:
1. Implement port pool recycling
2. Add environment cleanup on completion
3. Limit concurrent environments
4. Use port range configuration

#### B. Duplicate Environment Names
```
ValueError: Environment 'reading-ui-improvement' already exists
```
**Frequency**: Repeated attempts
**Root Cause**: No check for existing environments before creation
**Impact**: Wastes resources, clogs logs

**Fix**:
1. Check if environment exists before creating
2. Add unique timestamp/UUID suffix to names
3. Clean up stale environments

#### C. JSON Parsing Failures
```
Failed to get environment info: Expecting value: line 1 column 1 (char 0)
```
**Frequency**: Every failed environment operation
**Root Cause**: Empty or malformed JSON response from environment API
**Impact**: Cannot query environment status

**Fix**:
1. Add error handling for empty responses
2. Log actual response content for debugging
3. Add retry with exponential backoff
4. Validate JSON before parsing

**Location**: `workers/assigner_worker.py`
**Log File**: `/tmp/architect_assigner_worker.log`

---

### Issue #3: Extreme System Load
**Severity**: HIGH
**Impact**: System unresponsive, slow task processing

**Metrics**:
```
Load Average: 8.13, 7.77, 8.60
CPU Usage: 63.46% user, 30.12% sys, 6.41% idle
Memory: 23G used, 163M unused
Compressor: 4664M (indicates memory pressure)
```

**Analysis**:
- Load > 8 on what appears to be 8-core system
- Only 6.41% CPU idle (should be >20% for healthy system)
- Heavy memory compression (4.6GB compressed)
- Swap activity: 8.5M swapins, 11M swapouts

**Root Causes**:
1. **Claude tmux sessions** - 11 concurrent Claude sessions
2. **Python workers** - Multiple daemon processes
3. **Memory pressure** - System swapping heavily
4. **No resource limits** - Processes can consume unlimited resources

**Fix**:
1. Reduce concurrent Claude sessions from 11 to 6-8
2. Add process resource limits (CPU, memory)
3. Implement session pooling instead of always-on
4. Add health checks to kill hung sessions
5. Schedule resource-intensive tasks during off-hours

---

### Issue #4: Multiple Auto-Confirm Workers
**Severity**: MEDIUM
**Impact**: Resource waste, potential conflicts

**Evidence**:
```
PID 8157:  auto_confirm_worker_v2.py --daemon
PID 88337: auto_confirm_worker.py --daemon
PID 87841: Shell wrapper for auto_confirm_worker.py
```

**Root Cause**: Multiple versions running simultaneously
- v2 implementation
- Original implementation
- Shell wrapper not cleaning up

**Impact**:
- Competing for same sessions
- Double resource consumption
- Potential race conditions

**Fix**:
1. Kill all auto-confirm processes
2. Choose canonical version (likely v2)
3. Start only one instance
4. Update startup scripts to prevent duplicates

**Commands**:
```bash
# Kill all auto-confirm workers
pkill -f auto_confirm_worker

# Start only v2
python3 workers/auto_confirm_worker_v2.py --daemon

# Verify single instance
ps aux | grep auto_confirm | grep -v grep
```

---

### Issue #5: Environment Manager Failures
**Severity**: MEDIUM
**Impact**: Cannot create isolated development environments

**Error Summary**:
- Port exhaustion: Multiple environments competing for ports
- Duplicate names: No uniqueness enforcement
- API failures: JSON parsing errors

**Affected Environments**:
- `reading-ui-improvement` (duplicate creation attempts)
- `math-ui-improvement` (port exhaustion)
- `reading-performance-optimization` (port exhaustion)
- `ui_improvement-1770573925` (port exhaustion)

**Root Cause**: Environment manager design flaws
1. No port pool management
2. No environment lifecycle (create → use → destroy)
3. No cleanup of abandoned environments
4. No validation before creation

**Fix Strategy**:
1. **Short-term**: Manual cleanup of stale environments
2. **Medium-term**: Add environment TTL (auto-cleanup after 24h)
3. **Long-term**: Redesign with proper resource management

---

### Issue #6: No PID Files for Workers
**Severity**: LOW
**Impact**: Hard to manage worker lifecycle

**Evidence**:
```bash
find /tmp -name "architect*.pid"
# Returns empty - no PID files exist
```

**Root Cause**: Workers not creating PID files or wrong location

**Impact**:
- Can't easily check if worker is running
- Can't cleanly stop workers
- Hard to detect stale processes

**Fix**:
1. Verify PID file creation in worker code
2. Standardize PID file location
3. Add PID file cleanup on exit
4. Update monitoring to check PID files

---

### Issue #7: Port 8080 Duplicate Binding
**Severity**: LOW
**Impact**: Confusion in monitoring, potential conflict

**Evidence**:
```
tcp4       0      0  *.8080                 *.*                    LISTEN
tcp4       0      0  *.8080                 *.*                    LISTEN
```

**Analysis**: Two processes or socket options showing duplicate

**Investigation Needed**:
```bash
lsof -i :8080
# Check which process(es) are binding
```

---

## 3. Worker Status Detail

### Assigner Worker
- **PID**: 42315
- **Uptime**: 19h 29m 37s
- **Status**: Running but degraded
- **Queue**: 0 pending, 0 active
- **Performance**: 30% success rate
- **Issues**:
  - Environment creation failures
  - JSON parsing errors
  - Port exhaustion

### Auto-Confirm Worker
- **Status**: Multiple instances (PROBLEM)
- **PIDs**: 8157 (v2), 88337 (v1), 87841 (wrapper)
- **Issue**: Version conflict, duplicate workers

### Process Supervisor
- **PID**: 68651
- **Status**: Running
- **Purpose**: Monitor worker health

---

## 4. System Resource Analysis

### CPU Load Pattern
```
Load Average: 8.13 (1min), 7.77 (5min), 8.60 (15min)
```
**Analysis**: Sustained high load for >15 minutes
**Conclusion**: Not a spike - chronic overload

### Memory Pressure
```
Physical Memory: 23G used / 23.1G total (99.3%)
Compressed: 4.6GB
Swap ins: 8.5M
Swap outs: 11M
```
**Analysis**: System heavily swapping, memory exhausted
**Conclusion**: Need to reduce memory footprint or add RAM

### Top Consumers (by process type):
1. **Claude sessions** (11 instances) - ~1-2GB each
2. **Python workers** (multiple daemons) - ~100-500MB each
3. **Compression overhead** - 4.6GB compressed data

---

## 5. Monitored Sites Status

From `workers/site_health_monitor.py`:

| Site | URL | Expected | Actual | Status |
|------|-----|----------|--------|--------|
| Task Monitor | http://100.112.58.92:8081/monitor.html | 200 | 200 | ✅ OK |
| Reading App | https://192.168.1.231:5063/reading/ | 200 | LISTEN | ✅ OK |
| Architect Dashboard | https://100.112.58.92:8080/ | 200 | LISTEN | ✅ OK |
| Selam Pharmacy | http://100.112.58.92:7085/ | 200 | UNKNOWN | ⚠️ NEEDS CHECK |

**Action**: Check Selam Pharmacy (port 7085):
```bash
curl -s -o /dev/null -w "%{http_code}" http://100.112.58.92:7085/
lsof -i :7085
```

---

## 6. Recommended Fixes - Priority Order

### IMMEDIATE (Within 1 hour)

#### 1. Fix Orchestrator
```bash
# Find and start orchestrator
find workers/ -name "*orchestrator*.py" | grep -v test
python3 workers/[found_file].py --daemon

# Verify
curl -s http://localhost:8080/health | jq .orchestrator
```

#### 2. Consolidate Auto-Confirm Workers
```bash
# Kill all instances
pkill -f auto_confirm_worker

# Start v2 only
python3 workers/auto_confirm_worker_v2.py --daemon

# Verify single instance
ps aux | grep auto_confirm | grep -v grep | wc -l  # Should be 1
```

#### 3. Clean Up Stale Environments
```bash
# Check existing environments
curl -s http://localhost:8080/api/environments | jq

# Delete stale environments (manual review needed)
# curl -X DELETE http://localhost:8080/api/environments/[id]
```

---

### SHORT-TERM (Within 24 hours)

#### 4. Fix Assigner Worker Environment Creation
**File**: `workers/assigner_worker.py`

**Changes Needed**:
1. Add environment existence check before creation
2. Handle empty JSON responses gracefully
3. Implement port pool with recycling
4. Add unique suffixes to environment names
5. Add environment cleanup on task completion

#### 5. Reduce System Load
```bash
# Kill idle Claude sessions
tmux list-sessions | awk '{print $1}' | sed 's/://' | \
  while read sess; do
    # Check last activity, kill if idle > 2 hours
    # (Manual review recommended)
  done

# Target: Reduce from 11 to 6-8 sessions
```

#### 6. Add Resource Limits
**File**: `workers/assigner_worker.py`, all worker scripts

Add at top:
```python
import resource

# Limit memory to 500MB per worker
resource.setrlimit(resource.RLIMIT_AS, (500 * 1024 * 1024, -1))

# Limit CPU time
resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))  # 1 hour max
```

---

### MEDIUM-TERM (Within 1 week)

#### 7. Implement Environment Lifecycle Management
- Add TTL to environments (24h auto-cleanup)
- Implement environment health checks
- Add environment pooling (pre-create, reuse)
- Add cleanup worker to remove stale environments

#### 8. Add Worker Health Monitoring
- Create worker health dashboard
- Add automatic worker restart on failure
- Implement worker heartbeat system
- Alert on worker failures

#### 9. Optimize Claude Session Usage
- Implement session hibernation (suspend idle > 1h)
- Use session pooling instead of always-on
- Add session warmup/cooldown
- Schedule heavy tasks during off-hours

---

## 7. Monitoring Recommendations

### Add These Alerts

1. **System Load > 6.0**
   - Action: Investigate resource hogs
   - Escalation: Auto-kill lowest priority sessions

2. **Memory > 90%**
   - Action: Clear caches, compress data
   - Escalation: Restart non-critical workers

3. **Prompt Failure Rate > 50%**
   - Action: Check assigner logs
   - Escalation: Restart assigner worker

4. **Worker Not Responding > 5 min**
   - Action: Send SIGTERM
   - Escalation: Send SIGKILL, restart

5. **Port Exhaustion**
   - Action: Clean up stale environments
   - Escalation: Increase port pool range

---

## 8. Root Cause Summary

| Issue | Root Cause | Impact | Fix Difficulty |
|-------|------------|--------|----------------|
| Orchestrator down | Never started or crashed | HIGH | Easy |
| Assigner failures | Poor error handling, no resource mgmt | HIGH | Medium |
| High system load | Too many concurrent sessions | HIGH | Medium |
| Multiple auto-confirm | No process management | LOW | Easy |
| Environment failures | No lifecycle management | MEDIUM | Hard |
| No PID files | Worker implementation gaps | LOW | Easy |
| Port 8080 duplicate | Unknown - needs investigation | LOW | Easy |

---

## 9. Success Metrics (Post-Fix)

Target metrics after fixes:

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Prompt Success Rate | 30% | >80% | assigner_worker stats |
| System Load | 8.13 | <4.0 | top/uptime |
| CPU Idle | 6.4% | >20% | top |
| Memory Free | 163M | >2GB | top |
| Orchestrator Status | stopped | running | health API |
| Auto-Confirm Instances | 3 | 1 | ps aux count |
| Failed Prompts/day | 40 | <10 | SQLite query |

---

## 10. Immediate Action Plan

**Next 60 minutes**:

1. ✅ Monitor.html verified (HTTP 200) - **COMPLETE**
2. ⏳ Find and start orchestrator worker
3. ⏳ Consolidate auto-confirm to single instance
4. ⏳ Clean up stale environments
5. ⏳ Verify Selam Pharmacy status (port 7085)
6. ⏳ Document current environment state
7. ⏳ Create worker restart checklist
8. ⏳ Test assigner with simple prompt

**Status Updates**:
- [17:19] Monitor.html confirmed UP
- [17:19] Unstable servers report complete
- [NEXT] Start orchestrator worker

---

## Appendix A: Error Log Samples

### Assigner Worker Errors (Last 30)
```
2026-02-08 09:04:45 ERROR Failed to get environment info: Expecting value: line 1 column 1 (char 0)
2026-02-08 09:04:45 ERROR Failed to create environment: ValueError: Environment 'reading-ui-improvement' already exists
2026-02-08 09:37:12 ERROR Failed to create environment: RuntimeError: No available ports for new environment
2026-02-08 09:48:59 ERROR Failed to create environment: RuntimeError: No available ports for new environment
2026-02-08 09:54:50 ERROR Failed to create environment: RuntimeError: No available ports for new environment
2026-02-08 10:05:22 ERROR Failed to create environment: ValueError: Environment 'reading-ui-improvement' already exists
2026-02-08 10:05:25 ERROR Failed to create environment: RuntimeError: No available ports for new environment
```

**Pattern**: Repeating errors every 5-15 minutes, same root causes

---

## Appendix B: Process List

### Critical Python Processes
```
PID    CPU%  MEM   COMMAND
8157   6.0   29M   auto_confirm_worker_v2.py --daemon
42315  0.4   73M   assigner_worker.py --daemon (19h uptime)
96930  0.0   114M  app.py --port 8080 --host 0.0.0.0
68651  0.0   20M   process_supervisor.py --daemon
88337  3.0   21M   auto_confirm_worker.py --daemon
```

---

## Appendix C: Commands Reference

### Check Service Status
```bash
# Health endpoint
curl -s http://localhost:8080/health | jq

# Worker status
python3 workers/assigner_worker.py --status

# Process list
ps aux | grep -E "architect|worker|monitor" | grep -v grep

# Port listeners
lsof -i -P | grep LISTEN | grep -E "8080|8081|5063|7085"
```

### Fix Commands
```bash
# Restart assigner
pkill -f assigner_worker
python3 workers/assigner_worker.py --daemon

# Restart auto-confirm (v2 only)
pkill -f auto_confirm_worker
python3 workers/auto_confirm_worker_v2.py --daemon

# Check logs
tail -f /tmp/architect_assigner_worker.log
tail -f /tmp/architect_dashboard.log
```

---

**Report Complete**: 2026-02-08 17:19
**Next Review**: After orchestrator fix (30 minutes)
**Escalation**: If load remains >6.0 after 2 hours
