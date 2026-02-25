# Auto-Confirm Intelligent Escalation System

**Status**: ARCHITECTURE PROPOSAL
**Priority**: CRITICAL
**Created**: 2026-02-21

## User Requirement

> "I don't want to have to manually intervene the auto confirm needs to either confirm or send a stuck session to an architect or a manager."

**Translation**: Auto-confirm must be **fully autonomous**. It should NEVER block waiting for manual user intervention. Instead:
1. **Auto-approve** when safe and low-risk
2. **Escalate to architect/manager** when uncertain or high-risk
3. **Never** leave a session stuck waiting for human action

## Current State vs. Desired State

### Current Flow ❌
```
Claude Session encounters permission prompt
    ↓
Sends to claude_interactions table
    ↓
Waits for manual user approval
    ↓
SESSION BLOCKS (⚠️ STUCK!)
    ↓
User has to manually review and approve
    ↓
Session resumes
```

### Desired Flow ✅
```
Claude Session encounters permission prompt
    ↓
Auto-Confirm Engine evaluates:
    ├─ Pattern match (known-safe operation)?
    │   └─ YES → Auto-approve, continue immediately
    │
    ├─ High-confidence pattern?
    │   └─ YES → Auto-approve, log action
    │
    ├─ Risky operation (delete, force-push)?
    │   └─ YES → Escalate to architect_manager
    │
    ├─ Provider mismatch/unusual?
    │   └─ YES → Escalate to wrapper_claude
    │
    └─ Default (unknown)?
        └─ Auto-approve with conditions (sandbox, rollback ready)
```

## Intelligent Auto-Confirm Decision Tree

```
┌─ Permission Prompt Received ─────────────────────────────┐
│                                                          │
├─→ [1] Extract operation details                        │
│   ├─ Operation type (edit, delete, git, shell, etc.)  │
│   ├─ File path or scope                                │
│   ├─ Risk level assessment                             │
│   └─ Session type (worker, manager, codex, etc.)      │
│                                                          │
├─→ [2] Check auto-approval patterns                     │
│   ├─ Exact match in approved_patterns table?          │
│   │   └─ YES → Auto-approve immediately ✓             │
│   │                                                     │
│   ├─ Matches safety rules?                             │
│   │   ├─ File edit in /tmp/? → AUTO-APPROVE           │
│   │   ├─ File read in /home? → AUTO-APPROVE           │
│   │   ├─ Git pull/fetch? → AUTO-APPROVE               │
│   │   ├─ Git commit to feature/*? → AUTO-APPROVE      │
│   │   ├─ Git push to main/master? → ESCALATE ⚠️       │
│   │   ├─ Force-push? → ESCALATE to architect ⛔       │
│   │   ├─ Delete operation? → ESCALATE ⛔               │
│   │   ├─ Shell exec (rm, dd, etc.)? → ESCALATE ⛔     │
│   │   └─ Install dependencies? → AUTO-APPROVE         │
│   │                                                     │
│   ├─ Check context match score                         │
│   │   ├─ Score > 0.8? (high confidence) → AUTO ✓      │
│   │   ├─ Score 0.5-0.8? (medium) → ESCALATE           │
│   │   └─ Score < 0.5? (low) → ESCALATE ⚠️             │
│   │                                                     │
│   ├─ Check time-based rules                            │
│   │   ├─ Night mode (9 PM - 6 AM)? → ESCALATE         │
│   │   ├─ During testing window? → AUTO-APPROVE        │
│   │   └─ During deployment? → HOLD (escalate)         │
│   │                                                     │
│   ├─ Check frequency/load                              │
│   │   ├─ >10 prompts queued? → AUTO-APPROVE (speed)  │
│   │   ├─ <3 prompts queued? → ESCALATE (careful)      │
│   │   └─ Unusual pattern? → ESCALATE                  │
│   │                                                     │
│   └─ Check session health                              │
│       ├─ Session stuck recently? → ESCALATE            │
│       ├─ Session failing? → ESCALATE                   │
│       ├─ Session doing well? → AUTO-APPROVE           │
│       └─ Unknown session? → ESCALATE                   │
│                                                          │
├─→ [3] Risk Assessment                                  │
│   ├─ SAFE (risk < 0.2) → AUTO-APPROVE ✓               │
│   ├─ LOW (risk 0.2-0.4) → AUTO-APPROVE                │
│   ├─ MEDIUM (risk 0.4-0.7) → ESCALATE to manager      │
│   ├─ HIGH (risk 0.7-0.9) → ESCALATE to architect      │
│   └─ CRITICAL (risk > 0.9) → HOLD + ALERT             │
│                                                          │
├─→ [4] Escalation Decision                              │
│   ├─ Auto-approve? (low risk, high confidence)         │
│   │   └─ ✓ Approve immediately                         │
│   │      ├─ Log to claude_interactions                 │
│   │      ├─ Set status = 'auto_approved'               │
│   │      ├─ Continue session immediately (NO BLOCK!)   │
│   │      └─ Send summary to architect (async)          │
│   │                                                     │
│   ├─ Escalate? (risky, uncertain, or policy blocked)   │
│   │   └─ Send to manager/architect for human review    │
│   │      ├─ Determine target:                          │
│   │      │   ├─ Delete/force-push → architect_manager │
│   │      │   ├─ Medium risk → wrapper_claude           │
│   │      │   ├─ Codex operations → architect_manager   │
│   │      │   └─ Unknown → architect_manager            │
│   │      ├─ Create async task:                         │
│   │      │   ├─ type: 'claude_permission_review'       │
│   │      │   ├─ priority: 8+ (urgent)                  │
│   │      │   ├─ timeout: 5 minutes                     │
│   │      │   └─ assign_to: target_session              │
│   │      ├─ Send notification to target (tmux)         │
│   │      ├─ Set session to HELD status (not blocked!)  │
│   │      │   ↓                                          │
│   │      ├─ Session can still accept other prompts     │
│   │      │   but current task waits for approval       │
│   │      └─ If timeout (5 min), auto-escalate to      │
│   │          claude_code_high_level for decision       │
│   │                                                     │
│   └─ Conditional auto-approve (with safeguards)?       │
│       ├─ Sandbox: Run in isolated environment          │
│       ├─ Rollback: Keep previous state for undo        │
│       ├─ Logging: Enhanced audit trail                 │
│       └─ Monitoring: Watch for side effects            │
│                                                          │
└─→ [5] Take Action & Log                                │
    ├─ Update claude_interactions status                  │
    ├─ Log decision to audit trail                        │
    ├─ Notify all relevant parties (async)               │
    ├─ Update session status                              │
    ├─ Continue or hold session appropriately             │
    └─ Return to assigner for next task                  │
```

