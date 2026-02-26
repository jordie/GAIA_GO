#!/bin/bash
#
# Start a Claude session with the wrapper in a tmux session.
#
# Usage:
#   ./start_wrapped_session.sh <session_name> [--auto-respond] [--approve-all]
#
# Examples:
#   ./start_wrapped_session.sh arch_dev --auto-respond
#   ./start_wrapped_session.sh edu_worker --approve-all
#   ./start_wrapped_session.sh worker1
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/claude_wrapper.py"

# Parse arguments
SESSION_NAME="${1:-claude_session}"
shift 2>/dev/null || true

AUTO_ARGS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto-respond|-a)
            AUTO_ARGS="$AUTO_ARGS --auto-respond"
            shift
            ;;
        --approve-all)
            AUTO_ARGS="$AUTO_ARGS --approve-all"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Check if tmux session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists."
    echo "Attaching..."
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

echo "Starting wrapped Claude session: $SESSION_NAME"
echo "Wrapper: $WRAPPER"
echo "Args: $AUTO_ARGS"

# Create new tmux session with the wrapper
tmux new-session -d -s "$SESSION_NAME" "python3 $WRAPPER $AUTO_ARGS"

echo "Session '$SESSION_NAME' created."
echo ""
echo "To attach: tmux attach -t $SESSION_NAME"
echo "To send task: tmux send-keys -t $SESSION_NAME '<task>' Enter"
echo ""

# Optionally attach
read -p "Attach now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    tmux attach-session -t "$SESSION_NAME"
fi
