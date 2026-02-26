# Claude Confirmation System with Auto-Approval Patterns and AI Fallback

## Overview

The Claude Confirmation System provides intelligent, automated approval of Claude Code file operations using learned patterns and an AI agent fallback mechanism. This prevents Claude Code from blocking on every confirmation prompt while maintaining security.

## Architecture

```
Confirmation Request
    ↓
┌─────────────────────────────────────────┐
│ Check Session Allow-All Preference      │
│ (fastest path - pre-approval)           │
└────────────┬────────────────────────────┘
             ↓ (no)
┌─────────────────────────────────────────┐
│ Pattern Matching (Learned Patterns)     │
│ • Path pattern matching                 │
│ • Permission type matching              │
│ • Context keyword matching              │
│ • Confidence scoring (0-1.0)            │
└────────────┬────────────────────────────┘
             ↓ (no match or low confidence)
┌─────────────────────────────────────────┐
│ AI Agent Fallback (Claude API)          │
│ • Send to Claude for decision           │
│ • Considers matched patterns            │
│ • Provides reasoning for decision       │
│ • Tracks confidence and cost            │
└────────────┬────────────────────────────┘
             ↓ (disabled or error)
┌─────────────────────────────────────────┐
│ Default Deny                            │
│ (most secure fallback)                  │
└─────────────────────────────────────────┘
```

## Key Components

### 1. Models (models.go)
- **ConfirmationRequest**: Represents a permission request from Claude Code
- **ApprovalPattern**: Learned patterns for automatic approval
- **AIAgentDecision**: Decisions made by the AI agent fallback
- **SessionApprovalPreference**: Per-session approval settings

### 2. Pattern Matcher (pattern_matcher.go)
Matches incoming requests against learned patterns using multi-factor scoring:

**Scoring Formula (0-1.0):**
- Permission Type Match: 40% weight
- Resource Type Match: 30% weight
- Path Pattern Match: 20% weight
- Context Keywords Match: 10% weight

**Confidence Threshold:** 50% minimum match confidence required

### 3. AI Agent (ai_agent.go)
Provides intelligent fallback decisions using Claude API:

**Decision Heuristics:**
- **Read Operations**: Generally approved (0.9 confidence)
- **Write Operations**: Approved for project directories only (0.7-0.8 confidence)
- **Execute Operations**: Approved for test/build commands (0.7 confidence)
- **Delete Operations**: Denied by default (0.95 confidence)
- **Network Operations**: Denied by default (0.95 confidence)

**Integration Points:**
- Considers matched patterns in decision
- Provides reasoning for each decision
- Tracks cost and token usage
- Supports Claude API integration (mock implementation included)

### 4. Confirmation Service (confirmation_service.go)
Orchestrates the entire workflow:

```go
service := claude_confirm.NewConfirmationService(db, aiAgent)
decision, reason, err := service.ProcessConfirmation(ctx, &request)
```

## Usage Guide

### Basic Usage

```go
// Create a confirmation request
req := &claude_confirm.ConfirmationRequest{
    SessionID:      "basic_edu",
    PermissionType: "read",
    ResourceType:   "file",
    ResourcePath:   "/data/project/main.py",
    Context:        "Reading project source code",
}

// Process the request
decision, reason, err := service.ProcessConfirmation(ctx, req)
if decision == claude_confirm.DecisionApprove {
    // Allow the operation
} else {
    // Block the operation
}
```

### Creating Approval Patterns

```go
// Define a pattern
pattern := &claude_confirm.ApprovalPattern{
    Name:           "Read Python Files",
    Description:    "Allow reading .py files in project",
    PermissionType: "read",
    ResourceType:   "file",
    PathPattern:    "~/**/*.py",
    ContextKeywords: []string{"read", "python", "source"},
    DecisionType:   "approve",
    Confidence:     0.90,
}

// Create it
if err := service.CreatePattern(ctx, pattern); err != nil {
    log.Fatal(err)
}
```

### Setting Session Preferences

```go
// Enable pre-approval for a session
pref := &claude_confirm.SessionApprovalPreference{
    SessionID:      "basic_edu",
    AllowAll:       false,
    UseAIFallback:  true,
}

service.SetSessionPreference(ctx, pref)
```

### Full Pre-Approval (Skip All Checks)

```go
// Dangerous but useful for trusted sessions during development
pref := &claude_confirm.SessionApprovalPreference{
    SessionID: "my_dev_session",
    AllowAll:  true,  // Skip all checks
}

service.SetSessionPreference(ctx, pref)
```

## HTTP API Endpoints

### Confirmation Requests
```bash
# Process a new confirmation request
POST /api/claude/confirm/request
{
  "session_id": "basic_edu",
  "permission_type": "read",
  "resource_type": "file",
  "resource_path": "/data/project/main.py",
  "context": "Reading source code"
}

# Get confirmation history
GET /api/claude/confirm/history/{sessionID}?limit=50

# Get session statistics
GET /api/claude/confirm/stats/{sessionID}
```

### Pattern Management
```bash
# List all patterns
GET /api/claude/confirm/patterns?enabled=true&limit=100

# Create a pattern
POST /api/claude/confirm/patterns
{
  "name": "Read Project Files",
  "permission_type": "read",
  "resource_type": "file",
  "path_pattern": "/data/*",
  "context_keywords": ["read", "project"],
  "decision_type": "approve",
  "confidence": 0.95
}

# Update a pattern
PUT /api/claude/confirm/patterns/{patternID}
{
  "enabled": false,
  "confidence": 0.85
}

# Delete a pattern
DELETE /api/claude/confirm/patterns/{patternID}

# Get pattern statistics
GET /api/claude/confirm/patterns/stats/{patternID}
```