## Safety Rule Matrix

| Operation | Worker | Manager | Architect | High-Level | Risk | Action |
|-----------|--------|---------|-----------|------------|------|--------|
| File edit in /tmp/ | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| File edit in project dir | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| File delete | ✗ | ~ | ✓ | ✓ | HIGH | Escalate |
| File read (public) | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| Git pull/fetch | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| Git commit to feature/* | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| Git push to feature/* | ~ | ✓ | ✓ | ✓ | MED | Conditional |
| Git commit to main | ✗ | ~ | ✓ | ✓ | HIGH | Escalate |
| Git push --force | ✗ | ✗ | ✓ | ✓ | CRITICAL | Escalate + Alert |
| Shell exec (safe) | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| Shell exec (rm) | ✗ | ~ | ✓ | ✓ | HIGH | Escalate |
| Shell exec (dd, mount) | ✗ | ✗ | ✓ | ✓ | CRITICAL | Escalate + Alert |
| Install dependencies | ✓ | ✓ | ✓ | ✓ | MED | Auto-approve |
| Test execution | ✓ | ✓ | ✓ | ✓ | LOW | Auto-approve |
| Deploy to prod | ✗ | ~ | ✓ | ✓ | CRITICAL | Escalate + Alert |

*Key: ✓ = Safe, ~ = Case-by-case, ✗ = Requires escalation*

## Implementation: Auto-Confirm Engine

### New Module: `services/auto_confirm_engine.py`

```python
class AutoConfirmEngine:
    """
    Intelligent auto-confirm decision system.
    Never blocks - always either approves or escalates.
    """

    def __init__(self):
        self.db = get_connection()
        self.assigner_db = AssignerDatabase()
        self.risk_calculator = RiskCalculator()
        self.pattern_matcher = PatternMatcher()

    async def evaluate_permission(self, interaction):
        """
        Evaluate a Claude permission prompt.
        Returns: {'action': 'approve'|'escalate', 'reason': str, 'target': str}
        """

        # Extract operation details
        op_type = interaction['operation']
        session = interaction['session']
        scope = interaction['scope']
        confidence = self.calculate_confidence(interaction)
        risk = self.risk_calculator.assess(interaction)

        # Check 1: Exact pattern match (highest confidence)
        if self.pattern_matcher.exact_match(interaction):
            return {
                'action': 'approve',
                'reason': 'Exact pattern match',
                'auto': True
            }

        # Check 2: Safety rules
        rule_result = self.check_safety_rules(op_type, scope, session)
        if rule_result['action'] == 'escalate':
            return rule_result

        # Check 3: Risk assessment
        if risk > 0.7:
            return await self.escalate(interaction, session, 'High risk')

        # Check 4: Confidence score
        if confidence > 0.8:
            return {
                'action': 'approve',
                'reason': f'High confidence ({confidence:.0%})',
                'auto': True
            }

        # Check 5: Context matching
        context_score = self.assigner_db.calculate_context_match_score(
            session, interaction.get('context', {})
        )
        if context_score > 0.8:
            return {
                'action': 'approve',
                'reason': f'Context match {context_score:.0%}',
                'auto': True
            }

        # Check 6: Time-based rules
        if self.is_night_mode():
            return await self.escalate(
                interaction, 'architect_manager',
                'Night mode - escalating for safety'
            )

        # Check 7: System load
        queue_depth = self.assigner_db.get_stats()['pending_count']
        if queue_depth > 10 and risk < 0.5:
            # Under load, be more aggressive with auto-approval
            return {
                'action': 'approve',
                'reason': f'Auto-approve under load (queue={queue_depth})',
                'auto': True
            }

        # Default: Escalate for human review
        return await self.escalate(
            interaction, session,
            f'Uncertain case (confidence={confidence:.0%}, risk={risk:.0%})'
        )

    async def escalate(self, interaction, target_session, reason):
        """
        Escalate permission to manager/architect.
        Never blocks the session.
        """

        # Determine escalation target if not specified
        if not target_session:
            target = self.determine_escalation_target(interaction)
        else:
            target = target_session

        # Create async task for manager/architect
        task_id = self.assigner_db.add_prompt(
            content=f"Permission review required:\n{interaction['operation']}\n\nScope: {interaction['scope']}\nReason: {reason}",
            priority=9,  # High priority
            target_session=target,
            timeout_minutes=5  # Must review within 5 minutes
        )

        # Update interaction status
        self.update_interaction(interaction['id'], {
            'status': 'held',
            'escalation_task': task_id,
            'escalation_target': target,
            'escalation_reason': reason,
            'escalation_time': datetime.now()
        })

        # Notify target session (async, non-blocking)
        await self.notify_target(target, {
            'type': 'permission_escalation',
            'interaction_id': interaction['id'],
            'task_id': task_id,
            'reason': reason
        })

        # Don't block the session - return held status
        return {
            'action': 'held',
            'reason': reason,
            'escalation_target': target,
            'task_id': task_id
        }

    def determine_escalation_target(self, interaction):
        """Determine best manager/architect for escalation"""

        op_type = interaction['operation']
        risk = interaction.get('risk', 0.5)

        # High-risk operations go to architect
        if risk > 0.7 or op_type in ['delete', 'force_push', 'deploy']:
            return 'architect_manager'

        # Medium-risk go to wrapper_claude
        if risk > 0.4:
            return 'wrapper_claude'

        # Unknown type goes to manager
        return 'architect_manager'

    def check_safety_rules(self, op_type, scope, session):
        """Check against safety rule matrix"""

        # Load safety rules from config
        rules = self.load_safety_rules()

        # Find applicable rule
        rule = self.find_matching_rule(op_type, scope)

        if rule['action'] == 'auto_approve':
            return {
                'action': 'approve',
                'reason': f'Safety rule: {rule["name"]}'
            }

        if rule['action'] == 'escalate':
            return {
                'action': 'escalate',
                'reason': f'Safety rule requires escalation: {rule["name"]}',
                'target': rule.get('escalate_to', 'architect_manager')
            }

        # Conditional - decide based on context
        return {
            'action': 'evaluate',
            'reason': 'Rule is conditional'
        }

    def calculate_confidence(self, interaction):
        """Calculate confidence in auto-approval (0.0 to 1.0)"""

        confidence = 0.5  # Base confidence

        # Increase confidence for known patterns
        if interaction.get('pattern_id'):
            confidence += 0.2

        # Increase for frequently approved operations
        if interaction.get('approval_history', {}).get('approve_rate', 0) > 0.9:
            confidence += 0.2

        # Increase for safe operations on watched paths
        if interaction.get('scope') in self.get_safe_paths():
            confidence += 0.15

        # Decrease for unusual contexts
        if interaction.get('context_similarity', 1.0) < 0.7:
            confidence -= 0.15

        # Decrease for session that's been slow/stuck
        if interaction.get('session') in self.get_problematic_sessions():
            confidence -= 0.2

        return max(0.0, min(1.0, confidence))
```

### Database Changes

```sql
-- Add status types
ALTER TABLE claude_interactions ADD COLUMN status TEXT DEFAULT 'pending';
-- Values: pending, approved, rejected, auto_approved, held, escalated

ALTER TABLE claude_interactions ADD COLUMN escalation_target TEXT;
ALTER TABLE claude_interactions ADD COLUMN escalation_reason TEXT;
ALTER TABLE claude_interactions ADD COLUMN escalation_time TIMESTAMP;
ALTER TABLE claude_interactions ADD COLUMN escalation_task_id INTEGER;
ALTER TABLE claude_interactions ADD COLUMN auto_approved BOOLEAN DEFAULT 0;
ALTER TABLE claude_interactions ADD COLUMN risk_score FLOAT DEFAULT 0.5;
ALTER TABLE claude_interactions ADD COLUMN confidence_score FLOAT DEFAULT 0.5;

-- Audit trail
CREATE TABLE permission_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    decision TEXT NOT NULL,  -- 'approved', 'rejected', 'escalated', 'timed_out'
    reason TEXT,
    auto_decision BOOLEAN DEFAULT 0,
    escalation_target TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interaction_id) REFERENCES claude_interactions(id)
);

-- Pattern definitions for auto-approval
CREATE TABLE approval_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    operation TEXT NOT NULL,
    scope_regex TEXT,
    session_type TEXT,
    risk_level TEXT,
    auto_approve BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0
);

-- Safe paths that don't require approval
CREATE TABLE safe_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    operation TEXT,  -- NULL = all operations safe
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO safe_paths (path) VALUES
    ('/tmp/'),
    ('/private/tmp/'),
    ('project_root/'),
    ('.claude/'),
    ('.git/');
```

## Configuration Addition

```yaml
# In ~/.gaia/config.json
auto_confirm:
  enabled: true
  intelligent_escalation: true  # NEW
  escalation_targets:           # NEW
    high_risk: "architect_manager"
    medium_risk: "wrapper_claude"
    low_risk: "auto_approve"

  safety_rules:                 # NEW
    - pattern: "file_edit_in_tmp"
      action: "auto_approve"
    - pattern: "git_delete_force"
      action: "escalate"
      target: "architect_manager"

  night_mode:                   # NEW
    enabled: true
    start_hour: 21
    end_hour: 6
    action: "escalate"

  escalation_timeout_minutes: 5 # NEW - how long to wait for manager
  fallback_escalation: "claude_code_high_level"  # If manager unavailable
```

## Flow Diagram: No Manual Intervention Required

```
Session encounters permission
         │
         ▼
Auto-Confirm Engine evaluates
         │
    ┌────┴────┐
    ▼         ▼
 AUTO-     ESCALATE
APPROVE      TO
(99%)      MANAGER
           (1%)
    │         │
    ├─────┬───┤
    ▼     ▼
SESSION  MANAGER
CONTINUES  REVIEWS
IMMEDIATELY  (in bg)
    │       │
    │       ▼
    │    Approve  → continues
    │       OR
    │    Deny     → fails with error
    │
    └─→ Next task
```

## Key Principles

1. **Zero Manual Intervention**: Auto-confirm MUST never require user action
2. **Fast Escalation**: Send to manager in <100ms, don't block session
3. **Smart Defaults**: Auto-approve safe operations by default
4. **Audit Everything**: Log all decisions for later review
5. **Graceful Degradation**: If manager unavailable, escalate higher
6. **Context Aware**: Use session history and patterns
7. **Risk-Based**: Scale automation with risk assessment
8. **Fast-Fail**: If escalation times out, auto-approve or auto-deny based on operation type

## Success Metrics

- ✅ 95%+ auto-approval rate for safe operations
- ✅ <100ms decision latency
- ✅ Zero manual user interventions needed
- ✅ 100% of high-risk operations escalated to manager
- ✅ <5 minute response time for escalated decisions
- ✅ Zero stuck sessions waiting for approval
- ✅ Full audit trail of all decisions

---

**Status**: Ready for implementation
**Priority**: CRITICAL - blocks Phase 3/4 completion
**Estimated Effort**: 20-30 hours
**Target**: Must be in place before heavy multi-worker load testing
