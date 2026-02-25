# Auto-Confirm Intelligent Escalation - PHASE 2 Implementation Spec

**Status**: BLOCKING - CRITICAL PATH
**Priority**: 10/10
**Owner**: architect_manager
**Blocker For**: Phase 4 (Claude sidecar), Assigner enhancement, interrupt prevention
**Dependency**: Phase 1 must be complete

---

## Executive Summary

Phase 2 implements the **escalation and held-state system** that prevents ANY session from blocking on user approval. This is the difference between:

❌ **Current**: Session blocks, waits for manual user approval
✅ **After Phase 2**: Session escalates to manager, continues working, manager reviews async

**No manual user intervention ever required.**

---

## Implementation Overview

### Module: `services/auto_confirm_escalation.py`

This replaces Phase 1's decision logic with actual escalation execution.

```python
class EscalationManager:
    """
    Handles all escalation logic for Phase 2.
    - Routes to correct target (architect_manager or wrapper_claude)
    - Creates non-blocking async tasks
    - Manages held status
    - Implements timeouts with fallback
    - Handles approval/denial callbacks
    """
```

---

## Component 1: Escalation Routing Logic

### File: `services/auto_confirm_escalation.py` - `route_escalation()`

```python
async def route_escalation(
    interaction: Dict,
    risk_score: float,
    confidence: float,
    session_name: str
) -> Dict:
    """
    Route escalation to appropriate target.

    Args:
        interaction: Permission prompt details
        risk_score: 0.0-1.0 (0=safe, 1=critical)
        confidence: 0.0-1.0 (our confidence in decision)
        session_name: Which session triggered this

    Returns:
        {
            'target': 'architect_manager' | 'wrapper_claude' | 'claude_code_high_level',
            'priority': 8-10,
            'task_id': int,
            'send_notification': bool
        }
    """

    # ROUTING MATRIX

    # Critical risk (>0.9) → Always architect_manager
    if risk_score > 0.9:
        return {
            'target': 'architect_manager',
            'priority': 10,
            'reason': f'CRITICAL: {interaction["operation"]} (risk={risk_score:.0%})'
        }

    # High risk (>0.7) → architect_manager
    if risk_score > 0.7:
        return {
            'target': 'architect_manager',
            'priority': 9,
            'reason': f'High risk operation: {interaction["operation"]}'
        }

    # Medium risk (0.4-0.7) → wrapper_claude (more flexible)
    if risk_score > 0.4:
        return {
            'target': 'wrapper_claude',
            'priority': 8,
            'reason': f'Medium risk: {interaction["operation"]} (confidence={confidence:.0%})'
        }

    # Low risk but low confidence (<0.5) → wrapper_claude (learning)
    if confidence < 0.5:
        return {
            'target': 'wrapper_claude',
            'priority': 7,
            'reason': f'Unknown pattern: {interaction["operation"]}'
        }

    # Should not reach here (Phase 1 should auto-approve)
    # Fallback: escalate to highest level
    return {
        'target': 'architect_manager',
        'priority': 5,
        'reason': 'Fallback escalation'
    }
```

---

## Component 2: Async Task Creation (Non-Blocking)

### File: `services/auto_confirm_escalation.py` - `create_escalation_task()`

```python
async def create_escalation_task(
    interaction: Dict,
    target_session: str,
    priority: int,
    reason: str
) -> int:
    """
    Create async task for manager review WITHOUT BLOCKING session.

    Returns: task_id (for tracking)
    """

    # 1. Create task in assigner queue
    task_id = self.assigner_db.add_prompt(
        content=self._format_escalation_request(interaction, reason),
        priority=priority,
        target_session=target_session,
        timeout_minutes=5,  # CRITICAL: 5 min max
        metadata={
            'type': 'permission_escalation',
            'interaction_id': interaction['id'],
            'original_operation': interaction['operation'],
            'original_scope': interaction['scope'],
            'risk_score': interaction.get('risk_score', 0.5),
            'confidence': interaction.get('confidence', 0.5)
        }
    )

    # 2. Update interaction status to HELD (not BLOCKED)
    self.update_interaction(interaction['id'], {
        'status': 'held',
        'escalation_task_id': task_id,
        'escalation_target': target_session,
        'escalation_reason': reason,
        'escalation_time': datetime.now(),
        'held_at': datetime.now()  # Track hold duration
    })

    # 3. Send async notification to target (non-blocking)
    asyncio.create_task(
        self._notify_target_session(target_session, task_id, interaction)
    )

    # 4. Start timeout watchdog (5 minutes max)
    asyncio.create_task(
        self._watch_escalation_timeout(task_id, interaction['id'])
    )

    logger.info(
        f"Escalation created: task={task_id}, target={target_session}, "
        f"interaction={interaction['id']}, reason={reason}"
    )

    return task_id
```

