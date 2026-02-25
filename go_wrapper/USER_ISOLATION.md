## User-Based Isolation System

## Overview

The user-based isolation system enforces **strict separation between workers and managers** using Unix user accounts. Each agent runs as a specific Unix user with their own:

- Home directory and workspace
- Git credentials and SSH keys
- File access permissions
- Environment isolation

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Manager (architect_manager / wrapper_manager)               │
│  Role: Coordinate, test, delegate                            │
│  Access: Read-only to worker spaces, full access to own      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ Delegates tasks
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Workers (dev_worker1, dev_worker2, etc.)                    │
│  Role: Write code, make commits, implement features          │
│  Access: Full access to own workspace, shared git repo       │
└──────────────────────────────────────────────────────────────┘

Each user has:
┌─────────────────────────────────────────────────────────────┐
│  /home/<username>/                                          │
│  ├── .ssh/                  # SSH keys (0700)               │
│  │   └── id_rsa             # Private key (0600)            │
│  ├── .gitconfig             # Git credentials               │
│  └── workspace/             # Working directory (0750)      │
│      ├── data/              # Databases and logs            │
│      ├── logs/              # Agent logs                    │
│      └── repos/             # Git repositories              │
└─────────────────────────────────────────────────────────────┘

Shared Git Repository:
┌─────────────────────────────────────────────────────────────┐
│  /path/to/architect/                                        │
│  Owner: current_user                                         │
│  Group: architect_workers                                   │
│  Permissions: 775 (rwxrwxr-x)                               │
│  SGID bit: Set (new files inherit group)                    │
│                                                              │
│  All workers in architect_workers group can:                │
│  - Read all files                                            │
│  - Write/modify files                                        │
│  - Create commits                                            │
│  - Push changes                                              │
└─────────────────────────────────────────────────────────────┘
```

## Roles

### Workers
**Purpose**: Execute actual development work - write code, make commits, implement features

**Permissions**:
- ✅ Full read/write access to own workspace
- ✅ Read/write access to shared git repository
- ✅ Can create commits with own git credentials
- ✅ Can push to remote branches
- ❌ Cannot access other workers' private workspaces
- ❌ Cannot modify system files

**Example Workers**:
- `dev_worker1` - General development work
- `dev_worker2` - Parallel development tasks
- `concurrent_worker1` - Concurrent feature development
- `edu_worker1` - Educational app features

### Managers
**Purpose**: Coordinate work, test, delegate tasks

**Permissions**:
- ✅ Read access to worker outputs
- ✅ Can test code
- ✅ Can delegate tasks to workers
- ✅ Read access to shared git repository
- ❌ Should not write code directly
- ❌ Should not make commits (workers do that)

**Example Managers**:
- `architect_manager` - High-level coordination
- `wrapper_manager` - Wrapper system management

## Components

### 1. User Manager (`stream/user_manager.go`)

Manages Unix users for workers and managers.

**Key Features**:
- Create Unix users with `useradd`
- Setup home directories and workspaces
- Configure git credentials per user
- Setup SSH keys
- Manage group permissions for shared repos
- Save/load user configurations

**Key Methods**:
```go
um := NewUserManager("config/worker_users.json")

// Create worker with git credentials
gitConfig := stream.GitConfig{
    Name:  "Dev Worker 1",
    Email: "dev.worker1@architect.local",
    Token: "ghp_xxxxx", // Optional
}
um.CreateWorkerUser("dev_worker1", "worker", gitConfig)

// Get user info
user, _ := um.GetUser("dev_worker1")

// List workers
workers := um.ListWorkers()

// Setup shared git repository
um.SetupSharedGitRepo("/path/to/architect", "architect_workers",
    []string{"dev_worker1", "dev_worker2"})
```

### 2. User Process Wrapper (`stream/user_process_wrapper.go`)

Starts agent processes as specific Unix users using `sudo`.

**Key Features**:
- Run process as specified user via `sudo -u`
- Set user's environment variables
- Use user's workspace as working directory
- Track user, role, and git config
- Log all operations with user context

**Key Methods**:
```go
// Create wrapper for worker
wrapper, err := NewUserProcessWrapper(
    "agent_name",
    "dev_worker1",  // Username
    "logs",
    "dev",          // Environment
    "claude",       // Command
    "--version",    // Args...
)

// Start process as user
wrapper.Start()

// Wait for completion
wrapper.Wait()

// Get user info
username := wrapper.GetUsername()
role := wrapper.GetRole()
workspace := wrapper.GetWorkspace()
gitConfig := wrapper.GetGitConfig()
```

### 3. Setup Script (`cmd/setup_workers/main.go`)

Command-line tool to create and manage worker/manager users.

**Usage**:
```bash
# Create standard workers and managers
sudo go run cmd/setup_workers/main.go

# Interactive mode
sudo go run cmd/setup_workers/main.go --interactive