### Session Preferences
```bash
# Get session preferences
GET /api/claude/confirm/preferences/{sessionID}

# Set session preferences
POST /api/claude/confirm/preferences/{sessionID}
{
  "allow_all": false,
  "use_ai_fallback": true,
  "pattern_ids": ["pattern-uuid-1", "pattern-uuid-2"]
}
```

### Global Statistics
```bash
# Get global confirmation statistics
GET /api/claude/confirm/stats

# Response includes:
# - Total confirmations
# - Approval rate
# - Pattern performance
# - AI agent statistics
```

## Decision Flow Examples

### Example 1: Pattern Match - Reading Project File

```
Request: Read ~/projects/myapp/main.py
         Context: "Reading source code"

↓ Session Preference: No allow-all

↓ Pattern Matching:
  • Pattern: "Read Project Files"
  • Path matches: ~/projects/* ✓
  • Permission matches: read ✓
  • Score: 0.95 (exceeds 50% threshold)
  • Pattern history: 48/50 successful (96% accuracy)

Result: APPROVE (via pattern)
Reason: "Pattern 'Read Project Files' matched with 95% confidence"
```

### Example 2: No Pattern Match - AI Agent Decides

```
Request: Execute custom command
         Context: "Running analysis script"

↓ No matching pattern

↓ AI Agent Decision:
  • Permission: execute (cautious)
  • Context: "analysis" (not test/build)
  • Risk level: medium
  • Claude decision: DENY
  • Confidence: 0.85

Result: DENY
Reason: "Execute operations are restricted unless explicitly for testing"
```

### Example 3: Session Pre-Approval

```
Request: Any operation from "dev_session"

↓ Session Preference Check:
  • allow_all = true

Result: APPROVE (instant)
Reason: "Approved by session allow-all preference"
```

## Pattern Learning

Patterns improve over time based on outcomes:

```go
// Record successful pattern use
patternMatcher.RecordPatternUse(ctx, patternID, true)

// Update pattern statistics
// Pattern.SuccessCount++

// Accuracy = SuccessCount / (SuccessCount + FailureCount)
// Patterns with >90% accuracy are promoted
```

## AI Agent Cost Tracking

The system tracks Claude API usage:

```go
decision := &claude_confirm.AIAgentDecision{
    Decision:      "approve",
    Confidence:    0.85,
    TokensUsed:    1200,
    CostUSD:       0.0012,  // Calculated from tokens
    ResponseTime:  145,     // milliseconds
}
```

## Security Considerations

### Denial Patterns (High Confidence)
```
- Delete operations: 95% deny confidence
- Network operations: 95% deny confidence
- System directory writes: 95% deny confidence
```

### Approval Patterns (High Confidence)
```
- Read project files: 95% approve confidence
- Read home directory: 85% approve confidence
- Test/build execution: 80% approve confidence
```

### AI Agent Safeguards
1. Conservative by default (deny if uncertain)
2. High confidence threshold for approvals
3. Explicit risk assessment for each decision
4. Reasoning required for all decisions
5. Cost tracking to detect API issues

## Configuration

### Enable AI Agent
```go
config := claude_confirm.AIAgentConfig{
    Model:           "claude-opus-4.5",
    MaxTokens:       2000,
    DecisionTimeout: 10 * time.Second,
    Enabled:         true,
}
aiAgent := claude_confirm.NewAIAgent(db, config)
```

### Disable AI Agent (Safer)
```go
config := claude_confirm.AIAgentConfig{
    Enabled: false,  // All unmatched requests denied
}
```

## Monitoring & Analytics

### Key Metrics
- **Approval Rate**: % of requests approved vs denied
- **Pattern Accuracy**: % of pattern-based decisions that were correct
- **AI Confidence**: Average confidence scores from AI agent
- **Response Time**: Average milliseconds per decision
- **Cost**: Total Claude API cost for AI decisions

### Dashboard Queries
```bash
# Top performing patterns
GET /api/claude/confirm/patterns?limit=5

# Session approval statistics
GET /api/claude/confirm/stats/basic_edu

# Global system health
GET /api/claude/confirm/stats
```

## Troubleshooting

### Q: Claude Code is still blocking on every confirmation
A: Check that:
1. Session preference has `use_ai_fallback: true`
2. AI agent is enabled (`config.Enabled: true`)
3. Patterns are being matched (check `/patterns/stats`)
4. Claude API key is configured

### Q: Patterns never match
A: Review:
1. Path patterns use correct glob syntax (wildcards, etc.)
2. Context keywords are reasonable substrings
3. Pattern threshold (currently 50%) matches use case
4. Enable logging to see scoring details

### Q: AI agent is making wrong decisions
A: Consider:
1. Reducing confidence threshold temporarily
2. Creating explicit patterns for edge cases
3. Checking risk assessment logic
4. Reviewing decision reasoning in logs

## Future Enhancements

1. **Machine Learning**: Learn from user feedback on decisions
2. **Collaborative Learning**: Share patterns across teams
3. **Audit Trail**: Complete audit log of all operations
4. **Custom Rules**: User-defined decision logic
5. **Real-time Monitoring**: Live decision dashboard
6. **Cost Optimization**: Cache decisions, reduce API calls
7. **Compliance**: Export approval history for audits

## Related Files

- `models.go` - Data models
- `pattern_matcher.go` - Pattern matching logic
- `ai_agent.go` - AI fallback implementation
- `confirmation_service.go` - Main service
- `handlers.go` - HTTP endpoints
- `migrations/010_*.sql` - Database schema

## See Also

- STABLE_RELEASES.md - Version and release information
- VERSION - Current release notes
- pkg/http/handlers/claude_confirm_handlers.go - HTTP handlers