### Helper: Format Escalation Request

```python
def _format_escalation_request(self, interaction: Dict, reason: str) -> str:
    """Format human-readable escalation request for manager."""

    return f"""
PERMISSION ESCALATION REQUEST
══════════════════════════════════════════════════════════════════

OPERATION:      {interaction['operation']}
SCOPE:          {interaction['scope']}
SESSION:        {interaction.get('session', 'unknown')}
REASON:         {reason}

RISK LEVEL:     {self._format_risk(interaction.get('risk_score', 0.5))}
CONFIDENCE:     {interaction.get('confidence', 0.5):.0%}

CONTEXT:
  - File path: {interaction.get('file_path', 'N/A')}
  - Operation type: {interaction.get('operation_type', 'N/A')}
  - Session type: {interaction.get('session_type', 'N/A')}

REQUIRED ACTION:
1. Review the operation details above
2. Type: APPROVE or DENY
3. System will auto-timeout in 5 minutes

TIMEOUT BEHAVIOR:
- If APPROVE: Continue operation
- If DENY: Fail with error message
- If TIMEOUT: Auto-escalate to claude_code_high_level for decision

Do NOT block: Continue accepting other prompts while reviewing this.
═══════════════════════════════════════════════════════════════════
    """.strip()
```

### Helper: Notify Target Session

```python
async def _notify_target_session(
    self,
    target_session: str,
    task_id: int,
    interaction: Dict
) -> None:
    """Send notification to tmux session WITHOUT BLOCKING."""

    try:
        # Send message to tmux session (non-blocking)
        notification = f"🔔 Permission escalation #{task_id}: {interaction['operation']}"

        subprocess.Popen([
            'tmux', 'send-keys', '-t', target_session,
            notification, 'Enter'
        ])

        logger.debug(f"Notification sent to {target_session}")

    except Exception as e:
        logger.error(f"Failed to notify {target_session}: {e}")
        # Don't fail the escalation if notification fails
```

---

## Component 3: Held Status Management

### File: `services/auto_confirm_escalation.py` - `manage_held_status()`

**KEY CONCEPT**: Session is NOT BLOCKED. It's in HELD state:
- Can accept new prompts
- Current operation waits for approval
- No user intervention required

```python
class HeldStatusManager:
    """Manages held permissions during escalation."""

    async def can_continue_session(
        self,
        session_name: str,
        new_prompt: Dict
    ) -> bool:
        """
        Check if session can accept new prompt while in held state.

        YES: Session is in held state but it's for a different operation
        NO: Session is blocked on critical operation
        """

        held_interactions = self.db.query(
            f"""SELECT * FROM claude_interactions
               WHERE session='{session_name}' AND status='held'"""
        )

        # Can have multiple held interactions
        # Only blocked if >3 concurrent or one is CRITICAL
        if len(held_interactions) > 3:
            return False  # Too many held items

        critical_held = any(
            h['risk_score'] > 0.9 for h in held_interactions
        )

        if critical_held:
            return False  # Can't proceed with critical held

        return True  # Can continue working

    async def poll_held_status(
        self,
        interaction_id: int,
        poll_interval_seconds: int = 1
    ) -> str:
        """
        Poll for escalation decision.

        Returns: 'approved' | 'denied' | 'timed_out' | 'escalated_higher'
        """

        max_polls = 5 * 60  # 5 minutes (timeout)
        polls = 0

        while polls < max_polls:
            interaction = self.db.query_one(
                f"SELECT status FROM claude_interactions WHERE id={interaction_id}"
            )

            if interaction['status'] == 'approved':
                return 'approved'
            elif interaction['status'] == 'denied':
                return 'denied'
            elif interaction['status'] == 'escalated_higher':
                return 'escalated_higher'

            # Still held, wait and retry
            await asyncio.sleep(poll_interval_seconds)
            polls += 1

        # Timeout reached
        return 'timed_out'

    async def handle_escalation_response(
        self,
        interaction_id: int,
        decision: str,  # 'approve' or 'deny'
        manager_session: str
    ) -> None:
        """
        Manager sends decision back via tmux input.
        System processes and updates interaction status.
        """

        if decision.lower() == 'approve':
            self.db.update('claude_interactions',
                where=f'id={interaction_id}',
                values={
                    'status': 'approved',
                    'approved_by': manager_session,
                    'approved_at': datetime.now()
                }
            )
            logger.info(f"Interaction {interaction_id} approved by {manager_session}")

        elif decision.lower() == 'deny':
            self.db.update('claude_interactions',
                where=f'id={interaction_id}',
                values={
                    'status': 'denied',
                    'denied_by': manager_session,
                    'denied_at': datetime.now(),
                    'denial_reason': 'Manager denied escalation'
                }
            )
            logger.info(f"Interaction {interaction_id} denied by {manager_session}")
```

