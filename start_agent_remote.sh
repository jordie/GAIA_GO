#!/bin/bash
# Start agent on remote node with proper paths

AGENT_NAME="$1"
AGENT_TOOL="$2"

if [ -z "$AGENT_NAME" ] || [ -z "$AGENT_TOOL" ]; then
    echo "Usage: $0 <agent-name> <tool>"
    exit 1
fi

echo "🚀 Starting agent: $AGENT_NAME with tool: $AGENT_TOOL"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source environment
[ -f "$SCRIPT_DIR/.env.gemini" ] && source "$SCRIPT_DIR/.env.gemini"

# Use full path to tmux
TMUX="/opt/homebrew/bin/tmux"

case $AGENT_TOOL in
    gemini)
        echo "Starting Gemini agent..."
        $TMUX new-session -d -s "$AGENT_NAME" "
export GEMINI_API_KEY='${GEMINI_API_KEY}'
echo '=================================='
echo 'Agent: $AGENT_NAME'
echo 'Tool: Gemini'
echo 'Node: Pink Laptop'
echo '=================================='
echo 'Ready for tasks!'
echo ''
gemini --model gemini-pro 2>/dev/null || bash
"
        ;;
    claude|codex)
        echo "Starting Claude agent..."
        $TMUX new-session -d -s "$AGENT_NAME" "
echo '=================================='
echo 'Agent: $AGENT_NAME'
echo 'Tool: Claude'
echo 'Node: Pink Laptop'
echo '=================================='
echo 'Ready for tasks!'
echo ''
claude 2>/dev/null || bash
"
        ;;
    *)
        echo "Unknown tool: $AGENT_TOOL"
        exit 1
        ;;
esac

echo "✅ Agent $AGENT_NAME started"
echo "📺 Attach: $TMUX attach -t $AGENT_NAME"
