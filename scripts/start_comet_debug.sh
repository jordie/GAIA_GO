#!/bin/bash
#
# Start Comet with Remote Debugging
#
# This script starts the Comet app with remote debugging enabled on port 9222.
#
# Usage:
#   ./start_comet_debug.sh              # Start with default port 9222
#   ./start_comet_debug.sh 9223         # Start with custom port
#   ./start_comet_debug.sh --check      # Check if Comet debug is running
#   ./start_comet_debug.sh --stop       # Stop Comet

set -e

DEBUG_PORT="${1:-9222}"
COMET_PATH="/Applications/Comet.app/Contents/MacOS/Comet"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_debug() {
    if curl -s "http://localhost:$DEBUG_PORT/json" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

start_comet_debug() {
    if check_debug; then
        echo -e "${YELLOW}Debug already running on port $DEBUG_PORT${NC}"
        echo -e "Endpoint: ${GREEN}http://localhost:$DEBUG_PORT${NC}"
        return 0
    fi

    # Check if Comet is running without debug
    if pgrep -q "Comet"; then
        echo -e "${YELLOW}Comet is running without debug mode.${NC}"
        echo "Stopping Comet..."
        pkill -x "Comet" 2>/dev/null || true
        sleep 2
    fi

    if [[ ! -f "$COMET_PATH" ]]; then
        echo -e "${RED}Comet not found at: $COMET_PATH${NC}"
        exit 1
    fi

    echo -e "${GREEN}Starting Comet with remote debugging on port $DEBUG_PORT...${NC}"

    "$COMET_PATH" --remote-debugging-port=$DEBUG_PORT --remote-allow-origins=* &

    echo -n "Waiting for debug server..."
    for i in {1..30}; do
        if check_debug; then
            echo -e " ${GREEN}Ready!${NC}"
            echo -e "Debug endpoint: ${GREEN}http://localhost:$DEBUG_PORT${NC}"
            echo ""
            echo "To list targets: curl http://localhost:$DEBUG_PORT/json"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo -e " ${RED}Timeout!${NC}"
    exit 1
}

stop_comet() {
    echo "Stopping Comet..."
    pkill -x "Comet" 2>/dev/null || true
    echo -e "${GREEN}Comet stopped${NC}"
}

show_status() {
    echo "Comet Debug Status"
    echo "=================="
    if check_debug; then
        echo -e "Status: ${GREEN}Running${NC}"
        echo -e "Port: $DEBUG_PORT"
        echo ""
        echo "Available targets:"
        curl -s "http://localhost:$DEBUG_PORT/json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, page in enumerate(data[:10]):
    print(f\"  {i+1}. {page.get('title', 'Untitled')[:50]}\")
    print(f\"     {page.get('url', 'No URL')[:60]}\")
" 2>/dev/null || echo "  (Could not fetch)"
    else
        echo -e "Status: ${RED}Not Running${NC}"
    fi
}

case "$1" in
    --check|--status)
        show_status
        ;;
    --stop)
        stop_comet
        ;;
    --help|-h)
        echo "Usage: $0 [PORT|OPTION]"
        echo ""
        echo "Options:"
        echo "  [PORT]     Start with debugging on specified port (default: 9222)"
        echo "  --check    Check debug status"
        echo "  --stop     Stop Comet"
        ;;
    *)
        start_comet_debug
        ;;
esac