---

## Component 4: Timeout & Fallback Logic

### File: `services/auto_confirm_escalation.py` - `watch_escalation_timeout()`

```python
async def _watch_escalation_timeout(
    self,
    task_id: int,
    interaction_id: int,
    timeout_seconds: int = 300  # 5 minutes
) -> None:
    """
    Watch for escalation timeout.
    If no response after 5 min, escalate to higher level.
    """

    try:
        # Wait for timeout period
        await asyncio.sleep(timeout_seconds)

        # Check if still held
        interaction = self.db.query_one(
            f"SELECT status FROM claude_interactions WHERE id={interaction_id}"
        )

        if interaction['status'] != 'held':
            # Already resolved
            return

        # TIMEOUT: Escalate to highest level
        logger.warning(
            f"Escalation timeout for interaction {interaction_id}, "
            f"escalating to claude_code_high_level"
        )

        # Create new escalation task for high-level
        new_task_id = await self.create_escalation_task(
            interaction=interaction,
            target_session='claude_code_high_level',
            priority=10,
            reason='Escalation timeout - manager unavailable'
        )

        # Update interaction
        self.db.update('claude_interactions',
            where=f'id={interaction_id}',
            values={
                'escalation_target': 'claude_code_high_level',
                'escalation_task_id': new_task_id,
                'escalation_reason': 'Timeout - escalated to high-level',
                'escalation_count': interaction.get('escalation_count', 0) + 1
            }
        )

    except Exception as e:
        logger.error(f"Error in escalation timeout watchdog: {e}")
        # Don't fail, just log
```

---

## Component 5: Conditional Auto-Approve with Safeguards

### File: `services/auto_confirm_escalation.py` - `conditional_auto_approve()`

For operations that are slightly uncertain but low enough risk:

```python
async def conditional_auto_approve(
    self,
    interaction: Dict,
    confidence: float,
    risk: float
) -> Dict:
    """
    For medium-low risk operations with moderate confidence,
    auto-approve WITH SAFEGUARDS rather than blocking.
    """

    if risk > 0.4 or confidence < 0.6:
        # Too risky, don't use this path
        return {'action': 'escalate'}

    safeguards = {
        'sandbox': False,      # Run in isolated context?
        'rollback': False,     # Keep rollback data?
        'log_extra': False,    # Enhanced logging?
        'monitor': False       # Active monitoring?
    }

    # File edits in safe paths
    if (interaction['operation'] == 'file_edit' and
        interaction['scope'] in ['/tmp/', '.claude/', '.git/']):
        safeguards['log_extra'] = True
        safeguards['monitor'] = True
        return {
            'action': 'conditional_approve',
            'safeguards': safeguards,
            'reason': f'Safe path: {interaction["scope"]}'
        }

    # Git commits to feature branches (low risk)
    if (interaction['operation'] == 'git_commit' and
        '/feature/' in interaction['scope']):
        safeguards['log_extra'] = True
        return {
            'action': 'conditional_approve',
            'safeguards': safeguards,
            'reason': 'Feature branch commit (low risk)'
        }

    # Test execution (very low risk)
    if interaction['operation'] == 'test_execution':
        return {
            'action': 'conditional_approve',
            'safeguards': {'monitor': True},
            'reason': 'Test execution (low risk)'
        }

    # Default: escalate
    return {'action': 'escalate'}
```

