# Phase 10: Auto-Confirm Patterns with AI Fallback - Quick Start

## What's New

The Claude auto-confirm patterns system enables Claude Code to work autonomously without blocking on permission confirmations. It uses:

1. **Learned Patterns** - Rules that Claude learns from successful operations
2. **AI Agent Fallback** - Claude API decides on unmatched requests
3. **Session Preferences** - Per-session approval settings

## 5-Minute Setup

### 1. Enable the Service

```go
import "github.com/jgirmay/GAIA_GO/pkg/services/claude_confirm"

// In your main.go or server initialization
aiConfig := claude_confirm.AIAgentConfig{
    Model:   "claude-opus-4.5",
    Enabled: true,
}
aiAgent := claude_confirm.NewAIAgent(db, aiConfig)
confirmationService := claude_confirm.NewConfirmationService(db, aiAgent)

// Register HTTP handlers
handlers := handlers.NewClaudeConfirmHandlers(confirmationService)
handlers.RegisterRoutes(router)
```

### 2. Enable for Specific Sessions

```bash
# Allow all operations (most permissive - development only)
curl -X POST http://localhost:8080/api/claude/confirm/preferences/basic_edu \
  -H "Content-Type: application/json" \
  -d '{"allow_all": true}'

# Use patterns and AI fallback (recommended)
curl -X POST http://localhost:8080/api/claude/confirm/preferences/rando_inspector \
  -H "Content-Type: application/json" \
  -d '{"allow_all": false, "use_ai_fallback": true}'
```

### 3. Create a Pattern (Optional)

```bash
curl -X POST http://localhost:8080/api/claude/confirm/patterns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project Read Access",
    "permission_type": "read",
    "resource_type": "file",
    "path_pattern": "/Users/jgirmay/Desktop/gitrepo/**",
    "context_keywords": ["read", "project", "source"],
    "decision_type": "approve",
    "confidence": 0.95,
    "enabled": true
  }'
```

### 4. Test It

```bash
curl -X POST http://localhost:8080/api/claude/confirm/request \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "basic_edu",
    "permission_type": "read",
    "resource_type": "file",
    "resource_path": "/Users/jgirmay/Desktop/gitrepo/project.py",
    "context": "Reading project source code"
  }'
```

Response:
```json
{
  "decision": "approve",
  "reason": "Pattern 'Read Project Files' matched with 95% confidence",
  "request_id": "uuid-...",
  "timestamp": "2026-02-25T..."
}
```

## Common Scenarios

### Scenario 1: Development (Allow All)

```bash
# Quick setup for development - no confirmations at all
POST /api/claude/confirm/preferences/dev_session
{
  "allow_all": true,
  "use_ai_fallback": false
}
```

**Result**: All operations approved instantly.

### Scenario 2: Educational Apps (rando_inspector, basic_edu)

```bash
# Use learned patterns + AI fallback for safety
POST /api/claude/confirm/preferences/basic_edu
{
  "allow_all": false,
  "use_ai_fallback": true
}
```

**Result**:
- Matching patterns → Instant approve/deny
- No pattern match → Ask Claude AI → Approve/deny based on risk
- If Claude unavailable → Default deny (safest)

### Scenario 3: Production (Patterns Only, No AI)

```bash
# Conservative: Only pre-approved patterns, no AI guessing
POST /api/claude/confirm/preferences/prod_session
{
  "allow_all": false,
  "use_ai_fallback": false
}
```

**Result**:
- Matching pattern → Approve/deny
- No match → Deny by default

## Decision Flow Diagram

```
New Permission Request
    ↓
Check Session "allow_all" preference
    ↓ (no)
Try Pattern Matching
    ├─ High confidence match? → APPROVE/DENY
    └─ No match or low confidence? → Continue
    ↓
Is AI Agent Enabled?
    ├─ YES → Ask Claude API
    │   └─ Get decision + reasoning → APPROVE/DENY
    └─ NO → Continue
    ↓
Default Policy
    └─ DENY (most secure)
```

## API Endpoints

### Process a Confirmation
```bash
POST /api/claude/confirm/request
{
  "session_id": "session_name",
  "permission_type": "read|write|execute|delete|network",
  "resource_type": "file|directory|command|api|database",
  "resource_path": "/path/to/resource",
  "context": "What Claude is trying to do"
}
```

### View Confirmation History
```bash
GET /api/claude/confirm/history/{sessionID}?limit=50
```

