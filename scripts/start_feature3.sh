#!/bin/bash
# Feature 3 environment - Port 8087
# For feature development and testing

PORT=8087
ENV=feature3
PYTHON=/opt/homebrew/bin/python3
APP_DIR=/Users/jgirmay/Desktop/gitrepo/pyWork/architect
LOG=/tmp/architect_${ENV}.log

cd $APP_DIR

# Kill existing
pkill -f "APP_ENV=${ENV}.*app.py" 2>/dev/null
lsof -ti :$PORT | xargs kill -9 2>/dev/null
sleep 1

# Start
APP_ENV=$ENV PORT=$PORT $PYTHON app.py --ssl >> $LOG 2>&1 &

echo "Started Feature3 on https://0.0.0.0:$PORT"
echo "Database: data/${ENV}/architect.db"
echo "Log: $LOG"