---

## Component 6: Decision Caching & Learning

### File: `services/auto_confirm_escalation.py` - `CacheAndLearning`

```python
class DecisionCacheAndLearning:
    """
    Learn from decisions to improve future confidence.
    Reduce escalations for repeated operations.
    """

    def __init__(self, db):
        self.db = db
        self.cache = {}  # In-memory cache
        self.load_cache_from_db()

    def cache_decision(
        self,
        operation: str,
        scope: str,
        decision: str,  # 'auto_approved' | 'escalated' | 'denied'
        outcome: str = None  # 'success' | 'failed' | 'pending'
    ) -> None:
        """Remember this decision for future reference."""

        key = f"{operation}:{scope}"

        self.cache[key] = {
            'decision': decision,
            'outcome': outcome,
            'count': self.cache.get(key, {}).get('count', 0) + 1,
            'success_rate': self._calculate_success_rate(key, outcome),
            'last_at': datetime.now()
        }

        # Persist to DB
        self.db.upsert('decision_cache',
            where=f"operation='{operation}' AND scope='{scope}'",
            values=self.cache[key]
        )

    def get_cached_decision(self, operation: str, scope: str) -> Optional[Dict]:
        """Retrieve cached decision."""

        key = f"{operation}:{scope}"
        cached = self.cache.get(key)

        if cached and cached['count'] > 3 and cached['success_rate'] > 0.9:
            # High confidence in this pattern
            return {
                'use_cache': True,
                'cached_decision': cached['decision'],
                'confidence_boost': min(0.3, cached['count'] * 0.05)
            }

        return None

    def _calculate_success_rate(self, key: str, outcome: str) -> float:
        """Calculate success rate for cached decisions."""

        if key not in self.cache:
            return 0.0

        cached = self.cache[key]

        # Success if no failures recorded
        if outcome == 'success':
            cached['successes'] = cached.get('successes', 0) + 1
        elif outcome == 'failed':
            cached['failures'] = cached.get('failures', 0) + 1

        total = cached.get('successes', 0) + cached.get('failures', 0)
        if total == 0:
            return 1.0  # No data = assume success

        return cached.get('successes', 0) / total
```

---

## Component 7: Integration Testing Plan

### File: `tests/test_auto_confirm_phase2.py`

```python
import pytest
import asyncio
from services.auto_confirm_escalation import EscalationManager

class TestPhase2Escalation:
    """Test escalation system - CRITICAL for Phase 4."""

    @pytest.mark.asyncio
    async def test_escalation_routing_high_risk(self):
        """High risk ops route to architect_manager."""
        target = await self.manager.route_escalation(
            interaction={'operation': 'force_push', 'scope': 'main'},
            risk_score=0.95,
            confidence=0.8,
            session_name='dev_worker'
        )
        assert target['target'] == 'architect_manager'
        assert target['priority'] == 10

    @pytest.mark.asyncio
    async def test_escalation_non_blocking(self):
        """Session must NOT block during escalation."""
        # Create escalation
        task_id = await self.manager.create_escalation_task(
            interaction={'id': 1, 'operation': 'delete', 'scope': '/tmp/file'},
            target_session='architect_manager',
            priority=9,
            reason='High risk'
        )

        # Session should still accept new prompts
        can_continue = await self.manager.can_continue_session(
            'dev_worker', {'id': 2, 'content': 'new prompt'}
        )
        assert can_continue == True  # NOT BLOCKED

    @pytest.mark.asyncio
    async def test_escalation_timeout_fallback(self):
        """After 5 min timeout, escalate to higher level."""
        # Create escalation
        task_id = await self.manager.create_escalation_task(...)

        # Simulate timeout
        await asyncio.sleep(301)  # 5 min + 1 sec

        # Should be escalated to claude_code_high_level
        interaction = self.db.query_one(f"SELECT * FROM claude_interactions WHERE id=1")
        assert interaction['escalation_target'] == 'claude_code_high_level'

    @pytest.mark.asyncio
    async def test_held_status_multiple_operations(self):
        """Session can have multiple held operations."""
        # Create 3 held interactions
        for i in range(3):
            await self.manager.create_escalation_task(...)

        # Should still accept new prompts
        can_continue = await self.manager.can_continue_session('dev_worker', {})
        assert can_continue == True

    @pytest.mark.asyncio
    async def test_decision_caching_learning(self):
        """Repeated operations learn and reduce escalations."""
        operation = 'git_commit'
        scope = '/feature/auth'

        # First: escalate (unknown)
        decision1 = await self.manager.make_decision(operation, scope)
        assert decision1['action'] == 'escalate'

        # Manager approves
        await self.manager.cache_decision(operation, scope, 'auto_approved', 'success')

        # Second: should auto-approve (cached)
        decision2 = await self.manager.make_decision(operation, scope)
        assert decision2['action'] == 'auto_approve'
        assert decision2['confidence'] > 0.95

    @pytest.mark.asyncio
    async def test_response_time_under_load(self):
        """All decisions < 50ms latency."""
        import time

        start = time.time()
        for _ in range(100):
            await self.manager.route_escalation(...)
        elapsed = (time.time() - start) * 1000

        avg_latency = elapsed / 100
        assert avg_latency < 50, f"Latency too high: {avg_latency:.2f}ms"
```