### View Session Statistics
```bash
GET /api/claude/confirm/stats/{sessionID}
```

### List All Patterns
```bash
GET /api/claude/confirm/patterns?enabled=true&limit=100
```

### Create a Pattern
```bash
POST /api/claude/confirm/patterns
{
  "name": "Pattern Name",
  "permission_type": "read",
  "resource_type": "file",
  "path_pattern": "/path/*",
  "context_keywords": ["keyword1", "keyword2"],
  "decision_type": "approve",
  "confidence": 0.9
}
```

### View Global Statistics
```bash
GET /api/claude/confirm/stats
```

## Files Created

### Core Service
- `pkg/services/claude_confirm/models.go` - Data models
- `pkg/services/claude_confirm/pattern_matcher.go` - Pattern matching
- `pkg/services/claude_confirm/ai_agent.go` - AI fallback
- `pkg/services/claude_confirm/confirmation_service.go` - Main service
- `pkg/services/claude_confirm/confirmation_service_test.go` - Unit tests (9 tests)

### HTTP API
- `pkg/http/handlers/claude_confirm_handlers.go` - Route handlers

### Database
- `migrations/010_claude_confirmation_system.sql` - Schema + sample patterns

### Documentation
- `pkg/services/claude_confirm/README.md` - Complete reference
- `PHASE10_QUICKSTART.md` - This file

## Testing

Run tests to verify everything works:

```bash
go test ./pkg/services/claude_confirm/... -v
```

Expected output:
```
PASS: TestPatternMatching
PASS: TestNoPatternMatch
PASS: TestConfirmationServiceWithPattern
PASS: TestSessionPreferences
PASS: TestAIAgentFallback
PASS: TestPatternCRUD
PASS: TestConfirmationHistory
PASS: TestSessionStats
PASS: TestGlobalStats

ok  	github.com/jgirmay/GAIA_GO/pkg/services/claude_confirm	0.208s
```

## Best Practices

### Do ✅
- Use patterns for common, safe operations (reading project files)
- Use AI fallback as a safety net for edge cases
- Monitor approval statistics to identify problematic patterns
- Create explicit deny patterns for dangerous operations
- Start restrictive (patterns only), relax over time based on data

### Don't ❌
- Use `allow_all: true` in production
- Create overly broad approval patterns (e.g., path: `/`)
- Disable AI fallback entirely (dangerous)
- Approve all network operations
- Ignore denial statistics

## Performance

- **Pattern Matching**: < 5ms (in-memory scoring)
- **AI Agent**: 100-500ms (Claude API round-trip)
- **Default Deny**: < 1ms (instant)

Caching the session preferences makes repeated requests very fast.

## Troubleshooting

### Claude Code Still Blocks on Confirmations
- Check: Is `use_ai_fallback: true`?
- Check: Are patterns being created and enabled?
- Check: Is AI agent configured with correct API key?

### Patterns Never Match
- Check: Path pattern uses correct glob syntax (`~/**/*.py`, not `~/*.py`)
- Check: Context keywords are present in the request context
- Check: Permission and resource types match exactly

### AI Agent Making Wrong Decisions
- Review the reasoning in the AI decision
- Create explicit patterns for edge cases
- Reduce confidence threshold temporarily for testing

## Next Steps

1. **Apply to Educational Sessions**
   ```bash
   POST /api/claude/confirm/preferences/basic_edu
   POST /api/claude/confirm/preferences/rando_inspector
   ```

2. **Create Custom Patterns**
   - Identify common operations
   - Create patterns for safe operations
   - Monitor success rate over time

3. **Monitor and Refine**
   - Check approval statistics: `GET /api/claude/confirm/stats`
   - Review pattern accuracy: `GET /api/claude/confirm/patterns/stats/{patternID}`
   - Adjust confidence thresholds based on data

## See Also

- **Complete Reference**: `pkg/services/claude_confirm/README.md`
- **API Documentation**: See handlers in `pkg/http/handlers/claude_confirm_handlers.go`
- **Phase 10 Implementation**: Latest commit in this branch
- **Phase 9 Release**: `STABLE_RELEASES.md`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `pkg/services/claude_confirm/README.md`
3. Check test cases in `confirmation_service_test.go` for examples
4. Review migration file for database schema details

---

**Status**: Phase 10 - Auto-confirm patterns system ✅ Complete
**Tests**: 9/9 passing ✅
**Documentation**: Complete ✅
**Ready for Integration**: Yes ✅
