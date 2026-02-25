#!/bin/bash
# Goal Engine Runner Script
#
# This script runs the goal engine to generate and queue tasks based on strategic vision.
# It's designed to be run via cron or manually.

set -e

# Change to project root
cd "$(dirname "$0")/.."

# Configuration
MAX_TASKS=${MAX_TASKS:-3}  # Maximum tasks to queue per run
LOG_FILE=${LOG_FILE:-/tmp/goal_engine.log}
DRY_RUN=${DRY_RUN:-false}

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting Goal Engine"

# Check if assigner worker is running
if ! pgrep -f "assigner_worker.py" > /dev/null; then
    log "WARNING: Assigner worker is not running. Tasks will queue but not execute."
fi

# Generate and queue tasks
if [ "$DRY_RUN" = "true" ]; then
    log "Running in DRY RUN mode (tasks will not be queued)"
    python3 orchestrator/goal_engine.py --dry-run | tee -a "$LOG_FILE"
else
    log "Generating and queuing up to $MAX_TASKS tasks"
    python3 orchestrator/goal_engine.py --generate --max-tasks "$MAX_TASKS" | tee -a "$LOG_FILE"
fi

# Learn from patterns weekly (only on Sundays)
if [ "$(date +%u)" -eq 7 ]; then
    log "Running pattern learning (weekly)"
    python3 orchestrator/goal_engine.py --learn | tee -a "$LOG_FILE"
fi

log "Goal Engine completed"

# Send notification if available
if command -v curl &> /dev/null && [ -n "$WEBHOOK_URL" ]; then
    curl -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Goal Engine completed: Generated tasks with max $MAX_TASKS\"}" \
        &> /dev/null || true
fi
