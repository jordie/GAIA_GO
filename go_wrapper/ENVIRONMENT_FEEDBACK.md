# Environment Isolation & Feedback Loop System

## Overview

The environment and feedback system provides:
- **Environment Isolation**: Agents work in defined environments with enforced constraints
- **Feedback Loop**: Track what's working and what isn't to continuously improve
- **SQLite Data Isolation**: Separate databases per environment with proper permissions
- **Learning from Outcomes**: Analyze success/failure patterns to optimize agent behavior

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Request                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  EnvironmentManager                                         │
│  - Load environment config                                  │
│  - Enforce working directory                                │
│  - Validate operations (write, delete, network, commands)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                ┌──────┴──────┐
                ▼             ▼
          ALLOWED         BLOCKED
                │             │
                │             └──> FeedbackTracker.RecordBlocked()
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│  ProcessWrapper                                             │
│  - Execute operation                                        │
│  - Capture outcome                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                ┌──────┴──────┐
                ▼             ▼
           SUCCESS        FAILURE
                │             │
                │             └──> FeedbackTracker.RecordFailure()
                │
                └──────────────> FeedbackTracker.RecordSuccess()
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ DatabaseManager │
                              │ (SQLite)        │
                              └─────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Analysis &      │
                              │ Pattern Learning│
                              └─────────────────┘
```

## Environments

Defined in `config/environments.json`:

### Dev Environment
- **Purpose**: Development and experimentation
- **Working Directory**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect`
- **Permissions**: Full write, delete, network access
- **Constraints**: Restricted system paths, denied dangerous commands
- **Use Case**: Active development and testing

### Staging Environment
- **Purpose**: Pre-production testing
- **Working Directory**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect-staging`
- **Permissions**: Write allowed, delete denied, network allowed
- **Constraints**: Allowed commands whitelist, more restricted paths
- **Use Case**: Integration testing before production deployment

### Prod Environment
- **Purpose**: Production monitoring (read-only)
- **Working Directory**: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect-prod`
- **Permissions**: No write, no delete, no network
- **Constraints**: Very limited command set (ls, cat, grep, git log)
- **Use Case**: Safe production introspection

### Sandbox Environment
- **Purpose**: Isolated experimentation
- **Working Directory**: `/tmp/architect_sandbox`
- **Permissions**: Full write/delete, no network
- **Constraints**: Cannot access /System, /Library, /Users
- **Use Case**: Testing untrusted code or experimental features

## Environment Configuration

```json
{
  "name": "dev",
  "description": "Development environment",
  "working_dir": "/path/to/workspace",
  "user": "username",
  "constraints": {
    "allow_write": true,
    "allow_delete": true,
    "allow_network": true,
    "max_file_size_mb": 100,
    "restricted_paths": ["/System", "/Library/System"],
    "allowed_commands": ["*"],
    "denied_commands": ["rm -rf /", "sudo rm"]
  },
  "feedback_config": {
    "track_outcomes": true,
    "auto_report_errors": true,
    "collect_metrics": true
  }
}
```

## Feedback Tracking

### What Gets Tracked

1. **Operation Outcomes**
   - Task type (tool_use, decision, operation, validation)
   - Action attempted
   - Success/failure status
   - Duration
   - Error messages (if failed)
   - Context data

2. **Constraint Violations**
   - Blocked operations
   - Reason for blocking
   - Risk level

3. **Success Patterns**
   - Pattern that matched
   - Frequency of success
   - Average execution time

### Feedback Data Structure

```go
type FeedbackOutcome struct {
    ID          string
    Timestamp   time.Time
    AgentName   string
    Environment string
    TaskType    string
    Action      string
    Success     bool
    Duration    time.Duration
    ErrorMsg    string
    Pattern     string
    RiskLevel   string
    WasBlocked  bool
    BlockReason string
}
```

### Feedback Statistics

```
Total Outcomes: 245
Success Rate: 87.35%

By Task Type:
  command_validation: 120
  path_validation: 80
  write_validation: 25
  delete_validation: 15
  network_validation: 5

Top Successful Patterns:
  command_check: 98 times (avg: 2ms)
  path_check: 76 times (avg: 1ms)

Top Errors:
  path access denied: 18 times
  command denied: 13 times

Blocked Operations:
  sudo rm -rf /: command denied
  /System/test: path access denied
```

## SQLite Data Isolation

### Database Manager

Creates environment-specific databases with proper permissions:

```
data/
├── dev/
│   ├── feedback.db         (0640 permissions)
│   ├── extraction.db       (0640 permissions)
│   └── agent_worker1.db    (0640 permissions)
├── staging/
│   ├── feedback.db
│   └── extraction.db
└── prod/
    ├── feedback.db
    └── extraction.db
```

### Database Schemas

**feedback.db**:
- `outcomes` - All operation outcomes
- `feedback_stats` - Aggregated statistics per agent

**extraction.db**:
- `extraction_events` - Extracted events from agent output
- `pattern_stats` - Pattern matching statistics

**agent_{name}.db**:
- `agent_sessions` - Session tracking
- `agent_actions` - Action history

### Permissions

| Resource | Permissions | Owner |
|----------|-------------|-------|
| Data directory | 0750 (rwxr-x---) | User running agent |
| Database files | 0640 (rw-r-----) | User running agent |
| Log files | 0640 (rw-r-----) | User running agent |

## Usage

