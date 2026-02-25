#!/bin/bash

# Show what each environment is currently doing

echo "=================================="
echo "Environment Status Overview"
echo "=================================="
echo ""

ENVIRONMENTS=("dev1" "dev2" "dev3" "dev4" "dev5")
BASE_PATH="/Users/jgirmay/Desktop/gitrepo/pyWork"

for env in "${ENVIRONMENTS[@]}"; do
    ENV_PATH="$BASE_PATH/architect-$env"

    echo "📦 $env"
    echo "   Path: $ENV_PATH"

    if [ -d "$ENV_PATH" ]; then
        echo "   ✓ Directory exists"

        # Check git status
        cd "$ENV_PATH" 2>/dev/null
        if git rev-parse --git-dir > /dev/null 2>&1; then
            BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
            STATUS=$(git status --short 2>/dev/null | wc -l)
            echo "   Git: branch=$BRANCH, changes=$STATUS"
        fi

        # Check for running processes
        WORKER_PID=$(pgrep -f "${env}_worker" 2>/dev/null)
        if [ ! -z "$WORKER_PID" ]; then
            echo "   🔄 Worker running (PID: $WORKER_PID)"
        fi

        # Check dashboard
        PORT_DEV=$((8080 + ${env:3}))
        if lsof -Pi :$PORT_DEV -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "   🌐 Dashboard on port $PORT_DEV"
        fi
    else
        echo "   ❌ Directory not found"
    fi
    echo ""
done

echo "=================================="
echo "Current Session Overview"
echo "=================================="
echo ""

# Show active sessions
echo "Active tmux sessions:"
tmux list-sessions -F "#{session_name}: #{session_windows} window(s)" 2>/dev/null | head -15

echo ""
echo "Active Claude Code sessions:"
ps aux | grep "claude" | grep -v grep | wc -l
