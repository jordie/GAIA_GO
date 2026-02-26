#!/bin/bash
#
# setup_tmux_sessions.sh - Set up standard tmux sessions for Architect project
#
# Usage:
#   ./setup_tmux_sessions.sh           # Create all sessions
#   ./setup_tmux_sessions.sh --check   # Show session status without creating
#   ./setup_tmux_sessions.sh --kill-all # Kill all Architect sessions
#   ./setup_tmux_sessions.sh --help    # Show this help
#

set -e

# Configuration
WORK_DIR="/Users/jgirmay/Desktop/gitrepo/pyWork/architect"
CLAUDE_CMD="claude"

# Session definitions
SESSIONS=(
    "command_runner:Main management session"
    "autoconfirm:Auto-confirmation worker"
    "health_monitor:Server health monitor"
    "server_manager:Server management"
    "task_worker1:Task worker 1"
    "task_worker2:Task worker 2"
    "task_worker3:Task worker 3"
    "task_worker4:Task worker 4"
    "task_worker5:Task worker 5"
    "arch_prod:Production environment worker"
    "arch_qa:QA environment worker"
    "arch_dev:Development environment worker"
    "arch_env3:Environment 3 worker"
    "audit_manager:Audit and SOP management"
    "assigner_worker:Prompt assigner and dispatcher"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Set up standard tmux sessions for the Architect project."
    echo ""
    echo "Options:"
    echo "  --check      Show session status without creating"
    echo "  --kill-all   Kill all Architect sessions"
    echo "  --list       List all session names"
    echo "  --help       Show this help message"
    echo ""
    echo "Sessions created:"
    for session_def in "${SESSIONS[@]}"; do
        name="${session_def%%:*}"
        desc="${session_def#*:}"
        printf "  %-16s %s\n" "$name" "$desc"
    done
    echo ""
    echo "Each session will:"
    echo "  - Be created in directory: $WORK_DIR"
    echo "  - Start claude automatically"
}

# Check if a session exists
session_exists() {
    tmux has-session -t "$1" 2>/dev/null
}

# Get session status
check_sessions() {
    echo -e "${BLUE}=== Architect tmux Session Status ===${NC}"
    echo ""

    local running=0
    local stopped=0

    for session_def in "${SESSIONS[@]}"; do
        name="${session_def%%:*}"
        desc="${session_def#*:}"

        if session_exists "$name"; then
            echo -e "  ${GREEN}●${NC} $name - ${GREEN}running${NC} ($desc)"
            ((running++))
        else
            echo -e "  ${RED}○${NC} $name - ${RED}not running${NC} ($desc)"
            ((stopped++))
        fi
    done

    echo ""
    echo -e "${BLUE}Summary:${NC} $running running, $stopped not running"
    echo ""

    # Also show any other tmux sessions
    local other_sessions=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | grep -v -E "^($(IFS='|'; echo "${SESSIONS[*]%%:*}"))\$" || true)
    if [ -n "$other_sessions" ]; then
        echo -e "${YELLOW}Other tmux sessions:${NC}"
        echo "$other_sessions" | while read -r sess; do
            echo "  - $sess"
        done
    fi
}

# Kill all Architect sessions
kill_all_sessions() {
    echo -e "${YELLOW}=== Killing all Architect tmux sessions ===${NC}"
    echo ""

    local killed=0

    for session_def in "${SESSIONS[@]}"; do
        name="${session_def%%:*}"

        if session_exists "$name"; then
            echo -e "  Killing ${RED}$name${NC}..."
            tmux kill-session -t "$name" 2>/dev/null || true
            ((killed++))
        fi
    done

    if [ $killed -eq 0 ]; then
        echo "  No sessions to kill."
    else
        echo ""
        echo -e "${GREEN}Killed $killed session(s).${NC}"
    fi
}

# List session names only
list_sessions() {
    for session_def in "${SESSIONS[@]}"; do
        echo "${session_def%%:*}"
    done
}

# Create a single session
create_session() {
    local name="$1"
    local desc="$2"

    if session_exists "$name"; then
        echo -e "  ${YELLOW}⊘${NC} $name - already exists, skipping"
        return 0
    fi

    echo -e "  ${GREEN}+${NC} Creating $name ($desc)..."

    # Create detached session with working directory
    tmux new-session -d -s "$name" -c "$WORK_DIR"

    # Small delay to ensure session is ready
    sleep 0.2

    # Start claude in the session
    tmux send-keys -t "$name" "$CLAUDE_CMD" Enter

    echo -e "    ${GREEN}✓${NC} Started claude in $name"
}

# Create all sessions
create_all_sessions() {
    echo -e "${BLUE}=== Setting up Architect tmux sessions ===${NC}"
    echo ""
    echo "Working directory: $WORK_DIR"
    echo ""

    # Verify working directory exists
    if [ ! -d "$WORK_DIR" ]; then
        echo -e "${RED}Error: Working directory does not exist: $WORK_DIR${NC}"
        exit 1
    fi

    # Verify claude command exists
    if ! command -v "$CLAUDE_CMD" &> /dev/null; then
        echo -e "${YELLOW}Warning: '$CLAUDE_CMD' command not found in PATH${NC}"
        echo "Sessions will be created but claude may not start correctly."
        echo ""
    fi

    local created=0
    local skipped=0

    for session_def in "${SESSIONS[@]}"; do
        name="${session_def%%:*}"
        desc="${session_def#*:}"

        if session_exists "$name"; then
            echo -e "  ${YELLOW}⊘${NC} $name - already exists"
            ((skipped++))
        else
            create_session "$name" "$desc"
            ((created++))
        fi
    done

    echo ""
    echo -e "${GREEN}Done!${NC} Created $created session(s), skipped $skipped existing."
    echo ""
    echo "To attach to a session:"
    echo "  tmux attach -t <session_name>"
    echo ""
    echo "To check status:"
    echo "  $0 --check"
}

# Main
main() {
    case "${1:-}" in
        --help|-h)
            usage
            ;;
        --check|-c)
            check_sessions
            ;;
        --kill-all|-k)
            kill_all_sessions
            ;;
        --list|-l)
            list_sessions
            ;;
        "")
            create_all_sessions
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo ""
            usage
            exit 1
            ;;
    esac
}

main "$@"