### Starting Agent with Environment

```go
// Create wrapper with specific environment
wrapper := stream.NewProcessWrapperWithEnvironment(
    "worker1",           // agent name
    "logs/agents",       // logs directory
    "staging",           // environment
    "claude",           // command
    "--auto-approve",   // args...
)
```

### Validating Operations

```go
envManager := wrapper.GetEnvironmentManager()

// Validate command before execution
if err := envManager.ValidateCommand("git push"); err != nil {
    // Command blocked by environment constraints
    wrapper.RecordFeedback(stream.FeedbackOutcome{
        TaskType: "command_validation",
        Action: "git push",
        Success: false,
        WasBlocked: true,
        BlockReason: err.Error(),
    })
    return err
}
```

### Recording Feedback

```go
feedback := wrapper.GetFeedbackTracker()

// Record successful operation
feedback.RecordSuccess(
    "file_operation",           // task type
    "edit config.json",         // action
    "file_edit_pattern",        // pattern that matched
    time.Duration(150*time.Millisecond), // duration
    map[string]interface{}{     // context
        "file": "config.json",
        "lines_changed": 5,
    },
)

// Record failure
feedback.RecordFailure(
    "git_operation",
    "git push origin main",
    "authentication failed",
    time.Duration(2*time.Second),
    map[string]interface{}{
        "remote": "origin",
        "branch": "main",
    },
)
```

### Analyzing Feedback

```go
stats := feedback.GetStats()

// Get success rate
fmt.Printf("Success rate: %.2f%%\n", stats.SuccessRate)

// Get top errors
for _, err := range stats.TopErrors {
    fmt.Printf("Error: %s (%d times)\n", err.Error, err.Count)
}

// Get successful patterns
for _, pattern := range stats.TopSuccesses {
    fmt.Printf("Pattern: %s (%d times, avg: %v)\n",
        pattern.Pattern, pattern.Count, pattern.AvgDuration)
}
```

## Environment Enforcement

### Working Directory

Agents are automatically placed in their environment's working directory:

```go
envManager.EnforceWorkingDirectory()
// Changes to environment.WorkingDir
```

### Command Validation

```go
// In dev: allowed
envManager.ValidateCommand("go build ./...")

// In prod: blocked
envManager.ValidateCommand("rm file.txt")
// Error: command not allowed in prod environment
```

### Path Validation

```go
// In all environments: blocked
envManager.ValidatePath("/System/Library/test")
// Error: path access denied: /System/Library/test is restricted

// In dev: allowed
envManager.ValidatePath("/tmp/test.txt")
```

## Benefits

### 1. Safety

- Prevents accidental production modifications
- Blocks dangerous operations
- Enforces principle of least privilege
- Isolated data per environment

### 2. Learning

- Track what operations succeed/fail
- Identify problematic patterns
- Optimize based on historical data
- Continuous improvement loop

### 3. Debugging

- Full operation history
- Error frequency analysis
- Context preservation
- Reproducible failure scenarios

### 4. Auditing

- Who did what, when
- Environment-specific logs
- Immutable outcome records
- Compliance-ready tracking

## Testing

```bash
# Test environment enforcement
go run cmd/environment_demo/main.go dev

# Output:
# Environment loaded: dev
# Working directory: /Users/jgirmay/Desktop/gitrepo/pyWork/architect
#
# Testing Operations:
# 1. ✓ Working directory is correct
# 2. ✓ ls -lh - ALLOWED
#    ✗ sudo rm -rf / - BLOCKED: command denied
# 3. ✓ /tmp/test.txt - ACCESSIBLE
#    ✗ /System/Library - RESTRICTED: path access denied
# ...
# Success rate: 75.00%
```

## Integration with Extraction Layer

The feedback system integrates with the extraction layer:

```go
// Extracted events automatically create feedback outcomes
extractor.ProcessLine("⏺ Bash(ls -lh)")
// Creates extraction event AND feedback outcome

// Pattern success tracked in feedback
if pattern matches && execution succeeds {
    feedback.RecordSuccess(
        "tool_use",
        "bash: ls -lh",
        "bash_command_pattern",
        duration,
        extractionContext,
    )
}
```

## Future Enhancements

1. **ML-Based Recommendations**: Suggest patterns based on feedback data
2. **Auto-Tuning**: Adjust environment constraints based on outcomes
3. **Predictive Blocking**: Block operations likely to fail based on history
4. **Cross-Environment Learning**: Share successful patterns across environments
5. **User-Specific Environments**: Per-user environment configurations

## Files

```
go_wrapper/
├── config/
│   └── environments.json              # Environment definitions
├── stream/
│   ├── environment_manager.go         # Environment enforcement
│   └── feedback_tracker.go            # Outcome tracking
├── data/
│   └── database_manager.go            # SQLite isolation
├── cmd/
│   └── environment_demo/
│       └── main.go                    # Demo application
└── ENVIRONMENT_FEEDBACK.md            # This documentation
```

## Best Practices

1. **Always specify environment** when creating ProcessWrapper
2. **Validate before executing** - check constraints first
3. **Record all outcomes** - success and failure both matter
4. **Review feedback regularly** - analyze stats to improve
5. **Adjust constraints** based on actual usage patterns
6. **Use restrictive defaults** - allow only what's needed
7. **Separate production data** - never mix dev and prod databases

## License

Part of the Architect Dashboard project.
