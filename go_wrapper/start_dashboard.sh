#!/bin/bash
# Start Dashboard Server
# Supports environment-specific ports: DEV (8151), QA (8152), PROD (8163)

# Determine port based on environment
ENV=${APP_ENV:-dev}

case $ENV in
    dev)
        PORT=8151
        ;;
    qa)
        PORT=8152
        ;;
    prod)
        PORT=8163
        ;;
    *)
        PORT=8151  # Default to DEV
        ;;
esac

echo "=== Go Wrapper Dashboard ==="
echo ""
echo "Environment: $ENV"
echo "Port: $PORT"
echo ""
echo "Starting API server with dashboard..."
echo ""

./apiserver --port $PORT &
API_PID=$!

sleep 2

if ! kill -0 $API_PID 2>/dev/null; then
    echo "✗ Failed to start server"
    exit 1
fi

echo "✓ Server started (PID: $API_PID)"
echo ""
echo "Dashboard URLs:"
echo "  Main Dashboard:  http://localhost:$PORT/"
echo "  Enhanced:        http://localhost:$PORT/enhanced"
echo "  SSE Test Client: http://localhost:$PORT/test-sse"
echo ""
echo "API Endpoints:"
echo "  Health:          http://localhost:$PORT/api/health"
echo "  Agents:          http://localhost:$PORT/api/agents"
echo "  Metrics:         http://localhost:$PORT/metrics"
echo "  SSE Stats:       http://localhost:$PORT/api/sse/stats"
echo ""
echo "To use different environment:"
echo "  APP_ENV=dev ./start_dashboard.sh   # Port 8151"
echo "  APP_ENV=qa ./start_dashboard.sh    # Port 8152"
echo "  APP_ENV=prod ./start_dashboard.sh  # Port 8163"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping server...'; kill $API_PID 2>/dev/null; exit 0" INT

wait $API_PID
