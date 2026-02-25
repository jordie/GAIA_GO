#!/bin/bash
# Feature Environment 1 - Week 2 Advanced Features
# Port: 8081 (to avoid conflict with main dashboard on 8080)

export FEATURE_ENV="env_1"
export WEB_DASHBOARD_PORT="8081"
export DATA_DIR="$PWD/feature_environments/env_1/data"

# Create isolated data directory
mkdir -p "$DATA_DIR"

echo "=================================="
echo "Feature Environment 1 - Week 2"
echo "=================================="
echo "Port: $WEB_DASHBOARD_PORT"
echo "Data Dir: $DATA_DIR"
echo "Branch: feature/week2-advanced-features-0214"
echo "=================================="
