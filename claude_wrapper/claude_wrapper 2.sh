#!/bin/bash
#
# Claude Code Wrapper - Captures permission prompts automatically
#
# Usage:
#   ./claude_wrapper.sh              # Start Claude with prompt logging
#   ./claude_wrapper.sh --no-log     # Start without logging
#   ./claude_wrapper.sh [args]       # Pass args to claude
#
# The wrapper:
# 1. Runs Claude Code with output captured via `script`
# 2. After session ends, extracts permission prompts
# 3. Appends prompts to claude_confirmations.md
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/claude_confirmations.md"
OUTPUT_FILE="/tmp/claude_session_$$.txt"
EXTRACT_SCRIPT="${SCRIPT_DIR}/extract_prompts.py"

NO_LOG=false

# Parse our args
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-log)
            NO_LOG=true
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [ "$NO_LOG" = false ] && [ -f "$OUTPUT_FILE" ]; then
        echo ""
        echo "[Wrapper] Extracting prompts from session..."

        # Run the extractor
        if [ -f "$EXTRACT_SCRIPT" ]; then
            python3 "$EXTRACT_SCRIPT" < "$OUTPUT_FILE"
        else
            echo "[Wrapper] Warning: extract_prompts.py not found"
        fi
    fi

    # Keep the output file for debugging
    if [ -f "$OUTPUT_FILE" ]; then
        echo "[Wrapper] Session output saved to: $OUTPUT_FILE"
    fi
}

trap cleanup EXIT

echo "[Wrapper] Starting Claude Code with prompt capture..."
echo "[Wrapper] Output will be logged to: $OUTPUT_FILE"
echo ""

# Use script to capture output while preserving interactivity
# -q: quiet mode (don't print start/end messages)
# -F: flush after each write
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS version of script
    script -q "$OUTPUT_FILE" claude "$@"
else
    # Linux version of script
    script -q -c "claude $*" "$OUTPUT_FILE"
fi

echo ""
echo "[Wrapper] Session ended."
