# Pattern Tracking System

Automatically learns and adapts to LLM tool prompt patterns for autonomous agent operation.

## Overview

The pattern tracking system monitors permission prompts, errors, and other patterns across different LLM tools (Claude, Gemini, Ollama) and learns how to respond automatically. It tracks when patterns appear, detects changes/trends, and enables quick adaptation when tools update their interfaces.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Auto-Confirm Worker (auto_confirm_worker_v2.py)        │
│  • Monitors tmux sessions                              │
│  • Detects prompts                                     │
│  • Sends confirmations                                 │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Pattern Integration (pattern_integration.py)           │
│  • Detects known patterns                              │
│  • Identifies LLM tool type                            │
│  • Determines appropriate action                       │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Pattern Tracker (pattern_tracker.py)                   │
│  • Stores pattern definitions                          │
│  • Records occurrences                                 │
│  • Analyzes trends                                     │
│  • Detects changes                                     │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Database (/tmp/pattern_tracker.db)                     │
│  • patterns - Pattern definitions                      │
│  • occurrences - When patterns appear                  │
│  • trends - Hourly aggregates                          │
│  • pattern_changes - Detected changes                  │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

### patterns
- Pattern definitions with regex and actions
- Fields: pattern_type, pattern_name, pattern_regex, tool_name, action
- Example: `gemini_allow_once` → regex: `● 1\. Allow once` → action: `send_key:1`

### occurrences
- Records each time a pattern is detected
- Tracks session, matched text, action taken, success/failure
- Used for trend analysis

### trends
- Hourly aggregates of pattern occurrences
- Tracks occurrence count, success rate, response times
- Enables detecting changes in pattern behavior

### pattern_changes
- Alerts for significant changes
- Types: `pattern_disappeared`, `low_success_rate`, `new_pattern_detected`

## Pattern Types

### permission_prompt
Permission/confirmation prompts that need user approval.

**Examples:**
- Claude: "● 1. Allow once"
- Gemini: "● 1. Allow once"

**Actions:**
- `send_key:1` - Send "1" + Enter
- `send_key:2` - Send "2" + Enter

### error
Error messages that indicate problems.

**Examples:**
- Gemini API error: "models/gemini-pro is not found"

**Actions:**
- `alert:model_deprecated` - Alert about deprecated model

### status
Status indicators (not interactive prompts).

**Examples:**
- Claude: "accept edits on"

**Actions:**
- `skip` - Don't interact with this

## CLI Usage

### Initialize Patterns
```bash
python3 workers/pattern_tracker.py init
```

### View Statistics
```bash
python3 workers/pattern_tracker.py stats
```

Output:
```
============================================================
PATTERN TRACKER STATISTICS
============================================================

Total Patterns: 7
Active Patterns (last 24h): 0

Patterns by Tool:
  claude: 3
  gemini: 4

Recent Occurrences: 0
Success Rate: 0.0%
Pending Changes: 0
```

### Detect Changes
```bash
python3 workers/pattern_tracker.py changes
```

Detects:
- Patterns that haven't appeared in 24+ hours
- Patterns with declining success rates
- New patterns detected in last hour

### View Trends
```bash
python3 workers/pattern_tracker.py trends <pattern_id>
```

Shows hourly occurrence data, success rate over time.

### Export Patterns
```bash
python3 workers/pattern_tracker.py export
```

Exports all patterns to `patterns_export.json` for backup/analysis.

## API Endpoints

### GET /architecture/api/patterns/summary
Get pattern tracking summary.

**Response:**
```json
{
  "success": true,
  "total_patterns": 7,
  "active_patterns": 5,
  "by_tool": {
    "claude": 3,
    "gemini": 4
  },
  "recent_occurrences": 150,
  "success_rate": 98.5,
  "pending_changes": 0,
  "period_hours": 24
}
```

### GET /architecture/api/patterns/list
List all active patterns.

**Response:**
```json
{
  "success": true,
  "patterns": [
    {
      "id": 1,
      "pattern_type": "permission_prompt",
      "pattern_name": "claude_allow_once",
      "pattern_regex": "● 1\\. Allow once",
      "tool_name": "claude",
      "description": "Claude Code standard permission prompt",
      "action": "send_key:1",
      "occurrences": 120,
      "last_seen": 1707652800.0
    }
  ]
}
```

### GET /architecture/api/patterns/changes
Detect pattern changes.

**Response:**
```json
{
  "success": true,
  "changes": [
    {
      "type": "pattern_disappeared",
      "pattern_id": 3,
      "pattern_name": "old_gemini_prompt",
      "tool_name": "gemini",
      "description": "Pattern hasn't appeared in 48.2 hours"
    }
  ],
  "count": 1
}
```

### GET /architecture/api/patterns/<id>/trends?hours=24
Get trend data for specific pattern.

**Response:**
```json
{
  "success": true,
  "pattern_id": 1,
  "trends": [
    {
      "hour": "2026-02-11 08:00:00",
      "occurrences": 15,
      "successes": 15,
      "failures": 0,
      "success_rate": 1.0
    }
  ]
}
```

