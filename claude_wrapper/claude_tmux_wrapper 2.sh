#!/bin/bash
#
# Claude Code Tmux Wrapper - Runs Claude in tmux with automatic confirmation capture
#
# Usage:
#   ./claude_tmux_wrapper.sh                    # Start new session 'claude-agent'
#   ./claude_tmux_wrapper.sh --session NAME     # Use specific session name
#   ./claude_tmux_wrapper.sh --attach           # Attach to existing session
#
# The wrapper:
# 1. Creates/attaches to a tmux session
# 2. Runs Claude with output logging via `script`
# 3. Background process extracts confirmations in real-time
# 4. Unknown confirmation types are flagged for review
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/claude_logs"
CONFIRMATIONS_FILE="${SCRIPT_DIR}/claude_confirmations.md"
EXTRACT_SCRIPT="${SCRIPT_DIR}/extract_prompts.py"

SESSION_NAME="claude-agent"
ATTACH_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --session|-s)
            SESSION_NAME="$2"
            shift 2
            ;;
        --attach|-a)
            ATTACH_ONLY=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"

# Session-specific files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${LOG_DIR}/${SESSION_NAME}_${TIMESTAMP}.log"
CONFIRMATIONS_LOG="${LOG_DIR}/${SESSION_NAME}_confirmations.log"

# Function to extract confirmations from output in background
extract_confirmations() {
    local output_file="$1"
    local last_size=0

    while true; do
        if [ -f "$output_file" ]; then
            current_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)

            if [ "$current_size" -gt "$last_size" ]; then
                # New content - extract confirmations
                if [ -f "$EXTRACT_SCRIPT" ]; then
                    tail -c +$((last_size + 1)) "$output_file" | python3 "$EXTRACT_SCRIPT" --preview 2>/dev/null | tee -a "$CONFIRMATIONS_LOG"
                fi
                last_size=$current_size
            fi
        fi
        sleep 2
    done
}

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    if [ "$ATTACH_ONLY" = true ]; then
        echo "[Wrapper] Attaching to existing session: $SESSION_NAME"
        tmux attach -t "$SESSION_NAME"
        exit 0
    else
        echo "[Wrapper] Session '$SESSION_NAME' already exists."
        echo "[Wrapper] Use --attach to attach, or choose a different session name."
        echo ""
        echo "Active sessions:"
        tmux list-sessions
        exit 1
    fi
fi

echo "[Wrapper] Starting Claude in tmux session: $SESSION_NAME"
echo "[Wrapper] Output log: $OUTPUT_FILE"
echo "[Wrapper] Confirmations log: $CONFIRMATIONS_LOG"
echo ""

# Create the tmux session with claude wrapped in script command
# Using script to capture all output including ANSI codes
tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50

# Set up the session
tmux send-keys -t "$SESSION_NAME" "cd '$SCRIPT_DIR'" Enter
tmux send-keys -t "$SESSION_NAME" "echo '[Claude Wrapper] Starting session at $(date)' | tee '$OUTPUT_FILE'" Enter
tmux send-keys -t "$SESSION_NAME" "echo '[Claude Wrapper] Confirmations will be captured to: $CONFIRMATIONS_LOG'" Enter
tmux send-keys -t "$SESSION_NAME" "echo ''" Enter

# Start background confirmation extractor
extract_confirmations "$OUTPUT_FILE" &
EXTRACTOR_PID=$!
echo "[Wrapper] Background extractor PID: $EXTRACTOR_PID"

# Save PID for cleanup
echo "$EXTRACTOR_PID" > "${LOG_DIR}/${SESSION_NAME}_extractor.pid"

# Start claude with script to capture output
# The -q flag makes script quiet, -F flushes after each write
if [[ "$OSTYPE" == "darwin"* ]]; then
    tmux send-keys -t "$SESSION_NAME" "script -q -F '$OUTPUT_FILE' claude" Enter
else
    tmux send-keys -t "$SESSION_NAME" "script -q -f '$OUTPUT_FILE' -c claude" Enter
fi

echo ""
echo "[Wrapper] Session started. To attach:"
echo "  tmux attach -t $SESSION_NAME"
echo ""
echo "[Wrapper] Or use the Architecture Dashboard to send tasks."
echo ""

# Attach to the session
tmux attach -t "$SESSION_NAME"

# Cleanup when detached
if [ -f "${LOG_DIR}/${SESSION_NAME}_extractor.pid" ]; then
    kill $(cat "${LOG_DIR}/${SESSION_NAME}_extractor.pid") 2>/dev/null
    rm "${LOG_DIR}/${SESSION_NAME}_extractor.pid"
fi

echo ""
echo "[Wrapper] Session detached. Output saved to: $OUTPUT_FILE"

# Final extraction
if [ -f "$EXTRACT_SCRIPT" ] && [ -f "$OUTPUT_FILE" ]; then
    echo "[Wrapper] Extracting final confirmations..."
    python3 "$EXTRACT_SCRIPT" < "$OUTPUT_FILE"
fi
