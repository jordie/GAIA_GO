#!/bin/bash
#
# Start Autonomous Development System
#
# Starts all components:
# 1. Comet with debug mode (for Perplexity)
# 2. Project Orchestrator daemon
# 3. Perplexity Sheets daemon
# 4. Auto-confirm worker
#
# Usage:
#   ./start_autonomous.sh          # Start all
#   ./start_autonomous.sh status   # Check status
#   ./start_autonomous.sh stop     # Stop all
#   ./start_autonomous.sh restart  # Restart all

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

check_comet() {
    curl -s "http://localhost:9222/json" > /dev/null 2>&1
}

start_comet() {
    log "Starting Comet with debug mode..."

    if check_comet; then
        echo -e "${YELLOW}Comet already running${NC}"
        return 0
    fi

    # Clean up locks
    rm -f "$HOME/Library/Application Support/Comet/SingletonLock" 2>/dev/null || true

    # Kill existing Comet
    pkill -x "Comet" 2>/dev/null || true
    sleep 2

    # Start Comet
    "$SCRIPT_DIR/start_comet_debug.sh"

    if check_comet; then
        echo -e "${GREEN}Comet started${NC}"
        return 0
    else
        echo -e "${RED}Failed to start Comet${NC}"
        return 1
    fi
}

start_orchestrator() {
    log "Starting Project Orchestrator..."

    if [ -f /tmp/project_orchestrator.pid ]; then
        pid=$(cat /tmp/project_orchestrator.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Orchestrator already running (PID $pid)${NC}"
            return 0
        fi
    fi

    cd "$PROJECT_DIR"
    nohup python3 workers/project_orchestrator.py --daemon > /tmp/project_orchestrator_out.log 2>&1 &
    sleep 2

    if [ -f /tmp/project_orchestrator.pid ]; then
        pid=$(cat /tmp/project_orchestrator.pid)
        echo -e "${GREEN}Orchestrator started (PID $pid)${NC}"
    else
        echo -e "${RED}Failed to start Orchestrator${NC}"
    fi
}

start_perplexity_sheets() {
    log "Starting Perplexity Sheets daemon..."

    if [ -f /tmp/perplexity_sheets.pid ]; then
        pid=$(cat /tmp/perplexity_sheets.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Perplexity Sheets already running (PID $pid)${NC}"
            return 0
        fi
    fi

    cd "$PROJECT_DIR"
    nohup python3 workers/perplexity_sheets.py --daemon > /tmp/perplexity_sheets_out.log 2>&1 &
    sleep 2

    if [ -f /tmp/perplexity_sheets.pid ]; then
        pid=$(cat /tmp/perplexity_sheets.pid)
        echo -e "${GREEN}Perplexity Sheets started (PID $pid)${NC}"
    else
        echo -e "${RED}Failed to start Perplexity Sheets${NC}"
    fi
}

start_autoconfirm() {
    log "Starting Auto-confirm worker..."

    # Check if running
    if pgrep -f "auto_confirm_worker.py" > /dev/null; then
        echo -e "${YELLOW}Auto-confirm already running${NC}"
        return 0
    fi

    # Start in tmux session
    if ! tmux has-session -t autoconfirm 2>/dev/null; then
        tmux new-session -d -s autoconfirm
    fi

    cd "$PROJECT_DIR"
    tmux send-keys -t autoconfirm "python3 workers/auto_confirm_worker.py" Enter
    sleep 2

    if pgrep -f "auto_confirm_worker.py" > /dev/null; then
        echo -e "${GREEN}Auto-confirm started${NC}"
    else
        echo -e "${RED}Failed to start Auto-confirm${NC}"
    fi
}

show_status() {
    echo ""
    echo -e "${BLUE}=== Autonomous Development System Status ===${NC}"
    echo ""

    # Comet
    if check_comet; then
        targets=$(curl -s "http://localhost:9222/json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
        echo -e "Comet:              ${GREEN}Running${NC} ($targets targets)"
    else
        echo -e "Comet:              ${RED}Stopped${NC}"
    fi

    # Orchestrator
    if [ -f /tmp/project_orchestrator.pid ]; then
        pid=$(cat /tmp/project_orchestrator.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "Orchestrator:       ${GREEN}Running${NC} (PID $pid)"
        else
            echo -e "Orchestrator:       ${RED}Stopped${NC} (stale PID)"
        fi
    else
        echo -e "Orchestrator:       ${RED}Stopped${NC}"
    fi

    # Perplexity Sheets
    if [ -f /tmp/perplexity_sheets.pid ]; then
        pid=$(cat /tmp/perplexity_sheets.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "Perplexity Sheets:  ${GREEN}Running${NC} (PID $pid)"
        else
            echo -e "Perplexity Sheets:  ${RED}Stopped${NC} (stale PID)"
        fi
    else
        echo -e "Perplexity Sheets:  ${RED}Stopped${NC}"
    fi

    # Auto-confirm
    if pgrep -f "auto_confirm_worker.py" > /dev/null; then
        pid=$(pgrep -f "auto_confirm_worker.py" | head -1)
        echo -e "Auto-confirm:       ${GREEN}Running${NC} (PID $pid)"
    else
        echo -e "Auto-confirm:       ${RED}Stopped${NC}"
    fi

    echo ""
    echo -e "${BLUE}=== Recent Activity ===${NC}"
    echo ""
    echo "Orchestrator log:"
    tail -5 /tmp/project_orchestrator.log 2>/dev/null || echo "  (no log)"
    echo ""
    echo "Perplexity Sheets log:"
    tail -3 /tmp/perplexity_sheets.log 2>/dev/null || echo "  (no log)"
    echo ""
}

stop_all() {
    log "Stopping all components..."

    # Stop orchestrator
    if [ -f /tmp/project_orchestrator.pid ]; then
        pid=$(cat /tmp/project_orchestrator.pid)
        kill "$pid" 2>/dev/null && echo -e "${GREEN}Stopped Orchestrator${NC}"
        rm -f /tmp/project_orchestrator.pid
    fi

    # Stop perplexity sheets
    if [ -f /tmp/perplexity_sheets.pid ]; then
        pid=$(cat /tmp/perplexity_sheets.pid)
        kill "$pid" 2>/dev/null && echo -e "${GREEN}Stopped Perplexity Sheets${NC}"
        rm -f /tmp/perplexity_sheets.pid
    fi

    # Stop auto-confirm
    pkill -f "auto_confirm_worker.py" 2>/dev/null && echo -e "${GREEN}Stopped Auto-confirm${NC}"

    # Optionally stop Comet
    # pkill -x "Comet" 2>/dev/null && echo -e "${GREEN}Stopped Comet${NC}"

    echo -e "${GREEN}All components stopped${NC}"
}

start_all() {
    echo ""
    echo -e "${BLUE}=== Starting Autonomous Development System ===${NC}"
    echo ""

    start_comet
    sleep 2
    start_autoconfirm
    sleep 1
    start_perplexity_sheets
    sleep 1
    start_orchestrator

    echo ""
    show_status

    echo ""
    echo -e "${GREEN}System started!${NC}"
    echo ""
    echo "Google Sheet: https://docs.google.com/spreadsheets/d/12i2uO6-41uZdHl_a9BbhBHhR1qbNlAqOgH-CWQBz7rA"
    echo ""
    echo "Add tasks to the 'Orchestrator' sheet with status 'pending'"
    echo "The system will:"
    echo "  1. Research solutions via Perplexity"
    echo "  2. Send implementation to Claude Code tmux sessions"
    echo "  3. Monitor completion and create follow-up tasks"
    echo ""
}

case "${1:-start}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