# List existing users
./bin/setup_workers --list

# Setup shared git repository
sudo ./bin/setup_workers --setup-repo /path/to/architect --group architect_workers
```

## User Configuration Format

Users are stored in `config/worker_users.json`:

```json
{
  "dev_worker1": {
    "username": "dev_worker1",
    "uid": "1001",
    "gid": "1001",
    "home_dir": "/home/dev_worker1",
    "workspace_dir": "/home/dev_worker1/workspace",
    "role": "worker",
    "git_config": {
      "name": "Dev Worker 1",
      "email": "dev.worker1@architect.local",
      "token": ""
    },
    "ssh_key_path": "/home/dev_worker1/.ssh/id_rsa",
    "metadata": {}
  },
  "architect_manager": {
    "username": "architect_manager",
    "uid": "1002",
    "gid": "1002",
    "home_dir": "/home/architect_manager",
    "workspace_dir": "/home/architect_manager/workspace",
    "role": "manager",
    "git_config": {
      "name": "Architect Manager",
      "email": "architect@architect.local"
    },
    "ssh_key_path": "/home/architect_manager/.ssh/id_rsa",
    "metadata": {}
  }
}
```

## Setup Instructions

### Step 1: Create Workers and Managers

Run the setup script with sudo privileges:

```bash
cd go_wrapper

# Build setup tool
go build -o bin/setup_workers cmd/setup_workers/main.go

# Create standard users
sudo ./bin/setup_workers

# Or create custom user interactively
sudo ./bin/setup_workers --interactive
```

**Output**:
```
=== Setting Up Standard Workers & Managers ===

Creating worker: dev_worker1
[User Manager] Creating Unix user: dev_worker1 (role: worker)
[User Manager] ✓ Created user dev_worker1 (UID: 1001, Home: /home/dev_worker1)
[User Manager] Setting up environment for dev_worker1
[User Manager] ✓ Git configured for dev_worker1 (dev.worker1@architect.local)
[User Manager] ✓ Environment ready for dev_worker1
  ✓ Created dev_worker1

Creating worker: dev_worker2
...

Creating manager: architect_manager
...

=== Setup Complete ===
```

### Step 2: Setup Shared Git Repository

Configure the shared repository so all workers can commit:

```bash
# Setup shared repo
sudo ./bin/setup_workers --setup-repo /Users/jgirmay/Desktop/gitrepo/pyWork/architect --group architect_workers
```

**What this does**:
1. Creates `architect_workers` group
2. Adds all workers to the group
3. Sets repository group to `architect_workers`
4. Sets permissions to `775` (rwxrwxr-x)
5. Sets SGID bit so new files inherit group

**Output**:
```
=== Setting Up Shared Git Repository ===

Repository: /Users/jgirmay/Desktop/gitrepo/pyWork/architect
Group: architect_workers

Workers: [dev_worker1 dev_worker2 dev_worker3 concurrent_worker1 edu_worker1]

[User Manager] Setting up shared git repo: /Users/jgirmay/Desktop/gitrepo/pyWork/architect
[User Manager] ✓ Shared repo configured for group architect_workers
✓ Shared repository configured

All workers can now commit to the repository:
  - dev_worker1
  - dev_worker2
  - dev_worker3
  - concurrent_worker1
  - edu_worker1
```

### Step 3: Verify Setup

List all registered users:

```bash
./bin/setup_workers --list
```

**Output**:
```
=== Registered Users ===

Workers (5):
  - dev_worker1 (UID: 1001)
    Home: /home/dev_worker1
    Workspace: /home/dev_worker1/workspace
    Git: Dev Worker 1 <dev.worker1@architect.local>

  - dev_worker2 (UID: 1002)
    Home: /home/dev_worker2
    Workspace: /home/dev_worker2/workspace
    Git: Dev Worker 2 <dev.worker2@architect.local>

  ...

Managers (2):
  - architect_manager (UID: 1006)
    Home: /home/architect_manager
    Git: Architect Manager <architect@architect.local>

  ...
```

## Running Agents as Specific Users

### Example 1: Start Agent as Worker

```go
package main

import (
    "github.com/architect/go_wrapper/stream"
)

func main() {
    // Create wrapper to run as dev_worker1
    wrapper, err := stream.NewUserProcessWrapper(
        "dev_agent",      // Agent name
        "dev_worker1",    // Run as this user
        "logs",           // Log directory
        "dev",            // Environment
        "claude",         // Command
        "code",           // Args...
    )
    if err != nil {
        panic(err)
    }

    // Start process
    if err := wrapper.Start(); err != nil {
        panic(err)
    }

    // Wait for completion
    wrapper.Wait()
}
```

### Example 2: Delegate Task to Worker

From a manager session, delegate work to a worker:

```bash
# Manager delegates to worker
python3 workers/assigner_worker.py \
  --send "Implement user authentication feature" \
  --target dev_worker1 \
  --priority 8
