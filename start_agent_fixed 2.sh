#!/bin/bash
# Start a functioning agent with Claude/Gemini (Fixed for remote nodes)

AGENT_NAME="$1"
AGENT_TOOL="$2"  # claude, gemini, or codex

if [ -z "$AGENT_NAME" ] || [ -z "$AGENT_TOOL" ]; then
    echo "Usage: $0 <agent-name> <tool>"
    echo "  tool: claude, gemini, or codex"
    exit 1
fi

echo "🚀 Starting agent: $AGENT_NAME with tool: $AGENT_TOOL"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source Gemini API key if exists
if [ -f "$SCRIPT_DIR/.env.gemini" ]; then
    source "$SCRIPT_DIR/.env.gemini"
fi

# Find tmux
TMUX_CMD=$(command -v tmux || echo "/usr/local/bin/tmux")

# Create tmux session with actual LLM running
case $AGENT_TOOL in
    gemini)
        echo "Starting Gemini agent..."
        $TMUX_CMD new-session -d -s "$AGENT_NAME" bash << 'TMUX_CMD'
echo '=================================='
echo "Agent: $AGENT_NAME"
echo 'Tool: Gemini'
echo 'File Locking: ENABLED'
echo '=================================='
echo ''
echo 'Ready to receive tasks!'
echo ''
if [ -n "$GEMINI_API_KEY" ]; then
    export GEMINI_API_KEY="$GEMINI_API_KEY"
    gemini --model gemini-pro
else
    echo "⚠️  GEMINI_API_KEY not set"
    bash
fi
TMUX_CMD
        ;;
    claude|codex)
        echo "Starting Claude agent..."
        $TMUX_CMD new-session -d -s "$AGENT_NAME" bash << 'TMUX_CMD'
echo '=================================='
echo "Agent: $AGENT_NAME"
echo 'Tool: Claude'
echo 'File Locking: ENABLED'
echo '=================================='
echo ''
echo 'Ready to receive tasks!'
echo ''
claude || bash
TMUX_CMD
        ;;
    *)
        echo "Unknown tool: $AGENT_TOOL"
        exit 1
        ;;
esac

echo "✅ Agent $AGENT_NAME started"
echo "📺 Attach with: $TMUX_CMD attach -t $AGENT_NAME"
