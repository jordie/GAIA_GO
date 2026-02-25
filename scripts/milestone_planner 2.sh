#!/bin/bash
# Milestone Planner Helper Script
#
# Manages the milestone planning worker for the Architect dashboard.
#
# Usage:
#   ./milestone_planner.sh start          # Start worker as daemon
#   ./milestone_planner.sh stop           # Stop worker
#   ./milestone_planner.sh status         # Check status
#   ./milestone_planner.sh scan           # Run immediate scan
#   ./milestone_planner.sh scan <project> # Scan specific project
#   ./milestone_planner.sh logs           # Show logs
#   ./milestone_planner.sh clean          # Clean old milestone files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
WORKER_SCRIPT="$BASE_DIR/workers/milestone_worker.py"
PID_FILE="/tmp/architect_milestone_worker.pid"
LOG_FILE="/tmp/architect_milestone_worker.log"
MILESTONES_DIR="$BASE_DIR/data/milestones"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure milestones directory exists
mkdir -p "$MILESTONES_DIR"

case "${1:-}" in
    start)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo -e "${YELLOW}Milestone worker already running (PID: $PID)${NC}"
                exit 0
            else
                echo "Removing stale PID file"
                rm "$PID_FILE"
            fi
        fi

        echo -e "${GREEN}Starting milestone worker...${NC}"
        python3 "$WORKER_SCRIPT" --daemon
        sleep 1

        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo -e "${GREEN}Milestone worker started (PID: $PID)${NC}"
            echo "Logs: $LOG_FILE"
        else
            echo -e "${RED}Failed to start worker${NC}"
            exit 1
        fi
        ;;

    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo -e "${YELLOW}Milestone worker not running${NC}"
            exit 0
        fi

        PID=$(cat "$PID_FILE")
        echo -e "${YELLOW}Stopping milestone worker (PID: $PID)...${NC}"

        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID"
            sleep 2

            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Worker didn't stop gracefully, forcing..."
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi

        rm -f "$PID_FILE"
        echo -e "${GREEN}Milestone worker stopped${NC}"
        ;;

    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p "$PID" > /dev/null 2>&1; then
                echo -e "${GREEN}Milestone worker is running (PID: $PID)${NC}"
                echo ""
                ps -p "$PID" -o pid,ppid,etime,cmd
                echo ""
                echo "Recent activity:"
                tail -5 "$LOG_FILE" 2>/dev/null || echo "No logs yet"
            else
                echo -e "${RED}Milestone worker not running (stale PID file)${NC}"
                rm "$PID_FILE"
                exit 1
            fi
        else
            echo -e "${YELLOW}Milestone worker not running${NC}"
            exit 1
        fi
        ;;

    scan)
        PROJECT="${2:-}"
        echo -e "${GREEN}Running immediate milestone scan...${NC}"

        if [ -n "$PROJECT" ]; then
            echo "Project: $PROJECT"
            python3 "$WORKER_SCRIPT" --scan --project "$PROJECT"
        else
            echo "Scanning all active projects"
            python3 "$WORKER_SCRIPT" --scan
        fi

        echo ""
        echo -e "${GREEN}Scan complete!${NC}"
        echo "Results in: $MILESTONES_DIR"
        ls -lth "$MILESTONES_DIR" | head -10
        ;;

    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo -e "${YELLOW}No log file found${NC}"
            exit 1
        fi
        ;;

    clean)
        echo -e "${YELLOW}Cleaning old milestone files...${NC}"

        # Keep only last 30 days
        find "$MILESTONES_DIR" -name "*.json" -mtime +30 -delete
        find "$MILESTONES_DIR" -name "*.md" -mtime +30 -delete

        echo -e "${GREEN}Cleanup complete${NC}"
        echo "Remaining files:"
        ls -lth "$MILESTONES_DIR" | head -10
        ;;

    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;

    *)
        echo "Milestone Planner Helper"
        echo ""
        echo "Usage:"
        echo "  $0 start              Start worker as daemon"
        echo "  $0 stop               Stop worker"
        echo "  $0 restart            Restart worker"
        echo "  $0 status             Check worker status"
        echo "  $0 scan               Scan all projects now"
        echo "  $0 scan <project>     Scan specific project"
        echo "  $0 logs               Tail log file"
        echo "  $0 clean              Remove old milestone files"
        echo ""
        echo "Active Projects (4):"
        echo "  - architect"
        echo "  - claude_browser_agent"
        echo "  - basic_edu_apps_final"
        echo "  - mentor_v2"
        echo ""
        echo "Output: $MILESTONES_DIR"
        exit 1
        ;;
esac