---

## Database Schema (Phase 2 Additions)

```sql
-- Track held permissions
ALTER TABLE claude_interactions ADD COLUMN held_at TIMESTAMP;
ALTER TABLE claude_interactions ADD COLUMN escalation_count INTEGER DEFAULT 0;

-- Cache decisions for learning
CREATE TABLE decision_cache (
    operation TEXT NOT NULL,
    scope TEXT NOT NULL,
    decision TEXT,
    success_rate FLOAT DEFAULT 1.0,
    count INTEGER DEFAULT 1,
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    last_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (operation, scope)
);

-- Track escalation history
CREATE TABLE escalation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    from_target TEXT,
    to_target TEXT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interaction_id) REFERENCES claude_interactions(id)
);

-- Audit approvals/denials
CREATE TABLE escalation_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    decision TEXT,  # 'approved' | 'denied'
    decided_by TEXT,
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    FOREIGN KEY (interaction_id) REFERENCES claude_interactions(id)
);
```

---

## Success Metrics (MUST MEET ALL)

```
✅ Zero blocking sessions during escalation
✅ Escalation response time: < 5 minutes (timeout)
✅ Decision latency: < 50ms
✅ Fallback works if target unavailable
✅ Full audit trail of all escalations
✅ Learning reduces escalations by 50% after 100 ops
✅ No data loss or race conditions
✅ Works with all session types (worker, manager, codex)
✅ Tested under load (10 concurrent escalations)
```

---

## Implementation Order

1. **Escalation Routing Logic** (Component 1)
2. **Async Task Creation** (Component 2)
3. **Held Status Management** (Component 3)
4. **Timeout & Fallback** (Component 4)
5. **Conditional Auto-Approve** (Component 5)
6. **Decision Caching** (Component 6)
7. **Integration Tests** (Component 7)
8. **Load Testing** (Verify performance)
9. **Deployment** (Move to GAIA_HOME)

---

## Blockers & Dependencies

**Blocks**:
- Phase 4 (Claude sidecar)
- Assigner worker enhancement
- Interrupt prevention
- Internal diagnostic extension

**Depends On**:
- Phase 1 complete (AutoConfirmEngine, decision tree)
- Database schema from Phase 1
- GAIA config from Phase 1

---

## Critical Success Factors

1. **NO BLOCKING**: Session must NEVER wait for manual approval
2. **ASYNC ESCALATION**: Non-blocking task creation & notification
3. **FALLBACK**: If architect_manager doesn't respond, escalate higher
4. **AUDIT**: Track every decision with full context
5. **PERFORMANCE**: <50ms latency, <5% CPU overhead

---

**Ready for architect_manager to implement.**
**This is the gate for Phase 4.**

