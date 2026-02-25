#!/bin/bash
#
# Start Codex Worker in a tmux session
#
# This script sets up a codex_chat.py worker in a tmux session that can receive
# prompts from the assigner system.
#
# Usage:
#   ./scripts/start_codex_worker.sh                    # Start with default name 'codex'
#   ./scripts/start_codex_worker.sh codex_dev          # Start with custom session name
#   ./scripts/start_codex_worker.sh codex --provider ollama  # Use specific provider
#
# The worker will:
# - Run in worker mode (--worker flag)
# - Be detectable by the assigner worker
# - Process prompts sent via tmux send-keys
# - Report task completion back to the system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Default session name
SESSION_NAME="${1:-codex}"
shift 2>/dev/null || true

# Additional arguments (e.g., --provider ollama)
EXTRA_ARGS="$@"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists."
    echo "Use 'tmux attach -t $SESSION_NAME' to attach, or"
    echo "Use 'tmux kill-session -t $SESSION_NAME' to remove it first."
    exit 1
fi

# Create the tmux session
echo "Creating tmux session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME" -c "$BASE_DIR"

# Set up the environment
tmux send-keys -t "$SESSION_NAME" "cd '$BASE_DIR'" Enter
tmux send-keys -t "$SESSION_NAME" "export CODEX_SESSION='$SESSION_NAME'" Enter

# Activate virtual environment if it exists
if [ -d "$BASE_DIR/venv" ]; then
    tmux send-keys -t "$SESSION_NAME" "source venv/bin/activate" Enter
elif [ -d "$BASE_DIR/.venv" ]; then
    tmux send-keys -t "$SESSION_NAME" "source .venv/bin/activate" Enter
fi

# Start the codex worker
echo "Starting codex worker in session: $SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "python3 codex_chat.py --worker --session '$SESSION_NAME' $EXTRA_ARGS" Enter

echo ""
echo "Codex worker started in tmux session: $SESSION_NAME"
echo ""
echo "Commands:"
echo "  tmux attach -t $SESSION_NAME    # Attach to session"
echo "  tmux kill-session -t $SESSION_NAME  # Stop session"
echo ""
echo "To send prompts to this worker:"
echo "  python3 workers/assigner_worker.py --send \"Your prompt\" --target $SESSION_NAME"
echo ""