```

The assigner will:
1. Find dev_worker1's tmux session
2. Send the task
3. The wrapper starts Claude as `dev_worker1` Unix user
4. Claude runs with dev_worker1's credentials
5. Any commits use dev_worker1's git config

## Security Benefits

### 1. File Access Isolation
- Workers cannot access each other's private workspaces
- Each user has `0700` home directory permissions
- SSH keys are `0600` (readable only by owner)

### 2. Git Commit Attribution
- Each worker has unique git credentials
- Commits are properly attributed to the worker
- Git history shows who worked on what

### 3. Audit Trail
- All file operations logged with username
- Feedback tracker records which user performed actions
- Easy to trace who did what

### 4. Limited Privileges
- Workers run with regular user privileges (not root)
- Cannot modify system files
- Cannot access other users' data

### 5. Shared Repository Control
- Group-based permissions for collaboration
- SGID ensures consistent group ownership
- All workers can commit, but with their own identity

## Workflow Examples

### Worker Makes a Commit

```bash
# Running as dev_worker1
cd /home/dev_worker1/workspace/repos/architect

# Make changes
vim app.py

# Commit with dev_worker1's credentials
git add app.py
git commit -m "Add authentication feature"
# Author: Dev Worker 1 <dev.worker1@architect.local>

# Push
git push origin feature/auth
```

### Manager Coordinates

```bash
# Manager reviews work
cd /path/to/architect
git log --author="dev.worker1"

# Manager tests
pytest tests/

# Manager delegates next task
python3 workers/assigner_worker.py \
  --send "Fix failing authentication tests" \
  --target dev_worker2
```

## Permission Matrix

| Operation | Worker | Manager | Notes |
|-----------|--------|---------|-------|
| Read own workspace | ✅ Full | ✅ Full | Each user controls their workspace |
| Write own workspace | ✅ Full | ✅ Full | |
| Read shared repo | ✅ Full | ✅ Full | All can read repository |
| Write shared repo | ✅ Full | ❌ No | Workers write code |
| Create commits | ✅ Yes | ❌ No | Workers make commits |
| Read other workspaces | ❌ No | ⚠️ Limited | Requires sudo |
| Run tests | ✅ Yes | ✅ Yes | Both can test |
| Deploy | ⚠️ Via script | ✅ Yes | Controlled deployment |

## Troubleshooting

### sudo: command not found
Install sudo or run as root:
```bash
su -
useradd -m -s /bin/bash dev_worker1
```

### Permission denied accessing shared repo
Check group membership:
```bash
groups dev_worker1
# Should include: architect_workers

# If not, add to group
sudo usermod -a -G architect_workers dev_worker1
```

### Git commits use wrong credentials
Verify git config for user:
```bash
sudo -u dev_worker1 git config --global user.name
sudo -u dev_worker1 git config --global user.email
```

### Worker cannot push to remote
Setup SSH key for worker:
```bash
# Generate SSH key
sudo -u dev_worker1 ssh-keygen -t rsa -b 4096 -f /home/dev_worker1/.ssh/id_rsa -N ""

# Add public key to GitHub/GitLab
sudo cat /home/dev_worker1/.ssh/id_rsa.pub
```

### SGID bit not set on repository
Set it manually:
```bash
sudo chmod g+s /path/to/architect
sudo chmod -R g+rwX /path/to/architect
```

## Best Practices

### 1. One Worker Per Feature
- Assign each feature to a specific worker
- Clear attribution in git history
- Easy to track progress

### 2. Managers Coordinate, Workers Execute
- Managers should not write production code
- Managers delegate to appropriate workers
- Workers focus on implementation

### 3. Regular User Audits
- Review which users exist
- Remove inactive users
- Check workspace disk usage

### 4. Git Credentials Per Environment
- Dev workers use dev credentials
- Staging workers use staging credentials
- Prod workers use prod credentials (read-only)

### 5. Workspace Cleanup
- Archive old workspaces periodically
- Workers clean up temporary files
- Managers monitor disk usage

## Future Enhancements

1. **Resource Limits**: Use `ulimit` to restrict worker CPU/memory
2. **Audit Logging**: Log all file access by workers
3. **Automated Backups**: Backup worker workspaces
4. **Worker Rotation**: Rotate SSH keys and credentials
5. **Container Isolation**: Use Docker for stronger isolation
6. **SELinux/AppArmor**: Additional mandatory access control

## Files

```
go_wrapper/
├── stream/
│   ├── user_manager.go           # Unix user management
│   └── user_process_wrapper.go   # Process wrapper with user switching
├── cmd/
│   └── setup_workers/
│       └── main.go                # Worker setup CLI tool
├── config/
│   └── worker_users.json          # User configuration
└── USER_ISOLATION.md              # This documentation
```

## License

Part of the Architect Dashboard project.
