## Environment Setup & Configuration Management

## Overview

The environment setup system **automatically initializes and maintains isolated execution environments** for agents. Each environment has its own working directory, databases, configuration, and constraints. The system handles:

1. **Automatic Environment Setup** - Creates directories, databases, and config files
2. **Dynamic Configuration Updates** - Modify constraints and settings on the fly
3. **Change Broadcasting** - Notify all agents when environments change
4. **Status Tracking** - Monitor which agents are using which environments

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Wrapper Initialization                                     │
│  - Agent starts with environment name (dev/staging/prod)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Environment Manager Loads Config                           │
│  - Reads config/environments.json                           │
│  - Selects environment by name                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Environment Setup Initializes                              │
│  1. Create working directory                                │
│  2. Create subdirectories (data, logs, config, tmp)         │
│  3. Initialize databases with proper permissions            │
│  4. Setup environment variables                             │
│  5. Create .architect_env file                              │
│  6. Update environment status                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent Runs in Isolated Environment                         │
│  - Working directory enforced                               │
│  - Constraints validated on every operation                 │
│  - Feedback tracked to environment-specific database        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Config Updater Manages Changes                             │
│  - Update constraints dynamically                           │
│  - Save changes to config file                              │
│  - Log all changes with reason and timestamp                │
│  - Broadcast changes to active agents                       │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Environment Setup (`stream/environment_setup.go`)

Automatically initializes a complete environment for an agent.

**Responsibilities:**
- Create working directory with proper permissions (0750)
- Create required subdirectories (data, logs, config, tmp)
- Initialize environment-specific databases (0640 permissions)
- Set up environment variables
- Create `.architect_env` file with configuration
- Update environment status tracking
- Cleanup agent from status when done

**Key Methods:**
```go
setup := NewEnvironmentSetup(environment, agentName)

// Initialize complete environment
if err := setup.Initialize(); err != nil {
    // Handle error
}

// Get current status
status, err := setup.GetStatus()

// Cleanup on shutdown
defer setup.Cleanup()
```

### 2. Config Updater (`stream/environment_config_updater.go`)

Manages dynamic configuration updates and change broadcasting.

**Responsibilities:**
- Update environment constraints
- Add/remove restricted paths and denied commands
- Update feedback configuration
- Save changes to config file (with backup)
- Log all changes with timestamp and reason
- Broadcast changes to active agents
- Track change history

**Key Methods:**
```go
updater, err := NewEnvironmentConfigUpdater("config/environments.json")

// Update constraint
updater.UpdateConstraint("dev", "max_file_size_mb", 150, "admin", "Increase limit")

// Add restricted path
updater.AddRestrictedPath("prod", "/sensitive", "admin", "Protect data")

// Add denied command
updater.AddDeniedCommand("staging", "reboot", "admin", "Prevent reboots")

// Update feedback config
updater.UpdateFeedbackConfig("dev", "track_outcomes", true, "admin", "Enable tracking")

// Get recent changes
changes := updater.GetRecentChanges("dev", 10)

// Broadcast change to agents
agents, _ := updater.GetActiveAgents("dev")
updater.BroadcastChange(change, agents)
```

### 3. Environment Status

Tracks the state of each environment and which agents are using it.

**Status Fields:**
- `Name` - Environment name
- `Status` - ready, initializing, error
- `ActiveAgents` - List of agents currently using the environment
- `LastUpdated` - When status was last updated
- `WorkingDirSize` - Size of working directory in bytes
- `DatabasesReady` - Whether databases are initialized
- `Metadata` - Additional custom metadata

**Status File Location:**
```
<working_dir>/data/status/<environment>_status.json
```

**Example Status:**
```json
{
  "name": "dev",
  "status": "ready",
  "active_agents": ["agent1", "agent2"],
  "last_updated": "2026-02-09T18:00:00Z",
  "working_dir_size_bytes": 52428800,
  "databases_ready": true,
  "metadata": {}
}
```

## Directory Structure

When an environment is initialized, the following structure is created:

```
<working_dir>/
├── .architect_env              # Environment variables file
├── data/
│   ├── feedback/               # Feedback tracking databases
│   │   └── <env>_feedback.db
│   ├── patterns/               # Pattern learning databases
│   │   └── <env>_patterns.db
│   ├── training/               # Training data databases
│   │   └── <env>_training.db
│   ├── extraction/             # Extraction event databases
│   │   └── <env>_extraction.db
│   └── status/                 # Environment status files
│       └── <env>_status.json
├── logs/
│   └── agents/                 # Agent log files
│       ├── <agent>-stdout.log
│       └── <agent>-stderr.log
├── config/                     # Environment-specific configs
└── tmp/                        # Temporary files
```

## Permissions

