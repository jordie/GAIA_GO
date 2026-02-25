#!/bin/bash
# Agent Wrapper with File Locking
# Wraps agent commands with automatic file locking for safe multi-agent operation

AGENT_NAME="$1"
WORK_DIR="$2"
COMMAND="${@:3}"

LOCK_MANAGER="/Users/jgirmay/Desktop/gitrepo/pyWork/architect/file_lock_manager.py"
LOCK_LOG="/tmp/agent_locks/${AGENT_NAME}.log"

# Create lock log directory
mkdir -p /tmp/agent_locks

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$AGENT_NAME] $1" | tee -a "$LOCK_LOG"
}

# Function to acquire lock before work
acquire_lock() {
    local dir="$1"
    log "🔒 Requesting lock on: $dir"

    # Use Python lock manager
    python3 "$LOCK_MANAGER" acquire "$AGENT_NAME" "$dir" 2>&1 | tee -a "$LOCK_LOG"

    if [ $? -eq 0 ]; then
        log "✅ Lock acquired on: $dir"
        return 0
    else
        log "❌ Failed to acquire lock on: $dir"
        return 1
    fi
}

# Function to release lock after work
release_lock() {
    local dir="$1"
    log "🔓 Releasing lock on: $dir"

    python3 "$LOCK_MANAGER" release "$AGENT_NAME" "$dir" 2>&1 | tee -a "$LOCK_LOG"

    if [ $? -eq 0 ]; then
        log "✅ Lock released on: $dir"
    else
        log "⚠️  Failed to release lock on: $dir"
    fi
}

# Trap to ensure lock release on exit
cleanup() {
    log "🧹 Cleanup triggered"
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        release_lock "$WORK_DIR"
    fi
}

trap cleanup EXIT INT TERM

# Main execution
log "========================================="
log "Agent: $AGENT_NAME"
log "Work Directory: $WORK_DIR"
log "Command: $COMMAND"
log "========================================="

# Validate work directory
if [ -z "$WORK_DIR" ]; then
    log "❌ Error: Work directory not specified"
    exit 1
fi

if [ ! -d "$WORK_DIR" ]; then
    log "⚠️  Work directory does not exist, creating: $WORK_DIR"
    mkdir -p "$WORK_DIR"
fi

# Acquire lock before starting work
if ! acquire_lock "$WORK_DIR"; then
    log "❌ Cannot proceed without lock"
    exit 1
fi

# Execute the command
log "🚀 Executing command..."
cd "$WORK_DIR" || exit 1

eval "$COMMAND"
EXIT_CODE=$?

log "📊 Command exit code: $EXIT_CODE"

# Lock will be released by cleanup trap
exit $EXIT_CODE
