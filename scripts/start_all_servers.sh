#!/bin/bash
# EDU Apps Master Startup Script for LaunchDaemon
# Starts DEV, QA, PROD servers in tmux sessions
# Binds to 0.0.0.0 for Tailscale accessibility
export PATH=~/homebrew/bin:$PATH

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing servers on our ports
sleep 5
lsof -i :5051 -t | xargs kill -9 2>/dev/null
lsof -i :5052 -t | xargs kill -9 2>/dev/null
lsof -i :5063 -t | xargs kill -9 2>/dev/null
sleep 2

# Kill existing tmux sessions
tmux kill-session -t dev 2>/dev/null
tmux kill-session -t qa 2>/dev/null
tmux kill-session -t prod 2>/dev/null

# Start servers using individual startup scripts
tmux new-session -d -s dev  "$SCRIPT_DIR/start_dev.sh"
tmux new-session -d -s qa   "$SCRIPT_DIR/start_qa.sh"
tmux new-session -d -s prod "$SCRIPT_DIR/start_prod.sh"

echo "EDU Apps started at $(date)" >> ~/edu_startup.log
echo "DEV:  https://0.0.0.0:5051/"
echo "QA:   https://0.0.0.0:5052/"
echo "PROD: https://0.0.0.0:5063/"