### GET /architecture/api/patterns/export
Export all patterns.

## Integration with Auto-Confirm

The auto-confirm worker can use pattern detection for smarter confirmations:

```python
from pattern_integration import PatternDetector, adaptive_confirm

detector = PatternDetector()
detector.load_patterns()

# When checking a session
session_output = capture_tmux_pane(session_name)
should_confirm, key, pattern = adaptive_confirm(
    session_name,
    session_output,
    detector
)

if should_confirm:
    send_key_to_session(session_name, key)

    # Record the occurrence
    detector.record_pattern_occurrence(
        pattern_id=pattern['pattern_id'],
        session_name=session_name,
        matched_text=pattern['matched_text'],
        action_taken=f"send_key:{key}",
        success=True
    )
```

## Adding New Patterns

### Manually via Database
```python
from pattern_tracker import PatternTracker

tracker = PatternTracker()
tracker.add_pattern(
    pattern_type='permission_prompt',
    pattern_name='new_tool_confirm',
    pattern_regex=r'Press Y to continue',
    tool_name='newtool',
    description='New tool confirmation prompt',
    action='send_key:Y'
)
```

### Automatically via Detection
The system can detect unknown patterns automatically:

```python
# When an unknown prompt format appears, it's logged
unknown = detect_unknown_patterns(session_output, session_name)
# ⚠️  Unknown pattern detected in dev-agent-1: Press Y to continue
```

These can be reviewed and added as new patterns.

## Adaptation Workflow

1. **Initial State**: Default patterns for Claude and Gemini
2. **Detection**: System monitors sessions and detects patterns
3. **Recording**: Each occurrence is recorded with timestamp
4. **Trend Analysis**: Hourly aggregates show pattern frequency
5. **Change Detection**: System detects when patterns stop appearing
6. **Alerting**: Changes trigger alerts for human review
7. **Adaptation**: New patterns can be added, old ones deactivated

## Use Cases

### Tool Version Updates
When Gemini updates and changes prompt format:
1. Old pattern stops appearing → detected as "pattern_disappeared"
2. New format appears → detected as "unknown pattern"
3. Admin reviews and adds new pattern
4. Auto-confirm adapts automatically

### Success Rate Monitoring
When a pattern's success rate drops:
1. Trend analysis detects declining success rate
2. Alert generated: "low_success_rate"
3. Admin investigates (tool changed? regex needs update?)
4. Pattern updated with new regex or action

### Cross-Tool Learning
When adding a new LLM tool:
1. Add basic patterns for the tool
2. System learns which patterns actually appear
3. Refine patterns based on occurrence data
4. Remove patterns that never appear

## Benefits

### Autonomous Adaptation
- System learns from experience
- Adapts to tool updates automatically
- No manual intervention for known patterns

### Quick Response to Changes
- Detects changes within 1 hour
- Alerts human when action needed
- Historical data helps understand trends

### Multi-Tool Support
- Patterns specific to each tool
- Generic patterns work across tools
- Easy to add new tools

### Data-Driven Decisions
- Know which patterns appear most
- Track success rates over time
- Identify unused patterns

## Future Enhancements

### Machine Learning
- Use ML to detect similar patterns
- Predict which action to take
- Auto-generate regex from examples

### Cross-Session Learning
- Share patterns across deployments
- Crowdsource pattern updates
- Version control for patterns

### Proactive Alerts
- Predict when tools will update based on patterns
- Alert before patterns stop working
- Suggest pattern updates

## Maintenance

### Regular Tasks

**Daily:**
- Review pending changes: `python3 workers/pattern_tracker.py changes`
- Check success rates in stats

**Weekly:**
- Export patterns for backup
- Review unknown pattern logs
- Update patterns if needed

**Monthly:**
- Analyze long-term trends
- Clean up unused patterns
- Update pattern confidence thresholds

### Troubleshooting

**Pattern not detecting:**
1. Check regex syntax
2. Verify tool name matches session
3. Test regex against actual output
4. Check pattern is active

**Low success rate:**
1. Review actual vs expected behavior
2. Check if prompt format changed
3. Update regex or action
4. Verify timing/delays aren't causing issues

**Database growth:**
- Occurrences table grows over time
- Consider archiving old data (>90 days)
- Trend aggregates reduce storage needs

## Files

```
workers/
├── pattern_tracker.py         # Core pattern tracking
├── pattern_integration.py     # Integration with auto-confirm
└── auto_confirm_worker_v2.py  # Auto-confirm worker

/tmp/
└── pattern_tracker.db         # Pattern database
```

## Dashboard Integration

The Architecture Dashboard includes a Pattern Tracking panel showing:
- Total patterns by tool
- Recent occurrences and success rate
- Pattern changes/alerts
- Trend charts for each pattern
- Unknown pattern detection log

Access at: https://localhost:5051/architecture/ → Patterns panel
