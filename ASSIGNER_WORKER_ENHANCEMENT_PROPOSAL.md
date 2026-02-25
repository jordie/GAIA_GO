# Assigner Worker Enhancement Project

**Status**: PROPOSED
**Priority**: HIGH
**Complexity**: MEDIUM-HIGH
**Estimated Effort**: 40-60 hours

## Executive Summary

The current assigner worker is functional but limited in complexity for production GAIA system. It needs enhancement to:
1. Be properly integrated into GAIA_HOME (currently in architect directory)
2. Handle distributed queue management across multiple machines
3. Implement session capacity/health monitoring
4. Add intelligent queue routing and load balancing
5. Improve robustness with circuit breakers and graceful degradation
6. Support cross-machine prompt assignment via WebSocket/REST
7. Add comprehensive monitoring and alerting

## Current Implementation Analysis

### Existing Strengths ✅
- SQLite-based persistent queue (prompts, sessions, assignment_history tables)
- Priority-based prompt ordering (priority DESC, created_at ASC)
- Session status tracking (idle, busy, offline)
- Basic timeout handling (30 min default, configurable)
- Retry logic (max 3 retries by default)
- Provider targeting (claude, codex, ollama, openai, gemini)
- Context matching for smart session selection
- Assignment history logging

### Critical Gaps ❌

#### 1. **No Distributed Queue Architecture**
- Queue is file-local only (SQLite on single machine)
- Pink Laptop and Mac Mini queues are isolated
- No cross-machine prompt assignment
- No support for load balancing across nodes

#### 2. **Insufficient Session Health Monitoring**
- Session status detection is reactive (polls tmux every 5-10 seconds)
- No capacity tracking (how many tasks can a session handle?)
- No performance metrics (task latency, success rate per session)
- No predictive idle detection
- No session warming/optimization

#### 3. **Basic Queue Management**
- FIFO with priority levels (0-10) only
- No queue depth monitoring
- No back-pressure handling when queue grows
- No task grouping or batching
- No queue priority escalation for aging tasks
- No fairness/starvation prevention for long-waiting tasks

