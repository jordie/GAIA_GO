#!/bin/bash
# Start the Claw browser automation agent on pink laptop
# This script should be run on the pink laptop (192.168.1.172)

AGENT_NAME="claw"

echo "🦞 Starting Claw Browser Automation Agent"
echo "=========================================="

# Check if running on pink laptop
if [[ "$(hostname)" != *"pink"* ]] && [[ "$(hostname)" != *"Pink"* ]]; then
    echo "⚠️  Warning: This script is designed to run on the pink laptop"
    echo "Current hostname: $(hostname)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if tmux session already exists
if tmux has-session -t "$AGENT_NAME" 2>/dev/null; then
    echo "❌ Agent '$AGENT_NAME' is already running"
    echo "📺 Attach with: tmux attach -t $AGENT_NAME"
    echo "💀 Kill with: tmux kill-session -t $AGENT_NAME"
    exit 1
fi

# Start the agent
echo "🚀 Starting Claw agent in tmux session..."

tmux new-session -d -s "$AGENT_NAME" "
    echo '=================================================='
    echo '🦞 Claw - Browser Automation Agent'
    echo 'Tool: OpenClaw'
    echo 'Node: Pink Laptop'
    echo 'File Locking: ENABLED'
    echo '=================================================='
    echo ''
    echo 'Ready to receive browser automation tasks!'
    echo ''
    echo 'Task Types:'
    echo '  • Web scraping'
    echo '  • Browser automation'
    echo '  • Form filling'
    echo '  • Screenshot capture'
    echo '  • Data extraction'
    echo ''
    echo 'When you receive a task:'
    echo '  1. Use file_lock_manager.py to acquire lock'
    echo '  2. Execute browser automation'
    echo '  3. Release the lock'
    echo ''

    # Check if OpenClaw is installed
    if command -v openclaw &> /dev/null; then
        echo '✅ OpenClaw found - starting...'
        openclaw
    elif command -v claw &> /dev/null; then
        echo '✅ Claw found - starting...'
        claw
    else
        echo '⚠️  OpenClaw/Claw not found on this system'
        echo ''
        echo 'Install OpenClaw:'
        echo '  pip install openclaw'
        echo ''
        echo 'Or install from source:'
        echo '  git clone https://github.com/openclaw/openclaw'
        echo '  cd openclaw && pip install -e .'
        echo ''
        echo 'Falling back to Claude for now...'
        echo 'Press any key to start Claude, or Ctrl+C to exit'
        read -n 1
        claude
    fi
"

# Wait a moment for session to start
sleep 1

# Check if session was created successfully
if tmux has-session -t "$AGENT_NAME" 2>/dev/null; then
    echo "✅ Claw agent started successfully"
    echo "📺 Attach with: tmux attach -t $AGENT_NAME"
    echo "📊 Monitor with: python3 workers/session_state_manager.py list"
    echo ""
    echo "To send tasks to Claw:"
    echo "  python3 agent_task_router.py assign \"<task>\" /path/to/workdir claw"
else
    echo "❌ Failed to start Claw agent"
    exit 1
fi