All files and directories created with secure permissions:

| Type | Permissions | Description |
|------|-------------|-------------|
| Directories | 0750 | Owner: rwx, Group: rx, Others: none |
| Databases | 0640 | Owner: rw, Group: r, Others: none |
| Config files | 0640 | Owner: rw, Group: r, Others: none |
| Log files | 0640 | Owner: rw, Group: r, Others: none |

## Environment Variables

The setup automatically configures these environment variables:

| Variable | Description |
|----------|-------------|
| `ARCHITECT_ENV` | Environment name (dev, staging, prod, sandbox) |
| `ARCHITECT_AGENT` | Agent name |
| `ARCHITECT_WORKING_DIR` | Working directory path |
| `ARCHITECT_DATA_DIR` | Data directory path |
| `ARCHITECT_LOGS_DIR` | Logs directory path |
| `ARCHITECT_CONFIG_DIR` | Config directory path |
| `ARCHITECT_ALLOW_WRITE` | Write operations allowed (true/false) |
| `ARCHITECT_ALLOW_DELETE` | Delete operations allowed (true/false) |
| `ARCHITECT_ALLOW_NETWORK` | Network operations allowed (true/false) |
| `ARCHITECT_MAX_FILE_SIZE_MB` | Max file size in MB |
| `ARCHITECT_TRACK_OUTCOMES` | Feedback tracking enabled (true/false) |
| `ARCHITECT_AUTO_REPORT_ERRORS` | Auto error reporting enabled (true/false) |
| `ARCHITECT_COLLECT_METRICS` | Metrics collection enabled (true/false) |

## Configuration Changes

### Change Log Format

All configuration changes are logged to `config/environment_changes.jsonl`:

```json
{
  "timestamp": "2026-02-09T18:00:00Z",
  "environment": "dev",
  "changed_by": "admin",
  "change_type": "constraint",
  "field": "max_file_size_mb",
  "old_value": 100,
  "new_value": 150,
  "reason": "Increase limit for large datasets",
  "broadcast_to": ["agent1", "agent2"],
  "acknowledged_by": []
}
```

### Change Types

| Type | Description | Fields |
|------|-------------|--------|
| `constraint` | Constraint modifications | allow_write, allow_delete, allow_network, max_file_size_mb, restricted_paths, denied_commands |
| `config` | Feedback config changes | track_outcomes, auto_report_errors, collect_metrics |
| `metadata` | Environment metadata | Any custom field |

## Broadcasting Changes

When configuration changes, the system can notify all active agents:

1. **Get Active Agents**: Query environment status to find active agents
2. **Create Notification**: Prepare change notification
3. **Broadcast**: Write notification to each agent's notification file
4. **Agent Reads**: Agents read their notification files periodically

**Notification File Location:**
```
config/notifications/<agent>_notifications.jsonl
```

**Notification Format:**
```json
{
  "timestamp": "2026-02-09T18:00:00Z",
  "environment": "dev",
  "change_type": "constraint",
  "field": "max_file_size_mb",
  "old_value": 100,
  "new_value": 150,
  "reason": "Increase limit",
  "broadcast_to": ["agent1", "agent2"]
}
```

## Integration with ProcessWrapper

The ProcessWrapper automatically sets up environments on initialization:

```go
// In stream/process.go
func NewProcessWrapperWithEnvironment(agentName, logsDir, environment string, command string, args ...string) *ProcessWrapper {
    // ... create wrapper ...

    // Initialize environment manager
    envManager, err := NewEnvironmentManager("config/environments.json", environment)
    if err == nil {
        // Automatically setup environment
        envSetup := NewEnvironmentSetup(envManager.GetEnvironment(), agentName)
        if err := envSetup.Initialize(); err != nil {
            fmt.Printf("[Wrapper] Warning: Environment setup failed: %v\n", err)
        }

        // Enforce working directory
        envManager.EnforceWorkingDirectory()
    }

    return pw
}
```

## Usage Examples

### Example 1: Initialize Environment

```go
package main

import "architect/go_wrapper/stream"

func main() {
    // Load environment config
    config, _ := stream.LoadEnvironmentConfig("config/environments.json")

    // Get dev environment
    devEnv := config.Environments[0]

    // Create setup for agent
    setup := stream.NewEnvironmentSetup(&devEnv, "my_agent")

    // Initialize environment
    if err := setup.Initialize(); err != nil {
        panic(err)
    }

    // Environment is ready to use
    // Cleanup when done
    defer setup.Cleanup()
}
```

### Example 2: Update Configuration