#### 4. **Weak Error Handling & Resilience**
- No circuit breaker pattern for failed sessions
- Simple timeout (doesn't distinguish between stuck vs slow)
- No graceful degradation if queue gets overwhelmed
- No automatic session restart
- No cache of session capabilities/performance history
- No fallback strategies (e.g., redistribute if primary session fails)

#### 5. **Missing Observability**
- No real-time queue metrics dashboard
- No alerting (e.g., "queue depth > 100", "session stuck for 30+ min")
- No queue health scoring
- No historical trend analysis
- No cost tracking per prompt
- No performance analytics

#### 6. **Lack of Intelligent Routing**
- Session selection based only on static provider pref and context match
- No dynamic rebalancing based on current load
- No anti-affinity rules (spread tasks across sessions)
- No geographic affinity (prefer local sessions for real-time tasks)
- No cost-based routing (prefer cheap providers when possible)

#### 7. **Integration Issues**
- Tightly coupled to architect directory structure
- Not designed to run in GAIA_HOME
- No configuration in GAIA_HOME config system
- No integration with GAIA lock manager (though imports it)
- Missing error reporting to GAIA system

## Proposed Architecture

### 1. Distributed Queue System

```
┌─────────────────────────────────────┐
│     Central Queue Manager           │
│     (Redis or SQLite cluster)       │
│                                     │
│  ├─ Global prompt queue             │
│  ├─ Queue depth + metrics           │
│  ├─ Session registry (cross-machine)│
│  └─ Assignment ledger               │
└────────────┬────────────────────────┘
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
 Pink Laptop Mac Mini Server
  ┌──────┐ ┌──────┐  ┌──────┐
  │Queue │ │Queue │  │Queue │
  │Agent │ │Agent │  │Agent │
  │      │ │      │  │      │
  │ Claude Claude  ...... │
  │ Codex  Codex   ...... │
  └──────┘ └──────┘  └──────┘
```

### 2. Session Health Scoring System

```
Session Score = (BaseScore * WeightFactors) + AdjustmentFactors

Where:
- BaseScore = (success_rate * 0.4) + (response_time_percentile * 0.3) + (uptime * 0.3)
- WeightFactors = depends on session type, location, capabilities
- AdjustmentFactors =
    - Ready bonus (+1.0 if idle now)
    - Degradation penalty (-0.5 if timeout occurred recently)
    - Load factor (-0.1 * (current_tasks / max_capacity))
```

### 3. Smart Queue Routing

```
Assignment Algorithm:
1. Get all available sessions from registry
2. Filter by:
   - Provider match (if target_provider specified)
   - Capability match (context similarity)
   - Health (exclude if health_score < threshold)
3. Score remaining sessions by:
   - Health score (weighted 40%)
   - Idle time (weighted 30%)
   - Cost (weighted 20%)
   - Affinity (weighted 10%)
4. Select top N candidates
5. Distribute task with preference order
6. On failure, fallback to next candidate
```

### 4. Queue Components

**New Classes:**

```python
class DistributedQueue:
    """Central queue with cross-machine visibility"""
    - add_prompt()
    - get_pending_prompts()
    - get_queue_depth()
    - get_queue_health()
    - update_capacity()

class SessionRegistry:
    """Track sessions across all machines"""
    - register_session()
    - unregister_session()
    - update_session_health()
    - get_healthy_sessions()
    - get_session_capability()

class SessionHealthMonitor:
    """Monitor and score session health"""
    - calculate_health_score()
    - detect_degradation()
    - predict_availability()
    - recommend_restart()

class QueueRouter:
    """Intelligent prompt assignment"""
    - select_best_session()
    - distribute_with_fallback()
    - rebalance_queue()
    - handle_backpressure()

class CircuitBreaker:
    """Prevent cascading failures"""
    - check_status()
    - trip_on_failure()
    - attempt_reset()
    - is_healthy()

class QueueMetricsCollector:
    """Track and expose queue metrics"""
    - record_assignment()
    - record_completion()
    - get_metrics()
    - export_prometheus()
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Move assigner_worker.py to GAIA_HOME/workers/
- [ ] Create GAIA_HOME/config/assigner.yaml
- [ ] Implement DistributedQueue with Redis fallback to SQLite
- [ ] Add SessionRegistry for cross-machine tracking
- [ ] Add GAIA integration (logging, config, locking)

### Phase 2: Health & Monitoring (Week 2)
- [ ] Implement SessionHealthMonitor with scoring
- [ ] Add circuit breaker for session failure detection
- [ ] Implement QueueMetricsCollector
- [ ] Add Prometheus metrics export
- [ ] Create monitoring dashboard in GAIA web UI

### Phase 3: Smart Routing (Week 3)
- [ ] Implement QueueRouter with capability matching
- [ ] Add cost-based routing logic
- [ ] Implement load balancing strategies
- [ ] Add anti-affinity rules for distribution
- [ ] Add session restart automation

### Phase 4: Resilience & Optimization (Week 4)
- [ ] Add back-pressure handling
- [ ] Implement queue priority escalation for aging tasks
- [ ] Add graceful degradation when overloaded
- [ ] Implement queue rebalancing across sessions
- [ ] Add automatic provider fallback strategies

### Phase 5: Integration & Deployment (Week 5)
- [ ] WebSocket-based queue server for cross-machine access
- [ ] REST API for queue management
- [ ] Integration with GAIA dashboard
- [ ] Deployment scripts for Pink Laptop and Mac Mini
- [ ] Comprehensive testing and validation

## Success Criteria

### Functional Requirements
- ✅ Queue operates across Pink Laptop and Mac Mini simultaneously
- ✅ Prompts never sent to busy/stuck sessions
- ✅ Session health automatically detected and updated
- ✅ Failed prompts automatically retry with fallback sessions
- ✅ Queue depth stays below 50 with 5+ available sessions
- ✅ Average prompt latency < 2 seconds (from queue to assignment)
- ✅ Session failure recovery < 30 seconds

### Operational Requirements
- ✅ Assigner worker runs in GAIA_HOME
- ✅ Configuration in ~/.gaia/config.json
- ✅ Monitoring dashboard shows real-time queue health
- ✅ Alerting on queue overload or session failures
- ✅ Cross-machine session visibility
- ✅ Automatic load balancing

### Performance Targets
- ✅ Queue throughput: 100+ prompts/minute
- ✅ Session discovery latency: < 100ms
- ✅ Health score update: < 500ms
- ✅ Router decision latency: < 100ms

## Configuration Schema

```yaml
# GAIA_HOME config section
assigner:
  # Queue backend: sqlite, redis, or hybrid
  queue_backend: sqlite
  redis_url: redis://localhost:6379

  # Cross-machine settings
  cluster_mode: true
  machines:
    - name: pinklaptop
      host: pink-laptop.local
      port: 8888
    - name: macmini
      host: mac-mini.local
      port: 8888

  # Health monitoring
  health_check_interval: 5  # seconds
  health_score_threshold: 0.5
  session_timeout: 30  # minutes

  # Queue settings
  max_queue_depth: 200
  back_pressure_threshold: 150
  priority_escalation_minutes: 5

  # Routing
  enable_smart_routing: true
  load_balancing_strategy: round-robin  # or weighted, least-loaded
  allow_cross_provider: true

  # Monitoring
  metrics_enabled: true
  metrics_port: 9090
  alerting_enabled: true
  alert_thresholds:
    queue_depth: 100
    session_idle_wait: 60  # minutes
    assignment_latency: 1000  # ms
```

## Resources Needed

### External Dependencies
- Redis (optional, for distributed queue)
- Prometheus (for metrics)
- SQLite (built-in, for queue storage)

### Estimated Code Changes
- New files: 8-10 (core classes + tests)
- Modified files: 3-4 (integration points)
- Total LOC: 2000-3000

### File Structure
```
GAIA_HOME/
├── workers/
│   ├── assigner_worker.py (moved)
│   └── assigner/
│       ├── queue_manager.py (new)
│       ├── session_registry.py (new)
│       ├── health_monitor.py (new)
│       ├── router.py (new)
│       ├── circuit_breaker.py (new)
│       ├── metrics.py (new)
│       └── tests/ (comprehensive tests)
├── config/
│   └── assigner.yaml (new)
└── docs/
    └── ASSIGNER_WORKER_GUIDE.md (new)
```

## Risk Assessment

### High-Risk Areas
- **Distributed queue consistency**: Race conditions in multi-machine scenario
  - Mitigation: Use atomic operations, ACID transactions, write-ahead logs
- **Session health false positives**: Misdetecting healthy sessions as stuck
  - Mitigation: Multiple detection methods, configurable thresholds, manual override
- **Performance regression**: Smart routing adds latency
  - Mitigation: Async scoring, caching, benchmarking

### Medium-Risk Areas
- **Redis dependency**: If added as backend
  - Mitigation: Make optional, fallback to SQLite
- **Monitoring overhead**: Metrics collection impacts queue throughput
  - Mitigation: Async collection, sampling for high-volume metrics

### Low-Risk Areas
- Configuration changes (backward compatible)
- New CLI commands (additive only)

## References

- Current implementation: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers/assigner_worker.py`
- Related systems: GAIA lock manager, session management, tmux integration
- Similar systems: Kubernetes job queue, Celery distributed task queue, Jenkins queue

## Next Steps

1. Get project approval from user
2. Create GAIA queue for assigner worker enhancement tasks
3. Assign Phase 1 to architect_manager session
4. Execute iteratively with testing after each phase
5. Deploy to both machines (Pink Laptop + Mac Mini)
6. Monitor metrics and iterate based on real-world performance

---

**Created**: 2026-02-21
**Last Updated**: 2026-02-21
**Owner**: Claude Code - High-Level Session
