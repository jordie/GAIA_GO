#!/bin/bash
#
# Start Chrome with Remote Debugging
#
# This script starts Chrome with remote debugging enabled on port 9222,
# using the user's default profile (which includes extensions like Comet).
#
# Usage:
#   ./start_chrome_debug.sh              # Start with default port 9222
#   ./start_chrome_debug.sh 9223         # Start with custom port
#   ./start_chrome_debug.sh --check      # Check if Chrome debug is running
#   ./start_chrome_debug.sh --stop       # Stop Chrome debug instance
#

set -e

# Default port
DEBUG_PORT="${1:-9222}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    USER_DATA_DIR="$HOME/Library/Application Support/Google/Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CHROME_PATH="/usr/bin/google-chrome"
    USER_DATA_DIR="$HOME/.config/google-chrome"
else
    echo -e "${RED}Unsupported platform: $OSTYPE${NC}"
    exit 1
fi

check_chrome_debug() {
    # Check if Chrome with debugging is running
    if curl -s "http://localhost:$DEBUG_PORT/json" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

start_chrome_debug() {
    # Check if already running
    if check_chrome_debug; then
        echo -e "${YELLOW}Chrome debug already running on port $DEBUG_PORT${NC}"
        echo -e "Debug endpoint: ${GREEN}http://localhost:$DEBUG_PORT${NC}"
        return 0
    fi

    # Check if Chrome executable exists
    if [[ ! -f "$CHROME_PATH" ]]; then
        echo -e "${RED}Chrome not found at: $CHROME_PATH${NC}"
        echo "Please install Google Chrome or update the path in this script."
        exit 1
    fi

    echo -e "${GREEN}Starting Chrome with remote debugging on port $DEBUG_PORT...${NC}"
    echo "Using profile: $USER_DATA_DIR"

    # Start Chrome with debugging
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - open in background
        "$CHROME_PATH" \
            --remote-debugging-port=$DEBUG_PORT \
            --user-data-dir="$USER_DATA_DIR" \
            --no-first-run \
            --no-default-browser-check \
            &
    else
        # Linux
        "$CHROME_PATH" \
            --remote-debugging-port=$DEBUG_PORT \
            --user-data-dir="$USER_DATA_DIR" \
            --no-first-run \
            --no-default-browser-check \
            &
    fi

    # Wait for Chrome to start
    echo -n "Waiting for Chrome debug server..."
    for i in {1..30}; do
        if check_chrome_debug; then
            echo -e " ${GREEN}Ready!${NC}"
            echo -e "Debug endpoint: ${GREEN}http://localhost:$DEBUG_PORT${NC}"
            echo ""
            echo "To view debug info, open: http://localhost:$DEBUG_PORT/json"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo -e " ${RED}Timeout!${NC}"
    echo "Chrome debug server did not start within 30 seconds."
    echo "Check if another Chrome instance is already running."
    exit 1
}

stop_chrome_debug() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Find and kill Chrome processes with debug port
        pids=$(pgrep -f "remote-debugging-port=$DEBUG_PORT" || true)
        if [[ -n "$pids" ]]; then
            echo "Stopping Chrome debug instances..."
            echo "$pids" | xargs kill 2>/dev/null || true
            echo -e "${GREEN}Chrome debug stopped${NC}"
        else
            echo -e "${YELLOW}No Chrome debug instance found on port $DEBUG_PORT${NC}"
        fi
    else
        pkill -f "remote-debugging-port=$DEBUG_PORT" 2>/dev/null || true
        echo -e "${GREEN}Chrome debug stopped${NC}"
    fi
}

show_status() {
    echo "Chrome Debug Status"
    echo "==================="
    if check_chrome_debug; then
        echo -e "Status: ${GREEN}Running${NC}"
        echo -e "Port: $DEBUG_PORT"
        echo -e "Endpoint: http://localhost:$DEBUG_PORT"
        echo ""
        echo "Available pages:"
        curl -s "http://localhost:$DEBUG_PORT/json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, page in enumerate(data[:5]):
    print(f\"  {i+1}. {page.get('title', 'Untitled')[:50]}\")
    print(f\"     {page.get('url', 'No URL')[:60]}\")
" 2>/dev/null || echo "  (Could not fetch page list)"
    else
        echo -e "Status: ${RED}Not Running${NC}"
        echo ""
        echo "To start: $0"
    fi
}

# Handle arguments
case "$1" in
    --check|--status)
        show_status
        ;;
    --stop)
        stop_chrome_debug
        ;;
    --help|-h)
        echo "Usage: $0 [PORT|OPTION]"
        echo ""
        echo "Options:"
        echo "  [PORT]     Start Chrome with debugging on specified port (default: 9222)"
        echo "  --check    Check if Chrome debug is running"
        echo "  --status   Show debug status and open pages"
        echo "  --stop     Stop Chrome debug instance"
        echo "  --help     Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0              # Start with default port 9222"
        echo "  $0 9223         # Start with port 9223"
        echo "  $0 --check      # Check status"
        ;;
    *)
        start_chrome_debug
        ;;
esac
