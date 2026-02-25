#!/bin/bash
# Quick test script for Chrome extension browser automation

echo "🏗️  Architect Browser Agent Test"
echo "================================"
echo ""

# Check if websockets is installed
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "❌ websockets library not found"
    echo "Installing..."
    pip3 install websockets
fi

echo "✓ Dependencies OK"
echo ""

# Check if server is running
if ! nc -z localhost 8765 2>/dev/null; then
    echo "⚠️  WebSocket server not running on localhost:8765"
    echo ""
    echo "To start the server in another terminal:"
    echo "  python3 services/browser_ws_server.py"
    echo ""
    exit 1
fi

echo "✓ Server running on localhost:8765"
echo ""

# Check if extension is loaded
echo "Make sure Chrome extension is loaded:"
echo "  1. Open chrome://extensions/"
echo "  2. Enable Developer mode"
echo "  3. Load unpacked: chrome_extension/"
echo "  4. Click extension icon - should show '✓ Connected'"
echo ""
read -p "Press Enter when extension is loaded and connected..."
echo ""

# Run the test
GOAL="${1:-Find classes available for Saba on Wednesdays}"
URL="${2:-https://www.aquatechswim.com}"

echo "Running test:"
echo "  Goal: $GOAL"
echo "  URL: $URL"
echo ""

python3 workers/browser_automation/simple_planner.py "$GOAL" "$URL"
