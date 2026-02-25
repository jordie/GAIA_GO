#!/bin/bash
#
# Start GAIA Workers - AI worker sessions using gaia.py
#
# This script starts multiple AI worker sessions in tmux, each using
# GAIA (Generic AI Agent) which automatically routes between Claude,
# Ollama, and Gemini based on rate limits.
#
# Usage:
#   ./scripts/start_ai_workers.sh              # Start default workers
#   ./scripts/start_ai_workers.sh --all        # Start all defined workers
#   ./scripts/start_ai_workers.sh worker1      # Start specific worker
#   ./scripts/start_ai_workers.sh --stop       # Stop all workers
#   ./scripts/start_ai_workers.sh --status     # Show status
#
# GAIA features:
#   - Auto-selects best backend (Claude → Ollama → Gemini)
#   - Detects rate limits from CLI output and auto-switches
#   - Falls back when Claude is at 80% of limit
#   - Uses fastest Ollama endpoint (local or pinklaptop)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Default workers to start
DEFAULT_WORKERS=(
    "dev_worker1"
    "dev_worker2"
    "codex"
)

# All available workers
ALL_WORKERS=(
    "dev_worker1"
    "dev_worker2"
    "dev_worker3"
    "codex"
    "qa_tester1"
    "qa_tester2"
    "mcp_worker1"
    "concurrent_worker1"
    "concurrent_worker2"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

start_worker() {
    local name="$1"
    local extra_args="${2:-}"

    if tmux has-session -t "$name" 2>/dev/null; then
        echo -e "${YELLOW}Session '$name' already exists${NC}"
        return 0
    fi

    echo -e "${GREEN}Starting worker: $name${NC}"
    tmux new-session -d -s "$name" -c "$BASE_DIR"

    # Setup environment
    tmux send-keys -t "$name" "cd '$BASE_DIR'" Enter

    # Activate venv if exists
    if [ -d "$BASE_DIR/venv" ]; then
        tmux send-keys -t "$name" "source venv/bin/activate" Enter
    elif [ -d "$BASE_DIR/.venv" ]; then
        tmux send-keys -t "$name" "source .venv/bin/activate" Enter
    fi

    # Start GAIA
    tmux send-keys -t "$name" "python3 gaia.py --session '$name' $extra_args" Enter

    echo -e "${GREEN}  Started: $name${NC}"
}

stop_worker() {
    local name="$1"
    if tmux has-session -t "$name" 2>/dev/null; then
        tmux kill-session -t "$name"
        echo -e "${RED}Stopped: $name${NC}"
    fi
}

show_status() {
    echo ""
    echo "AI Worker Status"
    echo "================"
    echo ""

    # Show rate limit status
    python3 "$BASE_DIR/services/rate_limit_handler.py" 2>/dev/null || echo "Rate limiter not available"

    echo ""
    echo "Worker Sessions:"
    echo "----------------"

    for name in "${ALL_WORKERS[@]}"; do
        if tmux has-session -t "$name" 2>/dev/null; then
            # Check if ai_worker is running
            if tmux capture-pane -t "$name" -p 2>/dev/null | grep -q "ai>"; then
                echo -e "  ${GREEN}$name: RUNNING (idle)${NC}"
            elif tmux capture-pane -t "$name" -p 2>/dev/null | grep -q "Thinking"; then
                echo -e "  ${YELLOW}$name: RUNNING (busy)${NC}"
            else
                echo -e "  ${GREEN}$name: RUNNING${NC}"
            fi
        else
            echo -e "  ${RED}$name: STOPPED${NC}"
        fi
    done

    echo ""
    echo "Commands:"
    echo "  tmux attach -t <name>     # Attach to worker"
    echo "  tmux list-sessions        # List all sessions"
}

# Parse arguments
case "${1:-}" in
    --all)
        echo "Starting all AI workers..."
        for name in "${ALL_WORKERS[@]}"; do
            start_worker "$name"
        done
        echo ""
        echo "All workers started. Use 'tmux attach -t <name>' to attach."
        ;;

    --stop)
        echo "Stopping all AI workers..."
        for name in "${ALL_WORKERS[@]}"; do
            stop_worker "$name"
        done
        ;;

    --status)
        show_status
        ;;

    --help|-h)
        echo "Usage: $0 [OPTIONS] [WORKER_NAME...]"
        echo ""
        echo "Options:"
        echo "  --all       Start all defined workers"
        echo "  --stop      Stop all workers"
        echo "  --status    Show worker status"
        echo "  --help      Show this help"
        echo ""
        echo "Workers:"
        for name in "${ALL_WORKERS[@]}"; do
            echo "  $name"
        done
        ;;

    "")
        # Start default workers
        echo "Starting default AI workers..."
        for name in "${DEFAULT_WORKERS[@]}"; do
            start_worker "$name"
        done
        echo ""
        echo "Workers started. Use './scripts/start_ai_workers.sh --status' to check."
        ;;

    *)
        # Start specific worker(s)
        for name in "$@"; do
            start_worker "$name"
        done
        ;;
esac
