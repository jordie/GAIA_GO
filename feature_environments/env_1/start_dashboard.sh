#!/bin/bash
# Start Web Dashboard in Feature Environment 1
# Isolated from main architect session

cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Stop any existing dashboard in this env
pkill -f "web_dashboard.py.*8081"

# Set environment variables
export FEATURE_ENV="env_1"
export WEB_DASHBOARD_PORT="8081"

# Start dashboard on port 8081
echo "Starting Web Dashboard on port 8081 (Feature Env 1)"
python3 web_dashboard.py --port 8081 > feature_environments/env_1/dashboard.log 2>&1 &

PID=$!
echo "Dashboard PID: $PID"
echo "$PID" > feature_environments/env_1/dashboard.pid

sleep 2

# Test if running
if curl -s http://localhost:8081/api/health > /dev/null; then
    echo "✅ Dashboard running at http://localhost:8081"
else
    echo "❌ Dashboard failed to start. Check logs:"
    tail -20 feature_environments/env_1/dashboard.log
fi