```go
package main

import "architect/go_wrapper/stream"

func main() {
    // Create config updater
    updater, _ := stream.NewEnvironmentConfigUpdater("config/environments.json")

    // Increase file size limit
    updater.UpdateConstraint("dev", "max_file_size_mb", 200, "admin",
        "Support larger datasets")

    // Add restricted path
    updater.AddRestrictedPath("dev", "/tmp/sensitive", "admin",
        "Protect sensitive files")

    // Enable metrics collection
    updater.UpdateFeedbackConfig("dev", "collect_metrics", true, "admin",
        "Enable performance tracking")
}
```

### Example 3: Broadcast Changes to Agents

```go
package main

import "architect/go_wrapper/stream"

func main() {
    updater, _ := stream.NewEnvironmentConfigUpdater("config/environments.json")

    // Get active agents
    agents, _ := updater.GetActiveAgents("dev")

    // Create change notification
    change := stream.EnvironmentChange{
        Environment: "dev",
        ChangedBy:   "admin",
        ChangeType:  "constraint",
        Field:       "allow_network",
        OldValue:    true,
        NewValue:    false,
        Reason:      "Security policy update",
    }

    // Broadcast to all active agents
    updater.BroadcastChange(change, agents)
}
```

### Example 4: Check Environment Status

```go
package main

import "architect/go_wrapper/stream"

func main() {
    config, _ := stream.LoadEnvironmentConfig("config/environments.json")
    devEnv := config.Environments[0]

    setup := stream.NewEnvironmentSetup(&devEnv, "status_checker")

    // Get status
    status, err := setup.GetStatus()
    if err != nil {
        panic(err)
    }

    fmt.Printf("Environment: %s\n", status.Name)
    fmt.Printf("Status: %s\n", status.Status)
    fmt.Printf("Active agents: %v\n", status.ActiveAgents)
    fmt.Printf("Size: %.2f MB\n", float64(status.WorkingDirSize)/(1024*1024))
}
```

## Demo

Run the environment config demo:

```bash
cd go_wrapper
go run cmd/environment_config_demo/main.go
```

**Demo Output:**
```
=== Environment Setup & Config Update Demo ===

### Demo 1: Automatic Environment Setup ###

--- Setting up dev environment ---
[Environment Setup] Creating working directory: /path/to/dev
[Environment Setup] ✓ Created /path/to/dev
[Environment Setup] ✓ Created data/feedback
[Environment Setup] ✓ Created data/patterns
...
[Environment Setup] ✓ Environment dev ready for config_demo_agent

### Demo 2: Dynamic Config Updates ###

--- Updating dev environment constraints ---
[Config Updater] ✓ Updated dev.max_file_size_mb: 100 → 150 (by config_demo)
[Config Updater] ✓ Added restricted path to dev: /tmp/sensitive (by config_demo)
...

### Demo 3: Broadcasting Changes to Agents ###

Active agents in dev environment: [config_demo_agent]
[Config Updater] ✓ Broadcast change to 1 agents

### Demo 4: Environment Status Tracking ###

--- dev Environment Status ---
Status: ready
Active agents: 1
  1. config_demo_agent
Working dir size: 0.05 MB
Databases ready: true
Last updated: 2026-02-09 18:00:00
```

## Benefits

### Automatic Setup
- No manual directory or database creation
- Consistent structure across all environments
- Proper permissions set automatically
- Environment variables configured automatically

### Dynamic Configuration
- Update constraints without restarting
- Track all changes with audit trail
- Rollback support with config backups
- Reason tracking for compliance

### Agent Coordination
- Know which agents are using which environments
- Broadcast configuration changes to all agents
- Track agent activity and resource usage
- Graceful cleanup when agents terminate

### Security
- Environment isolation prevents cross-contamination
- Restrictive file permissions (0750/0640)
- Constraint validation before operations
- Audit trail of all configuration changes

## Future Enhancements

1. **Environment Cloning**: Clone environments for testing
2. **Resource Quotas**: Disk space and memory limits per environment
3. **Scheduled Cleanup**: Automatic cleanup of old data
4. **Environment Migration**: Move agents between environments
5. **Health Checks**: Periodic validation of environment integrity
6. **Configuration Templates**: Pre-defined environment templates
7. **Remote Environments**: Support for distributed environments
8. **Encryption**: Encrypt sensitive environment data

## Files

```
go_wrapper/
├── stream/
│   ├── environment_manager.go          # Environment constraints enforcement
│   ├── environment_setup.go            # Automatic environment initialization
│   └── environment_config_updater.go   # Dynamic config updates & broadcasting
├── cmd/
│   └── environment_config_demo/
│       └── main.go                     # Demo application
├── config/
│   ├── environments.json               # Environment definitions
│   ├── environment_changes.jsonl       # Change audit log
│   └── notifications/                  # Agent notification files
└── ENVIRONMENT_SETUP.md                # This documentation
```

## License

Part of the Architect Dashboard project.
